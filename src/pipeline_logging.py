"""Pipeline observability helpers for ingestion jobs and orchestration."""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from src.db import get_connection, init_database_schemas


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, default=str, sort_keys=True)


def start_run(
    pipeline_name: str,
    *,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create an ops.pipeline_runs row and return the run id."""
    init_database_schemas(target)
    run_id = str(uuid.uuid4())
    conn = get_connection(target)
    try:
        conn.execute(
            """
            insert into ops.pipeline_runs (
                run_id, pipeline_name, target, status, started_at, finished_at, metadata_json
            )
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            [run_id, pipeline_name, target or "local", "running", _now(), None, _json(metadata)],
        )
    finally:
        conn.close()
    return run_id


def finish_run(
    run_id: str,
    *,
    status: str,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Mark a pipeline run complete, failed, or skipped."""
    init_database_schemas(target)
    conn = get_connection(target)
    try:
        if metadata is None:
            conn.execute(
                """
                update ops.pipeline_runs
                set status = ?, finished_at = ?
                where run_id = ?
                """,
                [status, _now(), run_id],
            )
        else:
            conn.execute(
                """
                update ops.pipeline_runs
                set status = ?, finished_at = ?, metadata_json = ?
                where run_id = ?
                """,
                [status, _now(), _json(metadata), run_id],
            )
    finally:
        conn.close()


def start_task(
    run_id: str,
    task_name: str,
    *,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create an ops.pipeline_task_runs row and return the task run id."""
    init_database_schemas(target)
    task_run_id = str(uuid.uuid4())
    conn = get_connection(target)
    try:
        conn.execute(
            """
            insert into ops.pipeline_task_runs (
                task_run_id, run_id, task_name, status, started_at, finished_at,
                row_count, metadata_json, error_message
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [task_run_id, run_id, task_name, "running", _now(), None, None, _json(metadata), None],
        )
    finally:
        conn.close()
    return task_run_id


def finish_task(
    task_run_id: str,
    *,
    status: str,
    target: str | None = None,
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Finish an ops.pipeline_task_runs row."""
    init_database_schemas(target)
    conn = get_connection(target)
    try:
        conn.execute(
            """
            update ops.pipeline_task_runs
            set status = ?,
                finished_at = ?,
                row_count = ?,
                metadata_json = coalesce(?, metadata_json),
                error_message = ?
            where task_run_id = ?
            """,
            [status, _now(), row_count, _json(metadata), error_message, task_run_id],
        )
    finally:
        conn.close()


def log_error(
    *,
    run_id: str | None,
    task_name: str,
    error: BaseException | str,
    target: str | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Insert an ops.pipeline_errors row."""
    init_database_schemas(target)
    error_id = str(uuid.uuid4())
    if isinstance(error, BaseException):
        error_type = type(error).__name__
        error_message = str(error)
        context_payload = dict(context or {})
        context_payload.setdefault("traceback", traceback.format_exc())
    else:
        error_type = "Message"
        error_message = error
        context_payload = context

    conn = get_connection(target)
    try:
        conn.execute(
            """
            insert into ops.pipeline_errors (
                error_id, run_id, task_name, error_type, error_message,
                error_context_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            [error_id, run_id, task_name, error_type, error_message, _json(context_payload), _now()],
        )
    finally:
        conn.close()
    return error_id


def record_freshness_check(
    *,
    domain: str,
    table_name: str,
    target: str | None = None,
    timestamp_column: str = "updated_at",
    stale_after_hours: int | None = None,
) -> dict[str, Any]:
    """Record a row-count and max-timestamp freshness check for one table."""
    init_database_schemas(target)
    check_id = str(uuid.uuid4())
    checked_at = _now()
    conn = get_connection(target)
    try:
        try:
            row = conn.execute(
                f"""
                select
                    count(*)::bigint as row_count,
                    max(cast({timestamp_column} as timestamp)) as max_timestamp
                from {table_name}
                """
            ).fetchone()
            row_count = int(row[0] or 0)
            max_timestamp = row[1]
            if row_count == 0:
                status = "empty"
            elif stale_after_hours is not None and max_timestamp is not None:
                age_hours = (checked_at - max_timestamp).total_seconds() / 3600
                status = "stale" if age_hours > stale_after_hours else "fresh"
            else:
                status = "ok"
            details: dict[str, Any] = {}
        except Exception as exc:
            row_count = 0
            max_timestamp = None
            status = "error"
            details = {"error": str(exc)}

        conn.execute(
            """
            insert into ops.data_freshness_checks (
                check_id, domain, table_name, max_timestamp, row_count,
                status, checked_at, details_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [check_id, domain, table_name, max_timestamp, row_count, status, checked_at, _json(details)],
        )
        return {
            "check_id": check_id,
            "domain": domain,
            "table_name": table_name,
            "row_count": row_count,
            "max_timestamp": max_timestamp,
            "status": status,
        }
    finally:
        conn.close()


def record_standard_freshness_checks(target: str | None = None) -> list[dict[str, Any]]:
    """Record freshness checks for the core raw and mart domains."""
    checks = [
        ("macro", "raw.raw_macro_observations", "updated_at", 72),
        ("prices", "raw.raw_prices", "updated_at", 72),
        ("sec", "raw.raw_sec_filings", "updated_at", 168),
        ("news", "raw.raw_news_articles", "updated_at", 48),
        ("political", "raw.raw_political_transactions", "updated_at", 720),
        ("options", "raw.raw_options_chain", "updated_at", 48),
        ("ai_sec", "ai.sec_filing_summaries", "updated_at", 168),
        ("ai_news", "ai.news_summaries", "updated_at", 48),
    ]
    return [
        record_freshness_check(
            domain=domain,
            table_name=table,
            target=target,
            timestamp_column=timestamp_column,
            stale_after_hours=stale_after_hours,
        )
        for domain, table, timestamp_column, stale_after_hours in checks
    ]
