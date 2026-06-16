"""CapitalPilot DataPipeline internal observability dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db import get_streamlit_connection, resolve_db_target

st.set_page_config(page_title="CapitalPilot DataPipeline", page_icon="CP", layout="wide")

DOMAINS = {
    "macro": ["raw.raw_macro_observations", "marts.mart_macro_dashboard"],
    "prices": ["raw.raw_prices", "marts.mart_valuation_dashboard"],
    "sec": ["raw.raw_sec_filings", "raw.raw_sec_filing_documents", "marts.mart_sec_ai_summary_queue"],
    "news": ["raw.raw_news_articles", "marts.mart_news_ai_summary_queue"],
    "political": ["raw.raw_political_transactions", "marts.mart_political_trading_dashboard"],
    "options": ["raw.raw_options_chain", "marts.mart_options_dashboard"],
    "technicals": ["marts.mart_technical_dashboard", "marts.mart_daily_market_summary"],
    "ai": ["ai.sec_filing_summaries", "ai.news_summaries"],
}


def _safe_query(conn, sql: str, params: list[object] | None = None) -> pd.DataFrame:
    try:
        return conn.execute(sql, params or []).df()
    except Exception:
        return pd.DataFrame()


def _table_count(conn, table_name: str) -> int | None:
    try:
        return int(conn.execute(f"select count(*) from {table_name}").fetchone()[0])
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_dashboard_data() -> dict[str, object]:
    db_state = get_streamlit_connection()
    data: dict[str, object] = {
        "target": db_state.target,
        "available": db_state.available,
        "message": db_state.message,
        "latest_run": pd.DataFrame(),
        "task_runs": pd.DataFrame(),
        "errors": pd.DataFrame(),
        "freshness": pd.DataFrame(),
        "row_counts": pd.DataFrame(),
        "sec_queue": pd.DataFrame(),
        "news_queue": pd.DataFrame(),
        "previews": {},
    }
    if not db_state.available or db_state.connection is None:
        return data

    conn = db_state.connection
    data["latest_run"] = _safe_query(
        conn,
        """
        select *
        from ops.pipeline_runs
        order by started_at desc
        limit 1
        """,
    )
    data["task_runs"] = _safe_query(
        conn,
        """
        select task_name, status, started_at, finished_at, row_count, error_message
        from ops.pipeline_task_runs
        order by started_at desc
        limit 25
        """,
    )
    data["errors"] = _safe_query(
        conn,
        """
        select created_at, task_name, error_type, error_message
        from ops.pipeline_errors
        order by created_at desc
        limit 50
        """,
    )
    data["freshness"] = _safe_query(
        conn,
        """
        with ranked as (
            select
                *,
                row_number() over (
                    partition by domain, table_name
                    order by checked_at desc
                ) as rn
            from ops.data_freshness_checks
        )
        select domain, table_name, row_count, max_timestamp, status, checked_at
        from ranked
        where rn = 1
        order by domain, table_name
        """,
    )

    row_count_records = []
    for domain, tables in DOMAINS.items():
        for table_name in tables:
            count = _table_count(conn, table_name)
            row_count_records.append({"domain": domain, "table_name": table_name, "row_count": count})
    data["row_counts"] = pd.DataFrame(row_count_records)

    data["sec_queue"] = _safe_query(
        conn,
        """
        select summary_status, count(*) as filings
        from marts.mart_sec_ai_summary_queue
        group by 1
        order by 1
        """,
    )
    data["news_queue"] = _safe_query(
        conn,
        """
        select summary_status, count(*) as articles
        from marts.mart_news_ai_summary_queue
        group by 1
        order by 1
        """,
    )

    preview_tables = {
        "Macro": "marts.mart_macro_dashboard",
        "Prices": "raw.raw_prices",
        "SEC Filings": "marts.mart_sec_filings_dashboard",
        "News": "marts.mart_daily_news_dashboard",
        "Political": "marts.mart_political_trading_dashboard",
        "Options": "marts.mart_options_dashboard",
        "Technicals": "marts.mart_technical_dashboard",
        "Accumulation": "marts.mart_accumulation_dashboard",
    }
    previews: dict[str, pd.DataFrame] = {}
    for label, table_name in preview_tables.items():
        previews[label] = _safe_query(conn, f"select * from {table_name} limit 25")
    data["previews"] = previews
    return data


st.title("CapitalPilot DataPipeline")
st.caption("Internal pipeline observability and data-contract testing. Personal research only; no trading automation.")

data = load_dashboard_data()

if not data["available"]:
    st.info(data["message"])

latest_run = data["latest_run"]
latest_status = "not run"
latest_started = None
latest_finished = None
if isinstance(latest_run, pd.DataFrame) and not latest_run.empty:
    row = latest_run.iloc[0]
    latest_status = row.get("status", "unknown")
    latest_started = row.get("started_at")
    latest_finished = row.get("finished_at")

row_counts = data["row_counts"] if isinstance(data["row_counts"], pd.DataFrame) else pd.DataFrame()
total_rows = int(row_counts["row_count"].dropna().sum()) if not row_counts.empty else 0
error_count = len(data["errors"]) if isinstance(data["errors"], pd.DataFrame) else 0

cols = st.columns(4)
cols[0].metric("Database Target", data["target"] if data["available"] else resolve_db_target(None))
cols[1].metric("Latest Pipeline Run", latest_status)
cols[2].metric("Tracked Rows", f"{total_rows:,}")
cols[3].metric("Recent Errors", error_count)

if latest_started is not None:
    st.caption(f"Latest run started: {latest_started} | finished: {latest_finished}")

tab_runs, tab_freshness, tab_counts, tab_queues, tab_previews, tab_errors = st.tabs(
    ["Runs", "Freshness", "Row Counts", "AI Queues", "Previews", "Errors"]
)

with tab_runs:
    st.subheader("Recent Task Runs")
    task_runs = data["task_runs"]
    if isinstance(task_runs, pd.DataFrame) and not task_runs.empty:
        st.dataframe(task_runs, use_container_width=True, hide_index=True)
    else:
        st.info("No pipeline task runs have been recorded yet.")
    st.caption("GitHub Actions and local runs both write to ops.pipeline_runs and ops.pipeline_task_runs.")

with tab_freshness:
    st.subheader("Latest Freshness Checks")
    freshness = data["freshness"]
    if isinstance(freshness, pd.DataFrame) and not freshness.empty:
        st.dataframe(freshness, use_container_width=True, hide_index=True)
    else:
        st.info("No freshness checks have been recorded yet.")

with tab_counts:
    st.subheader("Raw, Mart, AI, and Ops Row Counts")
    if not row_counts.empty:
        st.dataframe(row_counts, use_container_width=True, hide_index=True)
        chart_df = row_counts.dropna(subset=["row_count"])
        if not chart_df.empty:
            st.bar_chart(chart_df, x="table_name", y="row_count")
    else:
        st.info("No row-count data is available yet.")

with tab_queues:
    left, right = st.columns(2)
    with left:
        st.subheader("SEC AI Summary Queue")
        sec_queue = data["sec_queue"]
        if isinstance(sec_queue, pd.DataFrame) and not sec_queue.empty:
            st.dataframe(sec_queue, use_container_width=True, hide_index=True)
        else:
            st.info("SEC summary queue is empty or not built yet.")
    with right:
        st.subheader("News AI Summary Queue")
        news_queue = data["news_queue"]
        if isinstance(news_queue, pd.DataFrame) and not news_queue.empty:
            st.dataframe(news_queue, use_container_width=True, hide_index=True)
        else:
            st.info("News summary queue is empty or not built yet.")

with tab_previews:
    previews = data["previews"] if isinstance(data["previews"], dict) else {}
    labels = list(previews.keys())
    selected = st.selectbox("Domain preview", labels) if labels else None
    if selected:
        preview = previews.get(selected, pd.DataFrame())
        if not preview.empty:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        else:
            st.info(f"No preview rows available for {selected}.")

with tab_errors:
    st.subheader("Recent Pipeline Errors")
    errors = data["errors"]
    if isinstance(errors, pd.DataFrame) and not errors.empty:
        st.dataframe(errors, use_container_width=True, hide_index=True)
    else:
        st.success("No recent pipeline errors recorded.")

st.warning(
    "This dashboard is for internal pipeline observability. AI interaction belongs in CapitalPilot_AI; "
    "end-user presentation belongs in CapitalPilot_UI."
)
