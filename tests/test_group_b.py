"""
Unit tests for Group B modules: Regime, Risk, Score Aggregator.

Tests cover:
- Market regime detection (Bull/Bear/Sideways/High Vol)
- Risk filters (liquidity, leverage, penny stocks, etc.)
- Position sizing (Kelly criterion)
- Score aggregator integration
"""

import pytest
from datetime import date

from domain.regime import (
    detect_market_regime,
    get_regime_weights,
    MarketRegime,
    RegimeContext,
    FactorWeights,
)
from domain.risk import (
    apply_risk_filters,
    compute_position_size,
    compute_kelly_fraction,
    check_market_cap,
    check_price,
    check_liquidity,
    check_days_to_cover,
    check_leverage,
    RiskFilters,
    PortfolioConstraints,
    FilterReason,
)
from domain.score_aggregator import (
    score_stock,
    score_stocks,
    select_picks,
    StockData,
    EnhancedScore,
)
from domain.models import Timeframe


class TestRegimeDetection:
    """Tests for market regime classification."""

    def test_bull_market_detection(self):
        """Bull: SPY > 200 SMA and VIX < 20."""
        regime = detect_market_regime(
            spy_price_current=500.0,
            spy_sma_200=480.0,
            vix_current=15.0,
        )
        assert regime.regime == MarketRegime.BULL
        assert regime.spy_above_sma is True
        assert "bull" in regime.description.lower()

    def test_bear_market_detection(self):
        """Bear: SPY < 200 SMA and VIX > 25."""
        regime = detect_market_regime(
            spy_price_current=420.0,
            spy_sma_200=480.0,
            vix_current=28.0,
        )
        assert regime.regime == MarketRegime.BEAR
        assert regime.spy_above_sma is False
        assert "bear" in regime.description.lower()

    def test_high_vol_overrides(self):
        """High vol (VIX > 30) should override other conditions."""
        # Even with bullish price action, high VIX = HIGH_VOL
        regime = detect_market_regime(
            spy_price_current=520.0,
            spy_sma_200=480.0,  # Above SMA
            vix_current=35.0,  # Crisis VIX
        )
        assert regime.regime == MarketRegime.HIGH_VOL
        assert "high volatility" in regime.description.lower()

    def test_sideways_mixed_signals(self):
        """Sideways when signals are mixed."""
        # Above SMA but elevated VIX (not bear-level)
        regime = detect_market_regime(
            spy_price_current=490.0,
            spy_sma_200=480.0,  # Barely above
            vix_current=22.0,  # Elevated but not high
        )
        assert regime.regime == MarketRegime.SIDEWAYS

    def test_regime_from_price_list(self):
        """Regime detection from full price list."""
        # Generate bullish prices (trending up)
        prices = [500 - i * 0.1 for i in range(252)]  # Most recent first, trending up
        regime = detect_market_regime(
            spy_prices=prices,
            vix_current=15.0,
        )
        assert regime.spy_sma_200 is not None
        assert regime.confidence >= 0.66

    def test_missing_data_defaults_sideways(self):
        """No data should default to sideways with low confidence."""
        regime = detect_market_regime()
        assert regime.regime == MarketRegime.SIDEWAYS
        assert regime.confidence == 0.0

    def test_regime_weights_sum_to_one(self):
        """All regime weights should sum to ~1.0."""
        for market_regime in MarketRegime:
            for timeframe in ["SHORT", "MEDIUM", "LONG"]:
                weights = get_regime_weights(market_regime, timeframe)
                total = sum(weights)
                assert abs(total - 1.0) < 0.02, f"{market_regime}/{timeframe} sums to {total}"

    def test_short_timeframe_favors_momentum(self):
        """SHORT timeframe should weight momentum higher."""
        bull_short = get_regime_weights(MarketRegime.BULL, "SHORT")
        bull_long = get_regime_weights(MarketRegime.BULL, "LONG")
        assert bull_short.momentum > bull_long.momentum

    def test_long_timeframe_favors_quality_value(self):
        """LONG timeframe should weight quality and value higher."""
        bull_short = get_regime_weights(MarketRegime.BULL, "SHORT")
        bull_long = get_regime_weights(MarketRegime.BULL, "LONG")
        assert bull_long.quality > bull_short.quality
        assert bull_long.value > bull_short.value


