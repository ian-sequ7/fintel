"""Volume-based indicators."""

from domain.indicators.moving_averages import sma


def volume_sma(volumes: list[float], period: int = 20) -> list[float]:
    """Calculate Simple Moving Average of volume.

    Args:
        volumes: List of volume values
        period: Period for moving average (default: 20)

    Returns:
        List of volume SMA values, with None for insufficient data points

    Example:
        >>> volumes = [1000000, 1100000, 1200000, 1300000, 1400000,
        ...            1500000, 1600000, 1700000, 1800000, 1900000,
        ...            2000000, 2100000, 2200000, 2300000, 2400000,
        ...            2500000, 2600000, 2700000, 2800000, 2900000, 3000000]
        >>> result = volume_sma(volumes, 20)
        >>> result[-1]
        2000000.0
    """
    return sma(volumes, period)


def volume_surge(
    volumes: list[float],
    period: int = 20,
    threshold: float = 2.0
) -> list[bool]:
    """Detect volume surges relative to average.

    A surge is detected when current volume exceeds the SMA by the threshold multiplier.

    Args:
        volumes: List of volume values
        period: Period for moving average (default: 20)
        threshold: Multiplier for surge detection (default: 2.0)

    Returns:
        List of boolean values indicating surge detection
        Returns False for periods with insufficient data

    Example:
        >>> volumes = [1000000] * 20 + [2500000]
        >>> result = volume_surge(volumes, period=20, threshold=2.0)
        >>> result[-1]  # Last value is a surge
        True
        >>> result[0]  # First values have insufficient data
        False

    Notes:
        - Returns False for first 'period' values (insufficient data)
        - Surge detected when: current_volume > (volume_sma * threshold)
    """
    if not volumes:
        return []

    vol_sma = volume_sma(volumes, period)

    result = []
    for i, vol in enumerate(volumes):
        if vol_sma[i] is None:
            result.append(False)
        else:
            result.append(vol > (vol_sma[i] * threshold))

    return result
