"""Configurable market-news ingestion helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import requests

from src.config import ROOT_DIR, get_secret, load_news_categories_config, load_news_sources_config


class MissingProviderSecret(ValueError):
    """Raised when an optional provider is requested without its API key."""


class NewsProvider(Protocol):
    """Provider interface for news ingestion."""

    name: str

    def fetch_articles(
        self,
        *,
        categories: list[dict[str, Any]],
        tickers: list[str],
        start_date: date,
        end_date: date,
        limit_per_category: int,
    ) -> pd.DataFrame:
        """Return normalized raw-news article rows."""


def normalize_url(url: str | None) -> str:
    """Normalize URL for stable dedupe."""
    if url is None or pd.isna(url):
        return ""
    parts = urlsplit(str(url).strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    normalized_query = urlencode(sorted(query))
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            normalized_query,
            "",
        )
    )


def article_id_for(
    *,
    source_provider: str,
    publisher: str | None,
    title: str | None,
    url: str | None,
    published_at: str | datetime | None,
) -> str:
    """Build a stable article id from source, URL/title, and timestamp."""
    key = "|".join(
        [
            source_provider.lower().strip(),
            (publisher or "").lower().strip(),
            normalize_url(url),
            (title or "").lower().strip(),
            str(published_at or "")[:19],
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def enabled_news_categories(category_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Return enabled news category dictionaries from config."""
    data = load_news_categories_config()
    entries = data.get("categories", [])
    if not isinstance(entries, list):
        raise ValueError("config/news_categories.yaml must contain a categories list.")
    selected = {item.strip() for item in category_ids or [] if item.strip()}
    categories = [
        item
        for item in entries
        if isinstance(item, dict)
        and item.get("enabled", True)
        and (not selected or str(item.get("id")) in selected or str(item.get("group")) in selected)
    ]
    return categories


def dedupe_articles(df: pd.DataFrame) -> pd.DataFrame:
    """Dedupe news articles by article_id, normalized URL, or title/publisher/date."""
    if df.empty:
        return df
    frame = df.copy()
    frame["normalized_url"] = frame["url"].map(normalize_url)
    frame["published_date"] = pd.to_datetime(frame["published_at"], errors="coerce").dt.date
    frame = frame.sort_values(["published_at", "updated_at"], na_position="last")
    deduped = frame.drop_duplicates(subset=["article_id"], keep="last")
    deduped = deduped.drop_duplicates(subset=["normalized_url"], keep="last")
    deduped = deduped.drop_duplicates(
        subset=["source_provider", "publisher", "title", "published_date", "category"],
        keep="last",
    )
    return deduped.drop(columns=["normalized_url", "published_date"])


def _base_article_record(
    *,
    source_provider: str,
    publisher: str | None,
    title: str | None,
    url: str | None,
    published_at: Any,
    category: str | None,
    query: str | None,
    related_tickers: list[str] | None,
    raw_summary: str | None,
    raw_sentiment: str | None,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "article_id": article_id_for(
            source_provider=source_provider,
            publisher=publisher,
            title=title,
            url=url,
            published_at=published_at,
        ),
        "source_provider": source_provider,
        "publisher": publisher,
        "title": title,
        "url": normalize_url(url) or url,
        "published_at": published_at,
        "category": category,
        "query": query,
        "related_tickers_json": json.dumps(related_tickers or [], sort_keys=True),
        "raw_summary": raw_summary,
        "raw_sentiment": raw_sentiment,
        "raw_payload_json": json.dumps(raw_payload, default=str, sort_keys=True),
        "updated_at": updated_at,
    }


