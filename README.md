# Roostoo Hackathon Trading Bot

A fully autonomous, rule-compliant trading bot for the **Hong Kong vs Australia vs India Quant Trading Hackathon** (Roostoo mock exchange), plus an offline backtester that runs the *exact same strategy code* on historical data.

> Built for a team that is new to coding. Every file is heavily commented so you can learn the system well enough to present it to judges.

---

## The strategy in plain English

**Diversified time-series momentum with a market regime switch, trend filter, and volatility targeting.**

1. **Regime switch** — when BTC (the market's weather vane) trades below its 2-week moving average, the bot sits entirely in USD. Across ~80 rolling 14-day backtest windows, this cut bear-market median drawdown from −6% to ~0%.
2. **Momentum** — crypto prices tend to keep moving in the same direction over days. Every hour we score each of **22 liquid coins** by its recent return over two lookbacks (short + long).
3. **Trend filter** — we only hold a coin while its price is above its own moving average. This rule does most of the downside protection (which is what Sortino rewards).
4. **Volatility targeting** — position size is momentum strength ÷ recent volatility. Jumpy coins get smaller allocations, so the equity curve stays calm (Sharpe/Calmar friendly).
5. **Concentration limits** — top 8 coins max, 20% single-coin cap, 5% cash buffer. No leverage, spot only, long only.

Why this fits the competition scoring:

| Judging metric | Weight | What this strategy does about it |
|---|---|---|
| Portfolio return | Leaderboard gate | Momentum captures trending crypto legs |
| Sortino ratio | 0.4 | Regime switch + trend filter cut downside bars |
| Sharpe ratio | 0.3 | Diversification across ~10 uncorrelated coins |
| Calmar ratio | 0.3 | Strict max-weight caps + cash buffer limit drawdown depth |

Deliberately **not** doing: high-frequency trading, market making, arbitrage (all banned), shorting (tested — no improvement, double the fees), over-trading (0.1% taker fee eats returns — entries only once a day, exits hourly).

---

## Honest backtest results

**Final config (22-coin universe, top 8, BTC regime switch), Jan → Sep 2026, hourly, 0.1% fee:**

| | Return | Sharpe | Sortino | Calmar | Max DD |
|---|---|---|---|---|---|
| **This strategy** | **+41.2%** | 1.59 | 1.59 | 4.52 | −15.1% |
| BTC buy & hold | −11.9% | −0.15 | −0.16 | −0.44 | −38.4% |

Earlier 10-coin version over the full Aug 2025 → Sep 2026 bear year: −12.8% vs BTC −26.5%. The strategy is regime-dependent by design: it protects capital in bears and compounds in trends. Single 14-day windows vary widely — see `eval_windows.py` for the distribution.

**Universe note.** We rank Roostoo's ~86 non-stable pairs by 24h traded value and trade the top 22 (BTC, ETH, BNB, SOL, XRP, ADA, DOGE, LINK, AVAX, DOT, ZEC, NEAR, UNI, SUI, WLD, PEPE, LTC, TAO, ENA, TRUMP, ARB, TRX). Widening 10 → 22 coins with top 6 → 8 roughly doubled returns in the Jul–Sep 2026 rally (+52.7% vs +20.1%) with similar rolling-window risk.

## Repository layout

```
roostoo-bot/
├── bot.py              # The live bot (runs 24/7 on AWS EC2)
├── roostoo_client.py   # API wrapper — every request is logged (compliance)
├── strategy.py         # Signal logic — SAME code in backtest and live
├── risk.py             # Turns target weights into orders, respects exchange limits
├── backtest.py         # Offline backtest + the judges' metrics
├── eval_windows.py     # Rolling 14-day evaluation (research evidence)
├── data_fetch.py       # Downloads historical hourly prices
├── seed_history.py     # Pre-seeds price history so the bot trades from hour 1
├── requirements.txt
├── .env.example        # Copy to .env and fill in your keys
└── README.md
```

## Quick start (backtest — no API keys needed)

```bash
pip install -r requirements.txt
python backtest.py            # ~2-3 min, prints metrics + writes equity curve CSV
python eval_windows.py        # ~8 min, rolling 14-day distribution for all variants
```

## Rehearse without API keys (dry-run paper trading)

You can test the full loop against **live Roostoo prices** before your team
keys arrive — no keys needed, no orders sent:

```bash
DRY_RUN=1 python3 -c "import bot; bot.run_once(full_rebalance=True)"
```

This uses a simulated $100k wallet (`data/paper_state.json`), fills market
orders at the live `LastPrice` with the real 0.1% taker fee, and logs to
`logs/trades.csv` exactly like the real thing. Delete `data/paper_state.json`
to reset the paper wallet.

## Live trading — IMPORTANT: seed history first

The strategy needs ~1 week of hourly bars before it can signal. Without
seeding, the bot would sit in cash for the first 7 days of a 14-day contest.

```bash
cp .env.example .env          # fill in ROOSTOO_API_KEY / ROOSTOO_SECRET_KEY
python seed_history.py 14     # downloads ~2 weeks of hourly prices FIRST
python bot.py                 # then start the bot — it trades from hour 1
```

Deploy on the AWS EC2 instance Roostoo provisions — one command:

```bash
./deploy/setup_ec2.sh <your-github-repo-url>
```

It installs Python, clones the repo, seeds history, and installs a systemd
service (`deploy/roostoo-bot.service`) that auto-restarts the bot on crash
or reboot. See `CHECKLIST.md` for the full competition runbook.

## Compliance checklist (Screen 1 — mandatory)

- [x] All trades placed only by `bot.py` — never call the API by hand once trading starts
- [x] Every API request logged to `logs/api_log.csv` (success/failure)
- [x] Every order logged to `logs/trades.csv`
- [x] Iterations committed to git with clear messages — clean, traceable history
- [x] Open-source repo with this README

## Presenting to judges

Be ready to explain: momentum rationale, the regime switch's role in downside protection (with the rolling-window numbers above), vol targeting, fee sensitivity (why entries are daily, not hourly), and the risk caps. The code comments walk you through it.
