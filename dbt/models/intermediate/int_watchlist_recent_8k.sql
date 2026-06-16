{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'sec', 'alerts']
) }}

select
    *,
    case
        when days_since_filing <= 7 then 'fresh'
        when days_since_filing <= 30 then 'recent'
        else 'stale'
    end as alert_freshness
from {{ ref('int_recent_sec_filings') }}
where form_type = '8-K'
  and filing_date >= current_date - interval '30 days'

