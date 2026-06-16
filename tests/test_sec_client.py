import json
from pathlib import Path

from src.sec_client import archive_document_url, parse_company_tickers, parse_recent_filings, ticker_cik_lookup


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_company_tickers_and_recent_filings():
    company_payload = json.loads((FIXTURES / "sec_company_tickers.json").read_text(encoding="utf-8"))
    submissions = json.loads((FIXTURES / "sec_submissions_nvda.json").read_text(encoding="utf-8"))

    tickers = parse_company_tickers(company_payload)
    lookup = ticker_cik_lookup(tickers)

    assert lookup["NVDA"] == "0001045810"
    assert archive_document_url("0001045810", "0001045810-26-000010", "nvda-20260131.htm").endswith(
        "/1045810/000104581026000010/nvda-20260131.htm"
    )

    filings = parse_recent_filings(
        submissions,
        ticker="NVDA",
        cik=lookup["NVDA"],
        forms=["10-K", "8-K"],
        max_filings=10,
    )

    assert set(filings["form_type"]) == {"10-K", "8-K"}
    assert filings.iloc[0]["document_url"].startswith("https://www.sec.gov/Archives/edgar/data/1045810/")

