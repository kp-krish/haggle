"""Deal lifecycle steps called by the negotiation state machine.

Everything around the offer turns: opening the deal, agreement, asking each student to
confirm, finalising the sale and closing the other buyers' deals. This function has no
KMS access; it never handles a limit.
"""

from __future__ import annotations

import logging
from functools import cache

import boto3
from boto3.dynamodb.conditions import Attr, Key

import notify
import store

log = logging.getLogger()
log.setLevel(logging.INFO)

ACTIVE = ("starting", "negotiating", "confirming")


@cache
def _sfn():
    return boto3.client("stepfunctions")


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


# ---------- Steps


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
        state="confirming",
        agreed_price=price,
        updated_at=store.now_iso(),
    )
    _dm_both(
        _deal(deal_id),
        {"content": f"**Haggle:** Price agreed at ${price}. Waiting for both students to confirm."},
    )


def request_confirm(deal_id: str, side: str, token: str) -> None:
    """Store this side's task token and ask the student. The state machine waits."""
    _update(deal_id, **{f"confirm_token_{side}": token})
    deal = _deal(deal_id)
    notify.dm(
        deal[f"{side}_id"],
        {
            "content": f"Confirm the deal? **{deal.get('title', 'Item')}** for "
            f"**${deal['agreed_price']}**. Nothing is final until you both say yes.",
            "components": [
                notify.row(
                    notify.button("Confirm deal", f"confirm:{deal_id}", notify.SUCCESS),
                    notify.button("Decline", f"decline:{deal_id}", notify.DANGER),
                )
            ],
        },
    )


def finalize(deal_id: str) -> dict:
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
        _update(deal_id, state="closed", updated_at=store.now_iso())
        _dm_both(deal, {"content": "**Haggle:** Sorry, the item was sold in another deal first."})
        return {"result": "lost"}

    _update(deal_id, state="confirmed", updated_at=store.now_iso())
    store.table("wants").update_item(
        Key={"want_id": deal["want_id"]},
        UpdateExpression="SET #s = :f",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":f": "fulfilled"},
    )
    # Identities are revealed only now, after both students confirmed.
    done = f"**Deal confirmed:** {deal.get('title', 'the item')} for ${deal['agreed_price']}."
    notify.dm(deal["seller_id"], {"content": f"{done} The buyer is <@{deal['buyer_id']}>."})
    notify.dm(deal["buyer_id"], {"content": f"{done} The seller is <@{deal['seller_id']}>."})
    close_others(deal)
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
            _update(other["deal_id"], expect=ACTIVE + ("proposed",), state="closed")
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
    _update(deal_id, state="closed", updated_at=store.now_iso())
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
    _update(deal_id, state="closed", updated_at=store.now_iso())
    _dm_both(
        deal, {"content": "**Haggle:** Something went wrong with this negotiation, so I closed it."}
    )


def handler(event: dict, context):
    action, deal_id = event["action"], event["deal_id"]
    if action == "start":
        return start(deal_id)
    if action == "agreed":
        return agreed(deal_id, int(event["price"]))
    if action == "request_confirm":
        return request_confirm(deal_id, event["side"], event["token"])
    if action == "finalize":
        return finalize(deal_id)
    if action == "declined":
        return declined(deal_id, event.get("error", ""))
    if action == "no_deal":
        return no_deal(deal_id)
    if action == "failed":
        return failed(deal_id)
    raise ValueError(f"unknown action {action}")
