"""Public political and official disclosure ingestion helpers."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from xml.etree import ElementTree

import pandas as pd
import requests

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - dependency availability is checked by tests/imports
    PdfReader = None

from src.config import ROOT_DIR, load_officials_watchlist_config

HOUSE_FD_XML_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.xml"
HOUSE_PTR_PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"


class PoliticalDisclosureClient(Protocol):
    """Disclosure provider interface."""

    name: str

    def fetch(
        self,
        *,
        days_back: int | None = None,
        officials: list[str] | None = None,
        max_reports: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return report rows and transaction rows."""


def normalize_transaction_type(value: Any) -> str | None:
    """Normalize disclosure transaction types without implying trading advice."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    code = text.split()[0].strip("()")
    if code == "p":
        return "purchase"
    if code == "s":
        return "sale"
    if code == "e":
        return "exchange"
    if any(token in text for token in ["purchase", "buy", "bought"]):
        return "purchase"
    if any(token in text for token in ["sale", "sell", "sold"]):
        return "sale"
    if "exchange" in text:
        return "exchange"
    if "gift" in text:
        return "gift"
    return text.replace(" ", "_")


def parse_amount_range(value: Any) -> tuple[float | None, float | None]:
    """Parse STOCK Act style value ranges while preserving uncertainty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    lowered = text.lower()
    numbers = [float(item.replace(",", "")) for item in re.findall(r"\$?\s*([0-9][0-9,]*(?:\.\d+)?)", text)]
    if "over" in lowered and numbers:
        return numbers[0], None
    if any(token in lowered for token in ["less than", "under", "up to"]) and numbers:
        return None, numbers[0]
    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1])
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return None, None


