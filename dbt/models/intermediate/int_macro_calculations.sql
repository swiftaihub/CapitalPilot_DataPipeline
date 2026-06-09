{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'macro']
) }}

with macro as (

    select *
    from {{ ref('stg_macro_observations') }}

),

pivoted as (

    select
        date,

        max(case when series_id in ('FEDFUNDS', 'EFFR') then value end) as fed_funds,
        max(case when series_id = 'DGS10' then value end) as ten_year,
        max(case when series_id = 'DGS2' then value end) as two_year,
        max(case when series_id = 'T10Y2Y' then value end) as ten_two_spread,
        max(case when series_id = 'CPIAUCSL' then value end) as cpi,
        max(case when series_id = 'UNRATE' then value end) as unemployment_rate,
        max(case when series_id = 'DTWEXBGS' then value end) as dollar_index,
        max(case when series_id = 'VIXCLS' then value end) as vix

    from macro
    group by 1

),

filled as (

    select
        date,

        last_value(fed_funds ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as fed_funds,

        last_value(ten_year ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as ten_year,

        last_value(two_year ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as two_year,

        last_value(ten_two_spread ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as ten_two_spread,

        last_value(cpi ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as cpi,

        last_value(unemployment_rate ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as unemployment_rate,

        last_value(dollar_index ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as dollar_index,

        last_value(vix ignore nulls) over (
            order by date rows between unbounded preceding and current row
        ) as vix

    from pivoted

),

calculated as (

    select
        date,
        fed_funds,
        ten_year,
        two_year,
        ten_two_spread,
        cpi,
        unemployment_rate,
        dollar_index,
        vix,

        case
            when lag(cpi, 252) over (order by date) is not null
            then cpi / lag(cpi, 252) over (order by date) - 1
        end as cpi_yoy,

        fed_funds - lag(fed_funds, 63) over (order by date) as fed_funds_3m_change,
        unemployment_rate - lag(unemployment_rate, 63) over (order by date) as unemployment_3m_change,

        case
            when lag(dollar_index, 63) over (order by date) is not null
            then dollar_index / lag(dollar_index, 63) over (order by date) - 1
        end as dollar_3m_change_pct

    from filled

),

final as (

    select
        *,
        cpi_yoy - lag(cpi_yoy, 63) over (order by date) as cpi_yoy_3m_change
    from calculated

)

select *
from final
