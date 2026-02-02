"""Relative Strength Index (RSI) indicator."""


def rsi(closes: list[float], period: int = 14) -> list[float]:
    """Calculate RSI using Wilder's smoothing method.

    Matches PineScript ta.rsi behavior. Returns values on 0-100 scale.
    Uses Wilder's smoothing (RMA) rather than simple moving average.

    Args:
        closes: List of closing prices
        period: RSI period (default: 14)

    Returns:
        List of RSI values (0-100), with None for insufficient data points

    Example:
        >>> prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
        ...           45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
        >>> result = rsi(prices, 14)
        >>> result[-1]  # Most recent RSI
        70.46...

    Notes:
        - Wilder's smoothing: New avg = (prev_avg * (period-1) + current) / period
        - First RSI value appears at index (period), not (period-1)
        - Returns None for first (period) values
    """
    if not closes or period <= 0 or len(closes) <= period:
        return [None] * len(closes) if closes else []

    result = [None] * period

    # WHY: Calculate initial gains and losses for first period
    gains = []
    losses = []

    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    # WHY: First average is simple average
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # WHY: Calculate first RSI
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - (100.0 / (1.0 + rs)))

    # WHY: Use Wilder's smoothing for subsequent values
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)

        # Wilder's smoothing formula
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))

    return result
