{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'options']
) }}

select
    *,
    date_diff('day', as_of_date, expiration_date) as days_to_expiration,
    case
        when bid is not null and ask is not null and ask >= bid then (bid + ask) / 2
        else mid
    end as calculated_mid,
    case
        when option_type = 'call' then greatest(0, coalesce(last_price, 0) - strike)
        when option_type = 'put' then greatest(0, strike - coalesce(last_price, 0))
    end as placeholder_intrinsic_value,
    false as is_investment_advice
from {{ ref('stg_options_chain') }}

