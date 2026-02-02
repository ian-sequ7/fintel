"""Tests for technical indicators library."""

import pytest
from domain.indicators import (
    adx,
    atr,
    bollinger_bands,
    camarilla_pivots,
    cci,
    change,
    crossover,
    crossunder,
    ema,
    fibonacci_pivots,
    highest,
    lowest,
    macd,
    obv,
    percent_change,
    roc,
    rsi,
    sma,
    standard_pivots,
    stochastic,
    volume_sma,
    volume_surge,
    vwap,
    williams_r,
    wma,
)


class TestMovingAverages:
    """Test moving average indicators."""

    def test_sma_basic(self):
        prices = [10, 11, 12, 13, 14, 15]
        result = sma(prices, 3)
        assert result[2] == 11.0
        assert result[3] == 12.0
        assert result[-1] == 14.0

    def test_sma_insufficient_data(self):
        prices = [10, 11]
        result = sma(prices, 3)
        assert all(v is None for v in result)

    def test_ema_basic(self):
        prices = [10, 11, 12, 13, 14, 15]
        result = ema(prices, 3)
        assert result[2] is not None
        assert result[-1] > result[-2]

    def test_wma_basic(self):
        prices = [10, 11, 12, 13, 14, 15]
        result = wma(prices, 3)
        assert result[2] is not None
        # WMA should weight recent values more
        assert result[2] > sma(prices, 3)[2]


class TestRSI:
    """Test RSI indicator."""

    def test_rsi_basic(self):
        closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
                  45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
        result = rsi(closes, 14)

        # Should have valid RSI after period
        assert result[14] is not None
        assert 0 <= result[14] <= 100

        # First period values should be None
        assert all(v is None for v in result[:14])

    def test_rsi_range(self):
        # Strongly uptrending should give high RSI
        uptrend = list(range(1, 20))
        result = rsi(uptrend, 14)
        assert result[-1] > 70

        # Strongly downtrending should give low RSI
        downtrend = list(range(20, 1, -1))
        result = rsi(downtrend, 14)
        assert result[-1] < 30


class TestMACD:
    """Test MACD indicator."""

    def test_macd_basic(self):
        closes = list(range(10, 50))
        macd_line, signal_line, histogram = macd(closes)

        # Should have values after slow period
        assert macd_line[-1] is not None
        assert signal_line[-1] is not None
        assert histogram[-1] is not None

        # Histogram should be difference
        assert abs(histogram[-1] - (macd_line[-1] - signal_line[-1])) < 0.001

    def test_macd_uptrend(self):
        closes = list(range(10, 50))
        macd_line, _, _ = macd(closes)

        # MACD should be positive in uptrend
        valid_values = [v for v in macd_line if v is not None]
        assert valid_values[-1] > 0


class TestBollingerBands:
    """Test Bollinger Bands indicator."""

    def test_bollinger_basic(self):
        closes = [20, 21, 22, 23, 24, 25, 24, 23, 22, 21,
                  20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
        upper, middle, lower = bollinger_bands(closes, period=20)

        # Upper > Middle > Lower
        assert upper[-1] > middle[-1]
        assert middle[-1] > lower[-1]

        # Middle should be SMA
        sma_20 = sma(closes, 20)
        assert abs(middle[-1] - sma_20[-1]) < 0.001

    def test_bollinger_width(self):
        # Low volatility should give narrow bands
        stable = [100] * 25
        upper, middle, lower = bollinger_bands(stable, period=20)
        assert upper[-1] == middle[-1] == lower[-1]


class TestATR:
    """Test ATR indicator."""

    def test_atr_basic(self):
        highs = [48, 49, 50, 51, 52] * 5
        lows = [46, 47, 48, 49, 50] * 5
        closes = [47, 48, 49, 50, 51] * 5

        result = atr(highs, lows, closes, 14)

        # Should have values after period
        assert result[14] is not None
        assert result[-1] > 0

    def test_atr_increasing_volatility(self):
        # Low volatility period
        highs_low = [101] * 15
        lows_low = [99] * 15
        closes_low = [100] * 15

        # High volatility period
        highs_high = [110, 90, 110, 90, 110] * 3
        lows_high = [90, 110, 90, 110, 90] * 3
        closes_high = [100, 100, 100, 100, 100] * 3

        atr_low = atr(highs_low, lows_low, closes_low, 14)
        atr_high = atr(highs_high, lows_high, closes_high, 14)

        # High volatility should have higher ATR
        assert atr_high[-1] > atr_low[-1]


class TestStochastic:
    """Test Stochastic Oscillator."""

    def test_stochastic_basic(self):
        # WHY: Need k_period + d_period values for valid %D
        highs = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68]
        lows = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66]
        closes = [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67]

        k, d = stochastic(highs, lows, closes, 14, 3)

        assert k[-1] is not None
        assert d[-1] is not None
        assert 0 <= k[-1] <= 100
        assert 0 <= d[-1] <= 100


