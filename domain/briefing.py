"""
Daily Market Briefing domain logic.

Combines economic calendar events with market news
to generate a morning briefing summary.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from datetime import date as date_type
from enum import Enum

from pydantic import BaseModel, Field

from .primitives import Observation
from .models import NewsItem, Impact


class EventImpact(str, Enum):
    """Impact level of economic event."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EconomicEvent(BaseModel):
    """Economic calendar event for briefing."""
    model_config = {"frozen": True, "extra": "forbid"}

    event: str = Field(description="Event name (e.g., 'Nonfarm Payrolls')")
    country: str = Field(default="US", description="Country code")
    time: datetime = Field(description="Release time (UTC)")
    impact: EventImpact = Field(description="Market impact level")
    actual: float | None = Field(default=None, description="Released value")
    forecast: float | None = Field(default=None, description="Consensus estimate")
    previous: float | None = Field(default=None, description="Prior period value")
    unit: str = Field(default="", description="Unit of measurement")

    @property
    def is_released(self) -> bool:
        """Check if event data has been released."""
        return self.actual is not None

    @property
    def surprise(self) -> float | None:
        """Calculate surprise vs forecast (actual - forecast)."""
        if self.actual is None or self.forecast is None:
            return None
        return self.actual - self.forecast


class PreMarketMover(BaseModel):
    """Pre-market stock mover for briefing display."""
    model_config = {"frozen": True, "extra": "forbid"}

    ticker: str = Field(description="Stock ticker symbol")
    company_name: str = Field(default="", description="Company name")
    price: float = Field(description="Current pre-market price")
    change: float = Field(description="Price change from previous close")
    change_percent: float = Field(description="Percentage change")
    volume: int = Field(default=0, description="Pre-market volume")
    previous_close: float = Field(description="Previous close price")
    is_gainer: bool = Field(description="True if positive change")

    @property
    def formatted_change(self) -> str:
        """Format change with sign and percentage."""
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f} ({sign}{self.change_percent:.2f}%)"


