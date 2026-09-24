"""
Rolling 14-day evaluation — the honest way to judge a strategy for this
competition. The live contest is ONE 14-day window; we can't know which
regime Oct 4-17 will be, so instead of one lucky backtest we slide a
14-day window across ~14 months of data and look at the DISTRIBUTION of
outcomes for each parameter set.

Simulation matches reality: before each window we include 7 prior days of
history (what seed_history.py gives the bot on day 1), and metrics are
computed only on the 14 competition days, with the real 0.1% taker fee.

Usage:
    python3 eval_windows.py            # runs the candidate grid
"""
import itertools
import sys
import time

import numpy as np
import pandas as pd

from backtest import run_backtest, perf_metrics, START_CASH

WINDOW_DAYS = 14
WARMUP_DAYS = 7          # pre-seeded history on competition day 1
STEP_DAYS = 5            # slide the window -> ~75 overlapping samples
BTC_PAIR = "BTC/USD"


def eval_one(prices, params, window_days=WINDOW_DAYS,
             warmup_days=WARMUP_DAYS, step_days=STEP_DAYS):
    """Return a per-window stats DataFrame for one parameter set."""
    params = dict(params)
    allow_shorts = bool(params.pop("_allow_shorts", False))
    bars_w = window_days * 24
    bars_warm = warmup_days * 24
    bars_step = step_days * 24
    rows = []
    for start in range(0, len(prices) - bars_warm - bars_w, bars_step):
        chunk = prices.iloc[start:start + bars_warm + bars_w]
        eq, stats = run_backtest(chunk, params=params, warmup=bars_warm,
                                 allow_shorts=allow_shorts)
        eq = eq.iloc[1:]                     # drop the warmup bar itself
        daily = eq.resample("1D").last().dropna()
        m = perf_metrics(daily)
        btc = chunk[BTC_PAIR].iloc[bars_warm:].dropna()
        btc_ret = btc.iloc[-1] / btc.iloc[0] - 1 if len(btc) > 1 else 0.0
        rows.append(dict(start=chunk.index[bars_warm],
                         ret=m["total_return"], sharpe=m["sharpe"],
                         sortino=m["sortino"], calmar=m["calmar"],
                         max_dd=m["max_drawdown"], composite=m["composite"],
                         btc_ret=btc_ret, trades=stats["trades"],
                         fees=stats["fees_paid"]))
    return pd.DataFrame(rows)


def summarize(df, name):
    """One-line distribution summary — medians, not lucky bests."""
    if df.empty:
        print(f"{name}: no windows")
        return None
    s = dict(
        name=name,
        n=len(df),
        med_ret=df["ret"].median(),
        p25_ret=df["ret"].quantile(0.25),   # bad-luck case
        worst_ret=df["ret"].min(),
        med_dd=df["max_dd"].median(),
        med_comp=df["composite"].median(),
        p25_comp=df["composite"].quantile(0.25),
        beat_btc=(df["ret"] > df["btc_ret"]).mean(),
        pos=(df["ret"] > 0).mean(),
        med_trades=df["trades"].median(),
        med_fees=df["fees"].median(),
    )
    print(f"{name:34s} n={s['n']:3d}  medRet={s['med_ret']:7.1%}  "
          f"p25Ret={s['p25_ret']:7.1%}  worst={s['worst_ret']:7.1%}  "
          f"medDD={s['med_dd']:6.1%}  medComp={s['med_comp']:5.2f}  "
          f"beatBTC={s['beat_btc']:4.0%}  pos={s['pos']:4.0%}  "
          f"fees=${s['med_fees']:5.0f}")
    return s


CANDIDATES = {
    # current defaults
    "current (24/168, ma120)": {},
    # faster momentum for a short contest
    "fast (12/72, ma72)": dict(mom_short=12, mom_long=72, trend_ma=72,
                               vol_window=48),
    # BTC regime switch
    "fast + BTC regime": dict(mom_short=12, mom_long=72, trend_ma=72,
                              vol_window=48, btc_regime_ma=120),
    # long/short variants (rules allow 1x spot short)
    "fast L/S": dict(mom_short=12, mom_long=72, trend_ma=72, vol_window=48,
                     short_top_n=3, _allow_shorts=True),
    "current L/S": dict(short_top_n=3, _allow_shorts=True),
    "current L/S + BTC regime": dict(short_top_n=3, btc_regime_ma=120,
                                     _allow_shorts=True),
}


if __name__ == "__main__":
    prices = pd.read_csv("data/historical_prices.csv",
                         index_col=0, parse_dates=True).dropna(how="all")
    print(f"data: {prices.index[0]} -> {prices.index[-1]} "
          f"({len(prices)} hourly bars)")
    print(f"window: {WINDOW_DAYS}d + {WARMUP_DAYS}d warmup, "
          f"step {STEP_DAYS}d\n")

    only = sys.argv[1:] or None
    summaries = []
    for name, params in CANDIDATES.items():
        if only and name not in only:
            continue
        t0 = time.time()
        df = eval_one(prices, params)
        s = summarize(df, name)
        if s:
            summaries.append(s)
        print(f"   ({time.time()-t0:.0f}s)")

    if summaries:
        out = pd.DataFrame(summaries)
        out.to_csv("data/window_eval_summary.csv", index=False)
        print("\nsaved -> data/window_eval_summary.csv")
