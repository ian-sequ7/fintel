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

import math
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

    # Quality (expanded for Novy-Marx, Fama-French)
    profit_margin_good: float = 0.15
    roe_good: float = 0.15
    gross_profitability_good: float = 0.33  # Novy-Marx: GP/Assets > 33% is strong
    asset_growth_high: float = 0.20  # >20% asset growth is negative predictor

    # Momentum (multi-period per Jegadeesh-Titman)
    momentum_strong: float = 0.10
    momentum_12_1_strong: float = 0.30  # 30% 12-1 month return is strong
    momentum_12_1_weak: float = -0.10  # -10% is weak signal
    volume_spike: float = 2.0

    # RSI-like thresholds
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # Days-to-Cover thresholds (Hong et al NBER)
    dtc_crowded: float = 10.0  # >10 days is crowded short (risky)
    dtc_low: float = 2.0  # <2 days is low short interest (bullish)


@dataclass(frozen=True)
class ScoringWeights:
    """
    Weights for combining component scores. Must sum to 1.0.

    Academic evidence-based weights (default):
    - Momentum (multi-period): 25% - Jegadeesh-Titman 12-1 month effect
    - Quality (expanded): 25% - Novy-Marx gross profitability + asset growth
    - Valuation: 20% - Classic value factors
    - Growth: 15% - Revenue/earnings growth
    - Analyst: 10% - Consensus estimates and targets
    - Smart Money: 5% - 13F changes, insider clusters
    """

    valuation: float = 0.20
    growth: float = 0.15
    quality: float = 0.25
    momentum: float = 0.25
    analyst: float = 0.10
    smart_money: float = 0.05

    def __post_init__(self) -> None:
        total = (self.valuation + self.growth + self.quality +
                 self.momentum + self.analyst + self.smart_money)
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


@dataclass(frozen=True)
class TimeframeWeights:
    """
    Timeframe-specific scoring weights.

    Different timeframes should emphasize different factors:
    - SHORT: Momentum + insider clusters (trade the catalyst)
    - MEDIUM: 13F changes + earnings revisions (follow smart money)
    - LONG: Quality + value (compound fundamentals)
    """

    @staticmethod
    def for_short() -> "ScoringWeights":
        """Weights for SHORT timeframe (days to weeks)."""
        return ScoringWeights(
            momentum=0.35,      # Primary: technical momentum
            quality=0.15,       # Less important for short-term
            valuation=0.15,     # Less important for short-term
            growth=0.15,        # Moderate importance
            analyst=0.10,       # Consensus can be slow
            smart_money=0.10,   # Insider clusters are important for catalysts
        )

    @staticmethod
    def for_medium() -> "ScoringWeights":
        """Weights for MEDIUM timeframe (weeks to months)."""
        return ScoringWeights(
            momentum=0.25,      # Still important but less so
            quality=0.20,       # Growing importance
            valuation=0.20,     # Growing importance
            growth=0.15,        # Moderate importance
            analyst=0.12,       # Earnings revisions matter here
            smart_money=0.08,   # 13F changes matter here
        )

    @staticmethod
    def for_long() -> "ScoringWeights":
        """Weights for LONG timeframe (months to years)."""
        return ScoringWeights(
            momentum=0.10,      # Less important for long-term
            quality=0.30,       # Primary: compound quality
            valuation=0.30,     # Primary: buy cheap
            growth=0.15,        # Important for compounding
            analyst=0.10,       # Helpful but not critical
            smart_money=0.05,   # Long-term fundamentals matter more
        )


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


