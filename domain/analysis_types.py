"""
Analysis types - inputs and outputs for the stock analysis engine.

These are pure data structures used by analysis functions.
Separating types from logic keeps the analysis module focused.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

from pydantic import BaseModel, Field

from .models import Timeframe, Trend, Impact, MacroIndicator


# ============================================================================
# Enums
# ============================================================================

class RiskCategory(str, Enum):
    """Categories of investment risk."""
    VALUATION = "valuation"
    MACRO = "macro"
    SECTOR = "sector"
    COMPANY = "company"
    TECHNICAL = "technical"
    LIQUIDITY = "liquidity"
    REGULATORY = "regulatory"


class StrategyType(str, Enum):
    """Investment strategy types."""
    VALUE = "value"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    QUALITY = "quality"
    DIVIDEND = "dividend"
    BALANCED = "balanced"


# ============================================================================
# Input Types
# ============================================================================

class StockMetrics(BaseModel):
    """
    Quantitative metrics for a stock.

    Input type for analysis functions - aggregates data from adapters.
    """
    model_config = {"frozen": True}

    ticker: str
    price: float = Field(gt=0)
    market_cap: float | None = Field(default=None, ge=0)

    # Valuation metrics
    pe_trailing: float | None = None
    pe_forward: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None
    price_to_sales: float | None = None

    # Growth metrics
    revenue_growth: float | None = None  # YoY percentage
    earnings_growth: float | None = None  # YoY percentage

    # Profitability
    profit_margin: float | None = None
    roe: float | None = None  # Return on equity
    roa: float | None = None  # Return on assets

    # Technical
    price_change_1d: float | None = None
    price_change_1w: float | None = None
    price_change_1m: float | None = None
    price_change_3m: float | None = None
    volume_avg: float | None = None
    volume_current: float | None = None

    # Dividend
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Analyst
    analyst_rating: float | None = Field(default=None, ge=1, le=5)  # 1=strong buy, 5=strong sell
    price_target: float | None = Field(default=None, gt=0)

    @property
    def upside_potential(self) -> float | None:
        """Calculate upside to analyst price target."""
        if self.price_target and self.price:
            return ((self.price_target - self.price) / self.price) * 100
        return None

    @property
    def volume_ratio(self) -> float | None:
        """Current volume vs average (>1 = above average)."""
        if self.volume_current and self.volume_avg and self.volume_avg > 0:
            return self.volume_current / self.volume_avg
        return None


class MacroContext(BaseModel):
    """
    Macroeconomic context for analysis.

    Aggregates macro indicators into a usable context object.
    """
    model_config = {"frozen": True}

    # Key rates
    fed_funds_rate: float | None = None
    treasury_10y: float | None = None
    treasury_2y: float | None = None

    # Economic indicators
    unemployment_rate: float | None = None
    inflation_rate: float | None = None  # CPI YoY
    gdp_growth: float | None = None

    # Sentiment
    consumer_sentiment: float | None = None
    vix: float | None = None  # Volatility index

    # Trends
    rate_trend: Trend = Trend.STABLE
    growth_trend: Trend = Trend.STABLE
    inflation_trend: Trend = Trend.STABLE

    @property
    def yield_curve_spread(self) -> float | None:
        """10Y - 2Y spread (negative = inverted)."""
        if self.treasury_10y is not None and self.treasury_2y is not None:
            return self.treasury_10y - self.treasury_2y
        return None

    @property
    def is_yield_curve_inverted(self) -> bool:
        """Check if yield curve is inverted (recession signal)."""
        spread = self.yield_curve_spread
        return spread is not None and spread < 0

    @property
    def real_rate(self) -> float | None:
        """Real interest rate (fed funds - inflation)."""
        if self.fed_funds_rate is not None and self.inflation_rate is not None:
            return self.fed_funds_rate - self.inflation_rate
        return None


# ============================================================================
# Output Types
# ============================================================================

class ConvictionScore(BaseModel):
    """
    Conviction score output from analysis.

    Breaks down the overall score into component factors.
    """
    model_config = {"frozen": True}

    overall: float = Field(ge=0, le=1, description="Overall conviction 0-1")

    # Component scores (all 0-1)
    valuation_score: float = Field(ge=0, le=1)
    growth_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    momentum_score: float = Field(ge=0, le=1)
    macro_adjustment: float = Field(
        ge=-0.5, le=0.5,
        description="Adjustment based on macro context (-0.5 to +0.5)"
    )

    # Metadata
    factors_used: list[str] = Field(default_factory=list)
    factors_missing: list[str] = Field(default_factory=list)
    confidence: float = Field(
        ge=0, le=1,
        description="Confidence in score based on data completeness"
    )


class Risk(BaseModel):
    """
    Identified risk factor.

    Output from risk identification functions.
    """
    model_config = {"frozen": True}

    category: RiskCategory
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    severity: float = Field(ge=0, le=1, description="Severity 0-1")
    probability: float = Field(ge=0, le=1, description="Probability 0-1")
    source_indicator: str | None = Field(
        default=None,
        description="The indicator that triggered this risk"
    )

    @property
    def risk_score(self) -> float:
        """Combined risk score (severity * probability)."""
        return self.severity * self.probability


# ============================================================================
# Configuration Types
# ============================================================================

@dataclass(frozen=True)
class ScoringConfig:
    """
    Configuration for scoring thresholds.

    Pass this to analysis functions to customize behavior.
    """
    # Valuation thresholds
    pe_low: float = 15.0      # Below = cheap
    pe_high: float = 30.0     # Above = expensive
    peg_fair: float = 1.0     # Below = undervalued for growth
    pb_low: float = 1.0       # Below = cheap
    pb_high: float = 5.0      # Above = expensive

    # Growth thresholds
    revenue_growth_high: float = 0.20   # 20%+ = high growth
    revenue_growth_low: float = 0.05    # Below 5% = low growth
    earnings_growth_high: float = 0.25  # 25%+ = high growth

    # Quality thresholds
    profit_margin_good: float = 0.15    # 15%+ = good
    roe_good: float = 0.15              # 15%+ = good

    # Momentum thresholds
    momentum_strong: float = 0.10       # 10%+ monthly = strong
    volume_spike: float = 2.0           # 2x avg = spike

    # Macro thresholds
    unemployment_high: float = 5.0      # Above = recession risk
    inflation_high: float = 4.0         # Above = Fed hawkish
    vix_high: float = 25.0              # Above = high fear

    # Analyst thresholds
    analyst_bullish: float = 2.0        # Below = bullish consensus
    analyst_bearish: float = 4.0        # Above = bearish consensus
    upside_significant: float = 15.0    # 15%+ upside = significant

    # Weights for overall score
    weight_valuation: float = 0.25
    weight_growth: float = 0.25
    weight_quality: float = 0.20
    weight_momentum: float = 0.15
    weight_analyst: float = 0.15


@dataclass(frozen=True)
class Strategy:
    """
    Investment strategy configuration.

    Adjusts how picks are ranked based on strategy preferences.
    """
    type: StrategyType = StrategyType.BALANCED

    # Factor preferences (higher = more important)
    valuation_weight: float = 1.0
    growth_weight: float = 1.0
    quality_weight: float = 1.0
    momentum_weight: float = 1.0
    dividend_weight: float = 0.0

    # Filters
    min_market_cap: float | None = None  # Minimum market cap
    max_pe: float | None = None          # Maximum PE ratio
    min_dividend_yield: float | None = None

    # Risk preferences
    max_risk_score: float = 0.7          # Maximum acceptable risk
    prefer_low_volatility: bool = False

    @classmethod
    def value_strategy(cls) -> "Strategy":
        """Pre-configured value investing strategy."""
        return cls(
            type=StrategyType.VALUE,
            valuation_weight=2.0,
            growth_weight=0.5,
            quality_weight=1.5,
            momentum_weight=0.3,
            max_pe=20.0,
        )

    @classmethod
    def growth_strategy(cls) -> "Strategy":
        """Pre-configured growth investing strategy."""
        return cls(
            type=StrategyType.GROWTH,
            valuation_weight=0.5,
            growth_weight=2.0,
            quality_weight=1.0,
            momentum_weight=1.5,
        )

    @classmethod
    def dividend_strategy(cls) -> "Strategy":
        """Pre-configured dividend investing strategy."""
        return cls(
            type=StrategyType.DIVIDEND,
            valuation_weight=1.0,
            growth_weight=0.3,
            quality_weight=1.5,
            momentum_weight=0.2,
            dividend_weight=2.0,
            min_dividend_yield=0.02,
        )
