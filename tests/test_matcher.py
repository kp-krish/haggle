import json
from unittest import mock

import pytest
from boto3.dynamodb.types import TypeSerializer

import interactions
import matcher
import store

FRIDGE = {
    "listing_id": "lst_1",
    "seller_id": "111",
    "title": "Mini fridge, 3.1 cu ft",
    "description": "Works great, small dent on the side.",
    "seller_notes": "mini fridge",
    "category": "appliances",
    "asking": 70,
    "area": "central",
    "status": "open",
    "created_at": "2026-10-24T20:00:00+00:00",
}
FRIDGE_WANT = {
    "want_id": "wnt_1",
    "buyer_id": "222",
    "query": "mini fridge",
    "keywords": ["mini fridge", "compact refrigerator", "dorm fridge"],
    "category": "appliances",
    "area": "north",
    "status": "open",
    "created_at": "2026-10-24T19:00:00+00:00",
}


def stream_event(new: dict, old: dict | None = None) -> dict:
    ser = TypeSerializer().serialize
    record = {"dynamodb": {"NewImage": {k: ser(v) for k, v in new.items()}}}
    if old:
        record["dynamodb"]["OldImage"] = {k: ser(v) for k, v in old.items()}
    return {"Records": [record]}


# ---------- scoring (pure)


def test_matching_words_in_same_category_score():
    assert matcher.score(FRIDGE, FRIDGE_WANT) > 0


def test_same_category_without_shared_words_does_not_match():
    microwave = {
        **FRIDGE,
        "title": "Microwave 700W",
        "description": "",
        "seller_notes": "microwave",
    }
    assert matcher.score(microwave, FRIDGE_WANT) == 0


def test_different_category_needs_strong_word_overlap():
    # "mini fridge" phrase + "mini" + "fridge" words: strong enough across categories.
    assert matcher.score({**FRIDGE, "category": "other"}, FRIDGE_WANT) >= 2
    # One weak shared word is not enough across categories.
    lamp = {
        **FRIDGE,
        "title": "Lamp",
        "description": "",
        "seller_notes": "lamp",
        "category": "decor",
    }
    assert matcher.score(lamp, {**FRIDGE_WANT, "query": "lamp oil", "keywords": []}) == 0


def test_listing_filed_as_other_still_meets_specific_want(dm):
    bottle = {
        **FRIDGE,
        "title": "Under Armour Water Bottle",
        "description": "",
        "seller_notes": "water bottle",
        "category": "other",
    }
    store.table("listings").put_item(Item=bottle)
    want = {
        **FRIDGE_WANT,
        "query": "water bottle",
        "keywords": ["water bottle", "sipper"],
        "category": "sports-outdoors",
    }
    assert matcher.handler(stream_event(want), None) == {"proposed": 1}


def test_seller_never_matches_own_want():
    assert matcher.score(FRIDGE, {**FRIDGE_WANT, "buyer_id": "111"}) == 0


def test_same_area_ranks_higher():
    near = matcher.score(FRIDGE, {**FRIDGE_WANT, "area": "central"})
    assert near > matcher.score(FRIDGE, FRIDGE_WANT)


def test_plurals_and_stopwords_are_ignored():
    assert matcher.words("The cheap Chairs for a desk") == {"chair", "desk"}


def test_deal_id_is_stable():
    assert matcher.deal_id_for("lst_1", "wnt_1") == matcher.deal_id_for("lst_1", "wnt_1")
    assert matcher.deal_id_for("lst_1", "wnt_1") != matcher.deal_id_for("lst_1", "wnt_2")


# ---------- stream handler


@pytest.fixture
def dm(aws):
    with (
        mock.patch("notify.dm") as dm,
        mock.patch("store.discord_secret", return_value={"guild_id": "g1"}),
    ):
        yield dm


