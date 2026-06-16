"""SEC filing pipeline observability page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db import get_streamlit_connection

st.set_page_config(page_title="SEC Filing Pipeline", page_icon="SEC", layout="wide")


@st.cache_data(ttl=300)
def load_sec_pipeline_data() -> tuple[dict[str, pd.DataFrame], str | None]:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return {}, db_state.message
    conn = db_state.connection

    def query(sql: str) -> pd.DataFrame:
        try:
            return conn.execute(sql).df()
        except Exception:
            return pd.DataFrame()

    return {
        "dashboard": query("select * from marts.mart_sec_filings_dashboard order by latest_filing_date desc nulls last"),
        "alerts": query("select * from marts.mart_watchlist_8k_alerts order by filing_date desc nulls last limit 100"),
        "queue": query(
            """
            select summary_status, count(*) as filings
            from marts.mart_sec_ai_summary_queue
            group by 1
            order by 1
            """
        ),
        "queue_rows": query(
            """
            select ticker, form_type, filing_date, accession_number, summary_status, document_url
            from marts.mart_sec_ai_summary_queue
            order by filing_date desc nulls last
            limit 100
            """
        ),
    }, None


st.title("SEC Filing Pipeline")
st.caption("Internal EDGAR ingestion, dbt mart, and AI-summary queue checks. Interactive AI belongs in CapitalPilot_AI.")

data, error = load_sec_pipeline_data()
if error:
    st.info(error)
    st.stop()

dashboard = data.get("dashboard", pd.DataFrame())
alerts = data.get("alerts", pd.DataFrame())
queue = data.get("queue", pd.DataFrame())

cols = st.columns(4)
cols[0].metric("Tickers With Filings", 0 if dashboard.empty else len(dashboard))
cols[1].metric("Recent 8-K Alerts", 0 if alerts.empty else len(alerts))
cols[2].metric("Queue Rows", 0 if data.get("queue_rows", pd.DataFrame()).empty else len(data["queue_rows"]))
pending = int(queue.loc[queue["summary_status"].isin(["pending", "pending_document"]), "filings"].sum()) if not queue.empty else 0
cols[3].metric("Pending AI Summaries", pending)

tab_dashboard, tab_alerts, tab_queue = st.tabs(["Filing Dashboard", "8-K Alerts", "AI Queue"])
with tab_dashboard:
    if dashboard.empty:
        st.info("No SEC filing dashboard rows yet. Run `jobs/refresh_sec_filings.py` with SEC_USER_AGENT, then dbt build.")
    else:
        st.dataframe(dashboard, use_container_width=True, hide_index=True)

with tab_alerts:
    if alerts.empty:
        st.info("No recent 8-K alerts.")
    else:
        st.dataframe(alerts, use_container_width=True, hide_index=True)

with tab_queue:
    if queue.empty:
        st.info("SEC AI summary queue is empty or not built yet.")
    else:
        st.dataframe(queue, use_container_width=True, hide_index=True)
        st.dataframe(data["queue_rows"], use_container_width=True, hide_index=True)

st.warning("Summaries are written by CapitalPilot_AI into ai.sec_filing_summaries; this repo only owns the queue and table contract.")
