{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'prices', 'technicals']
) }}

with prices as (

    select
        *,
        row_number() over (partition by ticker order by date) as observation_number,
        count(*) over (partition by ticker) as total_observations
    from {{ ref('stg_prices') }}
    where close is not null

),

returns as (

    select
        *,
        lag(close) over (partition by ticker order by date) as prev_close,
        close - lag(close) over (partition by ticker order by date) as close_delta,
        case
            when lag(close) over (partition by ticker order by date) > 0
            then ln(close / lag(close) over (partition by ticker order by date))
        end as log_return,
        greatest(
            high - low,
            abs(high - lag(close) over (partition by ticker order by date)),
            abs(low - lag(close) over (partition by ticker order by date))
        ) as true_range
    from prices

),

prepared as (

    select
        *,
        greatest(close_delta, 0) as rsi_gain,
        greatest(-close_delta, 0) as rsi_loss
    from returns

),

windowed as (

    select
        *,
        avg(close) over (partition by ticker order by date rows between 19 preceding and current row) as sma_20,
        avg(close) over (partition by ticker order by date rows between 49 preceding and current row) as sma_50,
        avg(close) over (partition by ticker order by date rows between 99 preceding and current row) as sma_100,
        avg(close) over (partition by ticker order by date rows between 199 preceding and current row) as sma_200,
        max(close) over (partition by ticker order by date rows between 251 preceding and current row) as high_52w,
        min(low) over (partition by ticker order by date rows between 59 preceding and current row) as support_60d,
        max(high) over (partition by ticker order by date rows between 59 preceding and current row) as resistance_60d,
        avg(rsi_gain) over (partition by ticker order by date rows between 13 preceding and current row) as avg_gain_14,
        avg(rsi_loss) over (partition by ticker order by date rows between 13 preceding and current row) as avg_loss_14,
        stddev_samp(log_return) over (partition by ticker order by date rows between 19 preceding and current row) * sqrt(252.0) as volatility_20d,
        stddev_samp(log_return) over (partition by ticker order by date rows between 59 preceding and current row) * sqrt(252.0) as volatility_60d,
        avg(close) over (partition by ticker order by date rows between 19 preceding and current row) as bollinger_mid_20,
        stddev_samp(close) over (partition by ticker order by date rows between 19 preceding and current row) as bollinger_std_20,
        avg(true_range) over (partition by ticker order by date rows between 13 preceding and current row) as atr_14,
        avg(volume) over (partition by ticker order by date rows between 19 preceding and current row) as volume_avg_20,
        close / nullif(lag(close, 20) over (partition by ticker order by date), 0) - 1 as return_20d,
        close / nullif(lag(close, 60) over (partition by ticker order by date), 0) - 1 as return_60d,
        close / nullif(lag(close, 120) over (partition by ticker order by date), 0) - 1 as return_120d,
        close / nullif(lag(close, 252) over (partition by ticker order by date), 0) - 1 as return_252d
    from prepared

)

select
    ticker,
    date,
    open,
    high,
    low,
    close,
    adj_close,
    volume,
    market_cap,
    observation_number,
    total_observations,
    sma_20,
    sma_50,
    sma_100,
    sma_200,
    high_52w,
    close / nullif(high_52w, 0) - 1 as drawdown_52w,
    close / nullif(sma_200, 0) - 1 as price_vs_sma_200_pct,
    case
        when avg_loss_14 = 0 and avg_gain_14 > 0 then 100
        when avg_loss_14 = 0 then null
        else 100 - (100 / (1 + avg_gain_14 / nullif(avg_loss_14, 0)))
    end as rsi_14,
    volatility_20d,
    volatility_60d,
    return_20d,
    return_60d,
    return_120d,
    return_252d,
    bollinger_mid_20,
    bollinger_mid_20 + 2 * bollinger_std_20 as bollinger_upper_20,
    bollinger_mid_20 - 2 * bollinger_std_20 as bollinger_lower_20,
    atr_14,
    volume_avg_20,
    volume / nullif(volume_avg_20, 0) - 1 as volume_vs_20d_avg,
    open / nullif(prev_close, 0) - 1 as gap_pct,
    support_60d,
    resistance_60d,
    source,
    updated_at
from windowed

