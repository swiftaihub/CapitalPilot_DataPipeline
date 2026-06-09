"""CapitalPilot Streamlit command center."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import load_watchlist
from src.db import get_streamlit_connection, resolve_db_target
from src.utils import format_compact_currency

st.set_page_config(page_title="CapitalPilot", page_icon="📈", layout="wide")


@st.cache_data(ttl=900)
def load_command_center_data() -> dict[str, object]:
    db_state = get_streamlit_connection()
    data: dict[str, object] = {
        "db_target": db_state.target,
        "db_available": db_state.available,
        "db_message": db_state.message,
        "macro": {},
        "ticker_count": 0,
        "market_cap_total": None,
        "errors": [],
    }
    if not db_state.available or db_state.connection is None:
        return data

    try:
        macro_df = db_state.connection.execute(
            """
            select date, macro_regime_label, macro_regime_explanation, macro_regime_score
            from marts.mart_macro_dashboard
            order by date desc
            limit 1
            """
        ).df()
        if not macro_df.empty:
            data["macro"] = macro_df.iloc[0].to_dict()
    except Exception as exc:
        data["errors"].append(f"Macro mart unavailable: {exc}")

    try:
        valuation_df = db_state.connection.execute(
            """
            select count(distinct ticker) as ticker_count, sum(market_cap) as market_cap_total
            from marts.mart_valuation_dashboard
            """
        ).df()
        if not valuation_df.empty:
            row = valuation_df.iloc[0]
            data["ticker_count"] = int(row["ticker_count"] or 0)
            data["market_cap_total"] = row["market_cap_total"]
    except Exception as exc:
        data["errors"].append(f"Valuation mart unavailable: {exc}")

    return data


st.title("CapitalPilot")
st.caption("For personal research only. Not financial advice. No automated trading.")

watchlist = load_watchlist()
tickers = [item.get("ticker", "") for item in watchlist if isinstance(item, dict)]
data = load_command_center_data()

header_cols = st.columns(4)
header_cols[0].metric(
    "Database Target",
    data["db_target"] if data["db_available"] else resolve_db_target(None),
)
header_cols[1].metric("Watchlist Tickers", len(tickers))
header_cols[2].metric("Tickers With Price Data", data["ticker_count"])
header_cols[3].metric("SEC Filing Agent", "Phase 2 placeholder")

if not data["db_available"]:
    st.info(data["db_message"])

errors = data.get("errors", [])
if errors:
    with st.expander("Data Read Status", expanded=False):
        for error in errors:
            st.write(error)

macro = data.get("macro", {})
left, right = st.columns([1.2, 0.8])
with left:
    st.subheader("Latest Macro Regime")
    if macro:
        st.metric("Regime", macro.get("macro_regime_label", "Insufficient data"))
        st.write(macro.get("macro_regime_explanation", "No explanation available."))
    else:
        st.info("Macro dashboard data is not available yet.")

with right:
    st.subheader("Watchlist")
    if tickers:
        st.write(", ".join(tickers))
    else:
        st.info("Add tickers to config/watchlist.yaml.")
    st.metric("Approx. Covered Market Cap", format_compact_currency(data.get("market_cap_total")))

st.divider()

st.subheader("Dashboards")
dash_cols = st.columns(3)
with dash_cols[0]:
    st.markdown("**Macro Monitor**")
    st.write("Rates, inflation, labor, dollar strength, volatility, and deterministic regime context.")
with dash_cols[1]:
    st.markdown("**SEC Filing Agent**")
    st.write("Phase 2 placeholder for EDGAR ingestion, filing analysis, and MCP-powered AI research.")
with dash_cols[2]:
    st.markdown("**Valuation Engine**")
    st.write("Phase 1 price and market-cap monitor with fundamental metrics planned for Phase 2.")

st.warning(
    "CapitalPilot frames outputs as research signals, context, and risk flags. "
    "It does not produce deterministic buy/sell recommendations."
)
