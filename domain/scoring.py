"""
Systematic Scoring Algorithm for Stock Picks.

Pure functions that compute conviction scores and classify investment timeframes.
No I/O - this is domain layer logic only.

The algorithm works in stages:
1. Component Scores: Compute valuation, momentum, quality scores (0-1 each)
2. Macro Adjustment: Adjust based on sector/macro alignment (-0.5 to +0.5)
3. Timeframe Classification: Determine SHORT/MEDIUM/LONG based on score patterns
4. Thesis Generation: Create narrative from top contributing factors
5. Risk Identification: Flag low-scoring factors as risks
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import NamedTuple

from .analysis_types import (
    ConvictionScore,
    MacroContext,
    Risk,
    RiskCategory,
    StockMetrics,
)
from .models import Timeframe, Trend


# ============================================================================
# Configuration Types (passed in, not imported)
# ============================================================================


@dataclass(frozen=True)
class ScoringThresholds:
    """Thresholds for scoring calculations. Load from config."""

    # Valuation
    pe_low: float = 15.0
    pe_high: float = 30.0
    peg_fair: float = 1.0
    pb_low: float = 1.0
    pb_high: float = 5.0

    # Growth
    revenue_growth_high: float = 0.20
    revenue_growth_low: float = 0.05
    earnings_growth_high: float = 0.25

    # Quality
    profit_margin_good: float = 0.15
    roe_good: float = 0.15

    # Momentum
    momentum_strong: float = 0.10
    volume_spike: float = 2.0

    # RSI-like thresholds
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0


@dataclass(frozen=True)
class ScoringWeights:
    """Weights for combining component scores. Must sum to 1.0."""

    valuation: float = 0.25
    growth: float = 0.25
    quality: float = 0.20
    momentum: float = 0.15
    analyst: float = 0.15

    def __post_init__(self) -> None:
        total = self.valuation + self.growth + self.quality + self.momentum + self.analyst
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class SectorSensitivities:
    """Macro sensitivity by sector. Values from -1 to 1."""

    rate_sensitivity: dict[str, float] = field(default_factory=dict)
    inflation_sensitivity: dict[str, float] = field(default_factory=dict)
    recession_sensitivity: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TimeframeRules:
    """Rules for classifying investment timeframe."""

    short_momentum_threshold: float = -0.15
    short_volume_spike: float = 2.0
    medium_valuation_gap: float = 0.20
    long_quality_threshold: float = 0.6
    long_valuation_fair: float = 0.4


# ============================================================================
# Output Types
# ============================================================================


@dataclass(frozen=True)
class ScoredPick:
    """Complete scored stock pick with conviction, timeframe, thesis, and risks."""

    ticker: str
    conviction: int  # 1-10 scale
    timeframe: Timeframe
    thesis: str
    risks: list[str]
    score_breakdown: ConvictionScore
    sector: str
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def conviction_normalized(self) -> float:
        """Conviction as 0-1 for compatibility."""
        return self.conviction / 10.0


class ScoreFactor(NamedTuple):
    """A contributing factor to the score."""

    name: str
    score: float  # 0-1
    weight: float  # contribution weight
    description: str


# ============================================================================
# Component Scoring Functions (Pure)
# ============================================================================


def _normalize_score(value: float, low: float, high: float, invert: bool = False) -> float:
    """
    Normalize a value to 0-1 range.

    Args:
        value: The value to normalize
        low: Value that maps to 1.0 (best)
        high: Value that maps to 0.0 (worst)
        invert: If True, low maps to 0.0 and high to 1.0

    Returns:
        Score between 0 and 1
    """
    if low == high:
        return 0.5

    # Calculate position in range
    normalized = (value - low) / (high - low)

    # Clamp to 0-1
    normalized = max(0.0, min(1.0, normalized))

    # Invert if needed (higher value = higher score)
    if not invert:
        normalized = 1.0 - normalized

    return round(normalized, 4)


def _score_pe(
    pe: float | None,
    sector_avg_pe: float,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """
    Score P/E ratio relative to sector average and absolute thresholds.

    Returns:
        (score, description)
    """
    if pe is None or pe <= 0:
        return 0.5, "P/E unavailable"

    # Relative to sector (40% weight)
    pe_ratio = pe / sector_avg_pe if sector_avg_pe > 0 else 1.0
    relative_score = _normalize_score(pe_ratio, 0.5, 1.5)  # 50% of sector = best, 150% = worst

    # Absolute score (60% weight)
    absolute_score = _normalize_score(pe, thresholds.pe_low, thresholds.pe_high)

    combined = 0.4 * relative_score + 0.6 * absolute_score

    if pe < sector_avg_pe * 0.7:
        desc = f"Attractive P/E of {pe:.1f}x vs sector {sector_avg_pe:.1f}x"
    elif pe > sector_avg_pe * 1.3:
        desc = f"Premium P/E of {pe:.1f}x vs sector {sector_avg_pe:.1f}x"
    else:
        desc = f"Fair P/E of {pe:.1f}x near sector average"

    return round(combined, 4), desc


def _score_peg(peg: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score PEG ratio (P/E to Growth)."""
    if peg is None or peg <= 0:
        return 0.5, "PEG unavailable"

    # PEG < 1 is undervalued, > 2 is overvalued
    score = _normalize_score(peg, thresholds.peg_fair * 0.5, thresholds.peg_fair * 2.0)

    if peg < thresholds.peg_fair:
        desc = f"Attractive PEG of {peg:.2f} (growth-adjusted value)"
    elif peg > thresholds.peg_fair * 1.5:
        desc = f"Elevated PEG of {peg:.2f} (expensive for growth)"
    else:
        desc = f"Fair PEG of {peg:.2f}"

    return round(score, 4), desc


