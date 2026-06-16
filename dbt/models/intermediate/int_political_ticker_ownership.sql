{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'political']
) }}

select
    ticker,
    count(*) as transaction_count,
    count(distinct official_name) as official_count,
    count(distinct case when branch = 'senate' then official_name end) as senator_count,
    count(distinct case when branch = 'house' then official_name end) as house_member_count,
    count(distinct case when branch = 'executive' then official_name end) as executive_official_count,
    max(filing_date) as latest_filing_date,
    min(amount_min) as disclosed_amount_min,
    max(amount_max) as disclosed_amount_max,
    bool_or(overlaps_watchlist) as overlaps_watchlist
from {{ ref('int_political_trades_normalized') }}
where ticker is not null
group by 1

