"""
Catalyst Awareness Factor Module.

Implements catalyst-based signals:
- Earnings Date Proximity (stocks often move around earnings)
- Sector Rotation (leading/lagging sectors based on regime)

These factors help time entries and capture event-driven alpha.

All scores returned on 0-100 scale.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import NamedTuple


class MarketRegime(str, Enum):
    """Market regime classification."""
    BULL = "bull"        # SPY > 200 SMA, VIX < 20
    BEAR = "bear"        # SPY < 200 SMA, VIX > 25
    SIDEWAYS = "sideways"  # Neither bull nor bear
    HIGH_VOL = "high_vol"  # VIX > 30 (defensive mode)


class CatalystComponent(NamedTuple):
    """Individual catalyst factor component."""
    name: str
    score: float  # 0-100
    weight: float
    trigger_date: date | None
    description: str


@dataclass(frozen=True)
class CatalystFactorResult:
    """Result of catalyst factor computation."""
    score: float  # 0-100 composite score
    components: list[CatalystComponent]
    data_completeness: float  # 0-1, fraction of data available
    has_near_term_catalyst: bool  # Earnings within 2 weeks

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


# Sector performance expectations by regime
SECTOR_REGIME_SCORES = {
    # Bull market: Growth and cyclicals lead
    MarketRegime.BULL: {
        "technology": 85,
        "consumer discretionary": 80,
        "communication services": 75,
        "financials": 75,
        "industrials": 70,
        "materials": 65,
        "real estate": 60,
        "healthcare": 55,
        "consumer staples": 45,
        "utilities": 40,
        "energy": 50,
    },
    # Bear market: Defensives and value lead
    MarketRegime.BEAR: {
        "utilities": 85,
        "consumer staples": 80,
        "healthcare": 75,
        "real estate": 60,
        "communication services": 50,
        "financials": 45,
        "industrials": 40,
        "materials": 40,
        "technology": 35,
        "consumer discretionary": 30,
        "energy": 55,  # Can be counter-cyclical
    },
    # Sideways: Quality and dividends
    MarketRegime.SIDEWAYS: {
        "healthcare": 70,
        "consumer staples": 70,
        "utilities": 65,
        "financials": 60,
        "industrials": 55,
        "technology": 55,
        "communication services": 55,
        "materials": 50,
        "real estate": 50,
        "consumer discretionary": 50,
        "energy": 50,
    },
    # High volatility: Maximum defensiveness
    MarketRegime.HIGH_VOL: {
        "utilities": 90,
        "consumer staples": 85,
        "healthcare": 80,
        "real estate": 55,
        "communication services": 45,
        "financials": 40,
        "industrials": 35,
        "materials": 35,
        "technology": 30,
        "consumer discretionary": 25,
        "energy": 45,
    },
}


def compute_earnings_proximity_score(
    next_earnings_date: date | str | None,
    today: date | None = None,
) -> tuple[float, date | None, str]:
    """
    Score based on proximity to next earnings date.

    Stocks often experience significant moves around earnings.
    For SHORT-term picks, being close to earnings is a catalyst.
    For LONG-term picks, this matters less.

    Scoring (for SHORT-term context):
    - Within 2 weeks: High score (catalyst imminent)
    - 2-4 weeks: Moderate score
    - 4-8 weeks: Lower score
    - > 8 weeks or unknown: Neutral

    Note: This factor should be weighted more heavily for SHORT timeframe.

    Args:
        next_earnings_date: Date of next earnings announcement
        today: Reference date (defaults to today)

    Returns:
        (score 0-100, earnings_date, description)
    """
    if today is None:
        today = date.today()

    if next_earnings_date is None:
        return 50.0, None, "Earnings date unknown"

    # Parse date if string
    if isinstance(next_earnings_date, str):
        try:
            next_earnings_date = date.fromisoformat(next_earnings_date)
        except (ValueError, TypeError):
            return 50.0, None, "Invalid earnings date format"

    days_until = (next_earnings_date - today).days

    if days_until < 0:
        # Earnings already passed, might be stale data
        return 50.0, next_earnings_date, "Earnings date may be stale"

    if days_until <= 7:
        score = 90.0 + min(10, (7 - days_until))
        desc = f"Earnings in {days_until} days - HIGH CATALYST"
    elif days_until <= 14:
        score = 75.0 + (14 - days_until) / 7 * 15
        desc = f"Earnings in {days_until} days - near-term catalyst"
    elif days_until <= 28:
        score = 55.0 + (28 - days_until) / 14 * 20
        desc = f"Earnings in ~{days_until // 7} weeks"
    elif days_until <= 56:
        score = 45.0 + (56 - days_until) / 28 * 10
        desc = f"Earnings in ~{days_until // 7} weeks"
    else:
        score = 45.0
        desc = f"Earnings in {days_until // 7}+ weeks"

    return _clamp(score), next_earnings_date, desc


def compute_sector_rotation_score(
    sector: str,
    sector_performance: dict[str, float] | None,
    regime: MarketRegime,
) -> tuple[float, str]:
    """
    Score sector based on rotation thesis and recent performance.

    Combines:
    1. Expected sector performance for current regime
    2. Recent sector momentum (if provided)

    Args:
        sector: Stock's GICS sector name
        sector_performance: Dict of sector -> 1-month return (optional)
        regime: Current market regime

    Returns:
        (score 0-100, description)
    """
    sector_lower = sector.lower()

    # Get expected score for this sector in current regime
    regime_scores = SECTOR_REGIME_SCORES.get(regime, SECTOR_REGIME_SCORES[MarketRegime.SIDEWAYS])

    # Find matching sector (fuzzy match)
    expected_score = 50.0  # Default
    matched_sector = None
    for known_sector, score in regime_scores.items():
        if known_sector in sector_lower or sector_lower in known_sector:
            expected_score = score
            matched_sector = known_sector
            break

    # Adjust based on recent performance if available
    if sector_performance and matched_sector:
        sector_return = sector_performance.get(matched_sector)
        if sector_return is not None:
            # Performance adjustment: +/-15 based on relative strength
            avg_return = sum(sector_performance.values()) / len(sector_performance)
            relative_return = sector_return - avg_return

            # Scale: +5% relative return = +15 points, -5% = -15 points
            performance_adj = relative_return / 0.05 * 15
            expected_score += _clamp(performance_adj, -15, 15)

    # Generate description
    regime_name = regime.value.replace("_", " ").title()

    if expected_score >= 75:
        desc = f"Favored sector in {regime_name} market"
    elif expected_score >= 55:
        desc = f"Neutral sector for {regime_name} conditions"
    else:
        desc = f"Less favored in {regime_name} market"

    return _clamp(expected_score), desc


def compute_catalyst_score(
    sector: str,
    regime: MarketRegime = MarketRegime.SIDEWAYS,
    next_earnings_date: date | str | None = None,
    sector_performance: dict[str, float] | None = None,
    today: date | None = None,
) -> CatalystFactorResult:
    """
    Compute composite catalyst awareness score.

    Weights (per PLAN-scoring.md):
    - Earnings Date Proximity: 50%
    - Sector Rotation: 50%

    Args:
        sector: Stock's sector
        regime: Current market regime
        next_earnings_date: Date of next earnings
        sector_performance: Recent sector returns
        today: Reference date

    Returns:
        CatalystFactorResult with score 0-100 and component breakdown
    """
    components: list[CatalystComponent] = []
    data_points = 0
    total_points = 2
    has_near_term_catalyst = False

    # 1. Earnings Proximity (50% weight)
    earn_score, earn_date, earn_desc = compute_earnings_proximity_score(
        next_earnings_date, today
    )
    if next_earnings_date is not None:
        data_points += 1
        # Check if near-term
        if earn_date:
            ref_date = today or date.today()
            days_until = (earn_date - ref_date).days
            if 0 <= days_until <= 14:
                has_near_term_catalyst = True

    components.append(CatalystComponent(
        name="Earnings Proximity",
        score=earn_score,
        weight=0.50,
        trigger_date=earn_date,
        description=earn_desc,
    ))

    # 2. Sector Rotation (50% weight)
    sector_score, sector_desc = compute_sector_rotation_score(
        sector, sector_performance, regime
    )
    data_points += 1  # Sector is always available

    components.append(CatalystComponent(
        name="Sector Rotation",
        score=sector_score,
        weight=0.50,
        trigger_date=None,
        description=sector_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return CatalystFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
        has_near_term_catalyst=has_near_term_catalyst,
    )
