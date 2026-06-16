import pytest

from src.options_math import (
    black_scholes_greeks,
    black_scholes_price,
    probability_above_strike_proxy,
    vertical_spread_metrics,
)


def test_black_scholes_outputs_are_sane():
    call = black_scholes_price("call", 100, 100, 1, 0.05, 0.2)
    put = black_scholes_price("put", 100, 100, 1, 0.05, 0.2)
    greeks = black_scholes_greeks("call", 100, 100, 1, 0.05, 0.2)

    assert call == pytest.approx(10.45, rel=0.01)
    assert put == pytest.approx(5.57, rel=0.01)
    assert 0 < greeks.delta < 1
    assert greeks.gamma > 0
    assert 0 < probability_above_strike_proxy(100, 100, 1, 0.2) < 1


def test_vertical_spreads_and_invalid_inputs():
    bull = vertical_spread_metrics("bull_call", 100, 110, long_premium=4, short_premium=1.5)
    bear = vertical_spread_metrics("bear_put", 90, 100, long_premium=5, short_premium=2)

    assert bull.max_loss == pytest.approx(2.5)
    assert bull.max_profit == pytest.approx(7.5)
    assert bull.breakeven == pytest.approx(102.5)
    assert bear.max_loss == pytest.approx(3.0)
    assert bear.max_profit == pytest.approx(7.0)
    assert bear.breakeven == pytest.approx(97.0)

    with pytest.raises(ValueError):
        black_scholes_price("call", 0, 100, 1, 0.05, 0.2)

