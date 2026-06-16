{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'sec']
) }}

with filings as (

    select *
    from {{ ref('stg_sec_filings') }}

),

counts as (

    select
        ticker,
        count(*) as filing_count,
        max(filing_date) as latest_filing_date,
        count(*) filter (where form_type = '10-K') as ten_k_count,
        count(*) filter (where form_type = '10-Q') as ten_q_count,
        count(*) filter (where form_type = '8-K') as eight_k_count
    from filings
    group by 1

),

latest as (

    select
        *,
        row_number() over (
            partition by ticker
            order by filing_date desc nulls last, acceptance_datetime desc nulls last
        ) as rn
    from filings

)

select
    counts.ticker,
    counts.filing_count,
    counts.latest_filing_date,
    latest.form_type as latest_form_type,
    latest.accession_number as latest_accession_number,
    latest.document_url as latest_document_url,
    counts.ten_k_count,
    counts.ten_q_count,
    counts.eight_k_count,
    false as is_investment_advice
from counts
left join latest
  on counts.ticker = latest.ticker
 and latest.rn = 1

