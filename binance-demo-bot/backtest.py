"""Replay the bot's rules on past Binance candles (public data, no API keys).

    python backtest.py --days 30
"""

import argparse
import time

import ccxt

from strategy import signal

FEE = 0.001  # Binance spot taker fee, 0.1%


def fetch_history(exchange, symbol, timeframe, days):
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    candles = []
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not batch:
            break
        candles += batch
        since = batch[-1][0] + 1
        if len(batch) < 1000:
            break
        time.sleep(exchange.rateLimit / 1000)
    return candles


def run(candles, fast, slow, order_usdt, stop_loss_pct, take_profit_pct):
    closes = [c[4] for c in candles]
    trades, pnl = [], 0.0
    qty = entry = None
    for i in range(slow + 1, len(closes) + 1):
        price = closes[i - 1]
        sig = signal(closes[:i], fast, slow)
        if qty:
            change = (price - entry) / entry * 100
            reason = ("stop-loss" if change <= -stop_loss_pct else
                      "take-profit" if change >= take_profit_pct else
                      "sma-cross-down" if sig == "sell" else None)
            if reason:
                gain = (price - entry) * qty - (price + entry) * qty * FEE
                pnl += gain
                trades.append((candles[i - 1][0], reason, entry, price, gain))
                qty = entry = None
        elif sig == "buy":
            qty, entry = order_usdt / price, price
    return trades, pnl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="15m")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--fast", type=int, default=9)
    p.add_argument("--slow", type=int, default=21)
    p.add_argument("--order-usdt", type=float, default=50)
    p.add_argument("--stop-loss-pct", type=float, default=3)
    p.add_argument("--take-profit-pct", type=float, default=5)
    args = p.parse_args()

    exchange = ccxt.binance({"enableRateLimit": True})
    candles = fetch_history(exchange, args.symbol, args.timeframe, args.days)
    trades, pnl = run(candles, args.fast, args.slow, args.order_usdt,
                      args.stop_loss_pct, args.take_profit_pct)

    for ts, reason, entry, exit_price, gain in trades:
        print(f"{exchange.iso8601(ts)[:16]}  {reason:<15} {entry:>10.2f} -> {exit_price:>10.2f}  {gain:+7.2f} USDT")
    wins = sum(1 for t in trades if t[4] > 0)
    hold = (candles[-1][4] - candles[0][4]) / candles[0][4] * args.order_usdt
    print(f"\n{len(candles)} candles, {len(trades)} trades, {wins} wins")
    print(f"Strategy P&L (after fees): {pnl:+.2f} USDT")
    print(f"Buy-and-hold {args.order_usdt} USDT instead: {hold:+.2f} USDT")


if __name__ == "__main__":
    main()
