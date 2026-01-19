"""
Scoring Bridge Module.

Maps between existing pipeline types (StockMetrics, MacroContext) and
the new enhanced scoring system (StockData, RegimeContext).

This is the integration layer for Module 5.1 (Pipeline Updates).
"""

from dataclasses import asdict
from datetime import date
from typing import Sequence

from .analysis_types import StockMetrics, MacroContext
from .score_aggregator import (
    StockData,
    EnhancedScore,
    score_stock,
    score_stocks,
    select_picks,
)
from .regime import (
    RegimeContext,
    detect_market_regime,
    get_regime_weights,
    MarketRegime,
)
from .risk import RiskFilters, PortfolioConstraints
from .models import Timeframe


def metrics_to_stock_data(
    metrics: StockMetrics,
    sector: str,
    prices: list[float] | None = None,
    volumes: list[float] | None = None,
    insider_trades: list[dict] | None = None,
    current_13f_holdings: list[dict] | None = None,
    previous_13f_holdings: list[dict] | None = None,
    congress_trades: list[dict] | None = None,
    next_earnings_date: date | str | None = None,
) -> StockData:
    """
    Convert existing StockMetrics to new StockData format.

    Maps fields from the pipeline's StockMetrics to the enhanced scoring
    system's StockData. Handles missing/optional fields gracefully.

    Args:
        metrics: Pipeline StockMetrics object
        sector: Sector classification
        prices: Historical prices (252 days, most recent first)
        volumes: Historical volumes matching prices
        insider_trades: Form 4 insider transactions
        current_13f_holdings: Current quarter 13F holdings
        previous_13f_holdings: Previous quarter 13F holdings
        congress_trades: Congressional trading data
        next_earnings_date: Next earnings report date

    Returns:
        StockData ready for enhanced scoring
    """
    # Calculate gross profit margin from components if available
    gross_profit_margin = None
    if metrics.profit_margin is not None:
        # Use profit margin as proxy (not exact but available)
        gross_profit_margin = metrics.profit_margin

    # Calculate debt-to-equity from price-to-book if ROE available
    # D/E = (1/ROE * earnings_yield) - 1 approximately
    # This is a rough proxy since we don't have direct D/E
    debt_equity = None

    return StockData(
        ticker=metrics.ticker,
        sector=sector,
        price=metrics.price,
        prices=prices,
        volumes=volumes,
        price_change_1m=metrics.price_change_1m,
        price_change_12m=metrics.price_change_12m,
        # Fundamentals
        market_cap=metrics.market_cap,
        eps=_compute_eps(metrics),
        book_value=_compute_book_value(metrics),
        fcf=None,  # Not available in current metrics
        price_to_book=metrics.price_to_book,
        # Quality metrics
        gross_profit_margin=gross_profit_margin,
        revenue=None,  # Not directly available
        cogs=None,
        total_assets=metrics.total_assets,
        roe=metrics.roe,
        debt_equity=debt_equity,
        margin_history=None,  # Would need historical data
        # Risk metrics
        avg_volume=metrics.volume_avg,
        days_to_cover=metrics.days_to_cover,
        current_ratio=None,  # Not available
        volatility=None,  # Will be computed from prices
        beta=None,  # Will be computed from prices
        # Smart money
        current_13f_holdings=current_13f_holdings,
        previous_13f_holdings=previous_13f_holdings,
        insider_trades=insider_trades,
        congress_trades=congress_trades,
        # Catalyst
        next_earnings_date=next_earnings_date,
        # Momentum - earnings revisions (not currently available)
        current_estimate=None,
        estimate_30d_ago=None,
        estimate_90d_ago=None,
    )


def _compute_eps(metrics: StockMetrics) -> float | None:
    """Compute EPS from PE and price if available."""
    if metrics.pe_trailing and metrics.price and metrics.pe_trailing > 0:
        return metrics.price / metrics.pe_trailing
    return None


def _compute_book_value(metrics: StockMetrics) -> float | None:
    """Compute book value per share from P/B and price if available."""
    if metrics.price_to_book and metrics.price and metrics.price_to_book > 0:
        return metrics.price / metrics.price_to_book
    return None


def macro_to_regime(
    macro: MacroContext,
    spy_prices: list[float] | None = None,
    spy_price_current: float | None = None,
    spy_sma_200: float | None = None,
) -> RegimeContext:
    """
    Convert MacroContext to RegimeContext for regime-aware scoring.

    Uses VIX from macro context and optional SPY data for full classification.

    Args:
        macro: MacroContext from pipeline
        spy_prices: SPY price history (252 days, most recent first)
        spy_price_current: Current SPY price
        spy_sma_200: Pre-computed 200-day SMA

    Returns:
        RegimeContext for scoring
    """
    return detect_market_regime(
        spy_prices=spy_prices,
        spy_price_current=spy_price_current,
        spy_sma_200=spy_sma_200,
        vix_current=macro.vix,
    )


