from datetime import datetime

import pandas as pd

from src import db


def test_resolve_db_target_precedence(monkeypatch):
    monkeypatch.setenv("CAPITALPILOT_DB_TARGET", "motherduck")

    assert db.resolve_db_target("local") == "local"
    assert db.resolve_db_target(None) == "motherduck"


def test_local_duckdb_raw_upsert_behavior(tmp_path, monkeypatch):
    test_db_path = tmp_path / "capitalpilot_test.duckdb"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    monkeypatch.setenv("CAPITALPILOT_DB_TARGET", "local")

    first_macro = pd.DataFrame(
        [
            {
                "series_id": "FEDFUNDS",
                "date": "2026-01-01",
                "value": 5.0,
                "source": "test",
                "updated_at": datetime(2026, 1, 2),
            }
        ]
    )
    second_macro = first_macro.copy()
    second_macro["value"] = 4.75

    assert db.upsert_raw_macro_observations(first_macro, target="local") == 1
    assert db.upsert_raw_macro_observations(second_macro, target="local") == 1

    conn = db.get_connection("local")
    try:
        rows = conn.execute("select count(*) as n, max(value) as value from raw.raw_macro_observations").fetchone()
    finally:
        conn.close()

    assert rows == (1, 4.75)

    first_price = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "date": "2026-01-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "adj_close": 104.0,
                "volume": 1000,
                "market_cap": 1_000_000,
                "source": "test",
                "updated_at": datetime(2026, 1, 2),
            }
        ]
    )
    second_price = first_price.copy()
    second_price["close"] = 110.0

    assert db.upsert_raw_prices(first_price, target="local") == 1
    assert db.upsert_raw_prices(second_price, target="local") == 1

    conn = db.get_connection("local")
    try:
        rows = conn.execute("select count(*) as n, max(close) as close from raw.raw_prices").fetchone()
    finally:
        conn.close()

    assert rows == (1, 110.0)

