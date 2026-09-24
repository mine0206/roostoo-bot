"""
Downloads historical hourly prices for the backtest (and optionally to
pre-seed the live bot's history so it is warm on day one of the contest).

Tries several free public sources and uses whichever responds — no API
keys needed. All return USD-ish prices for the same major coins, which is
fine for strategy research even if the exact exchange differs.
"""
import sys
import time

import pandas as pd
import requests

# Roostoo pair -> symbol on the external source
COIN_MAP = {
    "BTC/USD": ("bitcoin", "BTCUSDT", "BTC-USD"),
    "ETH/USD": ("ethereum", "ETHUSDT", "ETH-USD"),
    "BNB/USD": ("binancecoin", "BNBUSDT", "BNB-USD"),
    "SOL/USD": ("solana", "SOLUSDT", "SOL-USD"),
    "XRP/USD": ("ripple", "XRPUSDT", "XRP-USD"),
    "ADA/USD": ("cardano", "ADAUSDT", "ADA-USD"),
    "DOGE/USD": ("dogecoin", "DOGEUSDT", "DOGE-USD"),
    "LINK/USD": ("chainlink", "LINKUSDT", "LINK-USD"),
    "AVAX/USD": ("avalanche-2", "AVAXUSDT", "AVAX-USD"),
    "DOT/USD": ("polkadot", "DOTUSDT", "DOT-USD"),
    # --- widened universe: next most liquid non-stable pairs on Roostoo ---
    "ZEC/USD": ("zcash", "ZECUSDT", "ZEC-USD"),
    "NEAR/USD": ("near", "NEARUSDT", "NEAR-USD"),
    "UNI/USD": ("uniswap", "UNIUSDT", "UNI-USD"),
    "SUI/USD": ("sui", "SUIUSDT", "SUI-USD"),
    "WLD/USD": ("worldcoin-wld", "WLDUSDT", "WLD-USD"),
    "PEPE/USD": ("pepe", "PEPEUSDT", "PEPE-USD"),
    "LTC/USD": ("litecoin", "LTCUSDT", "LTC-USD"),
    "TAO/USD": ("bittensor", "TAOUSDT", "TAO-USD"),
    "ENA/USD": ("ethena", "ENAUSDT", "ENA-USD"),
    "TRUMP/USD": ("official-trump", "TRUMPUSDT", "TRUMP-USD"),
    "ARB/USD": ("arbitrum", "ARBUSDT", "ARB-USD"),
    "TRX/USD": ("tron", "TRXUSDT", "TRX-USD"),
}

# The 10 original majors
NARROW = ["BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD",
          "ADA/USD", "DOGE/USD", "LINK/USD", "AVAX/USD", "DOT/USD"]

# Narrow + the 12 above = 22 liquid pairs (by Roostoo 24h traded value)
WIDE = list(COIN_MAP)


def _try_binance(pair, days):
    symbol = COIN_MAP[pair][1]
    url = "https://api.binance.com/api/v3/klines"
    out, end = [], int(time.time() * 1000)
    while True:
        r = requests.get(url, params={"symbol": symbol, "interval": "1h",
                                      "endTime": end, "limit": 1000}, timeout=20)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out = rows + out
        end = rows[0][0] - 1
        if len(out) >= days * 24:
            break
    df = pd.DataFrame(out, columns=["ot", "o", "h", "l", "c", "v", "ct",
                                    "qv", "n", "tb", "tq", "ig"])
    s = pd.Series(df["c"].astype(float).values,
                  index=pd.to_datetime(df["ot"].astype("int64"), unit="ms", utc=True))
    return s.rename(pair)


def _try_yahoo(pair, days):
    symbol = COIN_MAP[pair][2]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, params={"interval": "1h", "range": f"{days}d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    j = r.json()["chart"]["result"][0]
    ts = j["timestamp"]
    close = j["indicators"]["quote"][0]["close"]
    s = pd.Series(close, index=pd.to_datetime(ts, unit="s", utc=True)).dropna()
    return s.rename(pair)


def _try_coingecko(pair, days):
    cid = COIN_MAP[pair][0]
    url = f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
    r = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=20)
    r.raise_for_status()
    prices = r.json()["prices"]
    s = pd.Series([p[1] for p in prices],
                  index=pd.to_datetime([p[0] for p in prices], unit="ms", utc=True))
    return s.resample("1h").last().dropna().rename(pair)


FETCHERS = [("binance", _try_binance), ("yahoo", _try_yahoo), ("coingecko", _try_coingecko)]


def fetch_history(pairs=None, days=90):
    """Return a wide DataFrame: one column per pair, hourly closes, USD."""
    pairs = pairs or list(COIN_MAP)
    columns = {}
    for pair in pairs:
        got = None
        for name, fn in FETCHERS:
            try:
                got = fn(pair, days)
                if got is not None and len(got) > days * 12:
                    print(f"  {pair}: {len(got)} hourly bars from {name}")
                    break
            except Exception as e:
                print(f"  {pair}: {name} failed ({type(e).__name__})")
                got = None
        if got is None:
            print(f"  {pair}: NO DATA — dropped from universe")
        else:
            columns[pair] = got
    df = pd.DataFrame(columns).sort_index()
    return df.dropna(how="all")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    hist = fetch_history(days=days)
    hist.to_csv("data/historical_prices.csv")
    print(f"saved {len(hist)} rows -> data/historical_prices.csv")
