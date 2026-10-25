"""Website API: what the Discord bot does, for the Next.js site.

Only the site's server calls this, never a browser. Each request is signed with a
shared secret and names the signed-in Discord user, so nobody can act as someone else:

    X-Haggle-User:      Discord user id (from the site's Discord login)
    X-Haggle-Timestamp: unix seconds; requests older than 5 minutes are refused
    X-Haggle-Signature: hex HMAC-SHA256 over
                        "{timestamp}\\n{method}\\n{path}\\n{query}\\n{user}\\n{sha256(body)}"

Private limits are encrypted here the moment they arrive. Responses never carry
ciphertext, task tokens, execution ids or anyone else's identity.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from functools import cache

import boto3
from boto3.dynamodb.conditions import Attr, Key

import badges
import game
import store
from categories import CATEGORIES
from interactions import (
    ACTIVE_DEAL,
    AREAS,
    CLOSED_DEAL,
    MAX_PRICE,
    PAUSED,
    cancel_booking,
    is_paused,
    parse_price,
    parse_style,
    save_user_defaults,
    stop_deal,
    user_defaults,
)
from scheduler import format_slot, load_places

log = logging.getLogger()
log.setLevel(logging.INFO)

MAX_SKEW_SECONDS = 300
MAX_PHOTO_BYTES = 10 * 1024 * 1024
PHOTO_URL_SECONDS = 3600
BROWSE_LIMIT = 60
UPLOAD_PREFIX = "uploads/"
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
PRIVATE_FIELDS = re.compile(
    r"(_enc$|token|execution_arn|photo_url|upload_key|^seller_id$|^buyer_id$|windows)"
)


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- AWS clients and secrets


@cache
def _s3():
    return boto3.client("s3")


@cache
def _lambda():
    return boto3.client("lambda")


@cache
def _hmac_secret() -> bytes:
    resp = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["WEB_SECRET_ARN"])
    return json.loads(resp["SecretString"])["hmac_secret"].encode()


# ---------- Request signing


def canonical(ts: str, method: str, path: str, query: str, user: str, body: bytes) -> bytes:
    digest = hashlib.sha256(body).hexdigest()
    return f"{ts}\n{method.upper()}\n{path}\n{query}\n{user}\n{digest}".encode()


def sign(secret: bytes, *parts) -> str:
    return hmac.new(secret, canonical(*parts), hashlib.sha256).hexdigest()


def authenticate(event: dict, body: bytes) -> str:
    """The signed-in Discord user id, or ApiError(401)."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    user = headers.get("x-haggle-user", "")
    ts = headers.get("x-haggle-timestamp", "")
    signature = headers.get("x-haggle-signature", "")
    if not (user.isdigit() and ts.isdigit() and signature):
        raise ApiError(401, "missing signature")
    if abs(time.time() - int(ts)) > MAX_SKEW_SECONDS:
        raise ApiError(401, "stale request")
    http = event["requestContext"]["http"]
    expected = sign(
        _hmac_secret(), ts, http["method"], event["rawPath"], event.get("rawQueryString", ""),
        user, body,
    )  # fmt: skip
    if not hmac.compare_digest(expected, signature):
        raise ApiError(401, "bad signature")
    return user


# ---------- Shaping responses


def _public(item: dict) -> dict:
    """Drop anything private and make DynamoDB numbers JSON-friendly."""
    out = {}
    for k, v in item.items():
        if PRIVATE_FIELDS.search(k):
            continue
        if hasattr(v, "as_integer_ratio") and not isinstance(v, bool):
            v = int(v) if v == int(v) else float(v)
        out[k] = v
    return out


def _photo_url(item: dict) -> str | None:
    if not item.get("photo_key"):
        return None
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["PHOTOS_BUCKET"], "Key": item["photo_key"]},
        ExpiresIn=PHOTO_URL_SECONDS,
    )


def listing_card(item: dict, viewer: str, seller: dict | None = None) -> dict:
    card = _public(item)
    card.pop("photo_key", None)
    card.pop("seller_notes", None)
    card["photo"] = _photo_url(item)
    card["mine"] = item["seller_id"] == viewer
    card["seller_badges"] = badges.badges(seller)
    return card


