from enum import Enum, auto


class Category(Enum):
    """Type of observation data."""
    PRICE = auto()
    FUNDAMENTAL = auto()
    MACRO = auto()
    NEWS = auto()
    SENTIMENT = auto()


class Direction(Enum):
    """Signal direction for trading signals."""
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()


class Timeframe(Enum):
    """Investment timeframe for signals."""
    SHORT = auto()   # days to weeks
    MEDIUM = auto()  # weeks to months
    LONG = auto()    # months to years


class SignalType(Enum):
    """Type of generated signal."""
    STOCK_PICK = auto()
    HEADWIND = auto()
    ALERT = auto()
    TREND = auto()
