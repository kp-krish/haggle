"""Offer math and accept rule. Code picks every number; the model only writes words.

Pure Python: no AWS or Discord imports, so negotiations can be replayed anywhere.

Each side's agent calls ``next_move`` with only its own ``Side``. The other side's limit
is never an input, so nothing here can leak it.

Turn order for one deal (T = ROUNDS):
    seller t=0   asking price (the published listing)
    buyer  t=0   opening offer O
    seller t=1 .. T, buyer t=1 .. T, alternating
    seller final turn (t = T+1): accept the buyer's last offer or walk away
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["seller", "buyer"]
Action = Literal["offer", "accept", "walk"]

ROUNDS = 6
OPENING_FRACTION = 0.6
STYLE_BETA = {"patient": 0.5, "balanced": 1.0, "quick": 2.0}


@dataclass(frozen=True)
class Side:
    """One side's private view of a deal.

    ``limit`` is the seller's floor F or the buyer's ceiling C.
    ``asking`` is the public asking price A, known to both sides.
    """

    role: Role
    asking: int
    limit: int
    style: str = "balanced"
    # Fraction of the concession range the agent keeps in reserve: its offers stop
    # short of the limit by this much, so the final offer doesn't reveal the limit.
    # It still accepts anything within the real limit in the final rounds.
    hold_back: float = 0.0
    # Buyer only: where the agent opens (the low end of a budget range set on the
    # website). None means the default, 60% of the asking price.
    opening: int | None = None

    def __post_init__(self) -> None:
        if self.role not in ("seller", "buyer"):
            raise ValueError(f"unknown role {self.role!r}")
        if self.style not in STYLE_BETA:
            raise ValueError(f"unknown style {self.style!r}")
        if self.asking < 1 or self.limit < 1:
            raise ValueError("prices must be positive whole dollars")
        if self.role == "seller" and self.limit > self.asking:
            raise ValueError("floor cannot be above the asking price")
        if not 0 <= self.hold_back <= 0.5:
            raise ValueError("hold_back must be between 0 and 0.5")
        if self.opening is not None and not 1 <= self.opening <= self.limit:
            raise ValueError("opening offer must be between $1 and the buyer's max")


@dataclass(frozen=True)
class Move:
    action: Action
    amount: int | None = None


def opening_offer(asking: int, ceiling: int) -> int:
    """Buyer's first offer: 60% of asking, capped at the ceiling, rounded down."""
    return max(1, min(math.floor(OPENING_FRACTION * asking), ceiling))


