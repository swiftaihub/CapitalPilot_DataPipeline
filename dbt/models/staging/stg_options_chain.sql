{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'options']
) }}

select
    upper(trim(ticker)) as ticker,
    cast(as_of_date as date) as as_of_date,
    cast(expiration_date as date) as expiration_date,
    lower(trim(option_type)) as option_type,
    cast(strike as double) as strike,
    cast(last_price as double) as last_price,
    cast(bid as double) as bid,
    cast(ask as double) as ask,
    cast(mid as double) as mid,
    cast(volume as double) as volume,
    cast(open_interest as double) as open_interest,
    cast(implied_volatility as double) as implied_volatility,
    cast(in_the_money as boolean) as in_the_money,
    source,
    cast(updated_at as timestamp) as updated_at
from {{ source('raw', 'raw_options_chain') }}
where ticker is not null
  and as_of_date is not null
  and expiration_date is not null
  and lower(trim(option_type)) in ('call', 'put')