def _deal_view(deal: dict, viewer: str) -> dict:
    view = _public(deal)
    hidden = ("last_text", "last_offer", "handoff_", "ladder", "reward_")
    for k in [k for k in view if k.startswith(hidden)]:
        view.pop(k)
    view["side"] = "seller" if deal["seller_id"] == viewer else "buyer"
    view["has_recap"] = bool(deal.get(f"reward_{view['side']}", {}).get("points"))
    if deal.get("slot_start"):
        view["pickup"] = f"{format_slot(datetime.fromisoformat(deal['slot_start']))}, " + (
            deal.get("spot_name", "")
        )
    return view


# ---------- Handlers


def _body_json(body: bytes) -> dict:
    try:
        data = json.loads(body or b"{}")
    except json.JSONDecodeError as e:
        raise ApiError(400, "body must be JSON") from e
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    return data


def _get_listing(listing_id: str) -> dict:
    item = store.table("listings").get_item(Key={"listing_id": listing_id}).get("Item")
    if not item:
        raise ApiError(404, "listing not found")
    return item


def _price(data: dict, field: str, label: str) -> int:
    value = parse_price(str(data.get(field, "")))
    if value is None:
        raise ApiError(400, f"{label} must be a whole dollar amount between $1 and ${MAX_PRICE}")
    return value


def _area(data: dict, user: dict) -> str:
    area = str(data.get("area") or user.get("campus_area") or "any").lower()
    if area not in AREAS:
        raise ApiError(400, f"area must be one of {', '.join(AREAS)}")
    return area


def _style(data: dict, user: dict) -> str:
    style = parse_style(str(data.get("style") or user.get("style") or "balanced"))
    if style is None:
        raise ApiError(400, "style must be patient, balanced or quick")
    return style


def browse(user_id: str, query: dict) -> dict:
    """Open listings, newest first, with optional category / area / text filters."""
    resp = store.table("listings").query(
        IndexName="by_status",
        KeyConditionExpression=Key("status").eq("open"),
        ScanIndexForward=False,
        Limit=200,
    )
    items = resp.get("Items", [])
    category, area = query.get("category"), query.get("area")
    words = [w for w in re.findall(r"[a-z0-9]+", (query.get("q") or "").lower())]
    if category in CATEGORIES:
        items = [i for i in items if i.get("category") == category]
    if area in AREAS and area != "any":
        items = [i for i in items if i.get("area") in (area, "any")]
    if words:

        def text(i: dict) -> str:
            return f"{i.get('title', '')} {i.get('description', '')}".lower()

        items = [i for i in items if all(w in text(i) for w in words)]
    sort = query.get("sort")
    if sort == "price_asc":
        items.sort(key=lambda i: i["asking"])
    elif sort == "price_desc":
        items.sort(key=lambda i: i["asking"], reverse=True)
    items = items[:BROWSE_LIMIT]
    sellers = store.get_users({i["seller_id"] for i in items})
    return {
        "listings": [listing_card(i, user_id, sellers.get(i["seller_id"])) for i in items],
        "categories": list(CATEGORIES),
        "areas": list(AREAS),
    }


def listing_detail(user_id: str, listing_id: str) -> dict:
    item = _get_listing(listing_id)
    mine = item["seller_id"] == user_id
    if item["status"] not in ("open", "sold") and not mine:
        raise ApiError(404, "listing not found")
    seller = store.table("users").get_item(Key={"user_id": item["seller_id"]}).get("Item")
    card = listing_card(item, user_id, seller)
    deals = store.table("deals").query(
        IndexName="by_listing", KeyConditionExpression=Key("listing_id").eq(listing_id)
    )["Items"]
    mine_deal = next(
        (d for d in deals if d["buyer_id"] == user_id and d.get("state") not in CLOSED_DEAL),
        None,
    )
    card["my_deal"] = _deal_view(mine_deal, user_id) if mine_deal else None
    if mine:
        card["rejected_reason"] = item.get("rejected_reason")
    return card


def create_upload(user_id: str, data: dict) -> dict:
    """A presigned POST so the browser uploads the photo straight to S3."""
    content_type = str(data.get("content_type", "")).lower()
    if content_type not in PHOTO_TYPES:
        raise ApiError(400, "photo must be a JPG, PNG, WebP or HEIC image")
    key = f"{UPLOAD_PREFIX}{user_id}/{uuid.uuid4().hex}"
    post = _s3().generate_presigned_post(
        Bucket=os.environ["PHOTOS_BUCKET"],
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, MAX_PHOTO_BYTES],
        ],
        ExpiresIn=600,
    )
    return {"upload": post, "key": key}


