"""Discord interactions endpoint: verify the Ed25519 signature, then route.

Discord sends every slash command, button click and form submit here as an HTTPS POST
and expects an answer within 3 seconds. Anything slow (Bedrock, photo upload, posting)
is handed to the listing agent Lambda asynchronously behind a deferred reply.

Private limits typed into forms are encrypted here, before anything else sees them.
"""

from __future__ import annotations

import base64
import json
import os
from functools import cache

import boto3
from boto3.dynamodb.conditions import Attr, Key
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import notify
import store
from notify import EPHEMERAL, private, respond
from strategy import STYLE_BETA

PING, COMMAND, COMPONENT, AUTOCOMPLETE, MODAL_SUBMIT = 1, 2, 3, 4, 5

AREAS = ("north", "central", "south")
MAX_PRICE = 10_000
MAX_PHOTO_BYTES = 10 * 1024 * 1024
OPEN_LISTING = ("preview", "open")
OPEN_WANT = ("open",)
CLOSED_DEAL = ("closed", "stopped", "done", "no_deal", "passed")


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def verify(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    try:
        VerifyKey(bytes.fromhex(public_key)).verify(
            f"{timestamp}{body}".encode(), bytes.fromhex(signature)
        )
        return True
    except (BadSignatureError, ValueError):
        return False


@cache
def _lambda():
    return boto3.client("lambda")


def run_async(job: str, interaction: dict, **fields) -> None:
    """Hand slow work to the listing agent. The interaction token lets it edit our reply."""
    payload = {
        "job": job,
        "app_id": interaction["application_id"],
        "token": interaction["token"],
        **fields,
    }
    _lambda().invoke(
        FunctionName=os.environ["WORKER_FUNCTION"],
        InvocationType="Event",
        Payload=json.dumps(payload).encode(),
    )


def _user_id(interaction: dict) -> str:
    user = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    return user["id"]


def _options(interaction: dict) -> dict:
    return {o["name"]: o for o in interaction["data"].get("options", [])}


def _modal_values(interaction: dict) -> dict[str, str]:
    values = {}
    for row in interaction["data"].get("components", []):
        for field in row.get("components", []):
            values[field["custom_id"]] = (field.get("value") or "").strip()
    return values


def _parse_price(raw: str) -> int | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if 1 <= value <= MAX_PRICE else None


def _parse_style(raw: str) -> str | None:
    style = (raw or "balanced").strip().lower()
    return style if style in STYLE_BETA else None


def _user_defaults(user_id: str) -> dict:
    return store.table("users").get_item(Key={"user_id": user_id}).get("Item") or {}


def _save_user_defaults(user_id: str, area: str, windows_text: str, style: str) -> None:
    store.table("users").update_item(
        Key={"user_id": user_id},
        UpdateExpression=(
            "SET campus_area = :a, default_windows = :w, #s = :s, "
            "created_at = if_not_exists(created_at, :now)"
        ),
        ExpressionAttributeNames={"#s": "style"},
        ExpressionAttributeValues={
            ":a": area,
            ":w": windows_text,
            ":s": style,
            ":now": store.now_iso(),
        },
    )


# ---------- Slash commands


def cmd_sell(interaction: dict, user_id: str) -> dict:
    opts = _options(interaction)
    attachment = interaction["data"]["resolved"]["attachments"][opts["photo"]["value"]]
    if not (attachment.get("content_type") or "").startswith("image/"):
        return private("That file isn't a photo. Try `/sell` again with a JPG or PNG.")
    if attachment.get("size", 0) > MAX_PHOTO_BYTES:
        return private("That photo is over 10 MB. Try a smaller one.")

    asking = opts["asking"]["value"]
    listing_id = store.new_id("lst")
    store.table("listings").put_item(
        Item={
            "listing_id": listing_id,
            "seller_id": user_id,
            "seller_notes": opts["description"]["value"],
            "asking": asking,
            "area": opts["area"]["value"],
            "photo_url": attachment["url"],
            "photo_type": attachment["content_type"],
            "status": "draft",
            "created_at": store.now_iso(),
        }
    )
    defaults = _user_defaults(user_id)
    return respond(
        notify.MODAL,
        {
            "custom_id": f"sell:{listing_id}",
            "title": f"Private details (asking ${asking})",
            "components": [
                notify.text_input(
                    "floor",
                    "Lowest price you'll accept ($)",
                    placeholder="Only your agent ever sees this",
                    max_length=6,
                ),
                notify.text_input(
                    "windows",
                    "When can you meet in the next few days?",
                    placeholder="e.g. weekdays after 3, Sat morning",
                    value=defaults.get("default_windows", ""),
                    paragraph=True,
                ),
                notify.text_input(
                    "style",
                    "Style: patient, balanced or quick",
                    value=defaults.get("style", "balanced"),
                    required=False,
                    max_length=10,
                ),
            ],
        },
    )


def cmd_want(interaction: dict, user_id: str) -> dict:
    opts = _options(interaction)
    want_id = store.new_id("wnt")
    store.table("wants").put_item(
        Item={
            "want_id": want_id,
            "buyer_id": user_id,
            "query": opts["item"]["value"],
            "area": opts["area"]["value"],
            "status": "draft",
            "created_at": store.now_iso(),
        }
    )
    defaults = _user_defaults(user_id)
    return respond(
        notify.MODAL,
        {
            "custom_id": f"want:{want_id}",
            "title": "Private details",
            "components": [
                notify.text_input(
                    "ceiling",
                    "Most you'll pay ($)",
                    placeholder="Only your agent ever sees this",
                    max_length=6,
                ),
                notify.text_input(
                    "windows",
                    "When can you meet in the next few days?",
                    placeholder="e.g. weekdays after 3, Sat morning",
                    value=defaults.get("default_windows", ""),
                    paragraph=True,
                ),
                notify.text_input(
                    "style",
                    "Style: patient, balanced or quick",
                    value=defaults.get("style", "balanced"),
                    required=False,
                    max_length=10,
                ),
            ],
        },
    )


def _query_index(name: str, index: str, key: str, user_id: str) -> list[dict]:
    resp = store.table(name).query(
        IndexName=index,
        KeyConditionExpression=Key(key).eq(user_id),
        ScanIndexForward=False,
        Limit=25,
    )
    return resp.get("Items", [])


def open_items(user_id: str) -> dict[str, list[dict]]:
    """The student's live listings, wants and deals (never includes limits)."""
    listings = [
        i
        for i in _query_index("listings", "by_seller", "seller_id", user_id)
        if i["status"] in OPEN_LISTING
    ]
    wants = [
        i
        for i in _query_index("wants", "by_buyer", "buyer_id", user_id)
        if i["status"] in OPEN_WANT
    ]
    deals = [
        d
        for d in _query_index("deals", "by_seller", "seller_id", user_id)
        + _query_index("deals", "by_buyer", "buyer_id", user_id)
        if d.get("state") not in CLOSED_DEAL
    ]
    return {"listings": listings, "wants": wants, "deals": deals}


def cmd_deals(interaction: dict, user_id: str) -> dict:
    items = open_items(user_id)
    lines = []
    if items["listings"]:
        lines.append("**Selling**")
        lines += [
            f"• {i.get('title') or i['seller_notes'][:40]} — asking ${i['asking']} "
            f"({i['status']}) `{i['listing_id']}`"
            for i in items["listings"]
        ]
    if items["wants"]:
        lines.append("**Looking for**")
        lines += [f"• {w['query']} `{w['want_id']}`" for w in items["wants"]]
    if items["deals"]:
        lines.append("**Negotiations**")
        lines += [
            f"• {d.get('title', 'Deal')} — {d.get('state', 'open')} `{d['deal_id']}`"
            for d in items["deals"]
        ]
    if not lines:
        return private("Nothing open right now. Use `/sell` or `/want` to start.")
    return private("\n".join(lines))


def cmd_stop(interaction: dict, user_id: str) -> dict:
    target = _options(interaction)["deal"]["value"].strip()
    try:
        if target.startswith("lst_"):
            store.table("listings").update_item(
                Key={"listing_id": target},
                UpdateExpression="SET #s = :stopped",
                ConditionExpression=Attr("seller_id").eq(user_id)
                & Attr("status").is_in(list(OPEN_LISTING)),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":stopped": "stopped"},
            )
            return private("Listing taken down. Buyers will see it's no longer available.")
        if target.startswith("wnt_"):
            store.table("wants").update_item(
                Key={"want_id": target},
                UpdateExpression="SET #s = :stopped",
                ConditionExpression=Attr("buyer_id").eq(user_id)
                & Attr("status").is_in(list(OPEN_WANT)),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":stopped": "stopped"},
            )
            return private("Stopped looking for that item.")
    except store.conditional_failed():
        return private("I couldn't find an open item with that id under your name.")
    return private("Pick one of your items from the list (start typing to see them).")


