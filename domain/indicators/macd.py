"""MACD (Moving Average Convergence Divergence) indicator."""

from domain.indicators.moving_averages import ema


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> tuple[list[float], list[float], list[float]]:
    """Calculate MACD indicator.

    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line, signal periods)
    Histogram = MACD Line - Signal Line

    Args:
        closes: List of closing prices
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)

    Returns:
        Tuple of (macd_line, signal_line, histogram)
        Each is a list with None for insufficient data points

    Example:
        >>> prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
        ...           21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
        ...           31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
        >>> macd_line, signal_line, histogram = macd(prices)
        >>> len([x for x in macd_line if x is not None]) > 0
        True

    Notes:
        - MACD line requires 'slow' periods of data
        - Signal line requires additional 'signal' periods
        - Histogram is simply the difference between MACD and Signal
    """
    if not closes or len(closes) < slow:
        n = len(closes) if closes else 0
        return ([None] * n, [None] * n, [None] * n)

    # Calculate fast and slow EMAs
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    # Calculate MACD line
    macd_line = []
    for i in range(len(closes)):
        if fast_ema[i] is None or slow_ema[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(fast_ema[i] - slow_ema[i])

    # WHY: Signal line is EMA of MACD line (excluding None values)
    # We need to handle None values specially
    signal_line = [None] * len(closes)
    histogram = [None] * len(closes)

    # Find first non-None MACD value
    first_valid_idx = None
    for i, val in enumerate(macd_line):
        if val is not None:
            first_valid_idx = i
            break

    if first_valid_idx is None:
        return (macd_line, signal_line, histogram)

    # Calculate signal line starting from first valid MACD
    macd_values = [v for v in macd_line[first_valid_idx:] if v is not None]
    signal_values = ema(macd_values, signal)

    # Map signal values back to original indices
    signal_idx = 0
    for i in range(first_valid_idx, len(closes)):
        if macd_line[i] is not None and signal_idx < len(signal_values):
            signal_line[i] = signal_values[signal_idx]
            signal_idx += 1

    # Calculate histogram
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    return (macd_line, signal_line, histogram)