@dataclass
class ManualCSVNewsProvider:
    """Load manually supplied news CSV files."""

    path: Path | None = None
    name: str = "manual"

    def fetch_articles(
        self,
        *,
        categories: list[dict[str, Any]],
        tickers: list[str],
        start_date: date,
        end_date: date,
        limit_per_category: int,
    ) -> pd.DataFrame:
        source_path = self.path or _manual_news_path()
        files = [source_path] if source_path.is_file() else sorted(source_path.glob("*.csv")) if source_path.exists() else []
        frames: list[pd.DataFrame] = []
        for file_path in files:
            frame = pd.read_csv(file_path)
            frame["source_file"] = str(file_path)
            frames.append(frame)
        if not frames:
            return empty_news_frame()
        raw = pd.concat(frames, ignore_index=True)
        selected_categories = {
            str(category.get("id")).lower().strip()
            for category in categories
            if isinstance(category, dict) and category.get("id")
        }
        records = []
        for row in raw.to_dict("records"):
            published_at = row.get("published_at")
            published_date = pd.to_datetime(published_at, errors="coerce")
            if pd.isna(published_date):
                continue
            category = str(row.get("category") or "").lower().strip()
            if selected_categories and category not in selected_categories:
                continue
            if not (start_date <= published_date.date() <= end_date):
                continue
            related = _split_list(row.get("related_tickers"))
            if tickers and related and not set(tickers).intersection({item.upper() for item in related}):
                continue
            records.append(
                _base_article_record(
                    source_provider=str(row.get("source_provider") or self.name),
                    publisher=row.get("publisher"),
                    title=row.get("title"),
                    url=row.get("url"),
                    published_at=published_at,
                    category=category,
                    query=row.get("query"),
                    related_tickers=related,
                    raw_summary=row.get("raw_summary"),
                    raw_sentiment=row.get("raw_sentiment"),
                    raw_payload=row,
                )
            )
        if not records:
            return empty_news_frame()
        deduped = dedupe_articles(pd.DataFrame.from_records(records))
        return deduped.sort_values("published_at", ascending=False).groupby("category", as_index=False).head(limit_per_category)


@dataclass
class AlphaVantageNewsProvider:
    """Optional Alpha Vantage NEWS_SENTIMENT provider."""

    api_key: str | None = None
    endpoint: str = "https://www.alphavantage.co/query"
    name: str = "alpha_vantage"

    def fetch_articles(
        self,
        *,
        categories: list[dict[str, Any]],
        tickers: list[str],
        start_date: date,
        end_date: date,
        limit_per_category: int,
    ) -> pd.DataFrame:
        key = self.api_key or get_secret("ALPHA_VANTAGE_API_KEY")
        if not key:
            raise MissingProviderSecret("ALPHA_VANTAGE_API_KEY is not set; skipping Alpha Vantage news.")
        records: list[dict[str, Any]] = []
        if tickers:
            params = {
                "function": "NEWS_SENTIMENT",
                "apikey": key,
                "tickers": ",".join(tickers),
                "limit": str(min(max(limit_per_category * max(len(categories), 1), limit_per_category), 1000)),
                "time_from": start_date.strftime("%Y%m%dT0000"),
                "time_to": (end_date + timedelta(days=1)).strftime("%Y%m%dT0000"),
                "sort": "LATEST",
            }
            payload = self._request_payload(params)
            for item in payload.get("feed", []):
                category = _match_category_for_alpha_item(item, categories) or {"id": "company_watchlist"}
                related = _alpha_related_tickers(item, tickers)
                records.append(
                    _base_article_record(
                        source_provider=self.name,
                        publisher=item.get("source"),
                        title=item.get("title"),
                        url=item.get("url"),
                        published_at=_parse_alpha_time(item.get("time_published")),
                        category=category.get("id"),
                        query=",".join(tickers),
                        related_tickers=related,
                        raw_summary=item.get("summary"),
                        raw_sentiment=item.get("overall_sentiment_label"),
                        raw_payload=item,
                    )
                )
            return _limit_articles_per_category(records, limit_per_category)

        topic_to_categories: dict[str, list[dict[str, Any]]] = {}
        for category in categories:
            topic_to_categories.setdefault(_alpha_topic_for_category(category), []).append(category)

        for topic, topic_categories in topic_to_categories.items():
            params = {
                "function": "NEWS_SENTIMENT",
                "apikey": key,
                "topics": topic,
                "limit": str(min(limit_per_category * len(topic_categories), 1000)),
                "time_from": start_date.strftime("%Y%m%dT0000"),
                "time_to": (end_date + timedelta(days=1)).strftime("%Y%m%dT0000"),
                "sort": "LATEST",
            }
            payload = self._request_payload(params)
            for item in payload.get("feed", []):
                category = _match_category_for_alpha_item(item, topic_categories) or topic_categories[0]
                related = _alpha_related_tickers(item, [])
                records.append(
                    _base_article_record(
                        source_provider=self.name,
                        publisher=item.get("source"),
                        title=item.get("title"),
                        url=item.get("url"),
                        published_at=_parse_alpha_time(item.get("time_published")),
                        category=category.get("id"),
                        query=topic,
                        related_tickers=related,
                        raw_summary=item.get("summary"),
                        raw_sentiment=item.get("overall_sentiment_label"),
                        raw_payload=item,
                    )
                )
        return _limit_articles_per_category(records, limit_per_category)

    def _request_payload(self, params: dict[str, str]) -> dict[str, Any]:
        response = requests.get(self.endpoint, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        for key in ["Error Message", "Information", "Note"]:
            if payload.get(key):
                raise RuntimeError(f"Alpha Vantage returned {key}: {payload[key]}")
        return payload


def provider_from_config(provider_name: str | None, *, manual_file: str | None = None) -> NewsProvider:
    """Instantiate a configured provider."""
    config = load_news_sources_config()
    selected = (provider_name or config.get("default_provider") or "manual").lower().strip()
    if selected == "manual":
        return ManualCSVNewsProvider(path=Path(manual_file) if manual_file else None)
    if selected in {"alpha_vantage", "alphavantage"}:
        endpoint = (
            config.get("providers", {})
            .get("alpha_vantage", {})
            .get("endpoint", "https://www.alphavantage.co/query")
        )
        return AlphaVantageNewsProvider(endpoint=endpoint)
    raise ValueError(f"Unsupported news provider: {provider_name}")


def empty_news_frame() -> pd.DataFrame:
    """Return an empty normalized news dataframe."""
    return pd.DataFrame(
        columns=[
            "article_id",
            "source_provider",
            "publisher",
            "title",
            "url",
            "published_at",
            "category",
            "query",
            "related_tickers_json",
            "raw_summary",
            "raw_sentiment",
            "raw_payload_json",
            "updated_at",
        ]
    )


def _manual_news_path() -> Path:
    config = load_news_sources_config()
    default_path = config.get("providers", {}).get("manual", {}).get("default_path", "data/manual/news_articles")
    path = Path(default_path)
    return path if path.is_absolute() else ROOT_DIR / path


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, str) and not value.strip():
        return []
    if isinstance(value, list):
        return [str(item).upper().strip() for item in value if str(item).strip()]
    return [item.strip().upper() for item in str(value).replace(";", ",").split(",") if item.strip()]


