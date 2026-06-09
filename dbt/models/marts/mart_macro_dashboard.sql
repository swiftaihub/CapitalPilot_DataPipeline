{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'macro']
) }}

with base as (

    select *
    from {{ ref('int_macro_calculations') }}

),

scored as (

    select
        *,

        (
            case when fed_funds_3m_change < 0 then 1 else 0 end
          + case when cpi_yoy_3m_change < 0 then 1 else 0 end
          - case when unemployment_3m_change > 0.3 then 1 else 0 end
          - case when ten_two_spread < 0 then 1 else 0 end
          - case when vix > 25 then 1 else 0 end
          - case when dollar_3m_change_pct > 0.05 then 1 else 0 end
        ) as macro_regime_score

    from base

),

labeled as (

    select
        *,

        case
            when macro_regime_score >= 2 then 'Risk-on / Easing-supportive'
            when macro_regime_score between 0 and 1 then 'Neutral / Mixed'
            when macro_regime_score < 0 then 'Risk-off / Macro pressure'
            else 'Insufficient data'
        end as macro_regime_label,

        case
            when macro_regime_score >= 2 then 'Macro backdrop appears more supportive for risk assets, but valuation and earnings still matter.'
            when macro_regime_score between 0 and 1 then 'Macro signals are mixed. Avoid over-interpreting a single indicator.'
            when macro_regime_score < 0 then 'Macro backdrop shows pressure from rates, volatility, dollar strength, labor weakness, or curve inversion.'
            else 'Insufficient macro data to classify regime.'
        end as macro_regime_explanation

    from scored

)

select *
from labeled
