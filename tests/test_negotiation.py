"""End-to-end negotiation without AWS: turns driven exactly like the state machine."""

import json
import re
from datetime import datetime, timedelta
from unittest import mock

import pytest

import deals
import interactions
import negotiator
import store
from scheduler import CAMPUS_TZ

SELLER, BUYER, OTHER_BUYER = "111", "222", "333"
ASKING, FLOOR, CEILING = 70, 47, 63


def tomorrow(hour: int) -> str:
    day = datetime.now(CAMPUS_TZ).date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, hour, tzinfo=CAMPUS_TZ).isoformat()


SELLER_WINDOWS = [{"start": tomorrow(14), "end": tomorrow(18)}]
BUYER_WINDOWS = [{"start": tomorrow(16), "end": tomorrow(19)}]


def polite(system: str, prompt: str, **kwargs) -> str:
    """A well-behaved fake model: uses exactly the number it is allowed."""
    allowed = re.search(r"only dollar amount you may write is (\$\d+|none)", system).group(1)
    return "Too far apart for me, thanks anyway." if allowed == "none" else f"How about {allowed}?"


def setup_deal(floor=FLOOR, ceiling=CEILING, buyer=BUYER, deal_id="deal_1", want_id="wnt_1"):
    listing = store.table("listings").get_item(Key={"listing_id": "lst_1"}).get("Item")
    if not listing:
        store.table("listings").put_item(
            Item={
                "listing_id": "lst_1",
                "seller_id": SELLER,
                "asking": ASKING,
                "title": "Mini fridge",
                "status": "open",
                "style": "balanced",
                "floor_enc": store.encrypt_limit(floor, "listing#lst_1", SELLER),
                "created_at": "2026-10-24T00:00:00+00:00",
                "category": "appliances",
                "area": "central",
                "windows": SELLER_WINDOWS,
            }
        )
    store.table("wants").put_item(
        Item={
            "want_id": want_id,
            "buyer_id": buyer,
            "query": "mini fridge",
            "status": "open",
            "style": "balanced",
            "ceiling_enc": store.encrypt_limit(ceiling, f"want#{want_id}", buyer),
            "created_at": "2026-10-24T00:00:00+00:00",
            "category": "appliances",
            "area": "central",
            "windows": BUYER_WINDOWS,
        }
    )
    store.table("deals").put_item(
        Item={
            "deal_id": deal_id,
            "listing_id": "lst_1",
            "want_id": want_id,
            "seller_id": SELLER,
            "buyer_id": buyer,
            "title": "Mini fridge",
            "description": "Works great.",
            "asking": ASKING,
            "state": "starting",
            "created_at": "2026-10-24T00:00:00+00:00",
        }
    )
    return deal_id


def run(deal_id: str, monkeypatch) -> dict:
    """Drive the turns the way negotiation.asl.json does."""
    nxt = deals.start(deal_id)["next"]
    for _ in range(20):
        monkeypatch.setenv("SIDE", nxt["side"])
        turn = negotiator.handler({"deal_id": deal_id, "t": nxt["t"], "side": nxt["side"]}, None)
        if turn["action"] != "offer":
            return turn
        nxt = turn["next"]
    raise AssertionError("negotiation did not end")


@pytest.fixture
def dms(aws):
    with (
        mock.patch("notify.dm") as dm,
        mock.patch("llm.converse", side_effect=polite) as model,
        mock.patch("deals._sfn") as sfn,
    ):
        yield dm, model, sfn


def sent(dm) -> list[tuple[str, str]]:
    return [(c.args[0], c.args[1].get("content", "")) for c in dm.call_args_list]


def test_agents_reach_a_price_inside_both_limits(dms, monkeypatch):
    dm, _, _ = dms
    turn = run(setup_deal(), monkeypatch)
    assert turn["action"] == "accept"
    assert FLOOR <= turn["price"] <= CEILING

    offers = store.table("offers").query(KeyConditionExpression=store.Key("deal_id").eq("deal_1"))[
        "Items"
    ]
    for o in offers:
        if o["side"] == "seller" and o["action"] == "offer":
            assert o["amount"] >= FLOOR
        if o["side"] == "buyer" and o["action"] == "offer":
            assert o["amount"] <= CEILING

    # Both students saw every line (the opening ask plus each turn).
    for user in (SELLER, BUYER):
        assert sum(1 for u, t in sent(dm) if u == user and "agent:**" in t) == len(offers) + 1


