"""
Chart your live portfolio history (recorded by portfolio.py --watch).

    python3 plot_portfolio.py

Reads logs/portfolio_history.csv, writes logs/portfolio_history.png.
Run it any time — the more watch data you have, the better it looks.
During the competition this becomes your live equity curve for the finals.
"""
import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HISTORY = "logs/portfolio_history.csv"
OUT = "logs/portfolio_history.png"
START_VALUE = float(os.getenv("PORTFOLIO_START", "50000"))  # 100000 in the contest


def main():
    if not os.path.exists(HISTORY):
        print("no history yet — run: python3 portfolio.py --watch")
        return
    df = pd.read_csv(HISTORY, parse_dates=["timestamp_utc"])
    if df.empty:
        print("history file is empty — let --watch collect a few points first")
        return
    df = df.drop_duplicates("timestamp_utc").sort_values("timestamp_utc")

    v = df["portfolio_value_usd"]
    ret = v.iloc[-1] / START_VALUE - 1
    peak = v.cummax()
    dd = ((v - peak) / peak).min() if len(v) > 1 else 0.0

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["timestamp_utc"], v, color="#2b6cb0", lw=1.8,
            label=f"live portfolio  ({ret:+.2%}, maxDD {dd:.2%})")
    ax.axhline(START_VALUE, color="black", lw=0.8, ls="--", alpha=0.5,
               label=f"start (${START_VALUE:,.0f})")
    ax.set_ylabel("portfolio value (USD)")
    ax.set_title(f"Live portfolio, {df['timestamp_utc'].iloc[0]:%b %d %H:%M} → "
                 f"{df['timestamp_utc'].iloc[-1]:%b %d %H:%M} UTC "
                 f"({len(df)} readings)")
    ax.legend(loc="best", fontsize=9, framealpha=0.9)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.savefig(OUT, dpi=130, bbox_inches="tight")
    print(f"saved {OUT}  ({len(df)} readings, latest ${v.iloc[-1]:,.2f})")


if __name__ == "__main__":
    main()
