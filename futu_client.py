"""
Futu (富途) adapter — drop-in replacement for roostoo_client.py so the SAME
bot, strategy, and risk code can trade through Futu instead of Roostoo.

    # .env
    BROKER_CLIENT=futu_client      # bot.py picks this up
    FUTU_TRD_ENV=SIMULATE          # paper trading. REAL only when you mean it.

Prerequisites (one-time):
  1. A Futu brokerage account with the crypto (universal) account opened
     — crypto API trading is available for HK / US / SG users.
  2. FutuOpenD >= 10.4.6408 running locally (default 127.0.0.1:11111).
  3. Python SDK:  pip install "futu-api>=10.5.6508"
     (10.5 is the first version with OpenCryptoTradeContext)
  4. Unlock trading in the OpenD window before starting the bot.

Design notes:
- Function signatures and return shapes mirror roostoo_client.py exactly,
  so bot.py / strategy.py / risk.py don't change.
- Every call is logged to logs/api_log.csv, same as the Roostoo client.
- Nothing here raises on broker errors — failures come back as
  {"Success": False, "ErrMsg": ...} so the bot logs and keeps going.
- "MARKET" orders are sent as aggressive LIMIT orders (last price +/- 0.3%)
  because crypto order-type support varies by broker entity; a slightly
  aggressive limit behaves like a market order but with bounded slippage.

WARNING: this adapter has been written against the Futu API docs but NOT
tested against a live OpenD — run it in SIMULATE first and watch a few
cycles before trusting it with real money.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone

HOST = os.getenv("FUTU_OPEND_HOST", "127.0.0.1")
PORT = int(os.getenv("FUTU_OPEND_PORT", "11111"))
TRD_ENV = os.getenv("FUTU_TRD_ENV", "SIMULATE")   # SIMULATE unless you say REAL
UNLOCK_PWD = os.getenv("FUTU_UNLOCK_PWD", "")      # optional; GUI unlock works too

LOG_DIR = "logs"
API_LOG = os.path.join(LOG_DIR, "api_log.csv")

# Roostoo-style "BTC/USD" -> Futu crypto pair code "CC.BTCUSD"
def pair_to_code(pair):
    return "CC." + pair.replace("/", "")

def code_to_pair(code):
    c = code.replace("CC.", "")
    return c[:-3] + "/" + c[-3:] if len(c) > 3 else code


_quote_ctx = None
_trd_ctx = None


def _futu():
    """Import the SDK lazily so machines without futu-api (e.g. the
    competition EC2) can still run the Roostoo client."""
    try:
        import futu
        return futu
    except ImportError:
        raise RuntimeError(
            "futu-api not installed. Run: pip install 'futu-api>=10.5.6508'")


def _get_quote_ctx():
    global _quote_ctx
    if _quote_ctx is None:
        futu = _futu()
        _quote_ctx = futu.OpenQuoteContext(host=HOST, port=PORT)
    return _quote_ctx


def _get_trd_ctx():
    global _trd_ctx
    if _trd_ctx is None:
        futu = _futu()
        _trd_ctx = futu.OpenCryptoTradeContext(
            host=HOST, port=PORT, security_firm=futu.SecurityFirm.NONE)
        if UNLOCK_PWD:
            ret, data = _trd_ctx.unlock_trade(UNLOCK_PWD)
            if ret != futu.RET_OK:
                raise RuntimeError(f"unlock_trade failed: {data}")
    return _trd_ctx


def _env():
    futu = _futu()
    return futu.TrdEnv.REAL if TRD_ENV.upper() == "REAL" else futu.TrdEnv.SIMULATE


def _log_api(endpoint, params, response, success):
    os.makedirs(LOG_DIR, exist_ok=True)
    write_header = not os.path.exists(API_LOG)
    with open(API_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp_utc", "endpoint", "params", "success", "response"])
        w.writerow([datetime.now(timezone.utc).isoformat(), endpoint,
                    json.dumps(params, default=str), bool(success),
                    json.dumps(response, default=str)[:2000]])


def _ok(**extra):
    return {"Success": True, "ErrMsg": "", **extra}


def _fail(msg):
    return {"Success": False, "ErrMsg": str(msg)}


# ---------------- market data ----------------

def server_time():
    return _ok(ServerTime=int(time.time() * 1000))


def exchange_info():
    """
    Roostoo's exchangeInfo carries per-pair precision/min-size metadata.
    Futu's crypto API doesn't expose an equivalent per-symbol table through
    this path, so we return an empty TradePairs dict — risk.py then falls
    back to its defaults (6 decimals, min notional $25), which are safe for
    Futu's crypto pairs. Tighten here if Futu rejects an order for size.
    """
    return _ok(TradePairs={})


def ticker(pair=None, universe=None):
    """
    Snapshot prices for the universe (or one pair).
    Returns the Roostoo shape: {"Success": True, "Data": {"BTC/USD":
    {"LastPrice": ...}}}
    """
    try:
        pairs = [pair] if pair else (universe or [])
        if not pairs:
            return _fail("ticker() needs pair or universe")
        codes = [pair_to_code(p) for p in pairs]
        ret, data = _get_quote_ctx().get_market_snapshot(codes)
        futu = _futu()
        if ret != futu.RET_OK:
            _log_api("snapshot", {"codes": codes}, {"err": data}, False)
            return _fail(data)
        out = {}
        for _, row in data.iterrows():
            p = code_to_pair(row["code"])
            out[p] = {"LastPrice": float(row["last_price"])}
            for src, dst in (("bid_price", "MaxBid"), ("ask_price", "MinAsk")):
                if src in row and row[src] == row[src]:  # not NaN
                    out[p][dst] = float(row[src])
        _log_api("snapshot", {"codes": codes}, {"pairs": len(out)}, True)
        return _ok(Data=out)
    except Exception as e:
        _log_api("snapshot", {"pair": pair}, {"err": str(e)}, False)
        return _fail(e)


# ---------------- account & orders ----------------

def balance():
    """
    Map Futu's crypto account to the Roostoo wallet shape:
    {"Wallet": {"USD": {"Free": cash, "Lock": frozen}, "BTC": {"Free": q, ...}}}

    Note: 'USD' here means 'whatever fiat currency the account reports'
    (Futu crypto accounts may report USD or HKD depending on entity).
    """
    try:
        futu = _futu()
        ctx = _get_trd_ctx()
        wallet = {}

        ret, acc = ctx.accinfo_query(trd_env=_env())
        if ret != futu.RET_OK:
            _log_api("accinfo_query", {}, {"err": acc}, False)
            return _fail(acc)
        row = acc.iloc[0]
        wallet["USD"] = {"Free": float(row.get("cash", 0.0)),
                         "Lock": float(row.get("frozen_cash", 0.0))}

        ret, pos = ctx.position_list_query(trd_env=_env(), refresh_cache=True)
        if ret == futu.RET_OK:
            for _, r in pos.iterrows():
                coin = code_to_pair(r["code"]).split("/")[0]
                wallet[coin] = {"Free": float(r.get("can_sell_qty", r["qty"])),
                                "Lock": float(r["qty"]) - float(r.get("can_sell_qty", r["qty"]))}
        _log_api("balance", {}, {"coins": len(wallet)}, True)
        return _ok(Wallet=wallet)
    except Exception as e:
        _log_api("balance", {}, {"err": str(e)}, False)
        return _fail(e)


def pending_count():
    """Number of working (not yet filled/cancelled) orders."""
    try:
        futu = _futu()
        ret, orders = _get_trd_ctx().order_list_query(trd_env=_env())
        if ret != futu.RET_OK:
            return _fail(orders)
        working = orders[orders["order_status"].isin([
            futu.OrderStatus.SUBMITTED, futu.OrderStatus.SUBMITTING,
            futu.OrderStatus.WAITING_SUBMIT, futu.OrderStatus.PARTIAL_FILLED,
        ])] if len(orders) else orders
        return _ok(PendingCount=int(len(working)))
    except Exception as e:
        return _fail(e)


def place_order(pair, side, quantity, price=None):
    """
    price=None -> aggressive limit at the current last price (slippage
    capped at 0.3%), which is the closest portable equivalent of a MARKET
    order across Futu broker entities.
    """
    futu = _futu()
    code = pair_to_code(pair)
    trd_side = futu.TrdSide.BUY if side.upper() == "BUY" else futu.TrdSide.SELL
    qty = float(quantity)

    if price is None:
        snap = ticker(pair=pair)
        last = snap.get("Data", {}).get(pair, {}).get("LastPrice")
        if not last:
            return _fail(f"no price for {pair}, cannot build market-equivalent order")
        price = round(last * (1.003 if trd_side == futu.TrdSide.BUY else 0.997), 6)

    try:
        ret, data = _get_trd_ctx().place_order(
            price=float(price), qty=qty, code=code, trd_side=trd_side,
            order_type=futu.OrderType.NORMAL, trd_env=_env(),
            remark="roostoo-bot futu adapter")
        if ret != futu.RET_OK:
            _log_api("place_order", {"pair": pair, "side": side, "qty": qty},
                     {"err": data}, False)
            return _fail(data)
        order_id = str(data.iloc[0]["order_id"]) if len(data) else ""
        _log_api("place_order", {"pair": pair, "side": side, "qty": qty,
                                 "price": price}, {"order_id": order_id}, True)
        return _ok(OrderDetail={"OrderID": order_id, "Status": "SUBMITTED"})
    except Exception as e:
        _log_api("place_order", {"pair": pair, "side": side}, {"err": str(e)}, False)
        return _fail(e)


def query_order(order_id=None, **kwargs):
    try:
        futu = _futu()
        ret, orders = _get_trd_ctx().order_list_query(
            order_id=str(order_id) if order_id else "", trd_env=_env())
        if ret != futu.RET_OK:
            return _fail(orders)
        return _ok(Data=json.loads(orders.to_json(orient="records")))
    except Exception as e:
        return _fail(e)


def cancel_order(order_id=None, **kwargs):
    if not order_id:
        return _fail("cancel_order needs order_id")
    try:
        futu = _futu()
        ret, data = _get_trd_ctx().modify_order(
            futu.ModifyOrderOp.CANCEL, str(order_id), 0, 0, trd_env=_env())
        if ret != futu.RET_OK:
            return _fail(data)
        return _ok(OrderDetail={"OrderID": str(order_id), "Status": "CANCELLED"})
    except Exception as e:
        return _fail(e)


def close():
    """Release OpenD connections (call on shutdown if you manage the loop)."""
    global _quote_ctx, _trd_ctx
    for ctx in (_quote_ctx, _trd_ctx):
        if ctx is not None:
            ctx.close()
    _quote_ctx = _trd_ctx = None
