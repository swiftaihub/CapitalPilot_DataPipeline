{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'technicals']
) }}

with ranked as (

    select
        *,
        row_number() over (
            partition by ticker
            order by date desc
        ) as rn
    from {{ ref('int_technical_indicators') }}

)

select *
from ranked
where rn = 1
order by ticker

