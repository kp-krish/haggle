"""Discord message cards: the negotiation and pickup messages as tidy embeds.

Plain run-on text is hard to scan in a DM, so each agent turn is a small card with a
coloured side bar (amber for the seller, teal for the buyer) and the number up front,
and each milestone is a card with labelled fields. Pure functions: no I/O.
"""

from __future__ import annotations

from datetime import datetime

from scheduler import format_slot

SELLER = 0xC97D35
BUYER = 0x2A9C80
HAGGLE = 0x5E9C8A  # milestones, recaps
QUIET = 0x4E5058  # endings and notices

LABEL = {"seller": "Seller's agent", "buyer": "Buyer's agent"}
VERB = {"offer": "offers", "accept": "accepts"}


def _when(deal: dict) -> str:
    return format_slot(datetime.fromisoformat(deal["slot_start"]))


def pickup_fields(deal: dict) -> list[dict]:
    return [
        {"name": "Price", "value": f"${deal['agreed_price']}", "inline": True},
        {"name": "Pickup", "value": _when(deal), "inline": True},
        {"name": "Where", "value": deal.get("spot_name", "a public spot"), "inline": True},
    ]


def agent_turn(side: str, text: str, action: str, amount: int | None, own: bool) -> dict:
    """One agent message. ``own`` marks the reader's own agent."""
    who = f"Your agent ({side})" if own else LABEL[side]
    head = f"{who} · {VERB[action]} ${amount}" if action in VERB and amount else who
    return {
        "embeds": [
            {
                "author": {"name": head},
                "description": text,
                "color": SELLER if side == "seller" else BUYER,
            }
        ]
    }


def started(deal: dict, side: str) -> dict:
    limit = "lowest price" if side == "seller" else "max price"
    return {
        "embeds": [
            {
                "title": f"Haggling started: {deal.get('title', 'your item')}",
                "description": f"Your agent never goes past your {limit}, and the other "
                "student never sees it. Every offer shows up here.",
                "fields": [{"name": "Asking", "value": f"${deal['asking']}", "inline": True}],
                "color": HAGGLE,
            }
        ]
    }


def confirm_request(deal: dict, status: str | None = None) -> dict:
    """Price and pickup, waiting for this student's yes. ``status`` replaces the
    call to action once they've answered."""
    return {
        "embeds": [
            {
                "title": f"Price agreed: {deal.get('title', 'your item')}",
                "description": status
                or "Confirm to lock it in. Nothing is final until you "
                "both say yes, and you'll see who you're meeting right after.",
                "fields": pickup_fields(deal),
                "color": HAGGLE,
            }
        ]
    }


def confirmed(deal: dict, meeting: str, other: str) -> dict:
    return {
        "embeds": [
            {
                "title": f"Deal confirmed: {deal.get('title', 'your item')}",
                "fields": [
                    *pickup_fields(deal),
                    {"name": f"Meeting the {other}", "value": meeting},
                ],
                "footer": {
                    "text": "Pay in person at pickup; Haggle never handles money. "
                    "Can't make it? Use /cancel or Cancel booking on the website."
                },
                "color": HAGGLE,
            }
        ]
    }


def reminder(deal: dict, meeting: str) -> dict:
    return {
        "embeds": [
            {
                "title": f"Pickup in about an hour: {deal.get('title', 'your item')}",
                "fields": [
                    *pickup_fields(deal),
                    {"name": "Meeting", "value": meeting},
                ],
                "color": HAGGLE,
            }
        ]
    }


def handoff(deal: dict) -> dict:
    return {
        "embeds": [
            {
                "title": f"Did the pickup happen? {deal.get('title', '')}".strip(),
                "description": "Tap Done to credit the other student. Their points and "
                "badges come from your answer.",
                "color": HAGGLE,
            }
        ]
    }


def notice(text: str) -> dict:
    """A short ending or update (deal off, item sold, no deal)."""
    return {"embeds": [{"description": text, "color": QUIET}]}
