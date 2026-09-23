"""Moving-average crossover strategy, shared by the bot and the backtest."""


def sma(values, length):
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def signal(closes, fast, slow):
    """Return "buy", "sell" or None based on a fast/slow SMA crossover.

    A crossover is detected by comparing the last closed candle with the
    candle before it, so a signal fires once per cross, not on every tick.
    """
    if len(closes) < slow + 1:
        return None
    prev_fast, prev_slow = sma(closes[:-1], fast), sma(closes[:-1], slow)
    cur_fast, cur_slow = sma(closes, fast), sma(closes, slow)
    if prev_fast <= prev_slow and cur_fast > cur_slow:
        return "buy"
    if prev_fast >= prev_slow and cur_fast < cur_slow:
        return "sell"
    return None
