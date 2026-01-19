"""
Unit tests for enhanced factor modules.

Tests cover:
- Quality Factor (Novy-Marx gross profitability, ROE, leverage, stability)
- Value Factor (earnings yield, book-to-market, FCF yield)
- Momentum Factor (12-1 month, volume-weighted, earnings revision)
- Low Volatility Factor (realized vol, beta)
- Smart Money Factor (13F, insider clusters, congress)
- Catalyst Factor (earnings proximity, sector rotation)
"""

import pytest
from datetime import date, timedelta

from domain.factors import (
    compute_quality_score,
    compute_value_score,
    compute_momentum_score,
    compute_low_vol_score,
    compute_smart_money_score,
    compute_catalyst_score,
    QualityFactorResult,
    ValueFactorResult,
    MomentumFactorResult,
    LowVolFactorResult,
    SmartMoneyFactorResult,
    CatalystFactorResult,
)
from domain.factors.quality import compute_gross_profitability
from domain.factors.value import compute_earnings_yield, compute_fcf_yield
from domain.factors.momentum import compute_price_momentum_12_1
from domain.factors.low_volatility import compute_realized_volatility, compute_beta
from domain.factors.smart_money import compute_insider_cluster_score
from domain.factors.catalyst import MarketRegime, compute_earnings_proximity_score


class TestQualityFactor:
    """Tests for Quality Factor module."""

    def test_gross_profitability_strong(self):
        """Strong GP/Assets > 33% should score high."""
        score, desc = compute_gross_profitability(
            revenue=1_000_000,
            cogs=600_000,  # 40% GP margin
            total_assets=1_000_000,  # 40% GP/Assets
        )
        assert score >= 75, f"Strong GP should score >=75, got {score}"
        assert "strong" in desc.lower() or "excellent" in desc.lower()

    def test_gross_profitability_weak(self):
        """Low GP/Assets < 10% should score low."""
        score, desc = compute_gross_profitability(
            revenue=1_000_000,
            cogs=950_000,  # 5% GP margin
            total_assets=1_000_000,  # 5% GP/Assets
        )
        assert score < 40, f"Weak GP should score <40, got {score}"

    def test_gross_profitability_unavailable(self):
        """Missing data should return neutral score."""
        score, desc = compute_gross_profitability(None, None, None)
        assert score == 50.0
        assert "unavailable" in desc.lower()

    def test_quality_composite_high(self):
        """High quality company should have high composite score."""
        result = compute_quality_score(
            gross_profit_margin=0.40,  # Excellent
            roe=0.22,  # Excellent
            debt_equity=0.3,  # Low leverage
            margin_history=[0.15, 0.16, 0.15, 0.14, 0.15],  # Stable
        )
        assert isinstance(result, QualityFactorResult)
        assert result.score >= 70, f"High quality should score >=70, got {result.score}"
        assert result.data_completeness == 1.0

    def test_quality_composite_low(self):
        """Low quality company should have low composite score."""
        result = compute_quality_score(
            gross_profit_margin=0.08,  # Weak
            roe=0.03,  # Low
            debt_equity=2.5,  # High leverage
            margin_history=[0.10, 0.05, 0.15, 0.02, 0.08],  # Volatile
        )
        assert result.score < 45, f"Low quality should score <45, got {result.score}"


class TestValueFactor:
    """Tests for Value Factor module."""

    def test_earnings_yield_high(self):
        """High E/P (low P/E) should score high."""
        score, desc = compute_earnings_yield(eps=10.0, price=100.0)  # 10% E/Y, P/E 10
        assert score >= 80, f"High E/Y should score >=80, got {score}"

    def test_earnings_yield_low(self):
        """Low E/P (high P/E) should score low."""
        score, desc = compute_earnings_yield(eps=2.0, price=100.0)  # 2% E/Y, P/E 50
        assert score < 35, f"Low E/Y should score <35, got {score}"

    def test_earnings_yield_negative(self):
        """Negative EPS should score very low."""
        score, desc = compute_earnings_yield(eps=-5.0, price=100.0)
        assert score < 35, f"Negative earnings should score <35, got {score}"
        assert "negative" in desc.lower()

    def test_fcf_yield_strong(self):
        """Strong FCF yield should score high."""
        score, desc = compute_fcf_yield(fcf=1e9, market_cap=10e9)  # 10% FCF yield
        assert score >= 80, f"Strong FCF yield should score >=80, got {score}"

    def test_fcf_yield_negative(self):
        """Negative FCF (cash burn) should score low."""
        score, desc = compute_fcf_yield(fcf=-500e6, market_cap=10e9)
        assert score < 30, f"Cash burn should score <30, got {score}"
        assert "burn" in desc.lower() or "negative" in desc.lower()

    def test_value_composite(self):
        """Test value composite with all data."""
        result = compute_value_score(
            eps=6.0,
            price=100.0,  # 6% E/Y
            price_to_book=1.5,  # Fair P/B
            fcf=800e6,
            market_cap=10e9,  # 8% FCF yield
        )
        assert isinstance(result, ValueFactorResult)
        assert 55 <= result.score <= 80
        assert result.data_completeness == 1.0


