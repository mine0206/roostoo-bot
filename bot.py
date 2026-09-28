"""
The live bot. This is what runs 24/7 on your AWS EC2 instance.

Every LOOP_MINUTES it:
  1. polls prices for the universe and appends them to a local history file
     (Roostoo has no candle endpoint, so the bot builds its own price
     history — indicators need history to work)
  2. runs the strategy on that history -> target weights
  3. fetches balances and places only the orders needed to reach targets
  4. logs every order to logs/trades.csv

Nothing here is manual. Once it starts, all trades are autonomous —
which is exactly what the competition's commit-history screen checks for.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd

import pandas as pd

import roostoo_client as api
from risk import exit_orders, plan_orders, sell_all_orders
from strategy import target_weights

LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "60"))
# Full rebalance (entries + weight adjustments) once per day; every other
# loop only exits coins that failed the trend filter. This mirrors the
# backtest exactly and keeps the 0.1% taker fee from grinding returns down.
REBALANCE_EVERY_LOOPS = int(os.getenv("REBALANCE_EVERY_LOOPS", "24"))
# DRY_RUN=1: paper-trade against LIVE Roostoo prices with a simulated
# $100k wallet (data/paper_state.json). No API keys needed, no orders sent.
# Use this to rehearse the full loop before your keys arrive.
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
PAPER_STATE = "data/paper_state.json"
UNIVERSE = [p.strip() for p in os.getenv(
    "UNIVERSE",
    "BTC/USD,ETH/USD,BNB/USD,SOL/USD,XRP/USD,ADA/USD,DOGE/USD,LINK/USD,"
    "AVAX/USD,DOT/USD,ZEC/USD,NEAR/USD,UNI/USD,SUI/USD,WLD/USD,PEPE/USD,"
    "LTC/USD,TAO/USD,ENA/USD,TRUMP/USD,ARB/USD,TRX/USD",
).split(",")]
HISTORY_FILE = "data/price_history.csv"
TRADE_LOG = "logs/trades.csv"


def load_history():
    if os.path.exists(HISTORY_FILE):
        df = pd.read_csv(HISTORY_FILE, index_col=0, parse_dates=True)
        # keep only our universe, in a stable column order
        return df.reindex(columns=UNIVERSE)
    return pd.DataFrame(columns=UNIVERSE)


def append_price_row(df, ts, price_map):
    row = {p: price_map.get(p) for p in UNIVERSE}
    new = pd.DataFrame([row], index=[ts])
    new.index.name = "timestamp"
    combined = pd.concat([df, new])
    return combined[~combined.index.duplicated(keep="last")].tail(2000)


def log_trade(order, response):
    os.makedirs("logs", exist_ok=True)
    write_header = not os.path.exists(TRADE_LOG)
    with open(TRADE_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp_utc", "pair", "side", "quantity",
                        "success", "order_status", "raw_response"])
        detail = response.get("OrderDetail", {}) if isinstance(response, dict) else {}
        w.writerow([
            datetime.now(timezone.utc).isoformat(),
            order.get("pair"), order.get("side"), order.get("quantity"),
            bool(response.get("Success")) if isinstance(response, dict) else False,
            detail.get("Status", ""), str(response)[:1000],
        ])


def portfolio_value_usd(balance, price_map):
    total = 0.0
    for coin, info in balance.get("Wallet", {}).items():
        free = info.get("Free", 0) or 0
        locked = info.get("Lock", 0) or 0
        if coin == "USD":
            total += free + locked
        else:
            price = price_map.get(f"{coin}/USD")
            if price:
                total += (free + locked) * price
    return total


# ---------------- dry-run (paper trading, no keys needed) ----------------

def load_paper_state():
    """Simulated wallet for DRY_RUN. Starts at the competition's $100k."""
    if os.path.exists(PAPER_STATE):
        with open(PAPER_STATE) as f:
            return json.load(f)
    return {"cash": 100_000.0, "qty": {}}