def autocomplete_stop(interaction: dict, user_id: str) -> dict:
    typed = str(_options(interaction).get("deal", {}).get("value", "")).lower()
    items = open_items(user_id)
    choices = [
        {"name": f"Selling: {i.get('title') or i['seller_notes']}"[:100], "value": i["listing_id"]}
        for i in items["listings"]
    ] + [{"name": f"Wanted: {w['query']}"[:100], "value": w["want_id"]} for w in items["wants"]]
    choices = [c for c in choices if typed in c["name"].lower() or typed in c["value"].lower()]
    return respond(notify.AUTOCOMPLETE_RESULT, {"choices": choices[:25]})


# ---------- Form submits


def submit_sell(interaction: dict, user_id: str, listing_id: str) -> dict:
    values = _modal_values(interaction)
    listing = store.table("listings").get_item(Key={"listing_id": listing_id}).get("Item")
    if not listing or listing["seller_id"] != user_id or listing["status"] != "draft":
        return private("This form has expired. Start again with `/sell`.")

    floor = _parse_price(values.get("floor", ""))
    if floor is None:
        return private("The lowest price needs to be a whole dollar amount, like `45`.")
    if floor > listing["asking"]:
        return private(
            f"Your lowest price can't be above your asking price (${listing['asking']}). "
            "Start again with `/sell`."
        )
    style = _parse_style(values.get("style", ""))
    if style is None:
        return private("Style must be `patient`, `balanced` or `quick`.")

    record = f"listing#{listing_id}"
    store.table("listings").update_item(
        Key={"listing_id": listing_id},
        UpdateExpression="SET floor_enc = :f, #st = :style, windows_text = :w, #s = :s",
        ConditionExpression=Attr("status").eq("draft"),
        ExpressionAttributeNames={"#s": "status", "#st": "style"},
        ExpressionAttributeValues={
            ":f": store.encrypt_limit(floor, record, user_id),
            ":style": style,
            ":w": values.get("windows", ""),
            ":s": "processing",
        },
    )
    _save_user_defaults(user_id, listing["area"], values.get("windows", ""), style)
    run_async("sell", interaction, listing_id=listing_id)
    return respond(notify.DEFERRED_MESSAGE, {"flags": EPHEMERAL})


