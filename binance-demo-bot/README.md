# Binance Demo Trading Bot

A small bot that trades one coin pair on **Binance Demo Trading**, where the money is fake. It has no real-money mode. Use it to see how a strategy behaves before you decide anything.

## What it does

- Every minute it checks the price of `BTC/USDT` on 15-minute candles.
- **Buy:** when the 9-candle average crosses above the 21-candle average, it spends 50 USDT.
- **Sell** (whichever comes first):
  - the price drops 3% below the buy price (stop-loss)
  - the price rises 5% above the buy price (take-profit)
  - the 9-candle average crosses back below the 21-candle average
- **Safety:** it stops completely once it has lost 100 USDT in total (if you decline that last sell, the coin stays in your demo account). It only ever sells what it bought itself.
- **It asks you before every order.** Nothing is bought or sold until you type `y` and press Enter. Anything else (or just Enter) means no:
  ```
  APPROVAL NEEDED: BUY 0.00046 BTC for ~50.00 USDT at ~108000.00. Place this order? [y/N]
  ```
  If you decline a buy, it skips that signal. If you decline a sell, it keeps holding and asks again at the next check while the sell condition is still true. While it waits for your answer it does nothing else, so a decision you leave unanswered can go stale as the price moves.
- Every trade is saved to `trades.csv`.

All of these numbers can be changed with options (see below).

## Setup on your PC (Windows, Mac or Linux)

1. Install Python 3.10 or newer from https://www.python.org/downloads/. On Windows, tick **"Add Python to PATH"**.
2. Open a terminal in this `binance-demo-bot` folder and run:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # Mac / Linux
   pip install -r requirements.txt
   ```
3. Get **demo** API keys:
   - Log in at https://demo.binance.com
   - Go to **API Management** (https://demo.binance.com/en/my/settings/api-management) and create a key.
4. Copy `.env.example` to a new file named `.env` and paste the key and secret into it. Never share this file or commit it; it's already in `.gitignore`.

## Run it

```
python backtest.py --days 30   # 1. how would it have done over the last 30 days? (no keys needed)
python bot.py --dry-run        # 2. watch live signals, no orders placed
python bot.py                  # 3. trade with fake money on Binance Demo
```

Press **Ctrl+C** to stop.

Useful options:

| Option | Default | Meaning |
|---|---|---|
| `--symbol` | `BTC/USDT` | pair to trade |
| `--timeframe` | `15m` | candle size (`5m`, `1h`, `4h`, ...) |
| `--fast` / `--slow` | `9` / `21` | moving-average lengths |
| `--order-usdt` | `50` | USDT spent per buy |
| `--stop-loss-pct` | `3` | sell if price falls this % below buy |
| `--take-profit-pct` | `5` | sell if price rises this % above buy |
| `--max-loss-usdt` | `100` | stop the bot after losing this much |
| `--mode testnet` | `demo` | use testnet.binance.vision keys instead |

## Things to know

- **A good backtest doesn't guarantee profit.** Moving-average strategies often lose money in sideways markets, and fees (0.1% per trade) add up. Compare the result with the "buy-and-hold" line the backtest prints.
- If you stop the bot while it holds a coin, that position stays open in your demo account. The bot doesn't pick it up again when restarted.
- Demo prices and order fills can differ a bit from real Binance.
- Run the demo for at least a few weeks before thinking about real money. If you do go live later, use a key that **can't withdraw**, limit it to your IP address, and start with an amount you can afford to lose.
