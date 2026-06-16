from pathlib import Path

from src.political_disclosures_client import (
    ManualCSVPoliticalDisclosureClient,
    normalize_transaction_type,
    parse_amount_range,
    parse_house_fd_xml,
    parse_house_ptr_pdf_text,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_amount_range_and_manual_csv_normalization():
    assert parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert parse_amount_range("Over $50,000") == (50000.0, None)
    assert normalize_transaction_type("Purchase") == "purchase"
    assert normalize_transaction_type("Sale") == "sale"

    provider = ManualCSVPoliticalDisclosureClient(FIXTURES / "political_transactions_sample.csv")
    reports, transactions = provider.fetch()

    assert len(reports) == 1
    assert len(transactions) == 2
    assert transactions.loc[transactions["ticker"] == "NVDA", "amount_max"].iloc[0] == 15000.0
    assert transactions["source_report_id"].nunique() == 1


def test_house_xml_and_ptr_text_parsing():
    xml_content = (FIXTURES / "house_fd_sample.xml").read_bytes()
    reports = parse_house_fd_xml(xml_content, source_url="https://example.test/2026FD.xml")

    assert len(reports) == 1
    report = reports.iloc[0].to_dict()
    assert report["report_id"] == "house-2026-20034201"
    assert report["source_pdf_url"].endswith("/ptr-pdfs/2026/20034201.pdf")

    text = (FIXTURES / "house_ptr_text_sample.txt").read_text(encoding="utf-8")
    transactions = parse_house_ptr_pdf_text(text, report=report)

    assert len(transactions) == 2
    assert transactions[0]["ticker"] == "AMZN"
    assert transactions[0]["transaction_type"] == "sale"
    assert transactions[1]["ticker"] == "AAPL"
    assert transactions[1]["transaction_type"] == "purchase"
    assert transactions[1]["amount_min"] == 15001.0
