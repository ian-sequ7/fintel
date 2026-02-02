"""Average True Range (ATR) indicator."""


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14
) -> list[float]:
    """Calculate Average True Range using Wilder's smoothing.

    True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    ATR = Wilder's smoothed average of True Range

    Matches PineScript ta.atr behavior.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        period: ATR period (default: 14)

    Returns:
        List of ATR values, with None for insufficient data points

    Example:
        >>> highs = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
        ...          58, 59, 60, 61, 62]
        >>> lows = [46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
        ...         56, 57, 58, 59, 60]
        >>> closes = [47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
        ...           57, 58, 59, 60, 61]
        >>> result = atr(highs, lows, closes, 14)
        >>> result[-1] > 0
        True

    Notes:
        - First ATR value is simple average of first 'period' true ranges
        - Subsequent values use Wilder's smoothing
        - Returns None for first 'period' values
    """
    if not (highs and lows and closes):
        return []

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have same length")

    if len(closes) <= period:
        return [None] * len(closes)

    result = [None] * period

    # Calculate true ranges
    true_ranges = [None]  # First value has no previous close

    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])

        tr = max(high_low, high_prev_close, low_prev_close)
        true_ranges.append(tr)

    # WHY: First ATR is simple average of first 'period' true ranges
    first_atr = sum(true_ranges[1:period + 1]) / period
    result.append(first_atr)

    # WHY: Use Wilder's smoothing for subsequent values
    atr_value = first_atr

    for i in range(period + 1, len(closes)):
        tr = true_ranges[i]
        # Wilder's smoothing formula
        atr_value = (atr_value * (period - 1) + tr) / period
        result.append(atr_value)

    return result
