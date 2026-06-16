from src.services.sec_research import (
    compare_companies_research_snapshot,
    find_watchlist_8k_filings,
    generate_weekly_research_brief,
    get_recent_10q_risk_factor_changes,
    search_sec_filings,
)


def test_sec_placeholder_functions_return_planned_status():
    responses = [
        search_sec_filings(ticker="NVDA"),
        get_recent_10q_risk_factor_changes("NVDA"),
        find_watchlist_8k_filings(),
        compare_companies_research_snapshot("MRVL", "AVGO"),
        generate_weekly_research_brief(["NVDA", "AVGO"]),
    ]

    assert all(response["status"] == "planned_phase_2" for response in responses)
    assert all("CapitalPilot_AI" in response["message"] or "DataPipeline" in response["message"] for response in responses)

