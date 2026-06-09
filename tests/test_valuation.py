from src.valuation import PLANNED_VALUATION_METRICS, get_phase1_valuation_notice, valuation_signal_payload


def test_valuation_placeholder_is_non_advice():
    payload = valuation_signal_payload("NVDA")

    assert payload["ticker"] == "NVDA"
    assert payload["valuation_signal"] == "Phase 1 price-only placeholder"
    assert payload["is_investment_advice"] is False
    assert "SEC company facts" in payload["message"]


def test_planned_valuation_metrics_include_core_fundamentals():
    assert "Revenue TTM" in PLANNED_VALUATION_METRICS
    assert "FCF Yield" in PLANNED_VALUATION_METRICS
    assert "Revenue Growth YoY" in PLANNED_VALUATION_METRICS
    assert "Phase 2" in get_phase1_valuation_notice()

