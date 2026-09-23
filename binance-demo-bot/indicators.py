"""Indicator math used by the scanner. Candles are ccxt OHLCV rows:
[timestamp, open, high, low, close, volume]."""


def rsi(closes, length=14):
    """Wilder's Relative Strength Index, 0-100. Above 70 = overbought, below 30 = oversold."""
    if len(closes) < length + 1:
        return None
    gains, losses = 0.0, 0.0
    for prev, cur in zip(closes[:length], closes[1:length + 1]):
        change = cur - prev
        gains += max(change, 0)
        losses += max(-change, 0)
    avg_gain, avg_loss = gains / length, losses / length
    for prev, cur in zip(closes[length:], closes[length + 1:]):
        change = cur - prev
        avg_gain = (avg_gain * (length - 1) + max(change, 0)) / length
        avg_loss = (avg_loss * (length - 1) + max(-change, 0)) / length
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def atr_pct(candles, length=14):
    """Average True Range as a % of the last close: how far price typically moves per candle."""
    if len(candles) < length + 1:
        return None
    ranges = []
    for prev, cur in zip(candles[-length - 1:-1], candles[-length:]):
        high, low, prev_close = cur[2], cur[3], prev[4]
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(ranges) / length / candles[-1][4] * 100


def volume_ratio(candles, length=20):
    """Last candle's volume divided by the average of the `length` candles before it."""
    if len(candles) < length + 1:
        return None
    avg = sum(c[5] for c in candles[-length - 1:-1]) / length
    return candles[-1][5] / avg if avg else None
