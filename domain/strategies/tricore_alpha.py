"""TriCore Alpha trading strategy.

A multi-strategy approach combining momentum, mean reversion, and breakout strategies
with market regime filtering and dynamic risk management.

Allocations:
- Momentum: 40% (MACD crossovers with trend/volume confirmation)
- Mean Reversion: 35% (Bollinger Band reversals in sideways markets)
- Breakout: 25% (Support/resistance breaks with volume surge)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from domain.algorithm_signals import (
    AlgorithmConfig,
    AlgorithmParameter,
    AlgorithmSignal,
    AlgorithmSignalType,
    IndicatorSnapshot,
)
from domain.indicators import (
    atr,
    bollinger_bands,
    crossover,
    crossunder,
    highest,
    lowest,
    macd,
    rsi,
    sma,
    volume_sma,
    volume_surge,
)
from domain.strategies.base import StrategyInput, TradingStrategy


class MarketRegime(Enum):
    """Market regime classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class StrategyType(Enum):
    """Sub-strategy that triggered the signal."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"


@dataclass
class TriCoreConfig:
    """Configuration parameters for TriCore Alpha strategy."""

    # MACD parameters
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # RSI parameters
    rsi_period: int = 14
    rsi_overbought: int = 75
    rsi_oversold: int = 25

    # Bollinger Bands parameters
    bb_period: int = 20
    bb_std_dev: float = 2.0

    # ATR & Risk parameters
    atr_period: int = 14
    base_stop_atr: float = 2.2
    base_target_atr: float = 3.5

    # Market filter parameters
    spy_trend_period: int = 50
    volume_surge_mult: float = 1.8

    # Breakout parameters
    breakout_period: int = 20

    # Momentum filter thresholds
    momentum_rsi_min: int = 45
    momentum_rsi_max: int = 70
    momentum_volume_mult: float = 1.3

    # Mean reversion filter thresholds
    mean_rev_rsi_overbought: int = 75
    mean_rev_rsi_oversold: int = 25


class TriCoreAlphaStrategy(TradingStrategy):
    """TriCore Alpha multi-strategy trading system."""

    def __init__(self, config: TriCoreConfig | None = None):
        """Initialize strategy with optional custom configuration.

        Args:
            config: Custom configuration, uses defaults if None
        """
        self.config = config or TriCoreConfig()

    @property
    def algorithm_id(self) -> str:
        """Unique identifier for the algorithm."""
        return "tricore_alpha_v1"

    @property
    def name(self) -> str:
        """Human-readable name for the algorithm."""
        return "TriCore Alpha"

    def _compute_full_indicators(self, data: StrategyInput) -> dict | None:
        """Compute all indicators with full arrays for crossover detection.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            Dictionary containing full indicator arrays and snapshot, or None if insufficient data
        """
        if not data.closes:
            return None

        # Compute MACD (full arrays for crossover detection)
        macd_line, macd_signal_line, macd_hist = macd(
            data.closes,
            fast=self.config.macd_fast,
            slow=self.config.macd_slow,
            signal=self.config.macd_signal,
        )

        # Compute RSI
        rsi_values = rsi(data.closes, period=self.config.rsi_period)

        # Compute Bollinger Bands
        bb_upper, bb_middle, bb_lower = bollinger_bands(
            data.closes,
            period=self.config.bb_period,
            std_dev=self.config.bb_std_dev,
        )

        # Compute ATR
        atr_values = atr(
            data.highs,
            data.lows,
            data.closes,
            period=self.config.atr_period,
        )

        # Compute moving averages
        sma_20 = sma(data.closes, 20)
        sma_50 = sma(data.closes, 50)

        # Compute volume metrics
        avg_volume = volume_sma(data.volumes, 20)
        vol_surge = volume_surge(
            data.volumes,
            period=20,
            threshold=self.config.volume_surge_mult,
        )

        # Get most recent values (last index)
        idx = -1
        volume_ratio = None
        if avg_volume[idx] and data.volumes[idx]:
            volume_ratio = data.volumes[idx] / avg_volume[idx]

        # Create snapshot
        snapshot = IndicatorSnapshot(
            rsi=rsi_values[idx],
            macd_line=macd_line[idx],
            macd_signal=macd_signal_line[idx],
            macd_histogram=macd_hist[idx],
            bb_upper=bb_upper[idx],
            bb_middle=bb_middle[idx],
            bb_lower=bb_lower[idx],
            atr=atr_values[idx],
            sma_20=sma_20[idx],
            sma_50=sma_50[idx],
            volume_surge=vol_surge[idx] if vol_surge else False,
            volume_ratio=volume_ratio,
        )

        # Return full arrays for crossover detection + snapshot
        return {
            "macd_line": macd_line,
            "macd_signal_line": macd_signal_line,
            "macd_hist": macd_hist,
            "rsi_values": rsi_values,
            "bb_upper": bb_upper,
            "bb_middle": bb_middle,
            "bb_lower": bb_lower,
            "atr_values": atr_values,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "avg_volume": avg_volume,
            "vol_surge": vol_surge,
            "snapshot": snapshot,
        }

    def compute_indicators(self, data: StrategyInput) -> IndicatorSnapshot:
        """Compute all indicator values for the most recent bar.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            IndicatorSnapshot with computed indicator values
        """
        result = self._compute_full_indicators(data)
        if result is None:
            return IndicatorSnapshot()
        return result["snapshot"]

    def generate_signal(self, data: StrategyInput) -> AlgorithmSignal | None:
        """Generate trading signal from input data.

        Evaluates three sub-strategies (momentum, mean reversion, breakout) and
        returns signal from highest-confidence trigger.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            AlgorithmSignal if conditions met, None otherwise
        """
        if not data.closes or len(data.closes) < max(
            self.config.macd_slow + self.config.macd_signal,
            self.config.bb_period,
            self.config.breakout_period,
        ):
            return None

        # Compute all indicators once
        ind = self._compute_full_indicators(data)
        if ind is None:
            return None

        # Extract arrays for crossover detection
        macd_line = ind["macd_line"]
        macd_signal_line = ind["macd_signal_line"]
        macd_hist = ind["macd_hist"]
        rsi_values = ind["rsi_values"]
        bb_upper = ind["bb_upper"]
        bb_lower = ind["bb_lower"]
        atr_values = ind["atr_values"]
        sma_20 = ind["sma_20"]
        avg_volume = ind["avg_volume"]
        vol_surge = ind["vol_surge"]
        indicators = ind["snapshot"]

        # Determine market regime
        regime = self._determine_market_regime(data)

        # Compute crossover/crossunder signals
        macd_cross_up = crossover(macd_line, macd_signal_line)
        macd_cross_down = crossunder(macd_line, macd_signal_line)

        # Support/Resistance levels for breakout
        resistance = highest(data.highs, self.config.breakout_period)
        support = lowest(data.lows, self.config.breakout_period)

        # Get current values
        idx = -1
        curr_close = data.closes[idx]
        curr_rsi = rsi_values[idx]
        curr_macd = macd_line[idx]
        curr_signal = macd_signal_line[idx]
        curr_hist = macd_hist[idx]
        curr_atr = atr_values[idx]
        curr_volume = data.volumes[idx]
        curr_avg_vol = avg_volume[idx]

        # Check for None values
        if None in [
            curr_rsi,
            curr_macd,
            curr_signal,
            curr_hist,
            curr_atr,
            bb_upper[idx],
            bb_lower[idx],
            sma_20[idx],
            curr_avg_vol,
        ]:
            return None

        # STRATEGY 1: MOMENTUM (40% allocation)
        momentum_long = (
            macd_cross_up[idx]
            and curr_macd < 0
            and self.config.momentum_rsi_min < curr_rsi < self.config.momentum_rsi_max
            and curr_close > sma_20[idx]
            and curr_volume > curr_avg_vol * self.config.momentum_volume_mult
            and regime == MarketRegime.BULLISH
        )

        momentum_short = (
            macd_cross_down[idx]
            and curr_macd > 0
            and 30 < curr_rsi < 55
            and curr_close < sma_20[idx]
            and curr_volume > curr_avg_vol * self.config.momentum_volume_mult
            and regime == MarketRegime.BEARISH
        )

        # STRATEGY 2: MEAN REVERSION (35% allocation)
        mean_rev_long = (
            curr_close <= bb_lower[idx]
            and data.closes[-2] > bb_lower[-2]  # Price crossing into lower band
            and curr_rsi <= self.config.mean_rev_rsi_oversold
            and curr_rsi > rsi_values[-2]  # RSI turning up
            and regime == MarketRegime.SIDEWAYS
        )

        mean_rev_short = (
            curr_close >= bb_upper[idx]
            and data.closes[-2] < bb_upper[-2]  # Price crossing into upper band
            and curr_rsi >= self.config.mean_rev_rsi_overbought
            and curr_rsi < rsi_values[-2]  # RSI turning down
            and regime == MarketRegime.SIDEWAYS
        )

        # STRATEGY 3: BREAKOUT (25% allocation)
        breakout_long = (
            curr_close > resistance[-2]  # Breaking above previous resistance
            and vol_surge[idx]
            and curr_rsi > 55
            and curr_hist > 0
        )

        breakout_short = (
            curr_close < support[-2]  # Breaking below previous support
            and vol_surge[idx]
            and curr_rsi < 45
            and curr_hist < 0
        )

        # Determine which strategy triggered and calculate confidence
        signal_type = None
        confidence = 0.0
        strategy_triggered = None
        rationale = ""

        if momentum_long:
            signal_type = AlgorithmSignalType.LONG_ENTRY
            confidence = 0.40  # Base allocation
            strategy_triggered = StrategyType.MOMENTUM
            rationale = (
                f"Momentum LONG: MACD bullish crossover at {curr_macd:.3f}, "
                f"RSI {curr_rsi:.1f} (neutral range), price above SMA20, "
                f"volume {curr_volume / curr_avg_vol:.1f}x average, bullish market regime"
            )
        elif momentum_short:
            signal_type = AlgorithmSignalType.SHORT_ENTRY
            confidence = 0.40
            strategy_triggered = StrategyType.MOMENTUM
            rationale = (
                f"Momentum SHORT: MACD bearish crossover at {curr_macd:.3f}, "
                f"RSI {curr_rsi:.1f} (neutral range), price below SMA20, "
                f"volume {curr_volume / curr_avg_vol:.1f}x average, bearish market regime"
            )
        elif mean_rev_long:
            signal_type = AlgorithmSignalType.LONG_ENTRY
            confidence = 0.35
            strategy_triggered = StrategyType.MEAN_REVERSION
            rationale = (
                f"Mean Reversion LONG: Price touched lower BB at ${bb_lower[idx]:.2f}, "
                f"RSI oversold at {curr_rsi:.1f} and turning up, sideways market regime"
            )
        elif mean_rev_short:
            signal_type = AlgorithmSignalType.SHORT_ENTRY
            confidence = 0.35
            strategy_triggered = StrategyType.MEAN_REVERSION
            rationale = (
                f"Mean Reversion SHORT: Price touched upper BB at ${bb_upper[idx]:.2f}, "
                f"RSI overbought at {curr_rsi:.1f} and turning down, sideways market regime"
            )
        elif breakout_long:
            signal_type = AlgorithmSignalType.LONG_ENTRY
            confidence = 0.25
            strategy_triggered = StrategyType.BREAKOUT
            rationale = (
                f"Breakout LONG: Price broke resistance at ${resistance[-2]:.2f}, "
                f"volume surge detected, RSI {curr_rsi:.1f}, MACD histogram positive"
            )
        elif breakout_short:
            signal_type = AlgorithmSignalType.SHORT_ENTRY
            confidence = 0.25
            strategy_triggered = StrategyType.BREAKOUT
            rationale = (
                f"Breakout SHORT: Price broke support at ${support[-2]:.2f}, "
                f"volume surge detected, RSI {curr_rsi:.1f}, MACD histogram negative"
            )

        if signal_type is None:
            return None

        # Adjust confidence based on market conditions
        confidence = self._adjust_confidence(
            confidence, regime, curr_rsi, vol_surge[idx], strategy_triggered
        )

        # Calculate dynamic stops based on strategy type and ATR
        stop_mult = self._get_stop_multiplier(strategy_triggered)
        suggested_stop = curr_atr * stop_mult
        suggested_target = curr_atr * self.config.base_target_atr

        return AlgorithmSignal(
            ticker=data.ticker,
            algorithm_id=self.algorithm_id,
            algorithm_name=self.name,
            signal_type=signal_type,
            confidence=confidence,
            price_at_signal=curr_close,
            timestamp=datetime.now(),
            indicators=indicators,
            rationale=rationale,
            suggested_entry=curr_close,
            suggested_stop=suggested_stop,
            suggested_target=suggested_target,
            metadata={
                "strategy_type": strategy_triggered.value,
                "market_regime": regime.value,
                "stop_multiplier": stop_mult,
            },
        )

    def _determine_market_regime(self, data: StrategyInput) -> MarketRegime:
        """Determine current market regime based on SPY trend or local price action.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            MarketRegime classification
        """
        # Use SPY if available for market regime
        if data.spy_closes and len(data.spy_closes) >= self.config.spy_trend_period:
            spy_sma = sma(data.spy_closes, self.config.spy_trend_period)
            if spy_sma[-1] is not None:
                current_spy = data.spy_closes[-1]
                if current_spy > spy_sma[-1]:
                    return MarketRegime.BULLISH
                elif current_spy < spy_sma[-1] * 0.98:  # 2% below trend
                    return MarketRegime.BEARISH
                else:
                    return MarketRegime.SIDEWAYS

        # Fallback to local trend analysis
        if len(data.closes) >= 50:
            local_sma = sma(data.closes, 50)
            if local_sma[-1] is not None:
                current_close = data.closes[-1]
                if current_close > local_sma[-1]:
                    return MarketRegime.BULLISH
                elif current_close < local_sma[-1] * 0.98:
                    return MarketRegime.BEARISH

        return MarketRegime.SIDEWAYS

    def _adjust_confidence(
        self,
        base_confidence: float,
        regime: MarketRegime,
        rsi_val: float,
        vol_surge_present: bool,
        strategy_type: StrategyType,
    ) -> float:
        """Adjust confidence based on market conditions.

        Args:
            base_confidence: Base confidence from strategy allocation
            regime: Current market regime
            rsi_val: Current RSI value
            vol_surge_present: Whether volume surge is detected
            strategy_type: Which sub-strategy triggered

        Returns:
            Adjusted confidence value (capped at 1.0)
        """
        confidence = base_confidence

        # Boost for strong RSI confirmation
        if strategy_type == StrategyType.MOMENTUM:
            if rsi_val > 60:  # Strong momentum
                confidence += 0.10
        elif strategy_type == StrategyType.MEAN_REVERSION:
            if rsi_val < 20 or rsi_val > 80:  # Extreme oversold/overbought
                confidence += 0.15

        # Boost for volume surge
        if vol_surge_present:
            confidence += 0.05

        # Penalty for mismatched regime
        if strategy_type == StrategyType.MOMENTUM and regime == MarketRegime.SIDEWAYS:
            confidence -= 0.10
        elif strategy_type == StrategyType.MEAN_REVERSION and regime != MarketRegime.SIDEWAYS:
            confidence -= 0.10

        return min(confidence, 1.0)

    def _get_stop_multiplier(self, strategy_type: StrategyType) -> float:
        """Get ATR stop multiplier based on strategy type.

        Args:
            strategy_type: Which sub-strategy triggered

        Returns:
            ATR multiplier for stop loss calculation
        """
        if strategy_type == StrategyType.BREAKOUT:
            return self.config.base_stop_atr * 0.8  # Tighter stops for breakouts
        elif strategy_type == StrategyType.MEAN_REVERSION:
            return self.config.base_stop_atr * 0.6  # Tightest stops for mean reversion
        else:  # MOMENTUM
            return self.config.base_stop_atr

    def get_config(self) -> AlgorithmConfig:
        """Get algorithm configuration with parameters.

        Returns:
            AlgorithmConfig with all configurable parameters
        """
        return AlgorithmConfig(
            algorithm_id=self.algorithm_id,
            name=self.name,
            description=(
                "Multi-strategy system combining momentum (40%), mean reversion (35%), "
                "and breakout (25%) strategies with market regime filtering and "
                "dynamic ATR-based risk management."
            ),
            version="1.0.0",
            parameters=[
                AlgorithmParameter(
                    name="macd_fast",
                    param_type="int",
                    default=self.config.macd_fast,
                    min_value=5,
                    max_value=20,
                    description="MACD fast EMA period",
                ),
                AlgorithmParameter(
                    name="macd_slow",
                    param_type="int",
                    default=self.config.macd_slow,
                    min_value=20,
                    max_value=40,
                    description="MACD slow EMA period",
                ),
                AlgorithmParameter(
                    name="macd_signal",
                    param_type="int",
                    default=self.config.macd_signal,
                    min_value=5,
                    max_value=15,
                    description="MACD signal line period",
                ),
                AlgorithmParameter(
                    name="rsi_period",
                    param_type="int",
                    default=self.config.rsi_period,
                    min_value=7,
                    max_value=21,
                    description="RSI calculation period",
                ),
                AlgorithmParameter(
                    name="rsi_overbought",
                    param_type="int",
                    default=self.config.rsi_overbought,
                    min_value=60,
                    max_value=85,
                    description="RSI overbought threshold",
                ),
                AlgorithmParameter(
                    name="rsi_oversold",
                    param_type="int",
                    default=self.config.rsi_oversold,
                    min_value=15,
                    max_value=40,
                    description="RSI oversold threshold",
                ),
                AlgorithmParameter(
                    name="bb_period",
                    param_type="int",
                    default=self.config.bb_period,
                    min_value=10,
                    max_value=30,
                    description="Bollinger Bands period",
                ),
                AlgorithmParameter(
                    name="bb_std_dev",
                    param_type="float",
                    default=self.config.bb_std_dev,
                    min_value=1.5,
                    max_value=3.0,
                    description="Bollinger Bands standard deviation multiplier",
                ),
                AlgorithmParameter(
                    name="atr_period",
                    param_type="int",
                    default=self.config.atr_period,
                    min_value=7,
                    max_value=21,
                    description="ATR calculation period",
                ),
                AlgorithmParameter(
                    name="base_stop_atr",
                    param_type="float",
                    default=self.config.base_stop_atr,
                    min_value=1.0,
                    max_value=4.0,
                    description="Base ATR multiplier for stop loss",
                ),
                AlgorithmParameter(
                    name="base_target_atr",
                    param_type="float",
                    default=self.config.base_target_atr,
                    min_value=2.0,
                    max_value=6.0,
                    description="ATR multiplier for profit target",
                ),
                AlgorithmParameter(
                    name="spy_trend_period",
                    param_type="int",
                    default=self.config.spy_trend_period,
                    min_value=20,
                    max_value=100,
                    description="SPY trend SMA period for market regime",
                ),
                AlgorithmParameter(
                    name="volume_surge_mult",
                    param_type="float",
                    default=self.config.volume_surge_mult,
                    min_value=1.2,
                    max_value=3.0,
                    description="Volume surge detection multiplier",
                ),
                AlgorithmParameter(
                    name="breakout_period",
                    param_type="int",
                    default=self.config.breakout_period,
                    min_value=10,
                    max_value=40,
                    description="Lookback period for support/resistance",
                ),
            ],
        )