class TestRiskFilters:
    """Tests for risk filter functions."""

    def test_market_cap_filter_passes(self):
        """Large cap should pass."""
        result = check_market_cap(market_cap=50e9, min_cap=2e9)
        assert result.passes is True

    def test_market_cap_filter_fails(self):
        """Small cap below threshold should fail."""
        result = check_market_cap(market_cap=1e9, min_cap=2e9)
        assert result.passes is False
        assert result.reason == FilterReason.MARKET_CAP_TOO_SMALL

    def test_price_filter_passes(self):
        """Normal price should pass."""
        result = check_price(price=50.0, min_price=5.0)
        assert result.passes is True

    def test_price_filter_fails_penny(self):
        """Penny stock should fail."""
        result = check_price(price=3.50, min_price=5.0)
        assert result.passes is False
        assert result.reason == FilterReason.PENNY_STOCK

    def test_liquidity_filter_passes(self):
        """High liquidity should pass."""
        result = check_liquidity(
            avg_volume=1_000_000,
            price=100.0,  # $100M daily
            min_dollar_volume=10e6,
        )
        assert result.passes is True

    def test_liquidity_filter_fails(self):
        """Low liquidity should fail."""
        result = check_liquidity(
            avg_volume=50_000,
            price=50.0,  # $2.5M daily
            min_dollar_volume=10e6,
        )
        assert result.passes is False
        assert result.reason == FilterReason.LOW_LIQUIDITY

    def test_dtc_filter_passes(self):
        """Normal DTC should pass."""
        result = check_days_to_cover(dtc=2.0, max_dtc=5.0)
        assert result.passes is True

    def test_dtc_filter_fails_crowded(self):
        """Crowded short should fail."""
        result = check_days_to_cover(dtc=8.0, max_dtc=5.0)
        assert result.passes is False
        assert result.reason == FilterReason.CROWDED_SHORT

    def test_leverage_filter_passes(self):
        """Low leverage should pass."""
        result = check_leverage(debt_equity=0.5, max_de=2.0)
        assert result.passes is True

    def test_leverage_filter_fails(self):
        """High leverage should fail."""
        result = check_leverage(debt_equity=3.0, max_de=2.0)
        assert result.passes is False
        assert result.reason == FilterReason.HIGH_LEVERAGE

    def test_combined_filters_all_pass(self):
        """Stock meeting all criteria should pass."""
        passes, reason, detail = apply_risk_filters(
            ticker="GOOD",
            market_cap=100e9,
            price=150.0,
            avg_volume=5_000_000,
            days_to_cover=2.0,
            debt_equity=0.5,
            conviction=8,
        )
        assert passes is True
        assert reason is None

    def test_combined_filters_fails_first(self):
        """Should fail on first failing filter."""
        passes, reason, detail = apply_risk_filters(
            ticker="BAD",
            market_cap=500e6,  # Too small
            price=150.0,
            conviction=8,
        )
        assert passes is False
        assert reason == FilterReason.MARKET_CAP_TOO_SMALL


class TestPositionSizing:
    """Tests for Kelly criterion position sizing."""

    def test_kelly_fraction_positive_edge(self):
        """Positive edge should give positive Kelly."""
        kelly = compute_kelly_fraction(
            win_rate=0.60,
            avg_win=0.15,
            avg_loss=0.10,
            safety_fraction=0.25,
        )
        assert kelly > 0

    def test_kelly_fraction_no_edge(self):
        """No edge should give zero Kelly."""
        kelly = compute_kelly_fraction(
            win_rate=0.50,
            avg_win=0.10,
            avg_loss=0.10,
            safety_fraction=0.25,
        )
        # With 50% win rate and 1:1 ratio, Kelly = 0
        assert kelly == 0

    def test_kelly_fraction_negative_edge(self):
        """Negative edge should give zero (floored)."""
        kelly = compute_kelly_fraction(
            win_rate=0.40,
            avg_win=0.10,
            avg_loss=0.10,
            safety_fraction=0.25,
        )
        assert kelly == 0

    def test_position_size_high_conviction(self):
        """High conviction should give larger position."""
        pos = compute_position_size(
            ticker="HIGH",
            conviction=9,
            score=85.0,
        )
        assert pos.final_size >= 0.04  # At least 4%

    def test_position_size_low_conviction(self):
        """Low conviction should give smaller position."""
        pos = compute_position_size(
            ticker="LOW",
            conviction=5,
            score=50.0,
        )
        assert pos.final_size <= 0.04  # At most 4%

    def test_position_size_respects_max(self):
        """Position should not exceed max constraint."""
        constraints = PortfolioConstraints(max_single_position=0.05)
        pos = compute_position_size(
            ticker="MAX",
            conviction=10,
            score=95.0,
            constraints=constraints,
        )
        assert pos.final_size <= 0.05

    def test_position_size_respects_min(self):
        """Position should not go below min constraint."""
        constraints = PortfolioConstraints(min_single_position=0.02)
        pos = compute_position_size(
            ticker="MIN",
            conviction=3,
            score=30.0,
            constraints=constraints,
        )
        assert pos.final_size >= 0.02