def save_paper_state(state):
    os.makedirs("data", exist_ok=True)
    with open(PAPER_STATE, "w") as f:
        json.dump(state, f, indent=2)


def paper_balance(state):
    wallet = {"USD": {"Free": state["cash"], "Lock": 0}}
    for coin, q in state["qty"].items():
        wallet[coin] = {"Free": q, "Lock": 0}
    return {"Wallet": wallet}


def paper_fill(state, order, price_map, fee=0.001):
    """Fill a market order at the live LastPrice with the real taker fee."""
    coin = order["pair"].split("/")[0]
    price = price_map.get(order["pair"])
    q = float(order["quantity"])
    if not price or q <= 0:
        return {"Success": False, "DryRun": True, "ErrMsg": "no price"}
    if order["side"] == "BUY":
        cost = q * price * (1 + fee)
        if cost > state["cash"]:           # scale down to available cash
            q = state["cash"] / (price * (1 + fee))
            cost = q * price * (1 + fee)
        if q <= 0:
            return {"Success": False, "DryRun": True, "ErrMsg": "no cash"}
        state["cash"] -= cost
        state["qty"][coin] = state["qty"].get(coin, 0.0) + q
    else:  # SELL
        q = min(q, state["qty"].get(coin, 0.0))
        if q <= 0:
            return {"Success": False, "DryRun": True, "ErrMsg": "nothing to sell"}
        state["cash"] += q * price * (1 - fee)
        state["qty"][coin] = state["qty"].get(coin, 0.0) - q
    return {"Success": True, "DryRun": True,
            "OrderDetail": {"Status": "FILLED", "FilledQty": q, "Price": price}}


def run_once(full_rebalance=True):
    info = api.exchange_info()
    tick = api.ticker()
    data = tick.get("Data", {})
    price_map = {k: v.get("LastPrice") for k, v in data.items() if k in UNIVERSE}

    ts = pd.Timestamp.now(tz="UTC")
    hist = append_price_row(load_history(), ts, price_map)
    os.makedirs("data", exist_ok=True)
    hist.to_csv(HISTORY_FILE)

    weights = target_weights(hist)

    if DRY_RUN:
        state = load_paper_state()
        bal = paper_balance(state)
    else:
        bal = api.balance()
    wallet = bal.get("Wallet", {})
    qty = {c: (i.get("Free", 0) or 0) for c, i in wallet.items()}
    value = portfolio_value_usd(bal, price_map)

    if weights.empty:
        # No qualifying coins -> flatten into USD (the trend filter at work).
        orders = sell_all_orders(price_map, qty, info)
    elif full_rebalance:
        # Daily: move all positions toward their target weights.
        orders = plan_orders(value, price_map, qty, weights, info)
    else:
        # Hourly: risk control only — dump coins that failed the trend filter.
        orders = exit_orders(price_map, qty, weights, info)

    for o in orders:
        if DRY_RUN:
            res = paper_fill(state, o, price_map)
            save_paper_state(state)
        else:
            res = api.place_order(o["pair"], o["side"], o["quantity"])
            time.sleep(2)  # stay well under rate limits
        log_trade(o, res)
        print(f"  order: {o['side']} {o['quantity']} {o['pair']} -> {res.get('Success')}")

    return len(orders), weights.to_dict()


if __name__ == "__main__":
    print(f"bot starting, polling every {LOOP_MINUTES} min, "
          f"full rebalance every {REBALANCE_EVERY_LOOPS} loops, "
          f"universe={len(UNIVERSE)} pairs")
    loop = 0
    while True:
        try:
            # loop 0 (startup) is always a full rebalance so we deploy capital
            # immediately; after that, full rebalance once a day.
            full = (loop % REBALANCE_EVERY_LOOPS == 0)
            n, w = run_once(full_rebalance=full)
            print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}] cycle {loop} "
                  f"({'full' if full else 'exits-only'}), "
                  f"{n} order(s), weights={w}")
        except Exception as e:  # never die — a crashed bot trades nothing
            print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}] error: {e}")
        loop += 1
        time.sleep(LOOP_MINUTES * 60)
