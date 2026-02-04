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
            signals["medium"] += 2
        elif metrics.revenue_growth > config.revenue_growth_low:
            signals["medium"] += 1

    # Earnings growth favors medium-term
    if metrics.earnings_growth is not None:
        if metrics.earnings_growth > config.earnings_growth_high:
            signals["medium"] += 2
        elif metrics.earnings_growth > 0:
            signals["medium"] += 1

    # Value stocks (low PE) are better for long term
    if metrics.pe_trailing is not None:
        if metrics.pe_trailing < config.pe_low:
            signals["long"] += 2
        elif metrics.pe_trailing > config.pe_high:
            signals["short"] += 2  # High valuation momentum play

    # Strong momentum suggests short-term opportunity
    if metrics.price_change_1m is not None:
        if abs(metrics.price_change_1m) > config.momentum_strong:
            signals["short"] += 3
        elif abs(metrics.price_change_1m) > config.momentum_strong / 2:
            signals["short"] += 1

    # 3-month momentum for short-medium
    if metrics.price_change_3m is not None:
        if abs(metrics.price_change_3m) > config.momentum_strong * 2:
            signals["short"] += 2
        elif abs(metrics.price_change_3m) > config.momentum_strong:
            signals["medium"] += 1

    # Volume spike indicates short-term catalyst
    if metrics.volume_ratio is not None and metrics.volume_ratio > config.volume_spike:
        signals["short"] += 2

    # Quality metrics suggest long-term hold
    if metrics.profit_margin is not None and metrics.profit_margin > config.profit_margin_good:
        signals["long"] += 1
        signals["medium"] += 1

    # ROE favors quality long-term holds
    if metrics.roe is not None and metrics.roe > config.roe_good:
        signals["long"] += 1

    # Dividend yield suggests long-term
    if metrics.dividend_yield is not None and metrics.dividend_yield > 0.02:
        signals["long"] += 2

    # Analyst price target proximity
    if metrics.upside_potential is not None:
        if metrics.upside_potential > 30:
            signals["medium"] += 2
        elif metrics.upside_potential > 15:
            signals["short"] += 2

    # Determine winner with strict comparisons
    if signals["long"] > signals["medium"] and signals["long"] > signals["short"]:
        return Timeframe.LONG
    elif signals["short"] > signals["medium"] and signals["short"] > signals["long"]:
        return Timeframe.SHORT
    elif signals["medium"] > signals["short"] and signals["medium"] > signals["long"]:
        return Timeframe.MEDIUM

    # Tiebreaker: use characteristic metrics to break ties
    # Momentum favors short, growth favors medium, stability favors long
    if signals["short"] == signals["medium"] == signals["long"]:
        # Three-way tie: check momentum first
        if metrics.price_change_1m is not None and abs(metrics.price_change_1m) > 0.05:
            return Timeframe.SHORT
        elif metrics.revenue_growth is not None and metrics.revenue_growth > 0.10:
            return Timeframe.MEDIUM
        else:
            return Timeframe.LONG
    elif signals["short"] == signals["long"]:
        # Short vs Long tie: momentum wins for short
        if metrics.price_change_1m is not None and abs(metrics.price_change_1m) > 0.03:
            return Timeframe.SHORT
        else:
            return Timeframe.LONG
    elif signals["short"] == signals["medium"]:
        # Short vs Medium tie: strong momentum wins for short
        if metrics.price_change_1m is not None and abs(metrics.price_change_1m) > 0.08:
            return Timeframe.SHORT
        else:
            return Timeframe.MEDIUM
    else:  # signals["medium"] == signals["long"]
        # Medium vs Long tie: growth wins for medium
        if metrics.revenue_growth is not None and metrics.revenue_growth > 0.15:
            return Timeframe.MEDIUM
        else:
            return Timeframe.LONG


# ============================================================================
# Risk Identification
# ============================================================================

