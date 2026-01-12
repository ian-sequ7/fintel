"""
Economic Calendar adapter.

Provides economic calendar data for daily market briefings using a hybrid approach:
1. Finnhub Earnings Calendar (FREE tier) - earnings announcements
2. Finnhub IPO Calendar (FREE tier) - upcoming IPOs
3. FRED Release Dates API (FREE with key) - major economic releases
4. Curated high-impact events - fallback for NFP, CPI, FOMC, etc.

Note: Finnhub /calendar/economic requires premium tier (403 on free).

TRACKED EVENT TYPES (via FRED API):
- Employment Situation (NFP) - First Friday of month
- Consumer Price Index (CPI) - Mid-month
- GDP - End of quarter
- Personal Income/PCE - End of month
- Retail Sales - Mid-month
- Housing Starts - Mid-month
- ISM Manufacturing PMI - First business day

NOT TRACKED (require premium APIs or manual curation):
- CB Employment Trends Index (Conference Board - no free API)
- FOMC Member Speeches (Fed calendar - manual only, frequently change)
- Treasury Auctions (Treasury operations, not economic data)
- Regional Fed surveys (Philly Fed, Empire, etc.)
- Consumer confidence surveys (non-govt)

SETUP REQUIRED:
- FRED API key: Set FINTEL_FRED_KEY in .env
  Get free key at: https://fred.stlouisfed.org/docs/api/api_key.html
- Without FRED key, only Finnhub premium economic calendar will be attempted

Free tier limits: 60 API calls/minute (Finnhub), unlimited (FRED CSV).
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError

from .base import BaseAdapter

logger = logging.getLogger(__name__)


# Major FRED release IDs for high-impact economic events
# Note: FOMC (release 101) removed - FRED returns daily Fed communications, not actual meeting dates.
# FOMC meeting dates should be sourced from Federal Reserve calendar directly.
FRED_MAJOR_RELEASES = {
    50: ("Employment Situation", "NFP", "high"),        # Nonfarm Payrolls
    10: ("Consumer Price Index", "CPI", "high"),        # Inflation
    53: ("Gross Domestic Product", "GDP", "high"),      # GDP
    54: ("Personal Income and Outlays", "PCE", "high"), # PCE Inflation
    46: ("Retail Sales", "Retail", "medium"),           # Consumer spending
    13: ("Housing Starts", "Housing", "medium"),        # Housing market
    83: ("ISM Manufacturing PMI", "PMI", "medium"),     # Business activity
}


class EventImpact(str, Enum):
    """Impact level of economic event."""
    HIGH = "high"      # NFP, CPI, GDP, PCE - major market movers
    MEDIUM = "medium"  # Housing starts, consumer sentiment
    LOW = "low"        # Minor regional data


@dataclass
class EconomicEvent:
    """Typed economic calendar event from Finnhub or FRED."""
    event: str              # "Nonfarm Payrolls", "FOMC Meeting"
    country: str            # "US"
    time: datetime          # Release time (UTC)
    impact: EventImpact     # High/Medium/Low
    actual: float | None    # Released value (None if pending)
    forecast: float | None  # Consensus estimate
    previous: float | None  # Prior period value
    unit: str               # "%", "K", "B"


@dataclass
class EarningsEvent:
    """Earnings announcement from Finnhub calendar."""
    symbol: str             # Stock ticker
    date: date              # Report date
    hour: str               # "bmo" (before open), "amc" (after close), "" (TBD)
    year: int               # Fiscal year
    quarter: int            # Fiscal quarter (1-4)
    eps_estimate: float | None
    eps_actual: float | None
    revenue_estimate: float | None
    revenue_actual: float | None


@dataclass
class IpoEvent:
    """IPO event from Finnhub calendar."""
    symbol: str             # Stock ticker
    name: str               # Company name
    date: date              # Expected date
    exchange: str           # Exchange (NASDAQ, NYSE)
    price_range: str        # e.g., "$16.00-18.00"
    shares: int             # Number of shares
    status: str             # "expected", "priced", "withdrawn", "filed"


class CalendarAdapter(BaseAdapter):
    """
    Hybrid Economic Calendar adapter.

    Provides calendar data from multiple free sources:
    - Finnhub Earnings Calendar (FREE) - earnings dates with timing
    - Finnhub IPO Calendar (FREE) - upcoming IPOs
    - FRED Release Dates API (FREE with key) - major economic releases
    - Curated events - fallback for high-impact events

    Note: Finnhub /calendar/economic requires premium (403 on free tier).
    Rate limit: 60 calls/min (Finnhub)
    """

    BASE_URL = "https://finnhub.io/api/v1"
    FRED_API_URL = "https://api.stlouisfed.org/fred"

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

    # =========================================================================
    # FREE TIER CALENDAR METHODS (Earnings, IPO, FRED)
    # =========================================================================

    def _get_fred_api_key(self) -> str | None:
        """Get FRED API key from config or environment."""
        key = self._settings.config.api_keys.fred
        if key:
            return key
        return os.environ.get("FRED_API_KEY")

    def get_earnings_calendar(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
    ) -> list[EarningsEvent]:
        """
        Fetch earnings calendar from Finnhub (FREE tier).

        Args:
            from_date: Start date (default: today)
            to_date: End date (default: today + 7 days)
            symbol: Filter by specific ticker (optional)

        Returns:
            List of EarningsEvent objects sorted by date
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Finnhub API key not configured for earnings calendar")
            return []

        from_date = from_date or date.today()
        to_date = to_date or (date.today() + timedelta(days=7))

        url = (
            f"{self.BASE_URL}/calendar/earnings"
            f"?from={from_date.isoformat()}"
            f"&to={to_date.isoformat()}"
            f"&token={api_key}"
        )
        if symbol:
            url += f"&symbol={symbol}"

        try:
            data = self._http_get_json(url)
        except FetchError as e:
            logger.warning(f"Failed to fetch earnings calendar: {e}")
            return []

        if not data or "earningsCalendar" not in data:
            logger.debug("No earnings data returned")
            return []

        earnings = []
        for item in data["earningsCalendar"]:
            try:
                event_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
                earnings.append(EarningsEvent(
                    symbol=item.get("symbol", ""),
                    date=event_date,
                    hour=item.get("hour", ""),
                    year=item.get("year", 0),
                    quarter=item.get("quarter", 0),
                    eps_estimate=item.get("epsEstimate"),
                    eps_actual=item.get("epsActual"),
                    revenue_estimate=item.get("revenueEstimate"),
                    revenue_actual=item.get("revenueActual"),
                ))
            except (KeyError, ValueError) as e:
                logger.debug(f"Skipping malformed earnings entry: {e}")
                continue

        # Sort by date, then by hour (bmo before amc)
        hour_order = {"bmo": 0, "": 1, "amc": 2}
        earnings.sort(key=lambda e: (e.date, hour_order.get(e.hour, 1)))

        logger.info(f"Fetched {len(earnings)} earnings events for {from_date} to {to_date}")
        return earnings

    def get_ipo_calendar(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[IpoEvent]:
        """
        Fetch IPO calendar from Finnhub (FREE tier).

        Args:
            from_date: Start date (default: today)
            to_date: End date (default: today + 14 days)

        Returns:
            List of IpoEvent objects sorted by date
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Finnhub API key not configured for IPO calendar")
            return []

        from_date = from_date or date.today()
        to_date = to_date or (date.today() + timedelta(days=14))

        url = (
            f"{self.BASE_URL}/calendar/ipo"
            f"?from={from_date.isoformat()}"
            f"&to={to_date.isoformat()}"
            f"&token={api_key}"
        )

        try:
            data = self._http_get_json(url)
        except FetchError as e:
            logger.warning(f"Failed to fetch IPO calendar: {e}")
            return []

        if not data or "ipoCalendar" not in data:
            # IPO endpoint returns array directly, not wrapped
            if isinstance(data, list):
                ipo_list = data
            else:
                logger.debug("No IPO data returned")
                return []
        else:
            ipo_list = data["ipoCalendar"]

        ipos = []
        for item in ipo_list:
            try:
                event_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
                ipos.append(IpoEvent(
                    symbol=item.get("symbol", ""),
                    name=item.get("name", ""),
                    date=event_date,
                    exchange=item.get("exchange", ""),
                    price_range=item.get("price", ""),
                    shares=item.get("numberOfShares", 0),
                    status=item.get("status", ""),
                ))
            except (KeyError, ValueError) as e:
                logger.debug(f"Skipping malformed IPO entry: {e}")
                continue

        # Sort by date
        ipos.sort(key=lambda i: i.date)

        logger.info(f"Fetched {len(ipos)} IPO events for {from_date} to {to_date}")
        return ipos

    def get_fred_release_dates(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        release_ids: list[int] | None = None,
    ) -> list[EconomicEvent]:
        """
        Fetch major economic release dates from FRED API.

        Uses FRED releases/dates endpoint to get scheduled dates for
        high-impact economic indicators (NFP, CPI, GDP, PCE, Retail, Housing, PMI).

        IMPORTANT: Requires FRED API key. Set FINTEL_FRED_KEY in .env.
        Get free key at: https://fred.stlouisfed.org/docs/api/api_key.html

        Events NOT included (require other sources):
        - CB Employment Trends Index (Conference Board)
        - FOMC Member Speeches (Fed calendar)
        - Treasury Auctions (TreasuryDirect.gov)

        Args:
            from_date: Start date (default: today)
            to_date: End date (default: today + 30 days)
            release_ids: Specific FRED release IDs (default: FRED_MAJOR_RELEASES)

        Returns:
            List of EconomicEvent objects for upcoming releases
        """
        api_key = self._get_fred_api_key()
        if not api_key:
            logger.warning(
                "FRED API key not configured. Set FINTEL_FRED_KEY in .env "
                "to enable economic calendar. Get free key at: "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )
            return []

        from_date = from_date or date.today()
        to_date = to_date or (date.today() + timedelta(days=30))
        release_ids = release_ids or list(FRED_MAJOR_RELEASES.keys())

        events = []

        for release_id in release_ids:
            if release_id not in FRED_MAJOR_RELEASES:
                continue

            name, short_name, impact_str = FRED_MAJOR_RELEASES[release_id]

            url = (
                f"{self.FRED_API_URL}/release/dates"
                f"?release_id={release_id}"
                f"&realtime_start={from_date.isoformat()}"
                f"&realtime_end={to_date.isoformat()}"
                f"&api_key={api_key}"
                f"&file_type=json"
            )

            try:
                data = self._http_get_json(url)
            except FetchError as e:
                logger.debug(f"Failed to fetch FRED release {release_id}: {e}")
                continue

            if not data or "release_dates" not in data:
                continue

            for rd in data["release_dates"]:
                try:
                    release_date_str = rd.get("date", "")
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                    # Only include future releases
                    if release_date.date() < date.today():
                        continue

                    impact = EventImpact.HIGH if impact_str == "high" else EventImpact.MEDIUM

                    events.append(EconomicEvent(
                        event=name,
                        country="US",
                        time=release_date.replace(hour=8, minute=30),  # Default 8:30 AM ET
                        impact=impact,
                        actual=None,
                        forecast=None,
                        previous=None,
                        unit="",
                    ))
                except (KeyError, ValueError) as e:
                    logger.debug(f"Skipping malformed FRED release date: {e}")
                    continue

        # Sort by date
        events.sort(key=lambda e: e.time)

        logger.info(f"Fetched {len(events)} FRED release dates for {from_date} to {to_date}")
        return events

    def get_hybrid_calendar(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        include_earnings: bool = True,
        include_ipos: bool = False,
        include_economic: bool = True,
    ) -> dict[str, Any]:
        """
        Get combined calendar data from all free sources.

        This is the main entry point for the daily briefing, combining:
        - Earnings calendar (Finnhub FREE)
        - IPO calendar (Finnhub FREE, optional)
        - Economic releases (FRED FREE)
        - Fallback to premium Finnhub economic if available

        Args:
            from_date: Start date (default: today)
            to_date: End date (default: today + 7 days)
            include_earnings: Include earnings announcements
            include_ipos: Include IPO events
            include_economic: Include economic releases

        Returns:
            Dictionary with categorized calendar events
        """
        from_date = from_date or date.today()
        to_date = to_date or (date.today() + timedelta(days=7))

        result: dict[str, Any] = {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "earnings": [],
            "ipos": [],
            "economic_events": [],
            "sources_used": [],
        }

        # Earnings Calendar (FREE)
        if include_earnings:
            earnings = self.get_earnings_calendar(from_date, to_date)
            result["earnings"] = [
                {
                    "symbol": e.symbol,
                    "date": e.date.isoformat(),
                    "hour": e.hour,
                    "year": e.year,
                    "quarter": e.quarter,
                    "eps_estimate": e.eps_estimate,
                    "eps_actual": e.eps_actual,
                    "revenue_estimate": e.revenue_estimate,
                    "revenue_actual": e.revenue_actual,
                }
                for e in earnings
            ]
            if earnings:
                result["sources_used"].append("finnhub_earnings")

        # IPO Calendar (FREE)
        if include_ipos:
            ipos = self.get_ipo_calendar(from_date, to_date)
            result["ipos"] = [
                {
                    "symbol": i.symbol,
                    "name": i.name,
                    "date": i.date.isoformat(),
                    "exchange": i.exchange,
                    "price_range": i.price_range,
                    "shares": i.shares,
                    "status": i.status,
                }
                for i in ipos
            ]
            if ipos:
                result["sources_used"].append("finnhub_ipo")

        # Economic Events (try FRED first, then Finnhub premium as fallback)
        if include_economic:
            # Try FRED release dates (FREE with API key)
            fred_events = self.get_fred_release_dates(from_date, to_date)
            if fred_events:
                result["economic_events"] = [
                    {
                        "event": e.event,
                        "country": e.country,
                        "time": e.time.isoformat(),
                        "impact": e.impact.value,
                        "actual": e.actual,
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "unit": e.unit,
                    }
                    for e in fred_events
                ]
                result["sources_used"].append("fred_releases")
                logger.info(f"Fetched {len(fred_events)} FRED economic events")
            else:
                # Fallback: try Finnhub economic calendar (premium, may 403)
                logger.debug("FRED calendar unavailable, trying Finnhub premium...")
                try:
                    finnhub_events = self.fetch(from_date=from_date, to_date=to_date)
                    result["economic_events"] = [obs.data for obs in finnhub_events]
                    if finnhub_events:
                        result["sources_used"].append("finnhub_economic")
                        logger.info(f"Fetched {len(finnhub_events)} Finnhub economic events")
                except (FetchError, DataError) as e:
                    logger.warning(
                        f"Economic calendar unavailable: {e}. "
                        "FRED API key not configured and Finnhub premium not available. "
                        "Set FINTEL_FRED_KEY in .env to enable economic calendar. "
                        "Note: Only major releases tracked (NFP, CPI, GDP, PCE, Retail, Housing, PMI). "
                        "Events like CB Employment Trends, Fed speeches, and Treasury auctions "
                        "require premium data sources."
                    )
                    # Both FRED and Finnhub failed - calendar will be empty
                    pass

        return result

    def get_todays_earnings(self, major_only: bool = True) -> list[EarningsEvent]:
        """Get earnings announcements for today.

        Args:
            major_only: If True, filter to well-known companies

        Returns:
            List of EarningsEvent for today, split by timing
        """
        today = date.today()
        earnings = self.get_earnings_calendar(from_date=today, to_date=today)

        if major_only:
            # Filter to companies with significant market presence
            # (has estimates, which indicates analyst coverage)
            earnings = [e for e in earnings if e.eps_estimate is not None]

        return earnings

    def get_week_earnings(self) -> dict[str, list[EarningsEvent]]:
        """Get earnings for the week grouped by day.

        Returns:
            Dictionary with date keys and lists of EarningsEvent
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=4)  # Friday

        earnings = self.get_earnings_calendar(from_date=week_start, to_date=week_end)

        by_day: dict[str, list[EarningsEvent]] = {}
        for e in earnings:
            day_key = e.date.isoformat()
            if day_key not in by_day:
                by_day[day_key] = []
            by_day[day_key].append(e)

        return by_day

    # =========================================================================
    # HISTORICAL EVENT REACTIONS
    # =========================================================================

    def get_historical_event_reactions(
        self,
        lookback_months: int = 6,
    ) -> dict[str, dict]:
        """
        Get historical market reactions to major economic events.

        Fetches the most recent occurrence of each major event type
        and calculates SPY's price reaction.

        Args:
            lookback_months: How far back to look for events (default 6 months)

        Returns:
            Dictionary of event_type -> reaction data:
            {
                "NFP": {
                    "event_type": "NFP",
                    "event_name": "Nonfarm Payrolls",
                    "event_date": "2025-01-10",
                    "actual": 256.0,
                    "forecast": 165.0,
                    "surprise_direction": "beat",
                    "spy_reaction_1d": 0.5,
                    "spy_reaction_5d": 1.2,
                },
                ...
            }
        """
        import yfinance as yf

        # Key events to track with their FRED series for actual values
        # Format: event_type -> (series_id, display_name, unit, is_inverse, transform_type)
        # is_inverse=True means lower is better (like CPI, unemployment)
        # transform_type: how to transform raw data into reported values
        #   - "mom_change": Month-over-month change (NFP)
        #   - "yoy_pct": Year-over-year percentage change (CPI)
        #   - "mom_pct": Month-over-month percentage change (Retail)
        #   - "level": Use raw value as-is (Unemployment, Housing)
        #   - "qoq_annualized": Quarterly % change annualized (GDP)
        EVENT_SERIES = {
            "NFP": ("PAYEMS", "Nonfarm Payrolls", "K", False, "mom_change"),
            "CPI": ("CPIAUCSL", "Consumer Price Index", "% YoY", True, "yoy_pct"),
            "GDP": ("GDP", "Gross Domestic Product", "% QoQ", False, "qoq_annualized"),
            "UNEMPLOYMENT": ("UNRATE", "Unemployment Rate", "%", True, "level"),
            "RETAIL": ("RSXFS", "Retail Sales", "% MoM", False, "mom_pct"),
            "HOUSING": ("HOUST", "Housing Starts", "K", False, "level"),
            # PMI: ISM Manufacturing PMI is not available in FRED (proprietary index)
            # MANEMP (Manufacturing Employment) is not a suitable proxy for the PMI index
        }

        reactions = {}
        lookback_start = date.today() - timedelta(days=lookback_months * 30)

        # Get SPY historical prices for reaction calculation
        try:
            spy_data = yf.download(
                "SPY",
                start=lookback_start.isoformat(),
                end=date.today().isoformat(),
                progress=False,
            )
            if spy_data.empty:
                logger.warning("No SPY data for historical reactions")
                return {}
        except Exception as e:
            logger.warning(f"Failed to fetch SPY data: {e}")
            return {}

        for event_type, (series_id, event_name, unit, is_inverse, transform_type) in EVENT_SERIES.items():
            try:
                # Get historical release dates and values from FRED
                release_dates = self._get_fred_release_history(
                    series_id, lookback_months, transform_type
                )

                if not release_dates:
                    logger.debug(f"No release history for {event_type}")
                    continue

                # Get the most recent release
                latest_release = release_dates[-1]
                release_date = latest_release["date"]
                actual_value = latest_release["value"]

                # Calculate forecast from historical trend
                # Use average of 3 prior values as proxy for market expectation
                forecast = None
                if len(release_dates) >= 4:
                    # Use 3 values before the latest (exclude latest actual)
                    prior_values = [r["value"] for r in release_dates[-4:-1]]
                    forecast = sum(prior_values) / len(prior_values)

                # Determine surprise direction
                if forecast is None or actual_value is None:
                    surprise = "in_line"
                else:
                    # For inverse metrics (CPI, unemployment), lower is better
                    if is_inverse:
                        if actual_value < forecast * 0.95:
                            surprise = "beat"
                        elif actual_value > forecast * 1.05:
                            surprise = "miss"
                        else:
                            surprise = "in_line"
                    else:
                        # For normal metrics (NFP, GDP, Retail), higher is better
                        if actual_value > forecast * 1.05:
                            surprise = "beat"
                        elif actual_value < forecast * 0.95:
                            surprise = "miss"
                        else:
                            surprise = "in_line"

                # Calculate SPY reaction
                spy_1d, spy_5d = self._calculate_spy_reaction(
                    spy_data, release_date
                )

                reactions[event_type] = {
                    "event_type": event_type,
                    "event_name": event_name,
                    "event_date": release_date.isoformat(),
                    "actual": actual_value,
                    "forecast": forecast,
                    "surprise_direction": surprise,
                    "spy_reaction_1d": round(spy_1d, 2) if spy_1d else 0.0,
                    "spy_reaction_5d": round(spy_5d, 2) if spy_5d else None,
                }

                logger.debug(
                    f"Historical reaction for {event_type}: "
                    f"{surprise}, SPY {'+' if spy_1d and spy_1d >= 0 else ''}{spy_1d:.2f}%"
                )

            except Exception as e:
                logger.warning(f"Failed to get historical reaction for {event_type}: {e}")
                continue

        logger.info(f"Fetched historical reactions for {len(reactions)} event types")
        return reactions

    def _get_fred_release_history(
        self,
        series_id: str,
        lookback_months: int = 6,
        transform_type: str = "level",
    ) -> list[dict]:
        """
        Get historical values for a FRED series with transformations.

        Args:
            series_id: FRED series ID (e.g., "PAYEMS", "CPIAUCSL")
            lookback_months: How far back to fetch data
            transform_type: How to transform raw data:
                - "level": Use raw value as-is
                - "mom_change": Month-over-month change (current - previous)
                - "mom_pct": Month-over-month percentage change
                - "yoy_pct": Year-over-year percentage change
                - "qoq_annualized": Quarter-over-quarter % change annualized

        Returns:
            List of {"date": date, "value": float} dicts with transformed values.
        """
        import csv
        import urllib.request
        from io import StringIO

        # Fetch extra data for transformations that need historical context
        # YoY needs 12 months prior, others need 1-3 months
        extra_months = 13 if transform_type == "yoy_pct" else 2
        fetch_start = date.today() - timedelta(days=(lookback_months + extra_months) * 30)

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Fintel/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
                reader = csv.reader(StringIO(content))
                next(reader)  # Skip header

                # First pass: collect all raw data points
                raw_data = []
                for row in reader:
                    if len(row) >= 2 and row[1] != ".":
                        try:
                            release_date = datetime.strptime(row[0], "%Y-%m-%d").date()
                            if release_date >= fetch_start:
                                value = float(row[1])
                                raw_data.append({
                                    "date": release_date,
                                    "value": value,
                                })
                        except (ValueError, IndexError):
                            continue

                if not raw_data:
                    return []

                # Second pass: apply transformations
                releases = []
                cutoff = date.today() - timedelta(days=lookback_months * 30)

                for i, item in enumerate(raw_data):
                    release_date = item["date"]

                    # Only include dates within the requested lookback period
                    if release_date < cutoff:
                        continue

                    if transform_type == "level":
                        # Use raw value as-is
                        transformed_value = item["value"]

                    elif transform_type == "mom_change":
                        # Month-over-month change (e.g., NFP jobs added)
                        if i == 0:
                            continue  # Skip first entry (no prior data)
                        transformed_value = item["value"] - raw_data[i - 1]["value"]

                    elif transform_type == "mom_pct":
                        # Month-over-month percentage change (e.g., Retail Sales)
                        if i == 0:
                            continue
                        prev_value = raw_data[i - 1]["value"]
                        if prev_value == 0:
                            continue
                        transformed_value = ((item["value"] - prev_value) / prev_value) * 100

                    elif transform_type == "yoy_pct":
                        # Year-over-year percentage change (e.g., CPI inflation)
                        # Find value from 12 months ago
                        year_ago_value = None
                        target_date = release_date - timedelta(days=365)

                        # Find closest data point to 12 months ago (within 45 days)
                        for j in range(max(0, i - 15), i):
                            days_diff = abs((raw_data[j]["date"] - target_date).days)
                            if days_diff <= 45:
                                year_ago_value = raw_data[j]["value"]
                                break

                        if year_ago_value is None or year_ago_value == 0:
                            continue

                        transformed_value = ((item["value"] - year_ago_value) / year_ago_value) * 100

                    elif transform_type == "qoq_annualized":
                        # Quarter-over-quarter percentage change, annualized (e.g., GDP)
                        # GDP data is quarterly, so previous entry is prior quarter
                        if i == 0:
                            continue
                        prev_value = raw_data[i - 1]["value"]
                        if prev_value == 0:
                            continue
                        qoq_pct = ((item["value"] - prev_value) / prev_value) * 100
                        # Annualize: compound 4 quarters
                        transformed_value = ((1 + qoq_pct / 100) ** 4 - 1) * 100

                    else:
                        logger.warning(f"Unknown transform_type: {transform_type}, using level")
                        transformed_value = item["value"]

                    releases.append({
                        "date": release_date,
                        "value": transformed_value,
                    })

                return releases

        except Exception as e:
            logger.debug(f"Failed to fetch FRED history for {series_id}: {e}")
            return []

    def _calculate_spy_reaction(
        self,
        spy_data,
        event_date: date,
    ) -> tuple[float | None, float | None]:
        """
        Calculate SPY price reaction after an economic event.

        Returns (1-day % change, 5-day % change).
        """
        import pandas as pd

        try:
            # Find the closest trading day on or after event date
            spy_dates = spy_data.index.date if hasattr(spy_data.index, 'date') else [d.date() for d in spy_data.index]

            # Find event day or next trading day
            event_idx = None
            for i, d in enumerate(spy_dates):
                if d >= event_date:
                    event_idx = i
                    break

            if event_idx is None or event_idx < 1:
                return None, None

            # Get prices
            # Handle both single-column and multi-column DataFrames
            close_col = spy_data["Close"]
            if hasattr(close_col, 'iloc'):
                pre_event = float(close_col.iloc[event_idx - 1])
                post_event_1d = float(close_col.iloc[event_idx])
                post_event_5d = float(close_col.iloc[min(event_idx + 4, len(close_col) - 1)])
            else:
                pre_event = float(close_col[event_idx - 1])
                post_event_1d = float(close_col[event_idx])
                post_event_5d = float(close_col[min(event_idx + 4, len(close_col) - 1)])

            # Calculate percentage changes
            spy_1d = ((post_event_1d - pre_event) / pre_event) * 100
            spy_5d = ((post_event_5d - pre_event) / pre_event) * 100

            return spy_1d, spy_5d

        except Exception as e:
            logger.debug(f"Failed to calculate SPY reaction: {e}")
            return None, None
