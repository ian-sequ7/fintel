from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import Category, Direction, Timeframe, SignalType


@dataclass(frozen=True)
class Observation:
    """
    Immutable fact collected from an external source.

    This is the input primitive - raw data before analysis.
    """
    source: str
    timestamp: datetime
    category: Category
    data: dict[str, Any]
    ticker: str | None = None
    reliability: float = 1.0  # 0-1, based on source reputation

    def __post_init__(self) -> None:
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError(f"reliability must be 0-1, got {self.reliability}")


@dataclass
class Signal:
    """
    Derived insight produced by analysis.

    This is the output primitive - actionable intelligence.
    """
    type: SignalType
    direction: Direction
    confidence: float
    timeframe: Timeframe
    summary: str
    evidence: list[Observation] = field(default_factory=list)
    ticker: str | None = None
    generated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {self.confidence}")
