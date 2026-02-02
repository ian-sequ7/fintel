"""Pivot Points and support/resistance levels."""

from typing import NamedTuple


class PivotLevels(NamedTuple):
    """Pivot point levels for a trading period."""
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


def standard_pivots(high: float, low: float, close: float) -> PivotLevels:
    """Calculate Standard Pivot Points.

    Standard pivot points are used to identify potential support and resistance levels.

    Args:
        high: Period high price
        low: Period low price
        close: Period close price

    Returns:
        PivotLevels with pivot, resistance (R1-R3), and support (S1-S3) levels

    Example:
        >>> levels = standard_pivots(high=105, low=95, close=100)
        >>> levels.pivot
        100.0
        >>> levels.r1
        105.0

    Notes:
        - Pivot = (High + Low + Close) / 3
        - R1 = (2 * Pivot) - Low
        - S1 = (2 * Pivot) - High
        - R2 = Pivot + (High - Low)
        - S2 = Pivot - (High - Low)
        - R3 = High + 2 * (Pivot - Low)
        - S3 = Low - 2 * (High - Pivot)
    """
    pivot = (high + low + close) / 3.0

    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high

    r2 = pivot + (high - low)
    s2 = pivot - (high - low)

    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)

    return PivotLevels(
        pivot=pivot,
        r1=r1,
        r2=r2,
        r3=r3,
        s1=s1,
        s2=s2,
        s3=s3
    )


def fibonacci_pivots(high: float, low: float, close: float) -> PivotLevels:
    """Calculate Fibonacci Pivot Points.

    Uses Fibonacci ratios (0.382, 0.618, 1.000) for support/resistance levels.

    Args:
        high: Period high price
        low: Period low price
        close: Period close price

    Returns:
        PivotLevels with pivot and Fibonacci-based support/resistance levels

    Example:
        >>> levels = fibonacci_pivots(high=105, low=95, close=100)
        >>> levels.pivot
        100.0

    Notes:
        - Pivot = (High + Low + Close) / 3
        - R1 = Pivot + 0.382 * (High - Low)
        - S1 = Pivot - 0.382 * (High - Low)
        - R2 = Pivot + 0.618 * (High - Low)
        - S2 = Pivot - 0.618 * (High - Low)
        - R3 = Pivot + 1.000 * (High - Low)
        - S3 = Pivot - 1.000 * (High - Low)
    """
    pivot = (high + low + close) / 3.0
    range_hl = high - low

    r1 = pivot + 0.382 * range_hl
    s1 = pivot - 0.382 * range_hl

    r2 = pivot + 0.618 * range_hl
    s2 = pivot - 0.618 * range_hl

    r3 = pivot + 1.000 * range_hl
    s3 = pivot - 1.000 * range_hl

    return PivotLevels(
        pivot=pivot,
        r1=r1,
        r2=r2,
        r3=r3,
        s1=s1,
        s2=s2,
        s3=s3
    )


def camarilla_pivots(high: float, low: float, close: float) -> PivotLevels:
    """Calculate Camarilla Pivot Points.

    Camarilla pivots use tighter levels based on a multiplier of 1.1/12.

    Args:
        high: Period high price
        low: Period low price
        close: Period close price

    Returns:
        PivotLevels with Camarilla support/resistance levels

    Example:
        >>> levels = camarilla_pivots(high=105, low=95, close=100)
        >>> levels.pivot
        100.0

    Notes:
        - Pivot = (High + Low + Close) / 3
        - R1 = Close + 1.1/12 * (High - Low)
        - S1 = Close - 1.1/12 * (High - Low)
        - R2 = Close + 1.1/6 * (High - Low)
        - S2 = Close - 1.1/6 * (High - Low)
        - R3 = Close + 1.1/4 * (High - Low)
        - S3 = Close - 1.1/4 * (High - Low)
    """
    pivot = (high + low + close) / 3.0
    range_hl = high - low

    r1 = close + (1.1 / 12.0) * range_hl
    s1 = close - (1.1 / 12.0) * range_hl

    r2 = close + (1.1 / 6.0) * range_hl
    s2 = close - (1.1 / 6.0) * range_hl

    r3 = close + (1.1 / 4.0) * range_hl
    s3 = close - (1.1 / 4.0) * range_hl

    return PivotLevels(
        pivot=pivot,
        r1=r1,
        r2=r2,
        r3=r3,
        s1=s1,
        s2=s2,
        s3=s3
    )
