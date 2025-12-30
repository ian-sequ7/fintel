"""
Yahoo Finance adapter.

Most reliable free source for:
- Price data (real-time quotes, historical)
- Fundamentals (PE, market cap, revenue)
- Company news
- Analyst recommendations
"""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from domain import Observation, Category
from ports import FetchError, RateLimitError
from config import get_settings

from .base import BaseAdapter


@dataclass
class PriceData:
    """Typed price data from Yahoo."""
    symbol: str
    price: float
    previous_close: float
    change: float
    change_percent: float
    volume: int
    market_cap: float | None = None


@dataclass
class FundamentalData:
    """Typed fundamental data from Yahoo."""
    symbol: str
    pe_trailing: float | None
    pe_forward: float | None
    peg_ratio: float | None
    price_to_book: float | None
    revenue_growth: float | None
    profit_margin: float | None
    recommendation: str | None  # buy, hold, sell


@dataclass
class NewsItem:
    """Typed news item from Yahoo."""
    title: str
    url: str
    published: datetime | None
    source: str | None


class YahooAdapter(BaseAdapter):
    """
    Yahoo Finance data adapter.

    Provides price, fundamental, and news data.
    No API key required.
    """

    BASE_URL = "https://query1.finance.yahoo.com"

    @property
    def source_name(self) -> str:
        return "yahoo"

    @property
    def category(self) -> Category:
        return Category.PRICE  # Primary category

    @property
    def reliability(self) -> float:
        return 0.9  # Very reliable

    def _request(self, url: str) -> dict[str, Any]:
        """Make HTTP request to Yahoo API."""
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=settings.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError()
            raise FetchError(self.source_name, f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise FetchError(self.source_name, f"Connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise FetchError(self.source_name, f"Invalid JSON: {e}")

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Route to specific fetch method based on data_type."""
        data_type = kwargs.get("data_type", "price")
        ticker = kwargs.get("ticker")

        if not ticker:
            raise FetchError(self.source_name, "ticker is required")

        if data_type == "price":
            return self._fetch_price(ticker)
        elif data_type == "fundamentals":
            return self._fetch_fundamentals(ticker)
        elif data_type == "news":
            return self._fetch_news(ticker)
        else:
            raise FetchError(self.source_name, f"Unknown data_type: {data_type}")

    def _fetch_price(self, ticker: str) -> list[Observation]:
        """Fetch current price data."""
        url = f"{self.BASE_URL}/v8/finance/chart/{ticker}?interval=1d&range=1d"
        data = self._request(url)

        result = data.get("chart", {}).get("result", [])
        if not result:
            raise FetchError(self.source_name, f"No data for {ticker}")

        meta = result[0].get("meta", {})
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]

        price = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("previousClose", price)

        price_data = PriceData(
            symbol=meta.get("symbol", ticker),
            price=price,
            previous_close=prev_close,
            change=price - prev_close,
            change_percent=((price - prev_close) / prev_close * 100) if prev_close else 0,
            volume=quote.get("volume", [0])[-1] if quote.get("volume") else 0,
            market_cap=meta.get("marketCap"),
        )

        return [self._create_observation(
            data={
                "price": price_data.price,
                "previous_close": price_data.previous_close,
                "change": price_data.change,
                "change_percent": price_data.change_percent,
                "volume": price_data.volume,
                "market_cap": price_data.market_cap,
            },
            ticker=ticker,
        )]

    def _fetch_fundamentals(self, ticker: str) -> list[Observation]:
        """Fetch fundamental data (PE, growth, etc.)."""
        modules = "financialData,defaultKeyStatistics,recommendationTrend"
        url = f"{self.BASE_URL}/v10/finance/quoteSummary/{ticker}?modules={modules}"

        try:
            data = self._request(url)
        except FetchError:
            # Fundamentals endpoint may be restricted, return empty
            return []

        result = data.get("quoteSummary", {}).get("result", [{}])[0]
        fin = result.get("financialData", {})
        stats = result.get("defaultKeyStatistics", {})
        recs = result.get("recommendationTrend", {}).get("trend", [{}])[0]

        def _get_raw(d: dict, key: str) -> float | None:
            val = d.get(key, {})
            return val.get("raw") if isinstance(val, dict) else None

        fundamental_data = FundamentalData(
            symbol=ticker,
            pe_trailing=_get_raw(stats, "trailingPE"),
            pe_forward=_get_raw(stats, "forwardPE"),
            peg_ratio=_get_raw(stats, "pegRatio"),
            price_to_book=_get_raw(stats, "priceToBook"),
            revenue_growth=_get_raw(fin, "revenueGrowth"),
            profit_margin=_get_raw(fin, "profitMargins"),
            recommendation=recs.get("buy") and "buy" or recs.get("sell") and "sell" or "hold",
        )

        return [Observation(
            source=self.source_name,
            timestamp=datetime.now(),
            category=Category.FUNDAMENTAL,
            data={
                "pe_trailing": fundamental_data.pe_trailing,
                "pe_forward": fundamental_data.pe_forward,
                "peg_ratio": fundamental_data.peg_ratio,
                "price_to_book": fundamental_data.price_to_book,
                "revenue_growth": fundamental_data.revenue_growth,
                "profit_margin": fundamental_data.profit_margin,
                "recommendation": fundamental_data.recommendation,
            },
            ticker=ticker,
            reliability=self.reliability,
        )]

    def _fetch_news(self, ticker: str) -> list[Observation]:
        """Fetch company news."""
        url = f"{self.BASE_URL}/v1/finance/search?q={ticker}&newsCount=10"
        data = self._request(url)

        news_items = data.get("news", [])
        observations = []

        for item in news_items:
            pub_time = item.get("providerPublishTime")
            published = datetime.fromtimestamp(pub_time) if pub_time else None

            news = NewsItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                published=published,
                source=item.get("publisher"),
            )

            observations.append(Observation(
                source=self.source_name,
                timestamp=published or datetime.now(),
                category=Category.NEWS,
                data={
                    "title": news.title,
                    "url": news.url,
                    "publisher": news.source,
                },
                ticker=ticker,
                reliability=self.reliability,
            ))

        return observations

    # Convenience methods for cleaner API
    def get_price(self, ticker: str) -> list[Observation]:
        """Get current price for a ticker."""
        return self.fetch(ticker=ticker, data_type="price")

    def get_fundamentals(self, ticker: str) -> list[Observation]:
        """Get fundamental data for a ticker."""
        return self.fetch(ticker=ticker, data_type="fundamentals")

    def get_news(self, ticker: str) -> list[Observation]:
        """Get news for a ticker."""
        return self.fetch(ticker=ticker, data_type="news")
