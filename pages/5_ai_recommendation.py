"""AI recommendation and refresh observability page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db import get_streamlit_connection

st.set_page_config(page_title="AI Recommendations", page_icon="AI", layout="wide")

AI_TABLES = {
    "SEC filing summaries": "ai.sec_filing_summaries",
    "News summaries": "ai.news_summaries",
    "Political trade signals": "ai.political_trade_signals",
    "Accumulation recommendations": "ai.accumulation_recommendations",
    "Options strategy signals": "ai.options_strategy_signals",
    "Daily technical summaries": "ai.daily_technical_summaries",
}


def _safe_query(conn, sql: str, params: list[object] | None = None) -> pd.DataFrame:
    try:
        return conn.execute(sql, params or []).df()
    except Exception:
        return pd.DataFrame()


def _table_exists(conn, table_name: str) -> bool:
    try:
        schema_name, name = table_name.split(".", 1)
        row = conn.execute(
            """
            select count(*) > 0
            from information_schema.tables
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            """,
            [schema_name, name],
        ).fetchone()
        return bool(row and row[0])
    except Exception:
        return False


def _table_columns(conn, table_name: str) -> list[str]:
    try:
        schema_name, name = table_name.split(".", 1)
        rows = conn.execute(
            """
            select column_name
            from information_schema.columns
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            order by ordinal_position
            """,
            [schema_name, name],
        ).fetchall()
        return [str(row[0]) for row in rows]
    except Exception:
        return []


def _fixed_table_query(conn, table_name: str, limit: int = 200) -> pd.DataFrame:
    if not _table_exists(conn, table_name):
        return pd.DataFrame()
    columns = _table_columns(conn, table_name)
    order_columns = [column for column in ["updated_at", "created_at", "summary_date", "filing_date", "as_of_date"] if column in columns]
    order_sql = ", ".join(f"{column} desc nulls last" for column in order_columns)
    if not order_sql:
        order_sql = "1"
    return _safe_query(conn, f"select * from {table_name} order by {order_sql} limit {int(limit)}")


def _label_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _format_latest(value: object) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    return str(value)


@st.cache_data(ttl=120)
def load_ai_dashboard_data() -> tuple[dict[str, object], str | None]:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return {}, db_state.message

    conn = db_state.connection
    table_status_records = []
    previews: dict[str, pd.DataFrame] = {}
    for label, table_name in AI_TABLES.items():
        exists = _table_exists(conn, table_name)
        df = _fixed_table_query(conn, table_name) if exists else pd.DataFrame()
        previews[label] = df
        latest_updated = df["updated_at"].max() if not df.empty and "updated_at" in df.columns else None
        table_status_records.append(
            {
                "label": label,
                "table_name": table_name,
                "exists": exists,
                "row_count": None if not exists else int(_safe_query(conn, f"select count(*) as row_count from {table_name}").iloc[0]["row_count"]),
                "latest_updated_at": latest_updated,
            }
        )

    data: dict[str, object] = {
        "table_status": pd.DataFrame(table_status_records),
        "previews": previews,
        "sec": previews["SEC filing summaries"],
        "news": previews["News summaries"],
        "latest_pipeline_run": _safe_query(
            conn,
            """
            select *
            from ops.pipeline_runs
            order by started_at desc
            limit 1
            """,
        ),
        "task_runs": _safe_query(
            conn,
            """
            select task_name, status, started_at, finished_at, row_count, error_message
            from ops.pipeline_task_runs
            order by started_at desc
            limit 50
            """,
        ),
        "errors": _safe_query(
            conn,
            """
            select created_at, task_name, error_type, error_message
            from ops.pipeline_errors
            order by created_at desc
            limit 50
            """,
        ),
        "freshness": _safe_query(
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
        ),
        "sec_queue": _safe_query(
            conn,
            """
            select summary_status, count(*) as rows
            from marts.mart_sec_ai_summary_queue
            group by 1
            order by 1
            """,
        ),
        "news_queue": _safe_query(
            conn,
            """
            select summary_status, count(*) as rows
            from marts.mart_news_ai_summary_queue
            group by 1
            order by 1
            """,
        ),
    }
    return data, None


st.title("AI Recommendations")
st.caption("Research-only AI outputs and refresh health. Not investment advice and not trading instructions.")

data, error = load_ai_dashboard_data()
if error:
    st.info(error)
    st.stop()

table_status = data.get("table_status", pd.DataFrame())
sec = data.get("sec", pd.DataFrame())
news = data.get("news", pd.DataFrame())
tasks = data.get("task_runs", pd.DataFrame())
errors = data.get("errors", pd.DataFrame())
latest_run = data.get("latest_pipeline_run", pd.DataFrame())

total_ai_rows = int(table_status["row_count"].dropna().sum()) if isinstance(table_status, pd.DataFrame) and not table_status.empty else 0
sec_rows = 0 if not isinstance(sec, pd.DataFrame) or sec.empty else len(sec)
news_rows = 0 if not isinstance(news, pd.DataFrame) or news.empty else len(news)
latest_ai_updated = (
    table_status["latest_updated_at"].dropna().max()
    if isinstance(table_status, pd.DataFrame) and not table_status.empty and "latest_updated_at" in table_status
    else None
)
latest_status = "not run"
if isinstance(latest_run, pd.DataFrame) and not latest_run.empty:
    latest_status = str(latest_run.iloc[0].get("status", "unknown"))

cols = st.columns(5)
cols[0].metric("AI Output Rows", f"{total_ai_rows:,}")
cols[1].metric("SEC Summaries", f"{sec_rows:,}")
cols[2].metric("News Summaries", f"{news_rows:,}")
cols[3].metric("Latest Pipeline Run", latest_status)
cols[4].metric("Recent Errors", 0 if not isinstance(errors, pd.DataFrame) else len(errors))
st.caption(f"Latest AI update: {_format_latest(latest_ai_updated)}")

tab_overview, tab_sec, tab_news, tab_optional, tab_pipeline = st.tabs(
    ["Overview", "SEC AI", "News AI", "Optional AI", "Pipeline Health"]
)

with tab_overview:
    st.subheader("AI Table Status")
    if isinstance(table_status, pd.DataFrame) and not table_status.empty:
        st.dataframe(table_status, use_container_width=True, hide_index=True)
        chart_df = table_status.dropna(subset=["row_count"])
        if not chart_df.empty:
            st.bar_chart(chart_df, x="label", y="row_count")
    else:
        st.info("No AI table status is available yet.")

    left, right = st.columns(2)
    with left:
        st.subheader("SEC Queue")
        sec_queue = data.get("sec_queue", pd.DataFrame())
        if isinstance(sec_queue, pd.DataFrame) and not sec_queue.empty:
            st.dataframe(sec_queue, use_container_width=True, hide_index=True)
        else:
            st.info("SEC AI queue is empty or not built yet.")
    with right:
        st.subheader("News Queue")
        news_queue = data.get("news_queue", pd.DataFrame())
        if isinstance(news_queue, pd.DataFrame) and not news_queue.empty:
            st.dataframe(news_queue, use_container_width=True, hide_index=True)
        else:
            st.info("News AI queue is empty or not built yet.")

with tab_sec:
    st.subheader("Latest SEC Filing AI Summaries")
    if isinstance(sec, pd.DataFrame) and not sec.empty:
        sec_label = _label_column(sec, ["market_impact_label", "business_impact", "broad_impact_label"])
        if sec_label:
            label_counts = sec.groupby(sec_label).size().reset_index(name="rows")
            st.bar_chart(label_counts, x=sec_label, y="rows")
        display_cols = [
            column
            for column in [
                "ticker",
                "form_type",
                "filing_date",
                "accession_number",
                "market_impact_label",
                "business_impact",
                "confidence_score",
                "summary",
                "updated_at",
            ]
            if column in sec.columns
        ]
        st.dataframe(sec[display_cols] if display_cols else sec, use_container_width=True, hide_index=True)
    else:
        st.info("No SEC AI summaries are available yet.")

with tab_news:
    st.subheader("Latest News AI Summaries")
    if isinstance(news, pd.DataFrame) and not news.empty:
        news_label = _label_column(news, ["market_impact_label", "bull_bear_label"])
        if news_label:
            label_counts = news.groupby(news_label).size().reset_index(name="rows")
            st.bar_chart(label_counts, x=news_label, y="rows")
        if "summary_date" in news.columns:
            dated = news.groupby("summary_date").size().reset_index(name="rows").sort_values("summary_date")
            st.line_chart(dated, x="summary_date", y="rows")
        display_cols = [
            column
            for column in [
                "summary_date",
                "category_id",
                "category_name",
                "category",
                "ticker",
                "headline",
                "market_impact_label",
                "bull_bear_label",
                "impact_score",
                "bull_bear_score",
                "confidence_score",
                "summary",
                "updated_at",
            ]
            if column in news.columns
        ]
        st.dataframe(news[display_cols] if display_cols else news, use_container_width=True, hide_index=True)
    else:
        st.info("No news AI summaries are available yet.")

with tab_optional:
    st.subheader("Feature-Flagged AI Domains")
    previews = data.get("previews", {})
    if isinstance(previews, dict):
        for label in [
            "Political trade signals",
            "Accumulation recommendations",
            "Options strategy signals",
            "Daily technical summaries",
        ]:
            st.markdown(f"**{label}**")
            preview = previews.get(label, pd.DataFrame())
            if isinstance(preview, pd.DataFrame) and not preview.empty:
                st.dataframe(preview, use_container_width=True, hide_index=True)
            else:
                st.info("No rows yet, or the optional AI contract has not been created.")

with tab_pipeline:
    st.subheader("Latest DataPipeline Run")
    if isinstance(latest_run, pd.DataFrame) and not latest_run.empty:
        st.dataframe(latest_run, use_container_width=True, hide_index=True)
    else:
        st.info("No pipeline run has been recorded yet.")

    st.subheader("Recent Task Runs")
    if isinstance(tasks, pd.DataFrame) and not tasks.empty:
        success_rate = float((tasks["status"].astype(str).str.lower() == "success").mean() * 100)
        st.metric("Recent Task Success Rate", f"{success_rate:.0f}%")
        st.dataframe(tasks, use_container_width=True, hide_index=True)
    else:
        st.info("No recent task runs are available.")

    st.subheader("Freshness Checks")
    freshness = data.get("freshness", pd.DataFrame())
    if isinstance(freshness, pd.DataFrame) and not freshness.empty:
        st.dataframe(freshness, use_container_width=True, hide_index=True)
    else:
        st.info("No freshness checks are available.")

    st.subheader("Recent Errors")
    if isinstance(errors, pd.DataFrame) and not errors.empty:
        st.dataframe(errors, use_container_width=True, hide_index=True)
    else:
        st.success("No recent pipeline errors recorded.")

st.warning(
    "This page visualizes structured CapitalPilot_AI outputs and pipeline health only. "
    "All labels are research context, not investment advice."
)
