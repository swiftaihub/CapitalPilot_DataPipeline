"""Deprecated SEC research service placeholders.

CapitalPilot_DataPipeline now owns SEC ingestion tables, dbt marts, and AI queue
contracts. Interactive AI and tool orchestration belong in CapitalPilot_AI.
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
    Deprecated placeholder.

    Future behavior:
    Read SEC filing marts from CapitalPilot_UI or CapitalPilot_AI.
    """
    return {
        "status": "planned_phase_2",
        "message": "Interactive SEC filing search is not implemented in CapitalPilot_DataPipeline.",
        "ticker": ticker,
        "form_type": form_type,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "data": [],
    }


def get_recent_10q_risk_factor_changes(ticker: str, count: int = 3) -> dict:
    """
    Deprecated placeholder.

    Future behavior:
    Compare risk factors across the latest N 10-Q filings for a ticker.
    """
    return {
        "status": "planned_phase_2",
        "message": "Risk factor diffing belongs in CapitalPilot_AI using DataPipeline SEC tables.",
        "ticker": ticker,
        "count": count,
        "data": [],
    }


def find_watchlist_8k_filings(days_back: int = 30) -> dict:
    """
    Deprecated placeholder.

    Future behavior:
    Find watchlist companies with 8-K filings in the specified date range.
    """
    return {
        "status": "planned_phase_2",
        "message": "Use DataPipeline marts.mart_watchlist_8k_alerts for produced 8-K rows.",
        "days_back": days_back,
        "data": [],
    }


def compare_companies_research_snapshot(ticker_a: str, ticker_b: str) -> dict:
    """
    Deprecated placeholder.

    Future behavior:
    Compare revenue growth, FCF yield, valuation, and recent filing risks.
    """
    return {
        "status": "planned_phase_2",
        "message": "Company comparison belongs in CapitalPilot_AI/UI using DataPipeline marts.",
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
    Deprecated placeholder.

    Future behavior:
    Generate a weekly research brief using macro, filings, valuation, and watchlist context.
    """
    return {
        "status": "planned_phase_2",
        "message": "Weekly research brief generation belongs in CapitalPilot_AI.",
        "watchlist": watchlist,
        "start_date": start_date,
        "end_date": end_date,
        "data": "",
    }

