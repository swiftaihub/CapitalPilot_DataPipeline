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


def init_raw_schema(target: str | None = None) -> None:
    """Create Phase 1 raw schemas and raw tables if they do not exist."""
    conn = get_connection(target)
    try:
        conn.execute("create schema if not exists raw")
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
    finally:
        conn.close()


def _normalize_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = None
    out = out[list(columns)]
    if "updated_at" in out.columns:
        out["updated_at"] = out["updated_at"].fillna(datetime.now(timezone.utc).replace(tzinfo=None))
    return out


def _delete_then_insert(
    df: pd.DataFrame,
    *,
    target: str | None,
    table_name: str,
    key_columns: list[str],
    columns: list[str],
) -> int:
    if df.empty:
        init_raw_schema(target)
        return 0

    init_raw_schema(target)
    normalized = _normalize_columns(df, columns)
    conn = get_connection(target)
    try:
        conn.register("incoming_rows", normalized)
        join_predicate = " and ".join(
            f"existing.{column} = incoming_rows.{column}" for column in key_columns
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


def upsert_raw_macro_observations(df: pd.DataFrame, target: str | None = None) -> int:
    """Idempotently upsert FRED macro observations into raw.raw_macro_observations."""
    prepared = df.copy()
    if not prepared.empty:
        prepared["series_id"] = prepared["series_id"].astype(str).str.upper().str.strip()
        prepared["date"] = pd.to_datetime(prepared["date"]).dt.date
        prepared["value"] = pd.to_numeric(prepared["value"], errors="coerce")
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
        prepared["date"] = pd.to_datetime(prepared["date"]).dt.date
        for column in ["open", "high", "low", "close", "adj_close", "volume", "market_cap"]:
            if column in prepared.columns:
                prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
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
