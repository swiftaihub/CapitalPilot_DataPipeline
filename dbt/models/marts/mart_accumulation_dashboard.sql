{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'accumulation']
) }}

select *
from {{ ref('int_accumulation_signals') }}
order by date desc, ticker

