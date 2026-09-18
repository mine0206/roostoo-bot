# Roostoo Hackathon Trading Bot

A fully autonomous, rule-compliant trading bot for the **Hong Kong vs Australia vs India Quant Trading Hackathon** (Roostoo mock exchange), plus an offline backtester that runs the *exact same strategy code* on historical data.

> Built for a team that is new to coding. Every file is heavily commented so you can learn the system well enough to present it to judges.

---

## The strategy in plain English

**Diversified time-series momentum with a trend filter and volatility targeting.**

1. **Momentum** — crypto prices tend to keep moving in the same direction over days (not seconds). Every hour we score each coin by its recent return over two lookbacks (short + long).
2. **Trend filter** — we only hold a coin while its price is above its own moving average. When nothing qualifies, the bot sits in USD. This one rule does most of the downside protection (which is what Sortino rewards).
3. **Volatility targeting** — position size is momentum strength ÷ recent volatility. Jumpy coins get smaller allocations, so the equity curve stays calm (Sharpe/Calmar friendly).
4. **Concentration limits** — top 6 coins max, single-coin cap, cash buffer. No leverage, spot only, long only.

Why this fits the competition scoring:

| Judging metric | Weight | What this strategy does about it |
|---|---|---|
| Portfolio return | Leaderboard gate | Momentum captures trending crypto legs |
| Sortino ratio | 0.4 | Trend filter cuts downside bars; vol targeting smooths the curve |
| Sharpe ratio | 0.3 | Diversification across ~10 uncorrelated coins |
| Calmar ratio | 0.3 | Strict max-weight caps + cash buffer limit drawdown depth |

Deliberately **not** doing: high-frequency trading, market making, arbitrage (all banned), shorts (docs hint the competition may disable them), over-trading (0.1% taker fee eats returns — we rebalance only on meaningful drift).

---

## Repository layout

```
roostoo-bot/
├── bot.py              # The live bot (runs 24/7 on AWS EC2)
├── roostoo_client.py   # API wrapper — every request is logged (compliance)
├── strategy.py         # Signal logic — SAME code in backtest and live
├── risk.py             # Turns target weights into orders, respects exchange limits
├── backtest.py         # Offline backtest + the judges' metrics
├── data_fetch.py       # Downloads historical hourly prices
├── requirements.txt
├── .env.example        # Copy to .env and fill in your keys
└── README.md
```

## Quick start (backtest — no API keys needed)

```bash
pip install -r requirements.txt
python backtest.py            # ~1-2 min, prints metrics + writes equity curve CSV
```

## Live trading

```bash
cp .env.example .env          # fill in ROOSTOO_API_KEY / ROOSTOO_SECRET_KEY
python bot.py                 # polls hourly, logs everything to logs/
```

Deploy on the AWS EC2 instance Roostoo provisions — see the hackathon AWS guide. Run it under `nohup python bot.py > logs/bot.out 2>&1 &` or a systemd service so it survives disconnects.

## Compliance checklist (Screen 1 — mandatory)

- [x] All trades placed only by `bot.py` — never call the API by hand once trading starts
- [x] Every API request logged to `logs/api_log.csv` (success/failure)
- [x] Every order logged to `logs/trades.csv`
- [x] Iterations committed to git with clear messages — clean, traceable history
- [x] Open-source repo with this README

## Presenting to judges

Be ready to explain: momentum rationale, the trend filter's role in downside protection, vol targeting, fee sensitivity (why we don't churn), and the risk caps. The code comments walk you through it.
