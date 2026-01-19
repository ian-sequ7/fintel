"""
Quality Factor Module.

Implements academic quality factors:
- Novy-Marx Gross Profitability (strongest quality predictor)
- Return on Equity (ROE)
- Debt-to-Equity ratio (leverage)
- Margin Stability (3-year standard deviation)

All scores returned on 0-100 scale.
"""

from dataclasses import dataclass
from typing import NamedTuple
import math


class QualityComponent(NamedTuple):
    """Individual quality factor component."""
    name: str
    score: float  # 0-100
    weight: float
    raw_value: float | None
    description: str


@dataclass(frozen=True)
class QualityFactorResult:
    """Result of quality factor computation."""
    score: float  # 0-100 composite score
    components: list[QualityComponent]
    data_completeness: float  # 0-1, fraction of data available

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def compute_gross_profitability(
    revenue: float | None,
    cogs: float | None,
    total_assets: float | None,
) -> tuple[float, str]:
    """
    Novy-Marx Gross Profitability = (Revenue - COGS) / Total Assets.

    This is THE strongest quality factor per academic research.
    Higher values indicate more efficient profit generation per unit of assets.

    Thresholds (academic evidence):
    - > 33%: Strong (top quartile)
    - 20-33%: Good
    - 10-20%: Modest
    - < 10%: Weak

    Args:
        revenue: Total revenue
        cogs: Cost of goods sold
        total_assets: Total assets

    Returns:
        (score 0-100, description)
    """
    if revenue is None or total_assets is None or total_assets <= 0:
        return 50.0, "Gross profitability unavailable"

    # If COGS not available, estimate from revenue (conservative)
    if cogs is None:
        # Assume 60% COGS as conservative estimate
        gross_profit = revenue * 0.4
    else:
        gross_profit = revenue - cogs

    gp_ratio = gross_profit / total_assets

    # Score mapping (higher GP = higher score)
    if gp_ratio >= 0.40:
        score = 90.0 + min(10, (gp_ratio - 0.40) * 100)  # 90-100
        desc = f"Excellent gross profitability of {gp_ratio:.1%}"
    elif gp_ratio >= 0.33:
        score = 75.0 + (gp_ratio - 0.33) / 0.07 * 15  # 75-90
        desc = f"Strong gross profitability of {gp_ratio:.1%}"
    elif gp_ratio >= 0.20:
        score = 55.0 + (gp_ratio - 0.20) / 0.13 * 20  # 55-75
        desc = f"Good gross profitability of {gp_ratio:.1%}"
    elif gp_ratio >= 0.10:
        score = 35.0 + (gp_ratio - 0.10) / 0.10 * 20  # 35-55
        desc = f"Modest gross profitability of {gp_ratio:.1%}"
    elif gp_ratio >= 0:
        score = 15.0 + gp_ratio / 0.10 * 20  # 15-35
        desc = f"Low gross profitability of {gp_ratio:.1%}"
    else:
        score = max(0, 15 + gp_ratio * 50)  # 0-15 for negative
        desc = f"Negative gross profitability of {gp_ratio:.1%}"

    return _clamp(score), desc


def _compute_roe_score(roe: float | None) -> tuple[float, str]:
    """
    Score Return on Equity.

    Thresholds:
    - > 20%: Excellent
    - 15-20%: Strong
    - 10-15%: Good
    - 5-10%: Modest
    - < 5%: Weak
    """
    if roe is None:
        return 50.0, "ROE unavailable"

    if roe >= 0.25:
        score = 90.0 + min(10, (roe - 0.25) * 100)
        desc = f"Exceptional ROE of {roe:.1%}"
    elif roe >= 0.20:
        score = 75.0 + (roe - 0.20) / 0.05 * 15
        desc = f"Excellent ROE of {roe:.1%}"
    elif roe >= 0.15:
        score = 60.0 + (roe - 0.15) / 0.05 * 15
        desc = f"Strong ROE of {roe:.1%}"
    elif roe >= 0.10:
        score = 45.0 + (roe - 0.10) / 0.05 * 15
        desc = f"Good ROE of {roe:.1%}"
    elif roe >= 0.05:
        score = 30.0 + (roe - 0.05) / 0.05 * 15
        desc = f"Modest ROE of {roe:.1%}"
    elif roe >= 0:
        score = 15.0 + roe / 0.05 * 15
        desc = f"Low ROE of {roe:.1%}"
    else:
        score = max(0, 15 + roe * 50)
        desc = f"Negative ROE of {roe:.1%}"

    return _clamp(score), desc


def _compute_debt_equity_score(debt_equity: float | None) -> tuple[float, str]:
    """
    Score Debt-to-Equity ratio.

    Lower leverage is generally better for quality.
    Thresholds:
    - < 0.3: Very low leverage (excellent)
    - 0.3-0.6: Low leverage (good)
    - 0.6-1.0: Moderate leverage
    - 1.0-2.0: High leverage (caution)
    - > 2.0: Very high leverage (risk)
    """
    if debt_equity is None:
        return 50.0, "Debt/Equity unavailable"

    if debt_equity < 0:
        # Negative equity (concerning)
        return 20.0, f"Negative equity (D/E: {debt_equity:.2f})"

    if debt_equity <= 0.3:
        score = 85.0 + (0.3 - debt_equity) / 0.3 * 15
        desc = f"Very low leverage (D/E: {debt_equity:.2f})"
    elif debt_equity <= 0.6:
        score = 70.0 + (0.6 - debt_equity) / 0.3 * 15
        desc = f"Low leverage (D/E: {debt_equity:.2f})"
    elif debt_equity <= 1.0:
        score = 50.0 + (1.0 - debt_equity) / 0.4 * 20
        desc = f"Moderate leverage (D/E: {debt_equity:.2f})"
    elif debt_equity <= 2.0:
        score = 25.0 + (2.0 - debt_equity) / 1.0 * 25
        desc = f"High leverage (D/E: {debt_equity:.2f})"
    else:
        score = max(5, 25 - (debt_equity - 2.0) * 10)
        desc = f"Very high leverage (D/E: {debt_equity:.2f})"

    return _clamp(score), desc


