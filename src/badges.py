"""Reliability badges, computed from the pickup counts the bot records.

Shown on listings without the seller's name, so anonymity until confirmation holds.
"""

from __future__ import annotations

RELIABLE_PICKUPS = 3
TRUSTED_PICKUPS = 10
TRUSTED_MAX_NO_SHOW_RATE = 0.05
HIDE_AFTER_NO_SHOWS = 2


def stats(user: dict | None) -> dict[str, int]:
    user = user or {}
    return {
        "pickups": int(user.get("done_count", 0)),
        "as_seller": int(user.get("done_as_seller", 0)),
        "as_buyer": int(user.get("done_as_buyer", 0)),
        "no_shows": int(user.get("no_show_count", 0)),
        "cancelled": int(user.get("cancel_count", 0)),
    }


def badges(user: dict | None) -> list[dict[str, str]]:
    """``[{"id", "label", "detail"}]``, most notable first. Empty after repeated no-shows."""
    s = stats(user)
    if s["no_shows"] >= HIDE_AFTER_NO_SHOWS:
        return []
    if s["pickups"] == 0:
        return [{"id": "new", "label": "New", "detail": "No completed pickups yet"}]

    out = []
    total = s["pickups"] + s["no_shows"]
    if s["pickups"] >= TRUSTED_PICKUPS and s["no_shows"] / total < TRUSTED_MAX_NO_SHOW_RATE:
        out.append(
            {"id": "trusted", "label": "Trusted", "detail": f"{s['pickups']} completed pickups"}
        )
    if s["no_shows"] == 0:
        for role in ("seller", "buyer"):
            if s[f"as_{role}"] >= RELIABLE_PICKUPS:
                out.append(
                    {
                        "id": f"reliable_{role}",
                        "label": f"Reliable {role}",
                        "detail": f"{s[f'as_{role}']} pickups as a {role}, no no-shows",
                    }
                )
    return out
