"""
Finviz news adapter.

Scrapes ticker-specific news from Finviz quote pages.
No API - scraping HTML tables with BeautifulSoup.

Source: https://finviz.com/quote.ashx?t={ticker}

Rate limiting:
- Aggressive scraping can trigger IP blocks
- Use min_delay (1-2 seconds between requests)
- Respect robots.txt
- Set proper User-Agent

News table structure:
- Table class: "fullview-news-outer"
- Rows contain: timestamp, headline, source, URL
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from domain import Observation, Category
from domain.news import RawNewsItem
from ports import FetchError, ParseError, ValidationError

from .base import BaseAdapter

logger = logging.getLogger(__name__)


@dataclass
class FinvizNewsItem:
    """Typed news item from Finviz."""
    headline: str
    url: str
    source: str
    published: datetime
    ticker: str


class FinvizAdapter(BaseAdapter):
    """
    Finviz news scraper.

    Fetches ticker-specific news from Finviz quote pages.

    Features:
    - News headlines, sources, timestamps, URLs
    - Converts to RawNewsItem for aggregation
    - Rate limited (1-2s delay to avoid blocks)
    - Cached (30 min TTL)

    Limitations:
    - Scraping-based (may break if HTML changes)
    - Limited to ~10-20 news items per ticker
    - No API key available
    """

    BASE_URL = "https://finviz.com/quote.ashx"

    @property
    def source_name(self) -> str:
        return "finviz"

    @property
    def category(self) -> Category:
        return Category.NEWS

    @property
    def reliability(self) -> float:
        return 0.75  # Aggregator with varied sources

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Fetch news for a ticker from Finviz."""
        ticker = kwargs.get("ticker")

        if not ticker:
            raise ValidationError(
                reason="ticker parameter is required",
                field="ticker",
                source=self.source_name,
            )

        ticker = self._validate_ticker(ticker)

        # Fetch and parse news
        news_items = self._fetch_ticker_news(ticker)

        if not news_items:
            logger.warning(f"No news found for {ticker} on Finviz")
            return []

        # Convert to RawNewsItem and wrap in Observation
        observations = []
        for item in news_items:
            raw_news = RawNewsItem(
                title=item.headline,
                url=item.url,
                source=item.source,
                published=item.published,
                description=None,  # Finviz doesn't provide descriptions
                category_hint=None,
                source_ticker=ticker,  # Tag with source ticker
            )

            obs = self._create_observation(
                data={
                    "raw_news": raw_news.model_dump(),
                    "headline": item.headline,
                    "url": item.url,
                    "source": item.source,
                    "published": item.published.isoformat(),
                },
                ticker=ticker,
            )
            observations.append(obs)

        logger.debug(f"Fetched {len(observations)} news items for {ticker} from Finviz")
        return observations

    def _fetch_ticker_news(self, ticker: str) -> list[FinvizNewsItem]:
        """
        Fetch and parse news table from Finviz quote page.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of parsed news items

        Raises:
            FetchError: On HTTP or network errors
            ParseError: On HTML parse errors
        """
        url = f"{self.BASE_URL}?t={ticker}"

        try:
            html = self._http_get_text(url)
        except FetchError as e:
            # Check for common blocking scenarios
            if "403" in str(e) or "Forbidden" in str(e):
                logger.error(
                    f"Finviz blocked request (403 Forbidden). "
                    f"Possible causes: too many requests, User-Agent blocked, IP rate limit. "
                    f"Try increasing rate_delays.finviz in config."
                )
            raise

        try:
            return self._parse_news_table(html, ticker)
        except Exception as e:
            raise ParseError(
                source=self.source_name,
                format_type="html",
                reason=f"Failed to parse news table: {e}",
                raw_content=html[:500] if html else "",
                cause=e,
            )

    def _parse_news_table(self, html: str, ticker: str) -> list[FinvizNewsItem]:
        """
        Parse news table from Finviz HTML.

        News table structure (as of 2025):
        <table class="fullview-news-outer">
            <tr>
                <td class="news_date-cell">Jan-03-26 04:30PM</td>
                <td class="news-link-left">
                    <a href="..." class="tab-link-news">Headline here</a>
                    <span class="news-link-right">
                        <span class="news-source">Source Name</span>
                    </span>
                </td>
            </tr>
        </table>

        Args:
            html: Raw HTML from Finviz
            ticker: Ticker being scraped (for context)

        Returns:
            List of parsed news items
        """
        soup = BeautifulSoup(html, "html.parser")

        # Find news table
        news_table = soup.find("table", class_="fullview-news-outer")

        if not news_table:
            logger.warning(f"News table not found for {ticker} (HTML structure may have changed)")
            return []

        news_items = []
        rows = news_table.find_all("tr")

        for row in rows:
            try:
                # Extract timestamp
                date_cell = row.find("td", class_="news_date-cell")
                if not date_cell:
                    continue

                timestamp_text = date_cell.get_text(strip=True)
                published = self._parse_finviz_date(timestamp_text)

                if not published:
                    logger.debug(f"Could not parse date: {timestamp_text}")
                    continue

                # Extract headline and URL
                link = row.find("a", class_="tab-link-news")
                if not link:
                    continue

                headline = link.get_text(strip=True)
                url = link.get("href", "")

                if not headline or not url:
                    continue

                # Extract source
                source_span = row.find("span", class_="news-source")
                source = source_span.get_text(strip=True) if source_span else "Finviz"

                news_items.append(FinvizNewsItem(
                    headline=headline,
                    url=url,
                    source=source,
                    published=published,
                    ticker=ticker,
                ))

            except Exception as e:
                logger.debug(f"Skipping news row due to parse error: {e}")
                continue

        return news_items

    def _parse_finviz_date(self, date_str: str) -> datetime | None:
        """
        Parse Finviz date format.

        Formats observed:
        - "Jan-03-26 04:30PM"  (with time)
        - "Jan-03-26"          (date only)
        - "Today 04:30PM"      (today with time)
        - "Yesterday"          (yesterday)

        Args:
            date_str: Date string from Finviz

        Returns:
            Parsed datetime or None
        """
        date_str = date_str.strip()

        # Handle relative dates
        now = datetime.now()

        if date_str.lower().startswith("today"):
            # Extract time if present
            time_match = re.search(r"(\d{1,2}):(\d{2})(AM|PM)", date_str, re.I)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                ampm = time_match.group(3).upper()

                # Convert to 24-hour format
                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0

                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return now.replace(hour=12, minute=0, second=0, microsecond=0)

        if date_str.lower() == "yesterday":
            return now - timedelta(days=1)

        # Parse standard format: "Jan-03-26 04:30PM" or "Jan-03-26"
        # Format: MMM-DD-YY [HH:MMAM/PM]
        parts = date_str.split()
        date_part = parts[0] if parts else date_str
        time_part = parts[1] if len(parts) > 1 else None

        try:
            # Parse date part (MMM-DD-YY)
            date_obj = datetime.strptime(date_part, "%b-%d-%y")

            # Parse time part if present
            if time_part:
                time_match = re.match(r"(\d{1,2}):(\d{2})(AM|PM)", time_part, re.I)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    ampm = time_match.group(3).upper()

                    # Convert to 24-hour format
                    if ampm == "PM" and hour != 12:
                        hour += 12
                    elif ampm == "AM" and hour == 12:
                        hour = 0

                    date_obj = date_obj.replace(hour=hour, minute=minute)

            return date_obj

        except ValueError as e:
            logger.debug(f"Date parse error for '{date_str}': {e}")
            return None

    # Convenience methods
    def get_ticker_news(self, ticker: str) -> list[Observation]:
        """
        Get news for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of observations containing RawNewsItem data
        """
        return self.fetch(ticker=ticker)

    def get_raw_news_items(self, ticker: str) -> list[RawNewsItem]:
        """
        Get news as RawNewsItem objects (for direct use with news aggregator).

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of RawNewsItem objects
        """
        observations = self.fetch(ticker=ticker)
        return [
            RawNewsItem(**obs.data["raw_news"])
            for obs in observations
            if "raw_news" in obs.data
        ]
