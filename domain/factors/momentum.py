"""
Momentum Factor Module.

Implements academic momentum factors:
- Jegadeesh-Titman 12-1 Month Momentum (skip recent month to avoid reversal)
- Volume-Weighted Momentum (high volume moves are more significant)
- Earnings Revision Momentum (analyst estimate changes)

All scores returned on 0-100 scale.
"""

from dataclasses import dataclass
from typing import NamedTuple
import math


class MomentumComponent(NamedTuple):
    """Individual momentum factor component."""
    name: str
    score: float  # 0-100
    weight: float
    raw_value: float | None
    description: str


@dataclass(frozen=True)
class MomentumFactorResult:
    """Result of momentum factor computation."""
    score: float  # 0-100 composite score
    components: list[MomentumComponent]
    data_completeness: float  # 0-1, fraction of data available

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def compute_price_momentum_12_1(prices: list[float]) -> tuple[float, str]:
    """
    Jegadeesh-Titman 12-1 Month Momentum.

    Calculates momentum as the return over months 2-12, SKIPPING the most
    recent month. Academic research shows the most recent month has a
    reversal effect, so excluding it improves signal quality.

    Expected price list: 252 trading days (1 year) of prices, most recent first.
    - prices[0]: today's price
    - prices[21]: ~1 month ago
    - prices[252]: ~12 months ago

    Thresholds (academic evidence):
    - > 30%: Strong positive momentum
    - 10-30%: Positive momentum
    - -10% to 10%: Neutral
    - -30% to -10%: Negative momentum
    - < -30%: Strong negative momentum

    Args:
        prices: List of prices, most recent first. Need at least 252 points.

    Returns:
        (score 0-100, description)
    """
    if prices is None or len(prices) < 252:
        # Fall back to shorter period if available
        if prices and len(prices) >= 63:  # ~3 months
            return _compute_shorter_momentum(prices)
        return 50.0, "Price history insufficient for 12-1 momentum"

    # 12-1 month momentum: return from month 2 to month 12
    # Skip month 1 (days 0-21) to avoid reversal effect
    price_1_month_ago = prices[21]  # ~1 month ago
    price_12_months_ago = prices[251]  # ~12 months ago

    if price_12_months_ago <= 0 or price_1_month_ago <= 0:
        return 50.0, "Invalid prices for momentum calculation"

    # Return from month 12 to month 1 (skipping most recent month)
    momentum_12_1 = (price_1_month_ago - price_12_months_ago) / price_12_months_ago

    return _score_momentum(momentum_12_1, "12-1M")


def _compute_shorter_momentum(prices: list[float]) -> tuple[float, str]:
    """Fallback for shorter price history."""
    if len(prices) >= 63:  # 3 months
        price_now = prices[0]
        price_3m = prices[62]
        if price_3m > 0:
            momentum = (price_now - price_3m) / price_3m
            return _score_momentum(momentum, "3M")
    return 50.0, "Insufficient price history"


def _score_momentum(momentum: float, period: str) -> tuple[float, str]:
    """Score a momentum value."""
    pct = momentum * 100

    if momentum >= 0.50:
        score = 95.0
        desc = f"Exceptional {period} momentum of {pct:+.1f}%"
    elif momentum >= 0.30:
        score = 80.0 + (momentum - 0.30) / 0.20 * 15
        desc = f"Strong {period} momentum of {pct:+.1f}%"
    elif momentum >= 0.15:
        score = 65.0 + (momentum - 0.15) / 0.15 * 15
        desc = f"Solid {period} momentum of {pct:+.1f}%"
    elif momentum >= 0.05:
        score = 55.0 + (momentum - 0.05) / 0.10 * 10
        desc = f"Positive {period} momentum of {pct:+.1f}%"
    elif momentum >= -0.05:
        score = 45.0 + (momentum + 0.05) / 0.10 * 10
        desc = f"Neutral {period} momentum of {pct:+.1f}%"
    elif momentum >= -0.15:
        score = 30.0 + (momentum + 0.15) / 0.10 * 15
        desc = f"Weak {period} momentum of {pct:+.1f}%"
    elif momentum >= -0.30:
        score = 15.0 + (momentum + 0.30) / 0.15 * 15
        desc = f"Negative {period} momentum of {pct:+.1f}%"
    else:
        score = max(5, 15 + (momentum + 0.30) * 30)
        desc = f"Strong negative {period} momentum of {pct:+.1f}%"

    return _clamp(score), desc


