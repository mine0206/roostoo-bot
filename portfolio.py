"""
Show my portfolio: what we hold, what it's worth, and the PnL so far.

    python3 portfolio.py             # one-off check
    python3 portfolio.py --watch     # re-check every 15 min, log to CSV
    python3 portfolio.py --watch 5   # custom interval (minutes)

Reads keys from .env automatically. Works for the general portfolio now,
and for the competition account after you swap keys on Oct 4.
Watch mode appends to logs/portfolio_history.csv — that's your own equity
curve data for the finals presentation.
"""
import csv
import os
import sys
import time
from datetime import datetime, timezone

import roostoo_client as api

START_VALUE = 50_000  # general portfolio; competition account starts at 100k
HISTORY = "logs/portfolio_history.csv"


def snapshot():
    """Return (total_value, rows) or None on failure."""
    bal = api.balance()
    if not bal.get("Success"):
        return None
    tick = api.ticker()
    prices = {k: v.get("LastPrice") for k, v in tick.get("Data", {}).items()}

    wallet = {}
    for key in ("SpotWallet", "Wallet"):
        if isinstance(bal.get(key), dict) and bal[key]:
            wallet = bal[key]
            break

    rows, total = [], 0.0
    for coin, info in sorted(wallet.items()):
        qty = (info.get("Free") or 0) + (info.get("Lock") or 0)
        if qty <= 0:
            continue
        px = 1.0 if coin == "USD" else (prices.get(f"{coin}/USD") or 0)
        value = qty * px
        rows.append((coin, qty, px, value))
        total += value
    return total, rows


def print_snapshot(total, rows):
    print(f"\n{'asset':8s} {'quantity':>14s} {'price':>12s} {'value USD':>12s}")
    print("-" * 50)
    for coin, qty, px, value in rows:
        if coin == "USD":
            print(f"{'USD':8s} {qty:>14,.2f} {'--':>12s} {value:>12,.2f}")
        else:
            print(f"{coin:8s} {qty:>14,.6f} {px:>12,.2f} {value:>12,.2f}")
    print("-" * 50)
    pnl = total - START_VALUE
    print(f"{'TOTAL':8s} {'':14s} {'':12s} {total:>12,.2f}")
    print(f"PnL vs ${START_VALUE:,} start: {pnl:+,.2f} ({pnl/START_VALUE:+.2%})\n")


def log_snapshot(total):
    os.makedirs("logs", exist_ok=True)
    write_header = not os.path.exists(HISTORY)
    with open(HISTORY, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp_utc", "portfolio_value_usd"])
        w.writerow([datetime.now(timezone.utc).isoformat(), f"{total:.2f}"])


def main():
    watch = "--watch" in sys.argv
    interval = 15
    if watch:
        i = sys.argv.index("--watch")
        if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            interval = max(1, int(sys.argv[i + 1]))  # minimum 1 minute

    while True:
        snap = snapshot()
        if snap is None:
            print(f"[{datetime.now(timezone.utc):%H:%M:%S}] balance request failed, "
                  f"retrying in {interval} min")
        else:
            total, rows = snap
            print_snapshot(total, rows)
            log_snapshot(total)
        if not watch:
            break
        print(f"(next check in {interval} min — Ctrl+C to stop)")
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
