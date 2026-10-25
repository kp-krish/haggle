"""Website API: signing, browsing, selling, interest and my deals."""

import base64
import json
import time
from unittest import mock

import pytest

import badges
import listing_agent
import store
import web_api

SECRET = b"test-secret"
SELLER, BUYER, STRANGER = "111", "222", "333"


def call(method, path, user=SELLER, body=None, query="", secret=SECRET, ts=None, sig=None):
    raw = json.dumps(body).encode() if body is not None else b""
    ts = str(ts or int(time.time()))
    signature = sig or web_api.sign(secret, ts, method, path, query, user, raw)
    params = dict(p.split("=", 1) for p in query.split("&")) if query else None
    event = {
        "rawPath": path,
        "rawQueryString": query,
        "queryStringParameters": params,
        "requestContext": {"http": {"method": method}},
        "headers": {
            "X-Haggle-User": user,
            "X-Haggle-Timestamp": ts,
            "X-Haggle-Signature": signature,
        },
        "body": base64.b64encode(raw).decode(),
        "isBase64Encoded": True,
    }
    resp = web_api.handler(event, None)
    return resp["statusCode"], json.loads(resp["body"])


@pytest.fixture
def api(aws, monkeypatch):
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn:sm")
    with (
        mock.patch("web_api._hmac_secret", return_value=SECRET),
        mock.patch("web_api._lambda") as lam,
        mock.patch("notify.dm"),
    ):
        yield lam.return_value


def jobs(lam):
    return [json.loads(c.kwargs["Payload"]) for c in lam.invoke.call_args_list]


def open_listing(listing_id="lst_1", seller=SELLER, asking=70, **extra):
    store.table("listings").put_item(
        Item={
            "listing_id": listing_id,
            "seller_id": seller,
            "seller_notes": "mini fridge",
            "title": "Mini fridge",
            "description": "Works great.",
            "category": "appliances",
            "asking": asking,
            "area": "central",
            "status": "open",
            "photo_key": f"photos/{listing_id}.jpg",
            "floor_enc": b"secret",
            "windows": [{"start": "x", "end": "y"}],
            "created_at": store.now_iso(),
            **extra,
        }
    )


# ---------- signing


def test_signed_request_is_accepted(api):
    assert call("GET", "/web/me")[0] == 200


@pytest.mark.parametrize(
    "kwargs",
    [
        {"secret": b"wrong"},
        {"ts": int(time.time()) - 3600},
        {"sig": "deadbeef"},
    ],
)
def test_bad_or_stale_signatures_are_refused(api, kwargs):
    assert call("GET", "/web/me", **kwargs)[0] == 401


def test_signature_binds_the_user(api):
    # A valid signature for the seller can't be replayed as the buyer.
    ts = str(int(time.time()))
    sig = web_api.sign(SECRET, ts, "GET", "/web/me", "", SELLER, b"")
    assert call("GET", "/web/me", user=BUYER, ts=ts, sig=sig)[0] == 401


def test_unknown_route_is_404(api):
    assert call("GET", "/web/nope")[0] == 404


# ---------- browse


def test_browse_shows_open_listings_without_private_fields(api):
    open_listing()
    open_listing("lst_2", status="sold")
    status, body = call("GET", "/web/listings", user=BUYER)
    assert status == 200
    [card] = body["listings"]
    assert card["listing_id"] == "lst_1" and card["mine"] is False
    assert card["photo"].startswith("https://")
    for private in ("floor_enc", "seller_id", "windows", "seller_notes", "photo_key"):
        assert private not in card
    assert card["seller_badges"] == [
        {"id": "new", "label": "New", "detail": "No completed pickups yet"}
    ]


def test_browse_filters_and_sorts(api):
    open_listing("lst_1", asking=70)
    open_listing("lst_2", asking=20, title="Desk lamp", category="decor", description="")
    _, body = call("GET", "/web/listings", query="q=lamp")
    assert [c["listing_id"] for c in body["listings"]] == ["lst_2"]
    _, body = call("GET", "/web/listings", query="category=appliances")
    assert [c["listing_id"] for c in body["listings"]] == ["lst_1"]
    _, body = call("GET", "/web/listings", query="sort=price_asc")
    assert [c["listing_id"] for c in body["listings"]] == ["lst_2", "lst_1"]


def test_seller_badges_appear_on_listings(api):
    open_listing()
    store.table("users").put_item(
        Item={"user_id": SELLER, "done_count": 4, "done_as_seller": 4, "no_show_count": 0}
    )
    _, body = call("GET", "/web/listings", user=BUYER)
    assert [b["id"] for b in body["listings"][0]["seller_badges"]] == ["reliable_seller"]


# ---------- sell


