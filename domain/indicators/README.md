# Technical Indicators Library

Pure Python implementation of technical indicators for trading algorithms. Matches PineScript behavior as closely as possible.

## Features

- **Pure Python** - No dependencies required (works standalone)
- **PineScript Compatible** - Matches `ta.*` functions behavior
- **Edge Case Handling** - Returns `None` for insufficient data
- **Wilder's Smoothing** - Proper implementation in RSI, ATR, ADX

## Installation

No installation needed - this is a pure Python library within the domain module.

```python
from domain.indicators import rsi, macd, bollinger_bands
```

## Quick Start

```python
from domain.indicators import rsi, ema, bollinger_bands, stochastic

# Price data
closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
          45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]

# Calculate RSI
rsi_values = rsi(closes, period=14)
print(f"Current RSI: {rsi_values[-1]}")

# Calculate EMA
ema_20 = ema(closes, 20)

# Calculate Bollinger Bands
upper, middle, lower = bollinger_bands(closes, period=20, std_dev=2.0)
```

## Available Indicators

### Trend Indicators

#### RSI (Relative Strength Index)
```python
from domain.indicators import rsi

rsi_values = rsi(closes, period=14)
# Returns: List[float | None]
# Range: 0-100
```

#### MACD (Moving Average Convergence Divergence)
```python
from domain.indicators import macd

macd_line, signal_line, histogram = macd(
    closes,
    fast=12,
    slow=26,
    signal=9
)
# Returns: Tuple[List[float | None], List[float | None], List[float | None]]
```

#### Bollinger Bands
```python
from domain.indicators import bollinger_bands

upper, middle, lower = bollinger_bands(
    closes,
    period=20,
    std_dev=2.0
)
# Returns: Tuple[List[float | None], List[float | None], List[float | None]]
```

#### ATR (Average True Range)
```python
from domain.indicators import atr

atr_values = atr(highs, lows, closes, period=14)
# Returns: List[float | None]
```

#### ADX (Average Directional Index)
```python
from domain.indicators import adx

adx_values, plus_di, minus_di = adx(
    highs,
    lows,
    closes,
    period=14
)
# Returns: Tuple[List[float | None], List[float | None], List[float | None]]
# Range: 0-100 for all values
```

#### Stochastic Oscillator
```python
from domain.indicators import stochastic

k_values, d_values = stochastic(
    highs,
    lows,
    closes,
    k_period=14,
    d_period=3
)
# Returns: Tuple[List[float | None], List[float | None]]
# Range: 0-100
```

### Moving Averages

```python
from domain.indicators import sma, ema, wma

# Simple Moving Average
sma_20 = sma(closes, 20)

# Exponential Moving Average (matches PineScript ta.ema)
ema_20 = ema(closes, 20)

# Weighted Moving Average
wma_20 = wma(closes, 20)
```

### Volume Indicators

#### OBV (On-Balance Volume)
```python
from domain.indicators import obv

obv_values = obv(closes, volumes)
# Returns: List[float]
```

#### VWAP (Volume Weighted Average Price)
```python
from domain.indicators import vwap, anchored_vwap

# Standard VWAP
vwap_values = vwap(highs, lows, closes, volumes)

# Anchored VWAP (from specific index)
anchored = anchored_vwap(highs, lows, closes, volumes, anchor_index=10)
# Returns: List[float | None]
```

#### Volume Analysis
```python
from domain.indicators import volume_sma, volume_surge

# Volume SMA
vol_avg = volume_sma(volumes, period=20)

# Volume surge detection
surges = volume_surge(volumes, period=20, threshold=2.0)
# Returns: List[bool]
```

### Momentum Indicators

#### ROC (Rate of Change)
```python
from domain.indicators import roc

roc_values = roc(closes, period=12)
# Returns: List[float | None]
# Values are percentages
```

#### CCI (Commodity Channel Index)
```python
from domain.indicators import cci

cci_values = cci(highs, lows, closes, period=20)
# Returns: List[float | None]
# Typically ranges -200 to +200
```

#### Williams %R
```python
from domain.indicators import williams_r

wr_values = williams_r(highs, lows, closes, period=14)
# Returns: List[float | None]
# Range: -100 to 0
```

### Pivot Points