def create_listing(user_id: str, data: dict) -> dict:
    if is_paused(user_id):
        raise ApiError(403, PAUSED)
    user = user_defaults(user_id)
    key = str(data.get("photo_key", ""))
    if not key.startswith(f"{UPLOAD_PREFIX}{user_id}/"):
        raise ApiError(400, "upload a photo first")
    description = str(data.get("description", "")).strip()[:300]
    if not description:
        raise ApiError(400, "add a few words about the item")
    asking = _price(data, "asking", "Asking price")
    floor = _price(data, "floor", "Lowest price")
    if floor > asking:
        raise ApiError(400, "your lowest price can't be above your asking price")
    area, style = _area(data, user), _style(data, user)
    windows = str(data.get("windows", "")).strip()[:500]

    listing_id = store.new_id("lst")
    store.table("listings").put_item(
        Item={
            "listing_id": listing_id,
            "seller_id": user_id,
            "seller_notes": description,
            "asking": asking,
            "area": area,
            "upload_key": key,
            "style": style,
            "windows_text": windows,
            "floor_enc": store.encrypt_limit(floor, f"listing#{listing_id}", user_id),
            "status": "processing",
            "source": "web",
            "created_at": store.now_iso(),
        }
    )
    save_user_defaults(user_id, area, windows, style)
    _run("sell", listing_id=listing_id)
    return {"listing_id": listing_id, "status": "processing"}


def _owned_transition(user_id: str, listing_id: str, expect: str, to: str) -> None:
    try:
        store.table("listings").update_item(
            Key={"listing_id": listing_id},
            UpdateExpression="SET #s = :to",
            ConditionExpression=Attr("seller_id").eq(user_id) & Attr("status").eq(expect),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":to": to},
        )
    except store.conditional_failed() as e:
        raise ApiError(409, "that listing can't do that right now") from e


def publish(user_id: str, listing_id: str) -> dict:
    _owned_transition(user_id, listing_id, "preview", "publishing")
    _run("publish", listing_id=listing_id)
    return {"listing_id": listing_id, "status": "publishing"}


def discard(user_id: str, listing_id: str) -> dict:
    _owned_transition(user_id, listing_id, "preview", "cancelled")
    return {"listing_id": listing_id, "status": "cancelled"}


def stop_listing(user_id: str, listing_id: str) -> dict:
    item = _get_listing(listing_id)
    if item["seller_id"] != user_id or item["status"] not in ("preview", "open"):
        raise ApiError(409, "that listing can't be stopped")
    _owned_transition(user_id, listing_id, item["status"], "stopped")
    return {"listing_id": listing_id, "status": "stopped"}


def express_interest(user_id: str, listing_id: str, data: dict) -> dict:
    """The website's 'Interested': a budget range starts a negotiation in Discord."""
    if is_paused(user_id):
        raise ApiError(403, PAUSED)
    listing = _get_listing(listing_id)
    if listing["status"] != "open":
        raise ApiError(409, "this item is no longer available")
    if listing["seller_id"] == user_id:
        raise ApiError(400, "that's your own listing")
    existing = store.table("deals").query(
        IndexName="by_listing", KeyConditionExpression=Key("listing_id").eq(listing_id)
    )["Items"]
    if any(d["buyer_id"] == user_id and d.get("state") in ACTIVE_DEAL for d in existing):
        raise ApiError(409, "you're already haggling for this")

    user = user_defaults(user_id)
    low = _price(data, "min", "The low end of your budget")
    high = _price(data, "max", "Your max")
    if low > high:
        raise ApiError(400, "the low end of your budget can't be above your max")
    if low >= int(listing["asking"]):
        raise ApiError(400, "the low end of your budget should be below the asking price")
    area, style = _area(data, user), _style(data, user)
    windows = str(data.get("windows", "")).strip()[:500]

    want_id = store.new_id("wnt")
    store.table("wants").put_item(
        Item={
            "want_id": want_id,
            "buyer_id": user_id,
            "listing_id": listing_id,
            "query": listing.get("title", ""),
            "category": listing.get("category", "other"),
            "area": area,
            "style": style,
            "windows_text": windows,
            "opening": low,
            "ceiling_enc": store.encrypt_limit(high, f"want#{want_id}", user_id),
            # Not "open": the matcher only pairs open wants, and this one already has
            # its listing.
            "status": "processing",
            "source": "web",
            "created_at": store.now_iso(),
        }
    )
    save_user_defaults(user_id, area, windows, style)
    _run("interest", want_id=want_id)
    return {"want_id": want_id, "status": "starting"}