class NewsPriority(str, Enum):
    """Priority level for news items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BriefingNewsItem(BaseModel):
    """News item for briefing display with impact scoring."""
    model_config = {"frozen": True, "extra": "forbid"}

    headline: str
    source: str
    url: str | None = None
    timestamp: datetime
    category: str = "market"  # market, fed, earnings, geopolitical
    priority: NewsPriority = NewsPriority.MEDIUM
    relevance_score: float = Field(default=0.5, ge=0, le=1)
    keywords: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)


class EarningsAnnouncement(BaseModel):
    """Earnings announcement for briefing display."""
    model_config = {"frozen": True, "extra": "forbid"}

    symbol: str = Field(description="Stock ticker symbol")
    date: date_type = Field(description="Report date")
    hour: str = Field(default="", description="bmo (before open), amc (after close), or empty")
    year: int = Field(default=0, description="Fiscal year")
    quarter: int = Field(default=0, description="Fiscal quarter (1-4)")
    eps_estimate: float | None = Field(default=None, description="EPS estimate")
    eps_actual: float | None = Field(default=None, description="Actual EPS if released")
    revenue_estimate: float | None = Field(default=None, description="Revenue estimate")
    revenue_actual: float | None = Field(default=None, description="Actual revenue if released")

    @property
    def timing_display(self) -> str:
        """Human-readable timing."""
        return {
            "bmo": "Before Open",
            "amc": "After Close",
            "": "TBD",
        }.get(self.hour, "TBD")

    @property
    def is_reported(self) -> bool:
        """Check if earnings have been reported."""
        return self.eps_actual is not None


class SurpriseDirection(str, Enum):
    """Direction of economic surprise vs forecast."""
    BEAT = "beat"       # Actual > Forecast (good for growth, bad for inflation)
    MISS = "miss"       # Actual < Forecast
    IN_LINE = "in_line" # Within ~0.1% of forecast


class HistoricalReaction(BaseModel):
    """Historical market reaction to an economic event."""
    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str = Field(description="Event type code (NFP, CPI, GDP, FOMC)")
    event_name: str = Field(description="Human-readable event name")
    event_date: date_type = Field(description="Date of the historical event")
    actual: float | None = Field(default=None, description="Actual released value")
    forecast: float | None = Field(default=None, description="Consensus forecast")
    surprise_direction: SurpriseDirection = Field(description="Beat/miss/in-line")
    spy_reaction_1d: float = Field(description="SPY % change next trading day")
    spy_reaction_5d: float | None = Field(default=None, description="SPY % change over 5 days")

    @property
    def summary(self) -> str:
        """Generate summary like 'Last NFP beat → SPY +1.2%'."""
        direction = self.surprise_direction.value
        sign = "+" if self.spy_reaction_1d >= 0 else ""
        return f"Last {self.event_type} {direction} → SPY {sign}{self.spy_reaction_1d:.1f}%"


class DailyBriefing(BaseModel):
    """Daily market briefing combining calendar + news."""
    model_config = {"extra": "forbid"}

    date: date_type = Field(description="Briefing date")
    generated_at: datetime = Field(default_factory=datetime.now)

    # Economic calendar
    events_today: list[EconomicEvent] = Field(
        default_factory=list,
        description="Today's economic releases"
    )
    events_upcoming: list[EconomicEvent] = Field(
        default_factory=list,
        description="Next 3 days, HIGH impact only"
    )
    next_major_event: EconomicEvent | None = Field(
        default=None,
        description="Next HIGH impact event for countdown"
    )

    # Pre-market movers
    premarket_gainers: list[PreMarketMover] = Field(
        default_factory=list,
        description="Top pre-market gainers"
    )
    premarket_losers: list[PreMarketMover] = Field(
        default_factory=list,
        description="Top pre-market losers"
    )

    # Earnings calendar
    earnings_today: list[EarningsAnnouncement] = Field(
        default_factory=list,
        description="Today's major earnings announcements"
    )
    earnings_before_open: list[EarningsAnnouncement] = Field(
        default_factory=list,
        description="Earnings before market open"
    )
    earnings_after_close: list[EarningsAnnouncement] = Field(
        default_factory=list,
        description="Earnings after market close"
    )

    # Market news
    market_news: list[BriefingNewsItem] = Field(
        default_factory=list,
        description="Top market-moving news"
    )
    fed_news: list[BriefingNewsItem] = Field(
        default_factory=list,
        description="Fed/monetary policy news"
    )

    # Historical context for today's events
    historical_context: dict[str, HistoricalReaction] = Field(
        default_factory=dict,
        description="Most recent reaction for each event type (NFP, CPI, etc.)"
    )

    @property
    def has_earnings_today(self) -> bool:
        """Check if there are earnings announcements today."""
        return len(self.earnings_today) > 0

    @property
    def has_high_impact_today(self) -> bool:
        """Check if there are HIGH impact events today."""
        return any(e.impact == EventImpact.HIGH for e in self.events_today)

    @property
    def time_to_next_major(self) -> timedelta | None:
        """Time until next major event."""
        if not self.next_major_event:
            return None
        return self.next_major_event.time - datetime.now()


def _observation_to_event(obs: Observation) -> EconomicEvent:
    """Convert calendar Observation to EconomicEvent."""
    data = obs.data
    return EconomicEvent(
        event=data.get("event", "Unknown"),
        country=data.get("country", "US"),
        time=datetime.fromisoformat(data["time"]) if isinstance(data.get("time"), str) else obs.timestamp,
        impact=EventImpact(data.get("impact", "low")),
        actual=data.get("actual"),
        forecast=data.get("forecast"),
        previous=data.get("previous"),
        unit=data.get("unit", ""),
    )


def _observation_to_news(obs: Observation) -> BriefingNewsItem:
    """Convert news Observation to BriefingNewsItem with impact scoring."""
    from .news import (
        score_source_credibility,
        score_keywords,
        extract_tickers,
        MARKET_KEYWORDS,
    )

    data = obs.data
    headline = data.get("title") or data.get("headline", "")
    description = data.get("description", "")
    text = f"{headline} {description}"

    # Categorize by keywords
    headline_lower = headline.lower()
    if any(kw in headline_lower for kw in ["fed", "fomc", "powell", "rate", "monetary"]):
        category = "fed"
    elif any(kw in headline_lower for kw in ["earnings", "profit", "revenue", "eps"]):
        category = "earnings"
    elif any(kw in headline_lower for kw in ["china", "russia", "war", "tariff", "election", "geopolitical"]):
        category = "geopolitical"
    else:
        category = "market"

    # Score the news item
    source = data.get("source", obs.source)
    source_score = score_source_credibility(source)
    keyword_score, keywords = score_keywords(text)
    tickers = extract_tickers(text)

    # Calculate relevance: weighted combination
    relevance = (source_score * 0.3) + (keyword_score * 0.5) + (0.2 if tickers else 0)
    relevance = min(1.0, round(relevance, 3))

    # Determine priority based on keywords and relevance
    critical_keywords = {"crash", "bankruptcy", "rate cut", "rate hike", "recession", "fomc", "fed"}
    high_keywords = {"earnings", "merger", "acquisition", "selloff", "rally", "inflation"}

    if any(kw in critical_keywords for kw in keywords) or relevance >= 0.8:
        priority = NewsPriority.CRITICAL
    elif any(kw in high_keywords for kw in keywords) or relevance >= 0.6:
        priority = NewsPriority.HIGH
    elif relevance >= 0.4:
        priority = NewsPriority.MEDIUM
    else:
        priority = NewsPriority.LOW

    return BriefingNewsItem(
        headline=headline,
        source=source,
        url=data.get("url"),
        timestamp=obs.timestamp,
        category=category,
        priority=priority,
        relevance_score=relevance,
        keywords=keywords[:5],  # Top 5 keywords
        tickers=tickers[:3],  # Top 3 tickers
    )


def generate_daily_briefing(
    calendar_observations: list[Observation],
    news_observations: list[Observation],
    briefing_date: date_type | None = None,
    max_news: int = 10,
) -> DailyBriefing:
    """
    Generate a daily market briefing from calendar and news data.

    Args:
        calendar_observations: Economic calendar events from CalendarAdapter
        news_observations: News items from RssAdapter
        briefing_date: Date for the briefing (defaults to today)
        max_news: Maximum number of news items to include

    Returns:
        DailyBriefing with organized events and news
    """
    briefing_date = briefing_date or date_type.today()
    now = datetime.now()

    # Convert calendar observations to events
    all_events = [_observation_to_event(obs) for obs in calendar_observations]

    # Split into today vs upcoming
    events_today = []
    events_upcoming = []
    next_major_event = None

    for event in sorted(all_events, key=lambda e: e.time):
        event_date = event.time.date()

        if event_date == briefing_date:
            events_today.append(event)
        elif event_date > briefing_date and event.impact == EventImpact.HIGH:
            events_upcoming.append(event)

        # Find next major event (HIGH impact, not yet released, in the future)
        if (
            event.impact == EventImpact.HIGH
            and not event.is_released
            and event.time > now
            and next_major_event is None
        ):
            next_major_event = event

    # Convert news observations
    all_news = [_observation_to_news(obs) for obs in news_observations]

    # Sort by timestamp (newest first) and take top N
    # Normalize to naive datetime for comparison (RSS feeds may have mixed tz awareness)
    def _sort_key(n):
        ts = n.timestamp
        if ts.tzinfo is not None:
            return ts.replace(tzinfo=None)
        return ts

    all_news.sort(key=_sort_key, reverse=True)
    top_news = all_news[:max_news]

    # Split news by category
    market_news = [n for n in top_news if n.category == "market"]
    fed_news = [n for n in top_news if n.category == "fed"]

    return DailyBriefing(
        date=briefing_date,
        generated_at=now,
        events_today=events_today,
        events_upcoming=events_upcoming[:5],  # Limit upcoming to 5
        next_major_event=next_major_event,
        market_news=market_news,
        fed_news=fed_news,
    )


def briefing_to_dict(briefing: DailyBriefing) -> dict:
    """Convert DailyBriefing to JSON-serializable dict for frontend."""
    return {
        "date": briefing.date.isoformat(),
        "generatedAt": briefing.generated_at.isoformat(),
        "eventsToday": [
            {
                "event": e.event,
                "time": e.time.isoformat(),
                "impact": e.impact.value,
                "actual": e.actual,
                "forecast": e.forecast,
                "previous": e.previous,
                "unit": e.unit,
                "isReleased": e.is_released,
            }
            for e in briefing.events_today
        ],
        "eventsUpcoming": [
            {
                "event": e.event,
                "time": e.time.isoformat(),
                "impact": e.impact.value,
                "forecast": e.forecast,
                "previous": e.previous,
                "unit": e.unit,
            }
            for e in briefing.events_upcoming
        ],
        "nextMajorEvent": {
            "event": briefing.next_major_event.event,
            "time": briefing.next_major_event.time.isoformat(),
            "impact": briefing.next_major_event.impact.value,
        } if briefing.next_major_event else None,
        "premarketGainers": [
            {
                "ticker": m.ticker,
                "companyName": m.company_name,
                "price": m.price,
                "change": m.change,
                "changePercent": m.change_percent,
                "volume": m.volume,
                "previousClose": m.previous_close,
                "isGainer": m.is_gainer,
            }
            for m in briefing.premarket_gainers
        ],
        "premarketLosers": [
            {
                "ticker": m.ticker,
                "companyName": m.company_name,
                "price": m.price,
                "change": m.change,
                "changePercent": m.change_percent,
                "volume": m.volume,
                "previousClose": m.previous_close,
                "isGainer": m.is_gainer,
            }
            for m in briefing.premarket_losers
        ],
        "earningsToday": [
            {
                "symbol": e.symbol,
                "date": e.date.isoformat(),
                "hour": e.hour,
                "timingDisplay": e.timing_display,
                "year": e.year,
                "quarter": e.quarter,
                "epsEstimate": e.eps_estimate,
                "epsActual": e.eps_actual,
                "revenueEstimate": e.revenue_estimate,
                "revenueActual": e.revenue_actual,
                "isReported": e.is_reported,
            }
            for e in briefing.earnings_today
        ],
        "earningsBeforeOpen": [
            {
                "symbol": e.symbol,
                "date": e.date.isoformat(),
                "hour": e.hour,
                "timingDisplay": e.timing_display,
                "year": e.year,
                "quarter": e.quarter,
                "epsEstimate": e.eps_estimate,
                "epsActual": e.eps_actual,
                "revenueEstimate": e.revenue_estimate,
                "revenueActual": e.revenue_actual,
                "isReported": e.is_reported,
            }
            for e in briefing.earnings_before_open
        ],
        "earningsAfterClose": [
            {
                "symbol": e.symbol,
                "date": e.date.isoformat(),
                "hour": e.hour,
                "timingDisplay": e.timing_display,
                "year": e.year,
                "quarter": e.quarter,
                "epsEstimate": e.eps_estimate,
                "epsActual": e.eps_actual,
                "revenueEstimate": e.revenue_estimate,
                "revenueActual": e.revenue_actual,
                "isReported": e.is_reported,
            }
            for e in briefing.earnings_after_close
        ],
        "hasEarningsToday": briefing.has_earnings_today,
        "marketNews": [
            {
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
                "timestamp": n.timestamp.isoformat(),
                "priority": n.priority.value,
                "relevanceScore": n.relevance_score,
                "category": n.category,
                "keywords": n.keywords,
                "tickers": n.tickers,
            }
            for n in briefing.market_news
        ],
        "fedNews": [
            {
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
                "timestamp": n.timestamp.isoformat(),
                "priority": n.priority.value,
                "relevanceScore": n.relevance_score,
                "category": n.category,
                "keywords": n.keywords,
                "tickers": n.tickers,
            }
            for n in briefing.fed_news
        ],
        "hasHighImpactToday": briefing.has_high_impact_today,
        "historicalContext": {
            event_type: {
                "eventType": reaction.event_type,
                "eventName": reaction.event_name,
                "eventDate": reaction.event_date.isoformat(),
                "actual": reaction.actual,
                "forecast": reaction.forecast,
                "surpriseDirection": reaction.surprise_direction.value,
                "spyReaction1d": reaction.spy_reaction_1d,
                "spyReaction5d": reaction.spy_reaction_5d,
                "summary": reaction.summary,
            }
            for event_type, reaction in briefing.historical_context.items()
        },
    }