def _score_price_to_book(pb: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score Price-to-Book ratio."""
    if pb is None or pb <= 0:
        return 0.5, "P/B unavailable"

    score = _normalize_score(pb, thresholds.pb_low, thresholds.pb_high)

    if pb < thresholds.pb_low:
        desc = f"Below book value at {pb:.2f}x"
    elif pb > thresholds.pb_high:
        desc = f"High P/B of {pb:.2f}x"
    else:
        desc = f"Reasonable P/B of {pb:.2f}x"

    return round(score, 4), desc


def compute_valuation_score(
    metrics: StockMetrics,
    sector_avg_pe: float,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """
    Compute valuation score from P/E, PEG, P/B metrics.

    Returns:
        (overall_score, list of contributing factors)
    """
    factors: list[ScoreFactor] = []

    # P/E (40% of valuation)
    pe_score, pe_desc = _score_pe(metrics.pe_trailing, sector_avg_pe, thresholds)
    factors.append(ScoreFactor("P/E Ratio", pe_score, 0.4, pe_desc))

    # PEG (35% of valuation)
    peg_score, peg_desc = _score_peg(metrics.peg_ratio, thresholds)
    factors.append(ScoreFactor("PEG Ratio", peg_score, 0.35, peg_desc))

    # P/B (25% of valuation)
    pb_score, pb_desc = _score_price_to_book(metrics.price_to_book, thresholds)
    factors.append(ScoreFactor("P/B Ratio", pb_score, 0.25, pb_desc))

    # Weighted average
    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


def _score_revenue_growth(growth: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score revenue growth rate."""
    if growth is None:
        return 0.5, "Revenue growth unavailable"

    # Score from low to high growth
    score = _normalize_score(
        growth,
        thresholds.revenue_growth_low,
        thresholds.revenue_growth_high,
        invert=True,  # Higher growth = higher score
    )

    pct = growth * 100
    if growth >= thresholds.revenue_growth_high:
        desc = f"Strong revenue growth of {pct:.1f}%"
    elif growth <= thresholds.revenue_growth_low:
        desc = f"Weak revenue growth of {pct:.1f}%"
    else:
        desc = f"Moderate revenue growth of {pct:.1f}%"

    return round(score, 4), desc


def _score_earnings_growth(growth: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score earnings growth rate."""
    if growth is None:
        return 0.5, "Earnings growth unavailable"

    score = _normalize_score(
        growth,
        0.0,
        thresholds.earnings_growth_high,
        invert=True,
    )

    pct = growth * 100
    if growth >= thresholds.earnings_growth_high:
        desc = f"Excellent earnings growth of {pct:.1f}%"
    elif growth <= 0:
        desc = f"Negative earnings growth of {pct:.1f}%"
    else:
        desc = f"Positive earnings growth of {pct:.1f}%"

    return round(score, 4), desc


def compute_growth_score(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """Compute growth score from revenue and earnings growth."""
    factors: list[ScoreFactor] = []

    # Revenue growth (55%)
    rev_score, rev_desc = _score_revenue_growth(metrics.revenue_growth, thresholds)
    factors.append(ScoreFactor("Revenue Growth", rev_score, 0.55, rev_desc))

    # Earnings growth (45%)
    earn_score, earn_desc = _score_earnings_growth(metrics.earnings_growth, thresholds)
    factors.append(ScoreFactor("Earnings Growth", earn_score, 0.45, earn_desc))

    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


def _score_profit_margin(margin: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score profit margin."""
    if margin is None:
        return 0.5, "Profit margin unavailable"

    score = _normalize_score(margin, 0.0, thresholds.profit_margin_good, invert=True)

    pct = margin * 100
    if margin >= thresholds.profit_margin_good:
        desc = f"Strong profit margin of {pct:.1f}%"
    elif margin <= 0:
        desc = f"Negative margin of {pct:.1f}%"
    else:
        desc = f"Modest profit margin of {pct:.1f}%"

    return round(score, 4), desc


def _score_roe(roe: float | None, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score return on equity."""
    if roe is None:
        return 0.5, "ROE unavailable"

    score = _normalize_score(roe, 0.0, thresholds.roe_good, invert=True)

    pct = roe * 100
    if roe >= thresholds.roe_good:
        desc = f"Excellent ROE of {pct:.1f}%"
    elif roe <= 0:
        desc = f"Negative ROE of {pct:.1f}%"
    else:
        desc = f"Adequate ROE of {pct:.1f}%"

    return round(score, 4), desc


def compute_quality_score(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """Compute quality score from profitability metrics."""
    factors: list[ScoreFactor] = []

    # Profit margin (50%)
    margin_score, margin_desc = _score_profit_margin(metrics.profit_margin, thresholds)
    factors.append(ScoreFactor("Profit Margin", margin_score, 0.5, margin_desc))

    # ROE (50%)
    roe_score, roe_desc = _score_roe(metrics.roe, thresholds)
    factors.append(ScoreFactor("ROE", roe_score, 0.5, roe_desc))

    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


def _estimate_rsi(price_change_1m: float | None) -> float | None:
    """
    Estimate RSI-like indicator from monthly price change.

    This is a simplified proxy - real RSI requires daily price data.
    Maps price change to 0-100 scale where:
    - Large gains -> high RSI (overbought)
    - Large losses -> low RSI (oversold)
    """
    if price_change_1m is None:
        return None

    # Map -30% to +30% price change to 20-80 RSI range
    # Beyond that, extrapolate linearly
    rsi = 50 + (price_change_1m * 100)  # 1% change = 1 RSI point
    return max(0.0, min(100.0, rsi))


def _score_momentum(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """Score price momentum from recent returns."""
    if metrics.price_change_1m is None:
        return 0.5, "Recent momentum unavailable"

    # Positive momentum is good, but not too extreme (overbought)
    rsi = _estimate_rsi(metrics.price_change_1m)

    if rsi is not None:
        if rsi < thresholds.rsi_oversold:
            # Oversold - contrarian opportunity (moderate score)
            score = 0.6
            desc = f"Oversold with RSI ~{rsi:.0f}, potential bounce"
        elif rsi > thresholds.rsi_overbought:
            # Overbought - caution
            score = 0.3
            desc = f"Overbought with RSI ~{rsi:.0f}, extended"
        else:
            # Normal range - score based on direction
            pct = metrics.price_change_1m * 100
            if metrics.price_change_1m > 0:
                score = 0.5 + min(0.3, metrics.price_change_1m)
                desc = f"Positive momentum of {pct:+.1f}% monthly"
            else:
                score = 0.5 + max(-0.2, metrics.price_change_1m)
                desc = f"Negative momentum of {pct:.1f}% monthly"
    else:
        pct = metrics.price_change_1m * 100
        score = 0.5 + max(-0.3, min(0.3, metrics.price_change_1m))
        desc = f"Monthly return of {pct:+.1f}%"

    return round(max(0.0, min(1.0, score)), 4), desc


def _score_volume(metrics: StockMetrics, thresholds: ScoringThresholds) -> tuple[float, str]:
    """Score volume activity."""
    ratio = metrics.volume_ratio
    if ratio is None:
        return 0.5, "Volume data unavailable"

    if ratio >= thresholds.volume_spike:
        score = 0.7  # High volume can indicate catalyst
        desc = f"Elevated volume at {ratio:.1f}x average"
    elif ratio >= 1.0:
        score = 0.55
        desc = f"Above-average volume at {ratio:.1f}x"
    else:
        score = 0.5
        desc = f"Below-average volume at {ratio:.1f}x"

    return round(score, 4), desc


def compute_momentum_score(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """Compute momentum score from price action and volume."""
    factors: list[ScoreFactor] = []

    # Price momentum (70%)
    mom_score, mom_desc = _score_momentum(metrics, thresholds)
    factors.append(ScoreFactor("Price Momentum", mom_score, 0.7, mom_desc))

    # Volume (30%)
    vol_score, vol_desc = _score_volume(metrics, thresholds)
    factors.append(ScoreFactor("Volume", vol_score, 0.3, vol_desc))

    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


def _score_analyst_rating(rating: float | None) -> tuple[float, str]:
    """Score analyst consensus (1=Strong Buy, 5=Strong Sell)."""
    if rating is None:
        return 0.5, "No analyst coverage"

    # Invert: 1 (buy) = high score, 5 (sell) = low score
    score = _normalize_score(rating, 1.0, 5.0)

    if rating <= 1.5:
        desc = f"Strong Buy consensus ({rating:.1f})"
    elif rating <= 2.5:
        desc = f"Buy consensus ({rating:.1f})"
    elif rating <= 3.5:
        desc = f"Hold consensus ({rating:.1f})"
    else:
        desc = f"Sell consensus ({rating:.1f})"

    return round(score, 4), desc


def _score_upside(metrics: StockMetrics) -> tuple[float, str]:
    """Score upside to analyst price target."""
    upside = metrics.upside_potential
    if upside is None:
        return 0.5, "No price target"

    # Map upside: 0% = 0.5, 20% = 0.8, -20% = 0.2
    score = 0.5 + (upside / 100) * 1.5
    score = max(0.0, min(1.0, score))

    if upside > 15:
        desc = f"Significant upside of {upside:.1f}% to target"
    elif upside > 0:
        desc = f"Modest upside of {upside:.1f}% to target"
    elif upside > -10:
        desc = f"Near target price ({upside:+.1f}%)"
    else:
        desc = f"Trading above target ({upside:+.1f}%)"

    return round(score, 4), desc


def compute_analyst_score(metrics: StockMetrics) -> tuple[float, list[ScoreFactor]]:
    """Compute score from analyst ratings and price targets."""
    factors: list[ScoreFactor] = []

    # Analyst rating (60%)
    rating_score, rating_desc = _score_analyst_rating(metrics.analyst_rating)
    factors.append(ScoreFactor("Analyst Rating", rating_score, 0.6, rating_desc))

    # Upside to target (40%)
    upside_score, upside_desc = _score_upside(metrics)
    factors.append(ScoreFactor("Price Target", upside_score, 0.4, upside_desc))

    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


# ============================================================================
# Macro Adjustment
# ============================================================================


def compute_macro_adjustment(
    sector: str,
    macro: MacroContext,
    sensitivities: SectorSensitivities,
) -> tuple[float, str]:
    """
    Compute macro adjustment based on sector sensitivity to current conditions.

    Returns adjustment in range -0.5 to +0.5.
    """
    sector_lower = sector.lower().replace(" ", "_")

    # Get sector sensitivities (default to 0 if unknown sector)
    rate_sens = sensitivities.rate_sensitivity.get(sector_lower, 0.0)
    inflation_sens = sensitivities.inflation_sensitivity.get(sector_lower, 0.0)
    recession_sens = sensitivities.recession_sensitivity.get(sector_lower, 0.0)

    adjustment = 0.0
    reasons = []

    # Rate environment
    if macro.rate_trend == Trend.RISING:
        adj = rate_sens * 0.15  # Rising rates
        adjustment += adj
        if adj > 0.05:
            reasons.append("benefits from rising rates")
        elif adj < -0.05:
            reasons.append("pressured by rising rates")
    elif macro.rate_trend == Trend.FALLING:
        adj = -rate_sens * 0.15  # Falling rates (inverse effect)
        adjustment += adj
        if adj > 0.05:
            reasons.append("benefits from falling rates")

    # Inflation environment
    if macro.inflation_rate is not None and macro.inflation_rate > 4.0:
        adj = inflation_sens * 0.1
        adjustment += adj
        if adj > 0.05:
            reasons.append("inflation hedge")
        elif adj < -0.05:
            reasons.append("inflation pressure on margins")

    # Recession risk (inverted yield curve)
    if macro.is_yield_curve_inverted:
        adj = recession_sens * 0.15
        adjustment += adj
        if adj > 0.05:
            reasons.append("defensive in slowdown")
        elif adj < -0.05:
            reasons.append("cyclical exposure to slowdown")

    # VIX / fear gauge
    if macro.vix is not None and macro.vix > 25:
        adjustment -= 0.05  # General caution in high volatility
        reasons.append("elevated volatility")

    # Clamp to range
    adjustment = max(-0.5, min(0.5, adjustment))

    if reasons:
        description = f"Macro: {'; '.join(reasons)}"
    elif adjustment > 0:
        description = "Favorable macro alignment"
    elif adjustment < 0:
        description = "Unfavorable macro alignment"
    else:
        description = "Neutral macro environment"

    return round(adjustment, 4), description


# ============================================================================
# Timeframe Classification
# ============================================================================


def classify_timeframe(
    valuation_score: float,
    momentum_score: float,
    quality_score: float,
    metrics: StockMetrics,
    rules: TimeframeRules,
) -> tuple[Timeframe, str]:
    """
    Classify investment timeframe based on score patterns.

    Returns:
        (Timeframe, reason)
    """
    # SHORT: Technical setups, momentum plays, oversold bounces

    # Oversold bounce - stock dropped significantly
    if metrics.price_change_1m is not None and metrics.price_change_1m < rules.short_momentum_threshold:
        rsi = _estimate_rsi(metrics.price_change_1m)
        if rsi is not None and rsi < 35:
            return Timeframe.SHORT, "Oversold bounce opportunity"

    # Volume spike - catalyst driven
    volume_ratio = metrics.volume_ratio or 1.0
    if volume_ratio >= rules.short_volume_spike:
        return Timeframe.SHORT, "Catalyst-driven volume spike"

    # Strong positive momentum - ride the wave
    if metrics.price_change_1m is not None and metrics.price_change_1m > 0.10:
        return Timeframe.SHORT, "Strong momentum play"

    # Strong 3-month momentum with high conviction
    if metrics.price_change_3m is not None and metrics.price_change_3m > 0.20:
        if momentum_score >= 0.6:
            return Timeframe.SHORT, "Strong trend momentum"

    # Strong analyst consensus (1.0 = Strong Buy) - near-term catalyst
    if metrics.analyst_rating is not None and metrics.analyst_rating <= 1.8:
        if momentum_score >= 0.4:
            return Timeframe.SHORT, "Strong analyst conviction catalyst"

    # High growth with positive momentum - capture growth phase
    if metrics.revenue_growth is not None and metrics.revenue_growth > 0.25:
        if momentum_score >= 0.5:
            return Timeframe.SHORT, "High growth momentum play"

    # LONG: High quality + fair valuation = compounding opportunity
    if quality_score >= rules.long_quality_threshold and valuation_score >= rules.long_valuation_fair:
        return Timeframe.LONG, "Quality compounder at fair value"

    # MEDIUM: Default for valuation gaps and sector plays
    if valuation_score >= 0.6:
        return Timeframe.MEDIUM, "Valuation gap closing opportunity"

    if momentum_score >= 0.6:
        return Timeframe.MEDIUM, "Trend following opportunity"

    # Default to MEDIUM
    return Timeframe.MEDIUM, "Balanced risk/reward profile"


# ============================================================================
# Thesis and Risk Generation
# ============================================================================


def generate_thesis(
    ticker: str,
    sector: str,
    factors: list[ScoreFactor],
    macro_description: str,
    timeframe: Timeframe,
    conviction: int,
) -> str:
    """Generate investment thesis from top contributing factors."""
    # Sort factors by contribution (score * weight)
    sorted_factors = sorted(factors, key=lambda f: f.score * f.weight, reverse=True)

    # Take top 2-3 positive factors
    top_factors = [f for f in sorted_factors[:3] if f.score >= 0.5]

    if not top_factors:
        return f"{ticker} ({sector}): Limited conviction due to weak fundamentals across metrics."

    # Build thesis
    factor_descriptions = [f.description for f in top_factors]

    timeframe_str = {
        Timeframe.SHORT: "near-term",
        Timeframe.MEDIUM: "medium-term",
        Timeframe.LONG: "long-term",
    }[timeframe]

    conviction_adj = {
        range(1, 4): "speculative",
        range(4, 6): "moderate",
        range(6, 8): "solid",
        range(8, 11): "high-conviction",
    }
    conv_str = next(
        (v for k, v in conviction_adj.items() if conviction in k),
        "moderate",
    )

    thesis = f"{ticker} ({sector}): {conv_str.capitalize()} {timeframe_str} opportunity. "
    thesis += ". ".join(factor_descriptions[:2]) + ". "

    if macro_description and "Neutral" not in macro_description:
        thesis += macro_description + "."

    return thesis


def identify_risks(
    factors: list[ScoreFactor],
    macro_adjustment: float,
    macro_description: str,
) -> list[str]:
    """Identify risk factors from low-scoring components."""
    risks: list[str] = []

    # Low-scoring factors become risks
    for factor in factors:
        if factor.score < 0.4:
            risk_desc = f"{factor.name}: {factor.description}"
            risks.append(risk_desc)

    # Macro risks
    if macro_adjustment < -0.1:
        risks.append(f"Macro headwind: {macro_description}")

    # Cap at 5 risks
    return risks[:5]


# ============================================================================
# Main Scoring Function
# ============================================================================


def score_stock(
    metrics: StockMetrics,
    macro: MacroContext,
    sector: str,
    sector_avg_pe: float,
    thresholds: ScoringThresholds | None = None,
    weights: ScoringWeights | None = None,
    sensitivities: SectorSensitivities | None = None,
    timeframe_rules: TimeframeRules | None = None,
) -> ScoredPick:
    """
    Compute complete scored pick for a stock.

    Args:
        metrics: Stock metrics from adapter
        macro: Macro context from adapter
        sector: Stock sector (e.g., "technology", "healthcare")
        sector_avg_pe: Average P/E for the sector
        thresholds: Scoring thresholds (optional, uses defaults)
        weights: Scoring weights (optional, uses defaults)
        sensitivities: Sector macro sensitivities (optional, uses defaults)
        timeframe_rules: Timeframe classification rules (optional)

    Returns:
        ScoredPick with conviction, timeframe, thesis, and risks
    """
    # Use defaults if not provided
    thresholds = thresholds or ScoringThresholds()
    weights = weights or ScoringWeights()
    sensitivities = sensitivities or SectorSensitivities()
    timeframe_rules = timeframe_rules or TimeframeRules()

    all_factors: list[ScoreFactor] = []
    factors_used: list[str] = []
    factors_missing: list[str] = []

    # Compute component scores
    valuation_score, val_factors = compute_valuation_score(metrics, sector_avg_pe, thresholds)
    all_factors.extend(val_factors)
    factors_used.append("valuation")

    growth_score, growth_factors = compute_growth_score(metrics, thresholds)
    all_factors.extend(growth_factors)
    if metrics.revenue_growth is not None or metrics.earnings_growth is not None:
        factors_used.append("growth")
    else:
        factors_missing.append("growth")

    quality_score, quality_factors = compute_quality_score(metrics, thresholds)
    all_factors.extend(quality_factors)
    if metrics.profit_margin is not None or metrics.roe is not None:
        factors_used.append("quality")
    else:
        factors_missing.append("quality")

    momentum_score, momentum_factors = compute_momentum_score(metrics, thresholds)
    all_factors.extend(momentum_factors)
    factors_used.append("momentum")

    analyst_score, analyst_factors = compute_analyst_score(metrics)
    all_factors.extend(analyst_factors)
    if metrics.analyst_rating is not None:
        factors_used.append("analyst")
    else:
        factors_missing.append("analyst")

    # Macro adjustment
    macro_adjustment, macro_desc = compute_macro_adjustment(sector, macro, sensitivities)

    # Weighted overall score (0-1)
    base_score = (
        weights.valuation * valuation_score
        + weights.growth * growth_score
        + weights.quality * quality_score
        + weights.momentum * momentum_score
        + weights.analyst * analyst_score
    )

    # Apply macro adjustment
    overall_score = max(0.0, min(1.0, base_score + macro_adjustment))

    # Convert to 1-10 conviction
    conviction = max(1, min(10, round(overall_score * 10)))

    # Confidence based on data completeness
    confidence = len(factors_used) / (len(factors_used) + len(factors_missing))

    # Create conviction score breakdown
    score_breakdown = ConvictionScore(
        overall=round(overall_score, 4),
        valuation_score=valuation_score,
        growth_score=growth_score,
        quality_score=quality_score,
        momentum_score=momentum_score,
        macro_adjustment=macro_adjustment,
        factors_used=factors_used,
        factors_missing=factors_missing,
        confidence=round(confidence, 4),
    )

    # Classify timeframe
    timeframe, timeframe_reason = classify_timeframe(
        valuation_score,
        momentum_score,
        quality_score,
        metrics,
        timeframe_rules,
    )

    # Generate thesis
    thesis = generate_thesis(
        metrics.ticker,
        sector,
        all_factors,
        macro_desc,
        timeframe,
        conviction,
    )

    # Identify risks
    risks = identify_risks(all_factors, macro_adjustment, macro_desc)

    return ScoredPick(
        ticker=metrics.ticker,
        conviction=conviction,
        timeframe=timeframe,
        thesis=thesis,
        risks=risks,
        score_breakdown=score_breakdown,
        sector=sector,
    )


# ============================================================================
# Batch Scoring
# ============================================================================


def score_stocks(
    stocks: list[tuple[StockMetrics, str, float]],  # (metrics, sector, sector_avg_pe)
    macro: MacroContext,
    thresholds: ScoringThresholds | None = None,
    weights: ScoringWeights | None = None,
    sensitivities: SectorSensitivities | None = None,
    timeframe_rules: TimeframeRules | None = None,
) -> list[ScoredPick]:
    """
    Score multiple stocks and return sorted by conviction.

    Args:
        stocks: List of (metrics, sector, sector_avg_pe) tuples
        macro: Shared macro context
        thresholds, weights, sensitivities, timeframe_rules: Optional config

    Returns:
        List of ScoredPick sorted by conviction (highest first)
    """
    picks = [
        score_stock(
            metrics=m,
            macro=macro,
            sector=s,
            sector_avg_pe=pe,
            thresholds=thresholds,
            weights=weights,
            sensitivities=sensitivities,
            timeframe_rules=timeframe_rules,
        )
        for m, s, pe in stocks
    ]

    # Sort by conviction (descending), then by confidence
    return sorted(picks, key=lambda p: (p.conviction, p.score_breakdown.confidence), reverse=True)
