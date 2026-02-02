"""Stochastic Oscillator indicators."""

from domain.indicators.moving_averages import sma


def stochastic(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    d_period: int = 3
) -> tuple[list[float], list[float]]:
    """Calculate Stochastic Oscillator (%K and %D).

    %K = 100 * (Close - Lowest Low) / (Highest High - Lowest Low)
    %D = SMA of %K

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        k_period: Lookback period for %K (default: 14)
        d_period: SMA period for %D (default: 3)

    Returns:
        Tuple of (k_values, d_values)
        Each is a list with None for insufficient data points

    Example:
        >>> highs = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64]
        >>> lows = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62]
        >>> closes = [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63]
        >>> k, d = stochastic(highs, lows, closes, 14, 3)
        >>> k[-1]  # Most recent %K
        50.0

    Notes:
        - Returns values on 0-100 scale
        - %K requires k_period values
        - %D requires additional d_period values
    """
    if not (highs and lows and closes):
        return ([], [])

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have same length")

    if len(closes) < k_period:
        n = len(closes)
        return ([None] * n, [None] * n)

    k_values = [None] * (k_period - 1)

    # Calculate %K for each period
    for i in range(k_period - 1, len(closes)):
        period_highs = highs[i - k_period + 1:i + 1]
        period_lows = lows[i - k_period + 1:i + 1]

        highest_high = max(period_highs)
        lowest_low = min(period_lows)

        # WHY: Prevent division by zero in flat markets
        if highest_high == lowest_low:
            k_values.append(50.0)
        else:
            k = 100.0 * (closes[i] - lowest_low) / (highest_high - lowest_low)
            k_values.append(k)

    # Calculate %D (SMA of %K)
    d_values = sma(k_values, d_period)

    return (k_values, d_values)
