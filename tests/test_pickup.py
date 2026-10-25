"""Phase 7: pickup slot and spot, extra windows, reminders, handoff and no-shows."""

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from test_negotiation import (
    BUYER,
    OTHER_BUYER,
    SELLER,
    agree,
    press,
    sent,
    setup_deal,
    tomorrow,
)

import deals
import interactions
import listing_agent
import store


@pytest.fixture
def world(aws, monkeypatch):
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn:sm")
    monkeypatch.setenv("DEALS_FUNCTION", "haggle-test-deals")
    monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:role:scheduler")
    with (
        mock.patch("notify.dm") as dm,
        mock.patch("notify.edit_original") as edit,
        mock.patch("notify.display_name", side_effect=lambda uid: f"<name {uid}>"),
        mock.patch("llm.converse", side_effect=lambda s, p, **k: "Deal?"),
        mock.patch("deals._sfn"),
        mock.patch("deals._scheduler") as sched,
        mock.patch("interactions._sfn") as isfn,
        mock.patch("interactions._lambda") as ilambda,
        mock.patch("listing_agent._sfn") as lsfn,
    ):
        yield {
            "dm": dm,
            "edit": edit,
            "sched": sched.return_value,
            "isfn": isfn.return_value,
            "ilambda": ilambda.return_value,
            "lsfn": lsfn.return_value,
        }


def deal():
    return store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]


def set_windows(table, key, windows):
    store.table(table).update_item(
        Key=key,
        UpdateExpression="SET windows = :w",
        ExpressionAttributeValues={":w": windows},
    )


def priced_deal(price=50):
    """A deal whose price was agreed but which has no pickup slot yet."""
    setup_deal()
    store.table("deals").update_item(
        Key={"deal_id": "deal_1"},
        UpdateExpression="SET agreed_price = :p, #s = :s",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":p": price, ":s": "scheduling"},
    )


# ---------- slot and spot


def test_agreed_price_comes_with_slot_and_public_spot(world, monkeypatch):
    agree(setup_deal(), monkeypatch)
    d = deal()
    assert d["state"] == "confirming"
    assert d["slot_start"] == tomorrow(16)  # earliest overlap of 14-18 and 16-19
    assert d["spot_name"] == "Memorial Union north entrance"
    line = sent(world["dm"])[-1][1]
    assert "Price agreed at $" in line and "Pickup:" in line and "Memorial Union" in line


def test_students_never_see_each_others_windows(world, monkeypatch):
    agree(setup_deal(), monkeypatch)
    for _, text in sent(world["dm"]):
        assert "14:00" not in text and "2:00 pm" not in text and "7:00 pm" not in text


def test_large_item_gets_curbside_spot(world, monkeypatch):
    setup_deal()
    store.table("listings").update_item(
        Key={"listing_id": "lst_1"},
        UpdateExpression="SET #large = :t",
        ExpressionAttributeNames={"#large": "large"},  # reserved word in DynamoDB
        ExpressionAttributeValues={":t": True},
    )
    agree("deal_1", monkeypatch)
    place_id = deal()["place_id"]
    places = {p["place_id"]: p for p in __import__("scheduler").load_places()["places"]}
    assert places[place_id]["curbside"]


def test_no_overlap_asks_for_another_time(world, monkeypatch):
    setup_deal()
    set_windows("wants", {"want_id": "wnt_1"}, [{"start": tomorrow(8), "end": tomorrow(9)}])
    turn = __import__("test_negotiation").run("deal_1", monkeypatch)
    deals.agreed("deal_1", turn["price"])
    assert deals.schedule("deal_1") == {"found": False}
    assert deal()["state"] == "scheduling"

    deals.request_window("deal_1", "buyer", "tok-w")
    user, payload = world["dm"].call_args.args
    assert user == BUYER and "couldn't find a pickup time" in payload["content"]
    assert [b["custom_id"] for b in payload["components"][0]["components"]] == [
        "window:deal_1",
        "nowindow:deal_1",
    ]


def test_extra_window_is_added_and_workflow_resumes(world, monkeypatch):
    priced_deal()
    set_windows("wants", {"want_id": "wnt_1"}, [{"start": tomorrow(8), "end": tomorrow(9)}])
    deals.request_window("deal_1", "buyer", "tok-w")

    assert press(BUYER, "window:deal_1")["type"] == 9  # modal opens
    assert press(SELLER, "window:deal_1")["data"]["content"] == "That request has expired."

    added = [{"start": tomorrow(15), "end": tomorrow(17)}]
    event = {
        "job": "window",
        "deal_id": "deal_1",
        "side": "buyer",
        "text": "tomorrow 3-5",
        "app_id": "app",
        "token": "tok",
    }
    with mock.patch("listing_agent.parse_windows", return_value=added):
        listing_agent.handler(event, None)

    want = store.table("wants").get_item(Key={"want_id": "wnt_1"})["Item"]
    assert want["windows"][-1] == added[0] and len(want["windows"]) == 2
    world["lsfn"].send_task_success.assert_called_once_with(
        taskToken="tok-w", output='{"side": "buyer"}'
    )
    assert "window_token_buyer" not in deal()
    # The seller's record was not touched.
    listing = store.table("listings").get_item(Key={"listing_id": "lst_1"})["Item"]
    assert len(listing["windows"]) == 1


def test_unreadable_extra_window_keeps_waiting(world):
    priced_deal()
    deals.request_window("deal_1", "buyer", "tok-w")
    event = {
        "job": "window",
        "deal_id": "deal_1",
        "side": "buyer",
        "text": "whenever lol",
        "app_id": "app",
        "token": "tok",
    }
    with mock.patch("listing_agent.parse_windows", return_value=[]):
        listing_agent.handler(event, None)
    world["lsfn"].send_task_success.assert_not_called()
    assert deal()["window_token_buyer"] == "tok-w"
    assert "couldn't read" in world["edit"].call_args.args[2]["content"]


