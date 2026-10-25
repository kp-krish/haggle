"""Gamification: ranks, points, achievements, rank roles, recaps and zone rivalry."""

import json
from datetime import UTC, datetime
from unittest import mock

import pytest
from test_negotiation import BUYER, SELLER, press, tomorrow
from test_pickup import cancel, confirmed_deal, deal, world  # noqa: F401  (fixture)

import deals
import game
import store


def user(user_id):
    return store.table("users").get_item(Key={"user_id": user_id}).get("Item") or {}


@pytest.fixture
def roles():
    """A fake Discord server with no rank roles yet."""
    server = {"roles": [{"id": "r-everyone", "name": "@everyone"}], "members": {}}

    def create(name, color):
        role = {"id": f"r-{name}", "name": name}
        server["roles"].append(role)
        return role

    with (
        mock.patch("notify.guild_roles", side_effect=lambda: list(server["roles"])),
        mock.patch("notify.create_role", side_effect=create) as create_role,
        mock.patch(
            "notify.member_roles",
            side_effect=lambda uid: list(server["members"].get(uid, set())),
        ),
        mock.patch(
            "notify.add_role",
            side_effect=lambda uid, rid: server["members"].setdefault(uid, set()).add(rid),
        ),
        mock.patch(
            "notify.remove_role",
            side_effect=lambda uid, rid: server["members"].setdefault(uid, set()).discard(rid),
        ),
    ):
        server["create"] = create_role
        yield server


# ---------- ranks and points


@pytest.mark.parametrize(
    "points, name, nxt, to_next",
    [
        (0, "Freshman", "Sophomore", 100),
        (-40, "Freshman", "Sophomore", 100),
        (99, "Freshman", "Sophomore", 1),
        (100, "Sophomore", "Junior", 150),
        (999, "Senior", "Sun Devil Legend", 1),
        (5000, "Sun Devil Legend", None, 0),
    ],
)
def test_rank_thresholds(points, name, nxt, to_next):
    r = game.rank(points)
    assert (r["name"], r["next"], r["to_next"]) == (name, nxt, to_next)
    assert 0 <= r["progress"] <= 1


def test_pickup_points_reward_quick_closes_and_good_savings():
    base = {"asking": 100, "agreed_price": 90, "ladder": [{"t": 0}, {"t": 3}]}
    assert game.pickup_points(base, "buyer") == [("Completed pickup", 50)]
    quick = {**base, "ladder": [{"t": 0}, {"t": 1}], "agreed_price": 75}
    assert dict(game.pickup_points(quick, "buyer")) == {
        "Completed pickup": 50,
        "Quick close": 10,
        "20% or more off": 10,
    }
    # The seller doesn't earn the buyer's saving bonus.
    assert "20% or more off" not in dict(game.pickup_points(quick, "seller"))


# ---------- the full loop: Done -> reward -> recap, role and achievements


def both_done():
    press(SELLER, "done:deal_1")
    press(BUYER, "done:deal_1")


def test_done_hands_the_reward_to_the_deals_function(world, monkeypatch):  # noqa: F811
    confirmed_deal(monkeypatch)
    content = press(SELLER, "done:deal_1")["data"]["content"]
    assert "arrive when the buyer confirms" in content
    payload = json.loads(world["ilambda"].invoke.call_args.kwargs["Payload"])
    assert payload == {"action": "reward", "deal_id": "deal_1", "role": "buyer"}


