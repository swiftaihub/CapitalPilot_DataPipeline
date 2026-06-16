"""Refresh optional option-chain data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import load_options_config, load_watchlist
from src.db import upsert_raw_options_chain
from src.options_client import fetch_yfinance_option_chain
from src.pipeline_logging import finish_run, finish_task, log_error, start_run, start_task


def parse_args() -> argparse.Namespace:
    config = load_options_config()
    parser = argparse.ArgumentParser(description="Refresh option-chain data for configured tickers.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--provider", default=config.get("provider", "yfinance"))
    parser.add_argument("--tickers", default=None)
    parser.add_argument("--max-expirations-per-ticker", type=int, default=int(config.get("max_expirations_per_ticker", 2)))
    parser.add_argument("--force", action="store_true", help="Run even if config/options_config.yaml has enabled: false.")
    return parser.parse_args()


def _tickers_from_args(value: str | None) -> list[str]:
    if value:
        return sorted({item.upper().strip() for item in value.split(",") if item.strip()})
    config = load_options_config()
    tickers: list[str] = []
    if config.get("watchlist", {}).get("use_config_watchlist", True):
        for item in load_watchlist():
            ticker = item.get("ticker") if isinstance(item, dict) else item
            if ticker:
                tickers.append(str(ticker).upper().strip())
    tickers.extend(str(item).upper().strip() for item in config.get("watchlist", {}).get("extra_tickers", []))
    return sorted(set(tickers))


def main() -> int:
    args = parse_args()
    run_id = start_run("refresh_options", target=args.target, metadata={"provider": args.provider})
    task_id = start_task(run_id, "options", target=args.target)
    try:
        config = load_options_config()
        if not config.get("enabled", False) and not args.force:
            message = "Options chain ingestion is disabled in config/options_config.yaml; skipping."
            print(message)
            finish_task(task_id, status="skipped", target=args.target, row_count=0, error_message=message)
            finish_run(run_id, status="skipped", target=args.target)
            return 0

        if args.provider.lower().strip() != "yfinance":
            raise ValueError("Only the optional yfinance options provider is implemented in this repo.")

        frames: list[pd.DataFrame] = []
        for ticker in _tickers_from_args(args.tickers):
            try:
                print(f"Fetching yfinance option chain for {ticker}")
                frame = fetch_yfinance_option_chain(ticker, max_expirations=args.max_expirations_per_ticker)
                frames.append(frame)
            except Exception as exc:
                print(f"Warning: failed options chain for {ticker}: {exc}")
                log_error(run_id=run_id, task_name="options", error=exc, target=args.target, context={"ticker": ticker})

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        upserted = upsert_raw_options_chain(combined, target=args.target)
        finish_task(task_id, status="success", target=args.target, row_count=upserted)
        finish_run(run_id, status="success", target=args.target)
        print(f"Upserted {upserted} option-chain rows.")
        return 0
    except Exception as exc:
        log_error(run_id=run_id, task_name="options", error=exc, target=args.target, context={"provider": args.provider})
        finish_task(task_id, status="failed", target=args.target, error_message=str(exc))
        finish_run(run_id, status="failed", target=args.target)
        print(f"Options refresh failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
