from datetime import date
from pathlib import Path

from src.news_client import AlphaVantageNewsProvider, ManualCSVNewsProvider, dedupe_articles


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


def test_alpha_vantage_watchlist_fetch_uses_single_request(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "feed": [
                    {
                        "title": "NVIDIA AI capex demand rises",
                        "url": "https://example.com/nvda-ai",
                        "time_published": "20260614T120000",
                        "source": "Example Wire",
                        "summary": "Semiconductor and AI infrastructure demand update.",
                        "overall_sentiment_label": "Bullish",
                        "ticker_sentiment": [{"ticker": "NVDA"}],
                        "topics": [{"topic": "technology"}],
                    }
                ]
            }

    def fake_get(url, params, timeout):
        calls.append(params)
        return Response()

    monkeypatch.setattr("src.news_client.requests.get", fake_get)
    provider = AlphaVantageNewsProvider(api_key="test")
    df = provider.fetch_articles(
        categories=[{"id": "ai_semiconductor_industry", "query_keywords": ["AI", "semiconductor"]}],
        tickers=["NVDA", "MSFT"],
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
        limit_per_category=10,
    )

    assert len(calls) == 1
    assert calls[0]["tickers"] == "NVDA,MSFT"
    assert len(df) == 1
    assert df.iloc[0]["category"] == "ai_semiconductor_industry"