def score_stocks_enhanced(
    metrics_by_ticker: dict[str, StockMetrics],
    sectors: dict[str, str],
    macro_context: MacroContext,
    spy_prices: list[float] | None = None,
    insider_by_ticker: dict[str, list[dict]] | None = None,
    holdings_13f_current: dict[str, list[dict]] | None = None,
    holdings_13f_previous: dict[str, list[dict]] | None = None,
    congress_by_ticker: dict[str, list[dict]] | None = None,
    earnings_dates: dict[str, date | str] | None = None,
    risk_filters: RiskFilters | None = None,
    portfolio_constraints: PortfolioConstraints | None = None,
    today: date | None = None,
) -> tuple[list[EnhancedScore], RegimeContext]:
    """
    Main entry point for enhanced scoring in the pipeline.

    Converts pipeline data to new formats and runs enhanced scoring.

    Args:
        metrics_by_ticker: Stock metrics keyed by ticker
        sectors: Sector mapping keyed by ticker
        macro_context: Macro context from pipeline
        spy_prices: SPY prices for regime detection
        insider_by_ticker: Insider trades grouped by ticker
        holdings_13f_current: Current 13F holdings by ticker
        holdings_13f_previous: Previous 13F holdings by ticker
        congress_by_ticker: Congress trades by ticker
        earnings_dates: Next earnings dates by ticker
        risk_filters: Risk filter configuration
        portfolio_constraints: Position sizing constraints
        today: Reference date (defaults to today)

    Returns:
        (list of EnhancedScore sorted by score, RegimeContext)
    """
    today = today or date.today()
    insider_by_ticker = insider_by_ticker or {}
    holdings_13f_current = holdings_13f_current or {}
    holdings_13f_previous = holdings_13f_previous or {}
    congress_by_ticker = congress_by_ticker or {}
    earnings_dates = earnings_dates or {}

    # Detect regime from macro context
    regime_context = macro_to_regime(macro_context, spy_prices=spy_prices)

    # Convert all metrics to StockData
    stock_data_list: list[StockData] = []
    for ticker, metrics in metrics_by_ticker.items():
        sector = sectors.get(ticker, "Unknown")
        data = metrics_to_stock_data(
            metrics=metrics,
            sector=sector,
            prices=None,  # Would need historical price service
            volumes=None,
            insider_trades=insider_by_ticker.get(ticker),
            current_13f_holdings=holdings_13f_current.get(ticker),
            previous_13f_holdings=holdings_13f_previous.get(ticker),
            congress_trades=congress_by_ticker.get(ticker),
            next_earnings_date=earnings_dates.get(ticker),
        )
        stock_data_list.append(data)

    # Score all stocks
    scores = score_stocks(
        stocks=stock_data_list,
        regime_context=regime_context,
        sector_performance=None,  # Could add sector ETF performance
        market_prices=spy_prices,
        risk_filters=risk_filters,
        portfolio_constraints=portfolio_constraints,
        today=today,
    )

    return scores, regime_context


def select_enhanced_picks(
    scores: list[EnhancedScore],
    picks_per_timeframe: tuple[int, int] = (3, 7),
    max_sector_per_timeframe: int = 2,
) -> dict[Timeframe, list[EnhancedScore]]:
    """
    Select final picks with sector diversification.

    Wrapper around select_picks that applies concentration limits.

    Args:
        scores: EnhancedScores sorted by score descending
        picks_per_timeframe: (min, max) picks per timeframe
        max_sector_per_timeframe: Max stocks from same sector

    Returns:
        Dict mapping Timeframe to selected picks
    """
    return select_picks(
        scores=scores,
        picks_per_timeframe=picks_per_timeframe,
        max_sector_per_timeframe=max_sector_per_timeframe,
    )


def enhanced_score_to_legacy_format(
    score: EnhancedScore,
    metrics: StockMetrics,
) -> dict:
    """
    Convert EnhancedScore to format compatible with existing reports.

    This allows gradual migration - the new scoring can produce data
    that works with existing presentation layer.

    Args:
        score: EnhancedScore from new system
        metrics: Original StockMetrics for price data

    Returns:
        Dict compatible with existing StockPick/ScoredPick format
    """
    # Calculate stop loss based on conviction
    if score.conviction >= 8:
        stop_pct = 0.05
    elif score.conviction >= 5:
        stop_pct = 0.08
    else:
        stop_pct = 0.12

    stop_loss = metrics.price * (1 - stop_pct) if metrics.price else None

    # Generate thesis from factor breakdown
    thesis = _generate_thesis_from_factors(score)

    # Generate risks from factor weaknesses
    risks = _generate_risks_from_factors(score)

    return {
        "ticker": score.ticker,
        "timeframe": score.timeframe,
        "conviction": score.conviction,
        "conviction_normalized": score.score / 100.0,  # 0-1 scale
        "score": score.score,
        "thesis": thesis,
        "risks": risks,
        "entry_price": metrics.price,
        "target_price": metrics.price * (1 + score.score / 100 * 0.3) if metrics.price and score.conviction > 5 else None,
        "stop_loss": stop_loss,
        "position_size": score.position_size,
        "regime": score.regime.value,
        "sector": score.sector,
        "factor_scores": score.factor_scores,
        "weights_used": {
            "quality": score.weights_used.quality,
            "value": score.weights_used.value,
            "momentum": score.weights_used.momentum,
            "low_vol": score.weights_used.low_vol,
            "smart_money": score.weights_used.smart_money,
            "catalyst": score.weights_used.catalyst,
        },
        "data_completeness": score.data_completeness,
        "passes_filters": score.passes_filters,
        "filter_reason": score.filter_reason,
    }