def _score_gross_profitability(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """
    Score gross profitability (Novy-Marx factor).

    Gross profitability = gross_profit / total_assets
    This is THE strongest quality factor per academic research.
    Higher is better - more profit generated per unit of assets.
    """
    gp = metrics.gross_profitability
    if gp is None:
        return 0.5, "Gross profitability unavailable"

    # Score: higher GP/Assets is better
    if gp >= thresholds.gross_profitability_good:
        score = 0.8
        desc = f"Strong gross profitability of {gp:.1%}"
    elif gp >= 0.20:  # 20% is decent
        score = 0.65
        desc = f"Good gross profitability of {gp:.1%}"
    elif gp >= 0.10:  # 10% is marginal
        score = 0.5
        desc = f"Modest gross profitability of {gp:.1%}"
    elif gp > 0:
        score = 0.35
        desc = f"Low gross profitability of {gp:.1%}"
    else:
        score = 0.2
        desc = f"Negative gross profitability of {gp:.1%}"

    return round(score, 4), desc


def _score_asset_growth(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """
    Score asset growth (Fama-French CMA factor).

    High asset growth is a NEGATIVE predictor per academic research.
    Companies that grow assets aggressively tend to underperform.
    Conservative (low growth) is better.
    """
    growth = metrics.asset_growth_yoy
    if growth is None:
        return 0.5, "Asset growth unavailable"

    # INVERTED: low growth = high score
    if growth >= thresholds.asset_growth_high:
        score = 0.3  # High growth = negative signal
        pct = growth * 100
        desc = f"High asset growth of {pct:.1f}% (negative signal)"
    elif growth >= 0.10:  # 10-20% growth
        score = 0.45
        pct = growth * 100
        desc = f"Moderate asset growth of {pct:.1f}%"
    elif growth >= 0.0:  # 0-10% growth
        score = 0.6
        pct = growth * 100
        desc = f"Conservative asset growth of {pct:.1f}%"
    elif growth >= -0.10:  # Slight shrinkage
        score = 0.55
        pct = growth * 100
        desc = f"Flat/declining assets ({pct:.1f}%)"
    else:  # Large shrinkage - may indicate distress
        score = 0.4
        pct = growth * 100
        desc = f"Shrinking assets of {pct:.1f}% (potential distress)"

    return round(score, 4), desc


def compute_quality_score(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """
    Compute quality score from profitability metrics.

    Expanded to include Novy-Marx and Fama-French quality factors:
    - Gross Profitability: 35% (Novy-Marx - strongest quality factor)
    - Profit Margin: 25% (traditional quality measure)
    - ROE: 25% (shareholder returns)
    - Asset Growth: 15% (Fama-French CMA - negative predictor)
    """
    factors: list[ScoreFactor] = []

    # Gross Profitability (35%) - Novy-Marx factor
    gp_score, gp_desc = _score_gross_profitability(metrics, thresholds)
    factors.append(ScoreFactor("Gross Profitability", gp_score, 0.35, gp_desc))

    # Profit margin (25%)
    margin_score, margin_desc = _score_profit_margin(metrics.profit_margin, thresholds)
    factors.append(ScoreFactor("Profit Margin", margin_score, 0.25, margin_desc))

    # ROE (25%)
    roe_score, roe_desc = _score_roe(metrics.roe, thresholds)
    factors.append(ScoreFactor("ROE", roe_score, 0.25, roe_desc))

    # Asset Growth (15%) - Fama-French CMA factor (negative predictor)
    ag_score, ag_desc = _score_asset_growth(metrics, thresholds)
    factors.append(ScoreFactor("Asset Growth", ag_score, 0.15, ag_desc))

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


def _score_momentum_12_1(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """
    Score 12-1 month momentum (Jegadeesh-Titman).

    Academic evidence: 12-month return minus most recent month captures
    the momentum effect while avoiding short-term reversal.
    This is THE strongest momentum signal with ~12% annual alpha.
    """
    momentum = metrics.momentum_12_1
    if momentum is None:
        # Fallback to 3-month if 12-1 not available
        if metrics.price_change_3m is not None:
            momentum = metrics.price_change_3m
        else:
            return 0.5, "12-1 month momentum unavailable"

    # Score based on academic thresholds
    if momentum >= thresholds.momentum_12_1_strong:
        score = 0.85
        pct = momentum * 100
        desc = f"Strong 12-1M momentum of {pct:+.1f}%"
    elif momentum >= 0.15:  # 15%
        score = 0.7
        pct = momentum * 100
        desc = f"Solid 12-1M momentum of {pct:+.1f}%"
    elif momentum >= 0.05:  # 5%
        score = 0.6
        pct = momentum * 100
        desc = f"Positive 12-1M momentum of {pct:+.1f}%"
    elif momentum >= thresholds.momentum_12_1_weak:
        score = 0.45
        pct = momentum * 100
        desc = f"Weak 12-1M momentum of {pct:+.1f}%"
    else:
        score = 0.25
        pct = momentum * 100
        desc = f"Negative 12-1M momentum of {pct:.1f}%"

    return round(score, 4), desc


def _score_days_to_cover(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, str]:
    """
    Score Days-to-Cover (DTC) signal.

    Per Hong et al NBER: DTC predicts returns with 1.2%/month alpha.
    High DTC (>10) indicates crowded short - both opportunity AND risk.
    Low DTC (<2) is bullish (little short pressure).
    """
    dtc = metrics.days_to_cover
    if dtc is None:
        return 0.5, "Short interest data unavailable"

    if dtc >= thresholds.dtc_crowded:
        # Crowded short - risky, potential squeeze but also means informed traders are bearish
        score = 0.4  # Slight negative - crowded shorts are risky
        desc = f"Crowded short with DTC of {dtc:.1f} days (squeeze risk)"
    elif dtc >= 5.0:
        score = 0.5  # Neutral - moderate short interest
        desc = f"Moderate short interest with DTC of {dtc:.1f} days"
    elif dtc >= thresholds.dtc_low:
        score = 0.6  # Slightly positive - low short pressure
        desc = f"Low short interest with DTC of {dtc:.1f} days"
    else:
        score = 0.7  # Positive - very low short pressure
        desc = f"Minimal short interest with DTC of {dtc:.1f} days"

    return round(score, 4), desc


def compute_momentum_score(
    metrics: StockMetrics,
    thresholds: ScoringThresholds,
) -> tuple[float, list[ScoreFactor]]:
    """
    Compute momentum score from multi-period price action.

    Academic evidence-based weighting:
    - 12-1 Month Momentum: 50% (Jegadeesh-Titman, strongest signal)
    - Short-term Momentum: 20% (1-month for timing)
    - Days-to-Cover: 15% (Hong et al short interest signal)
    - Volume: 15% (confirmation signal)
    """
    factors: list[ScoreFactor] = []

    # 12-1 Month momentum (50%) - PRIMARY MOMENTUM SIGNAL
    mom_12_1_score, mom_12_1_desc = _score_momentum_12_1(metrics, thresholds)
    factors.append(ScoreFactor("12-1M Momentum", mom_12_1_score, 0.50, mom_12_1_desc))

    # Short-term momentum (20%) - timing signal
    mom_1m_score, mom_1m_desc = _score_momentum(metrics, thresholds)
    factors.append(ScoreFactor("1M Momentum", mom_1m_score, 0.20, mom_1m_desc))

    # Days-to-Cover (15%) - short interest signal
    dtc_score, dtc_desc = _score_days_to_cover(metrics, thresholds)
    factors.append(ScoreFactor("Days-to-Cover", dtc_score, 0.15, dtc_desc))

    # Volume (15%) - confirmation
    vol_score, vol_desc = _score_volume(metrics, thresholds)
    factors.append(ScoreFactor("Volume", vol_score, 0.15, vol_desc))

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


@dataclass
class InstitutionalHolding:
    """
    Institutional holding data for smart money scoring.

    Matches HedgeFundHolding fields from db/models.py.
    """
    fund_name: str
    fund_style: str  # value, growth, quant, activist, macro
    action: str  # new, increased, decreased, sold, hold
    shares_change_pct: float | None
    portfolio_pct: float | None  # Position size in fund portfolio


@dataclass
class InsiderTransaction:
    """
    Insider transaction for cluster detection.

    Data source: Finnhub /stock/insider-transactions (Form 4 filings).
    """
    ticker: str  # Stock ticker
    officer_title: str  # CEO, CFO, COO, Director, etc.
    transaction_type: str  # buy, sell
    shares: int
    transaction_date: datetime
    is_c_suite: bool  # True for CEO, CFO, COO, CTO, etc.


# Top fund reputation weights (higher = more signal strength)
FUND_REPUTATION = {
    "berkshire hathaway": 1.0,  # Buffett's value picks carry most weight
    "bridgewater": 0.9,
    "renaissance": 0.85,
    "pershing square": 0.8,
    "soros": 0.8,
    "appaloosa": 0.75,
    "elliott": 0.75,
    "third point": 0.7,
    "baupost": 0.7,
    "viking": 0.65,
    "tiger global": 0.65,
    "citadel": 0.6,
    "de shaw": 0.6,
    "coatue": 0.55,
    "lone pine": 0.55,
}


def _get_fund_reputation(fund_name: str) -> float:
    """Get reputation weight for a fund (0.3-1.0 scale)."""
    name_lower = fund_name.lower()
    for known_fund, weight in FUND_REPUTATION.items():
        if known_fund in name_lower:
            return weight
    return 0.4  # Default for unknown funds


def _score_13f_holdings(
    holdings: list[InstitutionalHolding],
) -> tuple[float, str]:
    """
    Score institutional 13F activity for a ticker.

    Scoring logic:
    - New positions from reputable funds = strong bullish
    - Increased positions = moderate bullish
    - Decreased positions = moderate bearish
    - Sold positions = strong bearish
    - Weight by fund reputation and position size
    """
    if not holdings:
        return 0.5, "No institutional 13F activity"

    # Calculate weighted bullish/bearish signals
    bullish_score = 0.0
    bearish_score = 0.0
    total_weight = 0.0

    actions_summary = {"new": 0, "increased": 0, "decreased": 0, "sold": 0, "hold": 0}

    for h in holdings:
        reputation = _get_fund_reputation(h.fund_name)

        # Weight by change magnitude if available
        change_weight = 1.0
        if h.shares_change_pct is not None:
            # Larger changes = stronger signal
            change_weight = min(2.0, 1.0 + abs(h.shares_change_pct) / 50)

        signal_weight = reputation * change_weight
        total_weight += signal_weight

        if h.action == "new":
            bullish_score += signal_weight * 1.0  # New position = full bullish
            actions_summary["new"] += 1
        elif h.action == "increased":
            bullish_score += signal_weight * 0.7  # Increase = moderate bullish
            actions_summary["increased"] += 1
        elif h.action == "decreased":
            bearish_score += signal_weight * 0.7  # Decrease = moderate bearish
            actions_summary["decreased"] += 1
        elif h.action == "sold":
            bearish_score += signal_weight * 1.0  # Sold = full bearish
            actions_summary["sold"] += 1
        else:
            actions_summary["hold"] += 1

    if total_weight == 0:
        return 0.5, "No actionable 13F signals"

    # Net score: bullish - bearish, normalized
    net_signal = (bullish_score - bearish_score) / total_weight

    # Map to 0-1 scale (net_signal is roughly -1 to +1)
    score = 0.5 + (net_signal * 0.4)  # Range: 0.1 to 0.9
    score = max(0.1, min(0.9, score))

    # Build description
    parts = []
    if actions_summary["new"] > 0:
        parts.append(f"{actions_summary['new']} new position(s)")
    if actions_summary["increased"] > 0:
        parts.append(f"{actions_summary['increased']} increased")
    if actions_summary["decreased"] > 0:
        parts.append(f"{actions_summary['decreased']} decreased")
    if actions_summary["sold"] > 0:
        parts.append(f"{actions_summary['sold']} sold")

    if net_signal > 0.3:
        direction = "Strong institutional buying"
    elif net_signal > 0.1:
        direction = "Net institutional buying"
    elif net_signal < -0.3:
        direction = "Strong institutional selling"
    elif net_signal < -0.1:
        direction = "Net institutional selling"
    else:
        direction = "Mixed institutional activity"

    desc = f"{direction}: {', '.join(parts)}" if parts else direction

    return round(score, 4), desc


def _score_insider_cluster(
    transactions: list[InsiderTransaction],
) -> tuple[float, str]:
    """
    Score insider cluster buys.

    Per academic research (2IQ Research):
    - Cluster buy = 3+ C-suite insiders buying within 30-60 days
    - Single insider buy = weak signal (common for compensation)
    - Cluster buy = ~7.8% annual alpha

    NOTE: This requires Form 4 data which is a current DATA GAP.
    """
    if not transactions:
        return 0.5, "No insider data (Form 4 adapter needed)"

    # Filter to C-suite buys only
    c_suite_buys = [
        t for t in transactions
        if t.is_c_suite and t.transaction_type == "buy"
    ]

    if len(c_suite_buys) >= 3:
        # Cluster buy detected!
        score = 0.85
        desc = f"Insider cluster: {len(c_suite_buys)} C-suite buys in 60 days"
    elif len(c_suite_buys) == 2:
        score = 0.65
        desc = f"Moderate insider buying: {len(c_suite_buys)} C-suite buys"
    elif len(c_suite_buys) == 1:
        score = 0.55
        desc = "Single C-suite insider buy"
    else:
        # Check for any buys
        any_buys = [t for t in transactions if t.transaction_type == "buy"]
        if any_buys:
            score = 0.52
            desc = f"{len(any_buys)} non-C-suite insider buy(s)"
        else:
            score = 0.45
            desc = "No recent insider buying"

    return round(score, 4), desc


def compute_smart_money_score(
    ticker: str,
    institutional_holdings: list[InstitutionalHolding] | None = None,
    insider_transactions: list[InsiderTransaction] | None = None,
) -> tuple[float, list[ScoreFactor]]:
    """
    Compute smart money score from 13F institutional holdings and insider activity.

    Components:
    - Insider cluster buys (60%): 3+ C-suite buying in 30-60 days is strongest signal
      NOTE: Requires Form 4 adapter (DATA GAP - not yet implemented)
    - 13F ownership changes (40%): Quarter-over-quarter changes from top funds

    Academic evidence:
    - Insider clusters: ~7.8% annual alpha (2IQ Research)
    - 13F ownership changes: Predictive when action (not level) is tracked
    """
    factors: list[ScoreFactor] = []

    # Insider cluster signal (60% weight)
    # NOTE: Form 4 data is a current gap - this will return neutral until implemented
    insider_score, insider_desc = _score_insider_cluster(insider_transactions or [])
    factors.append(ScoreFactor("Insider Activity", insider_score, 0.6, insider_desc))

    # 13F ownership changes (40% weight)
    inst_score, inst_desc = _score_13f_holdings(institutional_holdings or [])
    factors.append(ScoreFactor("Institutional 13F", inst_score, 0.4, inst_desc))

    overall = sum(f.score * f.weight for f in factors)
    return round(overall, 4), factors


def holdings_to_institutional(
    holdings: list,  # List of HedgeFundHolding from db
    fund_lookup: dict[str, tuple[str, str]] | None = None,  # fund_id -> (name, style)
) -> list[InstitutionalHolding]:
    """
    Convert HedgeFundHolding objects to InstitutionalHolding for scoring.

    Args:
        holdings: List of HedgeFundHolding from database
        fund_lookup: Optional dict mapping fund_id to (fund_name, fund_style)

    Returns:
        List of InstitutionalHolding for smart money scoring
    """
    result = []
    fund_lookup = fund_lookup or {}

    for h in holdings:
        # Get fund info from lookup or use defaults
        fund_id = getattr(h, "fund_id", "")
        if fund_id in fund_lookup:
            fund_name, fund_style = fund_lookup[fund_id]
        else:
            # Try to get from holding attributes if available
            fund_name = getattr(h, "fund_name", "Unknown Fund")
            fund_style = getattr(h, "fund_style", "unknown")

        result.append(InstitutionalHolding(
            fund_name=fund_name,
            fund_style=fund_style,
            action=getattr(h, "action", "hold"),
            shares_change_pct=getattr(h, "shares_change_pct", None),
            portfolio_pct=getattr(h, "portfolio_pct", None),
        ))

    return result


def observations_to_insider_transactions(
    observations: list,  # List of Observation from FinnhubAdapter
) -> list[InsiderTransaction]:
    """
    Convert Finnhub insider transaction observations to InsiderTransaction for scoring.

    Args:
        observations: List of Observation from FinnhubAdapter.get_insider_transactions()

    Returns:
        List of InsiderTransaction for smart money scoring
    """
    result = []

    for obs in observations:
        data = getattr(obs, "data", obs) if hasattr(obs, "data") else obs

        # Get ticker from observation
        ticker = getattr(obs, "ticker", None) or data.get("ticker", "")

        # Parse transaction date
        txn_date_str = data.get("transaction_date", "")
        try:
            txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d") if txn_date_str else datetime.now()
        except ValueError:
            txn_date = datetime.now()

        result.append(InsiderTransaction(
            ticker=ticker,
            officer_title=data.get("officer_title", "Unknown"),
            transaction_type=data.get("transaction_type", "buy"),
            shares=data.get("shares_change", 0),
            transaction_date=txn_date,
            is_c_suite=data.get("is_c_suite", False),
        ))

    return result


def db_transactions_to_insider(
    db_transactions: list,  # List of InsiderTransaction from db/models.py
) -> list[InsiderTransaction]:
    """
    Convert database InsiderTransaction objects to scoring InsiderTransaction.

    The DB model and scoring dataclass have different structures.
    This converter bridges them for the scoring pipeline.

    Args:
        db_transactions: List of InsiderTransaction from db.get_insider_transactions()

    Returns:
        List of InsiderTransaction for smart money scoring
    """
    result = []

    for txn in db_transactions:
        # Handle both object and dict access
        if hasattr(txn, "transaction_date"):
            txn_date = txn.transaction_date
            if isinstance(txn_date, str):
                try:
                    txn_date = datetime.strptime(txn_date, "%Y-%m-%d")
                except ValueError:
                    txn_date = datetime.now()
            elif txn_date is None:
                txn_date = datetime.now()
            elif hasattr(txn_date, "year"):  # date object
                txn_date = datetime.combine(txn_date, datetime.min.time())
        else:
            txn_date = datetime.now()

        result.append(InsiderTransaction(
            ticker=getattr(txn, "ticker", ""),
            officer_title=getattr(txn, "officer_title", "Unknown"),
            transaction_type=getattr(txn, "transaction_type", "buy"),
            shares=getattr(txn, "shares", 0),
            transaction_date=txn_date,
            is_c_suite=getattr(txn, "is_c_suite", False),
        ))

    return result


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
    import hashlib

    # Sort factors by contribution (score * weight)
    sorted_factors = sorted(factors, key=lambda f: f.score * f.weight, reverse=True)

    # Take top 2-3 positive factors
    top_factors = [f for f in sorted_factors[:3] if f.score >= 0.5]

    if not top_factors:
        return f"{ticker}: Caution advised - weak fundamentals across key metrics."

    # Identify the dominant factor type for thesis framing
    top_factor_name = top_factors[0].name.lower()
    factor_descriptions = [f.description for f in top_factors]

    # Use ticker hash for deterministic but varied selection
    ticker_hash = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)

    # Varied opening phrases based on conviction and dominant factor
    if conviction >= 8:
        openings = [
            f"{ticker} stands out with exceptional fundamentals.",
            f"Strong conviction in {ticker} driven by multiple tailwinds.",
            f"{ticker} shows compelling characteristics across key metrics.",
        ]
    elif conviction >= 6:
        if "momentum" in top_factor_name or "technical" in top_factor_name:
            openings = [
                f"{ticker} shows favorable technical setup.",
                f"Momentum indicators favor {ticker}.",
                f"{ticker} benefits from positive price action.",
            ]
        elif "value" in top_factor_name or "pe" in top_factor_name:
            openings = [
                f"{ticker} trades at attractive valuations.",
                f"Value opportunity in {ticker}.",
                f"{ticker} offers compelling risk/reward at current prices.",
            ]
        elif "growth" in top_factor_name:
            openings = [
                f"{ticker} demonstrates strong growth trajectory.",
                f"Growth metrics favor {ticker}.",
                f"{ticker} positioned for continued expansion.",
            ]
        else:
            openings = [
                f"{ticker} presents a balanced opportunity.",
                f"Multiple factors support {ticker}.",
                f"{ticker} scores well on key fundamentals.",
            ]
    else:
        openings = [
            f"{ticker} warrants consideration despite mixed signals.",
            f"Selective opportunity in {ticker}.",
            f"{ticker} may suit risk-tolerant investors.",
        ]

    opening = openings[ticker_hash % len(openings)]

    # Build the thesis with key supporting factors
    thesis = f"{opening} {factor_descriptions[0]}"
    if len(factor_descriptions) > 1:
        thesis += f". {factor_descriptions[1]}"

    # Add macro context if meaningful
    if macro_description and "Neutral" not in macro_description:
        thesis += f". {macro_description}"

    # Add sector context occasionally
    if ticker_hash % 3 == 0 and sector:
        thesis += f" ({sector} sector)"

    return thesis + "."


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
    institutional_holdings: list[InstitutionalHolding] | None = None,
    insider_transactions: list[InsiderTransaction] | None = None,
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
        institutional_holdings: 13F holdings for smart money scoring (optional)
        insider_transactions: Form 4 transactions for insider cluster detection (optional)

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

    # Smart Money score (13F institutional holdings + insider clusters)
    smart_money_score, smart_money_factors = compute_smart_money_score(
        metrics.ticker,
        institutional_holdings=institutional_holdings,
        insider_transactions=insider_transactions,
    )
    all_factors.extend(smart_money_factors)
    factors_used.append("smart_money")  # Always included, even if neutral

    # Macro adjustment
    macro_adjustment, macro_desc = compute_macro_adjustment(sector, macro, sensitivities)

    # Weighted overall score (0-1)
    # Academic evidence-based weights:
    # Momentum 25%, Quality 25%, Valuation 20%, Growth 15%, Analyst 10%, Smart Money 5%
    base_score = (
        weights.valuation * valuation_score
        + weights.growth * growth_score
        + weights.quality * quality_score
        + weights.momentum * momentum_score
        + weights.analyst * analyst_score
        + weights.smart_money * smart_money_score
    )

    # Apply macro adjustment
    overall_score = max(0.0, min(1.0, base_score + macro_adjustment))

    # Apply score differentiation to spread out clustered scores
    # This uses a power transformation that amplifies differences from 0.5
    # Scores > 0.5 are pushed higher, scores < 0.5 are pushed lower
    centered = overall_score - 0.5
    amplification = 1.8  # Higher = more spread
    differentiated = 0.5 + (math.copysign(abs(centered) ** (1/amplification), centered))
    differentiated = max(0.0, min(1.0, differentiated))

    # Convert to 1-10 conviction using differentiated score
    conviction = max(1, min(10, round(differentiated * 10)))

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

    # Apply timeframe-specific weights (recalculate with appropriate emphasis)
    # This ensures SHORT picks emphasize momentum, LONG picks emphasize quality/valuation
    if timeframe == Timeframe.SHORT:
        tf_weights = TimeframeWeights.for_short()
    elif timeframe == Timeframe.LONG:
        tf_weights = TimeframeWeights.for_long()
    else:
        tf_weights = TimeframeWeights.for_medium()

    # Recalculate base score with timeframe-appropriate weights
    tf_base_score = (
        tf_weights.valuation * valuation_score
        + tf_weights.growth * growth_score
        + tf_weights.quality * quality_score
        + tf_weights.momentum * momentum_score
        + tf_weights.analyst * analyst_score
        + tf_weights.smart_money * smart_money_score
    )

    # Apply macro adjustment to timeframe-weighted score
    tf_overall_score = max(0.0, min(1.0, tf_base_score + macro_adjustment))

    # Apply score differentiation
    tf_centered = tf_overall_score - 0.5
    tf_differentiated = 0.5 + (math.copysign(abs(tf_centered) ** (1/amplification), tf_centered))
    tf_differentiated = max(0.0, min(1.0, tf_differentiated))

    # Recalculate conviction with timeframe-specific score
    conviction = max(1, min(10, round(tf_differentiated * 10)))

    # Update score breakdown with timeframe-weighted score
    score_breakdown = ConvictionScore(
        overall=round(tf_overall_score, 4),
        valuation_score=valuation_score,
        growth_score=growth_score,
        quality_score=quality_score,
        momentum_score=momentum_score,
        macro_adjustment=macro_adjustment,
        factors_used=factors_used,
        factors_missing=factors_missing,
        confidence=round(confidence, 4),
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


# ============================================================================
# Risk Overlay Filters
# ============================================================================


@dataclass(frozen=True)
class RiskOverlayConfig:
    """
    Configuration for risk overlay filters.

    These filters are applied AFTER scoring to ensure portfolio-level risk management:
    - Sector concentration limits (prevent overexposure to single sector)
    - Liquidity requirements (ensure positions can be exited)
    - Short squeeze avoidance (crowded shorts are risky)
    """

    max_picks_per_sector: int = 2  # Max 2 picks from any single sector
    min_daily_liquidity: float = 10_000_000.0  # $10M minimum daily volume
    max_days_to_cover: float = 10.0  # No picks with DTC > 10 (crowded shorts)
    min_conviction: int = 5  # Minimum conviction score to include


@dataclass
class FilteredPick:
    """A pick with filter status information."""

    pick: ScoredPick
    included: bool
    exclusion_reason: str | None = None


def _check_liquidity(
    metrics: StockMetrics,
    min_liquidity: float,
) -> tuple[bool, str | None]:
    """
    Check if stock meets minimum liquidity requirement.

    Args:
        metrics: Stock metrics with volume data
        min_liquidity: Minimum daily dollar volume

    Returns:
        (passes, reason_if_failed)
    """
    if metrics.volume_avg is None or metrics.price is None:
        return False, "Volume data unavailable"

    daily_dollar_volume = metrics.volume_avg * metrics.price
    if daily_dollar_volume < min_liquidity:
        vol_m = daily_dollar_volume / 1_000_000
        return False, f"Insufficient liquidity (${vol_m:.1f}M/day < $10M)"

    return True, None


def _check_dtc(
    metrics: StockMetrics,
    max_dtc: float,
) -> tuple[bool, str | None]:
    """
    Check if stock has acceptable Days-to-Cover.

    High DTC indicates crowded short - risky for longs due to:
    1. Informed traders may know something negative
    2. Short squeezes cause volatility in both directions

    Args:
        metrics: Stock metrics with short interest data
        max_dtc: Maximum acceptable days to cover

    Returns:
        (passes, reason_if_failed)
    """
    dtc = metrics.days_to_cover
    if dtc is None:
        # No data - allow but note
        return True, None

    if dtc > max_dtc:
        return False, f"Crowded short (DTC {dtc:.1f} > {max_dtc} days)"

    return True, None


def apply_risk_overlay(
    picks: list[ScoredPick],
    metrics_by_ticker: dict[str, StockMetrics],
    config: RiskOverlayConfig | None = None,
) -> tuple[list[ScoredPick], list[FilteredPick]]:
    """
    Apply risk overlay filters to scored picks.

    Filters applied in order:
    1. Minimum conviction filter
    2. Liquidity filter ($10M/day minimum)
    3. DTC filter (no crowded shorts with DTC > 10)
    4. Sector concentration limit (max 2 per sector)

    Args:
        picks: List of scored picks (already sorted by conviction)
        metrics_by_ticker: Dict mapping ticker to StockMetrics
        config: Risk overlay configuration

    Returns:
        (filtered_picks, all_picks_with_status)
    """
    config = config or RiskOverlayConfig()

    all_filtered: list[FilteredPick] = []
    included: list[ScoredPick] = []
    sector_counts: dict[str, int] = {}

    for pick in picks:
        exclusion_reason: str | None = None
        metrics = metrics_by_ticker.get(pick.ticker)

        # 1. Conviction filter
        if pick.conviction < config.min_conviction:
            exclusion_reason = f"Low conviction ({pick.conviction} < {config.min_conviction})"

        # 2. Liquidity filter
        elif metrics is not None:
            passes_liquidity, liquidity_reason = _check_liquidity(
                metrics, config.min_daily_liquidity
            )
            if not passes_liquidity:
                exclusion_reason = liquidity_reason

        # 3. DTC filter (crowded shorts)
        if exclusion_reason is None and metrics is not None:
            passes_dtc, dtc_reason = _check_dtc(metrics, config.max_days_to_cover)
            if not passes_dtc:
                exclusion_reason = dtc_reason

        # 4. Sector concentration limit
        if exclusion_reason is None:
            sector = pick.sector.lower()
            current_count = sector_counts.get(sector, 0)
            if current_count >= config.max_picks_per_sector:
                exclusion_reason = f"Sector limit ({config.max_picks_per_sector} {sector} picks already)"
            else:
                sector_counts[sector] = current_count + 1

        # Record result
        is_included = exclusion_reason is None
        all_filtered.append(FilteredPick(
            pick=pick,
            included=is_included,
            exclusion_reason=exclusion_reason,
        ))

        if is_included:
            included.append(pick)

    return included, all_filtered


def apply_risk_overlay_by_timeframe(
    picks: list[ScoredPick],
    metrics_by_ticker: dict[str, StockMetrics],
    config: RiskOverlayConfig | None = None,
    picks_per_timeframe: tuple[int, int] = (3, 7),
) -> dict[Timeframe, list[ScoredPick]]:
    """
    Apply risk overlay and return picks grouped by timeframe.

    Per requirements: 3-7 picks per timeframe after filtering.

    Args:
        picks: All scored picks
        metrics_by_ticker: Metrics for filtering
        config: Risk overlay config
        picks_per_timeframe: (min, max) picks per timeframe

    Returns:
        Dict mapping Timeframe to filtered picks list
    """
    config = config or RiskOverlayConfig()
    min_picks, max_picks = picks_per_timeframe

    # Group by timeframe first
    by_timeframe: dict[Timeframe, list[ScoredPick]] = {
        Timeframe.SHORT: [],
        Timeframe.MEDIUM: [],
        Timeframe.LONG: [],
    }

    for pick in picks:
        by_timeframe[pick.timeframe].append(pick)

    # Apply filters to each timeframe independently
    result: dict[Timeframe, list[ScoredPick]] = {}

    for timeframe, tf_picks in by_timeframe.items():
        # Sort by conviction within timeframe
        tf_picks_sorted = sorted(
            tf_picks,
            key=lambda p: (p.conviction, p.score_breakdown.confidence),
            reverse=True,
        )

        # Apply risk overlay
        filtered, _ = apply_risk_overlay(tf_picks_sorted, metrics_by_ticker, config)

        # Limit to max picks per timeframe
        result[timeframe] = filtered[:max_picks]

    return result


# ============================================================================
# Output Formatting (Signal Attribution)
# ============================================================================


@dataclass
class SignalAttribution:
    """A signal that contributed to the pick's qualification."""

    signal_name: str
    signal_value: str
    contribution: str  # e.g., "Strong", "Moderate", "Weak"


@dataclass
class PickSummary:
    """
    Formatted pick summary with signal attribution and key risk.

    This is the output format for institutional-grade picks:
    - WHY it qualified (top 3 signals)
    - KEY risk (single most important risk)
    """

    ticker: str
    conviction: int
    timeframe: Timeframe
    sector: str

    # Why it qualified
    thesis: str
    top_signals: list[SignalAttribution]

    # Key risk (single most important)
    key_risk: str

    # Score breakdown for transparency
    valuation_score: float
    growth_score: float
    quality_score: float
    momentum_score: float


def _get_signal_contribution(score: float) -> str:
    """Map score to contribution level."""
    if score >= 0.7:
        return "Strong"
    elif score >= 0.55:
        return "Moderate"
    elif score >= 0.4:
        return "Neutral"
    else:
        return "Weak"


def format_pick_with_attribution(
    pick: ScoredPick,
    all_factors: list[ScoreFactor] | None = None,
) -> PickSummary:
    """
    Format a scored pick with explicit signal attribution.

    Shows WHY the pick qualified by listing top contributing signals.
    Shows KEY risk (single most important risk factor).
    """
    breakdown = pick.score_breakdown

    # Build signal attributions from score breakdown
    signals: list[SignalAttribution] = []

    # Momentum signal
    if breakdown.momentum_score >= 0.5:
        signals.append(SignalAttribution(
            signal_name="Momentum",
            signal_value=f"{breakdown.momentum_score:.0%}",
            contribution=_get_signal_contribution(breakdown.momentum_score),
        ))

    # Quality signal
    if breakdown.quality_score >= 0.5:
        signals.append(SignalAttribution(
            signal_name="Quality",
            signal_value=f"{breakdown.quality_score:.0%}",
            contribution=_get_signal_contribution(breakdown.quality_score),
        ))

    # Valuation signal
    if breakdown.valuation_score >= 0.5:
        signals.append(SignalAttribution(
            signal_name="Valuation",
            signal_value=f"{breakdown.valuation_score:.0%}",
            contribution=_get_signal_contribution(breakdown.valuation_score),
        ))

    # Growth signal
    if breakdown.growth_score >= 0.5:
        signals.append(SignalAttribution(
            signal_name="Growth",
            signal_value=f"{breakdown.growth_score:.0%}",
            contribution=_get_signal_contribution(breakdown.growth_score),
        ))

    # Sort by score and take top 3
    signals.sort(key=lambda s: float(s.signal_value.rstrip("%")) / 100, reverse=True)
    top_signals = signals[:3]

    # If no strong signals, note that
    if not top_signals:
        top_signals = [SignalAttribution(
            signal_name="Mixed",
            signal_value="Balanced",
            contribution="Neutral",
        )]

    # Key risk: take the first risk or generate one
    key_risk = pick.risks[0] if pick.risks else "No major risks identified"

    return PickSummary(
        ticker=pick.ticker,
        conviction=pick.conviction,
        timeframe=pick.timeframe,
        sector=pick.sector,
        thesis=pick.thesis,
        top_signals=top_signals,
        key_risk=key_risk,
        valuation_score=breakdown.valuation_score,
        growth_score=breakdown.growth_score,
        quality_score=breakdown.quality_score,
        momentum_score=breakdown.momentum_score,
    )


@dataclass
class TimeframeSummary:
    """Summary of picks for a single timeframe."""

    timeframe: Timeframe
    timeframe_label: str
    picks: list[PickSummary]
    pick_count: int
    avg_conviction: float
    sectors: list[str]


def generate_timeframe_summary(
    picks_by_timeframe: dict[Timeframe, list[ScoredPick]],
) -> list[TimeframeSummary]:
    """
    Generate formatted summaries for each timeframe.

    Returns 3-7 picks per timeframe with signal attribution.
    """
    labels = {
        Timeframe.SHORT: "Short-Term (Days to Weeks)",
        Timeframe.MEDIUM: "Medium-Term (Weeks to Months)",
        Timeframe.LONG: "Long-Term (Months to Years)",
    }

    summaries: list[TimeframeSummary] = []

    for tf in [Timeframe.SHORT, Timeframe.MEDIUM, Timeframe.LONG]:
        picks = picks_by_timeframe.get(tf, [])

        # Format each pick with attribution
        formatted = [format_pick_with_attribution(p) for p in picks]

        # Calculate aggregate stats
        avg_conviction = (
            sum(p.conviction for p in formatted) / len(formatted)
            if formatted else 0.0
        )
        sectors = list(set(p.sector for p in formatted))

        summaries.append(TimeframeSummary(
            timeframe=tf,
            timeframe_label=labels[tf],
            picks=formatted,
            pick_count=len(formatted),
            avg_conviction=round(avg_conviction, 1),
            sectors=sectors,
        ))

    return summaries


def picks_to_display_dict(summaries: list[TimeframeSummary]) -> dict:
    """
    Convert timeframe summaries to frontend-ready dict.

    Includes signal attribution and key risks for each pick.
    """
    result = {}

    for summary in summaries:
        tf_key = summary.timeframe.value
        result[tf_key] = {
            "label": summary.timeframe_label,
            "pickCount": summary.pick_count,
            "avgConviction": summary.avg_conviction,
            "sectors": summary.sectors,
            "picks": [
                {
                    "ticker": p.ticker,
                    "conviction": p.conviction,
                    "sector": p.sector,
                    "thesis": p.thesis,
                    "keyRisk": p.key_risk,
                    "signals": [
                        {
                            "name": s.signal_name,
                            "value": s.signal_value,
                            "contribution": s.contribution,
                        }
                        for s in p.top_signals
                    ],
                    "scores": {
                        "valuation": round(p.valuation_score, 2),
                        "growth": round(p.growth_score, 2),
                        "quality": round(p.quality_score, 2),
                        "momentum": round(p.momentum_score, 2),
                    },
                }
                for p in summary.picks
            ],
        }

    return result
