"""Matcher: pairs listings with wants as they open. Triggered by DynamoDB Streams.

Matching uses only public fields (category, words, campus area). The matcher has no
KMS access, so it cannot see anyone's floor or ceiling; whether a price works is for
the negotiation to find out.
"""

from __future__ import annotations

import hashlib
import logging
import re

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer

import notify
import store
from categories import neighbours

log = logging.getLogger()
log.setLevel(logging.INFO)

MAX_MATCHES_PER_EVENT = 5
CROSS_CATEGORY_MIN_HITS = 2
STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "in", "on", "of", "to", "my", "i", "is", "it",
    "cheap", "used", "good", "great", "condition", "works", "small", "big", "new", "like",
    "budget", "nice", "old", "one", "some", "any",
}  # fmt: skip
_WORD = re.compile(r"[a-z0-9]+")
_deserialize = TypeDeserializer().deserialize


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def words(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS}


def listing_text(listing: dict) -> str:
    return " ".join(str(listing.get(k, "")) for k in ("title", "description", "seller_notes"))


def score(listing: dict, want: dict) -> int:
    """How many of the buyer's search terms the listing mentions. 0 means no match.

    A multi-word keyword ("desk chair") counts when all its words appear. Across
    categories the bar is higher, so a lamp listing doesn't match "lamp oil".
    """
    if listing.get("seller_id") == want.get("buyer_id"):
        return 0
    have = words(listing_text(listing))
    phrases = [words(k) for k in want.get("keywords", [])]
    hits = sum(1 for p in phrases if p and p <= have)
    hits += len(words(want.get("query", "")) & have)
    if listing.get("category") != want.get("category") and hits < CROSS_CATEGORY_MIN_HITS:
        return 0
    if hits and listing.get("area") == want.get("area"):
        hits += 1
    return hits


def deal_id_for(listing_id: str, want_id: str) -> str:
    """Deterministic, so the same pair is never proposed twice."""
    return "deal_" + hashlib.sha256(f"{listing_id}|{want_id}".encode()).hexdigest()[:24]


def _open_candidates(table: str, category: str) -> list[dict]:
    """Open items in this category and its neighbours (see categories.neighbours)."""
    items = []
    for cat in neighbours(category):
        resp = store.table(table).query(
            IndexName="by_category",
            KeyConditionExpression=Key("category").eq(cat),
            ScanIndexForward=False,
            Limit=100,
        )
        items += [i for i in resp.get("Items", []) if i.get("status") == "open"]
    return items


def propose(listing: dict, want: dict) -> bool:
    """Create the proposed deal and ask the buyer. False if this pair was already proposed."""
    deal_id = deal_id_for(listing["listing_id"], want["want_id"])
    try:
        store.table("deals").put_item(
            Item={
                "deal_id": deal_id,
                "listing_id": listing["listing_id"],
                "want_id": want["want_id"],
                "seller_id": listing["seller_id"],
                "buyer_id": want["buyer_id"],
                "title": listing.get("title", ""),
                "description": listing.get("description", ""),
                "asking": listing["asking"],
                "state": "proposed",
                "created_at": store.now_iso(),
            },
            ConditionExpression="attribute_not_exists(deal_id)",
        )
    except store.conditional_failed():
        return False

    embed = {
        "title": listing.get("title", "Item"),
        "description": listing.get("description", ""),
        "color": notify.COLOR,
        "fields": [
            {"name": "Asking", "value": f"${listing['asking']}", "inline": True},
            {"name": "Campus area", "value": listing.get("area", "?"), "inline": True},
        ],
    }
    if listing.get("channel_id") and listing.get("message_id"):
        embed["url"] = (
            f"https://discord.com/channels/{store.discord_secret()['guild_id']}/"
            f"{listing['channel_id']}/{listing['message_id']}"
        )
    try:
        notify.dm(
            want["buyer_id"],
            {
                "content": f"I found a match for **{want['query']}**. Start haggling? "
                "I'll negotiate within your max price and never reveal it.",
                "embeds": [embed],
                "components": [
                    notify.row(
                        notify.button("Start haggling", f"haggle:{deal_id}", notify.SUCCESS),
                        notify.button("Not interested", f"pass:{deal_id}", notify.SECONDARY),
                    )
                ],
            },
        )
    except Exception:
        # Undo so the stream retry proposes again instead of skipping a buyer never asked.
        store.table("deals").delete_item(Key={"deal_id": deal_id})
        raise
    return True


def on_listing_open(listing: dict) -> int:
    wants = _open_candidates("wants", listing.get("category", "other"))
    ranked = sorted(((score(listing, w), w) for w in wants), key=lambda pair: pair[0], reverse=True)
    return sum(propose(listing, w) for s, w in ranked[:MAX_MATCHES_PER_EVENT] if s > 0)


def on_want_open(want: dict) -> int:
    listings = _open_candidates("listings", want.get("category", "other"))
    ranked = sorted(
        ((score(item, want), item) for item in listings),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return sum(propose(item, want) for s, item in ranked[:MAX_MATCHES_PER_EVENT] if s > 0)


def _image(record: dict, which: str) -> dict:
    """Decode a stream image, dropping binary attributes (the encrypted limits).

    Streams deliver binary as base64 text, which TypeDeserializer rejects; the matcher
    has no use for ciphertext anyway, so it never even holds it.
    """
    raw = record.get("dynamodb", {}).get(which) or {}
    return {k: _deserialize(v) for k, v in raw.items() if "B" not in v and "BS" not in v}


def handler(event: dict, context) -> dict:
    proposed = 0
    for record in event.get("Records", []):
        new, old = _image(record, "NewImage"), _image(record, "OldImage")
        if new.get("status") != "open" or old.get("status") == "open":
            continue  # only act on the transition to open
        try:
            if "listing_id" in new:
                proposed += on_listing_open(new)
            elif "want_id" in new:
                proposed += on_want_open(new)
        except Exception:
            log.exception("matching failed for %s", new.get("listing_id") or new.get("want_id"))
            raise
    log.info("proposed %d deals", proposed)
    return {"proposed": proposed}