def my_haggle(user_id: str) -> dict:
    """The signed-in student's listings, interests, deals and badges."""

    def mine(table: str, index: str, key: str) -> list[dict]:
        return store.table(table).query(
            IndexName=index,
            KeyConditionExpression=Key(key).eq(user_id),
            ScanIndexForward=False,
            Limit=50,
        )["Items"]

    listings = [
        listing_card(i, user_id)
        for i in mine("listings", "by_seller", "seller_id")
        if i["status"] not in ("draft", "cancelled")
    ]
    deals = mine("deals", "by_seller", "seller_id") + mine("deals", "by_buyer", "buyer_id")
    deals.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    user = user_defaults(user_id)
    return {
        "profile": {
            "badges": badges.badges(user),
            "stats": badges.stats(user),
            "area": user.get("campus_area", "any"),
            "windows": user.get("default_windows", ""),
            "style": user.get("style", "balanced"),
            "paused": is_paused(user_id),
            "game": game.profile(user),
        },
        "listings": listings,
        "deals": [_deal_view(d, user_id) for d in deals if d.get("state") != "passed"],
    }


def update_preferences(user_id: str, data: dict) -> dict:
    user = user_defaults(user_id)
    area, style = _area(data, user), _style(data, user)
    windows = str(data.get("windows", user.get("default_windows", ""))).strip()[:500]
    save_user_defaults(user_id, area, windows, style)
    return {"area": area, "windows": windows, "style": style}


BOARD_STATES = ("negotiating", "scheduling", "confirming", "confirmed", "done")
BOARD_ROWS = 12


def board(user_id: str) -> dict:
    """Recent deals for the live board.

    Other students' deals show only status, round count and, once both sides have
    confirmed, the sold price: live offers would let a third buyer see how far a
    seller has already conceded. The viewer's own deals show their live offers.
    """
    items = store.table("deals").scan(
        FilterExpression=Attr("state").is_in(list(BOARD_STATES)),
        ProjectionExpression=(
            "deal_id, listing_id, title, asking, #s, #r, agreed_price, seller_id, buyer_id, "
            "last_offer_seller, last_offer_buyer, updated_at, created_at"
        ),
        ExpressionAttributeNames={"#s": "state", "#r": "round"},
    )["Items"]
    items.sort(key=lambda d: d.get("updated_at") or d.get("created_at", ""), reverse=True)
    rows = []
    for d in items[:BOARD_ROWS]:
        mine = user_id in (d.get("seller_id"), d.get("buyer_id"))
        sold = d["state"] in ("confirmed", "done")
        row = {
            "deal_id": d["deal_id"] if mine else None,
            "listing_id": d["listing_id"],
            "title": d.get("title", ""),
            "asking": int(d["asking"]),
            "state": d["state"],
            "rounds": int(d.get("round", 0)),
            "price": int(d["agreed_price"])
            if d.get("agreed_price") is not None and (sold or mine)
            else None,
            "mine": mine,
            "updated_at": d.get("updated_at") or d.get("created_at"),
        }
        if mine:
            row["side"] = "seller" if d.get("seller_id") == user_id else "buyer"
            for side in ("seller", "buyer"):
                offer = d.get(f"last_offer_{side}")
                row[f"{side}_offer"] = int(offer) if offer is not None else None
        rows.append(row)
    return {"rows": rows}


def campus_places(user_id: str) -> dict:
    """Zones and public meeting spots for the website's map."""
    places = load_places()
    return {"areas": places["areas"], "places": places["places"]}


def stop_my_deal(user_id: str, deal_id: str) -> dict:
    return {"message": stop_deal(user_id, deal_id)}


