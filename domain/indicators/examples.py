"""Example usage of technical indicators library."""

from domain.indicators import (
    adx,
    atr,
    bollinger_bands,
    cci,
    crossover,
    crossunder,
    ema,
    highest,
    lowest,
    macd,
    obv,
    roc,
    rsi,
    sma,
    standard_pivots,
    stochastic,
    volume_surge,
    vwap,
    williams_r,
)


def example_trend_following_strategy():
    """Example: RSI + Moving Average Crossover Strategy."""
    print("=" * 60)
    print("Example 1: RSI + MA Crossover Strategy")
    print("=" * 60)

    # Sample price data (20 days)
    closes = [
        100, 102, 101, 103, 105, 107, 106, 108, 110, 109,
        111, 113, 112, 114, 116, 115, 117, 119, 118, 120
    ]

    # Calculate indicators
    rsi_values = rsi(closes, period=14)
    fast_ma = ema(closes, period=5)
    slow_ma = ema(closes, period=10)

    # Detect crossovers
    bullish = crossover(fast_ma, slow_ma)
    bearish = crossunder(fast_ma, slow_ma)

    print(f"\nCurrent Price: ${closes[-1]}")
    print(f"RSI(14): {rsi_values[-1]:.2f}")
    print(f"EMA(5): ${fast_ma[-1]:.2f}")
    print(f"EMA(10): ${slow_ma[-1]:.2f}")

    if bullish[-1]:
        print("Signal: BULLISH CROSSOVER ✓")
    elif bearish[-1]:
        print("Signal: BEARISH CROSSOVER ✗")
    else:
        print("Signal: HOLD —")


def example_volatility_breakout():
    """Example: Bollinger Band Breakout Strategy."""
    print("\n" + "=" * 60)
    print("Example 2: Bollinger Band Breakout")
    print("=" * 60)

    closes = [
        100, 101, 100, 102, 101, 100, 99, 100, 101, 100,
        99, 100, 101, 100, 99, 100, 101, 102, 105, 108
    ]

    upper, middle, lower = bollinger_bands(closes, period=20, std_dev=2.0)

    print(f"\nCurrent Price: ${closes[-1]}")
    print(f"Upper Band: ${upper[-1]:.2f}")
    print(f"Middle Band (SMA): ${middle[-1]:.2f}")
    print(f"Lower Band: ${lower[-1]:.2f}")

    if closes[-1] > upper[-1]:
        print("Status: Price ABOVE upper band (potential overbought)")
    elif closes[-1] < lower[-1]:
        print("Status: Price BELOW lower band (potential oversold)")
    else:
        print("Status: Price within bands (normal)")


def example_momentum_analysis():
    """Example: Multiple Momentum Indicators."""
    print("\n" + "=" * 60)
    print("Example 3: Momentum Analysis")
    print("=" * 60)

    highs = [102, 103, 104, 105, 106, 107, 108, 109, 110, 111] * 3
    lows = [98, 99, 100, 101, 102, 103, 104, 105, 106, 107] * 3
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109] * 3

    # Calculate momentum indicators
    rsi_val = rsi(closes, 14)
    roc_val = roc(closes, 12)
    cci_val = cci(highs, lows, closes, 20)
    wr_val = williams_r(highs, lows, closes, 14)
    k, d = stochastic(highs, lows, closes, 14, 3)

    print(f"\nCurrent Price: ${closes[-1]}")
    print(f"RSI(14): {rsi_val[-1]:.2f}")
    print(f"ROC(12): {roc_val[-1]:.2f}%")
    print(f"CCI(20): {cci_val[-1]:.2f}")
    print(f"Williams %R(14): {wr_val[-1]:.2f}")
    print(f"Stochastic %K: {k[-1]:.2f}, %D: {d[-1]:.2f}")


def example_volume_analysis():
    """Example: Volume-Based Analysis."""
    print("\n" + "=" * 60)
    print("Example 4: Volume Analysis")
    print("=" * 60)

    highs = [102, 103, 104, 105, 106, 107, 108, 109, 110, 111] * 3
    lows = [98, 99, 100, 101, 102, 103, 104, 105, 106, 107] * 3
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109] * 3
    volumes = [1000000, 1100000, 1200000, 1300000, 1400000,
               1500000, 1600000, 1700000, 1800000, 3000000] * 3

    # Calculate volume indicators
    obv_val = obv(closes, volumes)
    vwap_val = vwap(highs, lows, closes, volumes)
    surges = volume_surge(volumes, period=20, threshold=2.0)

    print(f"\nCurrent Volume: {volumes[-1]:,}")
    print(f"OBV: {obv_val[-1]:,.0f}")
    print(f"VWAP: ${vwap_val[-1]:.2f}")
    print(f"Volume Surge Detected: {surges[-1]}")