def identify_headwinds(
    indicators: list[MacroIndicator],
    config: ScoringConfig | None = None,
) -> list[Risk]:
    """
    Identify macro headwinds from indicators across 8 risk categories.

    Pure function - analyzes macro data to find risks.

    Args:
        indicators: List of macro indicators
        config: Scoring configuration

    Returns:
        List of identified Risk objects sorted by risk score
    """
    config = config or ScoringConfig()
    risks = []

    # Build lookup for easier access
    by_name = {ind.name.lower(): ind for ind in indicators}
    by_id = {ind.series_id: ind for ind in indicators if ind.series_id}

    # Evaluate all risk categories
    risks.extend(_evaluate_recession_risk(by_id, by_name, config))
    risks.extend(_evaluate_credit_risk(by_id, by_name, config))
    risks.extend(_evaluate_housing_risk(by_id, by_name, config))
    risks.extend(_evaluate_financial_stress_risk(by_id, by_name, config))
    risks.extend(_evaluate_inflation_risk(by_id, by_name, config))
    risks.extend(_evaluate_labor_risk(by_id, by_name, config))
    risks.extend(_evaluate_valuation_risk(by_id, by_name, config))
    risks.extend(_evaluate_global_risk(by_id, by_name, config))

    return sorted(risks, key=lambda r: r.risk_score, reverse=True)


def _evaluate_recession_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate recession probability indicators."""
    risks = []

    # Yield curve 10Y-2Y (most watched)
    spread_2y = by_id.get("T10Y2Y") or by_name.get("10y-2y treasury spread")
    if spread_2y and spread_2y.current_value < 0:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Inverted Yield Curve (10Y-2Y)",
            description=f"Yield curve inverted at {spread_2y.current_value:.2f}% - historically precedes 87% of recessions",
            severity=0.8,
            probability=0.7,
            source_indicator="T10Y2Y",
        ))
    elif spread_2y and spread_2y.current_value < 0.25:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Flattening Yield Curve",
            description=f"Yield curve spread at {spread_2y.current_value:.2f}% - approaching inversion",
            severity=0.4,
            probability=0.5,
            source_indicator="T10Y2Y",
        ))

    # Yield curve 10Y-3M (higher accuracy)
    spread_3m = by_id.get("T10Y3M") or by_name.get("10y-3m treasury spread")
    if spread_3m and spread_3m.current_value < 0:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Inverted Yield Curve (10Y-3M)",
            description=f"10Y-3M spread inverted at {spread_3m.current_value:.2f}% - strongest recession signal",
            severity=0.85,
            probability=0.75,
            source_indicator="T10Y3M",
        ))

    # Sahm Rule recession indicator
    sahm = by_id.get("SAHMREALTIME") or by_name.get("sahm rule recession indicator")
    if sahm:
        if sahm.current_value >= 0.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Sahm Rule Triggered",
                description=f"Sahm indicator at {sahm.current_value:.2f}pp - recession likely in progress",
                severity=0.9,
                probability=0.85,
                source_indicator="SAHMREALTIME",
            ))
        elif sahm.current_value >= 0.3:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Sahm Rule Warning",
                description=f"Sahm indicator at {sahm.current_value:.2f}pp - approaching recession threshold (0.5)",
                severity=0.6,
                probability=0.6,
                source_indicator="SAHMREALTIME",
            ))

    # NY Fed recession probability
    rec_prob = by_id.get("RECPROUSM156N") or by_name.get("recession probability")
    if rec_prob:
        if rec_prob.current_value >= 50:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="High Recession Probability",
                description=f"NY Fed model shows {rec_prob.current_value:.0f}% recession probability",
                severity=0.85,
                probability=rec_prob.current_value / 100,
                source_indicator="RECPROUSM156N",
            ))
        elif rec_prob.current_value >= 30:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Recession Probability",
                description=f"NY Fed model shows {rec_prob.current_value:.0f}% recession probability",
                severity=0.55,
                probability=rec_prob.current_value / 100,
                source_indicator="RECPROUSM156N",
            ))

    # GDP growth trend
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

    return risks


def _evaluate_credit_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate credit and debt market risks."""
    risks = []

    # High yield credit spread (corporate distress signal)
    hy_spread = by_id.get("BAMLH0A0HYM2") or by_name.get("high yield spread")
    if hy_spread:
        if hy_spread.current_value >= 6.0:  # 600bps
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="High Yield Stress",
                description=f"HY spread at {hy_spread.current_value:.1f}% - elevated corporate default risk",
                severity=0.8,
                probability=0.7,
                source_indicator="BAMLH0A0HYM2",
            ))
        elif hy_spread.current_value >= 4.5:  # 450bps
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Credit Spreads",
                description=f"HY spread at {hy_spread.current_value:.1f}% - above normal levels",
                severity=0.5,
                probability=0.6,
                source_indicator="BAMLH0A0HYM2",
            ))

    # BBB investment grade spread (cliff risk - largest segment of IG market)
    bbb_spread = by_id.get("BAMLC0A4CBBB") or by_name.get("bbb corporate spread")
    if bbb_spread and bbb_spread.current_value >= 2.5:  # 250bps
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Investment Grade Stress",
            description=f"BBB spread at {bbb_spread.current_value:.1f}% - risk of fallen angels",
            severity=0.6,
            probability=0.55,
            source_indicator="BAMLC0A4CBBB",
        ))

    # Consumer credit delinquency
    cc_delinq = by_id.get("DRCCLACBS") or by_name.get("credit card delinquency rate")
    if cc_delinq:
        if cc_delinq.current_value >= 4.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Consumer Credit Stress",
                description=f"Credit card delinquency at {cc_delinq.current_value:.1f}% - consumer financial strain",
                severity=0.7,
                probability=0.75,
                source_indicator="DRCCLACBS",
            ))
        elif cc_delinq.current_value >= 3.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Delinquencies",
                description=f"Credit card delinquency at {cc_delinq.current_value:.1f}% - above historical average",
                severity=0.5,
                probability=0.65,
                source_indicator="DRCCLACBS",
            ))

    return risks


