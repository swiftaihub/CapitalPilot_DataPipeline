"""Refresh configurable daily market-news metadata."""

from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import load_news_sources_config, load_watchlist
from src.db import upsert_raw_news_articles
from src.news_client import MissingProviderSecret, enabled_news_categories, provider_from_config
from src.pipeline_logging import finish_run, finish_task, log_error, start_run, start_task


def parse_args() -> argparse.Namespace:
    config = load_news_sources_config()
    limits = config.get("limits", {})
    parser = argparse.ArgumentParser(description="Refresh CapitalPilot news article metadata.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--date", default=date_cls.today().isoformat())
    parser.add_argument("--days-back", type=int, default=1)
    parser.add_argument("--provider", default=config.get("default_provider", "manual"))
    parser.add_argument("--categories", default=None)
    parser.add_argument("--tickers", default=None)
    parser.add_argument("--limit-per-category", type=int, default=int(limits.get("default_limit_per_category", 25)))
    parser.add_argument("--manual-file", default=None)
    return parser.parse_args()


def _tickers_from_args(value: str | None) -> list[str]:
    if value:
        return sorted({item.upper().strip() for item in value.split(",") if item.strip()})
    tickers: list[str] = []
    for item in load_watchlist():
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            tickers.append(str(ticker).upper().strip())
    return sorted(set(tickers))


def _split_arg(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    args = parse_args()
    run_id = start_run(
        "refresh_news",
        target=args.target,
        metadata={"provider": args.provider, "date": args.date, "days_back": args.days_back},
    )
    task_id = start_task(run_id, "news", target=args.target)
    try:
        end_date = date_cls.fromisoformat(args.date)
        start_date = end_date - timedelta(days=max(args.days_back - 1, 0))
        categories = enabled_news_categories(_split_arg(args.categories))
        tickers = _tickers_from_args(args.tickers)
        provider = provider_from_config(args.provider, manual_file=args.manual_file)

        print(f"Fetching news provider={provider.name} categories={len(categories)}")
        articles = provider.fetch_articles(
            categories=categories,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            limit_per_category=args.limit_per_category,
        )
        upserted = upsert_raw_news_articles(articles, target=args.target)
        finish_task(
            task_id,
            status="success",
            target=args.target,
            row_count=upserted,
            metadata={"provider": provider.name, "categories": len(categories), "tickers": tickers},
        )
        finish_run(run_id, status="success", target=args.target)
        print(f"Upserted {upserted} news article rows.")
        return 0
    except MissingProviderSecret as exc:
        print(str(exc))
        log_error(run_id=run_id, task_name="news", error=str(exc), target=args.target, context={"provider": args.provider})
        finish_task(task_id, status="skipped", target=args.target, row_count=0, error_message=str(exc))
        finish_run(run_id, status="skipped", target=args.target)
        return 0
    except Exception as exc:
        log_error(run_id=run_id, task_name="news", error=exc, target=args.target, context={"provider": args.provider})
        finish_task(task_id, status="failed", target=args.target, error_message=str(exc))
        finish_run(run_id, status="failed", target=args.target)
        print(f"News refresh failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
