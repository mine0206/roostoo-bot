#!/usr/bin/env bash
# One-command setup for the Roostoo-provisioned AWS EC2 instance.
# Tested target: Ubuntu 22.04/24.04 (the usual hackathon AMI).
#
# Usage:
#   chmod +x deploy/setup_ec2.sh
#   ./deploy/setup_ec2.sh https://github.com/<your-team>/roostoo-bot.git
#
# What it does:
#   1. installs python + git
#   2. clones your repo into ~/roostoo-bot
#   3. creates a venv and installs requirements
#   4. reminds you to fill in .env (API keys) — the bot will NOT start without them
#   5. seeds ~2 weeks of price history (cold-start fix)
#   6. installs + starts a systemd service that restarts the bot on crash/reboot
set -euo pipefail

REPO_URL="${1:-}"
if [ -z "$REPO_URL" ]; then
  echo "usage: $0 <git-repo-url>"
  exit 1
fi

echo "==> 1/6 installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git

echo "==> 2/6 cloning repo"
if [ -d "$HOME/roostoo-bot" ]; then
  cd "$HOME/roostoo-bot" && git pull --ff-only
else
  git clone "$REPO_URL" "$HOME/roostoo-bot"
fi
cd "$HOME/roostoo-bot"

echo "==> 3/6 python venv + dependencies"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo "==> 4/6 env file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  *** ACTION REQUIRED ***"
  echo "  Edit ~/roostoo-bot/.env and fill in ROOSTOO_API_KEY / ROOSTOO_SECRET_KEY"
  echo "  (e.g. 'nano ~/roostoo-bot/.env'), then re-run this script."
  echo ""
  exit 0
fi
# load env for the seed step
set -a; . ./.env; set +a

echo "==> 5/6 seeding price history (cold-start fix)"
./.venv/bin/python seed_history.py 14

echo "==> 6/6 systemd service"
sudo cp deploy/roostoo-bot.service /etc/systemd/system/roostoo-bot.service
sudo systemctl daemon-reload
sudo systemctl enable roostoo-bot
sudo systemctl restart roostoo-bot

echo ""
echo "==> done. Bot is running under systemd. Useful commands:"
echo "    sudo systemctl status roostoo-bot     # is it up?"
echo "    journalctl -u roostoo-bot -f          # live logs"
echo "    tail -f ~/roostoo-bot/logs/trades.csv # trade log"
echo "    sudo systemctl restart roostoo-bot    # after any code/env change"
