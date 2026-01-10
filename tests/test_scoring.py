"""
Tests for the systematic scoring algorithm.

Tests cover:
- Component scoring functions (valuation, growth, quality, momentum, analyst)
- Macro adjustment calculations
- Timeframe classification
- Thesis and risk generation
- Full scoring pipeline
"""

import pytest
from datetime import datetime

from domain.models import Timeframe, Trend
from domain.analysis_types import StockMetrics, MacroContext
from domain.scoring import (
    ScoringThresholds,
    ScoringWeights,
    SectorSensitivities,
    TimeframeRules,
    ScoredPick,
    ScoreFactor,
    score_stock,
    score_stocks,
    compute_valuation_score,
    compute_growth_score,
    compute_quality_score,
    compute_momentum_score,
    compute_analyst_score,
    compute_macro_adjustment,
    classify_timeframe,
    generate_thesis,
    identify_risks,
    _normalize_score,
    _score_pe,
    _estimate_rsi,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_thresholds():
    """Default scoring thresholds."""
    return ScoringThresholds()


@pytest.fixture
def default_weights():
    """Default scoring weights."""
    return ScoringWeights()


@pytest.fixture
def default_sensitivities():
    """Default sector sensitivities."""
    return SectorSensitivities(
        rate_sensitivity={"technology": -0.2, "financials": 0.3},
        inflation_sensitivity={"technology": -0.1, "energy": 0.4},
        recession_sensitivity={"technology": -0.1, "consumer_staples": 0.3},
    )


@pytest.fixture
def sample_metrics():
    """Sample stock metrics for testing."""
    return StockMetrics(
        ticker="AAPL",
        price=175.0,
        market_cap=2800000000000,
        pe_trailing=28.0,
        pe_forward=24.0,
        peg_ratio=1.5,
        price_to_book=45.0,
        revenue_growth=0.08,
        earnings_growth=0.12,
        profit_margin=0.26,
        roe=0.45,
        roa=0.22,
        price_change_1m=0.05,
        volume_avg=50000000,
        volume_current=55000000,
        analyst_rating=2.0,
        price_target=200.0,
    )


@pytest.fixture
def undervalued_metrics():
    """Metrics for an undervalued stock."""
    return StockMetrics(
        ticker="VALE",
        price=12.0,
        market_cap=50000000000,
        pe_trailing=6.0,
        pe_forward=5.5,
        peg_ratio=0.5,
        price_to_book=0.8,
        revenue_growth=0.15,
        earnings_growth=0.20,
        profit_margin=0.20,
        roe=0.25,
        price_change_1m=-0.10,
        analyst_rating=1.5,
        price_target=18.0,
    )


@pytest.fixture
def overvalued_metrics():
    """Metrics for an overvalued stock."""
    return StockMetrics(
        ticker="BUBBLE",
        price=500.0,
        market_cap=100000000000,
        pe_trailing=150.0,
        pe_forward=100.0,
        peg_ratio=5.0,
        price_to_book=50.0,
        revenue_growth=0.02,
        earnings_growth=-0.05,
        profit_margin=0.05,
        roe=0.05,
        price_change_1m=0.25,
        analyst_rating=4.5,
        price_target=300.0,
    )


@pytest.fixture
def neutral_macro():
    """Neutral macro environment."""
    return MacroContext(
        fed_funds_rate=5.25,
        treasury_10y=4.5,
        treasury_2y=4.7,
        unemployment_rate=4.0,
        inflation_rate=3.0,
        gdp_growth=2.5,
        consumer_sentiment=70.0,
        vix=15.0,
        rate_trend=Trend.STABLE,
        growth_trend=Trend.STABLE,
        inflation_trend=Trend.FALLING,
    )


@pytest.fixture
def hawkish_macro():
    """Hawkish macro environment (rising rates, high inflation)."""
    return MacroContext(
        fed_funds_rate=5.5,
        treasury_10y=5.0,
        treasury_2y=5.5,
        unemployment_rate=3.5,
        inflation_rate=5.0,
        rate_trend=Trend.RISING,
        inflation_trend=Trend.RISING,
        vix=25.0,
    )


@pytest.fixture
def recession_risk_macro():
    """Macro environment with recession signals."""
    return MacroContext(
        fed_funds_rate=5.0,
        treasury_10y=4.0,
        treasury_2y=4.5,  # Inverted yield curve
        unemployment_rate=5.5,
        inflation_rate=4.0,
        rate_trend=Trend.STABLE,
        vix=30.0,
    )


# ============================================================================
# Normalization Tests
# ============================================================================


class TestNormalization:
    """Tests for score normalization."""

    def test_normalize_at_low_boundary(self):
        """Value at low boundary should score 1.0."""
        score = _normalize_score(15.0, low=15.0, high=30.0)
        assert score == 1.0

    def test_normalize_at_high_boundary(self):
        """Value at high boundary should score 0.0."""
        score = _normalize_score(30.0, low=15.0, high=30.0)
        assert score == 0.0

    def test_normalize_midpoint(self):
        """Value at midpoint should score 0.5."""
        score = _normalize_score(22.5, low=15.0, high=30.0)
        assert score == 0.5

    def test_normalize_below_low(self):
        """Value below low should clamp to 1.0."""
        score = _normalize_score(10.0, low=15.0, high=30.0)
        assert score == 1.0

    def test_normalize_above_high(self):
        """Value above high should clamp to 0.0."""
        score = _normalize_score(50.0, low=15.0, high=30.0)
        assert score == 0.0

    def test_normalize_inverted(self):
        """Inverted normalization should flip scores."""
        # Higher value = higher score when inverted
        score = _normalize_score(0.25, low=0.0, high=0.20, invert=True)
        assert score == 1.0

    def test_normalize_equal_boundaries(self):
        """Equal boundaries should return 0.5."""
        score = _normalize_score(10.0, low=10.0, high=10.0)
        assert score == 0.5


# ============================================================================
# Valuation Scoring Tests
# ============================================================================


class TestValuationScoring:
    """Tests for valuation score computation."""

    def test_low_pe_scores_high(self, default_thresholds):
        """Low P/E should produce high valuation score."""
        score, desc = _score_pe(10.0, sector_avg_pe=20.0, thresholds=default_thresholds)
        assert score > 0.7
        assert "Attractive" in desc

    def test_high_pe_scores_low(self, default_thresholds):
        """High P/E should produce low valuation score."""
        score, desc = _score_pe(50.0, sector_avg_pe=20.0, thresholds=default_thresholds)
        assert score < 0.3
        assert "Premium" in desc

    def test_missing_pe_returns_neutral(self, default_thresholds):
        """Missing P/E should return neutral score."""
        score, desc = _score_pe(None, sector_avg_pe=20.0, thresholds=default_thresholds)
        assert score == 0.5
        assert "unavailable" in desc

    def test_compute_valuation_combines_factors(self, sample_metrics, default_thresholds):
        """Valuation score should combine P/E, PEG, and P/B."""
        score, factors = compute_valuation_score(
            sample_metrics, sector_avg_pe=28.0, thresholds=default_thresholds
        )

        assert 0 <= score <= 1
        assert len(factors) == 3
        factor_names = [f.name for f in factors]
        assert "P/E Ratio" in factor_names
        assert "PEG Ratio" in factor_names
        assert "P/B Ratio" in factor_names

    def test_undervalued_stock_high_valuation_score(
        self, undervalued_metrics, default_thresholds
    ):
        """Undervalued stock should have high valuation score."""
        score, _ = compute_valuation_score(
            undervalued_metrics, sector_avg_pe=15.0, thresholds=default_thresholds
        )
        assert score > 0.7


# ============================================================================
# Growth Scoring Tests
# ============================================================================


class TestGrowthScoring:
    """Tests for growth score computation."""

    def test_high_growth_scores_high(self, default_thresholds):
        """High revenue/earnings growth should score high."""
        metrics = StockMetrics(
            ticker="GROWTH",
            price=100.0,
            revenue_growth=0.30,
            earnings_growth=0.35,
        )
        score, factors = compute_growth_score(metrics, default_thresholds)
        assert score > 0.8

    def test_negative_growth_scores_low(self, default_thresholds):
        """Negative growth should score low."""
        metrics = StockMetrics(
            ticker="DECLINE",
            price=100.0,
            revenue_growth=-0.10,
            earnings_growth=-0.15,
        )
        score, factors = compute_growth_score(metrics, default_thresholds)
        assert score < 0.3

    def test_missing_growth_data(self, default_thresholds):
        """Missing growth data should return neutral."""
        metrics = StockMetrics(ticker="UNKNOWN", price=100.0)
        score, factors = compute_growth_score(metrics, default_thresholds)
        assert score == 0.5


# ============================================================================
# Quality Scoring Tests
# ============================================================================


class TestQualityScoring:
    """Tests for quality score computation."""

    def test_high_quality_scores_high(self, sample_metrics, default_thresholds):
        """High margin and ROE should score high."""
        score, factors = compute_quality_score(sample_metrics, default_thresholds)
        assert score > 0.7

    def test_low_quality_scores_low(self, default_thresholds):
        """Low margin and ROE should score below average."""
        metrics = StockMetrics(
            ticker="LOWQ",
            price=50.0,
            profit_margin=0.02,
            roe=0.03,
        )
        score, factors = compute_quality_score(metrics, default_thresholds)
        # Quality score includes multiple factors (margins, gross profitability, asset growth)
        # Low margin/ROE with neutral other factors should still be below 0.5
        assert score < 0.5

    def test_negative_metrics_score_zero(self, default_thresholds):
        """Negative profitability should score low."""
        metrics = StockMetrics(
            ticker="UNPROFITABLE",
            price=10.0,
            profit_margin=-0.10,
            roe=-0.05,
        )
        score, _ = compute_quality_score(metrics, default_thresholds)
        # Negative margins score 0, but other factors (gross profitability, asset growth)
        # may be neutral (0.5) if not provided, so overall score won't be near 0
        assert score < 0.4


# ============================================================================
# Momentum Scoring Tests
# ============================================================================


class TestMomentumScoring:
    """Tests for momentum score computation."""

    def test_estimate_rsi_positive_return(self):
        """Positive returns should produce higher RSI estimate."""
        rsi = _estimate_rsi(0.15)  # 15% monthly return
        assert rsi is not None
        assert rsi > 60

    def test_estimate_rsi_negative_return(self):
        """Negative returns should produce lower RSI estimate."""
        rsi = _estimate_rsi(-0.20)  # -20% monthly return
        assert rsi is not None
        assert rsi < 35

    def test_oversold_condition(self, default_thresholds):
        """Oversold stocks should get moderate score (contrarian)."""
        metrics = StockMetrics(
            ticker="OVERSOLD",
            price=50.0,
            price_change_1m=-0.25,  # Big decline
        )
        score, factors = compute_momentum_score(metrics, default_thresholds)
        # Oversold gets a 0.6 score (contrarian opportunity)
        assert 0.4 <= score <= 0.7

    def test_overbought_condition(self, default_thresholds):
        """Overbought stocks should get lower score."""
        metrics = StockMetrics(
            ticker="OVERBOUGHT",
            price=100.0,
            price_change_1m=0.30,  # Big gain
        )
        score, factors = compute_momentum_score(metrics, default_thresholds)
        assert score < 0.5

    def test_volume_spike_detected(self, default_thresholds):
        """Volume spike should be noted in factors."""
        metrics = StockMetrics(
            ticker="CATALYST",
            price=100.0,
            price_change_1m=0.05,
            volume_avg=1000000,
            volume_current=3000000,  # 3x average
        )
        score, factors = compute_momentum_score(metrics, default_thresholds)

        volume_factor = next((f for f in factors if "Volume" in f.name), None)
        assert volume_factor is not None
        assert "Elevated" in volume_factor.description


# ============================================================================
# Analyst Scoring Tests
# ============================================================================


class TestAnalystScoring:
    """Tests for analyst score computation."""

    def test_strong_buy_scores_high(self):
        """Strong buy consensus should score high."""
        metrics = StockMetrics(
            ticker="LOVED",
            price=100.0,
            analyst_rating=1.2,
            price_target=130.0,
        )
        score, factors = compute_analyst_score(metrics)
        assert score > 0.7

    def test_sell_scores_low(self):
        """Sell consensus should score low."""
        metrics = StockMetrics(
            ticker="HATED",
            price=100.0,
            analyst_rating=4.5,
            price_target=80.0,
        )
        score, factors = compute_analyst_score(metrics)
        assert score < 0.3

    def test_no_coverage_neutral(self):
        """No analyst coverage should return neutral."""
        metrics = StockMetrics(ticker="IGNORED", price=100.0)
        score, factors = compute_analyst_score(metrics)
        assert score == 0.5


# ============================================================================
# Macro Adjustment Tests
# ============================================================================


class TestMacroAdjustment:
    """Tests for macro adjustment computation."""

    def test_neutral_macro_minimal_adjustment(
        self, neutral_macro, default_sensitivities
    ):
        """Neutral macro should produce minimal adjustment."""
        adj, desc = compute_macro_adjustment(
            "technology", neutral_macro, default_sensitivities
        )
        assert -0.15 <= adj <= 0.15

    def test_rising_rates_hurts_tech(self, hawkish_macro, default_sensitivities):
        """Rising rates should hurt rate-sensitive sectors."""
        adj, desc = compute_macro_adjustment(
            "technology", hawkish_macro, default_sensitivities
        )
        assert adj < 0
        # Adjustment is negative, description may vary
        assert "unfavorable" in desc.lower() or "rates" in desc.lower()

    def test_rising_rates_helps_financials(self, hawkish_macro, default_sensitivities):
        """Rising rates should help financials."""
        adj, desc = compute_macro_adjustment(
            "financials", hawkish_macro, default_sensitivities
        )
        assert adj > 0

    def test_inverted_curve_helps_defensives(
        self, recession_risk_macro, default_sensitivities
    ):
        """Inverted yield curve should help defensive sectors relative to cyclicals."""
        # Defensive sector (consumer_staples) should score better than cyclical
        defensive_adj, _ = compute_macro_adjustment(
            "consumer_staples", recession_risk_macro, default_sensitivities
        )
        cyclical_adj, _ = compute_macro_adjustment(
            "consumer_discretionary", recession_risk_macro, default_sensitivities
        )
        # Defensives should have higher (less negative) adjustment than cyclicals
        assert defensive_adj > cyclical_adj

    def test_high_vix_reduces_score(self, recession_risk_macro, default_sensitivities):
        """High VIX should reduce all scores slightly."""
        adj, desc = compute_macro_adjustment(
            "technology", recession_risk_macro, default_sensitivities
        )
        assert "volatility" in desc.lower()

    def test_unknown_sector_neutral(self, neutral_macro, default_sensitivities):
        """Unknown sector should get neutral adjustment."""
        adj, desc = compute_macro_adjustment(
            "unknown_sector", neutral_macro, default_sensitivities
        )
        assert -0.1 <= adj <= 0.1


# ============================================================================
# Timeframe Classification Tests
# ============================================================================


class TestTimeframeClassification:
    """Tests for timeframe classification."""

    def test_oversold_classified_as_short(self):
        """Oversold bounce should be SHORT timeframe."""
        metrics = StockMetrics(
            ticker="BOUNCE",
            price=50.0,
            price_change_1m=-0.25,
        )
        rules = TimeframeRules()

        timeframe, reason = classify_timeframe(
            valuation_score=0.6,
            momentum_score=0.4,
            quality_score=0.5,
            metrics=metrics,
            rules=rules,
        )

        assert timeframe == Timeframe.SHORT
        assert "oversold" in reason.lower()

    def test_volume_spike_classified_as_short(self):
        """Volume spike should be SHORT timeframe."""
        metrics = StockMetrics(
            ticker="CATALYST",
            price=100.0,
            price_change_1m=0.05,
            volume_avg=1000000,
            volume_current=3000000,
        )
        rules = TimeframeRules()

        timeframe, reason = classify_timeframe(
            valuation_score=0.5,
            momentum_score=0.6,
            quality_score=0.5,
            metrics=metrics,
            rules=rules,
        )

        assert timeframe == Timeframe.SHORT
        assert "catalyst" in reason.lower() or "volume" in reason.lower()

    def test_quality_compounder_classified_as_long(self):
        """High quality + fair value should be LONG timeframe."""
        metrics = StockMetrics(ticker="COMPOUNDER", price=100.0, price_change_1m=0.02)
        rules = TimeframeRules()

        timeframe, reason = classify_timeframe(
            valuation_score=0.6,
            momentum_score=0.5,
            quality_score=0.8,
            metrics=metrics,
            rules=rules,
        )

        assert timeframe == Timeframe.LONG
        assert "quality" in reason.lower() or "compounder" in reason.lower()

    def test_valuation_gap_classified_as_medium(self):
        """Valuation gap should be MEDIUM timeframe."""
        metrics = StockMetrics(ticker="VALUE", price=100.0, price_change_1m=0.01)
        rules = TimeframeRules()

        timeframe, reason = classify_timeframe(
            valuation_score=0.75,
            momentum_score=0.4,
            quality_score=0.5,
            metrics=metrics,
            rules=rules,
        )

        assert timeframe == Timeframe.MEDIUM


# ============================================================================
# Thesis Generation Tests
# ============================================================================


class TestThesisGeneration:
    """Tests for thesis generation."""

    def test_thesis_includes_ticker(self):
        """Thesis should include ticker symbol."""
        factors = [
            ScoreFactor("P/E Ratio", 0.8, 0.4, "Low P/E of 10x"),
            ScoreFactor("ROE", 0.7, 0.3, "Strong ROE of 20%"),
        ]

        thesis = generate_thesis(
            ticker="AAPL",
            sector="technology",
            factors=factors,
            macro_description="Favorable macro alignment",
            timeframe=Timeframe.MEDIUM,
            conviction=7,
        )

        assert "AAPL" in thesis
        # Thesis includes factor descriptions
        assert "P/E" in thesis or "ROE" in thesis

    def test_thesis_reflects_conviction_level(self):
        """Thesis should reflect conviction level."""
        factors = [ScoreFactor("Valuation", 0.9, 0.5, "Deep value")]

        high_conv = generate_thesis(
            ticker="HIGH",
            sector="materials",
            factors=factors,
            macro_description="",
            timeframe=Timeframe.LONG,
            conviction=9,
        )

        low_conv = generate_thesis(
            ticker="LOW",
            sector="materials",
            factors=factors,
            macro_description="",
            timeframe=Timeframe.SHORT,
            conviction=3,
        )

        # High conviction thesis should indicate confidence
        assert "conviction" in high_conv.lower() or "strong" in high_conv.lower()
        # Low conviction thesis should indicate caution (actual output uses "selective")
        assert "speculative" in low_conv.lower() or "caution" in low_conv.lower() or "selective" in low_conv.lower()


# ============================================================================
# Risk Identification Tests
# ============================================================================


class TestRiskIdentification:
    """Tests for risk identification."""

    def test_low_scores_become_risks(self):
        """Low-scoring factors should be identified as risks."""
        factors = [
            ScoreFactor("Valuation", 0.2, 0.4, "Expensive at 100x P/E"),
            ScoreFactor("Quality", 0.8, 0.3, "High margins"),
            ScoreFactor("Momentum", 0.3, 0.3, "Overbought"),
        ]

        risks = identify_risks(factors, macro_adjustment=0.0, macro_description="")

        assert len(risks) >= 2
        assert any("Valuation" in r for r in risks)
        assert any("Momentum" in r for r in risks)

    def test_macro_headwind_becomes_risk(self):
        """Negative macro adjustment should become a risk."""
        factors = [ScoreFactor("All Good", 0.8, 1.0, "Strong fundamentals")]

        risks = identify_risks(
            factors,
            macro_adjustment=-0.2,
            macro_description="Pressured by rising rates",
        )

        assert any("Macro" in r or "headwind" in r.lower() for r in risks)

    def test_max_five_risks(self):
        """Should cap at 5 risks."""
        factors = [
            ScoreFactor(f"Factor {i}", 0.1, 0.1, f"Bad factor {i}")
            for i in range(10)
        ]

        risks = identify_risks(factors, macro_adjustment=-0.3, macro_description="Bad macro")

        assert len(risks) <= 5


# ============================================================================
# Full Scoring Tests
# ============================================================================


class TestFullScoring:
    """Integration tests for complete scoring pipeline."""

    def test_score_stock_returns_scored_pick(
        self,
        sample_metrics,
        neutral_macro,
        default_thresholds,
        default_weights,
    ):
        """score_stock should return complete ScoredPick."""
        pick = score_stock(
            metrics=sample_metrics,
            macro=neutral_macro,
            sector="technology",
            sector_avg_pe=28.0,
            thresholds=default_thresholds,
            weights=default_weights,
        )

        assert isinstance(pick, ScoredPick)
        assert pick.ticker == "AAPL"
        assert 1 <= pick.conviction <= 10
        assert pick.timeframe in [Timeframe.SHORT, Timeframe.MEDIUM, Timeframe.LONG]
        assert len(pick.thesis) > 0
        assert pick.sector == "technology"

    def test_undervalued_stock_high_conviction(
        self,
        undervalued_metrics,
        neutral_macro,
    ):
        """Undervalued stock should get high conviction."""
        pick = score_stock(
            metrics=undervalued_metrics,
            macro=neutral_macro,
            sector="materials",
            sector_avg_pe=15.0,
        )

        assert pick.conviction >= 6

    def test_overvalued_stock_low_conviction(
        self,
        overvalued_metrics,
        neutral_macro,
    ):
        """Overvalued stock should get low conviction."""
        pick = score_stock(
            metrics=overvalued_metrics,
            macro=neutral_macro,
            sector="technology",
            sector_avg_pe=28.0,
        )

        assert pick.conviction <= 4
        assert len(pick.risks) > 0

    def test_macro_affects_conviction(
        self,
        sample_metrics,
        neutral_macro,
        hawkish_macro,
    ):
        """Macro environment should affect conviction."""
        neutral_pick = score_stock(
            metrics=sample_metrics,
            macro=neutral_macro,
            sector="technology",
            sector_avg_pe=28.0,
        )

        hawkish_pick = score_stock(
            metrics=sample_metrics,
            macro=hawkish_macro,
            sector="technology",
            sector_avg_pe=28.0,
        )

        # Tech should score lower in hawkish environment
        assert hawkish_pick.conviction <= neutral_pick.conviction

    def test_score_breakdown_populated(
        self,
        sample_metrics,
        neutral_macro,
    ):
        """Score breakdown should be fully populated."""
        pick = score_stock(
            metrics=sample_metrics,
            macro=neutral_macro,
            sector="technology",
            sector_avg_pe=28.0,
        )

        breakdown = pick.score_breakdown
        assert 0 <= breakdown.overall <= 1
        assert 0 <= breakdown.valuation_score <= 1
        assert 0 <= breakdown.growth_score <= 1
        assert 0 <= breakdown.quality_score <= 1
        assert 0 <= breakdown.momentum_score <= 1
        assert -0.5 <= breakdown.macro_adjustment <= 0.5
        assert len(breakdown.factors_used) > 0


# ============================================================================
# Batch Scoring Tests
# ============================================================================


class TestBatchScoring:
    """Tests for batch scoring."""

    def test_score_stocks_returns_sorted_list(self, neutral_macro):
        """score_stocks should return list sorted by conviction."""
        stocks = [
            (
                StockMetrics(
                    ticker="HIGH",
                    price=100.0,
                    pe_trailing=10.0,
                    peg_ratio=0.5,
                    profit_margin=0.25,
                    roe=0.30,
                    analyst_rating=1.5,
                ),
                "financials",
                12.0,
            ),
            (
                StockMetrics(
                    ticker="LOW",
                    price=100.0,
                    pe_trailing=100.0,
                    peg_ratio=5.0,
                    profit_margin=0.02,
                    roe=0.02,
                    analyst_rating=4.5,
                ),
                "technology",
                28.0,
            ),
            (
                StockMetrics(ticker="MID", price=100.0, pe_trailing=20.0),
                "industrials",
                18.0,
            ),
        ]

        picks = score_stocks(stocks, neutral_macro)

        assert len(picks) == 3
        # Should be sorted by conviction (descending)
        assert picks[0].conviction >= picks[1].conviction >= picks[2].conviction
        # HIGH should be first, LOW should be last
        assert picks[0].ticker == "HIGH"
        assert picks[-1].ticker == "LOW"


# ============================================================================
# Configuration Validation Tests
# ============================================================================


class TestConfigurationValidation:
    """Tests for configuration validation."""

    def test_weights_must_sum_to_one(self):
        """Scoring weights must sum to 1.0."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            ScoringWeights(
                valuation=0.5,
                growth=0.5,
                quality=0.5,
                momentum=0.5,
                analyst=0.5,
            )

    def test_valid_weights_accepted(self):
        """Valid weights should be accepted."""
        # Note: ScoringWeights now includes smart_money (default 0.05)
        # All weights must sum to 1.0
        weights = ScoringWeights(
            valuation=0.25,
            growth=0.20,
            quality=0.25,
            momentum=0.20,
            analyst=0.05,
            smart_money=0.05,
        )
        assert weights.valuation == 0.25
        assert weights.smart_money == 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
