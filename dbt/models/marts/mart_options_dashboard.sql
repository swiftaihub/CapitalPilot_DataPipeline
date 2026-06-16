{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'options']
) }}

with ranked as (

    select
        *,
        row_number() over (
            partition by ticker, expiration_date, option_type, strike
            order by as_of_date desc
        ) as rn
    from {{ ref('int_options_features') }}

)

select
    ticker,
    as_of_date,
    expiration_date,
    days_to_expiration,
    option_type,
    strike,
    last_price,
    bid,
    ask,
    calculated_mid as mid,
    volume,
    open_interest,
    implied_volatility,
    in_the_money,
    source,
    updated_at,
    is_investment_advice
from ranked
where rn = 1
order by ticker, expiration_date, option_type, strike