def _evaluate_housing_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate housing and mortgage market risks."""
    risks = []

    # 30-year mortgage rate (affordability)
    mortgage = by_id.get("MORTGAGE30US") or by_name.get("30-year mortgage rate")
    if mortgage:
        if mortgage.current_value >= 7.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Mortgage Rate Crisis",
                description=f"30-year rate at {mortgage.current_value:.2f}% - severe affordability pressure",
                severity=0.8,
                probability=0.8,
                source_indicator="MORTGAGE30US",
            ))
        elif mortgage.current_value >= 6.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Mortgage Rates",
                description=f"30-year rate at {mortgage.current_value:.2f}% - constraining housing demand",
                severity=0.5,
                probability=0.7,
                source_indicator="MORTGAGE30US",
            ))

    # Mortgage delinquency rate
    mtg_delinq = by_id.get("DRSFRMACBS") or by_name.get("mortgage delinquency rate")
    if mtg_delinq:
        if mtg_delinq.current_value >= 3.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Mortgage Delinquency Stress",
                description=f"Mortgage delinquency at {mtg_delinq.current_value:.1f}% - housing market strain",
                severity=0.75,
                probability=0.75,
                source_indicator="DRSFRMACBS",
            ))
        elif mtg_delinq.current_value >= 2.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Mortgage Delinquencies",
                description=f"Mortgage delinquency at {mtg_delinq.current_value:.1f}% - above normal",
                severity=0.5,
                probability=0.6,
                source_indicator="DRSFRMACBS",
            ))

    # Home price index (bubble/crash detection via trend)
    hpi = by_id.get("CSUSHPINSA") or by_name.get("case-shiller home price index")
    if hpi and hpi.trend == Trend.FALLING:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Declining Home Prices",
            description="Home prices falling - negative wealth effect on consumer spending",
            severity=0.65,
            probability=0.7,
            source_indicator="CSUSHPINSA",
        ))

    return risks


def _evaluate_financial_stress_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate financial system stress indicators."""
    risks = []

    # St. Louis Fed Financial Stress Index
    stlfsi = by_id.get("STLFSI4") or by_name.get("st. louis fed financial stress index")
    if stlfsi:
        if stlfsi.current_value >= 1.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Financial System Stress",
                description=f"Financial stress index at {stlfsi.current_value:.2f} - significant market disruption",
                severity=0.85,
                probability=0.8,
                source_indicator="STLFSI4",
            ))
        elif stlfsi.current_value >= 0.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Above-Normal Financial Stress",
                description=f"Financial stress index at {stlfsi.current_value:.2f} - above historical average",
                severity=0.5,
                probability=0.6,
                source_indicator="STLFSI4",
            ))

    # VIX (fear gauge)
    vix = by_id.get("VIXCLS") or by_name.get("vix volatility index")
    if vix:
        if vix.current_value >= 35:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Extreme Market Fear",
                description=f"VIX at {vix.current_value:.0f} - significant investor anxiety",
                severity=0.8,
                probability=0.75,
                source_indicator="VIXCLS",
            ))
        elif vix.current_value >= config.vix_high:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Volatility",
                description=f"VIX at {vix.current_value:.0f} - market uncertainty elevated",
                severity=0.55,
                probability=0.65,
                source_indicator="VIXCLS",
            ))

    # TED spread (interbank lending stress)
    ted = by_id.get("TEDRATE") or by_name.get("ted spread")
    if ted:
        if ted.current_value >= 1.0:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Banking Sector Stress",
                description=f"TED spread at {ted.current_value:.2f}% - interbank lending concerns",
                severity=0.8,
                probability=0.75,
                source_indicator="TEDRATE",
            ))
        elif ted.current_value >= 0.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated TED Spread",
                description=f"TED spread at {ted.current_value:.2f}% - credit market tightening",
                severity=0.5,
                probability=0.6,
                source_indicator="TEDRATE",
            ))

    return risks


