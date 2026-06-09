"""Phase 2 placeholder SEC research service functions.

These functions are intentionally Streamlit-independent and safe to expose through
a future read-only MCP server. They do not query SEC, MotherDuck, LLMs, or MCP in
Phase 1.
"""

from __future__ import annotations


def search_sec_filings(
    ticker: str | None = None,
    form_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
) -> dict:
    """
    Phase 2 placeholder.

    Future behavior:
    Search recent SEC filings from MotherDuck marts.
    """
    return {
        "status": "planned_phase_2",
        "message": "SEC filing search is not implemented in Phase 1.",
        "ticker": ticker,
        "form_type": form_type,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "data": [],
    }


def get_recent_10q_risk_factor_changes(ticker: str, count: int = 3) -> dict:
    """
    Phase 2 placeholder.

    Future behavior:
    Compare risk factors across the latest N 10-Q filings for a ticker.
    """
    return {
        "status": "planned_phase_2",
        "message": "Risk factor diffing is not implemented in Phase 1.",
        "ticker": ticker,
        "count": count,
        "data": [],
    }


def find_watchlist_8k_filings(days_back: int = 30) -> dict:
    """
    Phase 2 placeholder.

    Future behavior:
    Find watchlist companies with 8-K filings in the specified date range.
    """
    return {
        "status": "planned_phase_2",
        "message": "8-K watchlist search is not implemented in Phase 1.",
        "days_back": days_back,
        "data": [],
    }


def compare_companies_research_snapshot(ticker_a: str, ticker_b: str) -> dict:
    """
    Phase 2 placeholder.

    Future behavior:
    Compare revenue growth, FCF yield, valuation, and recent filing risks.
    """
    return {
        "status": "planned_phase_2",
        "message": "Company comparison with SEC context is not implemented in Phase 1.",
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "data": {},
    }


def generate_weekly_research_brief(
    watchlist: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Phase 2 placeholder.

    Future behavior:
    Generate a weekly research brief using macro, filings, valuation, and watchlist context.
    """
    return {
        "status": "planned_phase_2",
        "message": "Weekly research brief generation is not implemented in Phase 1.",
        "watchlist": watchlist,
        "start_date": start_date,
        "end_date": end_date,
        "data": "",
    }

