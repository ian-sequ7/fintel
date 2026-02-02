"""RSI + Moving Average Strategy.

Entry Logic:
- LONG: (RSI < oversold AND close > MA) OR price crosses above MA
- SHORT: (RSI > overbought AND close < MA) OR price crosses below MA

Exit Logic:
- LONG EXIT: RSI crosses below 50 OR price crosses below MA
- SHORT EXIT: RSI crosses above 50 OR price crosses above MA
"""

from datetime import datetime, timezone

from domain.algorithm_signals import (
    AlgorithmConfig,
    AlgorithmParameter,
    AlgorithmSignal,
    AlgorithmSignalType,
    IndicatorSnapshot,
)
from domain.indicators import crossover, crossunder, rsi, sma

from .base import StrategyInput, TradingStrategy


class RSIMAStrategy(TradingStrategy):
    """RSI + Moving Average combined trend/momentum strategy."""

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_overbought: int = 70,
        rsi_oversold: int = 30,
        ma_period: int = 50,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 4.0,
    ):
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.ma_period = ma_period
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    @property
    def algorithm_id(self) -> str:
        return "rsi_ma"

    @property
    def name(self) -> str:
        return "RSI + MA Strategy"

    def compute_indicators(self, data: StrategyInput) -> IndicatorSnapshot:
        """Compute RSI and MA indicators."""
        rsi_values = rsi(data.closes, self.rsi_period)
        ma_values = sma(data.closes, self.ma_period)

        current_rsi = rsi_values[-1] if rsi_values else None
        current_ma = ma_values[-1] if ma_values else None

        return IndicatorSnapshot(
            rsi=current_rsi,
            sma_50=current_ma if self.ma_period == 50 else None,
        )

    def generate_signal(self, data: StrategyInput) -> AlgorithmSignal | None:
        """Generate trading signal based on RSI and MA conditions."""
        if len(data.closes) < max(self.rsi_period, self.ma_period) + 1:
            return None

        rsi_values = rsi(data.closes, self.rsi_period)
        ma_values = sma(data.closes, self.ma_period)

        if not rsi_values or not ma_values:
            return None

        current_rsi = rsi_values[-1]
        current_ma = ma_values[-1]
        current_price = data.closes[-1]

        if current_rsi is None or current_ma is None:
            return None

        price_cross_above = crossover(data.closes, ma_values)
        price_cross_below = crossunder(data.closes, ma_values)
        rsi_cross_above_50 = crossover(rsi_values, [50.0] * len(rsi_values))
        rsi_cross_below_50 = crossunder(rsi_values, [50.0] * len(rsi_values))

        signal_type = None
        rationale_parts = []
        confidence = 0.0

        # LONG ENTRY conditions
        oversold_above_ma = current_rsi < self.rsi_oversold and current_price > current_ma
        if oversold_above_ma or price_cross_above[-1]:
            signal_type = AlgorithmSignalType.LONG_ENTRY
            if oversold_above_ma:
                rationale_parts.append(
                    f"RSI oversold ({current_rsi:.1f} < {self.rsi_oversold}) with price above MA"
                )
                confidence = 0.75
            if price_cross_above[-1]:
                rationale_parts.append(f"Price crossed above {self.ma_period}-period MA")
                confidence = max(confidence, 0.70)

        # SHORT ENTRY conditions
        elif (current_rsi > self.rsi_overbought and current_price < current_ma) or price_cross_below[-1]:
            signal_type = AlgorithmSignalType.SHORT_ENTRY
            if current_rsi > self.rsi_overbought and current_price < current_ma:
                rationale_parts.append(
                    f"RSI overbought ({current_rsi:.1f} > {self.rsi_overbought}) with price below MA"
                )
                confidence = 0.75
            if price_cross_below[-1]:
                rationale_parts.append(f"Price crossed below {self.ma_period}-period MA")
                confidence = max(confidence, 0.70)

        # LONG EXIT conditions
        elif rsi_cross_below_50[-1] or price_cross_below[-1]:
            signal_type = AlgorithmSignalType.LONG_EXIT
            if rsi_cross_below_50[-1]:
                rationale_parts.append("RSI crossed below 50")
            if price_cross_below[-1]:
                rationale_parts.append(f"Price crossed below {self.ma_period}-period MA")
            confidence = 0.65

        # SHORT EXIT conditions
        elif rsi_cross_above_50[-1] or price_cross_above[-1]:
            signal_type = AlgorithmSignalType.SHORT_EXIT
            if rsi_cross_above_50[-1]:
                rationale_parts.append("RSI crossed above 50")
            if price_cross_above[-1]:
                rationale_parts.append(f"Price crossed above {self.ma_period}-period MA")
            confidence = 0.65

        if signal_type is None:
            return None

        indicators = self.compute_indicators(data)
        rationale = "; ".join(rationale_parts)

        suggested_entry = current_price
        suggested_stop = None
        suggested_target = None

        if signal_type == AlgorithmSignalType.LONG_ENTRY:
            suggested_stop = current_price * (1 - self.stop_loss_pct / 100)
            suggested_target = current_price * (1 + self.take_profit_pct / 100)
        elif signal_type == AlgorithmSignalType.SHORT_ENTRY:
            suggested_stop = current_price * (1 + self.stop_loss_pct / 100)
            suggested_target = current_price * (1 - self.take_profit_pct / 100)

        return AlgorithmSignal(
            ticker=data.ticker,
            algorithm_id=self.algorithm_id,
            algorithm_name=self.name,
            signal_type=signal_type,
            confidence=confidence,
            price_at_signal=current_price,
            timestamp=datetime.now(timezone.utc),
            indicators=indicators,
            rationale=rationale,
            suggested_entry=suggested_entry,
            suggested_stop=suggested_stop,
            suggested_target=suggested_target,
        )

    def get_config(self) -> AlgorithmConfig:
        """Get algorithm configuration."""
        return AlgorithmConfig(
            algorithm_id=self.algorithm_id,
            name=self.name,
            description="Combined RSI and Moving Average strategy for trend following with momentum confirmation",
            version="1.0.0",
            parameters=[
                AlgorithmParameter(
                    name="rsi_period",
                    param_type="int",
                    default=14,
                    min_value=2,
                    max_value=50,
                    description="Period for RSI calculation",
                ),
                AlgorithmParameter(
                    name="rsi_overbought",
                    param_type="int",
                    default=70,
                    min_value=50,
                    max_value=90,
                    description="RSI overbought threshold",
                ),
                AlgorithmParameter(
                    name="rsi_oversold",
                    param_type="int",
                    default=30,
                    min_value=10,
                    max_value=50,
                    description="RSI oversold threshold",
                ),
                AlgorithmParameter(
                    name="ma_period",
                    param_type="int",
                    default=50,
                    min_value=10,
                    max_value=200,
                    description="Period for Moving Average",
                ),
                AlgorithmParameter(
                    name="stop_loss_pct",
                    param_type="float",
                    default=2.0,
                    min_value=0.5,
                    max_value=10.0,
                    description="Stop loss percentage",
                ),
                AlgorithmParameter(
                    name="take_profit_pct",
                    param_type="float",
                    default=4.0,
                    min_value=1.0,
                    max_value=20.0,
                    description="Take profit percentage",
                ),
            ],
        )
