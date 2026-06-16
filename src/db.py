"""Database access for local DuckDB and MotherDuck."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from src.config import DATA_DIR, DB_PATH, get_secret


@dataclass(frozen=True)
class StreamlitConnectionState:
    """Friendly result wrapper for Streamlit database reads."""

    connection: duckdb.DuckDBPyConnection | None
    target: str
    available: bool
    message: str


def resolve_db_target(explicit_target: str | None = None) -> str:
    """Resolve the database target from CLI input, environment, or default."""
    target = explicit_target or os.getenv("CAPITALPILOT_DB_TARGET") or "local"
    normalized = target.strip().lower()
    if normalized in {"md", "motherduck", "prod", "production"}:
        return "motherduck"
    if normalized in {"local", "dev", "development"}:
        return "local"
    raise ValueError(f"Unsupported database target: {target!r}. Use local or motherduck.")


def _motherduck_database_url() -> str:
    token = get_secret("MOTHERDUCK_TOKEN")
    if not token:
        raise ValueError("MOTHERDUCK_TOKEN is required when target is motherduck.")
    return f"md:capitalpilot?motherduck_token={token}"


def get_connection(
    target: str | None = None,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection for the selected target."""
    resolved = resolve_db_target(target)
    if resolved == "motherduck":
        return duckdb.connect(_motherduck_database_url(), read_only=read_only)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(DB_PATH)
    if read_only and not path.exists():
        raise FileNotFoundError(f"Local DuckDB database does not exist at {path}.")
    return duckdb.connect(str(path), read_only=read_only)