def compute_volume_weighted_momentum(
    prices: list[float],
    volumes: list[float],
    window: int = 20,
) -> tuple[float, str]:
    """
    Volume-Weighted Momentum.

    Price moves on high volume are more significant than low volume moves.
    This factor weights daily returns by relative volume to capture
    conviction behind price movements.

    Args:
        prices: List of prices, most recent first
        volumes: List of volumes, corresponding to prices
        window: Lookback window in trading days (default 20 = ~1 month)

    Returns:
        (score 0-100, description)
    """
    if (prices is None or volumes is None or
        len(prices) < window + 1 or len(volumes) < window):
        return 50.0, "Insufficient data for volume-weighted momentum"

    # Calculate average volume for normalization
    avg_volume = sum(volumes[:window]) / window
    if avg_volume <= 0:
        return 50.0, "Invalid volume data"

    # Calculate volume-weighted returns
    weighted_returns = []
    for i in range(window):
        if prices[i + 1] > 0:
            daily_return = (prices[i] - prices[i + 1]) / prices[i + 1]
            volume_weight = volumes[i] / avg_volume
            weighted_returns.append(daily_return * volume_weight)

    if not weighted_returns:
        return 50.0, "Could not calculate volume-weighted momentum"

    # Sum of volume-weighted returns
    vw_momentum = sum(weighted_returns)

    # Score similar to regular momentum but scaled for daily returns
    pct = vw_momentum * 100

    if vw_momentum >= 0.15:
        score = 90.0 + min(10, (vw_momentum - 0.15) * 50)
        desc = f"Strong volume-confirmed momentum of {pct:+.1f}%"
    elif vw_momentum >= 0.08:
        score = 70.0 + (vw_momentum - 0.08) / 0.07 * 20
        desc = f"Solid volume-confirmed momentum of {pct:+.1f}%"
    elif vw_momentum >= 0.03:
        score = 55.0 + (vw_momentum - 0.03) / 0.05 * 15
        desc = f"Positive volume-weighted momentum of {pct:+.1f}%"
    elif vw_momentum >= -0.03:
        score = 45.0 + (vw_momentum + 0.03) / 0.06 * 10
        desc = f"Neutral volume-weighted momentum of {pct:+.1f}%"
    elif vw_momentum >= -0.08:
        score = 30.0 + (vw_momentum + 0.08) / 0.05 * 15
        desc = f"Weak volume-weighted momentum of {pct:+.1f}%"
    else:
        score = max(10, 30 + (vw_momentum + 0.08) * 150)
        desc = f"Negative volume-weighted momentum of {pct:+.1f}%"

    return _clamp(score), desc


def _compute_earnings_revision_score(
    current_estimate: float | None,
    estimate_30d_ago: float | None,
    estimate_90d_ago: float | None,
) -> tuple[float, str]:
    """
    Earnings Revision Momentum.

    Tracks changes in analyst earnings estimates. Upward revisions
    are a strong positive signal; downward revisions are negative.

    Args:
        current_estimate: Current consensus EPS estimate
        estimate_30d_ago: EPS estimate from 30 days ago
        estimate_90d_ago: EPS estimate from 90 days ago

    Returns:
        (score 0-100, description)
    """
    if current_estimate is None:
        return 50.0, "Earnings estimates unavailable"

    # Calculate revision percentages
    revisions = []

    if estimate_30d_ago is not None and estimate_30d_ago != 0:
        rev_30d = (current_estimate - estimate_30d_ago) / abs(estimate_30d_ago)
        revisions.append(("30d", rev_30d, 0.6))  # More weight on recent

    if estimate_90d_ago is not None and estimate_90d_ago != 0:
        rev_90d = (current_estimate - estimate_90d_ago) / abs(estimate_90d_ago)
        revisions.append(("90d", rev_90d, 0.4))  # Less weight on older

    if not revisions:
        return 50.0, "Historical estimates unavailable for revision calculation"

    # Weighted average revision
    total_weight = sum(r[2] for r in revisions)
    weighted_revision = sum(r[1] * r[2] for r in revisions) / total_weight

    pct = weighted_revision * 100

    if weighted_revision >= 0.10:
        score = 90.0 + min(10, (weighted_revision - 0.10) * 50)
        desc = f"Strong upward revisions of {pct:+.1f}%"
    elif weighted_revision >= 0.05:
        score = 75.0 + (weighted_revision - 0.05) / 0.05 * 15
        desc = f"Solid upward revisions of {pct:+.1f}%"
    elif weighted_revision >= 0.02:
        score = 60.0 + (weighted_revision - 0.02) / 0.03 * 15
        desc = f"Modest upward revisions of {pct:+.1f}%"
    elif weighted_revision >= -0.02:
        score = 45.0 + (weighted_revision + 0.02) / 0.04 * 15
        desc = f"Stable estimates ({pct:+.1f}% revision)"
    elif weighted_revision >= -0.05:
        score = 30.0 + (weighted_revision + 0.05) / 0.03 * 15
        desc = f"Slight downward revisions of {pct:+.1f}%"
    elif weighted_revision >= -0.10:
        score = 15.0 + (weighted_revision + 0.10) / 0.05 * 15
        desc = f"Downward revisions of {pct:+.1f}%"
    else:
        score = max(5, 15 + (weighted_revision + 0.10) * 100)
        desc = f"Sharp downward revisions of {pct:+.1f}%"

    return _clamp(score), desc