def _evaluate_inflation_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate inflation and monetary policy risks."""
    risks = []

    # CPI inflation (YoY rate)
    cpi = by_id.get("CPIAUCSL") or by_name.get("cpi (inflation)")
    if cpi:
        inflation_rate = cpi.current_value
        if inflation_rate > config.inflation_high:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Inflation",
                description=f"CPI at {inflation_rate:.1f}% YoY - above Fed's 2% target, policy may stay restrictive",
                severity=0.7,
                probability=0.75,
                source_indicator="CPIAUCSL",
            ))
        elif inflation_rate > 3.0:
            if cpi.trend == Trend.RISING:
                risks.append(Risk(
                    category=RiskCategory.MACRO,
                    name="Rising Inflation",
                    description=f"Inflation at {inflation_rate:.1f}% and rising - Fed may maintain restrictive policy",
                    severity=0.6,
                    probability=0.7,
                    source_indicator="CPIAUCSL",
                ))
            else:
                risks.append(Risk(
                    category=RiskCategory.MACRO,
                    name="Above-Target Inflation",
                    description=f"Inflation at {inflation_rate:.1f}% YoY remains above Fed's 2% target",
                    severity=0.5,
                    probability=0.65,
                    source_indicator="CPIAUCSL",
                ))
        elif inflation_rate > 2.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Sticky Inflation",
                description=f"Inflation at {inflation_rate:.1f}% YoY, slightly above Fed's 2% target",
                severity=0.3,
                probability=0.5,
                source_indicator="CPIAUCSL",
            ))

    # Inflation expectations (breakeven rate)
    infl_exp = by_id.get("T5YIE") or by_name.get("5-year inflation expectations")
    if infl_exp and infl_exp.current_value >= 3.0:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Unanchored Inflation Expectations",
            description=f"5-year breakeven at {infl_exp.current_value:.1f}% - expectations above target",
            severity=0.6,
            probability=0.65,
            source_indicator="T5YIE",
        ))

    # Fed Funds rate
    fed = by_id.get("FEDFUNDS") or by_name.get("federal funds rate")
    if fed:
        if fed.current_value > 5.0:
            if fed.trend == Trend.RISING:
                risks.append(Risk(
                    category=RiskCategory.MACRO,
                    name="Rising Interest Rates",
                    description="Higher rates increase borrowing costs and reduce equity valuations",
                    severity=0.7,
                    probability=0.75,
                    source_indicator="FEDFUNDS",
                ))
            else:
                risks.append(Risk(
                    category=RiskCategory.MACRO,
                    name="Elevated Interest Rates",
                    description=f"Fed funds rate at {fed.current_value:.2f}% restricts economic growth",
                    severity=0.6,
                    probability=0.7,
                    source_indicator="FEDFUNDS",
                ))
        elif fed.trend == Trend.RISING:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Interest Rates",
                description="Higher rates increase borrowing costs and reduce equity valuations",
                severity=0.5,
                probability=0.7,
                source_indicator="FEDFUNDS",
            ))

    return risks


def _evaluate_labor_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate labor market risks."""
    risks = []

    # Unemployment rate
    unemp = by_id.get("UNRATE") or by_name.get("unemployment rate")
    if unemp:
        if unemp.current_value > config.unemployment_high:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="High Unemployment",
                description=f"Unemployment at {unemp.current_value}% signals weak labor market",
                severity=min(1.0, (unemp.current_value - config.unemployment_high) / 3 + 0.5),
                probability=0.8,
                source_indicator="UNRATE",
            ))
        elif unemp.current_value > 4.0 and unemp.trend == Trend.RISING:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Unemployment",
                description=f"Unemployment at {unemp.current_value}% and rising - labor market softening",
                severity=0.6,
                probability=0.7,
                source_indicator="UNRATE",
            ))

    # Initial jobless claims (real-time layoff signal)
    # FRED ICSA returns actual count (e.g., 208000 = 208,000 claims)
    claims = by_id.get("ICSA") or by_name.get("initial jobless claims")
    if claims:
        # Value is actual count, 300000 = 300k claims threshold
        claims_k = claims.current_value / 1000  # Convert to thousands for display
        if claims.current_value >= 300000:  # 300k+ claims
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Layoffs",
                description=f"Initial claims at {claims_k:.0f}k - significant job losses",
                severity=0.7,
                probability=0.75,
                source_indicator="ICSA",
            ))
        elif claims.current_value >= 250000:  # 250k+ claims
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Jobless Claims",
                description=f"Initial claims at {claims_k:.0f}k - labor market weakening",
                severity=0.5,
                probability=0.6,
                source_indicator="ICSA",
            ))

    # Job openings rate (labor demand)
    jolt = by_id.get("JTSJOR") or by_name.get("job openings rate")
    if jolt and jolt.current_value < 4.0:  # Below normal
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Weak Labor Demand",
            description=f"Job openings rate at {jolt.current_value:.1f}% - employer demand softening",
            severity=0.5,
            probability=0.6,
            source_indicator="JTSJOR",
        ))

    # Consumer sentiment (leading indicator of spending)
    sentiment = by_id.get("UMCSENT") or by_name.get("consumer sentiment")
    if sentiment and sentiment.current_value < 70:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Weak Consumer Sentiment",
            description=f"Consumer sentiment at {sentiment.current_value:.0f} - may reduce spending",
            severity=0.5,
            probability=0.65,
            source_indicator="UMCSENT",
        ))

    return risks


