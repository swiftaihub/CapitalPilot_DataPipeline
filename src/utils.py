"""Small UI and formatting helpers."""

from __future__ import annotations

from math import isnan
from typing import Any

import pandas as pd


def is_missing(value: Any) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and isnan(value))


def format_number(value: Any, digits: int = 2) -> str:
    if is_missing(value):
        return "N/A"
    return f"{float(value):,.{digits}f}"


def format_percent(value: Any, digits: int = 2, already_percent: bool = False) -> str:
    if is_missing(value):
        return "N/A"
    pct = float(value) if already_percent else float(value) * 100.0
    return f"{pct:,.{digits}f}%"


def format_currency(value: Any, digits: int = 2) -> str:
    if is_missing(value):
        return "N/A"
    return f"${float(value):,.{digits}f}"


def format_compact_currency(value: Any) -> str:
    if is_missing(value):
        return "N/A"
    number = float(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.2f}T"
    if abs_number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if abs_number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    return f"${number:,.0f}"


def safe_dataframe_dates(df: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    """Return a copy with a parsed date column if present."""
    if df.empty or column not in df.columns:
        return df.copy()
    out = df.copy()
    out[column] = pd.to_datetime(out[column], errors="coerce")
    return out.dropna(subset=[column])

