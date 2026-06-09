"""Streamlit-independent valuation research helpers."""

from __future__ import annotations

from src.valuation import get_phase1_valuation_notice, valuation_signal_payload


def get_valuation_snapshot(ticker: str | None = None) -> dict[str, object]:
    """Return the safe Phase 1 valuation snapshot payload."""
    payload = valuation_signal_payload(ticker)
    payload["status"] = "price_only_phase_1"
    payload["notice"] = get_phase1_valuation_notice()
    return payload