class TestMomentumFactor:
    """Tests for Momentum Factor module."""

    def test_momentum_12_1_strong(self):
        """Strong 12-1 month momentum should score high."""
        # Create price series: 252 days, starting at 100, ending at 140 (40% gain)
        # with last month flat to test 12-1 properly
        prices = []
        for i in range(252):
            if i <= 21:  # Last month: flat at 140
                prices.append(140.0)
            else:  # Previous 11 months: linear from 100 to 140
                progress = (252 - i) / 230
                prices.append(100 + progress * 40)

        score, desc = compute_price_momentum_12_1(prices)
        assert score >= 65, f"Strong momentum should score >=65, got {score}"

    def test_momentum_12_1_negative(self):
        """Negative 12-1 momentum should score low."""
        # Price declined from 100 to 70 over 12 months
        prices = [70.0 + (100 - 70) * i / 251 for i in range(252)]
        score, desc = compute_price_momentum_12_1(prices)
        assert score < 40, f"Negative momentum should score <40, got {score}"

    def test_momentum_insufficient_data(self):
        """Insufficient data should return neutral score."""
        score, desc = compute_price_momentum_12_1([100, 101, 102])
        assert score == 50.0
        assert "insufficient" in desc.lower()

    def test_momentum_composite_with_precomputed(self):
        """Test momentum with pre-computed values."""
        result = compute_momentum_score(
            price_change_12m=0.30,  # 30% 12M return
            price_change_1m=0.02,  # 2% 1M return (12-1 = 28%)
        )
        assert isinstance(result, MomentumFactorResult)
        assert result.score >= 60  # Should be good momentum


class TestLowVolatilityFactor:
    """Tests for Low Volatility Factor module."""

    def test_volatility_low(self):
        """Low volatility should score high (inverted factor)."""
        # Generate low vol price series (small daily moves)
        import math
        base = 100.0
        prices = []
        for i in range(253):
            # Small random-ish fluctuation (±0.5%)
            noise = 0.005 * math.sin(i * 0.5)
            prices.append(base * (1 + noise))

        score, vol, desc = compute_realized_volatility(prices=prices)
        assert score >= 70, f"Low vol should score >=70, got {score}"
        assert "low" in desc.lower()

    def test_volatility_high(self):
        """High volatility should score low (inverted factor)."""
        # Generate high vol price series with large random-ish moves
        import random
        random.seed(42)
        base = 100.0
        prices = [base]
        for i in range(252):
            # Large daily moves (±3-5% daily, ~50% annualized)
            daily_return = random.gauss(0, 0.03)
            prices.append(prices[-1] * (1 + daily_return))
        prices = list(reversed(prices))  # Most recent first

        score, vol, desc = compute_realized_volatility(prices=prices)
        assert score < 60, f"High vol should score <60, got {score} (vol: {vol})"

    def test_beta_defensive(self):
        """Defensive beta (<1) should score high."""
        # Stock moves half as much as market
        market_returns = [0.01, -0.02, 0.015, -0.01, 0.005] * 20
        stock_returns = [r * 0.5 for r in market_returns]  # Beta ~0.5

        score, beta, desc = compute_beta(
            stock_returns=stock_returns,
            market_returns=market_returns,
        )
        assert score >= 70, f"Defensive beta should score >=70, got {score}"
        assert beta is not None and beta < 0.7

    def test_beta_aggressive(self):
        """Aggressive beta (>1) should score low."""
        # Stock moves twice as much as market
        market_returns = [0.01, -0.02, 0.015, -0.01, 0.005] * 20
        stock_returns = [r * 2.0 for r in market_returns]  # Beta ~2.0

        score, beta, desc = compute_beta(
            stock_returns=stock_returns,
            market_returns=market_returns,
        )
        assert score < 40, f"Aggressive beta should score <40, got {score}"

    def test_low_vol_composite(self):
        """Test low vol composite with pre-computed values."""
        result = compute_low_vol_score(
            pre_computed_volatility=0.15,  # Low vol
            pre_computed_beta=0.7,  # Defensive
        )
        assert isinstance(result, LowVolFactorResult)
        assert result.score >= 70


