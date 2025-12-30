"""
Stock analysis engine - pure functions, no I/O.

All functions take typed domain objects and return typed domain objects.
No external dependencies, fully unit-testable.

Scoring logic is configurable via ScoringConfig parameter.
"""

from .models import StockPick, MacroIndicator, Timeframe, Trend, Impact
from .analysis_types import (
    StockMetrics,
    MacroContext,
    ConvictionScore,
    Risk,
    RiskCategory,
    ScoringConfig,
    Strategy,
    StrategyType,
)


# ============================================================================
# Scoring Functions
# ============================================================================

def score_stock(
    metrics: StockMetrics,
    macro_context: MacroContext | None = None,
    config: ScoringConfig | None = None,
) -> ConvictionScore:
    """
    Calculate conviction score for a stock.

    Pure function - takes metrics and context, returns score breakdown.

    Args:
        metrics: Stock metrics from data adapters
        macro_context: Current macro environment (optional)
        config: Scoring thresholds and weights (uses defaults if None)

    Returns:
        ConvictionScore with overall score and component breakdown
    """
    config = config or ScoringConfig()
    factors_used = []
    factors_missing = []

    # Calculate component scores
    val_score = _score_valuation(metrics, config, factors_used, factors_missing)
    growth_score = _score_growth(metrics, config, factors_used, factors_missing)
    quality_score = _score_quality(metrics, config, factors_used, factors_missing)
    momentum_score = _score_momentum(metrics, config, factors_used, factors_missing)

    # Calculate macro adjustment
    macro_adj = 0.0
    if macro_context:
        macro_adj = _calculate_macro_adjustment(macro_context, config)
        factors_used.append("macro_context")

    # Weighted average
    weights_sum = (
        config.weight_valuation +
        config.weight_growth +
        config.weight_quality +
        config.weight_momentum
    )

    overall = (
        val_score * config.weight_valuation +
        growth_score * config.weight_growth +
        quality_score * config.weight_quality +
        momentum_score * config.weight_momentum
    ) / weights_sum

    # Apply macro adjustment (clamped to 0-1)
    overall = max(0.0, min(1.0, overall + macro_adj))

    # Calculate confidence based on data completeness
    total_factors = len(factors_used) + len(factors_missing)
    confidence = len(factors_used) / total_factors if total_factors > 0 else 0.5

    return ConvictionScore(
        overall=round(overall, 4),
        valuation_score=round(val_score, 4),
        growth_score=round(growth_score, 4),
        quality_score=round(quality_score, 4),
        momentum_score=round(momentum_score, 4),
        macro_adjustment=round(macro_adj, 4),
        factors_used=factors_used,
        factors_missing=factors_missing,
        confidence=round(confidence, 4),
    )


def _score_valuation(
    metrics: StockMetrics,
    config: ScoringConfig,
    used: list[str],
    missing: list[str],
) -> float:
    """Score valuation metrics (0-1, higher = more attractive)."""
    scores = []

    # PE ratio scoring
    if metrics.pe_trailing is not None and metrics.pe_trailing > 0:
        used.append("pe_trailing")
        if metrics.pe_trailing < config.pe_low:
            scores.append(1.0)
        elif metrics.pe_trailing > config.pe_high:
            scores.append(0.0)
        else:
            # Linear interpolation
            scores.append(1.0 - (metrics.pe_trailing - config.pe_low) / (config.pe_high - config.pe_low))
    else:
        missing.append("pe_trailing")

    # PEG ratio scoring
    if metrics.peg_ratio is not None and metrics.peg_ratio > 0:
        used.append("peg_ratio")
        if metrics.peg_ratio < config.peg_fair:
            scores.append(1.0)
        elif metrics.peg_ratio > config.peg_fair * 2:
            scores.append(0.0)
        else:
            scores.append(1.0 - (metrics.peg_ratio - config.peg_fair) / config.peg_fair)
    else:
        missing.append("peg_ratio")

    # Price to book scoring
    if metrics.price_to_book is not None and metrics.price_to_book > 0:
        used.append("price_to_book")
        if metrics.price_to_book < config.pb_low:
            scores.append(1.0)
        elif metrics.price_to_book > config.pb_high:
            scores.append(0.0)
        else:
            scores.append(1.0 - (metrics.price_to_book - config.pb_low) / (config.pb_high - config.pb_low))
    else:
        missing.append("price_to_book")

    # Analyst target upside
    if metrics.upside_potential is not None:
        used.append("upside_potential")
        upside = metrics.upside_potential
        if upside > config.upside_significant:
            scores.append(1.0)
        elif upside < 0:
            scores.append(0.0)
        else:
            scores.append(upside / config.upside_significant)
    else:
        missing.append("upside_potential")

    return sum(scores) / len(scores) if scores else 0.5


