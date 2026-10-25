"""Campus ranks, points and achievements.

Everything here is earned from completed pickups and lost for cancelling or missing
one, so the game rewards exactly what makes the marketplace work. Savings are measured
against the public asking price, never against anyone's private limit.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import cache

from boto3.dynamodb.conditions import Attr

import notify
import scheduler
import store

log = logging.getLogger()

# (points needed, name, Discord role colour)
RANKS = [
    (0, "Freshman", 0x8A8C85),
    (100, "Sophomore", 0x5E9C8A),
    (250, "Junior", 0x2E7D69),
    (500, "Senior", 0xC08F2E),
    (1000, "Sun Devil Legend", 0x8C1D40),
]
PICKUP_POINTS = 50
QUICK_CLOSE_POINTS = 10
GOOD_SAVING_POINTS = 10
CANCEL_POINTS = -25
NO_SHOW_POINTS = -50

QUICK_ROUNDS = 2
GOOD_SAVING = 0.2  # 20% under the asking price
EVENING_HOUR = 18
ZONES = ("north", "central", "south")

ACHIEVEMENTS = {
    "first_deal": ("First Deal", "Complete your first pickup"),
    "hard_bargainer": ("Hard Bargainer", "Buy something for 20% or more off the asking price"),
    "quick_close": ("Quick Close", "Agree on a price within 2 rounds"),
    "campus_explorer": ("Campus Explorer", "Meet at 5 different spots"),
    "zone_hopper": ("Zone Hopper", "Pick up in all three campus zones"),
    "night_owl": ("Night Owl", "Finish a pickup in the evening"),
    "bike_flipper": ("Bike Flipper", "Sell 3 bikes or scooters"),
    "clean_record": ("Clean Record", "Reach 10 pickups with no cancellations or no-shows"),
}


# ---------- Ranks


def rank(points: int) -> dict:
    """Where a points total sits: name, the next rank and how far away it is."""
    points = max(0, int(points))
    current = max((r for r in RANKS if points >= r[0]), key=lambda r: r[0])
    later = [r for r in RANKS if r[0] > points]
    nxt = later[0] if later else None
    span = (nxt[0] - current[0]) if nxt else 1
    return {
        "name": current[1],
        "points": points,
        "next": nxt[1] if nxt else None,
        "to_next": nxt[0] - points if nxt else 0,
        "progress": round((points - current[0]) / span, 3) if nxt else 1.0,
    }


def rank_line(points: int) -> str:
    r = rank(points)
    if not r["next"]:
        return f"**{r['name']}** · {r['points']} points"
    return f"**{r['name']}** · {r['points']} points · {r['to_next']} to {r['next']}"


# ---------- Pickup facts


@cache
def _place_areas() -> dict[str, str]:
    return {p["place_id"]: p["area"] for p in scheduler.load_places()["places"]}


def zone_of(deal: dict) -> str | None:
    return _place_areas().get(deal.get("place_id", ""))


def rounds(deal: dict) -> int:
    """Rounds of offers (the turn counter starts at 0)."""
    turns = [int(s["t"]) for s in deal.get("ladder") or []]
    return (max(turns) if turns else int(deal.get("round", 0))) + 1


def saving(deal: dict) -> int:
    return int(deal["asking"]) - int(deal["agreed_price"])


def saving_share(deal: dict) -> float:
    return saving(deal) / int(deal["asking"]) if int(deal["asking"]) else 0.0


def _evening(deal: dict) -> bool:
    start = deal.get("slot_start")
    if not start:
        return False
    return datetime.fromisoformat(start).astimezone(scheduler.CAMPUS_TZ).hour >= EVENING_HOUR


def pickup_points(deal: dict, role: str) -> list[tuple[str, int]]:
    """The points one completed pickup earns, line by line."""
    lines = [("Completed pickup", PICKUP_POINTS)]
    if rounds(deal) <= QUICK_ROUNDS:
        lines.append(("Quick close", QUICK_CLOSE_POINTS))
    if role == "buyer" and saving_share(deal) >= GOOD_SAVING:
        lines.append(("20% or more off", GOOD_SAVING_POINTS))
    return lines


def _earned(user: dict, deal: dict, role: str) -> set[str]:
    """Achievements the student qualifies for after this pickup."""
    done = int(user.get("done_count", 0))
    out = set()
    if done >= 1:
        out.add("first_deal")
    if role == "buyer" and saving_share(deal) >= GOOD_SAVING:
        out.add("hard_bargainer")
    if rounds(deal) <= QUICK_ROUNDS:
        out.add("quick_close")
    if len(user.get("spots") or ()) >= 5:
        out.add("campus_explorer")
    if set(ZONES) <= set(user.get("zones") or ()):
        out.add("zone_hopper")
    if _evening(deal):
        out.add("night_owl")
    if int(user.get("sold_bikes", 0)) >= 3:
        out.add("bike_flipper")
    if (
        done >= 10
        and not int(user.get("cancel_count", 0))
        and not int(user.get("no_show_count", 0))
    ):
        out.add("clean_record")
    return out


# ---------- Recording


def credit_pickup(user_id: str, deal: dict, role: str) -> dict:
    """Points and achievements for one completed pickup.

    Returns ``{"points": [(reason, n)], "total": n, "new": [ids], "before": rank,
    "after": rank}``. The caller makes sure this runs once per student per deal.
    """
    lines = pickup_points(deal, role)
    gained = sum(n for _, n in lines)
    add = {":p": gained}
    parts = ["points :p"]
    if deal.get("place_id"):
        parts.append("spots :spot")
        add[":spot"] = {deal["place_id"]}
    if zone_of(deal):
        parts.append("zones :zone")
        add[":zone"] = {zone_of(deal)}
    if role == "seller" and deal.get("category") == "bikes-transport":
        parts.append("sold_bikes :one")
        add[":one"] = 1
    user = store.table("users").update_item(
        Key={"user_id": user_id},
        UpdateExpression="ADD " + ", ".join(parts),
        ExpressionAttributeValues=add,
        ReturnValues="ALL_NEW",
    )["Attributes"]

    have = set((user.get("achievements") or {}).keys())
    new = sorted(_earned(user, deal, role) - have, key=list(ACHIEVEMENTS).index)
    if new:
        # A nested path can only be set inside a map that already exists.
        merged = {**(user.get("achievements") or {}), **dict.fromkeys(new, store.now_iso())}
        store.table("users").update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET achievements = :a",
            ExpressionAttributeValues={":a": merged},
        )
    total = int(user.get("points", 0))
    return {
        "points": lines,
        "total": total,
        "new": new,
        "before": rank(total - gained),
        "after": rank(total),
    }


def penalize(user_id: str, points: int) -> int:
    """Take points away (cancelling, missing a pickup). Returns the new total."""
    user = store.table("users").update_item(
        Key={"user_id": user_id},
        UpdateExpression="ADD points :p",
        ExpressionAttributeValues={":p": points},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    return int(user.get("points", 0))


def profile(user: dict | None) -> dict:
    """What the website shows: rank, progress and every achievement, earned or not."""
    user = user or {}
    earned = user.get("achievements") or {}
    return {
        "rank": rank(int(user.get("points", 0))),
        "ranks": [{"name": name, "points": need} for need, name, _ in RANKS],
        "achievements": [
            {"id": key, "label": label, "detail": detail, "earned_at": earned.get(key)}
            for key, (label, detail) in ACHIEVEMENTS.items()
        ],
    }


# ---------- Discord rank roles


def sync_role(user_id: str, points: int) -> None:
    """Give the student the server role for their rank and drop the other rank roles.

    Best effort: needs the bot's Manage Roles permission, and a missing permission must
    never break a pickup.
    """
    try:
        want = rank(points)["name"]
        roles = {r["name"]: r["id"] for r in notify.guild_roles()}
        if want not in roles:
            colour = next(c for _, name, c in RANKS if name == want)
            roles[want] = notify.create_role(want, colour)["id"]
        held = set(notify.member_roles(user_id))
        for _, name, _ in RANKS:
            role_id = roles.get(name)
            if role_id and name != want and role_id in held:
                notify.remove_role(user_id, role_id)
        if roles[want] not in held:
            notify.add_role(user_id, roles[want])
    except Exception:
        log.exception("could not sync the rank role for %s", user_id)


# ---------- Zone rivalry


def week_start(now: datetime | None = None) -> datetime:
    """Monday 00:00 campus time (Arizona has no daylight saving)."""
    local = (now or datetime.now(UTC)).astimezone(scheduler.CAMPUS_TZ)
    monday = local - timedelta(days=local.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def zone_scores(now: datetime | None = None) -> dict:
    """Completed pickups per campus zone since Monday."""
    since = week_start(now)
    items = store.table("deals").scan(
        FilterExpression=Attr("slot_start").gte(since.isoformat())
        & (Attr("handoff_seller").eq("done") | Attr("handoff_buyer").eq("done")),
        ProjectionExpression="place_id, slot_start",
    )["Items"]
    scores = dict.fromkeys(ZONES, 0)
    for d in items:
        # ISO strings with mixed offsets don't compare reliably; check the real time.
        if datetime.fromisoformat(d["slot_start"]) < since:
            continue
        zone = zone_of(d)
        if zone in scores:
            scores[zone] += 1
    best = max(scores.values())
    leaders = [z for z, n in scores.items() if n == best and n > 0]
    return {
        "since": since.isoformat(),
        "scores": scores,
        "leader": leaders[0] if len(leaders) == 1 else None,
    }