def test_reward_credits_once_and_sends_a_recap(world, monkeypatch, roles):  # noqa: F811
    confirmed_deal(monkeypatch)
    both_done()
    d = deal()
    assert d["ladder"][0] == {"t": 0, "side": "seller", "amount": 70, "action": "offer"}
    assert d["ladder"][-1]["action"] == "accept"

    result = deals.reward("deal_1", "buyer")
    assert result["result"] == "rewarded"
    assert deals.reward("deal_1", "buyer") == {"result": "already rewarded"}

    buyer = user(BUYER)
    assert int(buyer["points"]) == result["points"] >= 50
    assert "first_deal" in buyer["achievements"]
    assert buyer["spots"] == {d["place_id"]}
    assert buyer["zones"] == {game.zone_of(d)}

    to, payload = world["dm"].call_args.args
    assert to == BUYER and "seller confirmed the pickup" in payload["content"]
    embed = payload["embeds"][0]
    assert embed["title"] == "Deal recap: Mini fridge"
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Offers"].startswith("```\nRound  Seller  Buyer\n1      $70")
    assert "First Deal" in next(v for k, v in fields.items() if k.startswith("New achievement"))
    assert "Freshman" in fields["Rank"]
    # Never a private limit: the test limits are $50 floor and $65 ceiling.
    assert "$50 floor" not in json.dumps(payload) and "65 max" not in json.dumps(payload)

    stored = deal()["reward_buyer"]
    assert stored["achievements"][0] == "first_deal" and stored["rank"] == "Freshman"
    assert roles["members"][BUYER] == {"r-Freshman"}


def test_rank_up_swaps_the_discord_role(world, monkeypatch, roles):  # noqa: F811
    store.table("users").put_item(Item={"user_id": BUYER, "points": 90})
    roles["roles"].append({"id": "r-Freshman", "name": "Freshman"})
    roles["members"][BUYER] = {"r-Freshman", "r-everyone"}
    confirmed_deal(monkeypatch)
    both_done()
    deals.reward("deal_1", "buyer")
    assert roles["members"][BUYER] == {"r-Sophomore", "r-everyone"}
    roles["create"].assert_called_once_with("Sophomore", 0x5E9C8A)
    fields = {f["name"]: f["value"] for f in world["dm"].call_args.args[1]["embeds"][0]["fields"]}
    assert "You're now a **Sophomore**" in fields["Rank"]
    assert deal()["reward_buyer"]["ranked_up"] is True


def test_missing_role_permission_never_breaks_the_reward(world, monkeypatch):  # noqa: F811
    confirmed_deal(monkeypatch)
    both_done()
    with mock.patch("notify.guild_roles", side_effect=RuntimeError("Missing Permissions")):
        assert deals.reward("deal_1", "seller")["result"] == "rewarded"
    assert world["dm"].call_args.args[0] == SELLER


def test_achievements_from_history():
    deal_ = {
        "asking": 100,
        "agreed_price": 70,
        "ladder": [{"t": 0}, {"t": 1}],
        "slot_start": tomorrow(19),
    }
    seasoned = {
        "done_count": 10,
        "spots": {"a", "b", "c", "d", "e"},
        "zones": {"north", "central", "south"},
        "sold_bikes": 3,
    }
    assert game._earned(seasoned, deal_, "buyer") == set(game.ACHIEVEMENTS)
    assert "clean_record" not in game._earned({**seasoned, "cancel_count": 1}, deal_, "buyer")
    assert "hard_bargainer" not in game._earned(seasoned, deal_, "seller")
    assert "night_owl" not in game._earned(seasoned, {**deal_, "slot_start": tomorrow(15)}, "buyer")


def test_bikes_count_for_the_seller(aws):
    d = {"asking": 100, "agreed_price": 90, "ladder": [], "category": "bikes-transport"}
    for _ in range(3):
        result = game.credit_pickup(SELLER, d, "seller")
    assert int(user(SELLER)["sold_bikes"]) == 3
    assert "bike_flipper" in user(SELLER)["achievements"]
    assert result["new"] == ["bike_flipper"]


# ---------- penalties


def test_cancelling_and_no_shows_cost_points(world, monkeypatch, roles):  # noqa: F811
    store.table("users").put_item(Item={"user_id": BUYER, "points": 120})
    confirmed_deal(monkeypatch)
    cancel(BUYER)
    assert int(user(BUYER)["points"]) == 95
    deals.cancelled("deal_1")
    assert roles["members"][BUYER] == {"r-Freshman"}  # dropped below Sophomore


def test_no_show_penalizes_the_other_side(world, monkeypatch):  # noqa: F811
    confirmed_deal(monkeypatch)
    press(SELLER, "noshow:deal_1")
    assert int(user(BUYER)["points"]) == game.NO_SHOW_POINTS
    payload = json.loads(world["ilambda"].invoke.call_args.kwargs["Payload"])
    assert payload == {"action": "reopen", "deal_id": "deal_1", "penalized": BUYER}


def test_rank_command(world, monkeypatch):  # noqa: F811
    store.table("users").put_item(
        Item={"user_id": BUYER, "points": 130, "achievements": {"first_deal": "2026-10-20"}}
    )
    content = press(BUYER, "", kind=2, name="rank")["data"]["content"]
    assert "**Sophomore** · 130 points · 120 to Junior" in content
    assert "First Deal" in content and "1 of 8" in content


# ---------- zone rivalry


def test_zone_scores_count_this_weeks_confirmed_pickups(aws):
    now = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)  # a Wednesday
    rows = [
        ("d1", "mu-north", "2026-10-27T10:00:00-07:00", "done"),  # central
        ("d2", "mu-north", "2026-10-26T09:00:00-07:00", "done"),
        ("d3", "old-main", "2026-10-25T12:00:00-07:00", "done"),  # last week
        ("d4", "old-main", "2026-10-27T12:00:00-07:00", None),  # never confirmed
    ]
    for deal_id, place, start, handoff in rows:
        item = {"deal_id": deal_id, "place_id": place, "slot_start": start}
        if handoff:
            item["handoff_buyer"] = handoff
        store.table("deals").put_item(Item=item)
    result = game.zone_scores(now)
    zone = game.zone_of({"place_id": "mu-north"})
    assert result["scores"][zone] == 2 and sum(result["scores"].values()) == 2
    assert result["leader"] == zone
    assert result["since"] == "2026-10-26T00:00:00-07:00"


def test_agent_turn_cards_label_the_readers_own_agent():
    import cards

    mine = cards.agent_turn("buyer", "How about $51?", "offer", 51, own=True)["embeds"][0]
    theirs = cards.agent_turn("buyer", "How about $51?", "offer", 51, own=False)["embeds"][0]
    assert mine["author"]["name"] == "Your agent (buyer) · offers $51"
    assert theirs["author"]["name"] == "Buyer's agent · offers $51"
    assert mine["color"] == cards.BUYER and mine["description"] == "How about $51?"
