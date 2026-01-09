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


class BriefingNewsItem(BaseModel):
    """News item for briefing display."""
    model_config = {"frozen": True, "extra": "forbid"}

    headline: str
    source: str
    url: str | None = None
    timestamp: datetime
    category: str = "market"  # market, fed, earnings, geopolitical


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

    # Market news
    market_news: list[BriefingNewsItem] = Field(
        default_factory=list,
        description="Top market-moving news"
    )
    fed_news: list[BriefingNewsItem] = Field(
        default_factory=list,
        description="Fed/monetary policy news"
    )

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
    """Convert news Observation to BriefingNewsItem."""
    data = obs.data
    headline = data.get("title") or data.get("headline", "")

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

    return BriefingNewsItem(
        headline=headline,
        source=data.get("source", obs.source),
        url=data.get("url"),
        timestamp=obs.timestamp,
        category=category,
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
        "marketNews": [
            {
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
                "timestamp": n.timestamp.isoformat(),
            }
            for n in briefing.market_news
        ],
        "fedNews": [
            {
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
                "timestamp": n.timestamp.isoformat(),
            }
            for n in briefing.fed_news
        ],
        "hasHighImpactToday": briefing.has_high_impact_today,
    }