def reserve_dollars(hold_back: float, concession_range: int) -> int:
    """Whole dollars held back from a range. At least $1 when holding back at all, and
    never more than half the range, so the agent still concedes."""
    if hold_back <= 0 or concession_range < 2:
        return 0
    return min(concession_range // 2, max(1, round(hold_back * concession_range)))


def _buyer_base(side: Side) -> int:
    """The buyer's unclamped starting point: their chosen opening, else 60% of asking."""
    if side.opening is not None:
        return side.opening
    return math.floor(OPENING_FRACTION * side.asking)


def offer_target(side: Side) -> int:
    """Where this side's offers end up at the last round: its limit, minus the reserve."""
    if side.role == "seller":
        return side.limit + reserve_dollars(side.hold_back, side.asking - side.limit)
    base = _buyer_base(side)
    # If the ceiling is below 60% of asking, hold back from the ceiling itself, so the
    # opening offer isn't the ceiling either.
    span = max(side.limit - base, math.ceil(0.2 * side.limit))
    return max(1, side.limit - reserve_dollars(side.hold_back, span))


def planned_offer(side: Side, t: int) -> int:
    """The offer this side plans to make at round ``t`` (0..T), in whole dollars.

    Seller rounds up and buyer rounds down, so rounding never crosses a limit.
    """
    t = min(max(t, 0), ROUNDS)
    progress = (t / ROUNDS) ** (1 / STYLE_BETA[side.style])
    target = offer_target(side)
    if side.role == "seller":
        raw = side.asking - (side.asking - target) * progress
        return max(target, math.ceil(raw - 1e-9))
    start = max(1, min(_buyer_base(side), target))
    raw = start + (target - start) * progress
    return min(target, math.floor(raw + 1e-9))


def should_accept(side: Side, t: int, their_offer: int) -> bool:
    """Accept when the other side's offer is at least as good as our own next planned
    offer and within our limit. In the final rounds, anything within the limit."""
    within = their_offer >= side.limit if side.role == "seller" else their_offer <= side.limit
    if not within:
        return False
    if t >= ROUNDS:
        return True
    planned = planned_offer(side, t)
    return their_offer >= planned if side.role == "seller" else their_offer <= planned


def next_move(
    side: Side,
    t: int,
    their_offer: int | None,
    own_last: int | None = None,
) -> Move:
    """Decide this side's move at round ``t``.

    ``their_offer`` is the other side's latest offer (None before they have made one).
    ``own_last`` is this side's previous offer; offers never move back from it unless the
    owner has since tightened their limit, in which case the limit wins.
    """
    if their_offer is not None and should_accept(side, t, their_offer):
        return Move("accept", their_offer)
    if t > ROUNDS:
        return Move("walk")

    amount = planned_offer(side, t)
    if own_last is not None:
        if side.role == "seller":
            amount = max(side.limit, min(amount, own_last))
        else:
            amount = min(side.limit, max(amount, own_last))
    return Move("offer", amount)


@dataclass
class Turn:
    role: Role
    t: int
    action: Action
    amount: int | None


@dataclass
class Result:
    price: int | None
    turns: list[Turn] = field(default_factory=list)

    @property
    def agreed(self) -> bool:
        return self.price is not None


def simulate(
    asking: int,
    floor: int,
    ceiling: int,
    seller_style: str = "balanced",
    buyer_style: str = "balanced",
    seller_hold: float = 0.0,
    buyer_hold: float = 0.0,
) -> Result:
    """Replay a whole negotiation with both sides' limits. For tests and local runs only;
    production never holds both limits in one place."""
    seller = Side("seller", asking, floor, seller_style, seller_hold)
    buyer = Side("buyer", asking, ceiling, buyer_style, buyer_hold)
    result = Result(price=None, turns=[Turn("seller", 0, "offer", asking)])
    last = {"seller": asking, "buyer": None}

    schedule: list[tuple[Side, int]] = [(buyer, 0)]
    for t in range(1, ROUNDS + 1):
        schedule += [(seller, t), (buyer, t)]
    schedule.append((seller, ROUNDS + 1))

    for side, t in schedule:
        other = "buyer" if side.role == "seller" else "seller"
        move = next_move(side, t, last[other], last[side.role])
        result.turns.append(Turn(side.role, t, move.action, move.amount))
        if move.action == "accept":
            result.price = move.amount
            break
        if move.action == "walk":
            break
        last[side.role] = move.amount
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description="Replay a Haggle negotiation locally.")
    parser.add_argument("--asking", type=int, required=True)
    parser.add_argument("--floor", type=int, required=True)
    parser.add_argument("--ceiling", type=int, required=True)
    parser.add_argument("--seller-style", default="balanced", choices=STYLE_BETA)
    parser.add_argument("--buyer-style", default="balanced", choices=STYLE_BETA)
    parser.add_argument("--seller-hold", type=float, default=0.1)
    parser.add_argument("--buyer-hold", type=float, default=0.1)
    args = parser.parse_args()

    result = simulate(
        args.asking,
        args.floor,
        args.ceiling,
        args.seller_style,
        args.buyer_style,
        args.seller_hold,
        args.buyer_hold,
    )
    for turn in result.turns:
        label = "Seller's agent" if turn.role == "seller" else "Buyer's agent"
        detail = f"${turn.amount}" if turn.amount is not None else ""
        print(f"{label:15} t={turn.t}  {turn.action:6} {detail}")
    print(f"\nAgreed at ${result.price}" if result.agreed else "\nNo deal: too far apart")


if __name__ == "__main__":
    _main()