def _score_growth(
    metrics: StockMetrics,
    config: ScoringConfig,
    used: list[str],
    missing: list[str],
) -> float:
    """Score growth metrics (0-1, higher = faster growth)."""
    scores = []

    # Revenue growth
    if metrics.revenue_growth is not None:
        used.append("revenue_growth")
        rg = metrics.revenue_growth
        if rg >= config.revenue_growth_high:
            scores.append(1.0)
        elif rg <= config.revenue_growth_low:
            scores.append(0.2)
        else:
            scores.append(0.2 + 0.8 * (rg - config.revenue_growth_low) / (config.revenue_growth_high - config.revenue_growth_low))
    else:
        missing.append("revenue_growth")

    # Earnings growth
    if metrics.earnings_growth is not None:
        used.append("earnings_growth")
        eg = metrics.earnings_growth
        if eg >= config.earnings_growth_high:
            scores.append(1.0)
        elif eg <= 0:
            scores.append(0.0)
        else:
            scores.append(eg / config.earnings_growth_high)
    else:
        missing.append("earnings_growth")

    return sum(scores) / len(scores) if scores else 0.5


def _score_quality(
    metrics: StockMetrics,
    config: ScoringConfig,
    used: list[str],
    missing: list[str],
) -> float:
    """Score quality metrics (0-1, higher = better quality)."""
    scores = []

    # Profit margin
    if metrics.profit_margin is not None:
        used.append("profit_margin")
        pm = metrics.profit_margin
        if pm >= config.profit_margin_good:
            scores.append(1.0)
        elif pm <= 0:
            scores.append(0.0)
        else:
            scores.append(pm / config.profit_margin_good)
    else:
        missing.append("profit_margin")

    # ROE
    if metrics.roe is not None:
        used.append("roe")
        if metrics.roe >= config.roe_good:
            scores.append(1.0)
        elif metrics.roe <= 0:
            scores.append(0.0)
        else:
            scores.append(metrics.roe / config.roe_good)
    else:
        missing.append("roe")

    # Analyst rating (1=strong buy, 5=strong sell)
    if metrics.analyst_rating is not None:
        used.append("analyst_rating")
        ar = metrics.analyst_rating
        if ar <= config.analyst_bullish:
            scores.append(1.0)
        elif ar >= config.analyst_bearish:
            scores.append(0.0)
        else:
            scores.append(1.0 - (ar - config.analyst_bullish) / (config.analyst_bearish - config.analyst_bullish))
    else:
        missing.append("analyst_rating")

    return sum(scores) / len(scores) if scores else 0.5


def _score_momentum(
    metrics: StockMetrics,
    config: ScoringConfig,
    used: list[str],
    missing: list[str],
) -> float:
    """Score momentum metrics (0-1, higher = stronger momentum)."""
    scores = []

    # 1-month price change
    if metrics.price_change_1m is not None:
        used.append("price_change_1m")
        pc = metrics.price_change_1m
        if pc >= config.momentum_strong:
            scores.append(1.0)
        elif pc <= -config.momentum_strong:
            scores.append(0.0)
        else:
            scores.append(0.5 + (pc / config.momentum_strong) * 0.5)
    else:
        missing.append("price_change_1m")

    # 3-month price change
    if metrics.price_change_3m is not None:
        used.append("price_change_3m")
        pc = metrics.price_change_3m
        threshold = config.momentum_strong * 3  # Scale for 3 months
        if pc >= threshold:
            scores.append(1.0)
        elif pc <= -threshold:
            scores.append(0.0)
        else:
            scores.append(0.5 + (pc / threshold) * 0.5)
    else:
        missing.append("price_change_3m")

    # Volume ratio
    if metrics.volume_ratio is not None:
        used.append("volume_ratio")
        vr = metrics.volume_ratio
        if vr >= config.volume_spike:
            scores.append(0.8)  # High volume can be good or bad
        elif vr >= 1.0:
            scores.append(0.6)
        else:
            scores.append(0.4)
    else:
        missing.append("volume_ratio")

    return sum(scores) / len(scores) if scores else 0.5


