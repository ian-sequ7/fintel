"""
RSS news adapter.

Sources:
- Google News (market news)
- MarketWatch
- Reuters

No API key required.
"""

import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime

from domain import Observation, Category
from ports import FetchError
from config import get_settings

from .base import BaseAdapter


@dataclass
class NewsArticle:
    """Typed news article data."""
    title: str
    url: str
    published: datetime | None
    source: str
    description: str | None = None


# RSS feed URLs (8 sources)
RSS_FEEDS = {
    # Google News aggregators
    "google_market": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
    "google_economy": "https://news.google.com/rss/search?q=economy+finance&hl=en-US&gl=US&ceid=US:en",
    "google_fed": "https://news.google.com/rss/search?q=federal+reserve&hl=en-US&gl=US&ceid=US:en",

    # Major financial news
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "investing": "https://www.investing.com/rss/news.rss",

    # Sector-specific
    "seekingalpha": "https://seekingalpha.com/market_currents.xml",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
}


class RssAdapter(BaseAdapter):
    """
    RSS news feed adapter.

    Aggregates market news from multiple RSS sources.
    """

    @property
    def source_name(self) -> str:
        return "rss"

    @property
    def category(self) -> Category:
        return Category.NEWS

    @property
    def reliability(self) -> float:
        return 0.85  # Established news sources

    def _request_xml(self, url: str) -> ET.Element:
        """Fetch and parse RSS XML."""
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=settings.request_timeout) as resp:
                content = resp.read().decode("utf-8")
                return ET.fromstring(content)
        except urllib.error.HTTPError as e:
            raise FetchError(self.source_name, f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise FetchError(self.source_name, f"Connection error: {e.reason}")
        except ET.ParseError as e:
            raise FetchError(self.source_name, f"Invalid XML: {e}")

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse RSS date format."""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return None

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Fetch news from RSS feeds."""
        feeds = kwargs.get("feeds", list(RSS_FEEDS.keys()))
        limit = kwargs.get("limit", 50)

        if isinstance(feeds, str):
            feeds = [feeds]

        observations = []

        for feed_name in feeds:
            url = RSS_FEEDS.get(feed_name)
            if not url:
                continue

            try:
                root = self._request_xml(url)
            except FetchError:
                continue  # Try other feeds

            items = root.findall(".//item")

            for item in items[:limit]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pubdate_elem = item.find("pubDate")
                desc_elem = item.find("description")
                source_elem = item.find("source")

                title = title_elem.text if title_elem is not None else ""
                url = link_elem.text if link_elem is not None else ""
                published = self._parse_date(
                    pubdate_elem.text if pubdate_elem is not None else None
                )
                description = desc_elem.text if desc_elem is not None else None
                source = source_elem.text if source_elem is not None else feed_name

                if not title:
                    continue

                article = NewsArticle(
                    title=title,
                    url=url,
                    published=published,
                    source=source,
                    description=description[:200] if description else None,
                )

                observations.append(Observation(
                    source=self.source_name,
                    timestamp=published or datetime.now(),
                    category=Category.NEWS,
                    data={
                        "title": article.title,
                        "url": article.url,
                        "source": article.source,
                        "description": article.description,
                        "feed": feed_name,
                    },
                    ticker=None,  # Market news, not ticker-specific
                    reliability=self.reliability,
                ))

        if not observations:
            raise FetchError(self.source_name, "No news retrieved")

        return observations

    def get_market_news(self, limit: int = 50) -> list[Observation]:
        """Get general market news."""
        return self.fetch(feeds=["google_market", "marketwatch"], limit=limit)

    def get_economy_news(self, limit: int = 25) -> list[Observation]:
        """Get economy/finance news."""
        return self.fetch(feeds=["google_economy"], limit=limit)

    def get_all(self, limit: int = 50) -> list[Observation]:
        """Get news from all feeds."""
        return self.fetch(feeds=list(RSS_FEEDS.keys()), limit=limit)
