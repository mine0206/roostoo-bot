"""Draw the backtest: strategy equity vs BTC/ETH buy & hold + drawdown.
Labels and title are computed from the data — run backtest.py (or the
wide-universe variant) first to refresh data/backtest_equity.csv."""
import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

eq = pd.read_csv("data/backtest_equity.csv", index_col=0, parse_dates=True).iloc[:, 0]
px_file = ("data/historical_prices_wide.csv"
           if os.path.exists("data/historical_prices_wide.csv")
           else "data/historical_prices.csv")
px = pd.read_csv(px_file, index_col=0, parse_dates=True)


def bench(pair):
    s = px[pair].dropna()
    s = s[s.index >= eq.index[0]]
    return s / s.iloc[0] * eq.iloc[0]


def label(name, s):
    ret = s.iloc[-1] / s.iloc[0] - 1
    d = s.resample("1D").last().dropna()
    dd = ((d - d.cummax()) / d.cummax()).min()
    return f"{name}  ({ret:+.1%}, maxDD {dd:.1%})"


daily = eq.resample("1D").last().dropna()
dd = (daily - daily.cummax()) / daily.cummax()

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(11, 7), sharex=True,
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})

ax1.plot(eq.index, eq.values, color="#2b6cb0", lw=2.2,
         label=label("our strategy", eq))
ax1.plot(bench("BTC/USD").index, bench("BTC/USD").values,
         color="#999999", lw=1.4, label=label("BTC buy & hold", bench("BTC/USD")))
ax1.plot(bench("ETH/USD").index, bench("ETH/USD").values,
         color="#cccccc", lw=1.4, label=label("ETH buy & hold", bench("ETH/USD")))
ax1.axhline(eq.iloc[0], color="black", lw=0.8, ls="--", alpha=0.5)
ax1.set_ylabel("portfolio value (USD)")
ax1.set_title(f"Backtest, {eq.index[0]:%b %d %Y} – {eq.index[-1]:%b %d %Y} "
              f"(hourly, net of 0.1% fees)")
ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax1.grid(alpha=0.25)

ax2.fill_between(dd.index, dd.values * 100, 0, color="#c53030", alpha=0.55)
ax2.set_ylabel("drawdown %")
ax2.set_xlabel("date")
ax2.grid(alpha=0.25)

fig.align_ylabels()
fig.savefig("data/backtest_equity.png", dpi=130, bbox_inches="tight")
print("saved data/backtest_equity.png")