def _calculate_macro_adjustment(
    macro: MacroContext,
    config: ScoringConfig,
) -> float:
    """
    Calculate macro adjustment to conviction score.

    Returns value between -0.2 and +0.2 based on macro conditions.
    """
    adjustments = []

    # Yield curve inversion (recession signal)
    if macro.is_yield_curve_inverted:
        adjustments.append(-0.15)

    # High unemployment
    if macro.unemployment_rate is not None:
        if macro.unemployment_rate > config.unemployment_high:
            adjustments.append(-0.1)
        elif macro.unemployment_rate < config.unemployment_high * 0.7:
            adjustments.append(0.05)

    # Inflation
    if macro.inflation_rate is not None:
        if macro.inflation_rate > config.inflation_high:
            adjustments.append(-0.1)  # Fed will be hawkish
        elif macro.inflation_rate < 2.0:
            adjustments.append(0.05)  # Goldilocks

    # VIX (fear gauge)
    if macro.vix is not None:
        if macro.vix > config.vix_high:
            adjustments.append(-0.1)  # High fear
        elif macro.vix < 15:
            adjustments.append(0.05)  # Low fear

    # Rate trend
    if macro.rate_trend == Trend.RISING:
        adjustments.append(-0.05)  # Rising rates hurt stocks
    elif macro.rate_trend == Trend.FALLING:
        adjustments.append(0.1)  # Falling rates help stocks

    # Sum and clamp
    total = sum(adjustments)
    return max(-0.2, min(0.2, total))


# ============================================================================
# Classification Functions
# ============================================================================

def classify_timeframe(
    metrics: StockMetrics,
    config: ScoringConfig | None = None,
) -> Timeframe:
    """
    Classify appropriate investment timeframe for a stock.

    Pure function - analyzes metrics to determine timeframe.

    Args:
        metrics: Stock metrics
        config: Scoring configuration

    Returns:
        Recommended Timeframe (SHORT, MEDIUM, LONG)
    """
    config = config or ScoringConfig()
    signals = {"short": 0, "medium": 0, "long": 0}

    # High growth stocks are better for short-medium term
    if metrics.revenue_growth is not None:
        if metrics.revenue_growth > config.revenue_growth_high:
            signals["short"] += 1
            signals["medium"] += 1

    # Value stocks (low PE) are better for long term
    if metrics.pe_trailing is not None:
        if metrics.pe_trailing < config.pe_low:
            signals["long"] += 2
        elif metrics.pe_trailing > config.pe_high:
            signals["short"] += 1  # Momentum play

    # Strong momentum suggests short-term opportunity
    if metrics.price_change_1m is not None:
        if abs(metrics.price_change_1m) > config.momentum_strong:
            signals["short"] += 2

    # Quality metrics suggest long-term hold
    if metrics.profit_margin is not None and metrics.profit_margin > config.profit_margin_good:
        signals["long"] += 1
        signals["medium"] += 1

    # Dividend yield suggests long-term
    if metrics.dividend_yield is not None and metrics.dividend_yield > 0.02:
        signals["long"] += 2

    # Analyst price target proximity
    if metrics.upside_potential is not None:
        if metrics.upside_potential > 30:
            signals["medium"] += 1
        elif metrics.upside_potential > 10:
            signals["short"] += 1

    # Determine winner
    if signals["long"] >= signals["medium"] and signals["long"] >= signals["short"]:
        return Timeframe.LONG
    elif signals["short"] > signals["medium"]:
        return Timeframe.SHORT
    else:
        return Timeframe.MEDIUM


# ============================================================================
# Risk Identification
# ============================================================================