class TestSmartMoneyFactor:
    """Tests for Smart Money Factor module."""

    def test_insider_cluster_detected(self):
        """3+ insiders buying should trigger cluster detection."""
        today = date(2026, 1, 18)
        trades = [
            {"insider_name": "CEO John", "insider_title": "CEO", "transaction_type": "P",
             "shares": 10000, "price": 100, "transaction_date": date(2026, 1, 10)},
            {"insider_name": "CFO Jane", "insider_title": "CFO", "transaction_type": "P",
             "shares": 5000, "price": 100, "transaction_date": date(2026, 1, 12)},
            {"insider_name": "Dir Bob", "insider_title": "Director", "transaction_type": "P",
             "shares": 2000, "price": 100, "transaction_date": date(2026, 1, 14)},
        ]
        score, count, desc = compute_insider_cluster_score(trades, today=today)
        assert score >= 80, f"Cluster buy should score >=80, got {score}"
        assert count >= 3
        assert "cluster" in desc.lower()

    def test_insider_no_activity(self):
        """No insider trades should return neutral."""
        score, count, desc = compute_insider_cluster_score([], today=date(2026, 1, 18))
        assert score == 50.0
        assert count == 0

    def test_smart_money_composite(self):
        """Test smart money composite with all signals."""
        today = date(2026, 1, 18)
        result = compute_smart_money_score(
            current_13f_holdings=[
                {"fund_name": "Berkshire Hathaway", "shares": 1000000},
            ],
            previous_13f_holdings=[],  # New position
            insider_trades=[
                {"insider_name": "CEO", "insider_title": "CEO", "transaction_type": "P",
                 "shares": 10000, "price": 100, "transaction_date": date(2026, 1, 10)},
            ],
            congress_trades=[
                {"representative": "Rep. Smith", "transaction_type": "purchase",
                 "amount_min": 15000, "amount_max": 50000, "transaction_date": date(2026, 1, 5)},
            ],
            today=today,
        )
        assert isinstance(result, SmartMoneyFactorResult)
        assert result.score >= 60  # Should be bullish with these signals


class TestCatalystFactor:
    """Tests for Catalyst Factor module."""

    def test_earnings_imminent(self):
        """Earnings within 7 days should score high."""
        today = date(2026, 1, 18)
        earnings = date(2026, 1, 25)  # 7 days away
        score, earn_date, desc = compute_earnings_proximity_score(earnings, today)
        assert score >= 85, f"Imminent earnings should score >=85, got {score}"
        assert "catalyst" in desc.lower() or "high" in desc.lower()

    def test_earnings_distant(self):
        """Earnings > 8 weeks away should score neutral."""
        today = date(2026, 1, 18)
        earnings = date(2026, 4, 1)  # ~10 weeks away
        score, earn_date, desc = compute_earnings_proximity_score(earnings, today)
        assert 40 <= score <= 55, f"Distant earnings should be neutral, got {score}"

    def test_sector_rotation_bull_tech(self):
        """Tech in bull market should score high."""
        result = compute_catalyst_score(
            sector="Technology",
            regime=MarketRegime.BULL,
        )
        assert result.score >= 65  # Tech favored in bull

    def test_sector_rotation_bear_utilities(self):
        """Utilities in bear market should score high."""
        result = compute_catalyst_score(
            sector="Utilities",
            regime=MarketRegime.BEAR,
        )
        assert result.score >= 65  # Utilities favored in bear

    def test_sector_rotation_bear_tech(self):
        """Tech in bear market should score low."""
        result = compute_catalyst_score(
            sector="Technology",
            regime=MarketRegime.BEAR,
        )
        assert result.score < 50  # Tech not favored in bear

    def test_catalyst_near_term_flag(self):
        """Near-term catalyst flag should be set correctly."""
        today = date(2026, 1, 18)
        result = compute_catalyst_score(
            sector="Technology",
            regime=MarketRegime.BULL,
            next_earnings_date=date(2026, 1, 28),  # 10 days away
            today=today,
        )
        assert isinstance(result, CatalystFactorResult)
        assert result.has_near_term_catalyst is True


class TestFactorScoreRanges:
    """Tests to verify score distributions are reasonable."""

    def test_all_factors_return_0_100(self):
        """All factors should return scores in 0-100 range."""
        quality = compute_quality_score(gross_profit_margin=0.50, roe=0.30)
        assert 0 <= quality.score <= 100

        value = compute_value_score(eps=10, price=100)
        assert 0 <= value.score <= 100

        momentum = compute_momentum_score(price_change_12m=0.50, price_change_1m=0.05)
        assert 0 <= momentum.score <= 100

        low_vol = compute_low_vol_score(pre_computed_volatility=0.20, pre_computed_beta=1.0)
        assert 0 <= low_vol.score <= 100

        smart_money = compute_smart_money_score()
        assert 0 <= smart_money.score <= 100

        catalyst = compute_catalyst_score(sector="Technology", regime=MarketRegime.SIDEWAYS)
        assert 0 <= catalyst.score <= 100

    def test_missing_data_returns_neutral(self):
        """Missing data should result in ~50 neutral score."""
        quality = compute_quality_score()  # No data
        assert 45 <= quality.score <= 55

        value = compute_value_score()  # No data
        assert 45 <= value.score <= 55

        momentum = compute_momentum_score()  # No data
        assert 45 <= momentum.score <= 55


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