def _parse_alpha_time(value: str | None) -> str | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, format="%Y%m%dT%H%M%S", errors="coerce", utc=True)
    if pd.isna(parsed):
        return value
    return parsed.to_pydatetime().replace(tzinfo=None).isoformat()


def _limit_articles_per_category(records: list[dict[str, Any]], limit_per_category: int) -> pd.DataFrame:
    if not records:
        return empty_news_frame()
    deduped = dedupe_articles(pd.DataFrame.from_records(records))
    return (
        deduped.sort_values("published_at", ascending=False)
        .groupby("category", as_index=False)
        .head(limit_per_category)
        .reset_index(drop=True)
    )


def _match_category_for_alpha_item(item: dict[str, Any], categories: list[dict[str, Any]]) -> dict[str, Any] | None:
    haystack = " ".join(
        str(value or "")
        for value in [
            item.get("title"),
            item.get("summary"),
            item.get("source"),
            " ".join(
                topic.get("topic", "")
                for topic in item.get("topics", [])
                if isinstance(topic, dict)
            ),
        ]
    ).lower()
    for category in categories:
        keywords = category.get("query_keywords") or [category.get("name"), category.get("id"), category.get("group")]
        if any(str(keyword).lower() in haystack for keyword in keywords if keyword):
            return category
    return None


def _alpha_topic_for_category(category: dict[str, Any]) -> str:
    group = str(category.get("group") or "").lower()
    category_id = str(category.get("id") or "").lower()
    text = f"{group} {category_id}"
    if "crypto" in text or "blockchain" in text:
        return "blockchain"
    if "earnings" in text:
        return "earnings"
    if "ipo" in text:
        return "ipo"
    if "mna" in text or "merger" in text or "acquisition" in text:
        return "mergers_and_acquisitions"
    if "monetary" in text or "fed" in text or "rate" in text:
        return "economy_monetary"
    if "fiscal" in text or "shutdown" in text or "debt_ceiling" in text:
        return "economy_fiscal"
    if "macro" in text or "inflation" in text or "labor" in text or "gdp" in text:
        return "economy_macro"
    if "energy" in text or "oil" in text or "transportation" in text:
        return "energy_transportation"
    if "bank" in text or "credit" in text or "finance" in text:
        return "finance"
    if "manufacturing" in text or "semiconductor" in text or "technology" in text or "ai_" in text:
        return "technology"
    if "retail" in text or "consumer" in text:
        return "retail_wholesale"
    if "real_estate" in text:
        return "real_estate"
    return "financial_markets"


def _alpha_related_tickers(item: dict[str, Any], requested_tickers: list[str]) -> list[str]:
    ticker_sentiment = item.get("ticker_sentiment") or []
    values = [
        str(row.get("ticker", "")).upper().strip()
        for row in ticker_sentiment
        if isinstance(row, dict) and row.get("ticker")
    ]
    if not values:
        values = [ticker.upper().strip() for ticker in requested_tickers]
    return sorted(set(item for item in values if item))