def _generate_thesis_from_factors(score: EnhancedScore) -> str:
    """Generate investment thesis from factor scores."""
    parts = []
    factors = score.factor_scores

    # Lead with strongest factor
    factor_ranking = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    top_factor, top_score = factor_ranking[0]

    factor_descriptions = {
        "quality": "strong fundamentals",
        "value": "attractive valuation",
        "momentum": "positive price momentum",
        "low_vol": "defensive characteristics",
        "smart_money": "institutional accumulation",
        "catalyst": "near-term catalysts",
    }

    if top_score >= 70:
        parts.append(f"Shows {factor_descriptions.get(top_factor, top_factor)}")

    # Add regime context
    regime_context = {
        MarketRegime.BULL: "bull market conditions favor risk-on positioning",
        MarketRegime.BEAR: "bear market conditions favor defensive quality",
        MarketRegime.SIDEWAYS: "neutral market supports balanced approach",
        MarketRegime.HIGH_VOL: "high volatility warrants caution",
    }
    parts.append(regime_context.get(score.regime, ""))

    # Add timeframe note
    timeframe_notes = {
        Timeframe.SHORT: "Short-term opportunity (days to weeks)",
        Timeframe.MEDIUM: "Medium-term holding (weeks to months)",
        Timeframe.LONG: "Long-term investment (months to years)",
    }
    parts.append(timeframe_notes.get(score.timeframe, ""))

    # Add conviction note
    if score.conviction >= 8:
        parts.append("High conviction based on multiple confirming signals")
    elif score.conviction >= 6:
        parts.append("Moderate conviction with supporting factors")

    return ". ".join(p for p in parts if p) + "."


def _generate_risks_from_factors(score: EnhancedScore) -> list[str]:
    """Generate risk factors from weak factor scores."""
    risks = []
    factors = score.factor_scores

    # Flag weak factors as risks
    if factors.get("quality", 50) < 40:
        risks.append("Quality concerns: weak fundamentals")
    if factors.get("value", 50) < 35:
        risks.append("Valuation risk: premium pricing")
    if factors.get("momentum", 50) < 35:
        risks.append("Momentum weakness: negative price trend")
    if factors.get("low_vol", 50) < 35:
        risks.append("High volatility: larger drawdown potential")
    if factors.get("smart_money", 50) < 40:
        risks.append("Limited institutional support")

    # Add regime-specific risks
    if score.regime == MarketRegime.HIGH_VOL:
        risks.append("Market volatility elevated - position size accordingly")
    if score.regime == MarketRegime.BEAR and factors.get("momentum", 50) > 60:
        risks.append("Momentum in bear market may reverse")

    # Add data quality risk
    if score.data_completeness < 0.5:
        risks.append("Limited data availability - higher uncertainty")

    # Limit to top 5 risks
    return risks[:5] if risks else ["Standard market risk applies"]


# Utility functions for pipeline integration

def get_regime_summary(regime_context: RegimeContext) -> dict:
    """Get regime summary for report/logging."""
    return {
        "regime": regime_context.regime.value,
        "description": regime_context.description,
        "confidence": regime_context.confidence,
        "spy_price": regime_context.spy_price,
        "spy_sma_200": regime_context.spy_sma_200,
        "vix": regime_context.vix,
        "is_risk_on": regime_context.is_risk_on,
        "is_risk_off": regime_context.is_risk_off,
    }


def get_scoring_stats(scores: list[EnhancedScore]) -> dict:
    """Get summary statistics for scored stocks."""
    if not scores:
        return {"total": 0}

    passing = [s for s in scores if s.passes_filters]
    by_timeframe = {
        Timeframe.SHORT: [s for s in passing if s.timeframe == Timeframe.SHORT],
        Timeframe.MEDIUM: [s for s in passing if s.timeframe == Timeframe.MEDIUM],
        Timeframe.LONG: [s for s in passing if s.timeframe == Timeframe.LONG],
    }

    avg_score = sum(s.score for s in scores) / len(scores)
    avg_completeness = sum(s.data_completeness for s in scores) / len(scores)

    return {
        "total": len(scores),
        "passing_filters": len(passing),
        "filtered_out": len(scores) - len(passing),
        "by_timeframe": {tf.value: len(lst) for tf, lst in by_timeframe.items()},
        "avg_score": round(avg_score, 2),
        "avg_data_completeness": round(avg_completeness, 2),
        "score_range": (
            round(min(s.score for s in scores), 2),
            round(max(s.score for s in scores), 2),
        ),
    }