def test_upload_is_scoped_to_the_user(api):
    status, body = call("POST", "/web/uploads", body={"content_type": "image/jpeg"})
    assert status == 200 and body["key"].startswith(f"uploads/{SELLER}/")
    assert call("POST", "/web/uploads", body={"content_type": "application/pdf"})[0] == 400


def test_create_listing_encrypts_floor_and_queues_the_agent(api):
    _, up = call("POST", "/web/uploads", body={"content_type": "image/jpeg"})
    status, body = call(
        "POST",
        "/web/listings",
        body={
            "photo_key": up["key"],
            "description": "mini fridge, small dent",
            "asking": 70,
            "floor": "$45",
            "area": "north",
            "windows": "weekdays after 3",
        },
    )
    assert status == 200
    listing_id = body["listing_id"]
    item = store.table("listings").get_item(Key={"listing_id": listing_id})["Item"]
    assert item["status"] == "processing" and item["upload_key"] == up["key"]
    assert store.decrypt_limit(item["floor_enc"].value, f"listing#{listing_id}", SELLER) == 45
    assert jobs(api) == [{"job": "sell", "listing_id": listing_id}]


@pytest.mark.parametrize(
    "change,expect",
    [
        ({"photo_key": f"uploads/{STRANGER}/x"}, "upload a photo"),
        ({"floor": 90}, "can't be above"),
        ({"asking": "lots"}, "whole dollar"),
        ({"area": "mars"}, "area must be"),
        ({"description": " "}, "few words"),
    ],
)
def test_create_listing_validation(api, change, expect):
    body = {"photo_key": f"uploads/{SELLER}/x", "description": "lamp", "asking": 70, "floor": 40}
    status, resp = call("POST", "/web/listings", body={**body, **change})
    assert status == 400 and expect in resp["error"]


def test_only_the_seller_publishes_their_preview(api):
    open_listing(status="preview")
    assert call("POST", "/web/listings/lst_1/publish", user=STRANGER)[0] == 409
    status, body = call("POST", "/web/listings/lst_1/publish")
    assert status == 200 and body["status"] == "publishing"
    assert jobs(api) == [{"job": "publish", "listing_id": "lst_1"}]
    assert call("POST", "/web/listings/lst_1/publish")[0] == 409


def test_web_sell_job_reads_photo_from_s3_and_skips_discord(aws):
    import io

    import boto3
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2000, 1500), "white").save(buf, format="JPEG")
    boto3.client("s3").put_object(Bucket="test-photos", Key="uploads/111/a", Body=buf.getvalue())
    store.table("listings").put_item(
        Item={
            "listing_id": "lst_w",
            "seller_id": SELLER,
            "seller_notes": "desk lamp",
            "asking": 20,
            "area": "any",
            "upload_key": "uploads/111/a",
            "status": "processing",
            "created_at": store.now_iso(),
        }
    )
    written = {
        "title": "Desk lamp",
        "description": "Works.",
        "category": "decor",
        "large": False,
        "prohibited": False,
        "prohibited_reason": "",
    }
    with (
        mock.patch("llm.converse_json", return_value=written),
        mock.patch("listing_agent.parse_windows", return_value=[]),
        mock.patch("notify.edit_original") as edit,
        mock.patch("listing_agent._download") as download,
    ):
        listing_agent.handler({"job": "sell", "listing_id": "lst_w"}, None)
    download.assert_not_called()
    edit.assert_not_called()
    item = store.table("listings").get_item(Key={"listing_id": "lst_w"})["Item"]
    assert item["status"] == "preview" and item["photo_key"] == "photos/lst_w.jpg"


# ---------- interest


def test_interest_encrypts_max_and_queues_the_negotiation(api):
    open_listing()
    status, body = call(
        "POST",
        "/web/listings/lst_1/interest",
        user=BUYER,
        body={"min": 40, "max": 60, "windows": "sat morning", "area": "any"},
    )
    assert status == 200
    want = store.table("wants").get_item(Key={"want_id": body["want_id"]})["Item"]
    assert want["status"] == "processing"  # never "open", so the matcher ignores it
    assert want["opening"] == 40 and want["listing_id"] == "lst_1"
    assert store.decrypt_limit(want["ceiling_enc"].value, f"want#{body['want_id']}", BUYER) == 60
    assert jobs(api) == [{"job": "interest", "want_id": body["want_id"]}]


@pytest.mark.parametrize(
    "user,body,status,expect",
    [
        (SELLER, {"min": 40, "max": 60}, 400, "your own listing"),
        (BUYER, {"min": 70, "max": 80}, 400, "below the asking"),
        (BUYER, {"min": 50, "max": 40}, 400, "can't be above your max"),
        (BUYER, {"min": "", "max": 40}, 400, "whole dollar"),
    ],
)
def test_interest_validation(api, user, body, status, expect):
    open_listing()
    code, resp = call("POST", "/web/listings/lst_1/interest", user=user, body=body)
    assert code == status and expect in resp["error"]


