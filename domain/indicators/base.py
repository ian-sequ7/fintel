"""Base types and protocols for technical indicators."""

from dataclasses import dataclass
from typing import Protocol


class IndicatorResult(Protocol):
    """Protocol for indicator results."""
    pass


@dataclass
class OHLCVData:
    """Standard OHLCV price data.

    Attributes:
        opens: List of opening prices
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        volumes: List of volume data

    Example:
        >>> data = OHLCVData(
        ...     opens=[100.0, 101.0, 102.0],
        ...     highs=[102.0, 103.0, 104.0],
        ...     lows=[99.0, 100.0, 101.0],
        ...     closes=[101.0, 102.0, 103.0],
        ...     volumes=[1000000, 1100000, 1200000]
        ... )
    """
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
