"""Summarise the bot's trades.csv: is it actually making money?

    python report.py
    python report.py --file trades.csv --fee-pct 0.1
"""

import argparse
import csv
from collections import defaultdict


def load_round_trips(path, fee_pct):
    """Pair each buy with the next sell of the same symbol."""
    open_buys, trips = {}, []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            symbol, qty, price = row["symbol"], float(row["qty"]), float(row["price"])
            if row["side"] == "buy":
                open_buys[symbol] = (row["time_utc"], qty, price)
            elif symbol in open_buys:
                bought_at, buy_qty, buy_price = open_buys.pop(symbol)
                fees = (buy_price * buy_qty + price * qty) * fee_pct / 100
                trips.append({
                    "symbol": symbol, "reason": row["reason"], "opened": bought_at, "closed": row["time_utc"],
                    "cost": buy_price * buy_qty, "pnl": (price - buy_price) * qty - fees, "fees": fees,
                    "pct": (price - buy_price) / buy_price * 100,
                })
    return trips, open_buys


def summary_line(label, trips):
    pnl = sum(t["pnl"] for t in trips)
    wins = sum(1 for t in trips if t["pnl"] > 0)
    return f"  {label:<18} {len(trips):>4} trades  {wins / len(trips) * 100:>5.0f}% wins  {pnl:>+9.2f} USDT"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", default="trades.csv")
    p.add_argument("--fee-pct", type=float, default=0.1, help="fee per order, %% (Binance spot default 0.1)")
    args = p.parse_args()

    try:
        trips, still_open = load_round_trips(args.file, args.fee_pct)
    except FileNotFoundError:
        print(f"No {args.file} yet. Run the bot first.")
        return
    if not trips:
        print("No finished trades yet (a trade counts once it has been bought and sold).")
    else:
        wins = [t for t in trips if t["pnl"] > 0]
        losses = [t for t in trips if t["pnl"] <= 0]
        total = sum(t["pnl"] for t in trips)
        fees = sum(t["fees"] for t in trips)
        print(f"\nFinished trades: {len(trips)}   ({trips[0]['opened'][:10]} to {trips[-1]['closed'][:10]})")
        print(f"Result after fees: {total:+.2f} USDT   (fees paid: {fees:.2f} USDT)")
        print(f"Wins: {len(wins)} ({len(wins) / len(trips) * 100:.0f}%)   Losses: {len(losses)}")
        if wins:
            print(f"Average win:  {sum(t['pnl'] for t in wins) / len(wins):+.2f} USDT")
        if losses:
            print(f"Average loss: {sum(t['pnl'] for t in losses) / len(losses):+.2f} USDT")
        gross_loss = -sum(t["pnl"] for t in losses)
        if wins and gross_loss:
            ratio = sum(t["pnl"] for t in wins) / gross_loss
            print(f"Profit factor: {ratio:.2f}   (above 1 = making money; below 1 = losing)")

        for title, key in (("By coin", "symbol"), ("By exit reason", "reason")):
            groups = defaultdict(list)
            for t in trips:
                groups[t[key]].append(t)
            print(f"\n{title}:")
            for name, group in sorted(groups.items(), key=lambda g: sum(t["pnl"] for t in g[1])):
                print(summary_line(name, group))

        worst = sorted(losses, key=lambda t: t["pnl"])[:3]
        if worst:
            print("\nWorst trades:")
        for t in worst:
            print(f"  {t['closed'][:16]}  {t['symbol']:<12} {t['reason']:<15} {t['pct']:+6.2f}%  {t['pnl']:+.2f} USDT")

        if total < 0 < total + fees:
            print(f"\nNote: before fees this was {total + fees:+.2f} USDT. Fees turned it into a loss; trading less often may help.")

    if still_open:
        print("\nStill holding (bought, not sold yet):")
        for symbol, (opened, qty, price) in still_open.items():
            print(f"  {symbol:<12} {qty} bought at {price} on {opened[:16]}")


if __name__ == "__main__":
    main()
