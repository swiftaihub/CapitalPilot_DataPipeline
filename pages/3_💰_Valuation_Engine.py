"""Valuation Engine dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import line_chart
from src.db import get_streamlit_connection
from src.utils import format_compact_currency, format_currency, format_number, safe_dataframe_dates
from src.valuation import PLANNED_VALUATION_METRICS, get_phase1_valuation_notice

st.set_page_config(page_title="Valuation Engine", page_icon="💰", layout="wide")


@st.cache_data(ttl=900)
def load_valuation_dashboard() -> tuple[pd.DataFrame, str | None]:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return pd.DataFrame(), db_state.message
    try:
        df = db_state.connection.execute(
            """
            select *
            from marts.mart_valuation_dashboard
            order by date desc
            """
        ).df()
        return safe_dataframe_dates(df), None
    except Exception as exc:
        return pd.DataFrame(), f"Valuation mart is not available yet: {exc}"


@st.cache_data(ttl=900)
def load_price_history(ticker: str) -> pd.DataFrame:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return pd.DataFrame()
    try:
        df = db_state.connection.execute(
            """
            select ticker, date, close, adj_close, volume
            from raw.raw_prices
            where ticker = ?
            order by date
            """,
            [ticker],
        ).df()
        return safe_dataframe_dates(df)
    except Exception:
        return pd.DataFrame()


st.title("Valuation Engine")
st.caption("Phase 1 price-only research context. Not investment advice.")

df, error = load_valuation_dashboard()
if df.empty:
    st.info(error or "No valuation data is available yet.")
    st.info(get_phase1_valuation_notice())
    st.stop()

tickers = sorted(df["ticker"].dropna().unique().tolist())
selected_ticker = st.selectbox("Ticker selector", tickers)
selected = df[df["ticker"] == selected_ticker].sort_values("date").iloc[-1]

cols = st.columns(3)
cols[0].metric("Latest Price", format_currency(selected.get("price")))
cols[1].metric("Market Cap", format_compact_currency(selected.get("market_cap")))
cols[2].metric("Volume", format_number(selected.get("volume"), digits=0))

st.warning(get_phase1_valuation_notice())
st.write("Valuation signal is presented as research context only, not investment advice.")

history = load_price_history(selected_ticker)
if not history.empty:
    st.plotly_chart(
        line_chart(history, x="date", y="close", title=f"{selected_ticker} Price History", y_axis_title="Price"),
        use_container_width=True,
    )
else:
    st.info("Price history is not available yet for the selected ticker.")

st.subheader("Watchlist")
display_columns = [
    "ticker",
    "date",
    "price",
    "market_cap",
    "volume",
    "valuation_signal",
    "is_investment_advice",
]
st.dataframe(df[display_columns].sort_values("ticker"), use_container_width=True)

st.subheader("Planned Fundamental Metrics")
metric_cols = st.columns(5)
for idx, metric in enumerate(PLANNED_VALUATION_METRICS):
    metric_cols[idx % 5].metric(metric, "Phase 2")

with st.expander("Mart Details"):
    st.dataframe(df.sort_values("ticker"), use_container_width=True)
