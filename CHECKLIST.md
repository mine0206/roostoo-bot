# Competition checklist

## Done ✅
- [x] Register team (Team54-Saigo) — confirmation email received Sep 30
- [x] Receive Roostoo API credentials (general + competition)
- [x] Test signed endpoints + one tiny real order on the GENERAL portfolio
- [x] Public GitHub repo with full commit history

## Right now (Sep 30 – Oct 3)
- [ ] **Accept the AWS account invite within 7 days** of its arrival (check captain's email daily, incl. spam) — it expires
- [ ] Keep `.env` out of git (verified: `git check-ignore .env`). Never paste keys in WhatsApp/screenshots
- [ ] Watch the info-session recording linked in Edward's email
- [ ] Read the FAQ + Data Resource links from the email
- [ ] Launch EC2 (Ubuntu 24.04, t3.micro ok) in the AWS sub-account once invited:
  ```bash
  git clone https://github.com/mine0206/roostoo-bot.git && cd roostoo-bot
  ./deploy/setup_ec2.sh https://github.com/mine0206/roostoo-bot.git
  nano .env          # GENERAL keys for now
  ./deploy/setup_ec2.sh https://github.com/mine0206/roostoo-bot.git
  ```
- [ ] Verify on EC2: `sudo systemctl status roostoo-bot`, `journalctl -u roostoo-bot -f`, `cat logs/trades.csv`
- [ ] Rehearse a full 24h against the GENERAL portfolio on the EC2 box

## Oct 4 — competition start (IMPORTANT)
- [ ] Swap `.env` to the **COMPETITION** credentials (they're commented at the bottom of `.env`)
- [ ] `sudo systemctl restart roostoo-bot` and confirm the first cycle places orders
- [ ] Confirm starting balance is $100k via the bot's logs (general portfolio was $50k)
- [ ] Check the leaderboard in the Roostoo app for your bot name

## Oct 4–17 (live trading, 14 days)
- [ ] 5 min/day: `journalctl -u roostoo-bot --since today`, `trades.csv`, leaderboard
- [ ] ≥8 active trading days required — the compliance sleeve (min 10% invested) handles this automatically
- [ ] Iterate allowed: commit to git FIRST, then `git pull && sudo systemctl restart roostoo-bot` on EC2
- [ ] NEVER call the API manually (curl/app/console) on the competition account — Screen 1 disqualifies manual traces

## Before Oct 14
- [ ] Submit repo link — README.md must explain: strategy + motivation, implementation, backtest, trading engine, maker/taker fee handling, risk management (ours already does — keep it updated if the strategy changes)

## If finalists (announced Oct 21)
- [ ] Deck/md by Oct 27 — README §1–§5 + `data/window_eval_summary.csv` is the evidence base

