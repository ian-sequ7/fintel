"""Momentum indicators."""


def roc(closes: list[float], period: int = 12) -> list[float]:
    """Calculate Rate of Change.

    ROC = 100 * (Close - Close[period ago]) / Close[period ago]

    Args:
        closes: List of closing prices
        period: Lookback period (default: 12)

    Returns:
        List of ROC values (percentage)

    Example:
        >>> prices = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160]
        >>> result = roc(prices, 12)
        >>> result[-1]
        60.0

    Notes:
        - Returns None for first 'period' values
        - Values are percentages (not decimals)
    """
    if not closes or period <= 0 or len(closes) <= period:
        return [None] * len(closes) if closes else []

    result = [None] * period

    for i in range(period, len(closes)):
        past_close = closes[i - period]

        if past_close == 0:
            result.append(None)
        else:
            roc_value = 100.0 * (closes[i] - past_close) / past_close
            result.append(roc_value)

    return result


def cci(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 20
) -> list[float]:
    """Calculate Commodity Channel Index.

    CCI = (Typical Price - SMA of Typical Price) / (0.015 * Mean Deviation)
    Typical Price = (High + Low + Close) / 3

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        period: CCI period (default: 20)

    Returns:
        List of CCI values

    Example:
        >>> highs = [102] * 25
        >>> lows = [98] * 25
        >>> closes = [100] * 25
        >>> result = cci(highs, lows, closes, 20)
        >>> result[-1]
        0.0

    Notes:
        - Returns None for first (period - 1) values
        - Oscillator with no bounded range (typically -200 to +200)
        - 0.015 constant ensures ~70-80% of values fall between -100 and +100
    """
    if not (highs and lows and closes):
        return []

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have same length")

    if len(closes) < period:
        return [None] * len(closes)

    # Calculate typical prices
    typical_prices = [
        (highs[i] + lows[i] + closes[i]) / 3.0
        for i in range(len(closes))
    ]

    result = [None] * (period - 1)

    for i in range(period - 1, len(closes)):
        tp_window = typical_prices[i - period + 1:i + 1]

        # Calculate SMA of typical price
        sma_tp = sum(tp_window) / period

        # Calculate mean deviation
        mean_deviation = sum(abs(tp - sma_tp) for tp in tp_window) / period

        # WHY: Prevent division by zero
        if mean_deviation == 0:
            result.append(0.0)
        else:
            cci_value = (typical_prices[i] - sma_tp) / (0.015 * mean_deviation)
            result.append(cci_value)

    return result


def williams_r(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14
) -> list[float]:
    """Calculate Williams %R.

    Williams %R = -100 * (Highest High - Close) / (Highest High - Lowest Low)

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        period: Lookback period (default: 14)

    Returns:
        List of Williams %R values (-100 to 0)

    Example:
        >>> highs = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64]
        >>> lows = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62]
        >>> closes = [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63]
        >>> result = williams_r(highs, lows, closes, 14)
        >>> -100 <= result[-1] <= 0
        True

    Notes:
        - Returns None for first (period - 1) values
        - Values range from -100 (oversold) to 0 (overbought)
        - Inverse of Stochastic %K (flipped and shifted)
    """
    if not (highs and lows and closes):
        return []

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows, and closes must have same length")

    if len(closes) < period:
        return [None] * len(closes)

    result = [None] * (period - 1)

    for i in range(period - 1, len(closes)):
        period_highs = highs[i - period + 1:i + 1]
        period_lows = lows[i - period + 1:i + 1]

        highest_high = max(period_highs)
        lowest_low = min(period_lows)

        # WHY: Prevent division by zero in flat markets
        if highest_high == lowest_low:
            result.append(-50.0)
        else:
            wr = -100.0 * (highest_high - closes[i]) / (highest_high - lowest_low)
            result.append(wr)

    return result
