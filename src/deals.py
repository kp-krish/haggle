"""Deal lifecycle steps called by the negotiation state machine and EventBridge Scheduler.

Everything around the offer turns: opening the deal, agreement, finding a pickup slot
and spot, asking each student to confirm, finalising the sale, closing the other
buyers' deals, pickup reminders, the after-pickup check and no-show handling.
This function has no KMS access; it never handles a limit.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from functools import cache

import boto3
from boto3.dynamodb.conditions import Attr, Key

import notify
import scheduler
import store

log = logging.getLogger()
log.setLevel(logging.INFO)

ACTIVE = ("starting", "negotiating", "scheduling", "confirming")
LEAD_TIME = timedelta(hours=2)  # time to confirm and to send a reminder before pickup
REMINDER_BEFORE = timedelta(hours=1)
HANDOFF_AFTER = timedelta(minutes=15)  # ask "did it happen?" this long after the slot ends


@cache
def _sfn():
    return boto3.client("stepfunctions")


@cache
def _scheduler():
    return boto3.client("scheduler")


def _deal(deal_id: str) -> dict:
    return store.table("deals").get_item(Key={"deal_id": deal_id})["Item"]


def _update(deal_id: str, expect: tuple[str, ...] | None = None, **fields) -> None:
    kwargs = {}
    if expect:
        kwargs["ConditionExpression"] = Attr("state").is_in(list(expect))
    store.table("deals").update_item(
        Key={"deal_id": deal_id},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        ExpressionAttributeNames={f"#{k}": k for k in fields},
        ExpressionAttributeValues={f":{k}": v for k, v in fields.items()},
        **kwargs,
    )


def _set_status(table: str, key: dict, status: str, expect: str | None = None) -> bool:
    kwargs = {"ConditionExpression": Attr("status").eq(expect)} if expect else {}
    try:
        store.table(table).update_item(
            Key=key,
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
            **kwargs,
        )
        return True
    except store.conditional_failed():
        return False


def _dm_both(deal: dict, payload: dict) -> None:
    for user_id in (deal["seller_id"], deal["buyer_id"]):
        try:
            notify.dm(user_id, payload)
        except Exception:
            log.exception("could not DM %s", user_id)


def _controls(deal_id: str, limit_label: str) -> list[dict]:
    return [
        notify.row(
            notify.button(limit_label, f"limit:{deal_id}", notify.SECONDARY),
            notify.button("Stop", f"stop:{deal_id}", notify.DANGER),
        )
    ]


def pickup_line(deal: dict) -> str:
    start = datetime.fromisoformat(deal["slot_start"])
    return f"Pickup: {scheduler.format_slot(start)}, {deal['spot_name']}"


# ---------- Negotiation


def start(deal_id: str) -> dict:
    deal = _deal(deal_id)
    _update(
        deal_id,
        expect=("starting",),
        state="negotiating",
        last_offer_seller=deal["asking"],
        last_text_seller=f"{deal.get('title', 'Item')}. Asking ${deal['asking']}.",
        updated_at=store.now_iso(),
    )
    title = deal.get("title", "your item")
    notify.dm(
        deal["seller_id"],
        {
            "content": f"A buyer's agent wants **{title}**. I'm negotiating now and will "
            "stay at or above your lowest price. You'll see every offer here.",
            "components": _controls(deal_id, "Change my lowest price"),
        },
    )
    notify.dm(
        deal["buyer_id"],
        {
            "content": f"Haggling for **{title}** has started. I'll stay at or below your "
            "max price. You'll see every offer here.",
            "components": _controls(deal_id, "Change my max price"),
        },
    )
    _dm_both(deal, {"content": f"**Seller's agent:** {title}. Asking ${deal['asking']}."})
    return {"deal_id": deal_id, "next": {"side": "buyer", "t": 0}}


def agreed(deal_id: str, price: int) -> None:
    _update(
        deal_id,
        expect=("negotiating",),
        state="scheduling",
        agreed_price=price,
        updated_at=store.now_iso(),
    )


# ---------- Pickup slot and spot


def schedule(deal_id: str, now: datetime | None = None) -> dict:
    """Earliest slot in both students' windows plus a public spot. Code, not the model.

    Each side's windows stay private: students only ever see the chosen slot.
    """
    deal = _deal(deal_id)
    listing = store.table("listings").get_item(Key={"listing_id": deal["listing_id"]})["Item"]
    want = store.table("wants").get_item(Key={"want_id": deal["want_id"]})["Item"]
    now = now or datetime.now(UTC)
    pickup = scheduler.schedule(
        scheduler.windows_from_records(listing.get("windows")),
        scheduler.windows_from_records(want.get("windows")),
        listing.get("area", "central"),
        want.get("area", "central"),
        large=bool(listing.get("large")),
        not_before=now + LEAD_TIME,
    )
    if pickup is None:
        return {"found": False}

    _update(
        deal_id,
        expect=("scheduling",),
        state="confirming",
        slot_start=pickup.slot.start.isoformat(),
        slot_end=pickup.slot.end.isoformat(),
        place_id=pickup.place["place_id"],
        spot_name=pickup.place["name"],
        updated_at=store.now_iso(),
    )
    deal = _deal(deal_id)
    _dm_both(
        deal,
        {
            "content": f"**Haggle:** Price agreed at ${deal['agreed_price']}. "
            f"{pickup_line(deal)}. Waiting for both students to confirm."
        },
    )
    return {"found": True}


def request_window(deal_id: str, side: str, token: str) -> None:
    """No overlap: ask this student for one more free time, revealing nothing of the
    other side's schedule. The state machine waits on the token."""
    _update(deal_id, **{f"window_token_{side}": token})
    deal = _deal(deal_id)
    notify.dm(
        deal[f"{side}_id"],
        {
            "content": f"**Haggle:** Price agreed at ${deal['agreed_price']} for "
            f"**{deal.get('title', 'the item')}**, but I couldn't find a pickup time that "
            "works for both of you. Can you add another time in the next few days?",
            "components": [
                notify.row(
                    notify.button("Add a time", f"window:{deal_id}", notify.PRIMARY),
                    notify.button("I can't", f"nowindow:{deal_id}", notify.SECONDARY),
                )
            ],
        },
    )


