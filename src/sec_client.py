"""SEC EDGAR client helpers for filings and company metadata."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import pandas as pd
import requests

from src.config import get_secret

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def normalize_cik(cik: str | int) -> str:
    """Return a 10-digit SEC CIK."""
    return str(cik).strip().lstrip("0").zfill(10)


def archive_document_url(cik: str | int, accession_number: str, primary_document: str) -> str:
    """Build a filing primary-document URL from CIK, accession number, and document name."""
    cik_int = int(normalize_cik(cik))
    accession_no_dashes = str(accession_number).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primary_document}"


def archive_detail_url(cik: str | int, accession_number: str) -> str:
    """Build a filing archive detail directory URL."""
    cik_int = int(normalize_cik(cik))
    accession_no_dashes = str(accession_number).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/"


def validate_user_agent(user_agent: str | None) -> str:
    """Validate the SEC-required user agent string."""
    value = (user_agent or "").strip()
    lowered = value.lower()
    if not value:
        raise ValueError("SEC_USER_AGENT is required for SEC EDGAR requests.")
    if "your_email" in lowered or "example.com" in lowered:
        raise ValueError("SEC_USER_AGENT must include a real project/contact string, not a placeholder.")
    if len(value) < 12:
        raise ValueError("SEC_USER_AGENT is too short; include project name and contact email or URL.")
    return value


@dataclass(frozen=True)
class SECClientConfig:
    user_agent: str
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_seconds: float = 0.12


class SECClient:
    """Small SEC client with safe retry, timeout, and rate limiting."""

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        rate_limit_seconds: float = 0.12,
        session: requests.Session | None = None,
    ) -> None:
        self.config = SECClientConfig(
            user_agent=validate_user_agent(user_agent or get_secret("SEC_USER_AGENT")),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            rate_limit_seconds=rate_limit_seconds,
        )
        self.session = session or requests.Session()
        self._last_request_at = 0.0

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.config.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "",
        }

    def _headers_for_url(self, url: str) -> dict[str, str]:
        headers = dict(self.headers)
        if "data.sec.gov" in url:
            headers["Host"] = "data.sec.gov"
        else:
            headers["Host"] = "www.sec.gov"
        return headers

    def _sleep_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.config.rate_limit_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            self._sleep_for_rate_limit()
            self._last_request_at = time.monotonic()
            try:
                response = self.session.get(
                    url,
                    headers=self._headers_for_url(url),
                    timeout=self.config.timeout_seconds,
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.config.max_retries - 1:
                    time.sleep(1.0 + attempt)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.config.max_retries - 1:
                    time.sleep(1.0 + attempt)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError(f"Unable to fetch SEC URL: {url}")

    def get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON from SEC."""
        return self._get(url).json()

    def get_text(self, url: str) -> tuple[str, str | None]:
        """Fetch text content from SEC and return text plus content type."""
        response = self._get(url)
        return response.text, response.headers.get("content-type")

    def fetch_company_tickers(self) -> pd.DataFrame:
        """Fetch and normalize SEC ticker-to-CIK mapping."""
        return parse_company_tickers(self.get_json(SEC_COMPANY_TICKERS_URL))

    def fetch_submissions(self, cik: str | int) -> dict[str, Any]:
        """Fetch a company submissions payload."""
        return self.get_json(SEC_SUBMISSIONS_URL.format(cik=normalize_cik(cik)))

    def fetch_companyfacts(self, cik: str | int) -> dict[str, Any]:
        """Fetch a company facts payload for future fundamentals work."""
        return self.get_json(SEC_COMPANYFACTS_URL.format(cik=normalize_cik(cik)))

    def download_filing_document(self, document_url: str) -> tuple[str, str | None]:
        """Download a filing primary document."""
        return self.get_text(document_url)


