import pandas as pd

from src.technical_indicators import calculate_technical_indicators


def test_technical_indicator_calculation_on_sample_prices():
    prices = pd.DataFrame(
        {
            "ticker": ["NVDA"] * 260,
            "date": pd.date_range("2025-01-01", periods=260, freq="D"),
            "open": [100 + i * 0.5 for i in range(260)],
            "high": [101 + i * 0.5 for i in range(260)],
            "low": [99 + i * 0.5 for i in range(260)],
            "close": [100 + i * 0.5 for i in range(260)],
            "volume": [1_000_000 + i for i in range(260)],
        }
    )

    indicators = calculate_technical_indicators(prices)
    latest = indicators.iloc[-1]

    assert latest["sma_20"] > latest["sma_50"]
    assert latest["ema_12"] > latest["ema_26"]
    assert latest["macd"] > 0
    assert latest["rsi_14"] == 100
    assert latest["drawdown_52w"] == 0

