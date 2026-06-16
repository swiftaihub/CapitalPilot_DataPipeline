{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'technicals']
) }}

with recursive price_rows as (

    select
        ticker,
        date,
        close,
        row_number() over (partition by ticker order by date) as rn
    from {{ ref('stg_prices') }}
    where close is not null

),

ema_prices(ticker, date, rn, ema_12, ema_26) as (

    select
        ticker,
        date,
        rn,
        close as ema_12,
        close as ema_26
    from price_rows
    where rn = 1

    union all

    select
        price_rows.ticker,
        price_rows.date,
        price_rows.rn,
        price_rows.close * (2.0 / 13.0) + ema_prices.ema_12 * (1.0 - (2.0 / 13.0)) as ema_12,
        price_rows.close * (2.0 / 27.0) + ema_prices.ema_26 * (1.0 - (2.0 / 27.0)) as ema_26
    from price_rows
    join ema_prices
      on price_rows.ticker = ema_prices.ticker
     and price_rows.rn = ema_prices.rn + 1

),

macd_rows as (

    select
        ticker,
        date,
        rn,
        ema_12,
        ema_26,
        ema_12 - ema_26 as macd
    from ema_prices

),

macd_signal(ticker, date, rn, macd_signal) as (

    select
        ticker,
        date,
        rn,
        macd as macd_signal
    from macd_rows
    where rn = 1

    union all

    select
        macd_rows.ticker,
        macd_rows.date,
        macd_rows.rn,
        macd_rows.macd * (2.0 / 10.0) + macd_signal.macd_signal * (1.0 - (2.0 / 10.0)) as macd_signal
    from macd_rows
    join macd_signal
      on macd_rows.ticker = macd_signal.ticker
     and macd_rows.rn = macd_signal.rn + 1

),

features as (

    select *
    from {{ ref('int_price_technical_features') }}

)

select
    features.*,
    macd_rows.ema_12,
    macd_rows.ema_26,
    macd_rows.macd,
    macd_signal.macd_signal,
    macd_rows.macd - macd_signal.macd_signal as macd_histogram,
    case
        when features.observation_number < 50 then 'insufficient_data'
        when features.close > features.sma_50 and features.sma_50 >= features.sma_200 then 'uptrend'
        when features.close < features.sma_50 and features.sma_50 <= features.sma_200 then 'downtrend'
        else 'consolidation'
    end as trend_label,
    case
        when features.rsi_14 >= 70 then 'overbought'
        when features.rsi_14 <= 30 then 'oversold'
        when features.close >= features.resistance_60d * 0.995 and features.volume_vs_20d_avg > 0.2 then 'breakout'
        when features.close <= features.support_60d * 1.005 and features.volume_vs_20d_avg > 0.2 then 'breakdown'
        else 'neutral'
    end as technical_state,
    false as is_investment_advice
from features
left join macd_rows
  on features.ticker = macd_rows.ticker
 and features.date = macd_rows.date
left join macd_signal
  on features.ticker = macd_signal.ticker
 and features.date = macd_signal.date

