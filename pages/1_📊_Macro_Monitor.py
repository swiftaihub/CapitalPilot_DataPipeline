"""Macro Monitor dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import line_chart
from src.db import get_streamlit_connection
from src.utils import format_number, format_percent, safe_dataframe_dates

st.set_page_config(page_title="Macro Monitor", page_icon="📊", layout="wide")


@st.cache_data(ttl=900)
def load_macro_dashboard() -> tuple[pd.DataFrame, str | None]:
    db_state = get_streamlit_connection()
    if not db_state.available or db_state.connection is None:
        return pd.DataFrame(), db_state.message
    try:
        df = db_state.connection.execute(
            """
            select *
            from marts.mart_macro_dashboard
            order by date desc
            """
        ).df()
        return safe_dataframe_dates(df), None
    except Exception as exc:
        return pd.DataFrame(), f"Macro mart is not available yet: {exc}"


st.title("Macro Monitor")
st.caption("Research context only. Not financial advice.")

df, error = load_macro_dashboard()
if df.empty:
    st.info(error or "No macro data is available yet.")
    st.stop()

df = df.sort_values("date")
min_date = df["date"].min().date()
max_date = df["date"].max().date()

selected_range = st.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start, end = selected_range
else:
    start, end = min_date, max_date

filtered = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
if filtered.empty:
    st.info("No macro observations are available for the selected date range.")
    st.stop()

latest = filtered.sort_values("date").iloc[-1]

metric_options = {
    "Fed Funds": "fed_funds",
    "10Y Treasury": "ten_year",
    "2Y Treasury": "two_year",
    "10Y-2Y Spread": "ten_two_spread",
    "CPI YoY": "cpi_yoy",
    "Unemployment Rate": "unemployment_rate",
    "Dollar Index": "dollar_index",
    "VIX": "vix",
    "Macro Regime Score": "macro_regime_score",
}
selected_metric = st.selectbox("Metric selector", list(metric_options.keys()))
selected_column = metric_options[selected_metric]

kpi_rows = [
    ("Fed Funds", "fed_funds", True),
    ("10Y Treasury", "ten_year", True),
    ("10Y-2Y Spread", "ten_two_spread", True),
    ("CPI YoY", "cpi_yoy", False),
    ("Unemployment", "unemployment_rate", True),
    ("Dollar Index", "dollar_index", None),
    ("VIX", "vix", None),
    ("Regime Score", "macro_regime_score", None),
]

cols = st.columns(4)
for idx, (label, column, is_percent_points) in enumerate(kpi_rows):
    value = latest.get(column)
    if is_percent_points is True:
        formatted = format_percent(value, already_percent=True)
    elif is_percent_points is False:
        formatted = format_percent(value)
    else:
        formatted = format_number(value, digits=2)
    cols[idx % 4].metric(label, formatted)

st.subheader(latest.get("macro_regime_label", "Insufficient data"))
st.write(latest.get("macro_regime_explanation", "Insufficient macro data to classify regime."))

st.plotly_chart(
    line_chart(
        filtered,
        x="date",
        y=selected_column,
        title=f"{selected_metric} Over Time",
        y_axis_title=selected_metric,
    ),
    use_container_width=True,
)

tab_rates, tab_inflation, tab_labor, tab_risk = st.tabs(["Rates", "Inflation", "Labor", "Dollar and Volatility"])
with tab_rates:
    st.plotly_chart(
        line_chart(filtered, x="date", y=["fed_funds", "ten_year"], title="Fed Funds vs 10Y Treasury", y_axis_title="Percent"),
        use_container_width=True,
    )
    st.plotly_chart(
        line_chart(filtered, x="date", y="ten_two_spread", title="10Y-2Y Spread", y_axis_title="Percent"),
        use_container_width=True,
    )
with tab_inflation:
    st.plotly_chart(
        line_chart(filtered, x="date", y="cpi_yoy", title="CPI YoY", y_axis_title="Decimal"),
        use_container_width=True,
    )
with tab_labor:
    st.plotly_chart(
        line_chart(filtered, x="date", y="unemployment_rate", title="Unemployment Rate", y_axis_title="Percent"),
        use_container_width=True,
    )
with tab_risk:
    st.plotly_chart(
        line_chart(filtered, x="date", y="dollar_index", title="Dollar Index", y_axis_title="Index"),
        use_container_width=True,
    )
    st.plotly_chart(
        line_chart(filtered, x="date", y="vix", title="VIX", y_axis_title="Index"),
        use_container_width=True,
    )

with st.expander("Raw Mart Rows"):
    st.dataframe(filtered.sort_values("date", ascending=False), use_container_width=True)

