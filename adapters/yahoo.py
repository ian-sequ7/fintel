"""
Yahoo Finance adapter.

Most reliable free source for:
- Price data (real-time quotes, historical)
- Fundamentals (PE, market cap, revenue)
- Company news
- Analyst recommendations

Uses yfinance library for fundamentals as the raw API now requires auth.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import yfinance as yf

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError

from .base import BaseAdapter

logger = logging.getLogger(__name__)


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
    sector: str | None = None
    industry: str | None = None


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

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Route to specific fetch method based on data_type."""
        data_type = kwargs.get("data_type", "price")
        ticker = kwargs.get("ticker")

        # Input validation
        if not ticker:
            raise ValidationError(
                reason="ticker parameter is required",
                field="ticker",
                source=self.source_name,
            )

        ticker = self._validate_ticker(ticker)

        valid_types = ("price", "fundamentals", "news")
        if data_type not in valid_types:
            raise ValidationError(
                reason=f"data_type must be one of {valid_types}, got '{data_type}'",
                field="data_type",
                value=data_type,
                source=self.source_name,
            )

        if data_type == "price":
            return self._fetch_price(ticker)
        elif data_type == "fundamentals":
            return self._fetch_fundamentals(ticker)
        else:  # news
            return self._fetch_news(ticker)

    def _fetch_price(self, ticker: str) -> list[Observation]:
        """Fetch current price data."""
        url = f"{self.BASE_URL}/v8/finance/chart/{ticker}?interval=1d&range=1d"
        data = self._http_get_json(url)

        result = data.get("chart", {}).get("result", [])
        if not result:
            raise DataError.empty(
                source=self.source_name,
                description=f"No price data returned for {ticker}",
            )

        meta = result[0].get("meta", {})
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]

        price = meta.get("regularMarketPrice")
        if price is None:
            raise DataError.missing(self.source_name, field="regularMarketPrice")

        # Try previousClose first, then chartPreviousClose as fallback
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose") or price

        price_data = PriceData(
            symbol=meta.get("symbol", ticker),
            price=price,
            previous_close=prev_close,
            change=price - prev_close,
            change_percent=((price - prev_close) / prev_close * 100) if prev_close else 0,
            volume=quote.get("volume", [0])[-1] if quote.get("volume") else 0,
            market_cap=meta.get("marketCap"),
        )

        logger.debug(
            f"Fetched price for {ticker}: ${price_data.price:.2f}",
            extra={
                "ticker": ticker,
                "price": price_data.price,
                "change_percent": price_data.change_percent,
            },
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
        """Fetch fundamental data (PE, growth, etc.) using yfinance library."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or info.get("regularMarketPrice") is None:
                raise DataError.empty(
                    source=self.source_name,
                    description=f"No fundamental data returned for {ticker}",
                )

            # Extract fundamental metrics
            fundamental_data = FundamentalData(
                symbol=ticker,
                pe_trailing=info.get("trailingPE"),
                pe_forward=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                revenue_growth=info.get("revenueGrowth"),
                profit_margin=info.get("profitMargins"),
                recommendation=info.get("recommendationKey", "hold"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )

            # Extract additional metrics for richer analysis
            additional_data = {
                "pe_trailing": fundamental_data.pe_trailing,
                "pe_forward": fundamental_data.pe_forward,
                "peg_ratio": fundamental_data.peg_ratio,
                "price_to_book": fundamental_data.price_to_book,
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "revenue_growth": fundamental_data.revenue_growth,
                "earnings_growth": info.get("earningsGrowth"),
                "profit_margin": fundamental_data.profit_margin,
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "recommendation": fundamental_data.recommendation,
                "analyst_rating": info.get("recommendationMean"),
                "price_target": info.get("targetMeanPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "beta": info.get("beta"),
                # Company info
                "company_name": info.get("shortName") or info.get("longName") or ticker,
                # Sector and industry for scoring
                "sector": fundamental_data.sector,
                "industry": fundamental_data.industry,
                # Technical data for momentum scoring
                "fifty_day_average": info.get("fiftyDayAverage"),
                "two_hundred_day_average": info.get("twoHundredDayAverage"),
                "average_volume": info.get("averageVolume"),
                "current_price": info.get("regularMarketPrice"),
            }

            logger.debug(
                f"Fetched fundamentals for {ticker}: PE={fundamental_data.pe_trailing}",
                extra={
                    "ticker": ticker,
                    "pe_trailing": fundamental_data.pe_trailing,
                    "pe_forward": fundamental_data.pe_forward,
                },
            )

            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.FUNDAMENTAL,
                data=additional_data,
                ticker=ticker,
                reliability=self.reliability,
            )]

        except Exception as e:
            logger.warning(
                f"Fundamentals unavailable for {ticker}: {e}",
                extra={"ticker": ticker},
            )
            raise FetchError(
                code="E999",
                message=f"Failed to fetch fundamentals for {ticker}: {e}",
                source=self.source_name,
            )

    def _fetch_news(self, ticker: str) -> list[Observation]:
        """Fetch company news."""
        # Get news count from config
        news_count = self._settings.config.data_sources.yahoo_news_count
        url = f"{self.BASE_URL}/v1/finance/search?q={ticker}&newsCount={news_count}"
        data = self._http_get_json(url)

        news_items = data.get("news", [])
        if not news_items:
            logger.debug(f"No news found for {ticker}")
            return []

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

        logger.debug(
            f"Fetched {len(observations)} news items for {ticker}",
            extra={"ticker": ticker, "count": len(observations)},
        )

        return observations

    def _fetch_price_history(self, ticker: str, days: int = 30) -> list[Observation]:
        """Fetch historical price data for charting."""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{days}d")

            if hist.empty:
                logger.debug(f"No price history for {ticker}")
                return []

            price_points = []
            for date, row in hist.iterrows():
                price_points.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })

            logger.debug(f"Fetched {len(price_points)} price points for {ticker}")

            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.PRICE,
                data={"price_history": price_points},
                ticker=ticker,
                reliability=self.reliability,
            )]

        except Exception as e:
            logger.warning(f"Price history unavailable for {ticker}: {e}")
            return []

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

    def get_price_history(self, ticker: str, days: int = 30) -> list[dict]:
        """Get historical price data for charting."""
        obs = self._fetch_price_history(ticker, days)
        if obs and "price_history" in obs[0].data:
            return obs[0].data["price_history"]
        return []
