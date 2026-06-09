"""Valuation helpers for the Phase 1 price-only dashboard."""

from __future__ import annotations

PLANNED_VALUATION_METRICS = [
    "Revenue TTM",
    "Net Income TTM",
    "FCF TTM",
    "PE",
    "PS",
    "FCF Yield",
    "FCF Margin",
    "Operating Margin",
    "Net Margin",
    "Revenue Growth YoY",
]

PHASE1_VALUATION_SIGNAL = "Phase 1 price-only placeholder"


def get_phase1_valuation_notice() -> str:
    """Return the standard Phase 1 valuation placeholder notice."""
    return (
        "Fundamental valuation metrics require SEC company facts and will be "
        "implemented in Phase 2."
    )


def valuation_signal_payload(ticker: str | None = None) -> dict[str, object]:
    """Return a safe non-advice valuation payload for the MVP."""
    return {
        "ticker": ticker,
        "valuation_signal": PHASE1_VALUATION_SIGNAL,
        "message": get_phase1_valuation_notice(),
        "planned_metrics": PLANNED_VALUATION_METRICS,
        "is_investment_advice": False,
    }