def identify_headwinds(
    indicators: list[MacroIndicator],
    config: ScoringConfig | None = None,
) -> list[Risk]:
    """
    Identify macro headwinds from indicators.

    Pure function - analyzes macro data to find risks.

    Args:
        indicators: List of macro indicators
        config: Scoring configuration

    Returns:
        List of identified Risk objects
    """
    config = config or ScoringConfig()
    risks = []

    # Build lookup for easier access
    by_name = {ind.name.lower(): ind for ind in indicators}
    by_id = {ind.series_id: ind for ind in indicators if ind.series_id}

    # Check unemployment
    unemp = by_id.get("UNRATE") or by_name.get("unemployment rate")
    if unemp and unemp.current_value > config.unemployment_high:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="High Unemployment",
            description=f"Unemployment at {unemp.current_value}% signals weak labor market",
            severity=min(1.0, (unemp.current_value - config.unemployment_high) / 3 + 0.5),
            probability=0.8,
            source_indicator="UNRATE",
        ))

    # Check inflation
    cpi = by_id.get("CPIAUCSL") or by_name.get("cpi (inflation)")
    if cpi and cpi.trend == Trend.RISING:
        severity = 0.6 if cpi.current_value > config.inflation_high else 0.4
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Rising Inflation",
            description="Rising inflation may force Fed to maintain restrictive policy",
            severity=severity,
            probability=0.7,
            source_indicator="CPIAUCSL",
        ))

    # Check Fed Funds rate trend
    fed = by_id.get("FEDFUNDS") or by_name.get("federal funds rate")
    if fed and fed.trend == Trend.RISING:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Rising Interest Rates",
            description="Higher rates increase borrowing costs and reduce equity valuations",
            severity=0.6,
            probability=0.75,
            source_indicator="FEDFUNDS",
        ))

    # Check yield curve (10Y-2Y spread)
    spread = by_id.get("T10Y2Y") or by_name.get("10y-2y treasury spread")
    if spread and spread.current_value < 0:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Inverted Yield Curve",
            description="Yield curve inversion historically precedes recessions",
            severity=0.8,
            probability=0.6,
            source_indicator="T10Y2Y",
        ))

    # Check consumer sentiment
    sentiment = by_id.get("UMCSENT") or by_name.get("consumer sentiment")
    if sentiment and sentiment.current_value < 70:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Weak Consumer Sentiment",
            description="Low consumer confidence may reduce spending",
            severity=0.5,
            probability=0.65,
            source_indicator="UMCSENT",
        ))

    # Check GDP growth trend
    gdp = by_id.get("GDP") or by_name.get("gross domestic product")
    if gdp and gdp.trend == Trend.FALLING:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Slowing GDP Growth",
            description="Declining GDP growth indicates economic slowdown",
            severity=0.7,
            probability=0.7,
            source_indicator="GDP",
        ))

    return sorted(risks, key=lambda r: r.risk_score, reverse=True)


def identify_stock_risks(
    metrics: StockMetrics,
    config: ScoringConfig | None = None,
) -> list[Risk]:
    """
    Identify stock-specific risks from metrics.

    Pure function - analyzes stock data to find risks.

    Args:
        metrics: Stock metrics
        config: Scoring configuration

    Returns:
        List of identified Risk objects
    """
    config = config or ScoringConfig()
    risks = []

    # Valuation risk
    if metrics.pe_trailing is not None and metrics.pe_trailing > config.pe_high * 1.5:
        risks.append(Risk(
            category=RiskCategory.VALUATION,
            name="Extreme Valuation",
            description=f"PE of {metrics.pe_trailing:.1f} significantly above market average",
            severity=0.7,
            probability=0.6,
            source_indicator="pe_trailing",
        ))

    # Negative growth
    if metrics.revenue_growth is not None and metrics.revenue_growth < 0:
        risks.append(Risk(
            category=RiskCategory.COMPANY,
            name="Revenue Decline",
            description=f"Revenue declining {abs(metrics.revenue_growth)*100:.1f}% YoY",
            severity=0.8,
            probability=0.8,
            source_indicator="revenue_growth",
        ))

    # Negative margins
    if metrics.profit_margin is not None and metrics.profit_margin < 0:
        risks.append(Risk(
            category=RiskCategory.COMPANY,
            name="Negative Profitability",
            description="Company is not profitable",
            severity=0.6,
            probability=0.9,
            source_indicator="profit_margin",
        ))

    # Analyst bearish
    if metrics.analyst_rating is not None and metrics.analyst_rating > config.analyst_bearish:
        risks.append(Risk(
            category=RiskCategory.COMPANY,
            name="Bearish Analyst Consensus",
            description="Analysts have negative outlook on the stock",
            severity=0.5,
            probability=0.6,
            source_indicator="analyst_rating",
        ))

    # High momentum (could reverse)
    if metrics.price_change_3m is not None and metrics.price_change_3m > 0.5:
        risks.append(Risk(
            category=RiskCategory.TECHNICAL,
            name="Extended Momentum",
            description=f"Stock up {metrics.price_change_3m*100:.0f}% in 3 months, may be overextended",
            severity=0.4,
            probability=0.5,
            source_indicator="price_change_3m",
        ))

    return sorted(risks, key=lambda r: r.risk_score, reverse=True)


# ============================================================================
# Ranking Functions
# ============================================================================

