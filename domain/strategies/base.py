"""Base classes for trading strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.algorithm_signals import AlgorithmConfig, AlgorithmSignal, IndicatorSnapshot


@dataclass
class StrategyInput:
    """Input data for strategy evaluation."""

    ticker: str
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
    spy_closes: list[float] | None = None
    vix_value: float | None = None


class TradingStrategy(ABC):
    """Base class for all trading strategies."""

    @property
    @abstractmethod
    def algorithm_id(self) -> str:
        """Unique identifier for the algorithm."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for the algorithm."""

    @abstractmethod
    def compute_indicators(self, data: StrategyInput) -> IndicatorSnapshot:
        """Compute indicator values from input data.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            IndicatorSnapshot with computed indicator values
        """

    @abstractmethod
    def generate_signal(self, data: StrategyInput) -> AlgorithmSignal | None:
        """Generate trading signal from input data.

        Args:
            data: Strategy input containing OHLCV data

        Returns:
            AlgorithmSignal if conditions met, None otherwise
        """

    @abstractmethod
    def get_config(self) -> AlgorithmConfig:
        """Get algorithm configuration.

        Returns:
            AlgorithmConfig with parameters and metadata
        """