def submit_want(interaction: dict, user_id: str, want_id: str) -> dict:
    values = _modal_values(interaction)
    want = store.table("wants").get_item(Key={"want_id": want_id}).get("Item")
    if not want or want["buyer_id"] != user_id or want["status"] != "draft":
        return private("This form has expired. Start again with `/want`.")

    ceiling = _parse_price(values.get("ceiling", ""))
    if ceiling is None:
        return private("The most you'll pay needs to be a whole dollar amount, like `65`.")
    style = _parse_style(values.get("style", ""))
    if style is None:
        return private("Style must be `patient`, `balanced` or `quick`.")

    record = f"want#{want_id}"
    store.table("wants").update_item(
        Key={"want_id": want_id},
        UpdateExpression="SET ceiling_enc = :c, #st = :style, windows_text = :w, #s = :s",
        ConditionExpression=Attr("status").eq("draft"),
        ExpressionAttributeNames={"#s": "status", "#st": "style"},
        ExpressionAttributeValues={
            ":c": store.encrypt_limit(ceiling, record, user_id),
            ":style": style,
            ":w": values.get("windows", ""),
            ":s": "processing",
        },
    )
    _save_user_defaults(user_id, want["area"], values.get("windows", ""), style)
    run_async("want", interaction, want_id=want_id)
    return respond(notify.DEFERRED_MESSAGE, {"flags": EPHEMERAL})


# ---------- Buttons


def press_publish(interaction: dict, user_id: str, listing_id: str) -> dict:
    try:
        store.table("listings").update_item(
            Key={"listing_id": listing_id},
            UpdateExpression="SET #s = :publishing",
            ConditionExpression=Attr("seller_id").eq(user_id) & Attr("status").eq("preview"),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":publishing": "publishing"},
        )
    except store.conditional_failed():
        return respond(notify.UPDATE_MESSAGE, {"content": "This preview is no longer active."})
    run_async("publish", interaction, listing_id=listing_id)
    return respond(notify.UPDATE_MESSAGE, {"content": "Publishing to #listings…", "components": []})