```python
from domain.indicators import (
    standard_pivots,
    fibonacci_pivots,
    camarilla_pivots,
    PivotLevels
)

# Calculate pivot levels for a period
levels: PivotLevels = standard_pivots(
    high=105.0,
    low=95.0,
    close=100.0
)

print(f"Pivot: {levels.pivot}")
print(f"R1: {levels.r1}, R2: {levels.r2}, R3: {levels.r3}")
print(f"S1: {levels.s1}, S2: {levels.s2}, S3: {levels.s3}")

# Fibonacci pivots
fib_levels = fibonacci_pivots(high=105.0, low=95.0, close=100.0)

# Camarilla pivots
cam_levels = camarilla_pivots(high=105.0, low=95.0, close=100.0)
```

### Utility Functions

```python
from domain.indicators import (
    crossover,
    crossunder,
    highest,
    lowest,
    change,
    percent_change
)

# Detect crossovers
fast_ema = ema(closes, 12)
slow_ema = ema(closes, 26)
cross_up = crossover(fast_ema, slow_ema)
cross_down = crossunder(fast_ema, slow_ema)

# Find highest/lowest values
high_14 = highest(closes, 14)
low_14 = lowest(closes, 14)

# Calculate changes
price_change = change(closes, period=1)
pct_change = percent_change(closes, period=1)
```

## Data Conventions

### Index Convention
- Most recent value is at index `-1` (end of list)
- Historical values are earlier in the list
- Matches time-series convention

### None Values
- Functions return `None` for periods with insufficient data
- First `period - 1` values are typically `None`
- Some indicators (like RSI with Wilder's smoothing) return `None` for first `period` values

### Example
```python
prices = [10, 11, 12, 13, 14, 15]
sma_3 = sma(prices, 3)
# Result: [None, None, 11.0, 12.0, 13.0, 14.0]
#          ↑ insufficient data   ↑ most recent
```

## PineScript Compatibility

### Wilder's Smoothing
RSI and ATR use Wilder's smoothing formula:
```
New avg = (prev_avg * (period - 1) + current) / period
```

This matches PineScript's `ta.rsi()` and `ta.atr()` behavior.

### EMA Calculation
EMA uses standard exponential smoothing:
```
alpha = 2 / (period + 1)
EMA = (close * alpha) + (prev_EMA * (1 - alpha))
```

First EMA value is SMA of first `period` values.

### Notable Differences
- **RSI**: Uses Wilder's smoothing (not simple average)
- **ATR**: Uses Wilder's smoothing on True Range
- **MACD**: Signal line is EMA of MACD line

## Usage in Trading Algorithms

```python
from domain.indicators import (
    rsi,
    ema,
    macd,
    bollinger_bands,
    crossover,
    crossunder
)

class RSIMACrossStrategy:
    def __init__(self):
        self.rsi_period = 14
        self.fast_period = 12
        self.slow_period = 26

    def generate_signals(self, closes):
        # Calculate indicators
        rsi_values = rsi(closes, self.rsi_period)
        fast_ema = ema(closes, self.fast_period)
        slow_ema = ema(closes, self.slow_period)

        # Detect crossovers
        bullish_cross = crossover(fast_ema, slow_ema)
        bearish_cross = crossunder(fast_ema, slow_ema)

        # Generate signals
        signals = []
        for i in range(len(closes)):
            if rsi_values[i] is None:
                signals.append(None)
            elif bullish_cross[i] and rsi_values[i] < 70:
                signals.append('BUY')
            elif bearish_cross[i] and rsi_values[i] > 30:
                signals.append('SELL')
            else:
                signals.append('HOLD')

        return signals
```

## Error Handling

All functions handle edge cases gracefully:

```python
# Insufficient data
rsi([], 14)  # Returns: []
rsi([1, 2, 3], 14)  # Returns: [None, None, None]

# Mismatched lengths
atr([1, 2], [1, 2], [1, 2, 3], 14)  # Raises: ValueError

# Division by zero
bollinger_bands([100] * 25, period=20)  # Handles gracefully
```

## Testing

```python
# Example test
from domain.indicators import rsi

closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
          45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]

rsi_values = rsi(closes, 14)

# Verify calculation
assert rsi_values[-1] is not None
assert 0 <= rsi_values[-1] <= 100
assert rsi_values[0] is None  # Insufficient data
```

## Performance Notes

- Pure Python implementation (no NumPy/Pandas required)
- Optimized for readability over speed
- For high-frequency trading, consider NumPy-based alternatives
- Suitable for daily/hourly timeframes with reasonable data sizes

## License

MIT