class TestADX:
    """Test ADX indicator."""

    def test_adx_basic(self):
        highs = [50] * 30
        lows = [48] * 30
        closes = [49] * 30

        adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)

        # Should have values after 2*period
        assert len(adx_vals) == 30
        assert len(plus_di) == 30
        assert len(minus_di) == 30


class TestVolumeIndicators:
    """Test volume-based indicators."""

    def test_obv_basic(self):
        closes = [10, 11, 10, 12, 11]
        volumes = [1000, 1500, 1200, 1800, 1000]

        result = obv(closes, volumes)

        assert result[0] == 0
        assert result[1] == 1500  # Price up
        assert result[2] == 300   # Price down
        assert result[3] == 2100  # Price up
        assert result[4] == 1100  # Price down

    def test_vwap_basic(self):
        highs = [102, 103, 104]
        lows = [100, 101, 102]
        closes = [101, 102, 103]
        volumes = [1000, 1500, 1200]

        result = vwap(highs, lows, closes, volumes)

        assert len(result) == 3
        assert all(v is not None for v in result)

    def test_volume_surge(self):
        volumes = [1000] * 20 + [2500]
        result = volume_surge(volumes, period=20, threshold=2.0)

        assert result[-1] is True  # Last value is a surge
        assert result[0] is False  # First values have insufficient data


class TestMomentumIndicators:
    """Test momentum indicators."""

    def test_roc_basic(self):
        prices = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160]
        result = roc(prices, 12)

        assert result[-1] == 60.0  # 60% change

    def test_cci_basic(self):
        highs = [102] * 25
        lows = [98] * 25
        closes = [100] * 25

        result = cci(highs, lows, closes, 20)

        # Flat prices should give CCI near 0
        assert result[-1] == 0.0

    def test_williams_r_basic(self):
        highs = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64]
        lows = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62]
        closes = [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63]

        result = williams_r(highs, lows, closes, 14)

        assert -100 <= result[-1] <= 0


class TestPivotPoints:
    """Test pivot point calculations."""

    def test_standard_pivots(self):
        levels = standard_pivots(high=105, low=95, close=100)

        assert levels.pivot == 100.0
        assert levels.r1 > levels.pivot
        assert levels.s1 < levels.pivot
        assert levels.r3 > levels.r2 > levels.r1
        assert levels.s1 > levels.s2 > levels.s3

    def test_fibonacci_pivots(self):
        levels = fibonacci_pivots(high=105, low=95, close=100)

        assert levels.pivot == 100.0
        assert levels.r1 > levels.pivot
        assert levels.s1 < levels.pivot

    def test_camarilla_pivots(self):
        levels = camarilla_pivots(high=105, low=95, close=100)

        assert levels.pivot == 100.0
        # Camarilla pivots are typically closer to close price
        assert abs(levels.r1 - 100) < abs(levels.r3 - 100)


class TestUtilities:
    """Test utility functions."""

    def test_crossover(self):
        fast = [10, 11, 12, 11, 10]
        slow = [11, 11, 11, 11, 11]

        result = crossover(fast, slow)

        assert result[0] is False  # No previous value
        assert result[2] is True   # Crosses above at index 2
        assert result[3] is False

    def test_crossunder(self):
        fast = [12, 11, 10, 11, 12]
        slow = [11, 11, 11, 11, 11]

        result = crossunder(fast, slow)

        assert result[0] is False
        assert result[2] is True   # Crosses below at index 2
        assert result[3] is False

    def test_highest(self):
        prices = [10, 12, 11, 15, 14, 13]
        result = highest(prices, 3)

        assert result[2] == 12
        assert result[3] == 15
        assert result[-1] == 15

    def test_lowest(self):
        prices = [10, 12, 11, 15, 14, 13]
        result = lowest(prices, 3)

        assert result[2] == 10
        assert result[3] == 11
        assert result[-1] == 13

    def test_change(self):
        prices = [10, 11, 12, 11, 10]
        result = change(prices, 1)

        assert result[1] == 1
        assert result[2] == 1
        assert result[3] == -1
        assert result[4] == -1

    def test_percent_change(self):
        prices = [100, 110, 121, 110, 100]
        result = percent_change(prices, 1)

        assert result[1] == 10.0
        assert result[2] == 10.0
        assert abs(result[3] - (-9.090909)) < 0.001


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_lists(self):
        assert rsi([], 14) == []
        assert sma([], 20) == []
        assert obv([], []) == []

    def test_insufficient_data(self):
        short_list = [1, 2, 3]
        result = rsi(short_list, 14)
        assert all(v is None for v in result)

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError):
            atr([1, 2], [1, 2], [1, 2, 3], 14)

        with pytest.raises(ValueError):
            obv([1, 2], [1, 2, 3])

    def test_none_values_in_input(self):
        # Utility functions should handle None gracefully
        values = [10, None, 12, 13, 14]
        result = highest(values, 3)
        assert result[2] is not None  # Should ignore None

    def test_zero_division(self):
        # Flat prices shouldn't cause division by zero
        flat = [100] * 25
        result = bollinger_bands(flat, period=20)
        assert result[0][-1] == result[1][-1] == result[2][-1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
