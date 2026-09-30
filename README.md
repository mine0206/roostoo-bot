# Roostoo Hackathon Trading Bot — Team54-Saigo (HKU)

Our bot for the HK vs AU vs IN Quant Trading Hackathon (Roostoo mock exchange).
None of us had built a trading bot before, so we kept the design simple and
wrote lots of comments — partly for the judges, mostly for ourselves.

---

## 1. The strategy, and how we got there

**Cross-sectional momentum with a market regime switch, trend filter, and
volatility sizing. Long-only, spot, no leverage.**

We started from a simple observation about crypto: coins that have been going
up tend to keep going up for days at a time, but the whole market rises and
falls together with BTC. So the strategy has two layers:

- **Pick the strongest coins.** Every hour we score 22 liquid pairs by a
  blend of their 24h and 7d returns, keep only coins above their own moving
  average, and take the top 8. Position size is momentum ÷ volatility, so
  jumpy coins get less money and the equity curve stays smooth.
- **Don't fight the market.** When BTC is below its 2-week moving average,
  altcoin "momentum" is mostly fake-outs, so we shrink to a 10% sleeve in the
  single strongest coin and wait. (We hold 10% rather than 0% because the
  rules require at least 8 active trading days — a bot sitting fully in cash
  for a week would fail that, and backtests showed the sleeve costs almost
  nothing in bears while catching early recoveries.)

Things we tested and **rejected**: faster/slower momentum lookbacks (no
robust difference), shorting the weakest coins (no improvement, ~2× the
fees — and the API docs hint shorts may be disabled for the competition
anyway), and trading more often (the 0.1% taker fee eats you alive).

## 2. Implementation

```
bot.py              the live bot — the only thing that places trades
roostoo_client.py   API wrapper; logs EVERY request to logs/api_log.csv
strategy.py         signal logic — the exact same functions the backtest calls
risk.py             turns target weights into valid orders (precision, min size)
backtest.py         offline backtest with the judges' metrics
eval_windows.py     rolling 14-day evaluation — our main research tool
data_fetch.py       downloads historical hourly prices (Binance/Yahoo/CoinGecko)
seed_history.py     pre-downloads ~2 weeks of prices before launch (see §4)
deploy/             one-command EC2 setup + systemd service (auto-restart)
```

The bot polls hourly. Entries and resizing happen once a day; exits (a coin
falling below its trend line) are checked every hour. Live trading runs the
identical `strategy.py` code as the backtest — what we tested is what runs.

## 3. Backtesting

Hourly data, real 0.1% taker fee on every trade, no lookahead (each bar only
sees the past). Jan–Sep 2026, 22-coin universe:

| | Return | Sharpe | Sortino | Calmar | Max drawdown |
|---|---|---|---|---|---|
| Our strategy | **+48.8%** | 1.75 | 2.56 | 5.91 | −13.9% |
| BTC buy & hold | −11.9% | −0.15 | −0.16 | −0.44 | −38.4% |

![equity curve](data/backtest_equity.png)

A single backtest can be luck, so our main tool is `eval_windows.py`: it
slides a 14-day window (the competition length) across the data — 46
windows — and reports the *distribution*. That's how we chose the regime
switch (it cut the median bear-window drawdown from −6% to ~0%) and how we
checked we hadn't overfit: we swept every parameter's neighbours, and they
all perform within noise of our chosen values. A flat plateau, not a spike.

To reproduce: `python backtest.py`, then `python eval_windows.py` (~8 min).

## 4. The trading engine

- **Self-built price history.** Roostoo has no candle endpoint, so the bot
  builds its own hourly history from `/v3/ticker` polls, persisted to
  `data/price_history.csv`. Before launch we run `seed_history.py` to
  pre-fill ~2 weeks — otherwise the bot would have no signals for its first
  7 days (the momentum lookback needs that much history).
- **Order planning.** `risk.py` compares current vs target weights and only
  trades on ≥2–3pp drift — this is what keeps fee spend sane. Quantities are
  rounded *down* to each pair's `AmountPrecision` from `/v3/exchangeInfo`
  and skipped below the min notional. Sells always use the actual free
  balance (the fee is deducted from received coins, so naive quantities
  bounce with "insufficient balance" — we learned that one the hard way).
- **Fee accounting.** Taker 0.1% (verified live: bought $25.15 of BTC, fee
  $0.0252). The backtest charges the same 0.1% on every fill; we use market
  orders, so maker fees don't apply — we'd rather pay 0.1% than risk a limit
  order hanging unfilled while momentum moves on.
- **Reliability.** On EC2 the bot runs under systemd and restarts in 30s on
  any crash; the main loop catches all exceptions so one bad API response
  never kills it. Every request (success or failure) lands in
  `logs/api_log.csv`, every order in `logs/trades.csv`.
- **Dry-run mode.** `DRY_RUN=1` paper-trades against live Roostoo prices
  with a simulated $100k wallet — how we rehearsed before keys arrived.

## 5. Risk management

- **Regime switch** — flat-ish when BTC is in a downtrend (the big one)
- **Per-coin trend filter with hourly exits** — a held coin that breaks its
  moving average is sold within the hour
- **Volatility targeting** — position size ∝ 1/vol
- **Concentration caps** — max 8 positions, 20% per coin, ~5% cash buffer
- **No leverage, spot long-only** — shorts evaluated and rejected on evidence
- **Turnover control** — daily entries only, drift thresholds, min-notional
  filters; fees are a risk too

## 6. Compliance

- All trades come from `bot.py`; nobody touches the API by hand during the
  competition. (Our pre-competition connectivity test was a single $25
  round-trip on the *general* portfolio, as intended for testing.)
- Full API and trade logs are kept (`logs/`), plus git history shows every
  strategy change as it happened — including the ideas we rejected.

## Running it

```bash
pip install -r requirements.txt
python backtest.py            # offline backtest
cp .env.example .env          # add keys (never commit .env)
python seed_history.py 14     # pre-fill price history FIRST
python bot.py                 # go live
```

On AWS: `./deploy/setup_ec2.sh <repo-url>` does all of the above plus systemd.
