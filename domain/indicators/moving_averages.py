"""Moving average indicators."""


def sma(values: list[float], period: int) -> list[float]:
    """Calculate Simple Moving Average.

    Args:
        values: List of values to calculate SMA over
        period: Number of periods for the moving average

    Returns:
        List of SMA values, with None for insufficient data points

    Example:
        >>> prices = [10, 11, 12, 13, 14, 15]
        >>> sma(prices, 3)
        [None, None, 11.0, 12.0, 13.0, 14.0]
    """
    if not values or period <= 0 or len(values) < period:
        return [None] * len(values) if values else []

    result = [None] * (period - 1)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        # WHY: Filter out None values before summing
        valid_values = [v for v in window if v is not None]
        if len(valid_values) < period:
            result.append(None)
        else:
            result.append(sum(valid_values) / period)

    return result


def ema(values: list[float], period: int) -> list[float]:
    """Calculate Exponential Moving Average.

    Uses standard exponential smoothing with alpha = 2/(period+1).
    Matches PineScript ta.ema behavior.

    Args:
        values: List of values to calculate EMA over
        period: Number of periods for the moving average

    Returns:
        List of EMA values, with None for insufficient data points

    Example:
        >>> prices = [10, 11, 12, 13, 14, 15]
        >>> ema(prices, 3)
        [None, None, 11.0, 12.0, 13.0, 14.0]
    """
    if not values or period <= 0 or len(values) < period:
        return [None] * len(values) if values else []

    alpha = 2.0 / (period + 1)
    result = [None] * (period - 1)

    # WHY: First EMA value is SMA of first 'period' values
    first_ema = sum(values[:period]) / period
    result.append(first_ema)

    # WHY: Subsequent values use exponential smoothing
    for i in range(period, len(values)):
        prev_ema = result[-1]
        new_ema = (values[i] * alpha) + (prev_ema * (1 - alpha))
        result.append(new_ema)

    return result


def wma(values: list[float], period: int) -> list[float]:
    """Calculate Weighted Moving Average.

    Weights are linearly decreasing: period, period-1, ..., 2, 1
    Most recent value has highest weight.

    Args:
        values: List of values to calculate WMA over
        period: Number of periods for the moving average

    Returns:
        List of WMA values, with None for insufficient data points

    Example:
        >>> prices = [10, 11, 12, 13, 14, 15]
        >>> wma(prices, 3)
        [None, None, 11.666..., 12.666..., 13.666..., 14.666...]
    """
    if not values or period <= 0 or len(values) < period:
        return [None] * len(values) if values else []

    result = [None] * (period - 1)

    # WHY: Weights sum needed for normalization
    weights = list(range(1, period + 1))
    weight_sum = sum(weights)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        weighted_sum = sum(v * w for v, w in zip(window, weights))
        result.append(weighted_sum / weight_sum)

    return result