def test_interest_job_opens_deal_and_starts_negotiation(api):
    open_listing()
    _, body = call("POST", "/web/listings/lst_1/interest", user=BUYER, body={"min": 40, "max": 60})
    with (
        mock.patch("listing_agent.parse_windows", return_value=[{"start": "a", "end": "b"}]),
        mock.patch("listing_agent._sfn") as sfn,
    ):
        sfn.return_value.start_execution.return_value = {"executionArn": "arn:exec"}
        listing_agent.handler({"job": "interest", "want_id": body["want_id"]}, None)
    kwargs = sfn.return_value.start_execution.call_args.kwargs
    deal_id = json.loads(kwargs["input"])["deal_id"]
    deal = store.table("deals").get_item(Key={"deal_id": deal_id})["Item"]
    assert deal["state"] == "starting" and deal["buyer_id"] == BUYER and deal["source"] == "web"
    assert deal["execution_arn"] == "arn:exec"
    want = store.table("wants").get_item(Key={"want_id": body["want_id"]})["Item"]
    assert want["status"] == "direct"

    # Already haggling: a second interest is refused.
    assert (
        call("POST", "/web/listings/lst_1/interest", user=BUYER, body={"min": 40, "max": 60})[0]
        == 409
    )
    # The listing page shows the buyer's live deal, without private fields.
    _, detail = call("GET", "/web/listings/lst_1", user=BUYER)
    assert detail["my_deal"]["state"] == "starting" and "execution_arn" not in detail["my_deal"]


def test_website_opening_offer_is_used_by_the_buyer_agent(aws, monkeypatch):
    import negotiator

    open_listing(floor_enc=store.encrypt_limit(45, "listing#lst_1", SELLER))
    store.table("wants").put_item(
        Item={
            "want_id": "wnt_w",
            "buyer_id": BUYER,
            "opening": 33,
            "style": "balanced",
            "ceiling_enc": store.encrypt_limit(60, "want#wnt_w", BUYER),
            "created_at": store.now_iso(),
            "category": "appliances",
        }
    )
    deal = {"deal_id": "d", "listing_id": "lst_1", "want_id": "wnt_w", "asking": 70}
    side = negotiator.load_side(deal, "buyer")
    assert side.opening == 33
    from strategy import planned_offer

    assert planned_offer(side, 0) == 33


# ---------- my haggle


def test_me_lists_own_items_and_badges(api):
    open_listing()
    store.table("deals").put_item(
        Item={
            "deal_id": "deal_1",
            "listing_id": "lst_1",
            "want_id": "w",
            "seller_id": SELLER,
            "buyer_id": BUYER,
            "title": "Mini fridge",
            "asking": 70,
            "state": "confirmed",
            "agreed_price": 55,
            "slot_start": "2026-10-29T16:30:00-07:00",
            "spot_name": "MU",
            "confirm_token_seller": "secret-token",
            "last_offer_buyer": 50,
            "created_at": store.now_iso(),
        }
    )
    status, body = call("GET", "/web/me")
    assert status == 200
    assert [i["listing_id"] for i in body["listings"]] == ["lst_1"]
    [deal] = body["deals"]
    assert deal["side"] == "seller" and deal["pickup"] == "Thu Oct 29, 4:30 pm, MU"
    for private in ("confirm_token_seller", "buyer_id", "seller_id", "last_offer_buyer"):
        assert private not in deal
    assert body["profile"]["badges"][0]["id"] == "new"


def test_stop_listing_only_by_owner(api):
    open_listing()
    assert call("POST", "/web/listings/lst_1/stop", user=STRANGER)[0] == 409
    assert call("POST", "/web/listings/lst_1/stop")[1]["status"] == "stopped"


def test_preferences_round_trip(api):
    status, body = call(
        "PUT",
        "/web/me/preferences",
        body={"area": "south", "style": "quick", "windows": "weekends"},
    )
    assert status == 200 and body == {"area": "south", "windows": "weekends", "style": "quick"}
    assert call("GET", "/web/me")[1]["profile"]["area"] == "south"


# ---------- badges


def test_badge_rules():
    assert badges.badges(None)[0]["id"] == "new"
    trusted = {"done_count": 12, "done_as_seller": 8, "done_as_buyer": 4, "no_show_count": 0}
    assert [b["id"] for b in badges.badges(trusted)] == [
        "trusted",
        "reliable_seller",
        "reliable_buyer",
    ]
    assert badges.badges({"done_count": 12, "no_show_count": 2}) == []
    one_slip = {"done_count": 30, "done_as_seller": 30, "no_show_count": 1}
    assert [b["id"] for b in badges.badges(one_slip)] == ["trusted"]
