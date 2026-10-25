import json
from unittest import mock

import pytest
from botocore.exceptions import ClientError
from nacl.signing import SigningKey

import interactions
import store

KEY = SigningKey.generate()
PUBLIC = KEY.verify_key.encode().hex()
SELLER, BUYER, STRANGER = "111", "222", "333"


def signed_event(payload: dict, key: SigningKey = KEY, timestamp: str = "1700000000") -> dict:
    body = json.dumps(payload)
    signature = key.sign(f"{timestamp}{body}".encode()).signature.hex()
    return {
        "headers": {"X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp},
        "body": body,
        "isBase64Encoded": False,
    }


@pytest.fixture(autouse=True)
def secret():
    with mock.patch("store.discord_secret", return_value={"public_key": PUBLIC}):
        yield


@pytest.fixture
def jobs():
    with mock.patch("interactions.run_async") as run_async:
        yield run_async


def body(resp: dict) -> dict:
    return json.loads(resp["body"])


def base(kind: int, user: str, data: dict) -> dict:
    return {
        "type": kind,
        "application_id": "app",
        "token": "tok",
        "member": {"user": {"id": user}},
        "data": data,
    }


def sell_command(user=SELLER, asking=70, content_type="image/jpeg", size=1000):
    return base(
        interactions.COMMAND,
        user,
        {
            "name": "sell",
            "options": [
                {"name": "photo", "value": "att1"},
                {"name": "description", "value": "mini fridge, small dent"},
                {"name": "asking", "value": asking},
                {"name": "area", "value": "central"},
            ],
            "resolved": {
                "attachments": {
                    "att1": {
                        "url": "https://cdn.example/f.jpg",
                        "content_type": content_type,
                        "size": size,
                    }
                }
            },
        },
    )


def modal(user: str, custom_id: str, **values) -> dict:
    return base(
        interactions.MODAL_SUBMIT,
        user,
        {
            "custom_id": custom_id,
            "components": [
                {"type": 1, "components": [{"custom_id": k, "value": v}]} for k, v in values.items()
            ],
        },
    )


def start_listing(user=SELLER) -> str:
    resp = body(interactions.route(sell_command(user)))
    assert resp["type"] == 9
    return resp["data"]["custom_id"].split(":", 1)[1]


# ---------- signature


def test_ping_gets_pong():
    resp = interactions.handler(signed_event({"type": 1}), None)
    assert resp["statusCode"] == 200
    assert body(resp) == {"type": 1}


def test_wrong_key_is_rejected():
    resp = interactions.handler(signed_event({"type": 1}, key=SigningKey.generate()), None)
    assert resp["statusCode"] == 401


def test_tampered_body_is_rejected():
    event = signed_event({"type": 1})
    event["body"] = event["body"].replace("1", "2")
    assert interactions.handler(event, None)["statusCode"] == 401


def test_missing_headers_are_rejected():
    assert interactions.handler({"headers": {}, "body": "{}"}, None)["statusCode"] == 401


# ---------- /sell


def test_sell_opens_private_form_and_saves_draft(aws):
    listing_id = start_listing()
    item = store.table("listings").get_item(Key={"listing_id": listing_id})["Item"]
    assert item["status"] == "draft" and item["seller_id"] == SELLER
    assert "floor_enc" not in item


def test_sell_rejects_non_image(aws):
    resp = body(interactions.route(sell_command(content_type="application/pdf")))
    assert resp["type"] == 4 and "photo" in resp["data"]["content"]


def test_floor_is_encrypted_and_never_stored_in_plain(aws, jobs):
    listing_id = start_listing()
    resp = interactions.route(
        modal(SELLER, f"sell:{listing_id}", floor="$45", windows="weekdays after 3", style="")
    )
    assert body(resp)["type"] == 5
    item = store.table("listings").get_item(Key={"listing_id": listing_id})["Item"]
    assert item["status"] == "processing" and item["style"] == "balanced"
    # No field holds the floor in plain text (checked per value: timestamps can contain 45).
    plain = [v for k, v in item.items() if k != "floor_enc"]
    assert not any(str(v).strip("$") == "45" for v in plain)
    assert store.decrypt_limit(item["floor_enc"].value, f"listing#{listing_id}", SELLER) == 45
    jobs.assert_called_once()
    assert jobs.call_args.kwargs == {"listing_id": listing_id}


@pytest.mark.parametrize(
    "floor,style,expect",
    [("abc", "", "whole dollar"), ("80", "", "above your asking"), ("40", "greedy", "Style")],
)
def test_bad_form_values_get_a_private_explanation(aws, jobs, floor, style, expect):
    listing_id = start_listing()
    resp = body(
        interactions.route(
            modal(SELLER, f"sell:{listing_id}", floor=floor, windows="x", style=style)
        )
    )
    assert resp["type"] == 4 and expect in resp["data"]["content"]
    assert resp["data"]["flags"] == 64
    jobs.assert_not_called()


def test_someone_elses_form_is_refused(aws, jobs):
    listing_id = start_listing()
    resp = body(interactions.route(modal(STRANGER, f"sell:{listing_id}", floor="45", windows="x")))
    assert "expired" in resp["data"]["content"]
    jobs.assert_not_called()


def test_only_the_seller_can_publish(aws, jobs):
    listing_id = start_listing()
    store.table("listings").update_item(
        Key={"listing_id": listing_id},
        UpdateExpression="SET #s = :p",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":p": "preview"},
    )
    press = lambda user: base(  # noqa: E731
        interactions.COMPONENT, user, {"custom_id": f"publish:{listing_id}"}
    )
    assert "no longer active" in body(interactions.route(press(STRANGER)))["data"]["content"]
    jobs.assert_not_called()
    assert body(interactions.route(press(SELLER)))["type"] == 7
    jobs.assert_called_once()
    # A second click does nothing.
    assert "no longer active" in body(interactions.route(press(SELLER)))["data"]["content"]


