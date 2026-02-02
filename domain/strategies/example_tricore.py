"""Example usage of TriCore Alpha strategy."""

from domain.strategies.base import StrategyInput
from domain.strategies.tricore_alpha import TriCoreAlphaStrategy, TriCoreConfig


def example_basic_usage():
    """Demonstrate basic TriCore Alpha strategy usage."""
    # Create strategy with default configuration
    strategy = TriCoreAlphaStrategy()

    # Sample market data (normally from database/API)
    # This represents 100 bars of OHLCV data
    data = StrategyInput(
        ticker="AAPL",
        opens=[150.0] * 100,
        highs=[152.0] * 100,
        lows=[148.0] * 100,
        closes=list(range(150, 250)),  # Uptrend
        volumes=[1_000_000] * 100,
        spy_closes=list(range(400, 500)),  # Bullish market
        vix_value=15.5,
    )

    # Generate signal
    signal = strategy.generate_signal(data)

    if signal:
        print(f"\n{'=' * 60}")
        print(f"Signal Generated for {signal.ticker}")
        print(f"{'=' * 60}")
        print(f"Type: {signal.signal_type.name}")
        print(f"Confidence: {signal.confidence:.1%}")
        print(f"Price: ${signal.price_at_signal:.2f}")
        print(f"\nRationale: {signal.rationale}")
        print(f"\nRisk Management:")
        print(f"  Entry: ${signal.suggested_entry:.2f}")
        print(f"  Stop: ${signal.suggested_stop:.2f} distance")
        print(f"  Target: ${signal.suggested_target:.2f} distance")
        print(f"\nMetadata:")
        print(f"  Strategy: {signal.metadata['strategy_type']}")
        print(f"  Regime: {signal.metadata['market_regime']}")
        print(f"  Stop Multiplier: {signal.metadata['stop_multiplier']:.2f}")
        print(f"\nKey Indicators:")
        print(f"  RSI: {signal.indicators.rsi:.1f}")
        print(f"  MACD: {signal.indicators.macd_line:.3f}")
        print(f"  BB Upper: ${signal.indicators.bb_upper:.2f}")
        print(f"  BB Lower: ${signal.indicators.bb_lower:.2f}")
        print(f"  ATR: ${signal.indicators.atr:.2f}")
    else:
        print("No signal generated")


def example_custom_config():
    """Demonstrate custom configuration usage."""
    # Create custom configuration for more conservative trading
    config = TriCoreConfig(
        rsi_period=21,  # Longer RSI period
        base_stop_atr=3.0,  # Wider stops
        base_target_atr=5.0,  # Higher targets
        volume_surge_mult=2.5,  # Require stronger volume
    )

    strategy = TriCoreAlphaStrategy(config)

    # Get algorithm configuration details
    algo_config = strategy.get_config()
    print(f"\n{'=' * 60}")
    print(f"Algorithm: {algo_config.name}")
    print(f"{'=' * 60}")
    print(f"ID: {algo_config.algorithm_id}")
    print(f"Version: {algo_config.version}")
    print(f"\nDescription: {algo_config.description}")
    print(f"\nParameters ({len(algo_config.parameters)}):")
    for param in algo_config.parameters:
        print(f"  {param.name}: {param.default} ({param.param_type})")
        if param.description:
            print(f"    → {param.description}")


def example_momentum_signal():
    """Example of momentum strategy triggering."""
    strategy = TriCoreAlphaStrategy()

    # Create data that triggers momentum long signal
    # Initial downtrend followed by reversal with MACD crossover
    base = 100.0
    downtrend = [base - i * 0.3 for i in range(40)]
    reversal = [downtrend[-1] + i * 0.4 for i in range(50)]
    closes = downtrend + reversal

    # Need more bars for indicators
    pad_before = [base + 2 - i * 0.1 for i in range(20)]
    closes = pad_before + closes

    data = StrategyInput(
        ticker="TSLA",
        opens=closes,
        highs=[c + 1 for c in closes],
        lows=[c - 1 for c in closes],
        closes=closes,
        volumes=[800_000] * 90 + [1_500_000] * 20,  # Volume surge at end
        spy_closes=[400 + i * 0.5 for i in range(110)],  # Bullish SPY
    )

    signal = strategy.generate_signal(data)
    if signal:
        print(f"\n{'=' * 60}")
        print("MOMENTUM SIGNAL EXAMPLE")
        print(f"{'=' * 60}")
        print(f"Signal: {signal.signal_type.name}")
        print(f"Strategy: {signal.metadata['strategy_type']}")
        print(f"Confidence: {signal.confidence:.1%}")
        print(f"Rationale: {signal.rationale}")
    else:
        print("\n[Momentum example: No signal generated - conditions not met]")


def example_mean_reversion_signal():
    """Example of mean reversion strategy triggering."""
    strategy = TriCoreAlphaStrategy()

    # Create data that triggers mean reversion long signal
    # Sideways market with sharp drop to lower BB
    base = 100.0
    sideways = [base + (i % 10 - 5) * 0.2 for i in range(80)]
    # Sharp drop and bounce
    drop = [sideways[-1] - i * 0.8 for i in range(8)]
    bounce = [drop[-1] + i * 0.1 for i in range(5)]
    closes = sideways + drop + bounce

    data = StrategyInput(
        ticker="MSFT",
        opens=closes,
        highs=[c + 0.5 for c in closes],
        lows=[c - 0.5 for c in closes],
        closes=closes,
        volumes=[1_000_000] * 93,
        spy_closes=[400.0] * 93,  # Flat SPY = sideways market
    )

    signal = strategy.generate_signal(data)
    if signal:
        print(f"\n{'=' * 60}")
        print("MEAN REVERSION SIGNAL EXAMPLE")
        print(f"{'=' * 60}")
        print(f"Signal: {signal.signal_type.name}")
        print(f"Strategy: {signal.metadata['strategy_type']}")
        print(f"Confidence: {signal.confidence:.1%}")
        print(f"Rationale: {signal.rationale}")
    else:
        print("\n[Mean Reversion example: No signal generated - conditions not met]")


if __name__ == "__main__":
    print("\nTriCore Alpha Strategy Examples")
    print("=" * 60)

    example_basic_usage()
    example_custom_config()
    example_momentum_signal()
    example_mean_reversion_signal()