@dataclass
class ManualCSVPoliticalDisclosureClient:
    """Load public-official transactions from a manually curated CSV file or directory."""

    path: Path
    name: str = "manual"

    def fetch(
        self,
        *,
        days_back: int | None = None,
        officials: list[str] | None = None,
        max_reports: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        files = [self.path] if self.path.is_file() else sorted(self.path.glob("*.csv")) if self.path.exists() else []
        frames: list[pd.DataFrame] = []
        for file_path in files:
            frame = pd.read_csv(file_path)
            frame["source_file"] = str(file_path)
            frames.append(frame)
        if not frames:
            return empty_reports_frame(), empty_transactions_frame()

        raw = pd.concat(frames, ignore_index=True)
        validate_manual_disclosure_columns(raw)
        selected_officials = {item.lower().strip() for item in officials or [] if item.strip()}
        if selected_officials:
            raw = raw[raw["official_name"].astype(str).str.lower().str.strip().isin(selected_officials)]

        if days_back is not None and "filing_date" in raw.columns:
            cutoff = pd.Timestamp.utcnow().date() - pd.Timedelta(days=int(days_back)).to_pytimedelta()
            filing_dates = pd.to_datetime(raw["filing_date"], errors="coerce").dt.date
            raw = raw[(filing_dates.isna()) | (filing_dates >= cutoff)]

        transactions = [_transaction_record(row) for row in raw.to_dict("records")]
        reports = _report_records(raw)
        return (
            pd.DataFrame.from_records(reports, columns=empty_reports_frame().columns),
            pd.DataFrame.from_records(transactions, columns=empty_transactions_frame().columns),
        )


@dataclass
class HouseDisclosureClient:
    """Automated House Clerk Periodic Transaction Report ingestion."""

    timeout_seconds: int = 30
    name: str = "house"

    def fetch(
        self,
        *,
        days_back: int | None = None,
        officials: list[str] | None = None,
        max_reports: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        selected_officials = {item.lower().strip() for item in officials or [] if item.strip()}
        years = _years_for_days_back(days_back)
        report_records: list[dict[str, Any]] = []
        transaction_records: list[dict[str, Any]] = []

        for year in years:
            reports = fetch_house_ptr_report_index(year, timeout_seconds=self.timeout_seconds)
            if days_back is not None and not reports.empty:
                cutoff = pd.Timestamp.utcnow().date() - pd.Timedelta(days=int(days_back)).to_pytimedelta()
                filing_dates = pd.to_datetime(reports["filing_date"], errors="coerce").dt.date
                reports = reports[(filing_dates.isna()) | (filing_dates >= cutoff)]
            if selected_officials and not reports.empty:
                reports = reports[
                    reports["official_name"].astype(str).str.lower().str.strip().isin(selected_officials)
                ]
            if max_reports is not None and max_reports > 0:
                remaining = max_reports - len(report_records)
                if remaining <= 0:
                    break
                reports = reports.head(remaining)

            for report in reports.to_dict("records"):
                report_records.append(report)
                try:
                    pdf_text = fetch_pdf_text(str(report["source_pdf_url"]), timeout_seconds=self.timeout_seconds)
                    parsed_transactions = parse_house_ptr_pdf_text(
                        pdf_text,
                        report=report,
                    )
                    transaction_records.extend(parsed_transactions)
                except Exception as exc:
                    transaction_records.append(_failed_pdf_transaction_placeholder(report, exc))

        return (
            pd.DataFrame.from_records(report_records, columns=empty_reports_frame().columns),
            pd.DataFrame.from_records(transaction_records, columns=empty_transactions_frame().columns),
        )


@dataclass
class ScaffoldDisclosureClient:
    """Documented placeholder for official live disclosure sources."""

    name: str

    def fetch(
        self,
        *,
        days_back: int | None = None,
        officials: list[str] | None = None,
        max_reports: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return empty_reports_frame(), empty_transactions_frame()


def provider_for_source(source: str, *, manual_file: str | None = None) -> PoliticalDisclosureClient:
    """Return a disclosure provider for the requested source."""
    normalized = source.lower().strip()
    if normalized == "manual":
        return ManualCSVPoliticalDisclosureClient(path=Path(manual_file) if manual_file else _default_manual_path())
    if normalized == "house":
        return HouseDisclosureClient()
    if normalized in {"senate", "oge"}:
        return ScaffoldDisclosureClient(name=normalized)
    raise ValueError(f"Unsupported political disclosure source: {source}")


def fetch_house_ptr_report_index(year: int, *, timeout_seconds: int = 30) -> pd.DataFrame:
    """Fetch House Clerk yearly XML index and return Periodic Transaction Reports."""
    url = HOUSE_FD_XML_URL.format(year=year)
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return parse_house_fd_xml(response.content, source_url=url)


def parse_house_fd_xml(xml_content: bytes | str, *, source_url: str | None = None) -> pd.DataFrame:
    """Parse House yearly financial-disclosure XML into PTR report metadata rows."""
    if isinstance(xml_content, bytes):
        text = xml_content.decode("utf-8-sig")
    else:
        text = xml_content.lstrip("\ufeff")
    root = ElementTree.fromstring(text)
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rows: list[dict[str, Any]] = []
    for member in root.findall("Member"):
        filing_type = _text(member, "FilingType").upper()
        if filing_type != "P":
            continue
        year_text = _text(member, "Year")
        doc_id = _text(member, "DocID")
        if not year_text or not doc_id:
            continue
        year = int(year_text)
        first = _text(member, "First")
        last = _text(member, "Last")
        suffix = _text(member, "Suffix")
        official_name = " ".join(part for part in [first, last, suffix] if part).strip()
        state_dst = _text(member, "StateDst")
        state = state_dst[:2] if state_dst else None
        pdf_url = HOUSE_PTR_PDF_URL.format(year=year, doc_id=doc_id)
        report_id = f"house-{year}-{doc_id}"
        raw_payload = {child.tag: child.text for child in member}
        rows.append(
            {
                "report_id": report_id,
                "official_name": official_name,
                "role": "Representative",
                "branch": "house",
                "chamber": "House",
                "party": None,
                "state": state,
                "report_type": "periodic_transaction_report",
                "report_date": None,
                "filing_date": _text(member, "FilingDate"),
                "source_url": source_url,
                "source_pdf_url": pdf_url,
                "raw_payload_json": json.dumps(raw_payload, default=str, sort_keys=True),
                "updated_at": updated_at,
            }
        )
    return pd.DataFrame.from_records(rows, columns=empty_reports_frame().columns)


def fetch_pdf_text(url: str, *, timeout_seconds: int = 30) -> str:
    """Download a PDF and extract text with pypdf."""
    if PdfReader is None:
        raise RuntimeError("pypdf is required for automated House PTR PDF parsing.")
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_house_ptr_pdf_text(text: str, *, report: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort parser for House PTR PDF text extracted by pypdf."""
    cleaned = _clean_pdf_text(text)
    pattern = re.compile(
        r"(?P<asset>.+?)\s+\((?P<ticker>[A-Z][A-Z0-9.\-/]{0,9})\)\s+\[(?P<asset_code>[A-Z]{2})\]\s+"
        r"(?P<transaction_type>[SPES]\s*(?:\([^)]+\))?)\s+"
        r"(?P<transaction_date>\d{2}/\d{2}/\d{4})\s*"
        r"(?P<notification_date>\d{2}/\d{2}/\d{4})?\s*"
        r"(?P<amount>\$[0-9,]+(?:\s*-\s*\$[0-9,]+)?|Over\s+\$[0-9,]+|None)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(cleaned):
        asset_name = _clean_asset_name(match.group("asset"))
        ticker = match.group("ticker").replace("/", ".").upper()
        amount_text = match.group("amount")
        amount_min, amount_max = parse_amount_range(amount_text)
        raw_payload = {
            "asset_text": asset_name,
            "asset_code": match.group("asset_code"),
            "raw_match": match.group(0),
            "source_parser": "house_ptr_pdf_text_v1",
        }
        row = {
            "official_name": report.get("official_name"),
            "role": report.get("role"),
            "branch": "house",
            "chamber": "House",
            "party": report.get("party"),
            "state": report.get("state"),
            "ticker": ticker,
            "asset_name": asset_name,
            "asset_type": _house_asset_type(match.group("asset_code")),
            "transaction_type": normalize_transaction_type(match.group("transaction_type")),
            "transaction_date": _date_from_house(match.group("transaction_date")),
            "notification_date": _date_from_house(match.group("notification_date")),
            "filing_date": report.get("filing_date"),
            "amount_min": amount_min,
            "amount_max": amount_max,
            "amount_text": amount_text,
            "owner": None,
            "source_report_id": report.get("report_id"),
            "source_url": report.get("source_url"),
            "source_pdf_url": report.get("source_pdf_url"),
            "raw_payload_json": json.dumps(raw_payload, default=str, sort_keys=True),
            "confidence_score": 0.72,
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        row["transaction_id"] = _stable_id(
            [
                row["source_report_id"],
                row["official_name"],
                row["ticker"],
                row["transaction_type"],
                row["transaction_date"],
                row["amount_text"],
                row["asset_name"],
            ]
        )
        rows.append(row)
    return rows


def validate_manual_disclosure_columns(df: pd.DataFrame) -> None:
    """Validate the manual CSV schema."""
    config = load_officials_watchlist_config()
    required = config.get("manual_ingestion", {}).get(
        "required_columns",
        [
            "official_name",
            "role",
            "branch",
            "transaction_date",
            "transaction_type",
            "asset_name",
            "amount_text",
            "source_url",
        ],
    )
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Manual political disclosure CSV is missing columns: {', '.join(missing)}")


def empty_reports_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "report_id",
            "official_name",
            "role",
            "branch",
            "chamber",
            "party",
            "state",
            "report_type",
            "report_date",
            "filing_date",
            "source_url",
            "source_pdf_url",
            "raw_payload_json",
            "updated_at",
        ]
    )


def empty_transactions_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "transaction_id",
            "official_name",
            "role",
            "branch",
            "chamber",
            "party",
            "state",
            "ticker",
            "asset_name",
            "asset_type",
            "transaction_type",
            "transaction_date",
            "notification_date",
            "filing_date",
            "amount_min",
            "amount_max",
            "amount_text",
            "owner",
            "source_report_id",
            "source_url",
            "source_pdf_url",
            "raw_payload_json",
            "confidence_score",
            "updated_at",
        ]
    )


def _default_manual_path() -> Path:
    config = load_officials_watchlist_config()
    default_path = config.get("manual_ingestion", {}).get("default_path", "data/manual/official_trades")
    path = Path(default_path)
    return path if path.is_absolute() else ROOT_DIR / path


def _years_for_days_back(days_back: int | None) -> list[int]:
    today = pd.Timestamp.utcnow().date()
    if days_back is None:
        return [today.year]
    cutoff = today - pd.Timedelta(days=int(days_back)).to_pytimedelta()
    return list(range(today.year, cutoff.year - 1, -1))


def _text(element: ElementTree.Element, tag: str) -> str:
    value = element.findtext(tag)
    return "" if value is None else str(value).strip()


def _clean_pdf_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n+", "\n", cleaned)
    return cleaned


def _clean_asset_name(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    markers = [
        "ID Owner Asset Transaction Type Date Notification Date Amount Cap. Gains > $200?",
        "Filing ID #",
    ]
    for marker in markers:
        if marker in text:
            text = text.split(marker)[-1].strip()
    return text[-300:].strip()


def _house_asset_type(asset_code: str | None) -> str | None:
    mapping = {
        "ST": "stock",
        "OT": "other_securities",
        "OP": "option",
        "MF": "mutual_fund",
        "EF": "exchange_traded_fund",
        "BO": "bond",
    }
    if not asset_code:
        return None
    return mapping.get(asset_code.upper().strip(), asset_code.upper().strip())


def _date_from_house(value: str | None) -> str | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, format="%m/%d/%Y", errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _failed_pdf_transaction_placeholder(report: dict[str, Any], error: BaseException) -> dict[str, Any]:
    raw_payload = {
        "source_parser": "house_ptr_pdf_text_v1",
        "parse_status": "failed",
        "error": str(error),
    }
    transaction_id = _stable_id([report.get("report_id"), "pdf_parse_failed"])
    return {
        "transaction_id": transaction_id,
        "official_name": report.get("official_name"),
        "role": report.get("role"),
        "branch": "house",
        "chamber": "House",
        "party": report.get("party"),
        "state": report.get("state"),
        "ticker": None,
        "asset_name": "House PTR PDF parse failed",
        "asset_type": None,
        "transaction_type": "unknown",
        "transaction_date": None,
        "notification_date": None,
        "filing_date": report.get("filing_date"),
        "amount_min": None,
        "amount_max": None,
        "amount_text": None,
        "owner": None,
        "source_report_id": report.get("report_id"),
        "source_url": report.get("source_url"),
        "source_pdf_url": report.get("source_pdf_url"),
        "raw_payload_json": json.dumps(raw_payload, default=str, sort_keys=True),
        "confidence_score": 0.0,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def _transaction_record(row: dict[str, Any]) -> dict[str, Any]:
    amount_min, amount_max = parse_amount_range(row.get("amount_text"))
    report_id = _report_id(row)
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {key: _jsonable(value) for key, value in row.items()}
    transaction_id = row.get("transaction_id") or _stable_id(
        [
            row.get("official_name"),
            row.get("transaction_date"),
            row.get("transaction_type"),
            row.get("ticker"),
            row.get("asset_name"),
            row.get("amount_text"),
            report_id,
        ]
    )
    return {
        "transaction_id": transaction_id,
        "official_name": row.get("official_name"),
        "role": row.get("role"),
        "branch": row.get("branch"),
        "chamber": row.get("chamber"),
        "party": row.get("party"),
        "state": row.get("state"),
        "ticker": _nullable_upper(row.get("ticker")),
        "asset_name": row.get("asset_name"),
        "asset_type": row.get("asset_type"),
        "transaction_type": normalize_transaction_type(row.get("transaction_type")),
        "transaction_date": row.get("transaction_date"),
        "notification_date": row.get("notification_date"),
        "filing_date": row.get("filing_date"),
        "amount_min": amount_min,
        "amount_max": amount_max,
        "amount_text": row.get("amount_text"),
        "owner": row.get("owner"),
        "source_report_id": report_id,
        "source_url": row.get("source_url"),
        "source_pdf_url": row.get("source_pdf_url"),
        "raw_payload_json": json.dumps(payload, default=str, sort_keys=True),
        "confidence_score": float(row.get("confidence_score", 0.8) or 0.8),
        "updated_at": updated_at,
    }


def _report_records(raw: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, group in raw.groupby(raw.apply(_report_id, axis=1)):
        first = group.iloc[0].to_dict()
        rows.append(
            {
                "report_id": _report_id(first),
                "official_name": first.get("official_name"),
                "role": first.get("role"),
                "branch": first.get("branch"),
                "chamber": first.get("chamber"),
                "party": first.get("party"),
                "state": first.get("state"),
                "report_type": first.get("report_type", "periodic_transaction_report"),
                "report_date": first.get("report_date"),
                "filing_date": first.get("filing_date"),
                "source_url": first.get("source_url"),
                "source_pdf_url": first.get("source_pdf_url"),
                "raw_payload_json": json.dumps(
                    {"transaction_count": len(group), "source": "manual_csv"},
                    sort_keys=True,
                ),
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
        )
    return rows


def _report_id(row: dict[str, Any] | pd.Series) -> str:
    explicit = row.get("source_report_id") if hasattr(row, "get") else None
    if explicit is not None and not (isinstance(explicit, float) and pd.isna(explicit)) and str(explicit).strip():
        return str(explicit).strip()
    return _stable_id([row.get("official_name"), row.get("filing_date"), row.get("source_url")])


def _stable_id(parts: list[Any]) -> str:
    key = "|".join("" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value) for value in parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _nullable_upper(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).upper().strip()
    return text or None


def _jsonable(value: Any) -> Any:
    if isinstance(value, float) and pd.isna(value):
        return None
    return value
