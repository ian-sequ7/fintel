"""Unit tests for TriCore Alpha strategy."""

from domain.strategies.base import StrategyInput
from domain.strategies.tricore_alpha import (
    MarketRegime,
    TriCoreAlphaStrategy,
    TriCoreConfig,
)


def test_strategy_initialization():
    """Test strategy can be initialized with default and custom config."""
    # Default config
    strategy = TriCoreAlphaStrategy()
    assert strategy.algorithm_id == "tricore_alpha_v1"
    assert strategy.name == "TriCore Alpha"

    # Custom config
    config = TriCoreConfig(rsi_period=21, base_stop_atr=3.0)
    strategy = TriCoreAlphaStrategy(config)
    assert strategy.config.rsi_period == 21
    assert strategy.config.base_stop_atr == 3.0

    print("✓ Strategy initialization test passed")


def test_compute_indicators():
    """Test indicator computation."""
    strategy = TriCoreAlphaStrategy()

    data = StrategyInput(
        ticker="TEST",
        opens=[100.0] * 100,
        highs=[102.0] * 100,
        lows=[98.0] * 100,
        closes=list(range(100, 200)),
        volumes=[1_000_000] * 100,
    )

    indicators = strategy.compute_indicators(data)

    # Check that indicators are computed
    assert indicators.rsi is not None
    assert indicators.macd_line is not None
    assert indicators.macd_signal is not None
    assert indicators.bb_upper is not None
    assert indicators.bb_lower is not None
    assert indicators.atr is not None
    assert indicators.sma_20 is not None

    print("✓ Indicator computation test passed")
    print(f"  RSI: {indicators.rsi:.2f}")
    print(f"  MACD: {indicators.macd_line:.3f}")
    print(f"  ATR: {indicators.atr:.2f}")


def test_market_regime_detection():
    """Test market regime classification."""
    strategy = TriCoreAlphaStrategy()

    # Bullish regime
    data_bullish = StrategyInput(
        ticker="TEST",
        opens=[100.0] * 100,
        highs=[102.0] * 100,
        lows=[98.0] * 100,
        closes=list(range(100, 200)),
        volumes=[1_000_000] * 100,
        spy_closes=list(range(400, 500)),
    )
    regime = strategy._determine_market_regime(data_bullish)
    assert regime == MarketRegime.BULLISH
    print("✓ Bullish regime detection test passed")

    # Bearish regime
    data_bearish = StrategyInput(
        ticker="TEST",
        opens=[200.0] * 100,
        highs=[202.0] * 100,
        lows=[198.0] * 100,
        closes=list(range(200, 100, -1)),
        volumes=[1_000_000] * 100,
        spy_closes=list(range(500, 400, -1)),
    )
    regime = strategy._determine_market_regime(data_bearish)
    assert regime == MarketRegime.BEARISH
    print("✓ Bearish regime detection test passed")

    # Sideways regime
    data_sideways = StrategyInput(
        ticker="TEST",
        opens=[100.0] * 100,
        highs=[102.0] * 100,
        lows=[98.0] * 100,
        closes=[100.0] * 100,
        volumes=[1_000_000] * 100,
        spy_closes=[400.0] * 100,
    )
    regime = strategy._determine_market_regime(data_sideways)
    assert regime == MarketRegime.SIDEWAYS
    print("✓ Sideways regime detection test passed")


def test_get_config():
    """Test algorithm configuration export."""
    strategy = TriCoreAlphaStrategy()
    config = strategy.get_config()

    assert config.algorithm_id == "tricore_alpha_v1"
    assert config.name == "TriCore Alpha"
    assert config.version == "1.0.0"
    assert len(config.parameters) == 14

    # Check parameter types
    param_names = [p.name for p in config.parameters]
    assert "macd_fast" in param_names
    assert "rsi_period" in param_names
    assert "bb_period" in param_names
    assert "atr_period" in param_names
    assert "base_stop_atr" in param_names

    print("✓ Configuration export test passed")
    print(f"  Parameters: {len(config.parameters)}")


def test_insufficient_data():
    """Test that strategy returns None with insufficient data."""
    strategy = TriCoreAlphaStrategy()

    # Only 10 bars - not enough for any strategy
    data = StrategyInput(
        ticker="TEST",
        opens=[100.0] * 10,
        highs=[102.0] * 10,
        lows=[98.0] * 10,
        closes=[100.0] * 10,
        volumes=[1_000_000] * 10,
    )

    signal = strategy.generate_signal(data)
    assert signal is None
    print("✓ Insufficient data test passed")


def test_confidence_adjustment():
    """Test confidence adjustment logic."""
    strategy = TriCoreAlphaStrategy()

    from domain.strategies.tricore_alpha import StrategyType

    # Test RSI boost for momentum
    confidence = strategy._adjust_confidence(
        base_confidence=0.40,
        regime=MarketRegime.BULLISH,
        rsi_val=65.0,
        vol_surge_present=True,
        strategy_type=StrategyType.MOMENTUM,
    )
    assert confidence > 0.40  # Should get boost
    print(f"✓ Confidence adjustment test passed (momentum with boost: {confidence:.2f})")

    # Test penalty for mismatched regime
    confidence = strategy._adjust_confidence(
        base_confidence=0.40,
        regime=MarketRegime.SIDEWAYS,
        rsi_val=50.0,
        vol_surge_present=False,
        strategy_type=StrategyType.MOMENTUM,
    )
    assert confidence < 0.40  # Should get penalty
    print(f"✓ Confidence adjustment test passed (momentum with penalty: {confidence:.2f})")


def test_stop_multipliers():
    """Test ATR stop multiplier calculation."""
    strategy = TriCoreAlphaStrategy()

    from domain.strategies.tricore_alpha import StrategyType

    momentum_mult = strategy._get_stop_multiplier(StrategyType.MOMENTUM)
    breakout_mult = strategy._get_stop_multiplier(StrategyType.BREAKOUT)
    mean_rev_mult = strategy._get_stop_multiplier(StrategyType.MEAN_REVERSION)

    # Verify relative ordering
    assert mean_rev_mult < breakout_mult < momentum_mult
    print("✓ Stop multiplier test passed")
    print(f"  Momentum: {momentum_mult:.2f}x ATR")
    print(f"  Breakout: {breakout_mult:.2f}x ATR")
    print(f"  Mean Reversion: {mean_rev_mult:.2f}x ATR")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TriCore Alpha Strategy Unit Tests")
    print("=" * 60 + "\n")

    test_strategy_initialization()
    test_compute_indicators()
    test_market_regime_detection()
    test_get_config()
    test_insufficient_data()
    test_confidence_adjustment()
    test_stop_multipliers()

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60 + "\n")
