"""Official trade pipeline observability page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db import get_streamlit_connection

st.set_page_config(page_title="official_trade", page_icon="OT", layout="wide")


def _safe_query(conn, sql: str, params: list[object] | None = None) -> pd.DataFrame:
    try:
        return conn.execute(sql, params or []).df()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_official_trade_data() -> tuple[dict[str, pd.DataFrame], str | None]:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return {}, db_state.message

    conn = db_state.connection
    data = {
        "summary": _safe_query(
            conn,
            """
            select
                (select count(*) from raw.raw_political_disclosure_reports) as raw_reports,
                (select count(*) from raw.raw_political_transactions) as raw_transactions,
                (select count(*) from marts.mart_political_trading_dashboard) as mart_transactions,
                (select count(distinct official_name) from marts.mart_political_trading_dashboard) as officials,
                (select count(distinct ticker) from marts.mart_political_trading_dashboard where ticker is not null) as tickers,
                (select max(filing_date) from marts.mart_political_trading_dashboard) as latest_filing_date
            """,
        ),
        "trades": _safe_query(
            conn,
            """
            select
                transaction_id,
                official_name,
                role,
                branch,
                chamber,
                party,
                state,
                ticker,
                asset_name,
                asset_type,
                transaction_type,
                transaction_direction,
                transaction_date,
                notification_date,
                filing_date,
                amount_min,
                amount_max,
                amount_text,
                amount_is_range_or_uncertain,
                owner,
                source_report_id,
                source_url,
                source_pdf_url,
                confidence_score,
                overlaps_watchlist,
                ticker_official_count,
                disclosure_note
            from marts.mart_political_trading_dashboard
            order by filing_date desc nulls last, transaction_date desc nulls last, official_name
            limit 5000
            """,
        ),
        "top_tickers": _safe_query(
            conn,
            """
            select
                ticker,
                count(*) as transaction_count,
                count(distinct official_name) as official_count,
                max(filing_date) as latest_filing_date,
                bool_or(overlaps_watchlist) as overlaps_watchlist
            from marts.mart_political_trading_dashboard
            where ticker is not null
            group by 1
            order by transaction_count desc, official_count desc, ticker
            limit 50
            """,
        ),
        "activity": _safe_query(
            conn,
            """
            select
                filing_date,
                count(*) as transactions,
                count(distinct source_report_id) as reports,
                count(distinct official_name) as officials
            from marts.mart_political_trading_dashboard
            where filing_date is not null
            group by 1
            order by filing_date
            """,
        ),
        "branch_summary": _safe_query(
            conn,
            """
            select
                branch,
                count(*) as transactions,
                count(distinct official_name) as officials,
                count(distinct source_report_id) as reports,
                max(filing_date) as latest_filing_date
            from marts.mart_political_trading_dashboard
            group by 1
            order by transactions desc
            """,
        ),
        "tasks": _safe_query(
            conn,
            """
            select task_name, status, started_at, finished_at, row_count, error_message
            from ops.pipeline_task_runs
            where lower(task_name) like '%political%'
            order by started_at desc
            limit 25
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
                where domain = 'political'
            )
            select domain, table_name, row_count, max_timestamp, status, checked_at
            from ranked
            where rn = 1
            order by table_name
            """,
        ),
        "errors": _safe_query(
            conn,
            """
            select created_at, task_name, error_type, error_message
            from ops.pipeline_errors
            where lower(task_name) like '%political%'
            order by created_at desc
            limit 50
            """,
        ),
        "raw_reports": _safe_query(
            conn,
            """
            select *
            from raw.raw_political_disclosure_reports
            order by filing_date desc nulls last, updated_at desc nulls last
            limit 200
            """,
        ),
        "raw_transactions": _safe_query(
            conn,
            """
            select *
            from raw.raw_political_transactions
            order by filing_date desc nulls last, transaction_date desc nulls last
            limit 200
            """,
        ),
    }
    return data, None


def _metric_value(summary: pd.DataFrame, column: str, default: object = 0) -> object:
    if summary.empty or column not in summary.columns:
        return default
    value = summary.iloc[0].get(column)
    if pd.isna(value):
        return default
    return value


def _filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted(str(item) for item in frame[column].dropna().unique().tolist())


st.title("official_trade")
st.caption("Internal monitor for public official transaction disclosure ingestion. Research context only.")

data, error = load_official_trade_data()
if error:
    st.info(error)
    st.stop()

summary = data.get("summary", pd.DataFrame())
trades = data.get("trades", pd.DataFrame())

cols = st.columns(6)
cols[0].metric("Raw Reports", f"{int(_metric_value(summary, 'raw_reports')):,}")
cols[1].metric("Raw Transactions", f"{int(_metric_value(summary, 'raw_transactions')):,}")
cols[2].metric("Mart Rows", f"{int(_metric_value(summary, 'mart_transactions')):,}")
cols[3].metric("Officials", f"{int(_metric_value(summary, 'officials')):,}")
cols[4].metric("Tickers", f"{int(_metric_value(summary, 'tickers')):,}")
cols[5].metric("Latest Filing", str(_metric_value(summary, "latest_filing_date", "n/a")))

if trades.empty:
    st.info("No official trade mart rows are available yet.")

tab_overview, tab_trades, tab_sources, tab_runs, tab_raw = st.tabs(
    ["Overview", "Transactions", "Source Health", "Runs and Errors", "Raw Tables"]
)

with tab_overview:
    left, right = st.columns([1.1, 0.9])
    with left:
        activity = data.get("activity", pd.DataFrame())
        st.subheader("Filing Activity")
        if activity.empty:
            st.info("No filing activity rows are available.")
        else:
            st.line_chart(activity, x="filing_date", y=["transactions", "reports", "officials"])
    with right:
        top_tickers = data.get("top_tickers", pd.DataFrame())
        st.subheader("Most Disclosed Tickers")
        if top_tickers.empty:
            st.info("No ticker aggregation rows are available.")
        else:
            st.dataframe(top_tickers, use_container_width=True, hide_index=True)

    branch_summary = data.get("branch_summary", pd.DataFrame())
    st.subheader("Branch Summary")
    if branch_summary.empty:
        st.info("No branch summary rows are available.")
    else:
        st.dataframe(branch_summary, use_container_width=True, hide_index=True)

with tab_trades:
    filtered = trades.copy()
    filter_cols = st.columns(4)
    selected_branch = filter_cols[0].multiselect("Branch", _filter_options(filtered, "branch"))
    selected_direction = filter_cols[1].multiselect("Direction", _filter_options(filtered, "transaction_direction"))
    selected_ticker = filter_cols[2].multiselect("Ticker", _filter_options(filtered, "ticker"))
    selected_official = filter_cols[3].multiselect("Official", _filter_options(filtered, "official_name"))

    if selected_branch:
        filtered = filtered[filtered["branch"].astype(str).isin(selected_branch)]
    if selected_direction:
        filtered = filtered[filtered["transaction_direction"].astype(str).isin(selected_direction)]
    if selected_ticker:
        filtered = filtered[filtered["ticker"].astype(str).isin(selected_ticker)]
    if selected_official:
        filtered = filtered[filtered["official_name"].astype(str).isin(selected_official)]

    st.metric("Filtered Rows", f"{len(filtered):,}")
    display_columns = [
        "filing_date",
        "transaction_date",
        "official_name",
        "branch",
        "ticker",
        "asset_name",
        "transaction_direction",
        "amount_text",
        "amount_is_range_or_uncertain",
        "confidence_score",
        "overlaps_watchlist",
        "source_pdf_url",
    ]
    existing_columns = [column for column in display_columns if column in filtered.columns]
    st.dataframe(filtered[existing_columns], use_container_width=True, hide_index=True)

with tab_sources:
    freshness = data.get("freshness", pd.DataFrame())
    st.subheader("Freshness")
    if freshness.empty:
        st.info("No political freshness check has been recorded yet.")
    else:
        st.dataframe(freshness, use_container_width=True, hide_index=True)

    if not trades.empty:
        source_cols = st.columns(3)
        range_rows = int(trades["amount_is_range_or_uncertain"].fillna(False).sum()) if "amount_is_range_or_uncertain" in trades else 0
        low_confidence = int((trades["confidence_score"].fillna(0) < 0.5).sum()) if "confidence_score" in trades else 0
        watchlist_overlap = int(trades["overlaps_watchlist"].fillna(False).sum()) if "overlaps_watchlist" in trades else 0
        source_cols[0].metric("Range/Uncertain Amounts", f"{range_rows:,}")
        source_cols[1].metric("Low Confidence Rows", f"{low_confidence:,}")
        source_cols[2].metric("Watchlist Overlaps", f"{watchlist_overlap:,}")

with tab_runs:
    tasks = data.get("tasks", pd.DataFrame())
    errors = data.get("errors", pd.DataFrame())
    st.subheader("Political Task Runs")
    if tasks.empty:
        st.info("No political task runs have been recorded yet.")
    else:
        st.dataframe(tasks, use_container_width=True, hide_index=True)

    st.subheader("Political Errors")
    if errors.empty:
        st.success("No political pipeline errors recorded.")
    else:
        st.dataframe(errors, use_container_width=True, hide_index=True)

with tab_raw:
    raw_reports = data.get("raw_reports", pd.DataFrame())
    raw_transactions = data.get("raw_transactions", pd.DataFrame())
    raw_tab_reports, raw_tab_transactions = st.tabs(["Reports", "Transactions"])
    with raw_tab_reports:
        if raw_reports.empty:
            st.info("No raw report rows are available.")
        else:
            st.dataframe(raw_reports, use_container_width=True, hide_index=True)
    with raw_tab_transactions:
        if raw_transactions.empty:
            st.info("No raw transaction rows are available.")
        else:
            st.dataframe(raw_transactions, use_container_width=True, hide_index=True)

st.warning(
    "Official disclosures can be delayed, range-based, and parser-dependent. "
    "This page does not infer exact holdings or make trading recommendations."
)