def press_cancel(interaction: dict, user_id: str, listing_id: str) -> dict:
    try:
        store.table("listings").update_item(
            Key={"listing_id": listing_id},
            UpdateExpression="SET #s = :cancelled",
            ConditionExpression=Attr("seller_id").eq(user_id) & Attr("status").eq("preview"),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":cancelled": "cancelled"},
        )
    except store.conditional_failed():
        pass
    return respond(
        notify.UPDATE_MESSAGE, {"content": "Listing discarded.", "embeds": [], "components": []}
    )


def press_haggle(interaction: dict, user_id: str, deal_id: str) -> dict:
    """Buyer agrees to start negotiating a matched listing."""
    deal = store.table("deals").get_item(Key={"deal_id": deal_id}).get("Item")
    if not deal or deal["buyer_id"] != user_id:
        return respond(notify.UPDATE_MESSAGE, {"content": "This match is no longer active."})
    listing = store.table("listings").get_item(Key={"listing_id": deal["listing_id"]}).get("Item")
    if not listing or listing.get("status") != "open":
        _set_deal_state(deal_id, "closed")
        return respond(
            notify.UPDATE_MESSAGE,
            {"content": "Sorry, that item is no longer available.", "components": []},
        )
    try:
        _set_deal_state(deal_id, "accepted", expect="proposed")
    except store.conditional_failed():
        return respond(notify.UPDATE_MESSAGE, {"content": "You already answered this one."})
    return respond(
        notify.UPDATE_MESSAGE,
        {
            "content": f"Got it. Your agent will haggle for **{deal.get('title', 'the item')}** "
            "and stay within your max price. You'll see each offer here.",
            "components": [],
        },
    )


def press_pass(interaction: dict, user_id: str, deal_id: str) -> dict:
    deal = store.table("deals").get_item(Key={"deal_id": deal_id}).get("Item")
    if deal and deal["buyer_id"] == user_id:
        try:
            _set_deal_state(deal_id, "passed", expect="proposed")
        except store.conditional_failed():
            pass
    return respond(
        notify.UPDATE_MESSAGE,
        {"content": "No problem, I'll keep looking.", "embeds": [], "components": []},
    )


def _set_deal_state(deal_id: str, state: str, expect: str | None = None) -> None:
    kwargs = {}
    if expect:
        kwargs["ConditionExpression"] = Attr("state").eq(expect)
    store.table("deals").update_item(
        Key={"deal_id": deal_id},
        UpdateExpression="SET #st = :s, updated_at = :now",
        ExpressionAttributeNames={"#st": "state"},
        ExpressionAttributeValues={":s": state, ":now": store.now_iso()},
        **kwargs,
    )


COMMANDS = {"sell": cmd_sell, "want": cmd_want, "deals": cmd_deals, "stop": cmd_stop}
MODALS = {"sell": submit_sell, "want": submit_want}
BUTTONS = {
    "publish": press_publish,
    "cancel": press_cancel,
    "haggle": press_haggle,
    "pass": press_pass,
}


def route(interaction: dict) -> dict:
    kind = interaction["type"]
    if kind == PING:
        return respond(notify.PONG)

    user_id = _user_id(interaction)
    data = interaction.get("data", {})
    if kind == COMMAND and data.get("name") in COMMANDS:
        return COMMANDS[data["name"]](interaction, user_id)
    if kind == AUTOCOMPLETE and data.get("name") == "stop":
        return autocomplete_stop(interaction, user_id)
    if kind in (MODAL_SUBMIT, COMPONENT):
        action, _, target = data.get("custom_id", "").partition(":")
        table = MODALS if kind == MODAL_SUBMIT else BUTTONS
        if action in table:
            return table[action](interaction, user_id, target)
    return private("I don't know that one yet.")


def handler(event: dict, context) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()

    if not verify(
        store.discord_secret()["public_key"],
        headers.get("x-signature-ed25519", ""),
        headers.get("x-signature-timestamp", ""),
        body,
    ):
        return _response(401, {"error": "invalid request signature"})

    return route(json.loads(body))
