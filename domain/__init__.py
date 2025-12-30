from .primitives import Observation, Signal
from .enums import Category, Direction, Timeframe, SignalType
from .models import (
    StockPick,
    MacroIndicator,
    NewsItem,
    MarketSignal,
    Trend,
    Impact,
    Strength,
    Timeframe as ModelTimeframe,
    SignalType as ModelSignalType,
    to_json_dict,
    from_json_dict,
)
from .analysis_types import (
    StockMetrics,
    MacroContext,
    ConvictionScore,
    Risk,
    RiskCategory,
    ScoringConfig,
    Strategy,
    StrategyType,
)
from .analysis import (
    score_stock,
    classify_timeframe,
    identify_headwinds,
    identify_stock_risks,
    rank_picks,
    filter_by_strategy,
    generate_thesis,
)

__all__ = [
    # Primitives (observation layer)
    "Observation",
    "Signal",
    # Enums (observation layer)
    "Category",
    "Direction",
    "Timeframe",
    "SignalType",
    # Domain models (analysis layer)
    "StockPick",
    "MacroIndicator",
    "NewsItem",
    "MarketSignal",
    "Trend",
    "Impact",
    "Strength",
    # Analysis types
    "StockMetrics",
    "MacroContext",
    "ConvictionScore",
    "Risk",
    "RiskCategory",
    "ScoringConfig",
    "Strategy",
    "StrategyType",
    # Analysis functions
    "score_stock",
    "classify_timeframe",
    "identify_headwinds",
    "identify_stock_risks",
    "rank_picks",
    "filter_by_strategy",
    "generate_thesis",
    # Serialization
    "to_json_dict",
    "from_json_dict",
]
