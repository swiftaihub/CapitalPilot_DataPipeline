"""Price data client using yfinance for the Phase 1 MVP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf


def _safe_market_cap(ticker_obj: yf.Ticker) -> float | None:
    try:
        info: dict[str, Any] = ticker_obj.info or {}
        market_cap = info.get("marketCap")
        return float(market_cap) if market_cap is not None else None
    except Exception:
        return None


def fetch_price_history(
    ticker: str,
    *,
    start_date: str,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Fetch daily price history for one ticker."""
    normalized = ticker.upper().strip()
    ticker_obj = yf.Ticker(normalized)
    history = ticker_obj.history(start=start_date, end=end_date, auto_adjust=False)
    if history.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "market_cap",
                "source",
                "updated_at",
            ]
        )

    history = history.reset_index()
    market_cap = _safe_market_cap(ticker_obj)
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    date_column = "Date" if "Date" in history.columns else history.columns[0]
    records = pd.DataFrame(
        {
            "ticker": normalized,
            "date": pd.to_datetime(history[date_column]).dt.date,
            "open": history.get("Open"),
            "high": history.get("High"),
            "low": history.get("Low"),
            "close": history.get("Close"),
            "adj_close": history.get("Adj Close", history.get("Close")),
            "volume": history.get("Volume"),
            "market_cap": market_cap,
            "source": "yfinance",
            "updated_at": updated_at,
        }
    )
    return records.dropna(subset=["date", "close"])