# ---------- /want


def test_want_encrypts_ceiling(aws, jobs):
    cmd = base(
        interactions.COMMAND,
        BUYER,
        {
            "name": "want",
            "options": [
                {"name": "item", "value": "mini fridge"},
                {"name": "area", "value": "north"},
            ],
        },
    )
    want_id = body(interactions.route(cmd))["data"]["custom_id"].split(":", 1)[1]
    resp = interactions.route(
        modal(BUYER, f"want:{want_id}", ceiling="65", windows="sat", style="quick")
    )
    assert body(resp)["type"] == 5
    item = store.table("wants").get_item(Key={"want_id": want_id})["Item"]
    assert store.decrypt_limit(item["ceiling_enc"].value, f"want#{want_id}", BUYER) == 65
    with pytest.raises(ClientError):
        store.decrypt_limit(item["ceiling_enc"].value, f"want#{want_id}", SELLER)


# ---------- /deals, /stop


def _open_listing(listing_id: str) -> None:
    store.table("listings").update_item(
        Key={"listing_id": listing_id},
        UpdateExpression="SET #s = :o, title = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":o": "open", ":t": "Mini fridge 3.1 cu ft"},
    )


def test_deals_lists_open_items_without_limits(aws):
    listing_id = start_listing()
    _open_listing(listing_id)
    resp = body(interactions.route(base(interactions.COMMAND, SELLER, {"name": "deals"})))
    assert "Mini fridge" in resp["data"]["content"] and listing_id in resp["data"]["content"]
    empty = body(interactions.route(base(interactions.COMMAND, BUYER, {"name": "deals"})))
    assert "Nothing open" in empty["data"]["content"]


def test_stop_takes_down_own_listing_only(aws):
    listing_id = start_listing()
    _open_listing(listing_id)
    stop = lambda user: base(  # noqa: E731
        interactions.COMMAND,
        user,
        {"name": "stop", "options": [{"name": "deal", "value": listing_id}]},
    )
    assert "couldn't find" in body(interactions.route(stop(STRANGER)))["data"]["content"]
    assert "taken down" in body(interactions.route(stop(SELLER)))["data"]["content"]
    item = store.table("listings").get_item(Key={"listing_id": listing_id})["Item"]
    assert item["status"] == "stopped"


def test_stop_autocomplete_suggests_own_items(aws):
    listing_id = start_listing()
    _open_listing(listing_id)
    resp = body(
        interactions.route(
            base(
                interactions.AUTOCOMPLETE,
                SELLER,
                {"name": "stop", "options": [{"name": "deal", "value": "fri"}]},
            )
        )
    )
    assert resp["type"] == 8
    assert resp["data"]["choices"] == [
        {"name": "Selling: Mini fridge 3.1 cu ft", "value": listing_id}
    ]