def test_cant_add_time_releases(world):
    priced_deal()
    deals.request_window("deal_1", "seller", "tok-w")
    assert "release" in press(SELLER, "nowindow:deal_1")["data"]["content"]
    world["isfn"].send_task_failure.assert_called_once_with(
        taskToken="tok-w", error="NoWindow", cause="seller"
    )
    deals.released("deal_1")
    assert deal()["state"] == "closed"
    assert "still listed" in sent(world["dm"])[-1][1]


# ---------- reminders and handoff


def confirmed_deal(monkeypatch):
    agree(setup_deal(), monkeypatch)
    deals.finalize("deal_1", own_arn="arn:aws:lambda:us-east-2:1:function:haggle-test-deals")


def test_finalize_schedules_reminder_and_handoff(world, monkeypatch):
    confirmed_deal(monkeypatch)
    calls = {c.kwargs["Name"]: c.kwargs for c in world["sched"].create_schedule.call_args_list}
    assert set(calls) == {"deal_1-remind", "deal_1-handoff"}
    start = datetime.fromisoformat(deal()["slot_start"]).astimezone(UTC)
    remind_at = (start - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    assert calls["deal_1-remind"]["ScheduleExpression"] == f"at({remind_at})"
    target = calls["deal_1-handoff"]["Target"]
    assert json.loads(target["Input"]) == {"action": "handoff", "deal_id": "deal_1"}
    assert target["RoleArn"] == "arn:role:scheduler"
    assert calls["deal_1-remind"]["ActionAfterCompletion"] == "DELETE"
    # The confirmation includes the pickup and the in-person payment note.
    final = sent(world["dm"])[-1][1]
    assert "Pickup:" in final and "never handles money" in final


def test_past_followups_are_skipped(world, monkeypatch):
    agree(setup_deal(), monkeypatch)
    d = deal()
    late = datetime.fromisoformat(d["slot_end"]) + timedelta(days=1)
    deals.schedule_followups(d, "arn:fn", now=late)
    world["sched"].create_schedule.assert_not_called()


def test_reminder_has_running_late_button(world, monkeypatch):
    confirmed_deal(monkeypatch)
    deals.remind("deal_1")
    reminders = [c.args for c in world["dm"].call_args_list if "Reminder" in c.args[1]["content"]]
    assert {u for u, _ in reminders} == {SELLER, BUYER}
    assert reminders[0][1]["components"][0]["components"][0]["custom_id"] == "late:deal_1"

    assert "running late" in press(BUYER, "late:deal_1")["data"]["content"]
    user, payload = world["dm"].call_args.args
    assert user == SELLER and "running a few minutes late" in payload["content"]


def test_reminder_skipped_for_cancelled_deal(world, monkeypatch):
    agree(setup_deal(), monkeypatch)
    before = world["dm"].call_count
    deals.remind("deal_1")  # never confirmed
    assert world["dm"].call_count == before


def test_both_done_closes_deal_and_counts_reliability(world, monkeypatch):
    confirmed_deal(monkeypatch)
    deals.handoff("deal_1")
    assert "Did the pickup" in sent(world["dm"])[-1][1]

    assert "glad it worked" in press(SELLER, "done:deal_1")["data"]["content"]
    assert deal()["state"] == "confirmed"
    assert "already recorded" in press(SELLER, "done:deal_1")["data"]["content"]
    press(BUYER, "done:deal_1")
    assert deal()["state"] == "done"
    for user in (SELLER, BUYER):
        assert store.table("users").get_item(Key={"user_id": user})["Item"]["done_count"] == 1


def test_no_show_relists_and_offers_item_to_earlier_buyer(world, monkeypatch):
    agree(setup_deal(), monkeypatch)
    # A second buyer was negotiating and lost out when the item sold.
    setup_deal(buyer=OTHER_BUYER, deal_id="deal_2", want_id="wnt_2")
    store.table("deals").update_item(
        Key={"deal_id": "deal_2"},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "negotiating"},
    )
    deals.finalize("deal_1", own_arn="arn:fn")
    assert (
        store.table("deals").get_item(Key={"deal_id": "deal_2"})["Item"]["close_reason"] == "sold"
    )

    assert "relisted" in press(SELLER, "noshow:deal_1")["data"]["content"]
    assert deal()["state"] == "no_show"
    buyer = store.table("users").get_item(Key={"user_id": BUYER})["Item"]
    assert buyer["no_show_count"] == 1
    payload = json.loads(world["ilambda"].invoke.call_args.kwargs["Payload"])
    assert payload == {"action": "reopen", "deal_id": "deal_1"}

    deals.reopen("deal_1")
    assert store.table("listings").get_item(Key={"listing_id": "lst_1"})["Item"]["status"] == "open"
    assert store.table("wants").get_item(Key={"want_id": "wnt_1"})["Item"]["status"] == "open"
    second = store.table("deals").get_item(Key={"deal_id": "deal_2"})["Item"]
    assert second["state"] == "proposed" and "close_reason" not in second
    user, payload = world["dm"].call_args.args
    assert user == OTHER_BUYER and "available again" in payload["content"]


def test_repeated_no_shows_pause_new_deals(world):
    store.table("users").put_item(Item={"user_id": BUYER, "no_show_count": 3})
    event = {
        "type": interactions.COMMAND,
        "application_id": "app",
        "token": "tok",
        "user": {"id": BUYER},
        "data": {
            "name": "want",
            "options": [{"name": "item", "value": "lamp"}, {"name": "area", "value": "north"}],
        },
    }
    assert "paused" in json.loads(interactions.route(event)["body"])["data"]["content"]
