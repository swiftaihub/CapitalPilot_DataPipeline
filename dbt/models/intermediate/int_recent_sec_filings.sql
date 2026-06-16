{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'sec']
) }}

select
    *,
    date_diff('day', filing_date, current_date) as days_since_filing,
    row_number() over (
        partition by ticker
        order by filing_date desc nulls last, acceptance_datetime desc nulls last
    ) as filing_recency_rank
from {{ ref('stg_sec_filings') }}
where filing_date >= current_date - interval '365 days'