def test_each_side_decrypts_only_its_own_limit(dms, monkeypatch):
    real = store.decrypt_limit
    calls = []

    def spy(ciphertext, record, owner):
        calls.append((negotiator.os.environ["SIDE"], record))
        return real(ciphertext, record, owner)

    with mock.patch("store.decrypt_limit", side_effect=spy):
        run(setup_deal(), monkeypatch)
    assert calls
    for side, record in calls:
        assert record.startswith("listing#" if side == "seller" else "want#")


def test_negotiator_refuses_to_act_for_the_other_side(monkeypatch):
    monkeypatch.setenv("SIDE", "buyer")
    with pytest.raises(PermissionError):
        negotiator.handler({"deal_id": "d", "t": 1, "side": "seller"}, None)


def test_other_sides_limit_never_reaches_the_prompt(dms, monkeypatch):
    _, model, _ = dms
    run(setup_deal(floor=41, ceiling=66), monkeypatch)
    # A limit may legitimately show up as a public offer once some agent has offered
    # that amount; otherwise it must never appear in any prompt.
    public = set()
    for call in model.call_args_list:
        system, prompt = call.args
        allowed = re.search(r"only dollar amount you may write is \$(\d+)", system)
        for limit in ("41", "66"):
            if limit not in public:
                assert limit not in prompt and f"${limit}" not in system.replace(
                    f"${allowed.group(1)}" if allowed else "-", ""
                )
        if allowed:
            public.add(allowed.group(1))


def test_leaky_model_reply_is_replaced(dms, monkeypatch):
    dm, model, _ = dms
    model.side_effect = lambda system, prompt, **kw: (
        f"My floor is {FLOOR}. " + polite(system, prompt)
    )
    run(setup_deal(), monkeypatch)
    for _, text in sent(dm):
        assert "floor is" not in text


def test_too_far_apart_ends_without_numbers(dms, monkeypatch):
    dm, _, _ = dms
    turn = run(setup_deal(floor=60, ceiling=50), monkeypatch)
    assert turn["action"] == "walk"
    deals.no_deal("deal_1")
    assert store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]["state"] == "no_deal"
    last = sent(dm)[-1][1]
    assert "too far apart" in last and "$" not in last


def test_stopped_deal_takes_no_more_turns(dms, monkeypatch):
    deal_id = setup_deal()
    deals.start(deal_id)
    store.table("deals").update_item(
        Key={"deal_id": deal_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "stopped"},
    )
    monkeypatch.setenv("SIDE", "buyer")
    assert negotiator.handler({"deal_id": deal_id, "t": 0}, None) == negotiator.STOPPED


# ---------- agreement and confirmation


def agree(deal_id, monkeypatch):
    turn = run(deal_id, monkeypatch)
    deals.agreed(deal_id, turn["price"])
    assert deals.schedule(deal_id) == {"found": True}
    return turn["price"]


def test_confirm_flow_reveals_identities_only_at_the_end(dms, monkeypatch):
    dm, _, _ = dms
    price = agree(setup_deal(), monkeypatch)
    deals.request_confirm("deal_1", "seller", "tok-s")
    deals.request_confirm("deal_1", "buyer", "tok-b")
    assert not any("The buyer is" in t or "The seller is" in t for _, t in sent(dm))

    assert deals.finalize("deal_1") == {"result": "confirmed"}
    assert store.table("listings").get_item(Key={"listing_id": "lst_1"})["Item"]["status"] == "sold"
    assert store.table("wants").get_item(Key={"want_id": "wnt_1"})["Item"]["status"] == "fulfilled"
    final = dict(sent(dm)[-2:])
    assert "The buyer is" in final[SELLER] and "The seller is" in final[BUYER]
    assert f"${price}" in final[SELLER]


def test_first_confirmed_deal_wins_and_others_close(dms, monkeypatch):
    dm, _, sfn = dms
    agree(setup_deal(), monkeypatch)
    setup_deal(buyer=OTHER_BUYER, deal_id="deal_2", want_id="wnt_2")
    store.table("deals").update_item(
        Key={"deal_id": "deal_2"},
        UpdateExpression="SET #s = :s, execution_arn = :e",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "negotiating", ":e": "arn:exec:2"},
    )
    deals.finalize("deal_1")
    assert store.table("deals").get_item(Key={"deal_id": "deal_2"})["Item"]["state"] == "closed"
    sfn.return_value.stop_execution.assert_called_once_with(
        executionArn="arn:exec:2", cause="item sold"
    )
    assert (OTHER_BUYER, "**Haggle:** Mini fridge was sold.") in sent(dm)

    # The losing deal can no longer finalise.
    assert deals.finalize("deal_2") == {"result": "lost"}


def test_declined_or_timed_out_deal_closes(dms, monkeypatch):
    dm, _, _ = dms
    agree(setup_deal(), monkeypatch)
    deals.declined("deal_1", "States.Timeout")
    assert store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]["state"] == "closed"
    assert "in time" in sent(dm)[-1][1]


