"""Plotly chart helpers."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def line_chart(
    df: pd.DataFrame,
    *,
    x: str,
    y: str | list[str],
    title: str,
    y_axis_title: str = "",
) -> go.Figure:
    """Build a simple line chart for Streamlit."""
    y_columns = [y] if isinstance(y, str) else y
    fig = go.Figure()
    for column in y_columns:
        if column in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df[x],
                    y=df[column],
                    mode="lines",
                    name=column.replace("_", " ").title(),
                )
            )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_axis_title,
        hovermode="x unified",
        margin=dict(l=12, r=12, t=48, b=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig

