"""
Thin wrapper around the Roostoo mock-exchange REST API.

Two things to know about this API:
1. Private endpoints are signed: we build a sorted query string that
   includes a millisecond timestamp, then HMAC-SHA256 it with the secret.
2. The competition asks teams to keep internal records of every API call,
   so EVERY request this module makes is appended to logs/api_log.csv.
"""
import csv
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

import requests

BASE_URL = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com")
API_KEY = os.getenv("ROOSTOO_API_KEY", "")
SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY", "")

LOG_DIR = "logs"
API_LOG = os.path.join(LOG_DIR, "api_log.csv")


def _log_api(endpoint, params, response, success):
    os.makedirs(LOG_DIR, exist_ok=True)
    write_header = not os.path.exists(API_LOG)
    with open(API_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp_utc", "endpoint", "params", "success", "response"])
        w.writerow([
            datetime.now(timezone.utc).isoformat(),
            endpoint,
            json.dumps(params),
            bool(success),
            json.dumps(response)[:2000],
        ])


def _timestamp_ms():
    return str(int(time.time() * 1000))


def _sign(params):
    """Add timestamp, sort params, HMAC them. Returns (headers, query_string)."""
    params = dict(params)
    params["timestamp"] = _timestamp_ms()
    qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sig = hmac.new(SECRET_KEY.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"RST-API-KEY": API_KEY, "MSG-SIGNATURE": sig}, qs


def _public_get(endpoint):
    r = requests.get(BASE_URL + endpoint, timeout=15)
    data = r.json()
    _log_api(endpoint, {}, data, data.get("Success", True))
    return data


def _signed_get(endpoint, params=None):
    headers, qs = _sign(params or {})
    full_params = dict((params or {}))
    full_params["timestamp"] = qs.split("timestamp=")[-1]
    r = requests.get(BASE_URL + endpoint, headers=headers, params=full_params, timeout=15)
    data = r.json()
    _log_api(endpoint, full_params, data, data.get("Success", False))
    return data


def _signed_post(endpoint, params=None):
    headers, qs = _sign(params or {})
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    r = requests.post(BASE_URL + endpoint, headers=headers, data=qs, timeout=15)
    data = r.json()
    _log_api(endpoint, params or {}, data, data.get("Success", False))
    return data


# ---------------- public endpoints ----------------

def server_time():
    return _public_get("/v3/serverTime")


def exchange_info():
    return _public_get("/v3/exchangeInfo")


def ticker(pair=None, universe=None):
    """All pairs when called with no args (universe is accepted for
    signature compatibility with futu_client.py and ignored — Roostoo
    returns everything anyway)."""
    params = {"timestamp": _timestamp_ms()}
    if pair:
        params["pair"] = pair
    r = requests.get(BASE_URL + "/v3/ticker", params=params, timeout=15)
    data = r.json()
    _log_api("/v3/ticker", params, data, data.get("Success", False))
    return data


# ---------------- signed endpoints ----------------

def balance():
    return _signed_get("/v3/balance")


def pending_count():
    return _signed_get("/v3/pending_count")


def place_order(pair, side, quantity, price=None):
    """MARKET order if price is None, otherwise LIMIT."""
    params = {
        "pair": pair,
        "side": side.upper(),
        "type": "LIMIT" if price is not None else "MARKET",
        "quantity": str(quantity),
    }
    if price is not None:
        params["price"] = str(price)
    return _signed_post("/v3/place_order", params)


def query_order(**kwargs):
    return _signed_post("/v3/query_order", {k: str(v) for k, v in kwargs.items()})


def cancel_order(**kwargs):
    return _signed_post("/v3/cancel_order", {k: str(v) for k, v in kwargs.items()})
