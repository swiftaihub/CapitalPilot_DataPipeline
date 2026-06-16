{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'political']
) }}

with trades as (

    select *
    from {{ ref('int_political_trades_normalized') }}

),

ownership as (

    select *
    from {{ ref('int_political_ticker_ownership') }}

)

select
    trades.transaction_id,
    trades.official_name,
    trades.role,
    trades.branch,
    trades.chamber,
    trades.party,
    trades.state,
    trades.ticker,
    trades.asset_name,
    trades.asset_type,
    trades.transaction_type,
    trades.transaction_direction,
    trades.transaction_date,
    trades.notification_date,
    trades.filing_date,
    trades.amount_min,
    trades.amount_max,
    trades.amount_text,
    trades.amount_is_range_or_uncertain,
    trades.owner,
    trades.source_report_id,
    trades.source_url,
    trades.source_pdf_url,
    trades.confidence_score,
    trades.overlaps_watchlist,
    ownership.official_count as ticker_official_count,
    ownership.senator_count as ticker_senator_count,
    ownership.executive_official_count as ticker_executive_official_count,
    ownership.latest_filing_date as ticker_latest_filing_date,
    'Disclosed values may be delayed, range-based, and incomplete.' as disclosure_note,
    false as is_investment_advice
from trades
left join ownership
  on trades.ticker = ownership.ticker
order by trades.filing_date desc nulls last, trades.transaction_date desc nulls last

