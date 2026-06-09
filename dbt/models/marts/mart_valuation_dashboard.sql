{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'valuation']
) }}

with inputs as (

    select *
    from {{ ref('int_valuation_inputs') }}

),

classified as (

    select
        ticker,
        date,
        price,
        adj_close,
        market_cap,
        volume,

        cast(null as double) as revenue_ttm,
        cast(null as double) as net_income_ttm,
        cast(null as double) as fcf_ttm,
        cast(null as double) as pe,
        cast(null as double) as ps,
        cast(null as double) as fcf_yield,
        cast(null as double) as fcf_margin,
        cast(null as double) as operating_margin,
        cast(null as double) as net_margin,
        cast(null as double) as revenue_growth_yoy,

        'Phase 1 price-only placeholder' as valuation_signal,
        'Fundamental metrics such as revenue, earnings, FCF, PE, PS, and FCF yield require SEC company facts and will be added in Phase 2.' as valuation_explanation,
        false as is_investment_advice

    from inputs

)

select *
from classified
