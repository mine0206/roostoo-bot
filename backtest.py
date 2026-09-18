"""
Offline backtest — runs the SAME strategy functions the live bot uses,
on downloaded historical hourly prices, with competition-realistic costs
(0.1% taker fee per trade on a $100k portfolio).

Outputs the exact metrics the judges score:
  total return, Sharpe, Sortino, Calmar, max drawdown,
  plus the composite: 0.4*Sortino + 0.3*Sharpe + 0.3*Calmar
"""
import os
import sys

import numpy as np
import pandas as pd

from data_fetch import fetch_history
from strategy import DEFAULTS, target_weights

FEE = 0.001          # 0.1% taker fee, conservative (maker limit orders are 0.05%)
START_CASH = 100_000
WARMUP = 200         # bars before trading starts (indicators need ~1 week of history)
REBALANCE_EVERY = 24 # full rebalance once per day (hourly bars); exits checked hourly


def perf_metrics(equity: pd.Series, periods_per_year=365):
    """Risk-adjusted metrics on an equity curve (daily-sampled)."""
    equity = equity.dropna()
    rets = equity.pct_change().dropna()
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    days = max((equity.index[-1] - equity.index[0]).total_seconds() / 86400, 1)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (365.0 / days) - 1
    std = rets.std()
    sharpe = rets.mean() / std * np.sqrt(periods_per_year) if std > 0 else 0.0
    downside = rets[rets < 0]
    dstd = np.sqrt((downside ** 2).mean())
    sortino = rets.mean() / dstd * np.sqrt(periods_per_year) if dstd > 0 else 0.0
    peak = equity.cummax()
    max_dd = ((equity - peak) / peak).min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0
    composite = 0.4 * sortino + 0.3 * sharpe + 0.3 * calmar
    return dict(total_return=total_ret, cagr=cagr, sharpe=sharpe,
                sortino=sortino, max_drawdown=max_dd, calmar=calmar,
                composite=composite)


def run_backtest(prices: pd.DataFrame, params=None, fee=FEE,
                 start_cash=START_CASH, warmup=WARMUP,
                 rebalance_every=REBALANCE_EVERY):
    """
    Mirrors the live bot exactly:
      - EXITS are checked every bar: a held coin that fails the trend
        filter gets sold immediately (risk control).
      - ENTRIES / weight adjustments happen at most once a day — this
        is what keeps fees from eating the strategy alive.
    """
    prices = prices.sort_index().ffill()
    pairs = list(prices.columns)
    cash, qty = start_cash, {}
    equity_rows, trade_stats = [], {"trades": 0, "bars_with_trades": 0,
                                    "turnover": 0.0, "fees_paid": 0.0}

    def do_trade(coin, pair, usd_amount, price):
        """usd_amount > 0 = buy, < 0 = sell. Returns whether it happened."""
        nonlocal cash
        if abs(usd_amount) < 25.0:  # skip dust
            return False
        if usd_amount > 0:
            spend = min(usd_amount, cash / (1 + fee))
            if spend <= 0:
                return False
            qty[coin] = qty.get(coin, 0.0) + spend * (1 - fee) / price
            cash -= spend
            trade_stats["fees_paid"] += spend * fee
            trade_stats["turnover"] += spend
        else:
            q = min(-usd_amount / price, qty.get(coin, 0.0))
            if q <= 0:
                return False
            cash += q * price * (1 - fee)
            qty[coin] = qty.get(coin, 0.0) - q
            trade_stats["fees_paid"] += q * price * fee
            trade_stats["turnover"] += q * price
        trade_stats["trades"] += 1
        return True

    for i in range(warmup, len(prices)):
        window = prices.iloc[:i]          # history up to NOW (no lookahead)
        bar = prices.iloc[i]
        ts = prices.index[i]

        w = target_weights(window, params)

        # current portfolio value at this bar's prices
        value = cash + sum(qty.get(p.split("/")[0], 0.0) * (bar.get(p) or 0.0)
                           for p in pairs)
        traded_this_bar = False

        # --- hourly exits: drop any held coin the strategy no longer wants ---
        for p in pairs:
            price = bar.get(p)
            if not price or np.isnan(price):
                continue
            coin = p.split("/")[0]
            if qty.get(coin, 0.0) > 0 and w.get(p, 0.0) <= 1e-9:
                if do_trade(coin, p, -qty[coin] * price, price):
                    traded_this_bar = True

        # --- daily rebalance toward target weights ---
        if (i - warmup) % rebalance_every == 0:
            for p in pairs:
                price = bar.get(p)
                if not price or np.isnan(price):
                    continue
                coin = p.split("/")[0]
                tw = w.get(p, 0.0)
                cw = (qty.get(coin, 0.0) * price) / value if value > 0 else 0.0
                if abs(tw - cw) < 0.02:   # 2pp weight drift threshold
                    continue
                usd_amount = (tw - cw) * value
                if do_trade(coin, p, usd_amount, price):
                    traded_this_bar = True

        if traded_this_bar:
            trade_stats["bars_with_trades"] += 1

        equity = cash + sum(qty.get(p.split("/")[0], 0.0) * (bar.get(p) or 0.0)
                            for p in pairs)
        equity_rows.append((ts, equity))

    eq = pd.Series(dict(equity_rows)).sort_index()
    return eq, trade_stats


def fmt(name, m):
    print(f"{name:26s} ret={m['total_return']:8.1%}  Sharpe={m['sharpe']:6.2f}  "
          f"Sortino={m['sortino']:6.2f}  Calmar={m['calmar']:6.2f}  "
          f"maxDD={m['max_drawdown']:8.1%}  composite={m['composite']:6.3f}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    os.makedirs("data", exist_ok=True)
    csv_path = "data/historical_prices.csv"
    if os.path.exists(csv_path):
        prices = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    else:
        print(f"downloading ~{days} days of hourly prices...")
        prices = fetch_history(days=days)
        prices.to_csv(csv_path)
    prices = prices.dropna(how="all")
    print(f"backtest window: {prices.index[0]} -> {prices.index[-1]} "
          f"({len(prices)} hourly bars, {prices.shape[1]} coins)")

    eq, stats = run_backtest(prices)
    daily = eq.resample("1D").last().dropna()

    print()
    print("=== STRATEGY (momentum + trend + vol targeting) ===")
    fmt("strategy, daily metrics", perf_metrics(daily))
    print(f"trades={stats['trades']}  active-bar-days={stats['bars_with_trades']}  "
          f"fees paid=${stats['fees_paid']:,.0f}")

    print()
    print("=== BENCHMARKS ===")
    btc = prices["BTC/USD"].dropna()
    fmt("BTC buy & hold", perf_metrics(btc.resample("1D").last().dropna()))
    if "ETH/USD" in prices:
        eth = prices["ETH/USD"].dropna()
        fmt("ETH buy & hold", perf_metrics(eth.resample("1D").last().dropna()))
    eq_usd = pd.Series(1.0, index=daily.index) * START_CASH
    fmt("stay in USD (flat)", perf_metrics(eq_usd))

    eq.to_csv("data/backtest_equity.csv")
    print()
    print("equity curve saved -> data/backtest_equity.csv")