def released(deal_id: str) -> None:
    deal = _deal(deal_id)
    _update(deal_id, state="closed", close_reason="no_slot", updated_at=store.now_iso())
    _dm_both(
        deal,
        {
            "content": "**Haggle:** I couldn't find a pickup time that works for both of "
            "you, so the deal is released. The item is still listed."
        },
    )


# ---------- Confirmation and sale


def request_confirm(deal_id: str, side: str, token: str) -> None:
    """Store this side's task token and ask the student. The state machine waits."""
    _update(deal_id, **{f"confirm_token_{side}": token})
    deal = _deal(deal_id)
    notify.dm(
        deal[f"{side}_id"],
        {
            "content": f"Confirm the deal? **{deal.get('title', 'Item')}** for "
            f"**${deal['agreed_price']}**. {pickup_line(deal)}. "
            "Nothing is final until you both say yes.",
            "components": [
                notify.row(
                    notify.button("Confirm deal", f"confirm:{deal_id}", notify.SUCCESS),
                    notify.button("Decline", f"decline:{deal_id}", notify.DANGER),
                )
            ],
        },
    )


def finalize(deal_id: str, own_arn: str | None = None) -> dict:
    """Both confirmed. First deal to get here wins the item."""
    deal = _deal(deal_id)
    try:
        store.table("listings").update_item(
            Key={"listing_id": deal["listing_id"]},
            UpdateExpression="SET #s = :sold, sold_deal = :d",
            ConditionExpression=Attr("status").eq("open"),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":sold": "sold", ":d": deal_id},
        )
    except store.conditional_failed():
        _update(deal_id, state="closed", close_reason="lost", updated_at=store.now_iso())
        _dm_both(deal, {"content": "**Haggle:** Sorry, the item was sold in another deal first."})
        return {"result": "lost"}

    _update(deal_id, state="confirmed", updated_at=store.now_iso())
    _set_status("wants", {"want_id": deal["want_id"]}, "fulfilled")

    # Identities are revealed only now, after both students confirmed.
    done = (
        f"**Deal confirmed:** {deal.get('title', 'the item')} for ${deal['agreed_price']}. "
        f"{pickup_line(deal)}. Pay in person at pickup; Haggle never handles money.\n"
        "Can't make it? Use `/cancel` here or Cancel booking on the website."
    )
    buyer, seller = notify.display_name(deal["buyer_id"]), notify.display_name(deal["seller_id"])
    notify.dm(deal["seller_id"], {"content": f"{done}\nThe buyer is {buyer}."})
    notify.dm(deal["buyer_id"], {"content": f"{done}\nThe seller is {seller}."})
    close_others(deal)
    if own_arn:
        schedule_followups(deal, own_arn)
    return {"result": "confirmed"}


