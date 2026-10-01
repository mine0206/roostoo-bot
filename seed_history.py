"""
Pre-seed the live bot's price history (COLD-START FIX).

Why this exists: strategy.target_weights() needs ~1 week of hourly bars
before it can produce a signal. The live bot builds history by polling
once per hour, so launching it on day 1 of the competition with an empty
history file means ~7 days sitting in cash — half the contest wasted.

Run this ONCE on the EC2 instance (or locally, then scp the CSV up)
before starting bot.py:

    python3 seed_history.py            # seeds ~14 days of hourly bars
    python3 seed_history.py 21         # seed 21 days instead

It downloads recent hourly closes via data_fetch.py and writes them to
data/price_history.csv — the exact file bot.py reads and appends to.
If the file already exists (e.g. the bot has been running), the new data
is merged in without deleting the bot's own recorded rows.
"""
import os
import sys

import pandas as pd

from data_fetch import fetch_history
from bot import HISTORY_FILE, UNIVERSE


def seed(days=14):
    print(f"downloading ~{days} days of hourly closes for {len(UNIVERSE)} pairs...")
    fresh = fetch_history(pairs=UNIVERSE, days=days)
    # bot.py expects the same column order as UNIVERSE and a named index
    fresh = fresh.reindex(columns=UNIVERSE)
    fresh.index.name = "timestamp"

    if os.path.exists(HISTORY_FILE):
        existing = pd.read_csv(HISTORY_FILE, index_col=0)
        # rows may mix timestamp formats (seed file vs bot-appended rows);
        # parse leniently so concat/sort never chokes on str-vs-Timestamp
        existing.index = pd.to_datetime(existing.index, utc=True, format="mixed")
        combined = pd.concat([existing, fresh])
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = fresh

    combined = combined.sort_index().tail(2000)  # match bot.py's cap
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    combined.to_csv(HISTORY_FILE)
    print(f"seeded {len(combined)} hourly bars "
          f"({combined.index[0]} -> {combined.index[-1]}) -> {HISTORY_FILE}")
    # sanity: enough bars for the strategy to trade immediately?
    from strategy import DEFAULTS
    need = max(DEFAULTS["mom_long"], DEFAULTS["trend_ma"],
               DEFAULTS["vol_window"]) + 2
    if len(combined) >= need:
        print(f"OK: {len(combined)} bars >= {need} needed — bot can trade from hour 1")
    else:
        print(f"WARNING: only {len(combined)} bars, strategy needs {need}. "
              f"Re-run with more days: python3 seed_history.py {days + 7}")


if __name__ == "__main__":
    seed(days=int(sys.argv[1]) if len(sys.argv) > 1 else 14)
