"""Volume Weighted Average Price (VWAP) indicator."""


def vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float]
) -> list[float]:
    """Calculate Volume Weighted Average Price.

    VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume)
    Typical Price = (High + Low + Close) / 3

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        volumes: List of volume values

    Returns:
        List of VWAP values

    Example:
        >>> highs = [102, 103, 104]
        >>> lows = [100, 101, 102]
        >>> closes = [101, 102, 103]
        >>> volumes = [1000, 1500, 1200]
        >>> result = vwap(highs, lows, closes, volumes)
        >>> len(result) == 3
        True

    Notes:
        - VWAP typically resets daily in real trading
        - This implementation calculates cumulative VWAP over entire period
        - All input lists must have same length
    """
    if not (highs and lows and closes and volumes):
        return []

    if not (len(highs) == len(lows) == len(closes) == len(volumes)):
        raise ValueError("All input lists must have same length")

    result = []
    cumulative_tp_volume = 0
    cumulative_volume = 0

    for i in range(len(closes)):
        # Calculate typical price
        typical_price = (highs[i] + lows[i] + closes[i]) / 3.0

        # Accumulate
        cumulative_tp_volume += typical_price * volumes[i]
        cumulative_volume += volumes[i]

        # WHY: Prevent division by zero
        if cumulative_volume == 0:
            result.append(None)
        else:
            result.append(cumulative_tp_volume / cumulative_volume)

    return result


def anchored_vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    anchor_index: int = 0
) -> list[float]:
    """Calculate VWAP anchored to a specific starting point.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        volumes: List of volume values
        anchor_index: Index to start VWAP calculation from (default: 0)

    Returns:
        List of VWAP values, with None before anchor_index

    Example:
        >>> highs = [100, 102, 103, 104, 105]
        >>> lows = [98, 100, 101, 102, 103]
        >>> closes = [99, 101, 102, 103, 104]
        >>> volumes = [1000, 1500, 1200, 1800, 1000]
        >>> result = anchored_vwap(highs, lows, closes, volumes, anchor_index=2)
        >>> result[0]  # Before anchor
        >>> result[2]  # At anchor
        102.0

    Notes:
        - Useful for anchoring VWAP to significant events (e.g., earnings)
        - Returns None for all values before anchor_index
    """
    if not (highs and lows and closes and volumes):
        return []

    if not (len(highs) == len(lows) == len(closes) == len(volumes)):
        raise ValueError("All input lists must have same length")

    if anchor_index < 0 or anchor_index >= len(closes):
        raise ValueError("anchor_index out of range")

    result = [None] * anchor_index
    cumulative_tp_volume = 0
    cumulative_volume = 0

    for i in range(anchor_index, len(closes)):
        typical_price = (highs[i] + lows[i] + closes[i]) / 3.0

        cumulative_tp_volume += typical_price * volumes[i]
        cumulative_volume += volumes[i]

        if cumulative_volume == 0:
            result.append(None)
        else:
            result.append(cumulative_tp_volume / cumulative_volume)

    return result
