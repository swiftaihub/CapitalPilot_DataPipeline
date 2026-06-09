"""Run the Phase 1 refresh pipeline locally or against MotherDuck."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CapitalPilot Phase 1 pipeline.")
    parser.add_argument("--target", choices=["local", "motherduck"], default="local")
    parser.add_argument("--run-dbt", action="store_true")
    return parser.parse_args()


def _run(command: list[str], cwd: Path | None = None) -> None:
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, cwd=cwd or ROOT_DIR, check=True)
    except FileNotFoundError as exc:
        executable = command[0]
        raise SystemExit(
            f"Could not find executable '{executable}'. Install dependencies in the active "
            "environment with `python -m pip install -r requirements.txt`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {' '.join(command)}") from exc


def _dbt_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "dbt.cli.main", *args]


def main() -> int:
    args = parse_args()
    _run([sys.executable, "jobs/refresh_macro.py", "--target", args.target])
    _run([sys.executable, "jobs/refresh_prices.py", "--target", args.target])

    if args.run_dbt:
        dbt_dir = ROOT_DIR / "dbt"
        profiles = dbt_dir / "profiles.yml"
        if not profiles.exists():
            shutil.copyfile(dbt_dir / "profiles.yml.example", profiles)
        dbt_target = "prod" if args.target == "motherduck" else "dev"
        if sys.version_info >= (3, 14):
            raise SystemExit(
                "dbt is not compatible with this Python 3.14 environment. "
                "CapitalPilot declares Python 3.11 in runtime.txt. Recreate the virtual "
                "environment with Python 3.11, then reinstall requirements and rerun the pipeline."
            )
        _run(_dbt_command("build", "--profiles-dir", ".", "--target", dbt_target), cwd=dbt_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
