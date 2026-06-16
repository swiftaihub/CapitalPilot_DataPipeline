"""Technical indicator calculations for tests and local parity checks."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_technical_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily technical indicators for a price dataframe."""
    if prices.empty:
        return prices.copy()
    required = {"ticker", "date", "close"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"Price dataframe missing required columns: {', '.join(sorted(missing))}")

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["ticker", "date"])
    grouped = frame.groupby("ticker", group_keys=False)

    for window in [20, 50, 100, 200]:
        frame[f"sma_{window}"] = grouped["close"].transform(lambda series: series.rolling(window, min_periods=window).mean())

    frame["ema_12"] = grouped["close"].transform(lambda series: series.ewm(span=12, adjust=False).mean())
    frame["ema_26"] = grouped["close"].transform(lambda series: series.ewm(span=26, adjust=False).mean())
    frame["macd"] = frame["ema_12"] - frame["ema_26"]
    frame["macd_signal"] = grouped["macd"].transform(lambda series: series.ewm(span=9, adjust=False).mean())
    frame["macd_histogram"] = frame["macd"] - frame["macd_signal"]

    delta = grouped["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(frame["ticker"]).transform(lambda series: series.rolling(14, min_periods=14).mean())
    avg_loss = loss.groupby(frame["ticker"]).transform(lambda series: series.rolling(14, min_periods=14).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    frame["rsi_14"] = 100 - (100 / (1 + rs))
    frame.loc[(avg_loss == 0) & (avg_gain > 0), "rsi_14"] = 100

    frame["return_20d"] = grouped["close"].pct_change(20)
    frame["return_60d"] = grouped["close"].pct_change(60)
    frame["return_120d"] = grouped["close"].pct_change(120)
    frame["return_252d"] = grouped["close"].pct_change(252)

    log_returns = np.log(frame["close"] / grouped["close"].shift(1))
    frame["volatility_20d"] = log_returns.groupby(frame["ticker"]).transform(
        lambda series: series.rolling(20, min_periods=20).std()
    ) * np.sqrt(252)
    frame["volatility_60d"] = log_returns.groupby(frame["ticker"]).transform(
        lambda series: series.rolling(60, min_periods=60).std()
    ) * np.sqrt(252)

    rolling_mid = grouped["close"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    rolling_std = grouped["close"].transform(lambda series: series.rolling(20, min_periods=20).std())
    frame["bollinger_mid_20"] = rolling_mid
    frame["bollinger_upper_20"] = rolling_mid + 2 * rolling_std
    frame["bollinger_lower_20"] = rolling_mid - 2 * rolling_std

    if {"high", "low"}.issubset(frame.columns):
        prev_close = grouped["close"].shift(1)
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - prev_close).abs(),
                (frame["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        frame["atr_14"] = true_range.groupby(frame["ticker"]).transform(lambda series: series.rolling(14, min_periods=14).mean())
    else:
        frame["atr_14"] = np.nan

    if "volume" in frame.columns:
        frame["volume_avg_20"] = grouped["volume"].transform(lambda series: series.rolling(20, min_periods=20).mean())
        frame["volume_vs_20d_avg"] = frame["volume"] / frame["volume_avg_20"] - 1
    else:
        frame["volume_avg_20"] = np.nan
        frame["volume_vs_20d_avg"] = np.nan

    frame["high_52w"] = grouped["close"].transform(lambda series: series.rolling(252, min_periods=20).max())
    frame["drawdown_52w"] = frame["close"] / frame["high_52w"] - 1
    frame["price_vs_sma_200_pct"] = frame["close"] / frame["sma_200"] - 1
    return frame
