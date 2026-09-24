"""Draw the backtest: strategy equity vs BTC/ETH buy & hold + drawdown."""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

eq = pd.read_csv("data/backtest_equity.csv", index_col=0, parse_dates=True).iloc[:, 0]
px = pd.read_csv("data/historical_prices.csv", index_col=0, parse_dates=True)

start, start_val = eq.index[0], eq.iloc[0]
btc = px["BTC/USD"].dropna()
btc = btc[btc.index >= start] / btc[btc.index >= start].iloc[0] * start_val
eth = px["ETH/USD"].dropna()
eth = eth[eth.index >= start] / eth[eth.index >= start].iloc[0] * start_val

daily = eq.resample("1D").last().dropna()
dd = (daily - daily.cummax()) / daily.cummax()

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(11, 7), sharex=True,
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})

ax1.plot(eq.index, eq.values, color="#2b6cb0", lw=2.2,
         label="our strategy  (+13.5%, maxDD -14.6%)")
ax1.plot(btc.index, btc.values, color="#999999", lw=1.4,
         label="BTC buy & hold  (-0.1%, maxDD -25.0%)")
ax1.plot(eth.index, eth.values, color="#cccccc", lw=1.4,
         label="ETH buy & hold  (+14.7%, maxDD -28.1%)")
ax1.axhline(100_000, color="black", lw=0.8, ls="--", alpha=0.5)
ax1.set_ylabel("portfolio value (USD)")
ax1.set_title("Backtest, May 16 – Sep 18 2026 (hourly, net of 0.1% fees)")
ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax1.grid(alpha=0.25)

ax2.fill_between(dd.index, dd.values * 100, 0, color="#c53030", alpha=0.55)
ax2.set_ylabel("drawdown %")
ax2.set_xlabel("date")
ax2.grid(alpha=0.25)

fig.align_ylabels()
fig.savefig("data/backtest_equity.png", dpi=130, bbox_inches="tight")
print("saved data/backtest_equity.png")
