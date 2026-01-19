"""
Score Aggregator Module.

Main entry point for the enhanced scoring algorithm. Combines:
- Factor computations (quality, value, momentum, low_vol, smart_money, catalyst)
- Regime-aware weight adjustments
- Position sizing
- Risk filtering

Returns EnhancedScore with full breakdown for transparency.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import NamedTuple

from .factors import (
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
from .factors.catalyst import MarketRegime
from .regime import RegimeContext, FactorWeights, detect_market_regime, get_regime_weights
from .risk import (
    apply_risk_filters,
    compute_position_size,
    RiskFilters,
    PortfolioConstraints,
    PositionSizeResult,
)
from .models import Timeframe


class FactorScores(NamedTuple):
    """All factor scores for a stock."""
    quality: QualityFactorResult
    value: ValueFactorResult
    momentum: MomentumFactorResult
    low_vol: LowVolFactorResult
    smart_money: SmartMoneyFactorResult
    catalyst: CatalystFactorResult


@dataclass(frozen=True)
class EnhancedScore:
    """
    Complete enhanced score with full transparency.

    Per PLAN-scoring.md Module 4.1.
    """
    ticker: str
    score: float                    # 0-100 composite score
    conviction: int                 # 1-10 scale (derived from score)
    timeframe: Timeframe
    sector: str
    regime: MarketRegime

    # Factor breakdown
    factor_scores: dict[str, float]  # Individual factor scores (0-100)
    weights_used: FactorWeights
    weighted_contributions: dict[str, float]  # Factor * weight

    # Position sizing
    position_size: float            # 0.01-0.08 (1%-8%)
    position_detail: str

    # Data quality
    data_completeness: float        # 0-1
    factors_available: list[str]
    factors_missing: list[str]

    # Risk status
    passes_filters: bool
    filter_reason: str | None

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def score_normalized(self) -> float:
        """Score on 0-1 scale for backward compatibility."""
        return self.score / 100.0


@dataclass
class StockData:
    """
    Input data for scoring a single stock.

    Aggregates all data needed for factor computation.
    """
    ticker: str
    sector: str

    # Price data
    price: float
    prices: list[float] | None = None           # 252 days, most recent first
    volumes: list[float] | None = None
    price_change_1m: float | None = None
    price_change_12m: float | None = None

    # Fundamentals
    market_cap: float | None = None
    eps: float | None = None
    book_value: float | None = None
    fcf: float | None = None
    price_to_book: float | None = None

    # Quality metrics
    gross_profit_margin: float | None = None
    revenue: float | None = None
    cogs: float | None = None
    total_assets: float | None = None
    roe: float | None = None
    debt_equity: float | None = None
    margin_history: list[float] | None = None

    # Risk metrics
    avg_volume: float | None = None
    days_to_cover: float | None = None
    current_ratio: float | None = None
    volatility: float | None = None
    beta: float | None = None

    # Smart money
    current_13f_holdings: list[dict] | None = None
    previous_13f_holdings: list[dict] | None = None
    insider_trades: list[dict] | None = None
    congress_trades: list[dict] | None = None

    # Catalyst
    next_earnings_date: date | str | None = None

    # Momentum - earnings revisions
    current_estimate: float | None = None
    estimate_30d_ago: float | None = None
    estimate_90d_ago: float | None = None


def _compute_all_factors(
    data: StockData,
    regime: MarketRegime,
    sector_performance: dict[str, float] | None = None,
    market_prices: list[float] | None = None,
    today: date | None = None,
) -> FactorScores:
    """Compute all six factor scores for a stock."""

    # 1. Quality Factor
    quality = compute_quality_score(
        gross_profit_margin=data.gross_profit_margin,
        revenue=data.revenue,
        cogs=data.cogs,
        total_assets=data.total_assets,
        roe=data.roe,
        debt_equity=data.debt_equity,
        margin_history=data.margin_history,
    )

    # 2. Value Factor
    value = compute_value_score(
        eps=data.eps,
        price=data.price,
        book_value=data.book_value,
        market_cap=data.market_cap,
        fcf=data.fcf,
        price_to_book=data.price_to_book,
    )

    # 3. Momentum Factor
    momentum = compute_momentum_score(
        prices=data.prices,
        volumes=data.volumes,
        price_change_12m=data.price_change_12m,
        price_change_1m=data.price_change_1m,
        current_estimate=data.current_estimate,
        estimate_30d_ago=data.estimate_30d_ago,
        estimate_90d_ago=data.estimate_90d_ago,
    )

    # 4. Low Volatility Factor
    low_vol = compute_low_vol_score(
        stock_prices=data.prices,
        market_prices=market_prices,
        pre_computed_volatility=data.volatility,
        pre_computed_beta=data.beta,
    )

    # 5. Smart Money Factor
    smart_money = compute_smart_money_score(
        current_13f_holdings=data.current_13f_holdings,
        previous_13f_holdings=data.previous_13f_holdings,
        insider_trades=data.insider_trades,
        congress_trades=data.congress_trades,
        today=today,
    )

    # 6. Catalyst Factor
    catalyst = compute_catalyst_score(
        sector=data.sector,
        regime=regime,
        next_earnings_date=data.next_earnings_date,
        sector_performance=sector_performance,
        today=today,
    )

    return FactorScores(
        quality=quality,
        value=value,
        momentum=momentum,
        low_vol=low_vol,
        smart_money=smart_money,
        catalyst=catalyst,
    )


def _classify_timeframe(
    factor_scores: FactorScores,
    has_near_term_catalyst: bool,
) -> Timeframe:
    """
    Classify investment timeframe based on factor profile.

    SHORT: High momentum, near-term catalyst, or smart money signals
    LONG: High quality + value, lower momentum
    MEDIUM: Everything else
    """
    momentum_score = factor_scores.momentum.score
    quality_score = factor_scores.quality.score
    value_score = factor_scores.value.score
    smart_money_score = factor_scores.smart_money.score

    # SHORT triggers
    if has_near_term_catalyst and momentum_score >= 60:
        return Timeframe.SHORT
    if momentum_score >= 75 and smart_money_score >= 65:
        return Timeframe.SHORT
    if momentum_score >= 80:
        return Timeframe.SHORT

    # LONG triggers
    if quality_score >= 70 and value_score >= 60 and momentum_score < 60:
        return Timeframe.LONG
    if quality_score >= 75 and value_score >= 55:
        return Timeframe.LONG

    # Default to MEDIUM
    return Timeframe.MEDIUM


def _differentiate_score(raw_score: float) -> float:
    """
    Apply score differentiation to spread the distribution.

    Uses power transformation to amplify differences from 50.
    Scores near 50 stay near 50, scores far from 50 move further.
    """
    import math

    # Center around 50
    centered = raw_score - 50

    # Power transformation with 1.8 amplification
    amplification = 1.8
    if centered >= 0:
        differentiated = 50 + (centered ** (1 / amplification))
    else:
        differentiated = 50 - (abs(centered) ** (1 / amplification))

    return max(0, min(100, differentiated))


def score_stock(
    data: StockData,
    regime_context: RegimeContext | None = None,
    sector_performance: dict[str, float] | None = None,
    market_prices: list[float] | None = None,
    risk_filters: RiskFilters | None = None,
    portfolio_constraints: PortfolioConstraints | None = None,
    historical_win_rate: float = 0.55,
    today: date | None = None,
) -> EnhancedScore:
    """
    Main scoring function - compute enhanced score for a single stock.

    This is the primary entry point for the enhanced scoring algorithm.

    Args:
        data: All data for the stock
        regime_context: Pre-computed regime (or will detect from market_prices)
        sector_performance: Sector returns for rotation signal
        market_prices: SPY prices for beta calculation and regime
        risk_filters: Risk filter configuration
        portfolio_constraints: Position sizing constraints
        historical_win_rate: Win rate for Kelly sizing
        today: Reference date

    Returns:
        EnhancedScore with full breakdown
    """
    today = today or date.today()
    risk_filters = risk_filters or RiskFilters()
    portfolio_constraints = portfolio_constraints or PortfolioConstraints()

    # Determine regime
    if regime_context is None:
        regime_context = detect_market_regime(spy_prices=market_prices)
    regime = regime_context.regime

    # Compute all factor scores
    factors = _compute_all_factors(
        data=data,
        regime=regime,
        sector_performance=sector_performance,
        market_prices=market_prices,
        today=today,
    )

    # Classify timeframe
    timeframe = _classify_timeframe(
        factors,
        has_near_term_catalyst=factors.catalyst.has_near_term_catalyst,
    )

    # Get regime and timeframe adjusted weights
    weights = get_regime_weights(regime, timeframe.value)

    # Compute weighted composite score
    factor_scores_dict = {
        "quality": factors.quality.score,
        "value": factors.value.score,
        "momentum": factors.momentum.score,
        "low_vol": factors.low_vol.score,
        "smart_money": factors.smart_money.score,
        "catalyst": factors.catalyst.score,
    }

    weighted_contributions = {
        "quality": factors.quality.score * weights.quality,
        "value": factors.value.score * weights.value,
        "momentum": factors.momentum.score * weights.momentum,
        "low_vol": factors.low_vol.score * weights.low_vol,
        "smart_money": factors.smart_money.score * weights.smart_money,
        "catalyst": factors.catalyst.score * weights.catalyst,
    }

    raw_score = sum(weighted_contributions.values())

    # Apply score differentiation
    final_score = _differentiate_score(raw_score)

    # Convert to 1-10 conviction
    conviction = max(1, min(10, round(final_score / 10)))

    # Apply risk filters
    passes_filters, filter_reason, filter_detail = apply_risk_filters(
        ticker=data.ticker,
        market_cap=data.market_cap,
        price=data.price,
        avg_volume=data.avg_volume,
        days_to_cover=data.days_to_cover,
        debt_equity=data.debt_equity,
        current_ratio=data.current_ratio,
        conviction=conviction,
        filters=risk_filters,
    )

    # Compute position size
    if passes_filters:
        position_result = compute_position_size(
            ticker=data.ticker,
            conviction=conviction,
            score=final_score,
            historical_win_rate=historical_win_rate,
            constraints=portfolio_constraints,
        )
        position_size = position_result.final_size
        position_detail = position_result.detail
    else:
        position_size = 0.0
        position_detail = f"Filtered: {filter_detail}"

    # Compute data completeness
    completeness_scores = [
        factors.quality.data_completeness,
        factors.value.data_completeness,
        factors.momentum.data_completeness,
        factors.low_vol.data_completeness,
        factors.smart_money.data_completeness,
        factors.catalyst.data_completeness,
    ]
    overall_completeness = sum(completeness_scores) / len(completeness_scores)

    # Track available/missing factors
    factors_available = []
    factors_missing = []
    for name, completeness in [
        ("quality", factors.quality.data_completeness),
        ("value", factors.value.data_completeness),
        ("momentum", factors.momentum.data_completeness),
        ("low_vol", factors.low_vol.data_completeness),
        ("smart_money", factors.smart_money.data_completeness),
        ("catalyst", factors.catalyst.data_completeness),
    ]:
        if completeness >= 0.5:
            factors_available.append(name)
        else:
            factors_missing.append(name)

    return EnhancedScore(
        ticker=data.ticker,
        score=round(final_score, 2),
        conviction=conviction,
        timeframe=timeframe,
        sector=data.sector,
        regime=regime,
        factor_scores=factor_scores_dict,
        weights_used=weights,
        weighted_contributions=weighted_contributions,
        position_size=position_size,
        position_detail=position_detail,
        data_completeness=round(overall_completeness, 2),
        factors_available=factors_available,
        factors_missing=factors_missing,
        passes_filters=passes_filters,
        filter_reason=filter_detail,
    )


def score_stocks(
    stocks: list[StockData],
    regime_context: RegimeContext | None = None,
    sector_performance: dict[str, float] | None = None,
    market_prices: list[float] | None = None,
    risk_filters: RiskFilters | None = None,
    portfolio_constraints: PortfolioConstraints | None = None,
    historical_win_rate: float = 0.55,
    today: date | None = None,
) -> list[EnhancedScore]:
    """
    Score multiple stocks with shared context.

    Args:
        stocks: List of StockData for each stock
        (other args same as score_stock)

    Returns:
        List of EnhancedScore sorted by score descending
    """
    today = today or date.today()

    # Detect regime once for all stocks
    if regime_context is None:
        regime_context = detect_market_regime(spy_prices=market_prices)

    scores = []
    for data in stocks:
        score = score_stock(
            data=data,
            regime_context=regime_context,
            sector_performance=sector_performance,
            market_prices=market_prices,
            risk_filters=risk_filters,
            portfolio_constraints=portfolio_constraints,
            historical_win_rate=historical_win_rate,
            today=today,
        )
        scores.append(score)

    # Sort by score descending
    scores.sort(key=lambda s: (s.score, s.conviction), reverse=True)

    return scores


def select_picks(
    scores: list[EnhancedScore],
    picks_per_timeframe: tuple[int, int] = (3, 7),
    max_sector_per_timeframe: int = 2,
) -> dict[Timeframe, list[EnhancedScore]]:
    """
    Select final picks from scored stocks.

    Applies:
    1. Filter to only passing stocks
    2. Sector concentration limit per timeframe
    3. Pick count limits per timeframe

    Args:
        scores: List of EnhancedScore (should be sorted by score)
        picks_per_timeframe: (min, max) picks per timeframe
        max_sector_per_timeframe: Max stocks from same sector in timeframe

    Returns:
        Dict mapping Timeframe to selected picks
    """
    min_picks, max_picks = picks_per_timeframe

    # Group by timeframe
    by_timeframe: dict[Timeframe, list[EnhancedScore]] = {
        Timeframe.SHORT: [],
        Timeframe.MEDIUM: [],
        Timeframe.LONG: [],
    }

    for score in scores:
        if score.passes_filters:
            by_timeframe[score.timeframe].append(score)

    # Apply sector limits and pick counts
    result: dict[Timeframe, list[EnhancedScore]] = {}

    for timeframe, tf_scores in by_timeframe.items():
        selected = []
        sector_counts: dict[str, int] = {}

        for score in tf_scores:
            if len(selected) >= max_picks:
                break

            sector = score.sector.lower()
            sector_count = sector_counts.get(sector, 0)

            if sector_count < max_sector_per_timeframe:
                selected.append(score)
                sector_counts[sector] = sector_count + 1

        result[timeframe] = selected

    return result
