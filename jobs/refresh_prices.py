"""Refresh raw price data from yfinance."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import load_watchlist
from src.db import upsert_raw_prices
from src.price_client import fetch_price_history


def _default_start_date(years_back: int = 5) -> str:
    today = date.today()
    try:
        return today.replace(year=today.year - years_back).isoformat()
    except ValueError:
        return today.replace(year=today.year - years_back, day=28).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh CapitalPilot price data.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--start-date", default=_default_start_date())
    parser.add_argument("--end-date", default=None)
    return parser.parse_args()


def _tickers_from_watchlist() -> list[str]:
    tickers: list[str] = []
    for item in load_watchlist():
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            tickers.append(str(ticker).upper().strip())
    return sorted(set(tickers))


def main() -> int:
    args = parse_args()
    frames: list[pd.DataFrame] = []
    for ticker in _tickers_from_watchlist():
        try:
            print(f"Fetching yfinance history for {ticker}")
            frame = fetch_price_history(ticker, start_date=args.start_date, end_date=args.end_date)
            if frame.empty:
                print(f"Warning: no price data returned for {ticker}; skipping.")
                continue
            frames.append(frame)
        except Exception as exc:
            print(f"Warning: failed to fetch {ticker}: {exc}")

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    inserted = upsert_raw_prices(combined, target=args.target)
    print(f"Upserted {inserted} price rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

