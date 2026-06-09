"""Macro research calculations shared by dbt tests, services, and UI code."""

from __future__ import annotations

from math import isnan
from typing import Any


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and isnan(value))


def _lt(value: Any, threshold: float) -> bool:
    return not _is_missing(value) and float(value) < threshold


def _gt(value: Any, threshold: float) -> bool:
    return not _is_missing(value) and float(value) > threshold


def calculate_cpi_yoy(current_cpi: float | None, prior_year_cpi: float | None) -> float | None:
    """Calculate year-over-year CPI growth as a decimal."""
    if _is_missing(current_cpi) or _is_missing(prior_year_cpi):
        return None
    if float(prior_year_cpi) == 0:
        return None
    return float(current_cpi) / float(prior_year_cpi) - 1.0


def calculate_macro_regime_score(
    *,
    fed_funds_3m_change: float | None = None,
    cpi_yoy_3m_change: float | None = None,
    unemployment_3m_change: float | None = None,
    ten_two_spread: float | None = None,
    vix: float | None = None,
    dollar_3m_change_pct: float | None = None,
) -> int:
    """Score macro conditions using the Phase 1 deterministic rules."""
    score = 0
    if _lt(fed_funds_3m_change, 0):
        score += 1
    if _lt(cpi_yoy_3m_change, 0):
        score += 1
    if _gt(unemployment_3m_change, 0.3):
        score -= 1
    if _lt(ten_two_spread, 0):
        score -= 1
    if _gt(vix, 25):
        score -= 1
    if _gt(dollar_3m_change_pct, 0.05):
        score -= 1
    return score


def label_macro_regime(score: int | None) -> str:
    """Return the dashboard label for a macro regime score."""
    if score is None:
        return "Insufficient data"
    if score >= 2:
        return "Risk-on / Easing-supportive"
    if 0 <= score <= 1:
        return "Neutral / Mixed"
    return "Risk-off / Macro pressure"


def explain_macro_regime(score: int | None) -> str:
    """Return the dashboard explanation for a macro regime score."""
    if score is None:
        return "Insufficient macro data to classify regime."
    if score >= 2:
        return (
            "Macro backdrop appears more supportive for risk assets, "
            "but valuation and earnings still matter."
        )
    if 0 <= score <= 1:
        return "Macro signals are mixed. Avoid over-interpreting a single indicator."
    return (
        "Macro backdrop shows pressure from rates, volatility, dollar strength, "
        "labor weakness, or curve inversion."
    )

