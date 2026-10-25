import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import strategy
from strategy import ROUNDS, Side, next_move, opening_offer, planned_offer, simulate

STYLES = list(strategy.STYLE_BETA)


@st.composite
def deals(draw):
    asking = draw(st.integers(min_value=1, max_value=5000))
    floor = draw(st.integers(min_value=1, max_value=asking))
    ceiling = draw(st.integers(min_value=1, max_value=asking * 2))
    return asking, floor, ceiling, draw(st.sampled_from(STYLES)), draw(st.sampled_from(STYLES))


@settings(max_examples=2000)
@given(deals())
def test_no_offer_ever_crosses_a_limit(deal):
    asking, floor, ceiling, s_style, b_style = deal
    result = simulate(asking, floor, ceiling, s_style, b_style)
    for turn in result.turns:
        if turn.amount is None:
            continue
        if turn.role == "seller" and turn.action == "offer":
            assert floor <= turn.amount <= asking
        if turn.role == "buyer" and turn.action == "offer":
            assert 1 <= turn.amount <= ceiling
    if result.agreed:
        assert floor <= result.price <= ceiling


@settings(max_examples=2000)
@given(deals())
def test_deal_happens_exactly_when_limits_overlap(deal):
    asking, floor, ceiling, s_style, b_style = deal
    assert simulate(asking, floor, ceiling, s_style, b_style).agreed == (floor <= ceiling)


@settings(max_examples=1000)
@given(deals())
def test_offers_never_go_back_on_a_concession(deal):
    asking, floor, ceiling, s_style, b_style = deal
    result = simulate(asking, floor, ceiling, s_style, b_style)
    seller = [t.amount for t in result.turns if t.role == "seller" and t.action == "offer"]
    buyer = [t.amount for t in result.turns if t.role == "buyer" and t.action == "offer"]
    assert seller == sorted(seller, reverse=True)
    assert buyer == sorted(buyer)


def test_fridge_example_lands_between_the_limits():
    result = simulate(asking=70, floor=45, ceiling=65)
    assert result.turns[1].amount == 42  # buyer opens at 60% of asking
    assert result.agreed and 45 <= result.price <= 65


def test_failed_negotiation_reveals_no_numbers_in_the_final_move():
    result = simulate(asking=70, floor=60, ceiling=50)
    assert not result.agreed
    assert result.turns[-1].action == "walk"
    assert result.turns[-1].amount is None


def test_opening_offer_is_capped_at_ceiling():
    assert opening_offer(asking=100, ceiling=40) == 40
    assert opening_offer(asking=100, ceiling=90) == 60


@pytest.mark.parametrize("style", STYLES)
def test_curve_ends_at_the_limit(style):
    assert planned_offer(Side("seller", 70, 45, style), 0) == 70
    assert planned_offer(Side("seller", 70, 45, style), ROUNDS) == 45
    assert planned_offer(Side("buyer", 70, 65, style), ROUNDS) == 65


def test_patient_concedes_later_than_quick():
    patient = planned_offer(Side("seller", 100, 50, "patient"), 2)
    quick = planned_offer(Side("seller", 100, 50, "quick"), 2)
    assert patient > quick


def test_tightened_limit_wins_over_previous_offer():
    # Seller offered $50, then raised their floor to $55 mid-deal.
    move = next_move(Side("seller", 70, 55), t=5, their_offer=40, own_last=50)
    assert move == strategy.Move("offer", 55)


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        Side("seller", asking=50, limit=60)
    with pytest.raises(ValueError):
        Side("buyer", asking=50, limit=40, style="aggressive")


# ---------- hidden reserve (hold_back)

HOLDS = st.floats(min_value=0.05, max_value=0.20)


@settings(max_examples=2000)
@given(deals(), HOLDS, HOLDS)
def test_reserve_never_crosses_a_limit_and_never_deals_without_overlap(deal, sh, bh):
    asking, floor, ceiling, s_style, b_style = deal
    result = simulate(asking, floor, ceiling, s_style, b_style, sh, bh)
    for turn in result.turns:
        if turn.action == "offer" and turn.role == "seller":
            assert floor <= turn.amount <= asking
        if turn.action == "offer" and turn.role == "buyer":
            assert 1 <= turn.amount <= ceiling
    if floor > ceiling:
        assert not result.agreed
    if result.agreed:
        assert floor <= result.price <= ceiling


@settings(max_examples=2000)
@given(deals(), HOLDS, HOLDS)
def test_reserve_still_closes_deals_with_room_to_spare(deal, sh, bh):
    asking, floor, ceiling, s_style, b_style = deal
    seller_reserve = strategy.offer_target(Side("seller", asking, floor, s_style, sh)) - floor
    buyer_reserve = ceiling - strategy.offer_target(Side("buyer", asking, ceiling, b_style, bh))
    if ceiling - floor >= min(seller_reserve, buyer_reserve):
        assert simulate(asking, floor, ceiling, s_style, b_style, sh, bh).agreed


@settings(max_examples=2000)
@given(deals(), HOLDS)
def test_final_offers_do_not_reveal_the_limit(deal, hold):
    asking, floor, ceiling, s_style, b_style = deal
    seller = Side("seller", asking, floor, s_style, hold)
    buyer = Side("buyer", asking, ceiling, b_style, hold)
    if asking - floor >= 2:
        assert planned_offer(seller, ROUNDS) > floor
    if ceiling >= 10:
        assert planned_offer(buyer, ROUNDS) < ceiling
        assert opening_offer(asking, strategy.offer_target(buyer)) < ceiling


def test_fridge_example_matches_the_spec_with_a_reserve():
    result = simulate(70, 45, 65, seller_hold=0.1, buyer_hold=0.1)
    assert result.price == 55


def test_reserve_is_bounded():
    assert strategy.reserve_dollars(0.2, 1) == 0
    assert strategy.reserve_dollars(0.01, 10) == 1
    assert strategy.reserve_dollars(0.5, 10) == 5
    with pytest.raises(ValueError):
        Side("seller", 70, 45, hold_back=0.9)
