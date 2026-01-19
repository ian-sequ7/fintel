"""
Enhanced Factor Modules for Stock Scoring.

This package contains modular factor computation functions that implement
academic research-backed signals for stock picking:

- quality: Novy-Marx gross profitability, ROE, leverage, margin stability
- value: Earnings yield, book-to-market, free cash flow yield
- momentum: Jegadeesh-Titman 12-1 month, volume-weighted, earnings revision
- low_volatility: Realized volatility, beta (inverted - lower = better)
- smart_money: Institutional accumulation, insider clusters, congress trades
- catalyst: Earnings proximity, sector rotation

All factor functions return scores on a 0-100 scale for better differentiation.
"""

from .quality import (
    compute_gross_profitability,
    compute_quality_score,
    QualityFactorResult,
)
from .value import (
    compute_earnings_yield,
    compute_fcf_yield,
    compute_value_score,
    ValueFactorResult,
)
from .momentum import (
    compute_price_momentum_12_1,
    compute_volume_weighted_momentum,
    compute_momentum_score,
    MomentumFactorResult,
)
from .low_volatility import (
    compute_realized_volatility,
    compute_beta,
    compute_low_vol_score,
    LowVolFactorResult,
)
from .smart_money import (
    compute_institutional_accumulation,
    compute_insider_cluster_score,
    compute_congress_trade_score,
    compute_smart_money_score,
    SmartMoneyFactorResult,
)
from .catalyst import (
    compute_earnings_proximity_score,
    compute_sector_rotation_score,
    compute_catalyst_score,
    CatalystFactorResult,
)

__all__ = [
    # Quality
    "compute_gross_profitability",
    "compute_quality_score",
    "QualityFactorResult",
    # Value
    "compute_earnings_yield",
    "compute_fcf_yield",
    "compute_value_score",
    "ValueFactorResult",
    # Momentum
    "compute_price_momentum_12_1",
    "compute_volume_weighted_momentum",
    "compute_momentum_score",
    "MomentumFactorResult",
    # Low Volatility
    "compute_realized_volatility",
    "compute_beta",
    "compute_low_vol_score",
    "LowVolFactorResult",
    # Smart Money
    "compute_institutional_accumulation",
    "compute_insider_cluster_score",
    "compute_congress_trade_score",
    "compute_smart_money_score",
    "SmartMoneyFactorResult",
    # Catalyst
    "compute_earnings_proximity_score",
    "compute_sector_rotation_score",
    "compute_catalyst_score",
    "CatalystFactorResult",
]