def rank_picks(
    candidates: list[StockPick],
    strategy: Strategy | None = None,
    scores: dict[str, ConvictionScore] | None = None,
) -> list[StockPick]:
    """
    Rank stock picks according to strategy preferences.

    Pure function - sorts candidates by strategy-weighted score.

    Args:
        candidates: List of stock picks to rank
        strategy: Strategy configuration (uses balanced if None)
        scores: Pre-computed conviction scores by ticker (optional)

    Returns:
        Sorted list of StockPick, best first
    """
    strategy = strategy or Strategy()

    def compute_rank_score(pick: StockPick) -> float:
        base_score = pick.conviction_score

        # Apply strategy weights if we have detailed scores
        if scores and pick.ticker in scores:
            s = scores[pick.ticker]
            weighted = (
                s.valuation_score * strategy.valuation_weight +
                s.growth_score * strategy.growth_weight +
                s.quality_score * strategy.quality_weight +
                s.momentum_score * strategy.momentum_weight
            )
            weight_sum = (
                strategy.valuation_weight +
                strategy.growth_weight +
                strategy.quality_weight +
                strategy.momentum_weight
            )
            base_score = weighted / weight_sum if weight_sum > 0 else base_score

        # Timeframe bonus (prefer picks matching strategy horizon)
        timeframe_bonus = 0.0
        if strategy.type == StrategyType.VALUE and pick.timeframe == Timeframe.LONG:
            timeframe_bonus = 0.1
        elif strategy.type == StrategyType.MOMENTUM and pick.timeframe == Timeframe.SHORT:
            timeframe_bonus = 0.1
        elif strategy.type == StrategyType.GROWTH and pick.timeframe == Timeframe.MEDIUM:
            timeframe_bonus = 0.05

        # Risk penalty
        risk_penalty = len(pick.risk_factors) * 0.02

        return base_score + timeframe_bonus - risk_penalty

    # Filter by strategy constraints
    filtered = []
    for pick in candidates:
        # Could add more filtering here based on strategy.min_market_cap, etc.
        # For now, include all
        filtered.append(pick)

    # Sort by computed score (descending)
    return sorted(filtered, key=compute_rank_score, reverse=True)


def filter_by_strategy(
    candidates: list[StockPick],
    strategy: Strategy,
    metrics_map: dict[str, StockMetrics],
) -> list[StockPick]:
    """
    Filter picks based on strategy constraints.

    Pure function - removes picks that don't meet strategy criteria.

    Args:
        candidates: List of stock picks
        strategy: Strategy with filter criteria
        metrics_map: Metrics by ticker for filtering

    Returns:
        Filtered list of picks meeting strategy criteria
    """
    result = []

    for pick in candidates:
        metrics = metrics_map.get(pick.ticker)
        if not metrics:
            continue

        # Market cap filter
        if strategy.min_market_cap is not None:
            if metrics.market_cap is None or metrics.market_cap < strategy.min_market_cap:
                continue

        # Max PE filter
        if strategy.max_pe is not None:
            if metrics.pe_trailing is not None and metrics.pe_trailing > strategy.max_pe:
                continue

        # Min dividend yield filter
        if strategy.min_dividend_yield is not None:
            if metrics.dividend_yield is None or metrics.dividend_yield < strategy.min_dividend_yield:
                continue

        result.append(pick)

    return result


# ============================================================================
# Utility Functions
# ============================================================================

def generate_thesis(
    metrics: StockMetrics,
    score: ConvictionScore,
    risks: list[Risk],
) -> str:
    """
    Generate an investment thesis from metrics and analysis.

    Pure function - creates human-readable thesis text.

    Args:
        metrics: Stock metrics
        score: Conviction score breakdown
        risks: Identified risks

    Returns:
        Thesis string
    """
    parts = []

    # Lead with overall assessment
    if score.overall > 0.7:
        parts.append(f"{metrics.ticker} presents a compelling opportunity")
    elif score.overall > 0.5:
        parts.append(f"{metrics.ticker} shows moderate potential")
    else:
        parts.append(f"{metrics.ticker} faces headwinds")

    # Valuation commentary
    if score.valuation_score > 0.7:
        parts.append("with attractive valuation")
    elif score.valuation_score < 0.3:
        parts.append("despite rich valuation")

    # Growth commentary
    if score.growth_score > 0.7:
        parts.append("and strong growth trajectory")
    elif score.growth_score < 0.3:
        parts.append("but limited growth")

    # Quality commentary
    if score.quality_score > 0.7:
        parts.append("backed by solid fundamentals")

    # Risk summary
    if risks:
        top_risk = risks[0]
        parts.append(f". Key risk: {top_risk.name.lower()}")

    thesis = " ".join(parts)
    if not thesis.endswith("."):
        thesis += "."

    return thesis
