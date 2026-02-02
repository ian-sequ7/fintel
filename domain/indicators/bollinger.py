"""Bollinger Bands indicator."""

from domain.indicators.moving_averages import sma


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[list[float], list[float], list[float]]:
    """Calculate Bollinger Bands.

    Upper Band = SMA + (std_dev * standard_deviation)
    Middle Band = SMA
    Lower Band = SMA - (std_dev * standard_deviation)

    Args:
        closes: List of closing prices
        period: Period for SMA and standard deviation (default: 20)
        std_dev: Number of standard deviations for bands (default: 2.0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
        Each is a list with None for insufficient data points

    Example:
        >>> prices = [20, 21, 22, 23, 24, 25, 24, 23, 22, 21,
        ...           20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
        ...           30, 29, 28, 27, 26]
        >>> upper, middle, lower = bollinger_bands(prices, period=20)
        >>> middle[-1]  # Most recent SMA
        24.95
    """
    if not closes or period <= 0 or len(closes) < period:
        n = len(closes) if closes else 0
        return ([None] * n, [None] * n, [None] * n)

    # Calculate middle band (SMA)
    middle_band = sma(closes, period)

    upper_band = [None] * (period - 1)
    lower_band = [None] * (period - 1)

    # Calculate standard deviation and bands for each valid period
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]

        # Calculate standard deviation
        mean = middle_band[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5

        upper_band.append(mean + (std_dev * std))
        lower_band.append(mean - (std_dev * std))

    return (upper_band, middle_band, lower_band)
