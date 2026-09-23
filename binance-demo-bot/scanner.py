"""Scan the most active Binance USDT pairs and show simple signals.

Read-only: uses public market data, needs no API keys and never places orders.

    python scanner.py                   # one scan of the top 30 coins by volume
    python scanner.py --watch 120       # rescan every 2 minutes
    python scanner.py --timeframe 1h --top 50
"""

import argparse
import csv
import os
import time
from datetime import datetime

import ccxt

from indicators import atr_pct, rsi, volume_ratio
from strategy import sma, signal

STABLECOINS = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "EUR", "AEUR", "EURI",
               "USDE", "PYUSD", "USD1", "RLUSD", "BFUSD", "XUSD", "UST", "USTC"}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def candidate_pairs(exchange, top, min_volume):
    tickers = exchange.fetch_tickers()
    pairs = []
    for symbol, t in tickers.items():
        market = exchange.markets.get(symbol)
        if not market or not market.get("spot") or not market.get("active") or market["quote"] != "USDT":
            continue
        base = market["base"]
        if base in STABLECOINS or base.endswith(LEVERAGED_SUFFIXES):
            continue
        if (t.get("quoteVolume") or 0) < min_volume or not t.get("last"):
            continue
        pairs.append(t)
    pairs.sort(key=lambda t: t["quoteVolume"], reverse=True)
    return pairs[:top]


def analyse(exchange, ticker, timeframe, fast, slow):
    candles = exchange.fetch_ohlcv(ticker["symbol"], timeframe, limit=101)[:-1]  # closed candles only
    closes = [c[4] for c in candles]
    if len(closes) < max(slow + 1, 30):
        return None
    row = {
        "symbol": ticker["symbol"],
        "price": ticker["last"],
        "change_24h": ticker.get("percentage") or 0.0,
        "volume_m": ticker["quoteVolume"] / 1e6,
        "trend": "up" if sma(closes, fast) > sma(closes, slow) else "down",
        "cross": signal(closes, fast, slow),
        "rsi": rsi(closes),
        "atr_pct": atr_pct(candles),
        "vol_x": volume_ratio(candles) or 0.0,
    }
    notes = []
    if row["cross"] == "buy":
        notes.append("NEW CROSS UP")
    elif row["cross"] == "sell":
        notes.append("new cross down")
    if row["rsi"] >= 70:
        notes.append("overbought")
    elif row["rsi"] <= 30:
        notes.append("oversold")
    if row["vol_x"] >= 2:
        notes.append("volume spike")
    if row["change_24h"] >= 15:
        notes.append("already pumped")
    elif row["change_24h"] <= -15:
        notes.append("crashing")
    if row["atr_pct"] >= 2:
        notes.append("very volatile")
    row["notes"] = ", ".join(notes)
    # Ranking: fresh cross up first, then uptrends that aren't overbought, then volume surge.
    # Overbought or already-pumped coins are pushed down so the list doesn't encourage chasing.
    chasing = row["rsi"] >= 70 or row["change_24h"] >= 15
    row["clean_setup"] = row["trend"] == "up" and not chasing
    row["score"] = ((row["cross"] == "buy") * 100
                    + row["clean_setup"] * 10
                    + min(row["vol_x"], 5)
                    - chasing * 50)
    return row


def print_table(rows, timeframe):
    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {len(rows)} coins  |  {timeframe} candles\n")
    header = f"{'#':>2}  {'Coin':<12} {'Price':>12} {'24h %':>7} {'Vol 24h':>9} {'Trend':>5} {'RSI':>4} {'Move':>6} {'Vol x':>5}  Notes"
    print(header)
    print("-" * len(header) + "-" * 20)
    for i, r in enumerate(rows, 1):
        print(f"{i:>2}  {r['symbol']:<12} {r['price']:>12.6g} {r['change_24h']:>+7.1f} {r['volume_m']:>8.0f}M "
              f"{r['trend']:>5} {r['rsi']:>4.0f} {r['atr_pct']:>5.2f}% {r['vol_x']:>5.1f}  {r['notes']}")
    print("\nMove  = average price move per candle. Vol x = last candle's volume vs normal.")
    print("These are signals, not predictions. 'already pumped' and 'very volatile' coins can drop just as fast.")
    if rows and rows[0]["clean_setup"]:
        top = rows[0]
        stop = max(1.0, round(top["atr_pct"] * 2, 1))
        print(f"\nTo demo-trade #1 (dry run first, stop-loss about 2x its usual move):")
        print(f"  python bot.py --symbol {top['symbol']} --timeframe {timeframe} --stop-loss-pct {stop} --dry-run")
    else:
        print("\nNo clean setup right now (uptrend that isn't overbought or already pumped). Waiting is fine.")


def save_csv(rows, path):
    new_file = not os.path.exists(path)
    fields = ["time", "symbol", "price", "change_24h", "volume_m", "trend", "rsi", "atr_pct", "vol_x", "notes"]
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        now = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            writer.writerow({**r, "time": now})


def scan(exchange, args):
    rows = []
    for ticker in candidate_pairs(exchange, args.top, args.min_volume * 1e6):
        try:
            row = analyse(exchange, ticker, args.timeframe, args.fast, args.slow)
        except ccxt.BaseError as e:
            print(f"skipped {ticker['symbol']}: {e}")
            continue
        if row and (not args.only_signals or row["cross"] == "buy"):
            rows.append(row)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="15m")
    p.add_argument("--top", type=int, default=30, help="how many of the highest-volume coins to check")
    p.add_argument("--min-volume", type=float, default=5, help="minimum 24h volume in million USDT")
    p.add_argument("--fast", type=int, default=9)
    p.add_argument("--slow", type=int, default=21)
    p.add_argument("--only-signals", action="store_true", help="show only coins with a new cross up")
    p.add_argument("--watch", type=int, default=0, help="rescan every N seconds (0 = scan once)")
    p.add_argument("--csv", help="also append results to this CSV file")
    args = p.parse_args()

    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    exchange.load_markets()
    while True:
        try:
            rows = scan(exchange, args)
            print_table(rows, args.timeframe)
            if args.csv:
                save_csv(rows, args.csv)
        except ccxt.NetworkError as e:
            print(f"Network error, will retry: {e}")
        if not args.watch:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