def test_new_listing_asks_matching_buyer_once(dm):
    store.table("wants").put_item(Item=FRIDGE_WANT)
    event = stream_event(FRIDGE, old={**FRIDGE, "status": "publishing"})
    assert matcher.handler(event, None) == {"proposed": 1}

    user, payload = dm.call_args.args
    assert user == "222"
    assert "mini fridge" in payload["content"]
    buttons = [b["custom_id"] for b in payload["components"][0]["components"]]
    deal_id = matcher.deal_id_for("lst_1", "wnt_1")
    assert buttons == [f"haggle:{deal_id}", f"pass:{deal_id}"]
    deal = store.table("deals").get_item(Key={"deal_id": deal_id})["Item"]
    assert deal["state"] == "proposed" and deal["seller_id"] == "111"
    assert not any("enc" in k for k in deal)  # no limits travel with the deal

    # Stream redelivery does not ask twice.
    assert matcher.handler(event, None) == {"proposed": 0}
    assert dm.call_count == 1


def test_stream_images_with_encrypted_limits_are_handled(dm):
    # Real streams carry the encrypted ceiling as base64 text under "B".
    store.table("listings").put_item(Item=FRIDGE)
    event = stream_event(FRIDGE_WANT)
    event["Records"][0]["dynamodb"]["NewImage"]["ceiling_enc"] = {"B": "AQIDBA=="}
    assert matcher.handler(event, None) == {"proposed": 1}


def test_new_want_finds_existing_listing(dm):
    store.table("listings").put_item(Item=FRIDGE)
    event = stream_event(FRIDGE_WANT, old={**FRIDGE_WANT, "status": "processing"})
    assert matcher.handler(event, None) == {"proposed": 1}


def test_updates_to_already_open_items_are_ignored(dm):
    store.table("wants").put_item(Item=FRIDGE_WANT)
    assert matcher.handler(stream_event(FRIDGE, old=FRIDGE), None) == {"proposed": 0}
    dm.assert_not_called()


def test_closed_wants_are_not_matched(dm):
    store.table("wants").put_item(Item={**FRIDGE_WANT, "status": "stopped"})
    assert matcher.handler(stream_event(FRIDGE), None) == {"proposed": 0}


def test_failed_dm_undoes_the_proposal_so_retry_works(dm):
    store.table("wants").put_item(Item=FRIDGE_WANT)
    dm.side_effect = RuntimeError("discord down")
    with pytest.raises(RuntimeError):
        matcher.handler(stream_event(FRIDGE), None)
    dm.side_effect = None
    assert matcher.handler(stream_event(FRIDGE), None) == {"proposed": 1}


# ---------- buyer's answer


def press(user: str, custom_id: str) -> dict:
    event = {
        "type": interactions.COMPONENT,
        "application_id": "app",
        "token": "tok",
        "user": {"id": user},
        "data": {"custom_id": custom_id},
    }
    return json.loads(interactions.route(event)["body"])


def test_buyer_starts_haggling(dm):
    store.table("listings").put_item(Item=FRIDGE)
    store.table("wants").put_item(Item=FRIDGE_WANT)
    matcher.handler(stream_event(FRIDGE), None)
    deal_id = matcher.deal_id_for("lst_1", "wnt_1")

    assert "no longer active" in press("333", f"haggle:{deal_id}")["data"]["content"]
    assert "Your agent will haggle" in press("222", f"haggle:{deal_id}")["data"]["content"]
    assert store.table("deals").get_item(Key={"deal_id": deal_id})["Item"]["state"] == "accepted"
    assert "already answered" in press("222", f"haggle:{deal_id}")["data"]["content"]


def test_sold_listing_cannot_be_haggled(dm):
    store.table("listings").put_item(Item=FRIDGE)
    store.table("wants").put_item(Item=FRIDGE_WANT)
    matcher.handler(stream_event(FRIDGE), None)
    store.table("listings").put_item(Item={**FRIDGE, "status": "stopped"})
    deal_id = matcher.deal_id_for("lst_1", "wnt_1")
    assert "no longer available" in press("222", f"haggle:{deal_id}")["data"]["content"]


def test_buyer_passes(dm):
    store.table("listings").put_item(Item=FRIDGE)
    store.table("wants").put_item(Item=FRIDGE_WANT)
    matcher.handler(stream_event(FRIDGE), None)
    deal_id = matcher.deal_id_for("lst_1", "wnt_1")
    assert "keep looking" in press("222", f"pass:{deal_id}")["data"]["content"]
    assert store.table("deals").get_item(Key={"deal_id": deal_id})["Item"]["state"] == "passed"
