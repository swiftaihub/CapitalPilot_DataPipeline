"""Optional option-chain ingestion providers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf


def fetch_yfinance_option_chain(
    ticker: str,
    *,
    max_expirations: int | None = None,
    as_of_date: date | None = None,
) -> pd.DataFrame:
    """Fetch option-chain rows from yfinance for one ticker."""
    normalized = ticker.upper().strip()
    ticker_obj = yf.Ticker(normalized)
    expirations = list(ticker_obj.options or [])
    if max_expirations is not None:
        expirations = expirations[:max_expirations]
    if not expirations:
        return empty_options_frame()

    rows: list[dict[str, Any]] = []
    current_date = as_of_date or date.today()
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for expiration in expirations:
        try:
            chain = ticker_obj.option_chain(expiration)
        except Exception:
            continue
        for option_type, frame in [("call", chain.calls), ("put", chain.puts)]:
            if frame is None or frame.empty:
                continue
            for row in frame.to_dict("records"):
                bid = _number(row.get("bid"))
                ask = _number(row.get("ask"))
                mid = (bid + ask) / 2 if bid is not None and ask is not None and ask >= bid else None
                rows.append(
                    {
                        "ticker": normalized,
                        "as_of_date": current_date,
                        "expiration_date": expiration,
                        "option_type": option_type,
                        "strike": row.get("strike"),
                        "last_price": row.get("lastPrice"),
                        "bid": bid,
                        "ask": ask,
                        "mid": mid,
                        "volume": row.get("volume"),
                        "open_interest": row.get("openInterest"),
                        "implied_volatility": row.get("impliedVolatility"),
                        "in_the_money": row.get("inTheMoney"),
                        "source": "yfinance",
                        "updated_at": updated_at,
                    }
                )
    return pd.DataFrame.from_records(rows, columns=empty_options_frame().columns) if rows else empty_options_frame()


def empty_options_frame() -> pd.DataFrame:
    """Return an empty normalized option-chain dataframe."""
    return pd.DataFrame(
        columns=[
            "ticker",
            "as_of_date",
            "expiration_date",
            "option_type",
            "strike",
            "last_price",
            "bid",
            "ask",
            "mid",
            "volume",
            "open_interest",
            "implied_volatility",
            "in_the_money",
            "source",
            "updated_at",
        ]
    )


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if pd.notna(parsed) else None
