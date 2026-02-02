"""On-Balance Volume (OBV) indicator."""


def obv(closes: list[float], volumes: list[float]) -> list[float]:
    """Calculate On-Balance Volume.

    OBV is a cumulative indicator that adds volume on up days
    and subtracts volume on down days.

    Args:
        closes: List of closing prices
        volumes: List of volume values

    Returns:
        List of OBV values

    Example:
        >>> closes = [10, 11, 10, 12, 11]
        >>> volumes = [1000, 1500, 1200, 1800, 1000]
        >>> obv(closes, volumes)
        [0, 1500, 300, 2100, 1100]

    Notes:
        - First value is always 0
        - Subsequent values accumulate based on price direction
        - If price unchanged, volume is not added or subtracted
    """
    if not closes or not volumes:
        return []

    if len(closes) != len(volumes):
        raise ValueError("closes and volumes must have same length")

    result = [0]
    cumulative = 0

    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            cumulative += volumes[i]
        elif closes[i] < closes[i - 1]:
            cumulative -= volumes[i]
        # If equal, cumulative stays the same

        result.append(cumulative)

    return result
