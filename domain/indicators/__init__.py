"""Technical indicators library for trading algorithms.

This package provides pure Python implementations of common technical indicators,
matching PineScript behavior as closely as possible.

Indicators:
    - RSI: Relative Strength Index using Wilder's smoothing
    - MACD: Moving Average Convergence Divergence
    - Bollinger Bands: Volatility bands using standard deviation
    - ATR: Average True Range using Wilder's smoothing
    - ADX: Average Directional Index with +DI/-DI
    - Stochastic: Stochastic Oscillator (%K and %D)
    - Moving Averages: SMA, EMA, WMA
    - Volume: OBV, VWAP, Volume SMA and surge detection
    - Momentum: ROC, CCI, Williams %R
    - Pivot Points: Standard, Fibonacci, Camarilla
    - Utils: Crossover, crossunder, highest, lowest, change

Example:
    >>> from domain.indicators import rsi, macd, bollinger_bands, stochastic
    >>>
    >>> closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
    ...           45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
    >>>
    >>> rsi_values = rsi(closes, period=14)
    >>> macd_line, signal_line, histogram = macd(closes)
    >>> upper, middle, lower = bollinger_bands(closes, period=20)
"""

from domain.indicators.adx import adx
from domain.indicators.atr import atr
from domain.indicators.base import IndicatorResult, OHLCVData
from domain.indicators.bollinger import bollinger_bands
from domain.indicators.macd import macd
from domain.indicators.momentum import cci, roc, williams_r
from domain.indicators.moving_averages import ema, sma, wma
from domain.indicators.obv import obv
from domain.indicators.pivots import (
    PivotLevels,
    camarilla_pivots,
    fibonacci_pivots,
    standard_pivots,
)
from domain.indicators.rsi import rsi
from domain.indicators.stochastic import stochastic
from domain.indicators.utils import (
    change,
    crossover,
    crossunder,
    highest,
    lowest,
    percent_change,
)
from domain.indicators.volume import volume_sma, volume_surge
from domain.indicators.vwap import anchored_vwap, vwap

__all__ = [
    # Base types
    "IndicatorResult",
    "OHLCVData",
    "PivotLevels",
    # Trend indicators
    "rsi",
    "macd",
    "bollinger_bands",
    "atr",
    "adx",
    "stochastic",
    # Moving averages
    "sma",
    "ema",
    "wma",
    # Volume
    "volume_sma",
    "volume_surge",
    "obv",
    "vwap",
    "anchored_vwap",
    # Momentum
    "roc",
    "cci",
    "williams_r",
    # Pivot points
    "standard_pivots",
    "fibonacci_pivots",
    "camarilla_pivots",
    # Utilities
    "crossover",
    "crossunder",
    "highest",
    "lowest",
    "change",
    "percent_change",
]
