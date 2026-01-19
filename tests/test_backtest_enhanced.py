"""
Unit tests for Enhanced Backtesting Framework.

Tests cover:
- EnhancedBacktestConfig defaults
- EnhancedBacktestTrade calculations
- Factor attribution
- Regime performance breakdown
- Performance tracking functions
"""

import pytest
from datetime import date, timedelta

from domain.backtest_enhanced import (
    EnhancedBacktestConfig,
    EnhancedBacktestTrade,
    EnhancedBacktestResult,
    PeriodReturn,
    FactorAttribution,
    RegimePerformance,
    track_pick_performance,
    analyze_picks_by_regime,
    analyze_factor_effectiveness,
    _compute_correlation,
    _calculate_momentum,
    _get_price_at_date,
)
from domain.regime import MarketRegime
from domain.models import Timeframe


class TestEnhancedBacktestConfig:
    """Tests for EnhancedBacktestConfig."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = EnhancedBacktestConfig()

        assert config.top_n_picks == 10
        assert config.min_conviction == 5
        assert config.rebalance_freq == "weekly"
        assert config.transaction_cost_bps == 10.0
        assert config.max_position_weight == 0.08
        assert config.benchmark_ticker == "SPY"

    def test_total_cost_bps(self):
        """Total cost includes transaction + slippage round trip."""
        config = EnhancedBacktestConfig(
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
        )
        # Round trip = (10 + 5) * 2 = 30 bps
        assert config.total_cost_bps == 30.0


class TestEnhancedBacktestTrade:
    """Tests for EnhancedBacktestTrade calculations."""

    def _make_trade(
        self,
        entry_price: float = 100.0,
        exit_price: float = 110.0,
        benchmark_entry: float = 450.0,
        benchmark_exit: float = 460.0,
        transaction_cost: float = 0.0,
    ) -> EnhancedBacktestTrade:
        return EnhancedBacktestTrade(
            ticker="TEST",
            entry_date=date(2024, 1, 1),
            exit_date=date(2024, 1, 8),
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=0.05,
            score=75.0,
            conviction=8,
            timeframe=Timeframe.MEDIUM,
            sector="Technology",
            regime_at_entry=MarketRegime.BULL,
            factor_scores={
                "quality": 70,
                "value": 60,
                "momentum": 80,
                "low_vol": 55,
                "smart_money": 65,
                "catalyst": 50,
            },
            factor_weights={
                "quality": 0.25,
                "value": 0.15,
                "momentum": 0.30,
                "low_vol": 0.10,
                "smart_money": 0.15,
                "catalyst": 0.05,
            },
            benchmark_entry=benchmark_entry,
            benchmark_exit=benchmark_exit,
            transaction_cost=transaction_cost,
        )

    def test_gross_return_pct(self):
        """Gross return calculation."""
        trade = self._make_trade(entry_price=100.0, exit_price=110.0)
        assert trade.gross_return_pct == pytest.approx(10.0)

    def test_gross_return_negative(self):
        """Negative return calculation."""
        trade = self._make_trade(entry_price=100.0, exit_price=95.0)
        assert trade.gross_return_pct == pytest.approx(-5.0)

    def test_net_return_with_costs(self):
        """Net return accounts for transaction costs."""
        trade = self._make_trade(
            entry_price=100.0,
            exit_price=110.0,
            transaction_cost=0.30,  # 0.3% of position
        )
        # Gross = 10%, cost = 0.3%
        assert trade.net_return_pct == pytest.approx(9.7)

    def test_benchmark_return(self):
        """Benchmark return calculation."""
        trade = self._make_trade(
            benchmark_entry=450.0,
            benchmark_exit=460.0,
        )
        # (460 - 450) / 450 * 100 = 2.22%
        assert trade.benchmark_return_pct == pytest.approx(2.222, rel=0.01)

    def test_alpha_calculation(self):
        """Alpha = net return - benchmark return."""
        trade = self._make_trade(
            entry_price=100.0,
            exit_price=110.0,
            benchmark_entry=450.0,
            benchmark_exit=460.0,
        )
        # Net return = 10%, benchmark = 2.22%, alpha = 7.78%
        assert trade.alpha == pytest.approx(7.78, rel=0.01)

    def test_is_winner(self):
        """Winner has positive net return."""
        winner = self._make_trade(exit_price=105.0)
        loser = self._make_trade(exit_price=95.0)

        assert winner.is_winner is True
        assert loser.is_winner is False

    def test_beat_benchmark(self):
        """Beat benchmark when outperforming SPY."""
        # Stock: +10%, Benchmark: +2.2%
        beats = self._make_trade(exit_price=110.0)
        assert beats.beat_benchmark is True

        # Stock: +1%, Benchmark: +2.2%
        loses = self._make_trade(exit_price=101.0)
        assert loses.beat_benchmark is False

    def test_factor_contribution(self):
        """Factor contribution sums to alpha."""
        trade = self._make_trade()
        contributions = trade.factor_contribution()

        assert "quality" in contributions
        assert "momentum" in contributions

        # Contributions should sum to approximately alpha
        total_contribution = sum(contributions.values())
        assert total_contribution == pytest.approx(trade.alpha, rel=0.01)


class TestEnhancedBacktestResult:
    """Tests for EnhancedBacktestResult metrics."""

    def _make_result(self) -> EnhancedBacktestResult:
        """Create a result with sample data."""
        config = EnhancedBacktestConfig()
        result = EnhancedBacktestResult(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            config=config,
            tickers_analyzed=100,
        )

        # Add period returns
        result.period_returns = [
            PeriodReturn(
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 8),
                portfolio_return=2.5,
                benchmark_return=1.0,
                regime=MarketRegime.BULL,
                num_picks=10,
                num_trades=10,
                transaction_costs=50.0,
                top_performer="AAPL",
                worst_performer="XYZ",
            ),
            PeriodReturn(
                period_start=date(2024, 1, 8),
                period_end=date(2024, 1, 15),
                portfolio_return=-1.0,
                benchmark_return=-0.5,
                regime=MarketRegime.BULL,
                num_picks=10,
                num_trades=10,
                transaction_costs=50.0,
                top_performer="MSFT",
                worst_performer="ABC",
            ),
            PeriodReturn(
                period_start=date(2024, 1, 15),
                period_end=date(2024, 1, 22),
                portfolio_return=3.0,
                benchmark_return=1.5,
                regime=MarketRegime.SIDEWAYS,
                num_picks=10,
                num_trades=10,
                transaction_costs=50.0,
                top_performer="NVDA",
                worst_performer="DEF",
            ),
        ]

        return result

    def test_total_return_compounded(self):
        """Total return is compounded."""
        result = self._make_result()
        # (1.025) * (0.99) * (1.03) = 1.0449
        # Return = 4.49%
        assert result.total_return == pytest.approx(4.49, rel=0.01)

    def test_benchmark_return_compounded(self):
        """Benchmark return is compounded."""
        result = self._make_result()
        # (1.01) * (0.995) * (1.015) = 1.0199
        # Return = 1.99%
        assert result.benchmark_return == pytest.approx(1.99, rel=0.01)

    def test_alpha(self):
        """Alpha = total return - benchmark."""
        result = self._make_result()
        expected_alpha = result.total_return - result.benchmark_return
        assert result.alpha == pytest.approx(expected_alpha, rel=0.01)

    def test_total_transaction_costs(self):
        """Total costs sum across periods."""
        result = self._make_result()
        assert result.total_transaction_costs == 150.0

    def test_max_drawdown(self):
        """Max drawdown calculated correctly."""
        result = self._make_result()
        # After period 1: cumulative = 1.025, peak = 1.025
        # After period 2: cumulative = 1.015, peak = 1.025, DD = 0.97%
        # After period 3: cumulative = 1.045, peak = 1.045
        assert result.max_drawdown > 0
        assert result.max_drawdown < 5  # Should be small

    def test_sharpe_ratio_positive(self):
        """Sharpe ratio is positive for profitable strategy."""
        result = self._make_result()
        # With positive returns, Sharpe should be positive
        assert result.sharpe_ratio > 0

    def test_summary_generation(self):
        """Summary generates without error."""
        result = self._make_result()
        summary = result.summary()

        assert "Total Return" in summary
        assert "Alpha" in summary
        assert "Sharpe Ratio" in summary

    def test_to_dict_serializable(self):
        """to_dict returns JSON-serializable dict."""
        result = self._make_result()
        d = result.to_dict()

        assert "performance" in d
        assert "alpha" in d["performance"]
        assert isinstance(d["start_date"], str)


class TestPerformanceTracking:
    """Tests for performance tracking functions."""

    def test_track_pick_performance(self):
        """Track individual pick performance."""
        from domain.score_aggregator import StockData, score_stock
        from domain.regime import detect_market_regime

        # Create a simple enhanced score
        data = StockData(
            ticker="TEST",
            sector="Technology",
            price=100.0,
            market_cap=50e9,
            avg_volume=5_000_000,
        )

        regime = detect_market_regime(vix_current=15.0)
        pick = score_stock(data, regime_context=regime)

        result = track_pick_performance(
            pick=pick,
            entry_price=100.0,
            exit_price=110.0,
            holding_days=7,
        )

        assert result["ticker"] == "TEST"
        assert result["return_pct"] == 10.0
        assert result["is_winner"] is True
        assert "factor_contributions" in result

    def test_analyze_picks_by_regime(self):
        """Analyze picks grouped by regime."""
        picks = [
            {"regime": "bull", "return_pct": 5.0, "is_winner": True, "ticker": "A"},
            {"regime": "bull", "return_pct": 3.0, "is_winner": True, "ticker": "B"},
            {"regime": "bear", "return_pct": -2.0, "is_winner": False, "ticker": "C"},
            {"regime": "bear", "return_pct": 1.0, "is_winner": True, "ticker": "D"},
        ]

        analysis = analyze_picks_by_regime(picks)

        assert "bull" in analysis
        assert "bear" in analysis
        assert analysis["bull"]["num_picks"] == 2
        assert analysis["bull"]["win_rate"] == 100.0
        assert analysis["bear"]["win_rate"] == 50.0

    def test_analyze_factor_effectiveness(self):
        """Analyze which factors predict returns."""
        picks = [
            {
                "return_pct": 10.0,
                "factor_scores": {"quality": 80, "momentum": 70},
                "factor_contributions": {"quality": 5.0, "momentum": 5.0},
            },
            {
                "return_pct": -5.0,
                "factor_scores": {"quality": 40, "momentum": 60},
                "factor_contributions": {"quality": -2.0, "momentum": -3.0},
            },
        ]

        analysis = analyze_factor_effectiveness(picks)

        assert "quality" in analysis
        assert "momentum" in analysis
        # Quality has higher score for winner, should correlate positively
        assert "correlation" in analysis["quality"]


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_correlation_perfect_positive(self):
        """Perfect positive correlation."""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        corr = _compute_correlation(x, y)
        assert corr == pytest.approx(1.0)

    def test_compute_correlation_perfect_negative(self):
        """Perfect negative correlation."""
        x = [1, 2, 3, 4, 5]
        y = [10, 8, 6, 4, 2]
        corr = _compute_correlation(x, y)
        assert corr == pytest.approx(-1.0)

    def test_compute_correlation_no_correlation(self):
        """Zero correlation for unrelated data."""
        x = [1, 2, 3, 4, 5]
        y = [5, 1, 4, 2, 3]  # Random
        corr = _compute_correlation(x, y)
        # Should be near zero but not exactly
        assert abs(corr) < 0.5

    def test_get_price_at_date(self):
        """Get price with lookback."""
        prices = {
            date(2024, 1, 1): 100.0,
            date(2024, 1, 2): 101.0,
            date(2024, 1, 5): 103.0,  # Skip weekend
        }

        # Exact match
        assert _get_price_at_date(prices, date(2024, 1, 1)) == 100.0

        # With lookback (weekend)
        assert _get_price_at_date(prices, date(2024, 1, 3)) == 101.0

    def test_calculate_momentum(self):
        """Calculate momentum metrics."""
        today = date(2024, 6, 15)
        prices = {
            today: 110.0,
            today - timedelta(days=30): 100.0,  # 1 month ago
            today - timedelta(days=365): 80.0,  # 12 months ago
        }

        momentum = _calculate_momentum(prices, today)

        # 1 month: (110 - 100) / 100 = 0.10
        assert momentum["change_1m"] == pytest.approx(0.10)

        # 12 month: (110 - 80) / 80 = 0.375
        assert momentum["change_12m"] == pytest.approx(0.375)


class TestFactorAttribution:
    """Tests for FactorAttribution dataclass."""

    def test_factor_attribution_creation(self):
        """Create factor attribution."""
        attr = FactorAttribution(
            factor="momentum",
            avg_score=65.0,
            contribution_to_alpha=3.5,
            correlation_with_returns=0.45,
            winners_avg=72.0,
            losers_avg=58.0,
        )

        assert attr.factor == "momentum"
        assert attr.winners_avg > attr.losers_avg


class TestRegimePerformance:
    """Tests for RegimePerformance dataclass."""

    def test_regime_performance_creation(self):
        """Create regime performance record."""
        perf = RegimePerformance(
            regime=MarketRegime.BULL,
            num_periods=10,
            num_trades=50,
            total_return=15.5,
            avg_return=1.55,
            hit_rate=62.0,
            win_rate=58.0,
            avg_alpha=0.5,
            sharpe_ratio=1.2,
        )

        assert perf.regime == MarketRegime.BULL
        assert perf.sharpe_ratio > 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
