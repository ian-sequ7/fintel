"""
Smart Money domain models.

Models for tracking institutional activity signals:
- Congress trades (politician stock transactions)
- Unusual options activity
- Dark pool / off-exchange trading
"""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from pydantic.functional_validators import AfterValidator


# ============================================================================
# Enums
# ============================================================================

class SmartMoneySignalType(str, Enum):
    """Type of smart money signal."""
    CONGRESS = "congress"
    OPTIONS = "options"
    DARKPOOL = "darkpool"


class TradeDirection(str, Enum):
    """Direction of trade."""
    BUY = "buy"
    SELL = "sell"
    EXCHANGE = "exchange"  # For stock exchanges/transfers


class PoliticalParty(str, Enum):
    """Political party affiliation."""
    DEMOCRAT = "D"
    REPUBLICAN = "R"
    INDEPENDENT = "I"


class Chamber(str, Enum):
    """Congressional chamber."""
    HOUSE = "House"
    SENATE = "Senate"


class OptionType(str, Enum):
    """Type of option contract."""
    CALL = "call"
    PUT = "put"


# ============================================================================
# Custom validators
# ============================================================================

def _validate_ticker(v: str) -> str:
    """Validate ticker symbol format."""
    v = v.upper().strip()
    if not v:
        raise ValueError("ticker cannot be empty")
    if len(v) > 10:
        raise ValueError("ticker too long (max 10 chars)")
    if not v.replace("-", "").replace(".", "").isalnum():
        raise ValueError("ticker must be alphanumeric (with - or .)")
    return v


def _validate_strength(v: float) -> float:
    """Validate strength score is between 0 and 1."""
    if not 0.0 <= v <= 1.0:
        raise ValueError("strength must be between 0 and 1")
    return round(v, 4)


Ticker = Annotated[str, AfterValidator(_validate_ticker)]
Strength = Annotated[float, AfterValidator(_validate_strength)]


# ============================================================================
# Detail Models
# ============================================================================

class CongressTradeDetails(BaseModel):
    """Details specific to congress trades."""
    model_config = {"frozen": True, "extra": "forbid"}

    politician: str = Field(
        min_length=1,
        max_length=100,
        description="Name of the politician"
    )
    party: PoliticalParty = Field(description="Political party")
    chamber: Chamber = Field(description="House or Senate")
    amount_low: int = Field(ge=0, description="Low end of amount range")
    amount_high: int = Field(ge=0, description="High end of amount range")
    asset_description: str = Field(
        default="",
        max_length=500,
        description="Description of the asset traded"
    )
    transaction_date: datetime | None = Field(
        default=None,
        description="Date of actual transaction"
    )
    disclosure_date: datetime = Field(
        description="Date trade was disclosed"
    )


class UnusualOptionsDetails(BaseModel):
    """Details specific to unusual options activity."""
    model_config = {"frozen": True, "extra": "forbid"}

    option_type: OptionType = Field(description="Call or put")
    strike: float = Field(gt=0, description="Strike price")
    expiry: datetime = Field(description="Expiration date")
    volume: int = Field(ge=0, description="Trading volume")
    open_interest: int = Field(ge=0, description="Open interest")
    volume_oi_ratio: float = Field(
        ge=0,
        description="Volume to open interest ratio (unusual if > 3)"
    )
    implied_volatility: float | None = Field(
        default=None,
        ge=0,
        le=5.0,  # 500% IV max
        description="Implied volatility"
    )
    premium_total: float | None = Field(
        default=None,
        ge=0,
        description="Total premium (volume * price * 100)"
    )


class DarkPoolDetails(BaseModel):
    """Details specific to dark pool activity."""
    model_config = {"frozen": True, "extra": "forbid"}

    dark_pool_percent: float = Field(
        ge=0,
        le=100,
        description="Percentage of volume in dark pools"
    )
    total_volume: int = Field(ge=0, description="Total trading volume")
    dark_pool_volume: int = Field(ge=0, description="Dark pool volume")
    reporting_period: str = Field(
        description="Reporting period (e.g., '2025-W01')"
    )
    source_venue: str = Field(
        default="",
        description="ATS/Dark pool venue name"
    )


# ============================================================================
# Main Smart Money Signal Model
# ============================================================================

class SmartMoneySignal(BaseModel):
    """
    A unified smart money signal for frontend display.

    Represents institutional activity that may indicate
    informed trading or significant market interest.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(
        min_length=1,
        description="Unique identifier for the signal"
    )
    signal_type: SmartMoneySignalType = Field(
        description="Type of signal (congress/options/darkpool)"
    )
    ticker: Ticker = Field(description="Stock ticker symbol")
    direction: TradeDirection = Field(
        description="Trade direction (buy/sell/exchange)"
    )
    strength: Strength = Field(
        default=0.5,
        description="Signal strength (0-1, higher = stronger signal)"
    )
    summary: str = Field(
        min_length=1,
        max_length=500,
        description="Human-readable summary of the signal"
    )
    details: CongressTradeDetails | UnusualOptionsDetails | DarkPoolDetails = Field(
        description="Type-specific details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the signal was detected"
    )
    source: str = Field(
        default="",
        max_length=100,
        description="Data source name"
    )

    @field_validator("summary")
    @classmethod
    def _clean_summary(cls, v: str) -> str:
        """Clean up summary text."""
        return v.strip()


# ============================================================================
# Context Model (for aggregated frontend data)
# ============================================================================

class SmartMoneyContext(BaseModel):
    """
    Aggregated smart money data for frontend consumption.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    signals: list[SmartMoneySignal] = Field(
        default_factory=list,
        description="List of smart money signals"
    )
    last_updated: datetime = Field(
        default_factory=datetime.now,
        description="When data was last updated"
    )
    total_signals: int = Field(
        default=0,
        ge=0,
        description="Total number of signals"
    )
    congress_count: int = Field(
        default=0,
        ge=0,
        description="Number of congress trade signals"
    )
    options_count: int = Field(
        default=0,
        ge=0,
        description="Number of unusual options signals"
    )
    darkpool_count: int = Field(
        default=0,
        ge=0,
        description="Number of dark pool signals"
    )

    @classmethod
    def from_signals(cls, signals: list[SmartMoneySignal]) -> "SmartMoneyContext":
        """Create context from a list of signals."""
        congress = sum(1 for s in signals if s.signal_type == SmartMoneySignalType.CONGRESS)
        options = sum(1 for s in signals if s.signal_type == SmartMoneySignalType.OPTIONS)
        darkpool = sum(1 for s in signals if s.signal_type == SmartMoneySignalType.DARKPOOL)

        return cls(
            signals=signals,
            last_updated=datetime.now(),
            total_signals=len(signals),
            congress_count=congress,
            options_count=options,
            darkpool_count=darkpool,
        )


# ============================================================================
# Serialization helpers
# ============================================================================

def signal_to_dict(signal: SmartMoneySignal) -> dict:
    """Convert signal to JSON-serializable dict for frontend."""
    return signal.model_dump(mode="json")


def context_to_dict(context: SmartMoneyContext) -> dict:
    """Convert context to JSON-serializable dict for frontend."""
    return context.model_dump(mode="json")