def _compute_margin_stability_score(
    margin_history: list[float] | None,
) -> tuple[float, str]:
    """
    Score margin stability (lower std dev = more stable = better).

    Uses standard deviation of profit margins over available history.
    Stable margins indicate consistent business quality.
    """
    if margin_history is None or len(margin_history) < 2:
        return 50.0, "Margin history unavailable"

    mean_margin = sum(margin_history) / len(margin_history)
    variance = sum((m - mean_margin) ** 2 for m in margin_history) / len(margin_history)
    std_dev = math.sqrt(variance)

    # Coefficient of variation for relative stability
    if mean_margin > 0:
        cv = std_dev / mean_margin
    else:
        cv = std_dev  # Use absolute std if mean is non-positive

    # Lower CV = more stable = higher score
    if cv <= 0.05:
        score = 90.0
        desc = f"Very stable margins (CV: {cv:.2f})"
    elif cv <= 0.10:
        score = 75.0 + (0.10 - cv) / 0.05 * 15
        desc = f"Stable margins (CV: {cv:.2f})"
    elif cv <= 0.20:
        score = 55.0 + (0.20 - cv) / 0.10 * 20
        desc = f"Moderately stable margins (CV: {cv:.2f})"
    elif cv <= 0.35:
        score = 35.0 + (0.35 - cv) / 0.15 * 20
        desc = f"Somewhat volatile margins (CV: {cv:.2f})"
    else:
        score = max(10, 35 - (cv - 0.35) * 50)
        desc = f"Volatile margins (CV: {cv:.2f})"

    return _clamp(score), desc


def compute_quality_score(
    gross_profit_margin: float | None = None,
    revenue: float | None = None,
    cogs: float | None = None,
    total_assets: float | None = None,
    roe: float | None = None,
    debt_equity: float | None = None,
    margin_history: list[float] | None = None,
) -> QualityFactorResult:
    """
    Compute composite quality factor score.

    Weights (per PLAN-scoring.md):
    - Gross Profitability (Novy-Marx): 35% (12% of total)
    - ROE: 25% (8% of total)
    - Debt/Equity: 20% (5% of total)
    - Margin Stability: 20% (5% of total)

    Args:
        gross_profit_margin: Pre-computed GP/Assets if available
        revenue: Total revenue (for computing GP)
        cogs: Cost of goods sold (for computing GP)
        total_assets: Total assets
        roe: Return on equity
        debt_equity: Debt-to-equity ratio
        margin_history: List of historical profit margins (for stability)

    Returns:
        QualityFactorResult with score 0-100 and component breakdown
    """
    components: list[QualityComponent] = []
    data_points = 0
    total_points = 4

    # 1. Gross Profitability (35% weight)
    if gross_profit_margin is not None:
        # Use pre-computed value
        if gross_profit_margin >= 0.33:
            gp_score = 75.0 + (gross_profit_margin - 0.33) / 0.17 * 25
            gp_desc = f"Strong gross profitability of {gross_profit_margin:.1%}"
        elif gross_profit_margin >= 0.20:
            gp_score = 55.0 + (gross_profit_margin - 0.20) / 0.13 * 20
            gp_desc = f"Good gross profitability of {gross_profit_margin:.1%}"
        else:
            gp_score = max(20, gross_profit_margin / 0.20 * 55)
            gp_desc = f"Modest gross profitability of {gross_profit_margin:.1%}"
        gp_score = _clamp(gp_score)
        data_points += 1
    else:
        gp_score, gp_desc = compute_gross_profitability(revenue, cogs, total_assets)
        if "unavailable" not in gp_desc.lower():
            data_points += 1

    components.append(QualityComponent(
        name="Gross Profitability",
        score=gp_score,
        weight=0.35,
        raw_value=gross_profit_margin,
        description=gp_desc,
    ))

    # 2. ROE (25% weight)
    roe_score, roe_desc = _compute_roe_score(roe)
    if roe is not None:
        data_points += 1
    components.append(QualityComponent(
        name="ROE",
        score=roe_score,
        weight=0.25,
        raw_value=roe,
        description=roe_desc,
    ))

    # 3. Debt/Equity (20% weight)
    de_score, de_desc = _compute_debt_equity_score(debt_equity)
    if debt_equity is not None:
        data_points += 1
    components.append(QualityComponent(
        name="Debt/Equity",
        score=de_score,
        weight=0.20,
        raw_value=debt_equity,
        description=de_desc,
    ))

    # 4. Margin Stability (20% weight)
    ms_score, ms_desc = _compute_margin_stability_score(margin_history)
    if margin_history and len(margin_history) >= 2:
        data_points += 1
    components.append(QualityComponent(
        name="Margin Stability",
        score=ms_score,
        weight=0.20,
        raw_value=None,  # Complex calculation
        description=ms_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return QualityFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
    )
