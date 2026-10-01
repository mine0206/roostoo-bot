"""
Show my portfolio: what we hold, what it's worth, and the PnL so far.

    python3 portfolio.py

Reads keys from .env automatically. Works for the general portfolio now,
and for the competition account after you swap keys on Oct 4.
"""
import roostoo_client as api

START_VALUE = 50_000  # general portfolio; competition account starts at 100k


def main():
    bal = api.balance()
    if not bal.get("Success"):
        print("balance request failed:", bal.get("ErrMsg"))
        return
    tick = api.ticker()
    prices = {k: v.get("LastPrice") for k, v in tick.get("Data", {}).items()}

    wallet = {}
    for key in ("SpotWallet", "Wallet"):
        if isinstance(bal.get(key), dict) and bal[key]:
            wallet = bal[key]
            break

    print(f"\n{'asset':8s} {'quantity':>14s} {'price':>12s} {'value USD':>12s}")
    print("-" * 50)
    total = 0.0
    for coin, info in sorted(wallet.items()):
        qty = (info.get("Free") or 0) + (info.get("Lock") or 0)
        if qty <= 0:
            continue
        if coin == "USD":
            value = qty
            print(f"{'USD':8s} {qty:>14,.2f} {'--':>12s} {value:>12,.2f}")
        else:
            px = prices.get(f"{coin}/USD") or 0
            value = qty * px
            print(f"{coin:8s} {qty:>14,.6f} {px:>12,.2f} {value:>12,.2f}")
        total += value
    print("-" * 50)
    pnl = total - START_VALUE
    print(f"{'TOTAL':8s} {'':14s} {'':12s} {total:>12,.2f}")
    print(f"\nPnL vs ${START_VALUE:,} start: {pnl:+,.2f} ({pnl/START_VALUE:+.2%})\n")


if __name__ == "__main__":
    main()