# ---------- buttons


def press(user, custom_id, kind=interactions.COMPONENT, **data):
    event = {
        "type": kind,
        "application_id": "app",
        "token": "tok",
        "user": {"id": user},
        "data": {"custom_id": custom_id, **data},
    }
    return json.loads(interactions.route(event)["body"])


@pytest.fixture
def sfn(dms, monkeypatch):
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn:sm")
    with mock.patch("interactions._sfn") as client:
        client.return_value.start_execution.return_value = {"executionArn": "arn:exec:1"}
        yield client.return_value


def test_start_haggling_starts_one_workflow(sfn):
    setup_deal()
    store.table("deals").update_item(
        Key={"deal_id": "deal_1"},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "proposed"},
    )
    assert "haggling" in press(BUYER, "haggle:deal_1")["data"]["content"]
    kwargs = sfn.start_execution.call_args.kwargs
    assert kwargs["stateMachineArn"] == "arn:sm" and kwargs["name"].startswith("deal_1-")
    assert kwargs["input"] == '{"deal_id": "deal_1"}'
    deal = store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]
    assert deal["state"] == "starting" and deal["execution_arn"] == "arn:exec:1"
    assert "already answered" in press(BUYER, "haggle:deal_1")["data"]["content"]


def test_confirm_and_decline_use_each_sides_own_token(sfn, monkeypatch):
    agree(setup_deal(), monkeypatch)
    deals.request_confirm("deal_1", "seller", "tok-s")
    deals.request_confirm("deal_1", "buyer", "tok-b")

    assert "no longer waiting" in press(OTHER_BUYER, "confirm:deal_1")["data"]["content"]
    assert "Waiting for the other" in press(SELLER, "confirm:deal_1")["data"]["content"]
    sfn.send_task_success.assert_called_once_with(taskToken="tok-s", output='{"side": "seller"}')
    assert "no longer waiting" in press(SELLER, "confirm:deal_1")["data"]["content"]

    assert "declined" in press(BUYER, "decline:deal_1")["data"]["content"]
    sfn.send_task_failure.assert_called_once_with(
        taskToken="tok-b", error="Declined", cause="buyer"
    )


def test_stop_button_ends_deal_and_tells_other_side_only_that(sfn, dms):
    dm, _, _ = dms
    setup_deal()
    store.table("deals").update_item(
        Key={"deal_id": "deal_1"},
        UpdateExpression="SET #s = :s, execution_arn = :e",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "negotiating", ":e": "arn:exec:1"},
    )
    assert "stopped" in press(BUYER, "stop:deal_1")["data"]["content"]
    sfn.stop_execution.assert_called_once()
    assert sent(dm)[-1] == (SELLER, "**Haggle:** The buyer has passed on Mini fridge.")
    assert "already ended" in press(BUYER, "stop:deal_1")["data"]["content"]


def test_change_limit_mid_deal(sfn):
    setup_deal()
    store.table("deals").update_item(
        Key={"deal_id": "deal_1"},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":s": "negotiating"},
    )
    assert press(SELLER, "limit:deal_1")["type"] == 9

    def submit(user, amount):
        return press(
            user,
            "limit:deal_1",
            kind=interactions.MODAL_SUBMIT,
            components=[{"type": 1, "components": [{"custom_id": "amount", "value": amount}]}],
        )["data"]["content"]

    assert "can't be above" in submit(SELLER, "90")
    assert "Updated to $40" in submit(SELLER, "40")
    listing = store.table("listings").get_item(Key={"listing_id": "lst_1"})["Item"]
    assert store.decrypt_limit(listing["floor_enc"].value, "listing#lst_1", SELLER) == 40
    assert "Updated to $68" in submit(BUYER, "68")
    want = store.table("wants").get_item(Key={"want_id": "wnt_1"})["Item"]
    assert store.decrypt_limit(want["ceiling_enc"].value, "want#wnt_1", BUYER) == 68


def test_display_name_spells_out_the_name_for_dms():
    import notify

    member = {"nick": None, "user": {"username": "krish123", "global_name": "Krish"}}
    with (
        mock.patch("notify._request", return_value=member),
        mock.patch("store.discord_secret", return_value={"guild_id": "g1"}),
    ):
        assert notify.display_name("42") == "**Krish** (@krish123)"
    # Not in the server any more: fall back to the global user.
    calls = [RuntimeError("not a member"), {"username": "krish123", "global_name": None}]
    with (
        mock.patch("notify._request", side_effect=calls),
        mock.patch("store.discord_secret", return_value={"guild_id": "g1"}),
    ):
        assert notify.display_name("42") == "**krish123** (@krish123)"
    with mock.patch("notify._request", side_effect=RuntimeError("discord down")):
        assert notify.display_name("42") == "<@42>"


