"""Streamlit-independent macro research helpers."""

from __future__ import annotations

import pandas as pd


def latest_macro_snapshot(df: pd.DataFrame) -> dict[str, object]:
    """Return a compact latest macro dashboard snapshot from a mart dataframe."""
    if df.empty:
        return {
            "status": "empty",
            "macro_regime_label": "Insufficient data",
            "macro_regime_explanation": "No macro mart data is available yet.",
        }
    latest = df.sort_values("date").iloc[-1].to_dict()
    return {
        "status": "ok",
        "date": latest.get("date"),
        "macro_regime_score": latest.get("macro_regime_score"),
        "macro_regime_label": latest.get("macro_regime_label"),
        "macro_regime_explanation": latest.get("macro_regime_explanation"),
    }

