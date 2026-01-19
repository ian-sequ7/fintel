"""
Market Regime Detection Module.

Implements simple, robust regime classification using free data:
- SPY price vs 200-day SMA (trend)
- VIX level (volatility/fear)

Regimes:
- BULL: SPY > 200 SMA, VIX < 20
- BEAR: SPY < 200 SMA, VIX > 25
- HIGH_VOL: VIX > 30 (overrides others - defensive mode)
- SIDEWAYS: Everything else

The regime determines factor weight adjustments for all-weather performance.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import NamedTuple

from .factors.catalyst import MarketRegime  # Re-export from catalyst


# Re-export MarketRegime for convenience
__all__ = ["MarketRegime", "RegimeContext", "FactorWeights", "detect_market_regime", "get_regime_weights"]


class FactorWeights(NamedTuple):
    """Factor weights for portfolio construction."""
    quality: float
    value: float
    momentum: float
    low_vol: float
    smart_money: float
    catalyst: float

    def validate(self) -> bool:
        """Check weights sum to ~1.0."""
        total = sum(self)
        return abs(total - 1.0) < 0.01

    def __str__(self) -> str:
        return (f"Q:{self.quality:.0%} V:{self.value:.0%} M:{self.momentum:.0%} "
                f"LV:{self.low_vol:.0%} SM:{self.smart_money:.0%} C:{self.catalyst:.0%}")


@dataclass(frozen=True)
class RegimeContext:
    """Context about current market regime."""
    regime: MarketRegime
    spy_price: float | None
    spy_sma_200: float | None
    vix: float | None
    spy_above_sma: bool | None
    confidence: float  # 0-1, based on data availability
    description: str

    @property
    def is_risk_on(self) -> bool:
        """True if regime favors risk assets."""
        return self.regime == MarketRegime.BULL

    @property
    def is_risk_off(self) -> bool:
        """True if regime favors defensive assets."""
        return self.regime in (MarketRegime.BEAR, MarketRegime.HIGH_VOL)


# Regime-specific factor weights (per SPEC-scoring.md)
REGIME_WEIGHTS = {
    MarketRegime.BULL: FactorWeights(
        quality=0.25,
        value=0.15,
        momentum=0.30,
        low_vol=0.10,
        smart_money=0.15,
        catalyst=0.05,
    ),
    MarketRegime.BEAR: FactorWeights(
        quality=0.35,
        value=0.25,
        momentum=0.05,
        low_vol=0.20,
        smart_money=0.10,
        catalyst=0.05,
    ),
    MarketRegime.SIDEWAYS: FactorWeights(
        quality=0.30,
        value=0.20,
        momentum=0.20,
        low_vol=0.15,
        smart_money=0.10,
        catalyst=0.05,
    ),
    MarketRegime.HIGH_VOL: FactorWeights(
        quality=0.35,
        value=0.20,
        momentum=0.05,
        low_vol=0.25,
        smart_money=0.10,
        catalyst=0.05,
    ),
}

# Timeframe adjustments (applied on top of regime weights)
TIMEFRAME_ADJUSTMENTS = {
    "SHORT": {
        "momentum": +0.15,
        "smart_money": +0.05,
        "catalyst": +0.05,
        "quality": -0.10,
        "value": -0.10,
        "low_vol": -0.05,
    },
    "MEDIUM": {
        # Balanced - no adjustments
    },
    "LONG": {
        "quality": +0.10,
        "value": +0.10,
        "momentum": -0.10,
        "catalyst": -0.05,
        "smart_money": -0.05,
        "low_vol": 0,
    },
}


def _calculate_sma(prices: list[float], period: int = 200) -> float | None:
    """Calculate Simple Moving Average."""
    if not prices or len(prices) < period:
        return None
    return sum(prices[:period]) / period


def detect_market_regime(
    spy_prices: list[float] | None = None,
    spy_price_current: float | None = None,
    spy_sma_200: float | None = None,
    vix_current: float | None = None,
) -> RegimeContext:
    """
    Classify current market regime based on SPY trend and VIX.

    Classification Logic:
    1. HIGH_VOL: VIX > 30 (crisis mode, overrides all)
    2. BULL: SPY > 200 SMA AND VIX < 20
    3. BEAR: SPY < 200 SMA AND VIX > 25
    4. SIDEWAYS: Everything else

    Args:
        spy_prices: List of SPY prices (most recent first), need 200+ for SMA
        spy_price_current: Current SPY price (alternative to prices[0])
        spy_sma_200: Pre-computed 200-day SMA (alternative to calculating)
        vix_current: Current VIX level

    Returns:
        RegimeContext with classification and supporting data
    """
    # Determine SPY price and SMA
    if spy_prices and len(spy_prices) >= 200:
        current_price = spy_prices[0]
        sma_200 = _calculate_sma(spy_prices, 200)
    else:
        current_price = spy_price_current
        sma_200 = spy_sma_200

    # Calculate data availability confidence
    data_points = 0
    if current_price is not None:
        data_points += 1
    if sma_200 is not None:
        data_points += 1
    if vix_current is not None:
        data_points += 1
    confidence = data_points / 3.0

    # Determine if SPY is above SMA
    spy_above_sma = None
    if current_price is not None and sma_200 is not None:
        spy_above_sma = current_price > sma_200

    # Classification logic
    if vix_current is not None and vix_current > 30:
        # HIGH_VOL: Crisis mode - maximum defensiveness
        regime = MarketRegime.HIGH_VOL
        desc = f"High volatility regime (VIX: {vix_current:.1f})"

    elif spy_above_sma is True and vix_current is not None and vix_current < 20:
        # BULL: Strong uptrend with low fear
        regime = MarketRegime.BULL
        pct_above = ((current_price - sma_200) / sma_200 * 100) if sma_200 else 0
        desc = f"Bull market (SPY +{pct_above:.1f}% above 200 SMA, VIX: {vix_current:.1f})"

    elif spy_above_sma is False and vix_current is not None and vix_current > 25:
        # BEAR: Downtrend with elevated fear
        regime = MarketRegime.BEAR
        pct_below = ((sma_200 - current_price) / sma_200 * 100) if sma_200 else 0
        desc = f"Bear market (SPY -{pct_below:.1f}% below 200 SMA, VIX: {vix_current:.1f})"

    elif spy_above_sma is None and vix_current is None:
        # No data - default to sideways
        regime = MarketRegime.SIDEWAYS
        desc = "Sideways (insufficient data for classification)"

    else:
        # SIDEWAYS: Mixed signals or moderate conditions
        regime = MarketRegime.SIDEWAYS
        parts = []
        if spy_above_sma is not None:
            parts.append(f"SPY {'above' if spy_above_sma else 'below'} 200 SMA")
        if vix_current is not None:
            parts.append(f"VIX: {vix_current:.1f}")
        desc = f"Sideways market ({', '.join(parts)})" if parts else "Sideways market"

    return RegimeContext(
        regime=regime,
        spy_price=current_price,
        spy_sma_200=sma_200,
        vix=vix_current,
        spy_above_sma=spy_above_sma,
        confidence=confidence,
        description=desc,
    )


def get_regime_weights(
    regime: MarketRegime,
    timeframe: str = "MEDIUM",
) -> FactorWeights:
    """
    Get factor weights adjusted for regime and timeframe.

    Args:
        regime: Current market regime
        timeframe: "SHORT", "MEDIUM", or "LONG"

    Returns:
        FactorWeights with regime and timeframe adjustments
    """
    # Start with regime base weights
    base = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS[MarketRegime.SIDEWAYS])

    # Apply timeframe adjustments
    adjustments = TIMEFRAME_ADJUSTMENTS.get(timeframe.upper(), {})

    if not adjustments:
        return base

    # Calculate adjusted weights
    adjusted = FactorWeights(
        quality=max(0.05, min(0.50, base.quality + adjustments.get("quality", 0))),
        value=max(0.05, min(0.40, base.value + adjustments.get("value", 0))),
        momentum=max(0.0, min(0.45, base.momentum + adjustments.get("momentum", 0))),
        low_vol=max(0.0, min(0.35, base.low_vol + adjustments.get("low_vol", 0))),
        smart_money=max(0.05, min(0.25, base.smart_money + adjustments.get("smart_money", 0))),
        catalyst=max(0.0, min(0.15, base.catalyst + adjustments.get("catalyst", 0))),
    )

    # Renormalize to sum to 1.0
    total = sum(adjusted)
    if total > 0 and abs(total - 1.0) > 0.01:
        normalized = FactorWeights(
            quality=adjusted.quality / total,
            value=adjusted.value / total,
            momentum=adjusted.momentum / total,
            low_vol=adjusted.low_vol / total,
            smart_money=adjusted.smart_money / total,
            catalyst=adjusted.catalyst / total,
        )
        return normalized

    return adjusted


def get_regime_description(regime: MarketRegime) -> str:
    """Get human-readable description of regime characteristics."""
    descriptions = {
        MarketRegime.BULL: (
            "Bull market conditions favor momentum and growth. "
            "Quality and smart money signals are important for picking winners."
        ),
        MarketRegime.BEAR: (
            "Bear market conditions favor defensive positioning. "
            "Focus on quality, value, and low volatility for capital preservation."
        ),
        MarketRegime.SIDEWAYS: (
            "Sideways/range-bound conditions require balanced approach. "
            "Quality and value provide stability while momentum captures breakouts."
        ),
        MarketRegime.HIGH_VOL: (
            "High volatility crisis mode requires maximum defensiveness. "
            "Prioritize quality and low volatility, minimize momentum exposure."
        ),
    }
    return descriptions.get(regime, "Unknown regime")