def close_others(winner: dict) -> None:
    """Close every other live negotiation on the same listing with 'item sold'."""
    resp = store.table("deals").query(
        IndexName="by_listing",
        KeyConditionExpression=Key("listing_id").eq(winner["listing_id"]),
    )
    for other in resp.get("Items", []):
        if other["deal_id"] == winner["deal_id"] or other.get("state") not in ACTIVE + (
            "proposed",
        ):
            continue
        try:
            _update(
                other["deal_id"],
                expect=ACTIVE + ("proposed",),
                state="closed",
                close_reason="sold",
            )
        except store.conditional_failed():
            continue
        if other.get("execution_arn"):
            try:
                _sfn().stop_execution(executionArn=other["execution_arn"], cause="item sold")
            except Exception:
                log.exception("could not stop %s", other["execution_arn"])
        try:
            notify.dm(
                other["buyer_id"],
                {"content": f"**Haggle:** {other.get('title', 'That item')} was sold."},
            )
        except Exception:
            log.exception("could not tell buyer %s", other["buyer_id"])


def declined(deal_id: str, error: str) -> None:
    deal = _deal(deal_id)
    _update(deal_id, state="closed", close_reason="declined", updated_at=store.now_iso())
    reason = "no confirmation arrived in time" if error == "States.Timeout" else "it was declined"
    _dm_both(deal, {"content": f"**Haggle:** The deal is off because {reason}."})


def no_deal(deal_id: str) -> None:
    deal = _deal(deal_id)
    _update(deal_id, state="no_deal", updated_at=store.now_iso())
    _dm_both(
        deal,
        {"content": "**Haggle:** No deal this time; the two sides were too far apart."},
    )


def failed(deal_id: str) -> None:
    deal = _deal(deal_id)
    _update(deal_id, state="closed", close_reason="error", updated_at=store.now_iso())
    _dm_both(
        deal, {"content": "**Haggle:** Something went wrong with this negotiation, so I closed it."}
    )


# ---------- Reminder and handoff (EventBridge Scheduler)


def schedule_followups(deal: dict, own_arn: str, now: datetime | None = None) -> None:
    """One-off schedules that call this function back: a reminder an hour before the
    pickup and a "did it happen?" check after it."""
    now = now or datetime.now(UTC)
    start = datetime.fromisoformat(deal["slot_start"])
    end = datetime.fromisoformat(deal["slot_end"])
    jobs = [("remind", start - REMINDER_BEFORE), ("handoff", end + HANDOFF_AFTER)]
    for action, when in jobs:
        if when <= now + timedelta(minutes=1):
            continue  # too close to bother; the confirmation already has the details
        try:
            _scheduler().create_schedule(
                Name=f"{deal['deal_id']}-{action}"[:64],
                ScheduleExpression=f"at({when.astimezone(UTC):%Y-%m-%dT%H:%M:%S})",
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode": "OFF"},
                ActionAfterCompletion="DELETE",
                Target={
                    "Arn": own_arn,
                    "RoleArn": os.environ["SCHEDULER_ROLE_ARN"],
                    "Input": json.dumps({"action": action, "deal_id": deal["deal_id"]}),
                },
            )
        except Exception:
            log.exception("could not schedule %s for %s", action, deal["deal_id"])


def remind(deal_id: str) -> None:
    deal = _deal(deal_id)
    if deal.get("state") != "confirmed":
        return
    for side, other in (("seller", "buyer"), ("buyer", "seller")):
        try:
            notify.dm(
                deal[f"{side}_id"],
                {
                    "content": f"**Reminder:** pickup for **{deal.get('title', 'the item')}** "
                    f"in about an hour. {pickup_line(deal)}. You're meeting "
                    f"{notify.display_name(deal[f'{other}_id'])}.",
                    "components": [
                        notify.row(
                            notify.button("Running late", f"late:{deal_id}", notify.SECONDARY)
                        )
                    ],
                },
            )
        except Exception:
            log.exception("could not remind %s", deal[f"{side}_id"])


def handoff(deal_id: str) -> None:
    deal = _deal(deal_id)
    if deal.get("state") != "confirmed":
        return
    _dm_both(
        deal,
        {
            "content": f"Did the pickup for **{deal.get('title', 'the item')}** happen?",
            "components": [
                notify.row(
                    notify.button("Done", f"done:{deal_id}", notify.SUCCESS),
                    notify.button("Didn't happen", f"noshow:{deal_id}", notify.DANGER),
                )
            ],
        },
    )


