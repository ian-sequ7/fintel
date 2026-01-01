"""
Domain models - pure data structures with validation.

These are immutable data carriers with no business logic.
All models are JSON-serializable and self-validating.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.functional_validators import AfterValidator


# ============================================================================
# Enums for domain models
# ============================================================================

class Timeframe(str, Enum):
    """Investment timeframe."""
    SHORT = "short"    # days to weeks
    MEDIUM = "medium"  # weeks to months
    LONG = "long"      # months to years


class Trend(str, Enum):
    """Direction of movement."""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


class Impact(str, Enum):
    """Impact assessment level."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class SignalType(str, Enum):
    """Type of market signal."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"


class Strength(str, Enum):
    """Signal strength."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


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


def _validate_score(v: float) -> float:
    """Validate score is between 0 and 1."""
    if not 0.0 <= v <= 1.0:
        raise ValueError("score must be between 0 and 1")
    return round(v, 4)


def _validate_url(v: str | None) -> str | None:
    """Validate URL format if provided."""
    if v is None:
        return None
    v = v.strip()
    if v and not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("url must start with http:// or https://")
    return v


# Type aliases with validation
Ticker = Annotated[str, AfterValidator(_validate_ticker)]
Score = Annotated[float, AfterValidator(_validate_score)]
Url = Annotated[str | None, AfterValidator(_validate_url)]


# ============================================================================
# Domain Models
# ============================================================================

class StockPick(BaseModel):
    """
    A stock recommendation with thesis and risk assessment.

    Represents an actionable investment idea with supporting rationale.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    ticker: Ticker = Field(description="Stock ticker symbol (e.g., AAPL)")
    timeframe: Timeframe = Field(description="Investment horizon")
    conviction_score: Score = Field(
        description="Confidence in the pick (0-1, higher = more confident)"
    )
    thesis: str = Field(
        min_length=10,
        max_length=1000,
        description="Investment thesis explaining the recommendation"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Key risks to the thesis"
    )
    entry_price: float | None = Field(
        default=None,
        gt=0,
        description="Suggested entry price"
    )
    target_price: float | None = Field(
        default=None,
        gt=0,
        description="Price target"
    )
    stop_loss: float | None = Field(
        default=None,
        gt=0,
        description="Stop loss price for risk management"
    )
    generated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _validate_prices(self) -> "StockPick":
        """Target price should be different from entry if both provided."""
        if self.entry_price and self.target_price:
            if self.entry_price == self.target_price:
                raise ValueError("target_price must differ from entry_price")
        return self

    @field_validator("risk_factors")
    @classmethod
    def _validate_risk_factors(cls, v: list[str]) -> list[str]:
        """Ensure risk factors are non-empty strings."""
        return [r.strip() for r in v if r and r.strip()]


class MacroIndicator(BaseModel):
    """
    A macroeconomic indicator with trend and impact assessment.

    Represents economic data points that influence market conditions.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Indicator name (e.g., 'Unemployment Rate')"
    )
    series_id: str | None = Field(
        default=None,
        description="Data series identifier (e.g., FRED series ID)"
    )
    current_value: float = Field(description="Current value of the indicator")
    previous_value: float | None = Field(
        default=None,
        description="Previous period value for comparison"
    )
    unit: str = Field(
        default="",
        max_length=20,
        description="Unit of measurement (e.g., '%', 'USD', 'Index')"
    )
    trend: Trend = Field(description="Direction of recent movement")
    impact_assessment: Impact = Field(
        description="Expected impact on markets (positive/negative/neutral)"
    )
    impact_reason: str = Field(
        default="",
        max_length=500,
        description="Brief explanation of the impact assessment"
    )
    as_of_date: datetime = Field(
        default_factory=datetime.now,
        description="Date the indicator value applies to"
    )

    @property
    def change(self) -> float | None:
        """Calculate change from previous value."""
        if self.previous_value is None:
            return None
        return self.current_value - self.previous_value

    @property
    def change_percent(self) -> float | None:
        """Calculate percentage change from previous value."""
        if self.previous_value is None or self.previous_value == 0:
            return None
        return ((self.current_value - self.previous_value) / abs(self.previous_value)) * 100


class NewsItem(BaseModel):
    """
    A news article with relevance scoring.

    Represents a news item that may impact markets or specific stocks.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    source: str = Field(
        min_length=1,
        max_length=100,
        description="News source name"
    )
    headline: str = Field(
        min_length=1,
        max_length=500,
        description="Article headline"
    )
    url: Url = Field(
        default=None,
        description="Link to the article"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Publication time"
    )
    relevance_score: Score = Field(
        default=0.5,
        description="Relevance to financial markets (0-1)"
    )
    sentiment: Impact = Field(
        default=Impact.NEUTRAL,
        description="Sentiment assessment"
    )
    tickers_mentioned: list[Ticker] = Field(
        default_factory=list,
        max_length=20,
        description="Stock tickers mentioned in the article"
    )
    summary: str | None = Field(
        default=None,
        max_length=1000,
        description="Brief summary or description"
    )

    @field_validator("tickers_mentioned")
    @classmethod
    def _dedupe_tickers(cls, v: list[str]) -> list[str]:
        """Remove duplicate tickers while preserving order."""
        seen = set()
        result = []
        for ticker in v:
            t = ticker.upper()
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result


class MarketSignal(BaseModel):
    """
    A market signal derived from analysis.

    Represents an actionable signal with supporting evidence.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    signal_type: SignalType = Field(description="Type of signal (buy/sell/hold/watch)")
    strength: Strength = Field(description="Signal strength")
    ticker: Ticker | None = Field(
        default=None,
        description="Specific ticker if signal is stock-specific"
    )
    confidence: Score = Field(
        default=0.5,
        description="Confidence in the signal (0-1)"
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Evidence supporting the signal"
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Evidence contradicting the signal"
    )
    timeframe: Timeframe = Field(
        default=Timeframe.MEDIUM,
        description="Relevant timeframe for the signal"
    )
    generated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("supporting_evidence", "contradicting_evidence")
    @classmethod
    def _clean_evidence(cls, v: list[str]) -> list[str]:
        """Filter out empty evidence strings."""
        return [e.strip() for e in v if e and e.strip()]

    @property
    def evidence_ratio(self) -> float:
        """Ratio of supporting to total evidence."""
        total = len(self.supporting_evidence) + len(self.contradicting_evidence)
        if total == 0:
            return 0.5
        return len(self.supporting_evidence) / total


# ============================================================================
# Serialization helpers
# ============================================================================

def to_json_dict(model: BaseModel) -> dict:
    """Convert model to JSON-serializable dict."""
    return model.model_dump(mode="json")


def from_json_dict[T: BaseModel](model_class: type[T], data: dict) -> T:
    """Create model instance from JSON dict."""
    return model_class.model_validate(data)
