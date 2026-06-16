{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'political']
) }}

with watchlist_proxy as (

    select distinct ticker
    from {{ ref('stg_prices') }}

),

base as (

    select *
    from {{ ref('stg_political_transactions') }}

)

select
    base.*,
    case
        when transaction_type in ('purchase', 'buy') then 'buy'
        when transaction_type in ('sale', 'sell') then 'sell'
        else 'other_or_unknown'
    end as transaction_direction,
    case
        when amount_min is not null and amount_max is not null and amount_min <> amount_max then true
        when amount_min is null or amount_max is null then true
        else false
    end as amount_is_range_or_uncertain,
    watchlist_proxy.ticker is not null as overlaps_watchlist
from base
left join watchlist_proxy
  on base.ticker = watchlist_proxy.ticker

