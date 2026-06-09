"""FRED API client for macro observations."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from src.config import get_secret

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_observations(
    series_id: str,
    *,
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Fetch observations for one FRED series."""
    key = api_key or get_secret("FRED_API_KEY")
    if not key:
        raise ValueError("FRED_API_KEY is required to refresh macro data.")

    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "observation_start": start_date,
    }
    if end_date:
        params["observation_end"] = end_date

    response = requests.get(FRED_OBSERVATIONS_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("observations", [])
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    records = []
    for row in rows:
        raw_value = row.get("value")
        if raw_value in {None, "."}:
            continue
        records.append(
            {
                "series_id": series_id,
                "date": row.get("date"),
                "value": raw_value,
                "source": "FRED",
                "updated_at": updated_at,
            }
        )

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return pd.DataFrame(columns=["series_id", "date", "value", "source", "updated_at"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "value"])

