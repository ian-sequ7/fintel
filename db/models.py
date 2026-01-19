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
        except (json.JSONDecodeError, TypeError, ValueError):
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
        except (json.JSONDecodeError, TypeError, ValueError):
            return []


@dataclass
class PickPerformance:
    """Track pick performance over time."""
    id: str
    pick_id: str
    ticker: str
    timeframe: str  # short/medium/long
    entry_price: float
    entry_date: date
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    # 7-day performance
    price_7d: Optional[float] = None
    return_7d: Optional[float] = None
    # 30-day performance
    price_30d: Optional[float] = None
    return_30d: Optional[float] = None
    # 90-day performance
    price_90d: Optional[float] = None
    return_90d: Optional[float] = None
    # Outcomes
    target_hit: bool = False
    target_hit_date: Optional[date] = None
    stop_hit: bool = False
    stop_hit_date: Optional[date] = None
    # Status
    status: str = "active"  # active/won/lost/expired
    final_return: Optional[float] = None
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_winner(self) -> bool:
        """Check if this pick is a winner based on available data."""
        if self.target_hit:
            return True
        # Use best available return
        best_return = self.return_90d or self.return_30d or self.return_7d
        return best_return is not None and best_return > 0

    @property
    def current_return(self) -> Optional[float]:
        """Get the most recent return value."""
        return self.return_90d or self.return_30d or self.return_7d


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


@dataclass
class HedgeFund:
    """Hedge fund tracked for 13F filings."""
    id: str
    name: str
    cik: str  # SEC Central Index Key (10 digits, zero-padded)
    manager: str  # Fund manager name (e.g., "Warren Buffett")
    aum: Optional[float] = None  # Assets under management
    style: str = ""  # value/growth/quant/activist/macro
    is_active: bool = True
    last_filing_date: Optional[date] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def cik_padded(self) -> str:
        """Return CIK with leading zeros (10 digits)."""
        return self.cik.zfill(10)


@dataclass
class HedgeFundHolding:
    """Individual holding from a 13F filing."""
    id: str
    fund_id: str
    ticker: str
    cusip: str
    issuer_name: str
    shares: int
    value: int  # Value in dollars (as reported, may be in thousands)
    filing_date: date
    report_date: date  # Quarter end date
    # Change tracking
    prev_shares: Optional[int] = None
    prev_value: Optional[int] = None
    shares_change: Optional[int] = None
    shares_change_pct: Optional[float] = None
    action: str = "hold"  # new/increased/decreased/sold/hold
    # Position info
    portfolio_pct: Optional[float] = None
    rank: Optional[int] = None  # Position rank by value
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_new_position(self) -> bool:
        """Check if this is a new position."""
        return self.action == "new"

    @property
    def is_increased(self) -> bool:
        """Check if position was increased."""
        return self.action == "increased"

    @property
    def is_decreased(self) -> bool:
        """Check if position was decreased."""
        return self.action == "decreased"

    @property
    def is_sold(self) -> bool:
        """Check if position was fully sold."""
        return self.action == "sold"

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        action_str = {
            "new": "NEW POSITION",
            "increased": f"+{self.shares_change_pct:.1f}%" if self.shares_change_pct else "INCREASED",
            "decreased": f"{self.shares_change_pct:.1f}%" if self.shares_change_pct else "DECREASED",
            "sold": "SOLD OUT",
            "hold": "NO CHANGE",
        }.get(self.action, self.action.upper())
        return f"{self.ticker}: {self.shares:,} shares (${self.value:,}) - {action_str}"