def parse_company_tickers(payload: dict[str, Any]) -> pd.DataFrame:
    """Parse SEC company_tickers.json into a dataframe."""
    rows: list[dict[str, Any]] = []
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in payload.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        cik = item.get("cik_str")
        if not ticker or cik is None:
            continue
        rows.append(
            {
                "ticker": ticker,
                "cik": normalize_cik(cik),
                "title": item.get("title"),
                "source": "SEC company_tickers.json",
                "raw_payload_json": json.dumps(item, sort_keys=True),
                "updated_at": updated_at,
            }
        )
    return pd.DataFrame.from_records(
        rows,
        columns=["ticker", "cik", "title", "source", "raw_payload_json", "updated_at"],
    )


def ticker_cik_lookup(company_tickers: pd.DataFrame) -> dict[str, str]:
    """Return a ticker-to-CIK lookup from parsed company ticker rows."""
    if company_tickers.empty:
        return {}
    frame = company_tickers.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["cik"] = frame["cik"].astype(str).map(normalize_cik)
    return dict(zip(frame["ticker"], frame["cik"], strict=False))


def _parse_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def parse_recent_filings(
    payload: dict[str, Any],
    *,
    ticker: str,
    cik: str | int,
    forms: Iterable[str],
    days_back: int | None = None,
    max_filings: int | None = None,
) -> pd.DataFrame:
    """Parse SEC submissions recent-filings arrays into one row per filing."""
    accepted_forms = {form.upper().strip() for form in forms}
    cutoff = None
    if days_back is not None:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=int(days_back))

    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return pd.DataFrame()
    forms_array = recent.get("form", []) or []
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    normalized_ticker = ticker.upper().strip()
    normalized_cik = normalize_cik(cik)

    rows: list[dict[str, Any]] = []
    for index, form in enumerate(forms_array):
        form_type = str(form or "").upper().strip()
        if form_type not in accepted_forms:
            continue

        accession_number = _array_value(recent, "accessionNumber", index)
        primary_document = _array_value(recent, "primaryDocument", index)
        filing_date = _parse_date(_array_value(recent, "filingDate", index))
        if accession_number in {None, ""} or primary_document in {None, ""}:
            continue
        if cutoff is not None and filing_date is not None and filing_date < cutoff:
            continue

        raw_row = {key: _array_value(recent, key, index) for key in recent}
        document_url = archive_document_url(normalized_cik, str(accession_number), str(primary_document))
        rows.append(
            {
                "ticker": normalized_ticker,
                "cik": normalized_cik,
                "accession_number": accession_number,
                "form_type": form_type,
                "filing_date": filing_date,
                "report_date": _parse_date(_array_value(recent, "reportDate", index)),
                "acceptance_datetime": _array_value(recent, "acceptanceDateTime", index),
                "primary_document": primary_document,
                "filing_detail_url": archive_detail_url(normalized_cik, str(accession_number)),
                "document_url": document_url,
                "document_text": None,
                "source": "SEC submissions API",
                "raw_payload_json": json.dumps(raw_row, default=str, sort_keys=True),
                "updated_at": updated_at,
            }
        )
        if max_filings is not None and len(rows) >= max_filings:
            break

    return pd.DataFrame.from_records(
        rows,
        columns=[
            "ticker",
            "cik",
            "accession_number",
            "form_type",
            "filing_date",
            "report_date",
            "acceptance_datetime",
            "primary_document",
            "filing_detail_url",
            "document_url",
            "document_text",
            "source",
            "raw_payload_json",
            "updated_at",
        ],
    )


def _array_value(container: dict[str, Any], key: str, index: int) -> Any:
    values = container.get(key, [])
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def build_document_record(
    filing: dict[str, Any],
    *,
    document_text: str | None,
    content_type: str | None,
    download_status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build a raw_sec_filing_documents row from a filing row and download result."""
    return {
        "ticker": filing.get("ticker"),
        "cik": filing.get("cik"),
        "accession_number": filing.get("accession_number"),
        "form_type": filing.get("form_type"),
        "filing_date": filing.get("filing_date"),
        "primary_document": filing.get("primary_document"),
        "document_url": filing.get("document_url"),
        "document_text": document_text,
        "content_type": content_type,
        "download_status": download_status,
        "error_message": error_message,
        "source": "SEC filing archive",
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
