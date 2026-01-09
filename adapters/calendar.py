"""
Finnhub Economic Calendar adapter.

Fetches economic events (GDP releases, FOMC decisions, jobs reports, etc.)
for the daily market briefing.

Uses Finnhub /calendar/economic endpoint.
Free tier: 60 API calls/minute.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from enum import Enum

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError

from .base import BaseAdapter

logger = logging.getLogger(__name__)


class EventImpact(str, Enum):
    """Impact level of economic event."""
    HIGH = "high"      # FOMC, NFP, CPI - major market movers
    MEDIUM = "medium"  # Housing starts, consumer sentiment
    LOW = "low"        # Minor regional data


@dataclass
class EconomicEvent:
    """Typed economic calendar event from Finnhub."""
    event: str              # "Nonfarm Payrolls", "FOMC Meeting"
    country: str            # "US"
    time: datetime          # Release time (UTC)
    impact: EventImpact     # High/Medium/Low
    actual: float | None    # Released value (None if pending)
    forecast: float | None  # Consensus estimate
    previous: float | None  # Prior period value
    unit: str               # "%", "K", "B"


class CalendarAdapter(BaseAdapter):
    """
    Finnhub Economic Calendar adapter.

    Fetches upcoming and recent economic events filtered to US-only.
    Rate limit: 60 calls/min (free tier)
    """

    BASE_URL = "https://finnhub.io/api/v1"

    @property
    def source_name(self) -> str:
        return "finnhub_calendar"

    @property
    def category(self) -> Category:
        return Category.MACRO

    @property
    def reliability(self) -> float:
        return 0.90  # Official economic data

    def _get_api_key(self) -> str | None:
        """Get Finnhub API key from config or environment."""
        key = self._settings.config.api_keys.finnhub
        if key:
            return key
        return os.environ.get("FINNHUB_API_KEY")

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Fetch economic calendar events."""
        api_key = self._get_api_key()
        if not api_key:
            raise FetchError(
                self.source_name,
                "Finnhub API key required. Set FINNHUB_API_KEY env var."
            )

        # Default to today + 7 days
        from_date = kwargs.get("from_date", date.today())
        to_date = kwargs.get("to_date", date.today() + timedelta(days=7))
        country_filter = kwargs.get("country", "US")

        if isinstance(from_date, datetime):
            from_date = from_date.date()
        if isinstance(to_date, datetime):
            to_date = to_date.date()

        url = (
            f"{self.BASE_URL}/calendar/economic"
            f"?from={from_date.isoformat()}"
            f"&to={to_date.isoformat()}"
            f"&token={api_key}"
        )

        data = self._http_get_json(url)

        if not data or "economicCalendar" not in data:
            raise DataError.empty(
                source=self.source_name,
                description="No economic calendar data returned",
            )

        events = data["economicCalendar"]
        observations = []

        for event_data in events:
            # Filter by country (US-only for v1)
            country = event_data.get("country", "")
            if country_filter and country != country_filter:
                continue

            # Parse impact level
            impact_str = event_data.get("impact", "low").lower()
            try:
                impact = EventImpact(impact_str)
            except ValueError:
                impact = EventImpact.LOW

            # Parse event time
            time_str = event_data.get("time", "")
            try:
                # Finnhub returns time in format like "2025-01-08 13:30:00"
                event_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Fall back to just the date
                event_time = datetime.combine(from_date, datetime.min.time())

            event = EconomicEvent(
                event=event_data.get("event", "Unknown Event"),
                country=country,
                time=event_time,
                impact=impact,
                actual=event_data.get("actual"),
                forecast=event_data.get("estimate"),
                previous=event_data.get("prev"),
                unit=event_data.get("unit", ""),
            )

            observations.append(Observation(
                source=self.source_name,
                timestamp=event_time,
                category=Category.MACRO,
                data={
                    "event": event.event,
                    "country": event.country,
                    "time": event_time.isoformat(),
                    "impact": event.impact.value,
                    "actual": event.actual,
                    "forecast": event.forecast,
                    "previous": event.previous,
                    "unit": event.unit,
                },
                ticker=None,
                reliability=self.reliability,
            ))

        if not observations:
            logger.warning(f"No {country_filter} economic events found for {from_date} to {to_date}")
            # Return empty list rather than raising - no events is valid
            return []

        logger.info(f"Fetched {len(observations)} economic events for {from_date} to {to_date}")
        return observations

    def get_todays_events(self) -> list[Observation]:
        """Get economic events for today only."""
        today = date.today()
        return self.fetch(from_date=today, to_date=today)

    def get_week_events(self) -> list[Observation]:
        """Get economic events for the next 7 days."""
        return self.fetch(from_date=date.today(), to_date=date.today() + timedelta(days=7))

    def get_high_impact_events(self, days: int = 7) -> list[Observation]:
        """Get only HIGH impact events for the next N days."""
        events = self.fetch(
            from_date=date.today(),
            to_date=date.today() + timedelta(days=days)
        )
        return [e for e in events if e.data.get("impact") == "high"]
