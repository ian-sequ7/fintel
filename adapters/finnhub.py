"""
Finnhub adapter for stock data.

Alternative/fallback data source for:
- Real-time quotes
- Company profile
- Basic fundamentals

Free tier: 60 API calls/minute.
Requires free API key from: https://finnhub.io/register

Setup:
1. Register at https://finnhub.io/register (free)
2. Get API key from dashboard
3. Set in config.toml: [api_keys] finnhub = "your_key"
   Or environment: export FINNHUB_API_KEY="your_key"

API docs: https://finnhub.io/docs/api
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError

from .base import BaseAdapter
from .cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class FinnhubQuote:
    """Typed quote data from Finnhub."""
    symbol: str
    current: float
    high: float
    low: float
    open: float
    previous_close: float
    change: float
    change_percent: float
    timestamp: int


@dataclass
class FinnhubProfile:
    """Typed company profile from Finnhub."""
    symbol: str
    name: str
    country: str | None
    currency: str | None
    exchange: str | None
    ipo: str | None
    market_cap: float | None
    industry: str | None
    sector: str | None
    website: str | None


class FinnhubAdapter(BaseAdapter):
    """
    Finnhub data adapter.

    Provides real-time quotes and company profiles.
    No API key required for basic quote endpoint.

    Rate limit: 60 calls/min (free tier)
    """

    BASE_URL = "https://finnhub.io/api/v1"

    @property
    def source_name(self) -> str:
        return "finnhub"

    @property
    def category(self) -> Category:
        return Category.PRICE

    @property
    def reliability(self) -> float:
        return 0.85

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Route to specific fetch method based on data_type."""
        data_type = kwargs.get("data_type", "quote")
        ticker = kwargs.get("ticker")

        if not ticker:
            raise ValidationError(
                reason="ticker parameter is required",
                field="ticker",
                source=self.source_name,
            )

        ticker = self._validate_ticker(ticker)

        if data_type == "quote":
            return self._fetch_quote(ticker)
        elif data_type == "profile":
            return self._fetch_profile(ticker)
        else:
            raise ValidationError(
                reason=f"data_type must be 'quote' or 'profile', got '{data_type}'",
                field="data_type",
                value=data_type,
                source=self.source_name,
            )

    def _fetch_quote(self, ticker: str) -> list[Observation]:
        """Fetch real-time quote from Finnhub.

        Endpoint: /quote?symbol={ticker}
        Returns: c, h, l, o, pc (current, high, low, open, previous close)
        """
        api_key = self._get_api_key()
        url = f"{self.BASE_URL}/quote?symbol={ticker}"
        if api_key:
            url += f"&token={api_key}"

        data = self._http_get_json(url)

        # Check for valid response (c = current price)
        if data.get("c") is None or data.get("c") == 0:
            raise DataError.empty(
                source=self.source_name,
                description=f"No quote data for {ticker}",
            )

        current = data["c"]
        previous_close = data.get("pc", current)

        quote = FinnhubQuote(
            symbol=ticker,
            current=current,
            high=data.get("h", current),
            low=data.get("l", current),
            open=data.get("o", current),
            previous_close=previous_close,
            change=current - previous_close,
            change_percent=((current - previous_close) / previous_close * 100) if previous_close else 0,
            timestamp=data.get("t", 0),
        )

        logger.debug(f"Fetched Finnhub quote for {ticker}: ${quote.current:.2f}")

        return [self._create_observation(
            data={
                "price": quote.current,
                "previous_close": quote.previous_close,
                "change": round(quote.change, 4),
                "change_percent": round(quote.change_percent, 2),
                "high": quote.high,
                "low": quote.low,
                "open": quote.open,
            },
            ticker=ticker,
        )]

    def _fetch_profile(self, ticker: str) -> list[Observation]:
        """Fetch company profile from Finnhub.

        Uses persistent cache (profiles rarely change).
        """
        cache = get_cache()
        cache_ttl = timedelta(days=7)  # Profiles are very stable

        # Check cache first
        cached = cache.get("finnhub_profile", ticker=ticker)
        if cached is not None:
            logger.debug(f"Using cached Finnhub profile for {ticker}")
            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.FUNDAMENTAL,
                data=cached,
                ticker=ticker,
                reliability=self.reliability,
            )]

        api_key = self._get_api_key()
        url = f"{self.BASE_URL}/stock/profile2?symbol={ticker}"
        if api_key:
            url += f"&token={api_key}"

        data = self._http_get_json(url)

        if not data or not data.get("name"):
            raise DataError.empty(
                source=self.source_name,
                description=f"No profile data for {ticker}",
            )

        profile = FinnhubProfile(
            symbol=ticker,
            name=data.get("name", ticker),
            country=data.get("country"),
            currency=data.get("currency"),
            exchange=data.get("exchange"),
            ipo=data.get("ipo"),
            market_cap=data.get("marketCapitalization"),
            industry=data.get("finnhubIndustry"),
            sector=None,  # Finnhub uses industry, not sector
            website=data.get("weburl"),
        )

        result = {
            "company_name": profile.name,
            "country": profile.country,
            "currency": profile.currency,
            "exchange": profile.exchange,
            "ipo_date": profile.ipo,
            "market_cap": profile.market_cap * 1_000_000 if profile.market_cap else None,  # Convert to full value
            "industry": profile.industry,
            "website": profile.website,
        }

        # Cache the result
        cache.set("finnhub_profile", result, cache_ttl, ticker=ticker)

        logger.debug(f"Fetched Finnhub profile for {ticker}: {profile.name}")

        return [Observation(
            source=self.source_name,
            timestamp=datetime.now(),
            category=Category.FUNDAMENTAL,
            data=result,
            ticker=ticker,
            reliability=self.reliability,
        )]

    def _get_api_key(self) -> str | None:
        """Get Finnhub API key from config or environment."""
        # Check config first
        key = self._settings.config.api_keys.finnhub
        if key:
            return key
        # Fall back to environment variable
        return os.environ.get("FINNHUB_API_KEY")

    def is_configured(self) -> bool:
        """Check if Finnhub adapter has API key configured."""
        return self._get_api_key() is not None

    # Convenience methods
    def get_quote(self, ticker: str) -> list[Observation]:
        """Get real-time quote for a ticker."""
        return self.fetch(ticker=ticker, data_type="quote")

    def get_profile(self, ticker: str) -> list[Observation]:
        """Get company profile for a ticker."""
        return self.fetch(ticker=ticker, data_type="profile")
