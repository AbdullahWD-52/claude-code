"""Binance DEMO trading bot (fake money only).

Trades one spot pair with a moving-average crossover. It only talks to
Binance Demo Trading (demo.binance.com) or the Spot Testnet
(testnet.binance.vision); there is deliberately no live-money mode.

    python bot.py --dry-run      # print signals, place no orders
    python bot.py                # trade on Binance Demo Trading
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

import ccxt

from strategy import signal

TRADES_FILE = "trades.csv"


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def make_exchange(mode):
    exchange = ccxt.binance({
        "apiKey": os.environ.get("BINANCE_DEMO_API_KEY", ""),
        "secret": os.environ.get("BINANCE_DEMO_API_SECRET", ""),
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    if mode == "demo":
        exchange.enable_demo_trading(True)
    else:
        exchange.set_sandbox_mode(True)
    api_url = str(exchange.urls["api"])
    if "demo" not in api_url and "testnet" not in api_url:
        sys.exit(f"Refusing to run: API is not a demo/testnet endpoint ({api_url})")
    return exchange


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def record_trade(side, symbol, qty, price, reason):
    new_file = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time_utc", "side", "symbol", "qty", "price", "usdt", "reason"])
        writer.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         side, symbol, qty, price, round(qty * price, 2), reason])


def closed_closes(exchange, symbol, timeframe, limit):
    candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit + 1)
    return [c[4] for c in candles[:-1]]  # drop the still-open candle


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["demo", "testnet"], default="demo")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="15m")
    p.add_argument("--fast", type=int, default=9)
    p.add_argument("--slow", type=int, default=21)
    p.add_argument("--order-usdt", type=float, default=50, help="USDT spent per buy")
    p.add_argument("--stop-loss-pct", type=float, default=3, help="sell if price falls this %% below entry")
    p.add_argument("--take-profit-pct", type=float, default=5, help="sell if price rises this %% above entry")
    p.add_argument("--max-loss-usdt", type=float, default=100, help="stop the bot after losing this much")
    p.add_argument("--interval", type=int, default=60, help="seconds between checks")
    p.add_argument("--dry-run", action="store_true", help="log signals without placing orders")
    p.add_argument("--once", action="store_true", help="run a single check and exit")
    args = p.parse_args()

    load_env()
    exchange = make_exchange(args.mode)
    exchange.load_markets()
    if args.symbol not in exchange.markets:
        sys.exit(f"Unknown symbol {args.symbol}")
    if not args.dry_run and not exchange.apiKey:
        sys.exit("Missing BINANCE_DEMO_API_KEY / BINANCE_DEMO_API_SECRET (see .env.example)")

    base = exchange.markets[args.symbol]["base"]
    log(f"Mode={args.mode} symbol={args.symbol} tf={args.timeframe} "
        f"SMA{args.fast}/{args.slow} order={args.order_usdt} USDT dry_run={args.dry_run}")

    # The bot only ever sells what it bought itself, never the rest of the balance.
    position_qty = 0.0
    entry_price = None
    realized_pnl = 0.0

    def sell(price, reason):
        nonlocal position_qty, entry_price, realized_pnl
        qty = float(exchange.amount_to_precision(args.symbol, position_qty))
        if not args.dry_run:
            order = exchange.create_market_sell_order(args.symbol, qty)
            price = order.get("average") or price
        pnl = (price - entry_price) * qty
        realized_pnl += pnl
        log(f"SELL {qty} {base} @ {price:.2f} ({reason}) pnl={pnl:+.2f} total={realized_pnl:+.2f} USDT")
        record_trade("sell", args.symbol, qty, price, reason)
        position_qty, entry_price = 0.0, None

    while True:
        try:
            closes = closed_closes(exchange, args.symbol, args.timeframe, args.slow + 1)
            price = exchange.fetch_ticker(args.symbol)["last"]
            sig = signal(closes, args.fast, args.slow)

            if position_qty > 0:
                change = (price - entry_price) / entry_price * 100
                if change <= -args.stop_loss_pct:
                    sell(price, "stop-loss")
                elif change >= args.take_profit_pct:
                    sell(price, "take-profit")
                elif sig == "sell":
                    sell(price, "sma-cross-down")
            elif sig == "buy":
                qty = float(exchange.amount_to_precision(args.symbol, args.order_usdt / price))
                if not args.dry_run:
                    order = exchange.create_market_buy_order(args.symbol, qty)
                    price = order.get("average") or price
                    qty = order.get("filled") or qty
                position_qty, entry_price = qty, price
                log(f"BUY {qty} {base} @ {price:.2f} (sma-cross-up)")
                record_trade("buy", args.symbol, qty, price, "sma-cross-up")
            else:
                held = f" holding {position_qty} {base} from {entry_price:.2f}" if position_qty else ""
                log(f"price={price:.2f} signal={sig or '-'}{held}")

            open_pnl = (price - entry_price) * position_qty if position_qty else 0.0
            if realized_pnl + open_pnl <= -args.max_loss_usdt:
                if position_qty:
                    sell(price, "max-loss")
                log(f"Max loss of {args.max_loss_usdt} USDT reached. Stopping.")
                break
        except ccxt.NetworkError as e:
            log(f"Network error, will retry: {e}")
        except ccxt.ExchangeError as e:
            log(f"Exchange error: {e}")

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user (Ctrl+C). Any open demo position is left as is.")
