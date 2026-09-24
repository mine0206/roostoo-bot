# Competition checklist

## By Sep 29 (HARD deadline — no late teams)
- [ ] Register the team (1–4 people) via the Typeform on the Luma page — registration is **not** on Luma itself
- [ ] Join the WhatsApp group (link on Luma page) — that's where keys/AWS accounts get distributed
- [ ] Watch the Sep 18 workshop recording if you missed it live

## Before Oct 1
- [ ] Push this repo to a **public** GitHub repo (`.gitignore` already excludes `.env` — verify: `git status` must never show `.env`)
- [ ] Make sure every team member can explain the strategy (README "Presenting to judges" section)

## Oct 1–3 (prep window — build & test deployment)
- [ ] Receive Roostoo API keys + AWS sub-account from organizers (via WhatsApp/email)
- [ ] Sign in to the AWS sub-account, launch an EC2 instance (Ubuntu 24.04, t3.micro is plenty)
- [ ] SSH in, then:
  ```bash
  git clone <your-repo-url> roostoo-bot && cd roostoo-bot
  ./deploy/setup_ec2.sh <your-repo-url>
  nano .env          # fill in ROOSTOO_API_KEY / ROOSTOO_SECRET_KEY
  ./deploy/setup_ec2.sh <your-repo-url>   # second run seeds history + starts the bot
  ```
- [ ] Verify it's alive:
  ```bash
  sudo systemctl status roostoo-bot    # active (running)
  journalctl -u roostoo-bot -f         # watch one cycle complete
  cat logs/trades.csv                  # orders appearing
  ```
- [ ] **Test with real (small) orders before Oct 4** — confirm the signed endpoints work and orders fill on the mock exchange
- [ ] Check your bot name appears on the leaderboard in the Roostoo app / app.roostoo.com
- [ ] Confirm the starting balance (rules say $100k; `exchangeInfo` says $50k — trust your `/v3/balance`)

## Oct 4–17 (live trading, 14 days)
- [ ] 5 minutes/day: `journalctl -u roostoo-bot --since today` for errors, `trades.csv` growing, leaderboard position
- [ ] Requirement: **≥8 active trading days** with strategy-driven trades — the bot does this automatically if it stays alive
- [ ] You may iterate and redeploy mid-contest. Rules: commit every change with a clear message BEFORE deploying it, redeploy with `git pull && sudo systemctl restart roostoo-bot`
- [ ] Never call the API manually (curl, console, app) — Screen 1 disqualifies manual intervention traces
- [ ] If the bot crashes, systemd restarts it in 30s; if the whole VM dies, reboot and it auto-starts (`enabled`)

## Before Oct 14
- [ ] Submit the repo link (it must stay public and runnable)

## If you make finals (announced Oct 21)
- [ ] Deck/md explaining the logic by Oct 27 — README's strategy section + `data/window_eval_summary.csv` are your evidence base
