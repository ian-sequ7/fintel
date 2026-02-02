"""Trading strategies for fintel.

This package provides trading strategy implementations that generate
algorithmic trading signals based on technical indicators.

Available Strategies:
    - RSIMAStrategy: Combined RSI and Moving Average strategy
    - TriCoreAlphaStrategy: Multi-strategy (momentum + mean reversion + breakout)

Example:
    >>> from domain.strategies import TriCoreAlphaStrategy, StrategyInput
    >>>
    >>> strategy = TriCoreAlphaStrategy()
    >>> data = StrategyInput(
    ...     ticker="AAPL",
    ...     opens=[...],
    ...     highs=[...],
    ...     lows=[...],
    ...     closes=[...],
    ...     volumes=[...],
    ...     spy_closes=[...]  # Optional for market regime
    ... )
    >>> signal = strategy.generate_signal(data)
"""

from domain.strategies.base import StrategyInput, TradingStrategy
from domain.strategies.rsi_ma import RSIMAStrategy
from domain.strategies.tricore_alpha import (
    MarketRegime,
    StrategyType,
    TriCoreAlphaStrategy,
    TriCoreConfig,
)
from domain.strategies.signal_generator import (
    STRATEGY_REGISTRY,
    get_available_strategies,
    generate_signals_for_ticker,
    generate_signals_batch,
)

__all__ = [
    "TradingStrategy",
    "StrategyInput",
    "RSIMAStrategy",
    "TriCoreAlphaStrategy",
    "TriCoreConfig",
    "MarketRegime",
    "StrategyType",
    "STRATEGY_REGISTRY",
    "get_available_strategies",
    "generate_signals_for_ticker",
    "generate_signals_batch",
]
