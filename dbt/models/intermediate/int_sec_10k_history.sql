{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'sec']
) }}

select
    *,
    row_number() over (
        partition by ticker
        order by filing_date desc nulls last, acceptance_datetime desc nulls last
    ) as ten_k_rank_desc
from {{ ref('stg_sec_filings') }}
where form_type = '10-K'