def init_database_schemas(target: str | None = None) -> None:
    """Create all schemas and contract tables used by the data pipeline."""
    conn = get_connection(target)
    try:
        for schema in ["raw", "staging", "intermediate", "marts", "ai", "ops"]:
            conn.execute(f"create schema if not exists {schema}")

        conn.execute(
            """
            create table if not exists raw.raw_macro_observations (
                series_id varchar,
                date date,
                value double,
                source varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_prices (
                ticker varchar,
                date date,
                open double,
                high double,
                low double,
                close double,
                adj_close double,
                volume double,
                market_cap double,
                source varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_sec_company_tickers (
                ticker varchar,
                cik varchar,
                title varchar,
                source varchar,
                raw_payload_json varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_sec_filings (
                ticker varchar,
                cik varchar,
                accession_number varchar,
                form_type varchar,
                filing_date date,
                report_date date,
                acceptance_datetime timestamp,
                primary_document varchar,
                filing_detail_url varchar,
                document_url varchar,
                document_text varchar,
                source varchar,
                raw_payload_json varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute("alter table raw.raw_sec_filings add column if not exists document_text varchar")
        conn.execute(
            """
            create table if not exists raw.raw_sec_filing_documents (
                ticker varchar,
                cik varchar,
                accession_number varchar,
                form_type varchar,
                filing_date date,
                primary_document varchar,
                document_url varchar,
                document_text varchar,
                content_type varchar,
                download_status varchar,
                error_message varchar,
                source varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_sec_companyfacts (
                ticker varchar,
                cik varchar,
                source varchar,
                raw_payload_json varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_news_articles (
                article_id varchar,
                source_provider varchar,
                publisher varchar,
                title varchar,
                url varchar,
                published_at timestamp,
                category varchar,
                query varchar,
                related_tickers_json varchar,
                raw_summary varchar,
                raw_sentiment varchar,
                raw_payload_json varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_political_disclosure_reports (
                report_id varchar,
                official_name varchar,
                role varchar,
                branch varchar,
                chamber varchar,
                party varchar,
                state varchar,
                report_type varchar,
                report_date date,
                filing_date date,
                source_url varchar,
                source_pdf_url varchar,
                raw_payload_json varchar,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_political_transactions (
                transaction_id varchar,
                official_name varchar,
                role varchar,
                branch varchar,
                chamber varchar,
                party varchar,
                state varchar,
                ticker varchar,
                asset_name varchar,
                asset_type varchar,
                transaction_type varchar,
                transaction_date date,
                notification_date date,
                filing_date date,
                amount_min double,
                amount_max double,
                amount_text varchar,
                owner varchar,
                source_report_id varchar,
                source_url varchar,
                source_pdf_url varchar,
                raw_payload_json varchar,
                confidence_score double,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists raw.raw_options_chain (
                ticker varchar,
                as_of_date date,
                expiration_date date,
                option_type varchar,
                strike double,
                last_price double,
                bid double,
                ask double,
                mid double,
                volume double,
                open_interest double,
                implied_volatility double,
                in_the_money boolean,
                source varchar,
                updated_at timestamp
            )
            """
        )

        conn.execute(
            """
            create table if not exists ai.sec_filing_summaries (
                summary_id varchar,
                ticker varchar,
                cik varchar,
                accession_number varchar,
                form_type varchar,
                filing_date date,
                summary_type varchar,
                summary varchar,
                key_points_json varchar,
                risk_factors_json varchar,
                business_impact varchar,
                market_impact_label varchar,
                market_impact_score double,
                confidence_score double,
                model_name varchar,
                prompt_version varchar,
                source_url varchar,
                created_at timestamp,
                updated_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists ai.news_summaries (
                summary_id varchar,
                summary_date date,
                category varchar,
                ticker varchar,
                headline varchar,
                summary varchar,
                bull_bear_label varchar,
                bull_bear_score double,
                reasoning_short varchar,
                affected_assets_json varchar,
                source_article_ids_json varchar,
                model_name varchar,
                prompt_version varchar,
                created_at timestamp,
                updated_at timestamp
            )
            """
        )

        conn.execute(
            """
            create table if not exists ops.pipeline_runs (
                run_id varchar,
                pipeline_name varchar,
                target varchar,
                status varchar,
                started_at timestamp,
                finished_at timestamp,
                metadata_json varchar
            )
            """
        )
        conn.execute(
            """
            create table if not exists ops.pipeline_task_runs (
                task_run_id varchar,
                run_id varchar,
                task_name varchar,
                status varchar,
                started_at timestamp,
                finished_at timestamp,
                row_count bigint,
                metadata_json varchar,
                error_message varchar
            )
            """
        )
        conn.execute(
            """
            create table if not exists ops.pipeline_errors (
                error_id varchar,
                run_id varchar,
                task_name varchar,
                error_type varchar,
                error_message varchar,
                error_context_json varchar,
                created_at timestamp
            )
            """
        )
        conn.execute(
            """
            create table if not exists ops.data_freshness_checks (
                check_id varchar,
                domain varchar,
                table_name varchar,
                max_timestamp timestamp,
                row_count bigint,
                status varchar,
                checked_at timestamp,
                details_json varchar
            )
            """
        )
    finally:
        conn.close()


def init_raw_schema(target: str | None = None) -> None:
    """Backward-compatible wrapper for Phase 1 callers."""
    init_database_schemas(target)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = None
    out = out[list(columns)]
    if "updated_at" in out.columns:
        out["updated_at"] = out["updated_at"].fillna(_utc_now_naive())
    return out


def _coerce_date(prepared: pd.DataFrame, column: str) -> None:
    if column in prepared.columns:
        prepared[column] = pd.to_datetime(prepared[column], errors="coerce").dt.date


def _coerce_timestamp(prepared: pd.DataFrame, column: str) -> None:
    if column in prepared.columns:
        prepared[column] = pd.to_datetime(prepared[column], errors="coerce", utc=True).dt.tz_convert(None)


def _coerce_numeric(prepared: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")


def _delete_then_insert(
    df: pd.DataFrame,
    *,
    target: str | None,
    table_name: str,
    key_columns: list[str],
    columns: list[str],
) -> int:
    init_database_schemas(target)
    if df.empty:
        return 0

    normalized = _normalize_columns(df, columns)
    conn = get_connection(target)
    try:
        conn.register("incoming_rows", normalized)
        join_predicate = " and ".join(
            f"existing.{column} is not distinct from incoming_rows.{column}" for column in key_columns
        )
        conn.execute(f"delete from {table_name} as existing using incoming_rows where {join_predicate}")
        column_list = ", ".join(columns)
        conn.execute(f"insert into {table_name} ({column_list}) select {column_list} from incoming_rows")
        return len(normalized)
    finally:
        try:
            conn.unregister("incoming_rows")
        except Exception:
            pass
        conn.close()


def upsert_dataframe(
    df: pd.DataFrame,
    *,
    target: str | None,
    table_name: str,
    key_columns: list[str],
    columns: list[str],
) -> int:
    """Idempotently upsert a dataframe into a known table."""
    return _delete_then_insert(
        df,
        target=target,
        table_name=table_name,
        key_columns=key_columns,
        columns=columns,
    )


def upsert_raw_macro_observations(df: pd.DataFrame, target: str | None = None) -> int:
    """Idempotently upsert FRED macro observations into raw.raw_macro_observations."""
    prepared = df.copy()
    if not prepared.empty:
        prepared["series_id"] = prepared["series_id"].astype(str).str.upper().str.strip()
        _coerce_date(prepared, "date")
        _coerce_numeric(prepared, ["value"])
        prepared["source"] = prepared.get("source", "FRED")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_macro_observations",
        key_columns=["series_id", "date"],
        columns=["series_id", "date", "value", "source", "updated_at"],
    )


def upsert_raw_prices(df: pd.DataFrame, target: str | None = None) -> int:
    """Idempotently upsert daily prices into raw.raw_prices."""
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        _coerce_date(prepared, "date")
        _coerce_numeric(prepared, ["open", "high", "low", "close", "adj_close", "volume", "market_cap"])
        prepared["source"] = prepared.get("source", "yfinance")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_prices",
        key_columns=["ticker", "date"],
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
        ],
    )


def upsert_raw_sec_company_tickers(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        prepared["cik"] = prepared["cik"].astype(str).str.zfill(10)
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_sec_company_tickers",
        key_columns=["ticker"],
        columns=["ticker", "cik", "title", "source", "raw_payload_json", "updated_at"],
    )


def upsert_raw_sec_filings(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        prepared["cik"] = prepared["cik"].astype(str).str.zfill(10)
        prepared["form_type"] = prepared["form_type"].astype(str).str.upper().str.strip()
        _coerce_date(prepared, "filing_date")
        _coerce_date(prepared, "report_date")
        _coerce_timestamp(prepared, "acceptance_datetime")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_sec_filings",
        key_columns=["accession_number"],
        columns=[
            "ticker",
            "cik",
            "accession_number",
            "form_type",
            "filing_date",
            "report_date",
            "acceptance_datetime",
            "primary_document",
            "filing_detail_url",
            "document_url",
            "document_text",
            "source",
            "raw_payload_json",
            "updated_at",
        ],
    )


def upsert_raw_sec_filing_documents(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        prepared["cik"] = prepared["cik"].astype(str).str.zfill(10)
        _coerce_date(prepared, "filing_date")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_sec_filing_documents",
        key_columns=["accession_number", "document_url"],
        columns=[
            "ticker",
            "cik",
            "accession_number",
            "form_type",
            "filing_date",
            "primary_document",
            "document_url",
            "document_text",
            "content_type",
            "download_status",
            "error_message",
            "source",
            "updated_at",
        ],
    )


def upsert_raw_sec_companyfacts(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        prepared["cik"] = prepared["cik"].astype(str).str.zfill(10)
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_sec_companyfacts",
        key_columns=["cik"],
        columns=["ticker", "cik", "source", "raw_payload_json", "updated_at"],
    )


def upsert_raw_news_articles(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        _coerce_timestamp(prepared, "published_at")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_news_articles",
        key_columns=["article_id"],
        columns=[
            "article_id",
            "source_provider",
            "publisher",
            "title",
            "url",
            "published_at",
            "category",
            "query",
            "related_tickers_json",
            "raw_summary",
            "raw_sentiment",
            "raw_payload_json",
            "updated_at",
        ],
    )


def upsert_raw_political_disclosure_reports(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        _coerce_date(prepared, "report_date")
        _coerce_date(prepared, "filing_date")
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_political_disclosure_reports",
        key_columns=["report_id"],
        columns=[
            "report_id",
            "official_name",
            "role",
            "branch",
            "chamber",
            "party",
            "state",
            "report_type",
            "report_date",
            "filing_date",
            "source_url",
            "source_pdf_url",
            "raw_payload_json",
            "updated_at",
        ],
    )


def upsert_raw_political_transactions(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        if "ticker" in prepared.columns:
            prepared["ticker"] = prepared["ticker"].map(
                lambda value: None
                if value is None or pd.isna(value) or str(value).strip().upper() in {"", "NAN", "NONE", "NULL"}
                else str(value).upper().strip()
            )
        for column in ["transaction_date", "notification_date", "filing_date"]:
            _coerce_date(prepared, column)
        _coerce_numeric(prepared, ["amount_min", "amount_max", "confidence_score"])
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_political_transactions",
        key_columns=["transaction_id"],
        columns=[
            "transaction_id",
            "official_name",
            "role",
            "branch",
            "chamber",
            "party",
            "state",
            "ticker",
            "asset_name",
            "asset_type",
            "transaction_type",
            "transaction_date",
            "notification_date",
            "filing_date",
            "amount_min",
            "amount_max",
            "amount_text",
            "owner",
            "source_report_id",
            "source_url",
            "source_pdf_url",
            "raw_payload_json",
            "confidence_score",
            "updated_at",
        ],
    )


def upsert_raw_options_chain(df: pd.DataFrame, target: str | None = None) -> int:
    prepared = df.copy()
    if not prepared.empty:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
        prepared["option_type"] = prepared["option_type"].astype(str).str.lower().str.strip()
        _coerce_date(prepared, "as_of_date")
        _coerce_date(prepared, "expiration_date")
        _coerce_numeric(
            prepared,
            [
                "strike",
                "last_price",
                "bid",
                "ask",
                "mid",
                "volume",
                "open_interest",
                "implied_volatility",
            ],
        )
    return _delete_then_insert(
        prepared,
        target=target,
        table_name="raw.raw_options_chain",
        key_columns=["ticker", "as_of_date", "expiration_date", "option_type", "strike"],
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
        ],
    )


def table_exists(table_name: str, target: str | None = None) -> bool:
    """Return whether a fully qualified table exists."""
    conn = get_connection(target)
    try:
        schema, name = table_name.split(".", 1)
        rows = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_schema = ?
              and table_name = ?
            """,
            [schema, name],
        ).fetchone()
        return bool(rows and rows[0])
    finally:
        conn.close()


def get_table_row_count(table_name: str, target: str | None = None) -> int | None:
    """Return a table row count, or None if the table cannot be read."""
    conn = get_connection(target)
    try:
        return int(conn.execute(f"select count(*) from {table_name}").fetchone()[0])
    except Exception:
        return None
    finally:
        conn.close()


try:
    import streamlit as st
except Exception:  # pragma: no cover - used only outside Streamlit/test installs
    st = None


def _cache_resource(func):
    return st.cache_resource(func) if st is not None else func


@_cache_resource
def get_streamlit_connection() -> StreamlitConnectionState:
    """Return a Streamlit-friendly read connection or a friendly empty state."""
    if st is not None:
        try:
            token = st.secrets.get("MOTHERDUCK_TOKEN")
        except Exception:
            token = None
        if token:
            try:
                conn = duckdb.connect(f"md:capitalpilot?motherduck_token={token}", read_only=True)
                return StreamlitConnectionState(conn, "motherduck", True, "Connected to MotherDuck.")
            except Exception as exc:
                return StreamlitConnectionState(None, "motherduck", False, str(exc))

    path = Path(DB_PATH)
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
            return StreamlitConnectionState(conn, "local", True, "Connected to local DuckDB.")
        except Exception as exc:
            return StreamlitConnectionState(None, "local", False, str(exc))

    return StreamlitConnectionState(
        None,
        "local",
        False,
        "No local database found yet. Run the ingestion jobs and dbt build to populate dashboards.",
    )