# ---------- final ask when rounds run out


def test_one_dollar_gap_ends_in_a_private_final_ask(dms, monkeypatch):
    dm, model, _ = dms
    turn = run(setup_deal(floor=35, ceiling=34), monkeypatch)
    assert turn["action"] == "walk"
    # The walk-away itself is silent: no "too far apart" line before the final ask.
    assert not any("Too far apart" in text for _, text in sent(dm))

    monkeypatch.setenv("SIDE", "buyer")
    with mock.patch("negotiator._sfn") as sfn:
        negotiator.handler(
            {"action": "final_ask", "deal_id": "deal_1", "side": "buyer", "token": "tok-f"}, None
        )
    sfn.return_value.send_task_failure.assert_not_called()
    final = int(
        store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]["last_offer_seller"]
    )
    assert final > 35  # the seller's final offer no longer gives away its floor
    user, text = sent(dm)[-1]
    assert user == BUYER
    assert f"${final}" in text and f"${final - 34} more than your max of $34" in text
    assert (
        store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]["final_token"] == "tok-f"
    )
    # The seller was told nothing about the buyer's max.
    assert not any("$34" in t and "max" in t for u, t in sent(dm) if u == SELLER)


def test_final_ask_skipped_when_far_apart(dms, monkeypatch):
    dm, _, _ = dms
    run(setup_deal(floor=60, ceiling=40), monkeypatch)
    before = len(dm.call_args_list)
    monkeypatch.setenv("SIDE", "buyer")
    with mock.patch("negotiator._sfn") as sfn:
        negotiator.handler(
            {"action": "final_ask", "deal_id": "deal_1", "side": "buyer", "token": "tok-f"}, None
        )
    sfn.return_value.send_task_failure.assert_called_once_with(
        taskToken="tok-f", error="NoFinalAsk", cause="out of reach"
    )
    assert len(dm.call_args_list) == before


def test_seller_negotiator_cannot_make_a_final_ask(monkeypatch):
    monkeypatch.setenv("SIDE", "seller")
    with pytest.raises(PermissionError):
        negotiator.handler(
            {"action": "final_ask", "deal_id": "d", "side": "seller", "token": "t"}, None
        )


def test_final_ask_reach():
    assert negotiator.final_ask_reach(10) == 5  # small items: at least $5
    assert negotiator.final_ask_reach(100) == 25


def test_buyer_accepts_final_offer_and_both_confirm(sfn, dms, monkeypatch):
    dm, _, _ = dms
    run(setup_deal(floor=35, ceiling=34), monkeypatch)
    monkeypatch.setenv("SIDE", "buyer")
    with mock.patch("negotiator._sfn"):
        negotiator.handler(
            {"action": "final_ask", "deal_id": "deal_1", "side": "buyer", "token": "tok-f"}, None
        )
    assert "expired" in press(SELLER, "final_yes:deal_1")["data"]["content"]
    final = int(
        store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]["last_offer_seller"]
    )
    assert f"Accepted ${final}" in press(BUYER, "final_yes:deal_1")["data"]["content"]
    sfn.send_task_success.assert_called_once_with(taskToken="tok-f", output='{"accepted": true}')

    # The workflow then records the seller agent's own final offer as the price.
    deals.handler({"action": "agreed", "deal_id": "deal_1"}, None)
    deal = store.table("deals").get_item(Key={"deal_id": "deal_1"})["Item"]
    assert deal["state"] == "scheduling" and deal["agreed_price"] == final


def test_buyer_declines_final_offer(sfn, dms, monkeypatch):
    run(setup_deal(floor=35, ceiling=34), monkeypatch)
    monkeypatch.setenv("SIDE", "buyer")
    with mock.patch("negotiator._sfn"):
        negotiator.handler(
            {"action": "final_ask", "deal_id": "deal_1", "side": "buyer", "token": "tok-f"}, None
        )
    assert "keep looking" in press(BUYER, "final_no:deal_1")["data"]["content"]
    sfn.send_task_failure.assert_called_once_with(
        taskToken="tok-f", error="Declined", cause="buyer"
    )


def test_reserve_is_hidden_but_stable():
    a = negotiator.hold_back_for(b"ciphertext-1", "deal_1")
    assert a == negotiator.hold_back_for(b"ciphertext-1", "deal_1")
    assert negotiator.HOLD_BACK_MIN <= a <= negotiator.HOLD_BACK_MAX
    assert a != negotiator.hold_back_for(b"ciphertext-2", "deal_1")