def cancelled(deal_id: str) -> None:
    """A confirmed pickup was called off (interactions.cancel_booking set the state)."""
    deal = _deal(deal_id)
    by = deal.get("cancelled_by")
    if deal.get("state") != "cancelled" or by not in ("seller", "buyer"):
        return
    other = "buyer" if by == "seller" else "seller"
    title = deal.get("title", "the item")
    notify.dm(
        deal[f"{other}_id"],
        {
            "content": f"**Haggle:** {notify.display_name(deal[f'{by}_id'])} cancelled the "
            f"pickup for **{title}**. Sorry about that."
        },
    )
    if by == "buyer":
        # The seller still wants to sell: relist and ask earlier buyers again.
        reopen(deal_id, reopen_want=False)
        return
    # The seller backed out, so the item comes down and the buyer's agent keeps looking.
    try:
        store.table("listings").update_item(
            Key={"listing_id": deal["listing_id"]},
            UpdateExpression="SET #s = :stopped",
            ConditionExpression=Attr("status").eq("sold") & Attr("sold_deal").eq(deal_id),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":stopped": "stopped"},
        )
    except store.conditional_failed():
        pass
    want = store.table("wants").get_item(Key={"want_id": deal["want_id"]}).get("Item") or {}
    # Interest from the website names one listing; only a general /want keeps searching.
    if not want.get("listing_id"):
        _set_status("wants", {"want_id": deal["want_id"]}, "open", expect="fulfilled")


def reopen(deal_id: str, reopen_want: bool = True) -> None:
    """A pickup didn't happen: relist the item and give earlier buyers another chance."""
    deal = _deal(deal_id)
    if reopen_want:
        _set_status("wants", {"want_id": deal["want_id"]}, "open", expect="fulfilled")
    try:
        store.table("listings").update_item(
            Key={"listing_id": deal["listing_id"]},
            UpdateExpression="SET #s = :open REMOVE sold_deal",
            ConditionExpression=Attr("status").eq("sold") & Attr("sold_deal").eq(deal_id),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":open": "open"},
        )
    except store.conditional_failed():
        return
    notify.dm(
        deal["seller_id"],
        {"content": f"**Haggle:** {deal.get('title', 'Your item')} is listed again."},
    )

    # Buyers who lost out when it sold get asked again, newest first.
    resp = store.table("deals").query(
        IndexName="by_listing",
        KeyConditionExpression=Key("listing_id").eq(deal["listing_id"]),
        ScanIndexForward=False,
    )
    for other in resp.get("Items", []):
        if other.get("close_reason") != "sold":
            continue
        try:
            store.table("deals").update_item(
                Key={"deal_id": other["deal_id"]},
                UpdateExpression="SET #st = :p REMOVE close_reason, execution_arn",
                ConditionExpression=Attr("state").eq("closed"),
                ExpressionAttributeNames={"#st": "state"},
                ExpressionAttributeValues={":p": "proposed"},
            )
        except store.conditional_failed():
            continue
        notify.dm(
            other["buyer_id"],
            {
                "content": f"Good news: **{other.get('title', 'an item')}** is available "
                "again. Start haggling?",
                "components": [
                    notify.row(
                        notify.button(
                            "Start haggling", f"haggle:{other['deal_id']}", notify.SUCCESS
                        ),
                        notify.button(
                            "Not interested", f"pass:{other['deal_id']}", notify.SECONDARY
                        ),
                    )
                ],
            },
        )


def handler(event: dict, context):
    action, deal_id = event["action"], event["deal_id"]
    if action == "start":
        return start(deal_id)
    if action == "agreed":
        # Without a price this is the buyer saying yes to the seller's final offer.
        price = event.get("price")
        if price is None:
            price = _deal(deal_id)["last_offer_seller"]
        return agreed(deal_id, int(price))
    if action == "schedule":
        return schedule(deal_id)
    if action == "request_window":
        return request_window(deal_id, event["side"], event["token"])
    if action == "released":
        return released(deal_id)
    if action == "request_confirm":
        return request_confirm(deal_id, event["side"], event["token"])
    if action == "finalize":
        return finalize(deal_id, getattr(context, "invoked_function_arn", None))
    if action == "declined":
        return declined(deal_id, event.get("error", ""))
    if action == "no_deal":
        return no_deal(deal_id)
    if action == "failed":
        return failed(deal_id)
    if action == "remind":
        return remind(deal_id)
    if action == "handoff":
        return handoff(deal_id)
    if action == "cancelled":
        return cancelled(deal_id)
    if action == "reopen":
        return reopen(deal_id)
    raise ValueError(f"unknown action {action}")
