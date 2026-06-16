from pathlib import Path


def test_phase2_dbt_models_exist():
    root = Path(__file__).resolve().parents[1] / "dbt" / "models"
    expected = [
        "marts/mart_sec_ai_summary_queue.sql",
        "marts/mart_news_ai_summary_queue.sql",
        "marts/mart_political_trading_dashboard.sql",
        "marts/mart_accumulation_dashboard.sql",
        "marts/mart_options_dashboard.sql",
        "marts/mart_technical_dashboard.sql",
        "intermediate/int_price_technical_features.sql",
        "intermediate/int_technical_indicators.sql",
    ]

    for relative in expected:
        assert (root / relative).exists()

