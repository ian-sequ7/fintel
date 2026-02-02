"""
Signal generator orchestration.
Runs trading strategies against price data to generate signals.
"""

from datetime import datetime
from typing import Iterator

from domain.algorithm_signals import AlgorithmSignal
from domain.strategies.base import TradingStrategy, StrategyInput
from domain.strategies.rsi_ma import RSIMAStrategy
from domain.strategies.tricore_alpha import TriCoreAlphaStrategy


# Registry of available strategies
STRATEGY_REGISTRY: dict[str, type[TradingStrategy]] = {
    "rsi_ma": RSIMAStrategy,
    "tricore_alpha_v1": TriCoreAlphaStrategy,
}


def get_available_strategies() -> list[dict]:
    """Get list of available strategies with their configs."""
    result = []
    for strategy_id, strategy_class in STRATEGY_REGISTRY.items():
        strategy = strategy_class()
        config = strategy.get_config()
        result.append({
            "algorithm_id": config.algorithm_id,
            "name": config.name,
            "description": config.description,
            "version": config.version,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type,
                    "default": p.default,
                    "min": p.min_value,
                    "max": p.max_value,
                    "description": p.description,
                }
                for p in config.parameters
            ],
        })
    return result


def generate_signals_for_ticker(
    ticker: str,
    price_data: list[dict],  # List of {date, open, high, low, close, volume}
    strategy_ids: list[str] | None = None,
    spy_data: list[dict] | None = None,
) -> list[AlgorithmSignal]:
    """
    Generate signals for a ticker using specified strategies.

    Args:
        ticker: Stock ticker symbol
        price_data: OHLCV price history
        strategy_ids: List of strategy IDs to run (None = all)
        spy_data: Optional SPY data for market context

    Returns:
        List of generated signals
    """
    if not price_data:
        return []

    # Build strategy input
    data = StrategyInput(
        ticker=ticker,
        opens=[d["open"] for d in price_data],
        highs=[d["high"] for d in price_data],
        lows=[d["low"] for d in price_data],
        closes=[d["close"] for d in price_data],
        volumes=[d["volume"] for d in price_data],
        spy_closes=[d["close"] for d in spy_data] if spy_data else None,
    )

    # Run strategies
    strategies_to_run = strategy_ids or list(STRATEGY_REGISTRY.keys())
    signals = []

    for strategy_id in strategies_to_run:
        if strategy_id not in STRATEGY_REGISTRY:
            continue

        strategy = STRATEGY_REGISTRY[strategy_id]()
        signal = strategy.generate_signal(data)
        if signal:
            signals.append(signal)

    return signals


def generate_signals_batch(
    tickers: list[str],
    price_data_map: dict[str, list[dict]],
    strategy_ids: list[str] | None = None,
    spy_data: list[dict] | None = None,
) -> dict[str, list[AlgorithmSignal]]:
    """
    Generate signals for multiple tickers.

    Returns:
        Dict mapping ticker to list of signals
    """
    results = {}
    for ticker in tickers:
        if ticker in price_data_map:
            results[ticker] = generate_signals_for_ticker(
                ticker, price_data_map[ticker], strategy_ids, spy_data
            )
    return results
