"""Utility functions for technical analysis."""

from typing import Optional


def crossover(series1: list[float], series2: list[float]) -> list[bool]:
    """Detect when series1 crosses above series2.

    Args:
        series1: First data series
        series2: Second data series

    Returns:
        List of boolean values indicating crossover points

    Example:
        >>> fast = [10, 11, 12, 11, 10]
        >>> slow = [11, 11, 11, 11, 11]
        >>> crossover(fast, slow)
        [False, False, True, False, False]

    Notes:
        - Returns True when series1[i-1] <= series2[i-1] and series1[i] > series2[i]
        - First element is always False (no previous value to compare)
        - Handles None values gracefully
    """
    if not series1 or not series2:
        return []

    if len(series1) != len(series2):
        raise ValueError("series1 and series2 must have same length")

    result = [False]

    for i in range(1, len(series1)):
        # WHY: Skip comparison if either value is None
        if (series1[i] is None or series2[i] is None or
            series1[i - 1] is None or series2[i - 1] is None):
            result.append(False)
        else:
            # Crossover: was below or equal, now above
            result.append(series1[i - 1] <= series2[i - 1] and series1[i] > series2[i])

    return result


def crossunder(series1: list[float], series2: list[float]) -> list[bool]:
    """Detect when series1 crosses below series2.

    Args:
        series1: First data series
        series2: Second data series

    Returns:
        List of boolean values indicating crossunder points

    Example:
        >>> fast = [12, 11, 10, 11, 12]
        >>> slow = [11, 11, 11, 11, 11]
        >>> crossunder(fast, slow)
        [False, False, True, False, False]

    Notes:
        - Returns True when series1[i-1] >= series2[i-1] and series1[i] < series2[i]
        - First element is always False (no previous value to compare)
        - Handles None values gracefully
    """
    if not series1 or not series2:
        return []

    if len(series1) != len(series2):
        raise ValueError("series1 and series2 must have same length")

    result = [False]

    for i in range(1, len(series1)):
        if (series1[i] is None or series2[i] is None or
            series1[i - 1] is None or series2[i - 1] is None):
            result.append(False)
        else:
            # Crossunder: was above or equal, now below
            result.append(series1[i - 1] >= series2[i - 1] and series1[i] < series2[i])

    return result


def highest(values: list[float], period: int) -> list[float]:
    """Find highest value over rolling period.

    Args:
        values: List of values
        period: Lookback period

    Returns:
        List of highest values for each period

    Example:
        >>> prices = [10, 12, 11, 15, 14, 13]
        >>> highest(prices, 3)
        [None, None, 12, 15, 15, 15]

    Notes:
        - Returns None for first (period - 1) values
        - Handles None values in input
    """
    if not values or period <= 0:
        return [None] * len(values) if values else []

    if len(values) < period:
        return [None] * len(values)

    result = [None] * (period - 1)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        # Filter out None values
        valid_values = [v for v in window if v is not None]

        if not valid_values:
            result.append(None)
        else:
            result.append(max(valid_values))

    return result


def lowest(values: list[float], period: int) -> list[float]:
    """Find lowest value over rolling period.

    Args:
        values: List of values
        period: Lookback period

    Returns:
        List of lowest values for each period

    Example:
        >>> prices = [10, 12, 11, 15, 14, 13]
        >>> lowest(prices, 3)
        [None, None, 10, 11, 11, 13]

    Notes:
        - Returns None for first (period - 1) values
        - Handles None values in input
    """
    if not values or period <= 0:
        return [None] * len(values) if values else []

    if len(values) < period:
        return [None] * len(values)

    result = [None] * (period - 1)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        valid_values = [v for v in window if v is not None]

        if not valid_values:
            result.append(None)
        else:
            result.append(min(valid_values))

    return result


def change(values: list[float], period: int = 1) -> list[float]:
    """Calculate change over specified period.

    Args:
        values: List of values
        period: Lookback period (default: 1)

    Returns:
        List of change values (current - past)

    Example:
        >>> prices = [10, 11, 12, 11, 10]
        >>> change(prices, 1)
        [None, 1, 1, -1, -1]
        >>> change(prices, 2)
        [None, None, 2, 0, -2]

    Notes:
        - Returns None for first 'period' values
        - change[i] = values[i] - values[i - period]
    """
    if not values or period <= 0:
        return [None] * len(values) if values else []

    if len(values) <= period:
        return [None] * len(values)

    result = [None] * period

    for i in range(period, len(values)):
        if values[i] is None or values[i - period] is None:
            result.append(None)
        else:
            result.append(values[i] - values[i - period])

    return result


def percent_change(values: list[float], period: int = 1) -> list[float]:
    """Calculate percentage change over specified period.

    Args:
        values: List of values
        period: Lookback period (default: 1)

    Returns:
        List of percentage change values (0-100 scale)

    Example:
        >>> prices = [100, 110, 121, 110, 100]
        >>> percent_change(prices, 1)
        [None, 10.0, 10.0, -9.090..., -9.090...]

    Notes:
        - Returns None for first 'period' values
        - Returns None if past value is zero (avoid division by zero)
        - Formula: 100 * (current - past) / past
    """
    if not values or period <= 0:
        return [None] * len(values) if values else []

    if len(values) <= period:
        return [None] * len(values)

    result = [None] * period

    for i in range(period, len(values)):
        if values[i] is None or values[i - period] is None or values[i - period] == 0:
            result.append(None)
        else:
            pct = 100.0 * (values[i] - values[i - period]) / values[i - period]
            result.append(pct)

    return result
