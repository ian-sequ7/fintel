from dataclasses import dataclass, field
from datetime import timedelta
from functools import lru_cache

from domain import Category


@dataclass
class Settings:
    """Global configuration for fintel."""

    # Cache TTLs by category
    cache_ttl: dict[Category, timedelta] = field(default_factory=lambda: {
        Category.PRICE: timedelta(minutes=1),
        Category.FUNDAMENTAL: timedelta(days=1),
        Category.MACRO: timedelta(weeks=1),
        Category.NEWS: timedelta(hours=1),
        Category.SENTIMENT: timedelta(hours=4),
    })

    # Rate limit settings (requests per minute)
    rate_limits: dict[str, int] = field(default_factory=lambda: {
        "yahoo": 60,
        "fred": 30,
        "reddit": 30,
        "rss": 60,
    })

    # Default tickers to track
    watchlist: list[str] = field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "JPM", "V",
    ])

    # Analysis thresholds
    pe_high_threshold: float = 30.0
    pe_low_threshold: float = 15.0
    sentiment_bullish_threshold: float = 0.6
    sentiment_bearish_threshold: float = 0.4

    # HTTP settings
    request_timeout: float = 10.0
    user_agent: str = "FintelBot/1.0"


@lru_cache
def get_settings() -> Settings:
    """Get singleton settings instance."""
    return Settings()
