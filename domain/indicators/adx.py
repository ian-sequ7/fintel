"""Average Directional Index (ADX) and related indicators."""


def _wilder_smooth(values: list[float], period: int) -> list[float]:
    """Apply Wilder's smoothing to a list of values.

    Internal helper for ADX calculation.

    Args:
        values: List of values to smooth
        period: Smoothing period

    Returns:
        List of smoothed values with None for insufficient data
    """
    if not values or len(values) < period:
        return [None] * len(values) if values else []

    result = [None] * (period - 1)

    # WHY: Filter out None values for first average
    first_period_values = [v for v in values[:period] if v is not None]
    if len(first_period_values) < period:
        return [None] * len(values)

    # First smoothed value is simple average
    first_smooth = sum(first_period_values) / period
    result.append(first_smooth)

    # Subsequent values use Wilder's smoothing
    smooth_value = first_smooth
    for i in range(period, len(values)):
        if values[i] is None:
            result.append(None)
        else:
            smooth_value = (smooth_value * (period - 1) + values[i]) / period
            result.append(smooth_value)

    return result


def adx(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14
) -> tuple[list[float], list[float], list[float]]:
    """Calculate Average Directional Index (ADX), +DI, and -DI.

    ADX measures trend strength (0-100 scale).
    +DI and -DI indicate directional movement.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        period: ADX period (default: 14)

    Returns:
        Tuple of (adx_values, plus_di, minus_di)
        Each is a list with None for insufficient data points

    Example:
        >>> highs = [50] * 30
        >>> lows = [48] * 30
        >>> closes = [49] * 30
        >>> adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)
        >>> len(adx_vals) == 30
        True

    Notes:
        - ADX requires 2*period - 1 values to calculate
        - Uses Wilder's smoothing throughout
        - Returns values on 0-100 scale
    """
    if not (highs and lows and closes):
        return ([], [], [])

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have same length")

    n = len(closes)
    if n < 2 * period:
        return ([None] * n, [None] * n, [None] * n)

    # Calculate +DM and -DM
    plus_dm = [None]
    minus_dm = [None]

    for i in range(1, n):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]

        # WHY: +DM is upward movement, -DM is downward movement
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
            minus_dm.append(0.0)
        elif low_diff > high_diff and low_diff > 0:
            plus_dm.append(0.0)
            minus_dm.append(low_diff)
        else:
            plus_dm.append(0.0)
            minus_dm.append(0.0)

    # Calculate True Range
    tr = [None]
    for i in range(1, n):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])
        tr.append(max(high_low, high_prev_close, low_prev_close))

    # Smooth +DM, -DM, and TR using Wilder's smoothing
    smoothed_plus_dm = _wilder_smooth(plus_dm, period)
    smoothed_minus_dm = _wilder_smooth(minus_dm, period)
    smoothed_tr = _wilder_smooth(tr, period)

    # Calculate +DI and -DI
    plus_di = []
    minus_di = []

    for i in range(n):
        if smoothed_tr[i] is None or smoothed_tr[i] == 0:
            plus_di.append(None)
            minus_di.append(None)
        else:
            plus_di.append(100.0 * smoothed_plus_dm[i] / smoothed_tr[i])
            minus_di.append(100.0 * smoothed_minus_dm[i] / smoothed_tr[i])

    # Calculate DX
    dx = []
    for i in range(n):
        if plus_di[i] is None or minus_di[i] is None:
            dx.append(None)
        else:
            di_sum = plus_di[i] + minus_di[i]
            if di_sum == 0:
                dx.append(0.0)
            else:
                dx.append(100.0 * abs(plus_di[i] - minus_di[i]) / di_sum)

    # Smooth DX to get ADX
    adx_values = _wilder_smooth(dx, period)

    return (adx_values, plus_di, minus_di)
