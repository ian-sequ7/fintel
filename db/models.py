"""
Database models for Fintel.

Dataclasses representing database entities for all pipeline data.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import json


@dataclass
class StockPick:
    """Stock pick recommendation."""
    id: str
    ticker: str
    timeframe: str  # short/medium/long
    conviction_score: float
    thesis: str
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_factors: str = ""  # JSON list
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def risk_factors_list(self) -> list[str]:
        """Parse risk factors from JSON."""
        if not self.risk_factors:
            return []
        try:
            return json.loads(self.risk_factors)
        except:
            return []


@dataclass
class StockMetrics:
    """Stock fundamentals and metrics."""
    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_trailing: Optional[float] = None
    pe_forward: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    avg_volume: Optional[int] = None
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PricePoint:
    """Historical price data point."""
    id: str
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MacroIndicator:
    """Macro economic indicator."""
    id: str
    series_id: str
    name: str
    value: float
    previous_value: Optional[float] = None
    unit: str = ""
    trend: str = "flat"  # up/down/flat
    source: str = "FRED"
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class MacroRisk:
    """Macro risk assessment."""
    id: str
    name: str
    severity: str  # low/medium/high
    description: str
    likelihood: float = 0.5
    affected_sectors: str = ""  # JSON list
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class NewsItem:
    """News article."""
    id: str
    headline: str
    source: str
    url: str
    category: str  # market/company/sector
    published_at: Optional[datetime] = None
    relevance_score: float = 0.5
    tickers_mentioned: str = ""  # JSON list
    excerpt: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def tickers_list(self) -> list[str]:
        """Parse tickers from JSON."""
        if not self.tickers_mentioned:
            return []
        try:
            return json.loads(self.tickers_mentioned)
        except:
            return []


@dataclass
class CongressTrade:
    """Congressional stock trade from Capitol Trades."""
    id: str
    politician: str
    party: str  # R/D/I
    chamber: str  # House/Senate
    state: str
    ticker: str
    issuer: str
    transaction_type: str  # buy/sell
    amount_low: int
    amount_high: int
    traded_date: Optional[date] = None
    disclosed_date: Optional[date] = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def amount_mid(self) -> float:
        """Middle of the amount range."""
        return (self.amount_low + self.amount_high) / 2

    @property
    def strength(self) -> float:
        """Signal strength based on trade size."""
        mid = self.amount_mid
        if mid <= 15000:
            return 0.3
        elif mid <= 50000:
            return 0.4
        elif mid <= 100000:
            return 0.5
        elif mid <= 250000:
            return 0.6
        elif mid <= 500000:
            return 0.7
        elif mid <= 1000000:
            return 0.8
        else:
            return 0.9

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        action = "bought" if self.transaction_type == "buy" else "sold"
        return (
            f"{self.politician} ({self.party}-{self.chamber}) {action} "
            f"{self.ticker} (${self.amount_low:,} - ${self.amount_high:,})"
        )


@dataclass
class OptionsActivity:
    """Unusual options activity signal."""
    id: str
    ticker: str
    option_type: str  # call/put
    strike: float
    expiry: date
    volume: int
    open_interest: int
    volume_oi_ratio: float
    implied_volatility: Optional[float] = None
    premium_total: Optional[float] = None
    direction: str = "buy"  # buy for calls, sell for puts
    strength: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        premium_str = f", ${self.premium_total/1000:.0f}K premium" if self.premium_total else ""
        return (
            f"Unusual {self.option_type.upper()} activity on {self.ticker}: "
            f"${self.strike:.0f} {self.expiry}, Volume/OI={self.volume_oi_ratio:.1f}x{premium_str}"
        )


@dataclass
class ScrapeRun:
    """Record of a scraping run."""
    id: Optional[int] = None
    source: str = ""  # congress/options
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    records_added: int = 0
    records_skipped: int = 0
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Duration of the scrape run in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