def _evaluate_valuation_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate market valuation risks (Buffett indicator)."""
    risks = []

    # Wilshire 5000 (for Buffett indicator calculation)
    # Note: Full Buffett indicator requires Wilshire/GDP ratio
    # We track Wilshire 5000 trend as a proxy
    wilshire = by_id.get("WILL5000PR") or by_name.get("wilshire 5000 price index")
    # GDP for Buffett indicator ratio
    gdp = by_id.get("GDP") or by_name.get("gross domestic product")

    # Calculate Buffett indicator if both available
    if wilshire and gdp and gdp.current_value > 0:
        # Buffett Indicator = Total Market Cap / GDP
        # WILL5000PR is a price index, but empirically:
        # - Index ~45,000-50,000 corresponds to market cap ~$45-50T
        # - Suggests approximate 1:1 ratio where index ≈ market cap in billions
        # This is a rough approximation for risk assessment purposes

        # Approximate market cap in billions (index value ≈ market cap in billions)
        market_cap_billions = wilshire.current_value

        # GDP is in billions USD from FRED
        gdp_billions = gdp.current_value

        # Calculate Buffett indicator ratio
        buffett_ratio = market_cap_billions / gdp_billions

        # Interpret the ratio
        # Historical ranges:
        # < 0.75: Significantly undervalued (rare, crisis levels)
        # 0.75-1.0: Undervalued to fairly valued
        # 1.0-1.25: Fairly valued to moderately overvalued
        # 1.25-1.5: Overvalued
        # > 1.5: Significantly overvalued (bubble territory)

        if buffett_ratio > 1.5:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Extreme Market Valuation",
                description=f"Buffett indicator at {buffett_ratio:.2f}x GDP - historically high valuation suggesting bubble risk",
                severity=0.85,
                probability=0.7,
                source_indicator="WILL5000PR",
            ))
        elif buffett_ratio > 1.25:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Elevated Market Valuation",
                description=f"Buffett indicator at {buffett_ratio:.2f}x GDP - market moderately overvalued vs historical norms",
                severity=0.6,
                probability=0.65,
                source_indicator="WILL5000PR",
            ))
        elif buffett_ratio < 0.75 and wilshire.trend == Trend.FALLING:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Market Capitulation",
                description=f"Buffett indicator at {buffett_ratio:.2f}x GDP - market significantly undervalued, potential crisis",
                severity=0.7,
                probability=0.75,
                source_indicator="WILL5000PR",
            ))

    return risks


def _evaluate_global_risk(
    by_id: dict,
    by_name: dict,
    config: ScoringConfig,
) -> list[Risk]:
    """Evaluate global and currency risks."""
    risks = []

    # Dollar index strength (strong dollar hurts exports and EM)
    dxy = by_id.get("DTWEXBGS") or by_name.get("trade weighted dollar index")
    if dxy:
        if dxy.current_value >= 115:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Dollar Strength",
                description=f"Dollar index at {dxy.current_value:.0f} - pressures multinational earnings and EM",
                severity=0.6,
                probability=0.7,
                source_indicator="DTWEXBGS",
            ))
        elif dxy.current_value >= 110 and dxy.trend == Trend.RISING:
            risks.append(Risk(
                category=RiskCategory.MACRO,
                name="Rising Dollar",
                description=f"Dollar index at {dxy.current_value:.0f} and rising - headwind for exporters",
                severity=0.45,
                probability=0.6,
                source_indicator="DTWEXBGS",
            ))

    # Trade balance (widening deficit)
    trade = by_id.get("BOPGSTB") or by_name.get("trade balance")
    if trade and trade.current_value < -80000 and trade.trend == Trend.FALLING:
        risks.append(Risk(
            category=RiskCategory.MACRO,
            name="Widening Trade Deficit",
            description=f"Trade deficit at ${abs(trade.current_value)/1000:.0f}B and widening",
            severity=0.4,
            probability=0.55,
            source_indicator="BOPGSTB",
        ))

    return risks


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

    # Valuation details with specific numbers
    val_details = []
    if metrics.pe_trailing is not None:
        val_details.append(f"PE of {metrics.pe_trailing:.1f}")
    if metrics.peg_ratio is not None and metrics.peg_ratio > 0:
        val_details.append(f"PEG of {metrics.peg_ratio:.2f}")

    if val_details:
        if score.valuation_score > 0.7:
            parts.append(f"with attractive valuation ({', '.join(val_details)})")
        elif score.valuation_score < 0.3:
            parts.append(f"despite rich valuation ({', '.join(val_details)})")
        else:
            parts.append(f"trading at {', '.join(val_details)}")

    # Growth details with specific numbers
    growth_details = []
    if metrics.revenue_growth is not None:
        growth_pct = metrics.revenue_growth * 100
        if growth_pct > 0:
            growth_details.append(f"{growth_pct:.0f}% revenue growth")
        else:
            growth_details.append(f"{abs(growth_pct):.0f}% revenue decline")

    if metrics.earnings_growth is not None:
        eg_pct = metrics.earnings_growth * 100
        if eg_pct > 0:
            growth_details.append(f"{eg_pct:.0f}% earnings growth")

    if growth_details:
        if score.growth_score > 0.7:
            parts.append(f"with strong growth ({', '.join(growth_details)})")
        elif score.growth_score < 0.3:
            parts.append(f"but limited growth ({', '.join(growth_details)})")
        else:
            parts.append(f"showing {', '.join(growth_details)}")

    # Quality/profitability metrics
    quality_details = []
    if metrics.profit_margin is not None:
        pm_pct = metrics.profit_margin * 100
        quality_details.append(f"{pm_pct:.1f}% profit margin")
    if metrics.roe is not None:
        roe_pct = metrics.roe * 100
        quality_details.append(f"{roe_pct:.1f}% ROE")

    if quality_details and score.quality_score > 0.7:
        parts.append(f"backed by solid fundamentals ({', '.join(quality_details)})")

    # Momentum with specific price changes
    if score.momentum_score > 0.6:
        momentum_details = []
        if metrics.price_change_3m is not None:
            change_pct = metrics.price_change_3m * 100
            if abs(change_pct) > 5:
                momentum_details.append(f"up {change_pct:.0f}% over 3 months")
        elif metrics.price_change_1m is not None:
            change_pct = metrics.price_change_1m * 100
            if abs(change_pct) > 3:
                momentum_details.append(f"up {change_pct:.0f}% in the past month")

        if momentum_details:
            parts.append(f". Momentum is strong: {', '.join(momentum_details)}")

    # Analyst targets
    if metrics.price_target is not None and metrics.upside_potential is not None:
        upside = metrics.upside_potential
        if upside > 5:  # Only mention if material upside
            parts.append(f". Analysts see {upside:.0f}% upside to ${metrics.price_target:.2f} target")
        elif upside < -5:
            parts.append(f". Trading {abs(upside):.0f}% above ${metrics.price_target:.2f} analyst target")

    # Dividend commentary
    if metrics.dividend_yield is not None and metrics.dividend_yield > 0.02:
        div_pct = metrics.dividend_yield * 100
        parts.append(f". Offers {div_pct:.1f}% dividend yield")

    # Risk summary
    if risks:
        top_risk = risks[0]
        parts.append(f". Key risk: {top_risk.name.lower()}")

    thesis = " ".join(parts)
    if not thesis.endswith("."):
        thesis += "."

    return thesis
