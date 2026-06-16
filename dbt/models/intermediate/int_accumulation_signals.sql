{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'accumulation']
) }}

with prices as (

    select *
    from {{ ref('int_price_technical_features') }}

),

macro_latest as (

    select
        (
            case when fed_funds_3m_change < 0 then 1 else 0 end
          + case when cpi_yoy_3m_change < 0 then 1 else 0 end
          - case when unemployment_3m_change > 0.3 then 1 else 0 end
          - case when ten_two_spread < 0 then 1 else 0 end
          - case when vix > 25 then 1 else 0 end
          - case when dollar_3m_change_pct > 0.05 then 1 else 0 end
        ) as macro_regime_score
    from {{ ref('int_macro_calculations') }}
    order by date desc
    limit 1

),

scored as (

    select
        prices.*,
        coalesce(macro_latest.macro_regime_score, 0) as macro_regime_score,
        (
            case
                when drawdown_52w <= -0.25 then 2
                when drawdown_52w <= -0.10 then 1
                when drawdown_52w > -0.02 then -1
                else 0
            end
          + case
                when rsi_14 <= 35 then 1
                when rsi_14 >= 70 then -1
                else 0
            end
          + case
                when price_vs_sma_200_pct <= -0.15 then 1
                when price_vs_sma_200_pct >= 0.25 then -1
                else 0
            end
          - case when volatility_20d >= 0.04 then 1 else 0 end
          + case
                when coalesce(macro_latest.macro_regime_score, 0) >= 2 then 1
                when coalesce(macro_latest.macro_regime_score, 0) < 0 then -1
                else 0
            end
        ) as accumulation_score
    from prices
    left join macro_latest on true

),

labeled as (

    select
        *,
        case
            when observation_number < 200 or sma_200 is null then 'insufficient_data'
            when macro_regime_score < 0 and volatility_20d >= 0.04 then 'risk_off'
            when price_vs_sma_200_pct >= 0.25 or rsi_14 >= 70 then 'extended'
            when accumulation_score >= 4 then 'accumulation_zone'
            when accumulation_score >= 2 then 'starter_zone'
            else 'watch'
        end as accumulation_zone
    from scored

)

select
    ticker,
    date,
    close,
    drawdown_52w,
    sma_50,
    sma_100,
    sma_200,
    price_vs_sma_200_pct,
    rsi_14,
    volatility_20d,
    return_20d,
    return_60d,
    return_252d,
    accumulation_score,
    accumulation_zone,
    concat(
        'Research-only rule score. Drawdown 52w=',
        coalesce(round(drawdown_52w * 100, 1)::varchar, 'n/a'),
        '%, RSI=',
        coalesce(round(rsi_14, 1)::varchar, 'n/a'),
        ', price vs 200DMA=',
        coalesce(round(price_vs_sma_200_pct * 100, 1)::varchar, 'n/a'),
        '%.'
    ) as explanation,
    false as is_investment_advice
from labeled

