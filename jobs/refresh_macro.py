"""Refresh raw FRED macro observations."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_secret, load_macro_series
from src.db import upsert_raw_macro_observations
from src.fred_client import fetch_fred_observations
from src.pipeline_logging import finish_run, finish_task, log_error, start_run, start_task


def _default_start_date(years_back: int = 10) -> str:
    today = date.today()
    try:
        return today.replace(year=today.year - years_back).isoformat()
    except ValueError:
        return today.replace(year=today.year - years_back, day=28).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh CapitalPilot macro data.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--start-date", default=_default_start_date())
    parser.add_argument("--end-date", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = start_run("refresh_macro", target=args.target, metadata={"start_date": args.start_date, "end_date": args.end_date})
    task_id = start_task(run_id, "macro", target=args.target)
    try:
        if not get_secret("FRED_API_KEY"):
            raise ValueError("FRED_API_KEY is required to refresh macro data.")

        frames: list[pd.DataFrame] = []
        for item in load_macro_series():
            series_id = str(item["id"]).upper().strip()
            print(f"Fetching FRED series {series_id}")
            frame = fetch_fred_observations(
                series_id,
                start_date=args.start_date,
                end_date=args.end_date,
            )
            frames.append(frame)

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        inserted = upsert_raw_macro_observations(combined, target=args.target)
        finish_task(task_id, status="success", target=args.target, row_count=inserted)
        finish_run(run_id, status="success", target=args.target)
        print(f"Upserted {inserted} macro observation rows.")
        return 0
    except Exception as exc:
        log_error(run_id=run_id, task_name="macro", error=exc, target=args.target)
        finish_task(task_id, status="failed", target=args.target, error_message=str(exc))
        finish_run(run_id, status="failed", target=args.target)
        print(f"Macro refresh failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

