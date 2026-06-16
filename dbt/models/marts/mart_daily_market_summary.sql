{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'technicals', 'summary']
) }}

with latest as (

    select *
    from {{ ref('mart_technical_dashboard') }}

),

summary as (

    select
        max(date) as summary_date,
        count(*) as ticker_count,
        count(*) filter (where trend_label = 'uptrend') as uptrend_count,
        count(*) filter (where trend_label = 'downtrend') as downtrend_count,
        count(*) filter (where technical_state = 'breakout') as breakout_count,
        count(*) filter (where technical_state = 'breakdown') as breakdown_count,
        count(*) filter (where rsi_14 >= 70) as overbought_count,
        count(*) filter (where rsi_14 <= 30) as oversold_count,
        count(*) filter (where close >= sma_200) as above_200dma_count
    from latest

)

select
    *,
    case
        when ticker_count = 0 then 'insufficient_data'
        when above_200dma_count >= ticker_count * 0.6 and uptrend_count >= downtrend_count then 'risk_on'
        when above_200dma_count <= ticker_count * 0.4 or downtrend_count > uptrend_count then 'risk_off'
        else 'mixed'
    end as market_summary_label,
    'Research-only technical breadth summary. No buy/sell recommendation.' as summary_note,
    false as is_investment_advice
from summary

