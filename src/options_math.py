"""Deterministic options pricing and payoff helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

OptionType = Literal["call", "put"]
SpreadDirection = Literal["bull_call", "bear_put"]


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


@dataclass(frozen=True)
class VerticalSpreadResult:
    strategy: str
    lower_strike: float
    upper_strike: float
    net_premium: float
    max_profit: float
    max_loss: float
    breakeven: float
    is_credit: bool


def black_scholes_price(
    option_type: OptionType,
    underlying_price: float,
    strike: float,
    time_to_expiration_years: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
) -> float:
    """Return Black-Scholes price for a European call or put."""
    _validate_option_inputs(option_type, underlying_price, strike, time_to_expiration_years, volatility)
    d1, d2 = _d1_d2(
        underlying_price,
        strike,
        time_to_expiration_years,
        risk_free_rate,
        volatility,
        dividend_yield,
    )
    discount_q = math.exp(-dividend_yield * time_to_expiration_years)
    discount_r = math.exp(-risk_free_rate * time_to_expiration_years)
    if option_type == "call":
        return underlying_price * discount_q * _norm_cdf(d1) - strike * discount_r * _norm_cdf(d2)
    return strike * discount_r * _norm_cdf(-d2) - underlying_price * discount_q * _norm_cdf(-d1)


def black_scholes_greeks(
    option_type: OptionType,
    underlying_price: float,
    strike: float,
    time_to_expiration_years: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
) -> Greeks:
    """Return Black-Scholes Greeks. Theta is annualized and vega/rho are per 1.00 change."""
    _validate_option_inputs(option_type, underlying_price, strike, time_to_expiration_years, volatility)
    d1, d2 = _d1_d2(
        underlying_price,
        strike,
        time_to_expiration_years,
        risk_free_rate,
        volatility,
        dividend_yield,
    )
    discount_q = math.exp(-dividend_yield * time_to_expiration_years)
    discount_r = math.exp(-risk_free_rate * time_to_expiration_years)
    pdf_d1 = _norm_pdf(d1)

    if option_type == "call":
        delta = discount_q * _norm_cdf(d1)
        theta = (
            -underlying_price * discount_q * pdf_d1 * volatility / (2 * math.sqrt(time_to_expiration_years))
            - risk_free_rate * strike * discount_r * _norm_cdf(d2)
            + dividend_yield * underlying_price * discount_q * _norm_cdf(d1)
        )
        rho = strike * time_to_expiration_years * discount_r * _norm_cdf(d2)
    else:
        delta = -discount_q * _norm_cdf(-d1)
        theta = (
            -underlying_price * discount_q * pdf_d1 * volatility / (2 * math.sqrt(time_to_expiration_years))
            + risk_free_rate * strike * discount_r * _norm_cdf(-d2)
            - dividend_yield * underlying_price * discount_q * _norm_cdf(-d1)
        )
        rho = -strike * time_to_expiration_years * discount_r * _norm_cdf(-d2)

    gamma = discount_q * pdf_d1 / (underlying_price * volatility * math.sqrt(time_to_expiration_years))
    vega = underlying_price * discount_q * pdf_d1 * math.sqrt(time_to_expiration_years)
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def option_payoff(option_type: OptionType, underlying_price: float, strike: float, premium: float) -> float:
    """Return expiration payoff net of premium for one long option contract share-equivalent."""
    _validate_type(option_type)
    if strike <= 0 or underlying_price < 0 or premium < 0:
        raise ValueError("underlying_price must be non-negative and strike/premium must be positive.")
    intrinsic = max(underlying_price - strike, 0.0) if option_type == "call" else max(strike - underlying_price, 0.0)
    return intrinsic - premium


def vertical_spread_metrics(
    strategy: SpreadDirection,
    lower_strike: float,
    upper_strike: float,
    long_premium: float,
    short_premium: float,
) -> VerticalSpreadResult:
    """Return breakeven and max profit/loss for bull-call or bear-put vertical spreads."""
    if lower_strike <= 0 or upper_strike <= 0 or upper_strike <= lower_strike:
        raise ValueError("upper_strike must be greater than lower_strike and strikes must be positive.")
    if long_premium < 0 or short_premium < 0:
        raise ValueError("premiums must be non-negative.")
    width = upper_strike - lower_strike
    net_premium = long_premium - short_premium
    is_credit = net_premium < 0

    if strategy == "bull_call":
        if net_premium <= 0:
            max_profit = width + abs(net_premium)
            max_loss = 0.0
        else:
            max_profit = width - net_premium
            max_loss = net_premium
        breakeven = lower_strike + net_premium
    elif strategy == "bear_put":
        if net_premium <= 0:
            max_profit = width + abs(net_premium)
            max_loss = 0.0
        else:
            max_profit = width - net_premium
            max_loss = net_premium
        breakeven = upper_strike - net_premium
    else:
        raise ValueError("strategy must be 'bull_call' or 'bear_put'.")

    return VerticalSpreadResult(
        strategy=strategy,
        lower_strike=lower_strike,
        upper_strike=upper_strike,
        net_premium=net_premium,
        max_profit=max(max_profit, 0.0),
        max_loss=max(max_loss, 0.0),
        breakeven=breakeven,
        is_credit=is_credit,
    )


def probability_above_strike_proxy(
    underlying_price: float,
    strike: float,
    time_to_expiration_years: float,
    volatility: float,
    drift: float = 0.0,
) -> float:
    """Return a simple lognormal probability proxy that price finishes above strike."""
    if underlying_price <= 0 or strike <= 0 or time_to_expiration_years <= 0 or volatility <= 0:
        raise ValueError("underlying_price, strike, time_to_expiration_years, and volatility must be positive.")
    z_score = (
        math.log(underlying_price / strike)
        + (drift - 0.5 * volatility**2) * time_to_expiration_years
    ) / (volatility * math.sqrt(time_to_expiration_years))
    return _norm_cdf(z_score)


def _validate_option_inputs(
    option_type: OptionType,
    underlying_price: float,
    strike: float,
    time_to_expiration_years: float,
    volatility: float,
) -> None:
    _validate_type(option_type)
    if underlying_price <= 0:
        raise ValueError("underlying_price must be positive.")
    if strike <= 0:
        raise ValueError("strike must be positive.")
    if time_to_expiration_years <= 0:
        raise ValueError("time_to_expiration_years must be positive.")
    if volatility <= 0:
        raise ValueError("volatility must be positive.")


def _validate_type(option_type: str) -> None:
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")


def _d1_d2(
    underlying_price: float,
    strike: float,
    time_to_expiration_years: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float,
) -> tuple[float, float]:
    d1 = (
        math.log(underlying_price / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiration_years
    ) / (volatility * math.sqrt(time_to_expiration_years))
    d2 = d1 - volatility * math.sqrt(time_to_expiration_years)
    return d1, d2


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)