class TestScoreAggregator:
    """Tests for the main score aggregator."""

    def test_score_single_stock(self):
        """Test scoring a single stock."""
        data = StockData(
            ticker="AAPL",
            sector="Technology",
            price=180.0,
            market_cap=3e12,
            eps=6.50,
            roe=0.25,
            debt_equity=0.3,
            gross_profit_margin=0.44,
            avg_volume=50_000_000,
        )

        score = score_stock(data)

        assert isinstance(score, EnhancedScore)
        assert score.ticker == "AAPL"
        assert 0 <= score.score <= 100
        assert 1 <= score.conviction <= 10
        assert score.sector == "Technology"
        assert score.timeframe in Timeframe
        assert score.regime in MarketRegime

    def test_score_includes_factor_breakdown(self):
        """Score should include all factor scores."""
        data = StockData(
            ticker="TEST",
            sector="Healthcare",
            price=100.0,
        )

        score = score_stock(data)

        assert "quality" in score.factor_scores
        assert "value" in score.factor_scores
        assert "momentum" in score.factor_scores
        assert "low_vol" in score.factor_scores
        assert "smart_money" in score.factor_scores
        assert "catalyst" in score.factor_scores

    def test_score_includes_weights_used(self):
        """Score should include the weights that were used."""
        data = StockData(ticker="TEST", sector="Financials", price=50.0)
        score = score_stock(data)

        assert score.weights_used is not None
        assert abs(sum(score.weights_used) - 1.0) < 0.02

    def test_score_position_size_zero_when_filtered(self):
        """Filtered stocks should have zero position size."""
        data = StockData(
            ticker="PENNY",
            sector="Technology",
            price=2.0,  # Penny stock - will be filtered
        )

        score = score_stock(data)

        assert score.passes_filters is False
        assert score.position_size == 0.0

    def test_score_multiple_stocks(self):
        """Test scoring multiple stocks at once."""
        stocks = [
            StockData(ticker="A", sector="Technology", price=100.0, market_cap=50e9),
            StockData(ticker="B", sector="Healthcare", price=80.0, market_cap=30e9),
            StockData(ticker="C", sector="Financials", price=60.0, market_cap=20e9),
        ]

        scores = score_stocks(stocks)

        assert len(scores) == 3
        # Should be sorted by score descending
        assert scores[0].score >= scores[1].score >= scores[2].score

    def test_select_picks_applies_limits(self):
        """select_picks should respect sector and count limits."""
        # Create mock scores
        scores = []
        for i in range(10):
            data = StockData(
                ticker=f"TECH{i}",
                sector="Technology",
                price=100.0,
                market_cap=50e9,
                avg_volume=5_000_000,
            )
            score = score_stock(data)
            # Manually set to pass filters for this test
            scores.append(score)

        # Select with max 2 per sector
        picks = select_picks(
            scores,
            picks_per_timeframe=(3, 7),
            max_sector_per_timeframe=2,
        )

        # Each timeframe should have at most 2 tech stocks
        for timeframe, tf_picks in picks.items():
            tech_count = sum(1 for p in tf_picks if p.sector == "Technology")
            assert tech_count <= 2, f"{timeframe} has {tech_count} tech picks"


class TestIntegration:
    """Integration tests for the full scoring pipeline."""

    def test_bull_market_favors_momentum(self):
        """In bull market, high momentum stock should score well."""
        data = StockData(
            ticker="MOMENTUM",
            sector="Technology",
            price=150.0,
            market_cap=100e9,
            price_change_12m=0.50,  # 50% gain
            price_change_1m=0.08,   # Strong recent momentum
            avg_volume=10_000_000,
        )

        regime = detect_market_regime(
            spy_price_current=500.0,
            spy_sma_200=450.0,
            vix_current=14.0,
        )

        score = score_stock(data, regime_context=regime)

        assert score.regime == MarketRegime.BULL
        assert score.factor_scores["momentum"] >= 60  # High momentum score

    def test_bear_market_favors_quality(self):
        """In bear market, high quality stock should be favored."""
        data = StockData(
            ticker="QUALITY",
            sector="Consumer Staples",
            price=80.0,
            market_cap=50e9,
            roe=0.28,
            debt_equity=0.2,
            gross_profit_margin=0.45,
            avg_volume=5_000_000,
        )

        regime = detect_market_regime(
            spy_price_current=400.0,
            spy_sma_200=480.0,
            vix_current=28.0,
        )

        score = score_stock(data, regime_context=regime)

        assert score.regime == MarketRegime.BEAR
        # Quality weight should be higher in bear market
        assert score.weights_used.quality >= 0.30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
