"""Run the CapitalPilot DataPipeline refresh locally or against MotherDuck."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_secret
from src.db import init_database_schemas
from src.pipeline_logging import (
    finish_run,
    finish_task,
    log_error,
    record_standard_freshness_checks,
    start_run,
    start_task,
)
from src.sec_client import validate_user_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CapitalPilot Phase 2 data pipeline.")
    parser.add_argument("--target", choices=["local", "motherduck"], default="local")
    parser.add_argument("--skip-sec", action="store_true")
    parser.add_argument("--skip-news", action="store_true")
    parser.add_argument("--skip-political", action="store_true")
    parser.add_argument("--skip-options", action="store_true")
    parser.add_argument("--news-provider", choices=["manual", "alpha_vantage"], default=None)
    parser.add_argument("--news-days-back", type=int, default=7)
    parser.add_argument("--political-source", choices=["manual", "house", "senate", "oge", "all"], default="manual")
    parser.add_argument("--political-max-reports", type=int, default=50)
    parser.add_argument("--run-dbt", action="store_true")
    return parser.parse_args()


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    print(f"Running: {' '.join(command)}")
    try:
        return subprocess.run(command, cwd=cwd or ROOT_DIR, check=False)
    except FileNotFoundError as exc:
        executable = command[0]
        raise RuntimeError(
            f"Could not find executable '{executable}'. Install dependencies in the active "
            "environment with `python -m pip install -r requirements.txt`."
        ) from exc


def _dbt_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "dbt.cli.main", *args]


def _run_logged_command(
    *,
    run_id: str,
    task_name: str,
    command: list[str],
    target: str,
    allow_failure: bool = False,
    cwd: Path | None = None,
) -> bool:
    task_id = start_task(run_id, task_name, target=target, metadata={"command": command})
    try:
        result = _run(command, cwd=cwd)
        if result.returncode == 0:
            finish_task(task_id, status="success", target=target, row_count=0)
            return True
        message = f"Command failed with exit code {result.returncode}: {' '.join(command)}"
        log_error(run_id=run_id, task_name=task_name, error=message, target=target)
        finish_task(task_id, status="failed", target=target, error_message=message)
        return bool(allow_failure)
    except Exception as exc:
        log_error(run_id=run_id, task_name=task_name, error=exc, target=target)
        finish_task(task_id, status="failed", target=target, error_message=str(exc))
        return bool(allow_failure)


def _skip_task(run_id: str, task_name: str, *, target: str, reason: str) -> None:
    task_id = start_task(run_id, task_name, target=target)
    print(f"Skipping {task_name}: {reason}")
    finish_task(task_id, status="skipped", target=target, row_count=0, error_message=reason)


def _ensure_dbt_profiles() -> None:
    dbt_dir = ROOT_DIR / "dbt"
    profiles = dbt_dir / "profiles.yml"
    if not profiles.exists():
        shutil.copyfile(dbt_dir / "profiles.yml.example", profiles)


def _valid_sec_user_agent() -> tuple[bool, str]:
    value = get_secret("SEC_USER_AGENT")
    try:
        validate_user_agent(value)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    args = parse_args()
    init_database_schemas(args.target)
    run_id = start_run("run_pipeline", target=args.target, metadata=vars(args))
    ok = True

    if get_secret("FRED_API_KEY"):
        ok = _run_logged_command(
            run_id=run_id,
            task_name="macro",
            command=[sys.executable, "jobs/refresh_macro.py", "--target", args.target],
            target=args.target,
            allow_failure=False,
        ) and ok
    else:
        _skip_task(run_id, "macro", target=args.target, reason="FRED_API_KEY is not set.")

    ok = _run_logged_command(
        run_id=run_id,
        task_name="prices",
        command=[sys.executable, "jobs/refresh_prices.py", "--target", args.target],
        target=args.target,
        allow_failure=False,
    ) and ok

    if args.skip_sec:
        _skip_task(run_id, "sec", target=args.target, reason="--skip-sec was supplied.")
    else:
        sec_ok, sec_reason = _valid_sec_user_agent()
        if not sec_ok:
            _skip_task(run_id, "sec", target=args.target, reason=sec_reason)
        else:
            _run_logged_command(
                run_id=run_id,
                task_name="sec",
                command=[sys.executable, "jobs/refresh_sec_filings.py", "--target", args.target],
                target=args.target,
                allow_failure=True,
            )

    if args.skip_news:
        _skip_task(run_id, "news", target=args.target, reason="--skip-news was supplied.")
    else:
        _run_logged_command(
            run_id=run_id,
            task_name="news",
            command=[
                sys.executable,
                "jobs/refresh_news.py",
                "--target",
                args.target,
                "--days-back",
                str(args.news_days_back),
                *(
                    ["--provider", args.news_provider]
                    if args.news_provider
                    else []
                ),
            ],
            target=args.target,
            allow_failure=True,
        )

    if args.skip_political:
        _skip_task(run_id, "political", target=args.target, reason="--skip-political was supplied.")
    else:
        _run_logged_command(
            run_id=run_id,
            task_name="political",
            command=[
                sys.executable,
                "jobs/refresh_political_trades.py",
                "--target",
                args.target,
                "--source",
                args.political_source,
                "--max-reports",
                str(args.political_max_reports),
            ],
            target=args.target,
            allow_failure=True,
        )

    if args.skip_options:
        _skip_task(run_id, "options", target=args.target, reason="--skip-options was supplied.")
    else:
        _run_logged_command(
            run_id=run_id,
            task_name="options",
            command=[sys.executable, "jobs/refresh_options.py", "--target", args.target],
            target=args.target,
            allow_failure=True,
        )

    if args.run_dbt:
        if sys.version_info >= (3, 14):
            message = (
                "dbt is not compatible with this Python 3.14 environment. "
                "CapitalPilot declares Python 3.11 in runtime.txt."
            )
            log_error(run_id=run_id, task_name="dbt", error=message, target=args.target)
            finish_run(run_id, status="failed", target=args.target)
            raise SystemExit(message)
        _ensure_dbt_profiles()
        dbt_target = "prod" if args.target == "motherduck" else "dev"
        ok = _run_logged_command(
            run_id=run_id,
            task_name="dbt_build",
            command=_dbt_command("build", "--profiles-dir", ".", "--target", dbt_target),
            cwd=ROOT_DIR / "dbt",
            target=args.target,
            allow_failure=False,
        ) and ok
    else:
        _skip_task(run_id, "dbt_build", target=args.target, reason="--run-dbt was not supplied.")

    try:
        checks = record_standard_freshness_checks(target=args.target)
        task_id = start_task(run_id, "freshness_checks", target=args.target)
        finish_task(task_id, status="success", target=args.target, row_count=len(checks))
    except Exception as exc:
        ok = False
        log_error(run_id=run_id, task_name="freshness_checks", error=exc, target=args.target)

    finish_run(run_id, status="success" if ok else "failed", target=args.target)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
