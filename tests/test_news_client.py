from datetime import date
from pathlib import Path

from src.news_client import ManualCSVNewsProvider, dedupe_articles


FIXTURES = Path(__file__).parent / "fixtures"


def test_manual_news_provider_dedupes_normalized_urls():
    provider = ManualCSVNewsProvider(path=FIXTURES / "news_articles_sample.csv")
    df = provider.fetch_articles(
        categories=[{"id": "fomc_rate_decision"}, {"id": "ai_semiconductor_industry"}],
        tickers=["NVDA"],
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
        limit_per_category=10,
    )

    assert len(df) == 2
    assert len(dedupe_articles(df)) == 2
    assert set(df["category"]) == {"fomc_rate_decision", "ai_semiconductor_industry"}

