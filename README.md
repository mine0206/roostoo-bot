# Roostoo Hackathon Trading Bot

A fully autonomous, rule-compliant trading bot for the **Hong Kong vs Australia vs India Quant Trading Hackathon** (Roostoo mock exchange), plus an offline backtester that runs the *exact same strategy code* on historical data.

> Built for a team that is new to coding. Every file is heavily commented so you can learn the system well enough to present it to judges.

---

## The strategy in plain English

**Diversified time-series momentum with a market regime switch, trend filter, and volatility targeting.**

1. **Regime switch** — when BTC (the market's weather vane) trades below its 2-week moving average, the bot sits entirely in USD. Across ~80 rolling 14-day backtest windows, this cut bear-market median drawdown from −6% to ~0%.
2. **Momentum** — crypto prices tend to keep moving in the same direction over days. Every hour we score each coin by its recent return over two lookbacks (short + long).
3. **Trend filter** — we only hold a coin while its price is above its own moving average. This rule does most of the downside protection (which is what Sortino rewards).
4. **Volatility targeting** — position size is momentum strength ÷ recent volatility. Jumpy coins get smaller allocations, so the equity curve stays calm (Sharpe/Calmar friendly).
5. **Concentration limits** — top 6 coins max, 20% single-coin cap, 5% cash buffer. No leverage, spot only, long only.

Why this fits the competition scoring:

| Judging metric | Weight | What this strategy does about it |
|---|---|---|
| Portfolio return | Leaderboard gate | Momentum captures trending crypto legs |
| Sortino ratio | 0.4 | Regime switch + trend filter cut downside bars |
| Sharpe ratio | 0.3 | Diversification across ~10 uncorrelated coins |
| Calmar ratio | 0.3 | Strict max-weight caps + cash buffer limit drawdown depth |

Deliberately **not** doing: high-frequency trading, market making, arbitrage (all banned), shorting (tested — no improvement, double the fees), over-trading (0.1% taker fee eats returns — entries only once a day, exits hourly).

---

## Honest backtest results (Aug 2025 → Sep 2026, hourly, 0.1% fee)

| | Return | Sharpe | Sortino | Calmar | Max DD |
|---|---|---|---|---|---|
| **This strategy** | −12.8% | −0.33 | −0.30 | −0.27 | −41.9% |
| BTC buy & hold | −26.5% | −0.40 | −0.40 | −0.45 | −53.0% |
| ETH buy & hold | −23.5% | −0.03 | −0.03 | −0.31 | −67.6% |

That year was a brutal crypto bear market — beating BTC by ~14pp with a smaller drawdown is the realistic claim. In bull regimes the strategy shines: Jul→Sep 2026 returned **+18.4%** (composite 5.2). The strategy is regime-dependent by design: it protects capital in bears and compounds in trends. Single 14-day windows vary widely — see `eval_windows.py` for the distribution.

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

## Live trading — IMPORTANT: seed history first

The strategy needs ~1 week of hourly bars before it can signal. Without
seeding, the bot would sit in cash for the first 7 days of a 14-day contest.

```bash
cp .env.example .env          # fill in ROOSTOO_API_KEY / ROOSTOO_SECRET_KEY
python seed_history.py 14     # downloads ~2 weeks of hourly prices FIRST
python bot.py                 # then start the bot — it trades from hour 1
```

Deploy on the AWS EC2 instance Roostoo provisions — see the hackathon AWS guide. Run it under `nohup python bot.py > logs/bot.out 2>&1 &` or a systemd service so it survives disconnects. Re-run `seed_history.py` (or just `scp data/price_history.csv` up) after any redeploy with a fresh machine.

## Compliance checklist (Screen 1 — mandatory)

- [x] All trades placed only by `bot.py` — never call the API by hand once trading starts
- [x] Every API request logged to `logs/api_log.csv` (success/failure)
- [x] Every order logged to `logs/trades.csv`
- [x] Iterations committed to git with clear messages — clean, traceable history
- [x] Open-source repo with this README

## Presenting to judges

Be ready to explain: momentum rationale, the regime switch's role in downside protection (with the rolling-window numbers above), vol targeting, fee sensitivity (why entries are daily, not hourly), and the risk caps. The code comments walk you through it.
