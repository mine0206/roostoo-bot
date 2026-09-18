"""
Risk layer: turn target weights into concrete orders the exchange accepts.

This is where "don't blow up" lives:
- positions are capped upstream in strategy.py (max_weight, top_n)
- we only trade when a position has drifted enough from target, so fees
  don't grind the portfolio down
- quantities are rounded to the exchange's amount precision and skipped
  if below the minimum notional
"""
import math


def round_step(qty, step):
    """Round DOWN to a multiple of step (exchange requirement)."""
    if not step or step <= 0:
        return qty
    return math.floor(qty / step) * step


def plan_orders(portfolio_value, prices, current_qty, target_w, exchange_info,
                min_weight_drift=0.03, min_notional=25.0):
    """
    Build the list of orders to move the portfolio toward target weights.

    We trade on WEIGHT drift, not notional drift: a position only gets
    adjusted when its share of the portfolio has moved by more than
    min_weight_drift (3pp by default). This is what keeps trading — and
    the 0.1% taker fee — under control.

    portfolio_value : total USD value of the portfolio
    prices          : dict  pair -> last price
    current_qty     : dict  coin -> free quantity held
    target_w        : Series pair -> target weight
    exchange_info   : Roostoo /v3/exchangeInfo response (for precision)
    """
    orders = []
    meta = (exchange_info or {}).get("TradePairs", {})

    for pair, w in target_w.items():
        coin = pair.split("/")[0]
        price = prices.get(pair)
        if not price or price <= 0:
            continue
        precision = meta.get(pair, {}).get("AmountPrecision", 6)
        step = 10 ** (-precision)

        target_qty = (portfolio_value * w) / price
        have_qty = current_qty.get(coin, 0.0)
        current_w = (have_qty * price) / portfolio_value if portfolio_value else 0.0

        # skip small tweaks — only trade on meaningful weight drift
        if abs(w - current_w) < min_weight_drift:
            continue

        qty = round_step(abs(target_qty - have_qty), step)
        if qty <= 0 or qty * price < min_notional:
            continue

        orders.append({
            "pair": pair,
            "side": "BUY" if target_qty > have_qty else "SELL",
            "quantity": f"{qty:.8f}".rstrip("0").rstrip("."),
        })
    return orders


def sell_all_orders(prices, current_qty, exchange_info, min_notional=10.0):
    """Emergency helper: flatten every non-USD position (go to cash)."""
    orders = []
    meta = (exchange_info or {}).get("TradePairs", {})
    for coin, qty in current_qty.items():
        if coin == "USD" or qty <= 0:
            continue
        pair = f"{coin}/USD"
        price = prices.get(pair)
        if not price or price <= 0:
            continue
        step = 10 ** (-meta.get(pair, {}).get("AmountPrecision", 6))
        q = round_step(qty, step)
        if q <= 0 or q * price < min_notional:
            continue
        orders.append({"pair": pair, "side": "SELL",
                       "quantity": f"{q:.8f}".rstrip("0").rstrip(".")})
    return orders