@dataclass
class InsiderTransaction:
    """
    Insider transaction from SEC Form 4 filings.

    Used for insider cluster detection - 3+ C-suite buys in 30-60 days
    indicates ~7.8% annual alpha (2IQ Research).

    Data source: Finnhub /stock/insider-transactions
    """
    id: str
    ticker: str
    insider_name: str
    transaction_type: str  # buy/sell
    shares: int  # Absolute number of shares traded
    shares_after: Optional[int] = None  # Holdings after transaction
    transaction_date: Optional[date] = None
    filing_date: Optional[date] = None
    transaction_code: str = ""  # SEC Form 4 code (P=Purchase, S=Sale)
    transaction_price: Optional[float] = None
    officer_title: str = ""  # CEO, CFO, etc. (if available)
    is_c_suite: bool = False  # True for CEO, CFO, COO, CTO, etc.
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_buy(self) -> bool:
        """Check if this is a purchase."""
        return self.transaction_type == "buy"

    @property
    def is_sell(self) -> bool:
        """Check if this is a sale."""
        return self.transaction_type == "sell"

    @property
    def dollar_value(self) -> Optional[float]:
        """Calculate dollar value of transaction."""
        if self.transaction_price:
            return self.shares * self.transaction_price
        return None

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        action = "bought" if self.is_buy else "sold"
        price_str = f" @ ${self.transaction_price:.2f}" if self.transaction_price else ""
        title_str = f" ({self.officer_title})" if self.officer_title else ""
        return f"{self.insider_name}{title_str} {action} {self.shares:,} shares{price_str}"


@dataclass
class MarketRegimeRecord:
    """
    Market regime snapshot for enhanced scoring (v3).

    Tracks regime classification over time for:
    - Historical performance analysis by regime
    - Regime transition detection
    - Factor weight calibration
    """
    id: str
    regime: str  # bull/bear/sideways/high_vol
    spy_price: Optional[float] = None
    spy_sma_200: Optional[float] = None
    vix: Optional[float] = None
    spy_above_sma: Optional[bool] = None
    confidence: float = 0.0
    description: str = ""
    is_risk_on: bool = False
    recorded_at: datetime = field(default_factory=datetime.now)

    @property
    def is_bull(self) -> bool:
        return self.regime == "bull"

    @property
    def is_bear(self) -> bool:
        return self.regime == "bear"

    @property
    def is_high_vol(self) -> bool:
        return self.regime == "high_vol"


@dataclass
class EnhancedPick:
    """
    Enhanced stock pick from v3 scoring system.

    Contains full factor breakdown and regime context for:
    - Performance attribution
    - Factor contribution analysis
    - Position sizing decisions
    """
    id: str
    ticker: str
    timeframe: str  # short/medium/long
    sector: str
    score: float  # 0-100 composite
    conviction: int  # 1-10
    position_size: Optional[float] = None  # 0.01-0.08
    regime: str = "sideways"

    # Factor breakdown (0-100)
    quality_score: Optional[float] = None
    value_score: Optional[float] = None
    momentum_score: Optional[float] = None
    low_vol_score: Optional[float] = None
    smart_money_score: Optional[float] = None
    catalyst_score: Optional[float] = None

    # Weights used
    quality_weight: Optional[float] = None
    value_weight: Optional[float] = None
    momentum_weight: Optional[float] = None
    low_vol_weight: Optional[float] = None
    smart_money_weight: Optional[float] = None
    catalyst_weight: Optional[float] = None

    # Risk status
    passes_filters: bool = True
    filter_reason: Optional[str] = None
    data_completeness: Optional[float] = None

    # Standard pick fields
    thesis: Optional[str] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_factors: str = ""  # JSON list

    # Tracking
    regime_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def risk_factors_list(self) -> list[str]:
        """Parse risk factors from JSON."""
        if not self.risk_factors:
            return []
        try:
            return json.loads(self.risk_factors)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    @property
    def conviction_normalized(self) -> float:
        """Conviction on 0-1 scale for backward compatibility."""
        return self.score / 100.0

    @property
    def factor_summary(self) -> str:
        """One-line summary of factor scores."""
        factors = []
        if self.quality_score is not None:
            factors.append(f"Q:{self.quality_score:.0f}")
        if self.value_score is not None:
            factors.append(f"V:{self.value_score:.0f}")
        if self.momentum_score is not None:
            factors.append(f"M:{self.momentum_score:.0f}")
        if self.low_vol_score is not None:
            factors.append(f"LV:{self.low_vol_score:.0f}")
        if self.smart_money_score is not None:
            factors.append(f"SM:{self.smart_money_score:.0f}")
        if self.catalyst_score is not None:
            factors.append(f"C:{self.catalyst_score:.0f}")
        return " ".join(factors)
