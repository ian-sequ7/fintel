# Trading Strategies

Python implementations of algorithmic trading strategies for the Fintel platform.

## Available Strategies

### TriCore Alpha (`tricore_alpha.py`)

A sophisticated multi-strategy trading system that combines three complementary approaches with dynamic risk management.

**Algorithm ID:** `tricore_alpha_v1`
**Version:** 1.0.0

#### Strategy Components

The TriCore Alpha uses three sub-strategies with different allocation weights:

1. **Momentum Strategy (40% allocation)**
   - Detects MACD crossovers with trend confirmation
   - Requires RSI in neutral range (45-70 for longs)
   - Confirms with volume surge (1.3x+ average)
   - Only triggers in aligned market regime

2. **Mean Reversion Strategy (35% allocation)**
   - Identifies Bollinger Band extremes
   - Waits for RSI reversal signals
   - Best in sideways/range-bound markets
   - Uses tighter stops (0.6x base ATR)

3. **Breakout Strategy (25% allocation)**
   - Monitors support/resistance breaks
   - Requires volume surge confirmation
   - Validates with RSI and MACD direction
   - Uses moderately tight stops (0.8x base ATR)

#### Market Regime Filtering

The strategy adapts to three market regimes:

- **Bullish**: SPY > SMA(50) or local uptrend
- **Bearish**: SPY < SMA(50) * 0.98 or local downtrend
- **Sideways**: Price near trend line

Each sub-strategy has regime preferences:
- Momentum favors trending markets
- Mean reversion favors sideways markets
- Breakout works in any regime with volume

#### Dynamic Risk Management

**ATR-Based Stops:**
- Momentum: 2.2x ATR (base)
- Breakout: 1.76x ATR (0.8x base)
- Mean Reversion: 1.32x ATR (0.6x base)

**Profit Targets:** 3.5x ATR (default)

**Confidence Scoring:**
- Base confidence = strategy allocation weight
- Adjusted for RSI extremes (+10-15%)
- Adjusted for volume surge (+5%)
- Penalized for regime mismatch (-10%)

#### Configuration Parameters

All parameters are configurable via `TriCoreConfig`:

**Indicators:**
- `macd_fast`: 12 (Fast EMA period)
- `macd_slow`: 26 (Slow EMA period)
- `macd_signal`: 9 (Signal line period)
- `rsi_period`: 14 (RSI calculation period)
- `rsi_overbought`: 75 (Overbought threshold)
- `rsi_oversold`: 25 (Oversold threshold)
- `bb_period`: 20 (Bollinger Bands period)
- `bb_std_dev`: 2.0 (Standard deviation multiplier)
- `atr_period`: 14 (ATR period)

**Risk Management:**
- `base_stop_atr`: 2.2 (ATR multiplier for stops)
- `base_target_atr`: 3.5 (ATR multiplier for targets)

**Filters:**
- `spy_trend_period`: 50 (Market regime SMA period)
- `volume_surge_mult`: 1.8 (Volume surge threshold)
- `breakout_period`: 20 (Support/resistance lookback)

#### Usage

**Basic Usage:**

```python
from domain.strategies.tricore_alpha import TriCoreAlphaStrategy
from domain.strategies.base import StrategyInput

# Initialize with defaults
strategy = TriCoreAlphaStrategy()

# Prepare market data
data = StrategyInput(
    ticker="AAPL",
    opens=[...],
    highs=[...],
    lows=[...],
    closes=[...],
    volumes=[...],
    spy_closes=[...],  # Optional but recommended
    vix_value=15.5,    # Optional
)

# Generate signal
signal = strategy.generate_signal(data)

if signal:
    print(f"Signal: {signal.signal_type.name}")
    print(f"Confidence: {signal.confidence:.1%}")
    print(f"Entry: ${signal.suggested_entry:.2f}")
    print(f"Stop: ${signal.suggested_stop:.2f}")
    print(f"Target: ${signal.suggested_target:.2f}")
    print(f"Rationale: {signal.rationale}")
```

**Custom Configuration:**

```python
from domain.strategies.tricore_alpha import TriCoreAlphaStrategy, TriCoreConfig

# Conservative configuration
config = TriCoreConfig(
    rsi_period=21,           # Longer period
    base_stop_atr=3.0,       # Wider stops
    base_target_atr=5.0,     # Higher targets
    volume_surge_mult=2.5,   # Stricter volume filter
)

strategy = TriCoreAlphaStrategy(config)
```

**Getting Algorithm Metadata:**

```python
algo_config = strategy.get_config()

print(f"Name: {algo_config.name}")
print(f"Description: {algo_config.description}")
print(f"Parameters: {len(algo_config.parameters)}")

for param in algo_config.parameters:
    print(f"  {param.name}: {param.default} ({param.param_type})")
```

#### Signal Output

The strategy returns `AlgorithmSignal` objects with:

**Core Fields:**
- `signal_type`: LONG_ENTRY or SHORT_ENTRY
- `confidence`: 0.0-1.0 (adjusted from base allocation)
- `price_at_signal`: Current market price
- `timestamp`: Signal generation time

**Risk Management:**
- `suggested_entry`: Recommended entry price
- `suggested_stop`: Stop loss distance (ATR-based)
- `suggested_target`: Profit target distance (ATR-based)

**Context:**
- `rationale`: Human-readable explanation
- `indicators`: Full snapshot of all indicators
- `metadata`: Strategy type, market regime, stop multiplier

#### Testing

Run the unit tests:

```bash
python3 -m domain.strategies.test_tricore
```

Run the examples:

```bash
python3 -m domain.strategies.example_tricore
```

#### Design Notes

**Why three strategies?**
- Diversification reduces dependence on any single market condition
- Different strategies excel in different market regimes
- Weighted allocation reflects historical effectiveness

**Why ATR-based stops?**
- Adapts to volatility automatically
- Prevents stops that are too tight (whipsaws) or too wide (excessive risk)
- Different strategies require different stop distances

**Why regime filtering?**
- Prevents momentum trades in choppy markets
- Prevents mean reversion trades in strong trends
- Improves win rate by waiting for favorable conditions

**Indicator choices:**
- MACD: Trend direction and momentum
- RSI: Overbought/oversold and divergence
- Bollinger Bands: Volatility and extremes
- ATR: Risk sizing and stop placement
- Volume: Confirmation and breakout validation

## Architecture

All strategies inherit from `TradingStrategy` base class and must implement:

- `algorithm_id`: Unique identifier (e.g., "tricore_alpha_v1")
- `name`: Human-readable name
- `compute_indicators()`: Calculate indicator values
- `generate_signal()`: Evaluate conditions and return signal
- `get_config()`: Export configuration metadata

## Adding New Strategies

1. Create new file in `domain/strategies/`
2. Import from `domain.strategies.base` and `domain.indicators`
3. Implement `TradingStrategy` interface
4. Add configuration dataclass for parameters
5. Write unit tests
6. Update this README

## Dependencies

- `domain.indicators`: Technical indicator library
- `domain.algorithm_signals`: Signal types and data structures
- `domain.strategies.base`: Strategy base classes

## Related

- Indicators: `/domain/indicators/`
- Backtesting: `/domain/backtest.py`
- Signal Types: `/domain/algorithm_signals.py`
