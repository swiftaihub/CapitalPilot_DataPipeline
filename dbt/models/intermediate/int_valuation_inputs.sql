{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'valuation']
) }}

with prices as (

    select *
    from {{ ref('stg_prices') }}

),

latest_prices as (

    select
        ticker,
        date,
        close,
        adj_close,
        market_cap,
        volume,
        row_number() over (
            partition by ticker
            order by date desc
        ) as rn
    from prices

),

final as (

    select
        ticker,
        date,
        close as price,
        adj_close,
        market_cap,
        volume
    from latest_prices
    where rn = 1

)

select *
from final