def example_trend_strength():
    """Example: ADX Trend Strength Analysis."""
    print("\n" + "=" * 60)
    print("Example 5: Trend Strength (ADX)")
    print("=" * 60)

    # WHY: ADX needs 2*period - 1 values to calculate (14*2 - 1 = 27)
    highs = list(range(100, 130))
    lows = list(range(98, 128))
    closes = list(range(99, 129))

    adx_val, plus_di, minus_di = adx(highs, lows, closes, 14)
    atr_val = atr(highs, lows, closes, 14)

    print(f"\nCurrent Price: ${closes[-1]}")
    if adx_val[-1] is not None:
        print(f"ADX(14): {adx_val[-1]:.2f}")
        print(f"+DI: {plus_di[-1]:.2f}")
        print(f"-DI: {minus_di[-1]:.2f}")
        print(f"ATR(14): ${atr_val[-1]:.2f}")

        if adx_val[-1] > 25:
            if plus_di[-1] > minus_di[-1]:
                print("Trend: STRONG UPTREND ↑")
            else:
                print("Trend: STRONG DOWNTREND ↓")
        else:
            print("Trend: WEAK/SIDEWAYS ↔")
    else:
        print("Insufficient data for ADX calculation")


def example_pivot_points():
    """Example: Daily Pivot Points."""
    print("\n" + "=" * 60)
    print("Example 6: Daily Pivot Points")
    print("=" * 60)

    # Previous day's data
    prev_high = 105.50
    prev_low = 98.20
    prev_close = 102.30

    levels = standard_pivots(prev_high, prev_low, prev_close)

    print(f"\nPrevious Day: H=${prev_high}, L=${prev_low}, C=${prev_close}")
    print(f"\nToday's Pivot Levels:")
    print(f"  R3: ${levels.r3:.2f}")
    print(f"  R2: ${levels.r2:.2f}")
    print(f"  R1: ${levels.r1:.2f}")
    print(f"  PP: ${levels.pivot:.2f}")
    print(f"  S1: ${levels.s1:.2f}")
    print(f"  S2: ${levels.s2:.2f}")
    print(f"  S3: ${levels.s3:.2f}")


def example_macd_signals():
    """Example: MACD Signal Generation."""
    print("\n" + "=" * 60)
    print("Example 7: MACD Signals")
    print("=" * 60)

    closes = list(range(100, 150))

    macd_line, signal_line, histogram = macd(closes, fast=12, slow=26, signal=9)

    # Detect crossovers
    bullish = crossover(macd_line, signal_line)
    bearish = crossunder(macd_line, signal_line)

    print(f"\nCurrent Price: ${closes[-1]}")
    print(f"MACD Line: {macd_line[-1]:.3f}")
    print(f"Signal Line: {signal_line[-1]:.3f}")
    print(f"Histogram: {histogram[-1]:.3f}")

    if bullish[-1]:
        print("Signal: BULLISH CROSSOVER (Buy)")
    elif bearish[-1]:
        print("Signal: BEARISH CROSSOVER (Sell)")
    elif histogram[-1] > 0:
        print("Signal: BULLISH (above signal)")
    else:
        print("Signal: BEARISH (below signal)")


def example_support_resistance():
    """Example: Support/Resistance Detection."""
    print("\n" + "=" * 60)
    print("Example 8: Support/Resistance Levels")
    print("=" * 60)

    closes = [
        100, 102, 101, 103, 105, 107, 106, 108, 110, 109,
        111, 113, 112, 114, 116, 115, 117, 119, 118, 120
    ]

    # Find recent highs and lows
    high_20 = highest(closes, 20)
    low_20 = lowest(closes, 20)

    # Calculate moving averages as dynamic support/resistance
    ma_50 = sma(closes, 20)  # Using 20 as proxy for 50
    ma_200 = sma(closes, 20)  # Using 20 as proxy for 200

    print(f"\nCurrent Price: ${closes[-1]}")
    print(f"20-Day High: ${high_20[-1]:.2f}")
    print(f"20-Day Low: ${low_20[-1]:.2f}")
    print(f"SMA(20): ${ma_50[-1]:.2f}")

    if high_20[-2] is not None and low_20[-2] is not None:
        if closes[-1] > high_20[-2]:
            print("Status: Breaking NEW HIGH ↑")
        elif closes[-1] < low_20[-2]:
            print("Status: Breaking NEW LOW ↓")
        else:
            print("Status: Within recent range")
    else:
        print("Status: Insufficient historical data")


if __name__ == "__main__":
    """Run all examples."""
    example_trend_following_strategy()
    example_volatility_breakout()
    example_momentum_analysis()
    example_volume_analysis()
    example_trend_strength()
    example_pivot_points()
    example_macd_signals()
    example_support_resistance()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