def deal_recap(user_id: str, deal_id: str) -> dict:
    """One finished deal for the student who was in it: the offers round by round, the
    outcome, and what it earned them. Both sides' offers were already in their DMs."""
    deal = store.table("deals").get_item(Key={"deal_id": deal_id}).get("Item")
    if not deal or user_id not in (deal["seller_id"], deal["buyer_id"]):
        raise ApiError(404, "deal not found")
    if deal.get("agreed_price") is None:
        raise ApiError(409, "this deal never reached a price")
    view = _deal_view(deal, user_id)
    reward = deal.get(f"reward_{view['side']}") or {}
    view["ladder"] = [
        {
            "round": int(s["t"]) + 1,
            "side": s["side"],
            "amount": int(s["amount"]),
            "accept": s["action"] == "accept",
        }
        for s in deal.get("ladder") or []
    ]
    view["rounds"] = game.rounds(deal)
    view["saving"] = game.saving(deal)
    view["reward"] = (
        {
            "points": [
                {"reason": p["reason"], "points": int(p["points"])} for p in reward["points"]
            ],
            "achievements": [
                {"id": a, "label": game.ACHIEVEMENTS[a][0], "detail": game.ACHIEVEMENTS[a][1]}
                for a in reward.get("achievements", [])
            ],
            "rank": reward.get("rank"),
            "ranked_up": bool(reward.get("ranked_up")),
        }
        if reward.get("points")
        else None
    )
    return view


def zones(user_id: str) -> dict:
    return game.zone_scores()


def cancel_my_booking(user_id: str, deal_id: str) -> dict:
    ok, message = cancel_booking(user_id, deal_id)
    if not ok:
        raise ApiError(409, message)
    return {"message": message}


def _run(job: str, **fields) -> None:
    """Hand slow work to the listing agent, as the Discord handler does."""
    _lambda().invoke(
        FunctionName=os.environ["WORKER_FUNCTION"],
        InvocationType="Event",
        Payload=json.dumps({"job": job, **fields}).encode(),
    )


ID = r"([A-Za-z0-9_]+)"
ROUTES = [
    ("GET", r"/web/board", lambda u, m, q, b: board(u)),
    ("GET", r"/web/places", lambda u, m, q, b: campus_places(u)),
    ("GET", r"/web/listings", lambda u, m, q, b: browse(u, q)),
    ("POST", r"/web/listings", lambda u, m, q, b: create_listing(u, b)),
    ("GET", rf"/web/listings/{ID}", lambda u, m, q, b: listing_detail(u, m[1])),
    ("POST", rf"/web/listings/{ID}/publish", lambda u, m, q, b: publish(u, m[1])),
    ("POST", rf"/web/listings/{ID}/discard", lambda u, m, q, b: discard(u, m[1])),
    ("POST", rf"/web/listings/{ID}/stop", lambda u, m, q, b: stop_listing(u, m[1])),
    ("POST", rf"/web/listings/{ID}/interest", lambda u, m, q, b: express_interest(u, m[1], b)),
    ("POST", r"/web/uploads", lambda u, m, q, b: create_upload(u, b)),
    ("GET", r"/web/me", lambda u, m, q, b: my_haggle(u)),
    ("PUT", r"/web/me/preferences", lambda u, m, q, b: update_preferences(u, b)),
    ("GET", r"/web/zones", lambda u, m, q, b: zones(u)),
    ("GET", rf"/web/deals/{ID}", lambda u, m, q, b: deal_recap(u, m[1])),
    ("POST", rf"/web/deals/{ID}/stop", lambda u, m, q, b: stop_my_deal(u, m[1])),
    ("POST", rf"/web/deals/{ID}/cancel", lambda u, m, q, b: cancel_my_booking(u, m[1])),
]


def _respond(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(payload, default=str),
    }


def handler(event: dict, context) -> dict:
    body = event.get("body") or ""
    raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()
    try:
        user_id = authenticate(event, raw)
        method = event["requestContext"]["http"]["method"].upper()
        path = event["rawPath"].rstrip("/")
        for verb, pattern, fn in ROUTES:
            match = re.fullmatch(pattern, path)
            if match and verb == method:
                data = _body_json(raw) if method in ("POST", "PUT") else {}
                return _respond(
                    200, fn(user_id, match, event.get("queryStringParameters") or {}, data)
                )
        raise ApiError(404, "not found")
    except ApiError as e:
        return _respond(e.status, {"error": e.message})
    except Exception:
        log.exception("web api request failed")
        return _respond(500, {"error": "something went wrong"})
