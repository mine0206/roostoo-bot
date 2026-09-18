"""
Strategy: diversified time-series momentum + trend filter + vol targeting.

IMPORTANT: these are PURE functions of a price table. The backtest and the
live bot both call them, so what we tested is exactly what runs.

Parameters are expressed in BARS (rows of the price table), not hours —
one bar = one poll of the bot. With hourly polling, mom_long=48 means
"return over the last 48 hours".

How to read target_weights(): it returns a pandas Series mapping
"COIN/USD" -> fraction of portfolio to hold (0.15 means 15%).
Coins it doesn't mention should be sold down to zero. Cash = 1 - sum.
"""
import numpy as np
import pandas as pd

DEFAULTS = dict(
    mom_short=24,     # 1 day of bars at hourly polling
    mom_long=168,     # 1 week of bars
    trend_ma=120,     # 5-day moving average regime filter
    vol_window=72,    # 3 days of volatility
    top_n=6,          # hold at most this many coins
    max_weight=0.20,  # never more than 20% in a single coin
    cash_buffer=0.05, # keep ~5% in USD for fees / safety
)


def momentum_score(prices: pd.DataFrame, mom_short=8, mom_long=48) -> pd.DataFrame:
    """Blend of short and long recent returns. Higher = stronger uptrend."""
    r_short = prices.pct_change(mom_short)
    r_long = prices.pct_change(mom_long)
    return 0.5 * r_short + 0.5 * r_long


def trend_on(prices: pd.DataFrame, trend_ma=36) -> pd.DataFrame:
    """True where price is above its moving average (regime filter)."""
    return prices > prices.rolling(trend_ma).mean()


def volatility(prices: pd.DataFrame, vol_window=24) -> pd.DataFrame:
    """Per-bar standard deviation of returns over the lookback."""
    return prices.pct_change().rolling(vol_window).std()


def target_weights(prices: pd.DataFrame, params=None) -> pd.Series:
    """
    Given a price table (columns = 'COIN/USD', rows = time, newest last),
    return target portfolio weights as a Series. Empty Series = hold cash.
    """
    p = {**DEFAULTS, **(params or {})}
    need = max(p["mom_long"], p["trend_ma"], p["vol_window"]) + 2
    prices = prices.dropna(how="all")
    if len(prices) < need:
        return pd.Series(dtype=float)  # not warmed up yet -> stay in cash

    score = momentum_score(prices, p["mom_short"], p["mom_long"]).iloc[-1]
    trend = trend_on(prices, p["trend_ma"]).iloc[-1]
    vol = volatility(prices, p["vol_window"]).iloc[-1].replace(0, np.nan)

    # Only long, only coins in an uptrend, only positive momentum.
    candidates = score[trend].dropna()
    candidates = candidates[candidates > 0]
    if candidates.empty:
        return pd.Series(dtype=float)

    # Best N coins, sized by momentum strength / volatility.
    top = candidates.sort_values(ascending=False).head(p["top_n"])
    inv_vol = 1.0 / vol[top.index]
    raw = top.clip(lower=0) * inv_vol
    if raw.sum() <= 0:
        return pd.Series(dtype=float)
    weights = raw / raw.sum()

    # Apply the single-coin cap, then renormalize to the invested fraction.
    weights = weights.clip(upper=p["max_weight"])
    weights = weights / weights.sum() * (1.0 - p["cash_buffer"])
    return weights.sort_values(ascending=False)