def compute_momentum_score(
    prices: list[float] | None = None,
    volumes: list[float] | None = None,
    price_change_12m: float | None = None,
    price_change_1m: float | None = None,
    current_estimate: float | None = None,
    estimate_30d_ago: float | None = None,
    estimate_90d_ago: float | None = None,
) -> MomentumFactorResult:
    """
    Compute composite momentum factor score.

    Weights (per PLAN-scoring.md):
    - 12-1 Month Price Momentum: 50%
    - Volume-Weighted Momentum: 25%
    - Earnings Revision Momentum: 25%

    Args:
        prices: Price history (most recent first, need 252 for full calc)
        volumes: Volume history (corresponding to prices)
        price_change_12m: Pre-computed 12-month return (optional shortcut)
        price_change_1m: Pre-computed 1-month return (optional shortcut)
        current_estimate: Current EPS estimate
        estimate_30d_ago: EPS estimate from 30 days ago
        estimate_90d_ago: EPS estimate from 90 days ago

    Returns:
        MomentumFactorResult with score 0-100 and component breakdown
    """
    components: list[MomentumComponent] = []
    data_points = 0
    total_points = 3

    # 1. 12-1 Month Price Momentum (50% weight)
    if prices is not None and len(prices) >= 252:
        pm_score, pm_desc = compute_price_momentum_12_1(prices)
        # Calculate raw 12-1 momentum
        price_1m = prices[21]
        price_12m = prices[251]
        pm_raw = (price_1m - price_12m) / price_12m if price_12m > 0 else None
        data_points += 1
    elif price_change_12m is not None and price_change_1m is not None:
        # Use pre-computed values
        momentum_12_1 = price_change_12m - price_change_1m
        pm_score, pm_desc = _score_momentum(momentum_12_1, "12-1M")
        pm_raw = momentum_12_1
        data_points += 1
    elif prices is not None and len(prices) >= 63:
        pm_score, pm_desc = _compute_shorter_momentum(prices)
        pm_raw = (prices[0] - prices[62]) / prices[62] if prices[62] > 0 else None
        data_points += 0.5  # Partial credit for shorter history
    else:
        pm_score, pm_desc = 50.0, "Price momentum unavailable"
        pm_raw = None

    components.append(MomentumComponent(
        name="12-1M Price Momentum",
        score=pm_score,
        weight=0.50,
        raw_value=pm_raw,
        description=pm_desc,
    ))

    # 2. Volume-Weighted Momentum (25% weight)
    if prices is not None and volumes is not None and len(prices) >= 21:
        vw_score, vw_desc = compute_volume_weighted_momentum(prices, volumes, 20)
        data_points += 1
    else:
        vw_score, vw_desc = 50.0, "Volume data unavailable"

    components.append(MomentumComponent(
        name="Volume-Weighted Momentum",
        score=vw_score,
        weight=0.25,
        raw_value=None,  # Complex calculation
        description=vw_desc,
    ))

    # 3. Earnings Revision Momentum (25% weight)
    er_score, er_desc = _compute_earnings_revision_score(
        current_estimate, estimate_30d_ago, estimate_90d_ago
    )
    if current_estimate is not None and (estimate_30d_ago is not None or estimate_90d_ago is not None):
        data_points += 1

    components.append(MomentumComponent(
        name="Earnings Revision",
        score=er_score,
        weight=0.25,
        raw_value=current_estimate,
        description=er_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return MomentumFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
    )
