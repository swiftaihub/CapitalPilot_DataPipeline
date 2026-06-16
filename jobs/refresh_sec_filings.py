"""Refresh SEC filing metadata and optional filing documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import load_sec_forms_config, load_watchlist
from src.db import (
    upsert_raw_sec_company_tickers,
    upsert_raw_sec_filing_documents,
    upsert_raw_sec_filings,
)
from src.pipeline_logging import finish_run, finish_task, log_error, start_run, start_task
from src.sec_client import SECClient, build_document_record, parse_recent_filings, ticker_cik_lookup


def parse_args() -> argparse.Namespace:
    config = load_sec_forms_config()
    parser = argparse.ArgumentParser(description="Refresh SEC filings for watchlist tickers.")
    parser.add_argument("--target", choices=["local", "motherduck"], default=None)
    parser.add_argument("--forms", default=",".join(config.get("default_forms", ["10-K", "10-Q", "8-K"])))
    parser.add_argument("--days-back", type=int, default=config.get("recent_filings", {}).get("days_back", 365))
    parser.add_argument("--tickers", default=None)
    parser.add_argument("--download-documents", action="store_true", default=False)
    parser.add_argument(
        "--max-filings-per-ticker",
        type=int,
        default=config.get("recent_filings", {}).get("max_filings_per_ticker", 20),
    )
    return parser.parse_args()


def _tickers_from_args(value: str | None) -> list[str]:
    if value:
        return sorted({item.upper().strip() for item in value.split(",") if item.strip()})
    tickers: list[str] = []
    for item in load_watchlist():
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            tickers.append(str(ticker).upper().strip())
    return sorted(set(tickers))


def _forms_from_arg(value: str) -> list[str]:
    return [item.upper().strip() for item in value.split(",") if item.strip()]


def main() -> int:
    args = parse_args()
    run_id = start_run(
        "refresh_sec_filings",
        target=args.target,
        metadata={
            "forms": args.forms,
            "days_back": args.days_back,
            "download_documents": args.download_documents,
        },
    )
    task_id = start_task(run_id, "sec_filings", target=args.target)
    try:
        forms = _forms_from_arg(args.forms)
        tickers = _tickers_from_args(args.tickers)
        config = load_sec_forms_config().get("fair_access", {})
        client = SECClient(
            timeout_seconds=int(config.get("timeout_seconds", 30)),
            max_retries=int(config.get("max_retries", 3)),
            rate_limit_seconds=float(config.get("min_request_interval_seconds", 0.12)),
        )

        print("Fetching SEC ticker-to-CIK mapping")
        company_tickers = client.fetch_company_tickers()
        upserted_companies = upsert_raw_sec_company_tickers(company_tickers, target=args.target)
        lookup = ticker_cik_lookup(company_tickers)

        filing_frames: list[pd.DataFrame] = []
        for ticker in tickers:
            cik = lookup.get(ticker)
            if not cik:
                message = f"No SEC CIK mapping found for {ticker}; skipping."
                print(f"Warning: {message}")
                log_error(run_id=run_id, task_name="sec_filings", error=message, target=args.target, context={"ticker": ticker})
                continue
            try:
                print(f"Fetching SEC submissions for {ticker} ({cik})")
                payload = client.fetch_submissions(cik)
                filings = parse_recent_filings(
                    payload,
                    ticker=ticker,
                    cik=cik,
                    forms=forms,
                    days_back=args.days_back,
                    max_filings=args.max_filings_per_ticker,
                )
                filing_frames.append(filings)
            except Exception as exc:
                print(f"Warning: failed to fetch SEC submissions for {ticker}: {exc}")
                log_error(run_id=run_id, task_name="sec_filings", error=exc, target=args.target, context={"ticker": ticker})

        filings_df = pd.concat(filing_frames, ignore_index=True) if filing_frames else pd.DataFrame()
        upserted_filings = upsert_raw_sec_filings(filings_df, target=args.target)
        upserted_documents = 0

        if args.download_documents and not filings_df.empty:
            document_records = []
            for filing in filings_df.to_dict("records"):
                try:
                    text, content_type = client.download_filing_document(str(filing["document_url"]))
                    document_records.append(
                        build_document_record(
                            filing,
                            document_text=text,
                            content_type=content_type,
                            download_status="completed",
                        )
                    )
                except Exception as exc:
                    print(f"Warning: failed to download SEC document {filing.get('document_url')}: {exc}")
                    log_error(
                        run_id=run_id,
                        task_name="sec_filing_documents",
                        error=exc,
                        target=args.target,
                        context={"accession_number": filing.get("accession_number"), "url": filing.get("document_url")},
                    )
                    document_records.append(
                        build_document_record(
                            filing,
                            document_text=None,
                            content_type=None,
                            download_status="failed",
                            error_message=str(exc),
                        )
                    )
            documents_df = pd.DataFrame.from_records(document_records)
            upserted_documents = upsert_raw_sec_filing_documents(documents_df, target=args.target)

        row_count = upserted_companies + upserted_filings + upserted_documents
        finish_task(
            task_id,
            status="success",
            target=args.target,
            row_count=row_count,
            metadata={
                "company_tickers": upserted_companies,
                "filings": upserted_filings,
                "documents": upserted_documents,
            },
        )
        finish_run(run_id, status="success", target=args.target)
        print(f"Upserted {upserted_filings} SEC filing rows and {upserted_documents} document rows.")
        return 0
    except Exception as exc:
        log_error(run_id=run_id, task_name="sec_filings", error=exc, target=args.target)
        finish_task(task_id, status="failed", target=args.target, error_message=str(exc))
        finish_run(run_id, status="failed", target=args.target)
        print(f"SEC refresh failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
