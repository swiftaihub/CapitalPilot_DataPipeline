"""Refresh public political and high-official disclosure transactions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db import upsert_raw_political_disclosure_reports, upsert_raw_political_transactions
from src.pipeline_logging import finish_run, finish_task, log_error, start_run, start_task
from src.political_disclosures_client import provider_for_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh public official disclosure transactions.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--source", choices=["senate", "house", "oge", "manual", "all"], default="manual")
    parser.add_argument("--days-back", type=int, default=365)
    parser.add_argument("--officials", default=None)
    parser.add_argument("--manual-file", default=None)
    parser.add_argument("--max-reports", type=int, default=50, help="Limit official-source report downloads; use 0 for no limit.")
    return parser.parse_args()


def _officials(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _sources(value: str) -> list[str]:
    if value == "all":
        return ["manual", "senate", "house", "oge"]
    return [value]


def main() -> int:
    args = parse_args()
    run_id = start_run(
        "refresh_political_trades",
        target=args.target,
        metadata={"source": args.source, "days_back": args.days_back},
    )
    task_id = start_task(run_id, "political_trades", target=args.target)
    try:
        report_frames: list[pd.DataFrame] = []
        transaction_frames: list[pd.DataFrame] = []
        for source in _sources(args.source):
            try:
                provider = provider_for_source(source, manual_file=args.manual_file)
                print(f"Fetching political disclosures source={source}")
                reports, transactions = provider.fetch(
                    days_back=args.days_back,
                    officials=_officials(args.officials),
                    max_reports=None if args.max_reports == 0 else args.max_reports,
                )
                report_frames.append(reports)
                transaction_frames.append(transactions)
            except Exception as exc:
                print(f"Warning: failed political disclosure source={source}: {exc}")
                log_error(run_id=run_id, task_name="political_trades", error=exc, target=args.target, context={"source": source})

        reports_df = pd.concat(report_frames, ignore_index=True) if report_frames else pd.DataFrame()
        transactions_df = pd.concat(transaction_frames, ignore_index=True) if transaction_frames else pd.DataFrame()
        upserted_reports = upsert_raw_political_disclosure_reports(reports_df, target=args.target)
        upserted_transactions = upsert_raw_political_transactions(transactions_df, target=args.target)
        finish_task(
            task_id,
            status="success",
            target=args.target,
            row_count=upserted_reports + upserted_transactions,
            metadata={"reports": upserted_reports, "transactions": upserted_transactions, "source": args.source},
        )
        finish_run(run_id, status="success", target=args.target)
        print(f"Upserted {upserted_reports} disclosure reports and {upserted_transactions} transactions.")
        return 0
    except Exception as exc:
        log_error(run_id=run_id, task_name="political_trades", error=exc, target=args.target)
        finish_task(task_id, status="failed", target=args.target, error_message=str(exc))
        finish_run(run_id, status="failed", target=args.target)
        print(f"Political disclosure refresh failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
