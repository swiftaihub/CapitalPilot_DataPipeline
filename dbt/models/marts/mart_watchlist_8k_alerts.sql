{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'sec', 'alerts']
) }}

select
    ticker,
    cik,
    accession_number,
    form_type,
    filing_date,
    report_date,
    acceptance_datetime,
    primary_document,
    filing_detail_url,
    document_url,
    days_since_filing,
    alert_freshness,
    '8-K filing alert for watchlist research review' as alert_label,
    false as is_investment_advice
from {{ ref('int_watchlist_recent_8k') }}
order by filing_date desc nulls last, ticker

