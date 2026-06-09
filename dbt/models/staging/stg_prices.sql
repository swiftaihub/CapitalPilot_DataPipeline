{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'prices']
) }}

with source as (

    select *
    from {{ source('raw', 'raw_prices') }}

),

cleaned as (

    select
        upper(trim(ticker)) as ticker,
        cast(date as date) as date,
        cast(open as double) as open,
        cast(high as double) as high,
        cast(low as double) as low,
        cast(close as double) as close,
        cast(adj_close as double) as adj_close,
        cast(volume as double) as volume,
        cast(market_cap as double) as market_cap,
        source,
        cast(updated_at as timestamp) as updated_at
    from source
    where ticker is not null
      and date is not null

)

select *
from cleaned
