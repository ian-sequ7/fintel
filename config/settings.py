"""
Settings module - backward-compatible interface to configuration.

This module provides the old Settings interface for backward compatibility
while using the new TOML-based configuration system under the hood.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from functools import lru_cache
from typing import TYPE_CHECKING

from domain import Category
from .loader import get_config, ConfigError
from .schema import FintelConfig

if TYPE_CHECKING:
    from .schema import FintelConfig


@dataclass
class Settings:
    """
    Global configuration for fintel.

    This class bridges the old settings interface with the new config system.
    """

    _config: FintelConfig = field(default_factory=get_config)

    @property
    def cache_ttl(self) -> dict[Category, timedelta]:
        """Cache TTLs by category."""
        cfg = self._config.cache_ttl
        return {
            Category.PRICE: timedelta(minutes=cfg.price_minutes),
            Category.FUNDAMENTAL: timedelta(hours=cfg.fundamental_hours),
            Category.MACRO: timedelta(hours=cfg.macro_hours),
            Category.NEWS: timedelta(minutes=cfg.news_minutes),
            Category.SENTIMENT: timedelta(hours=cfg.sentiment_hours),
        }

    @property
    def rate_limits(self) -> dict[str, int]:
        """Rate limit settings (requests per minute)."""
        cfg = self._config.rate_limits
        return {
            "yahoo": cfg.yahoo,
            "fred": cfg.fred,
            "reddit": cfg.reddit,
            "rss": cfg.rss,
        }

    @property
    def rate_delays(self) -> dict[str, float]:
        """Minimum delay between requests (seconds)."""
        cfg = self._config.rate_limits
        return {
            "yahoo": cfg.yahoo_delay,
            "fred": cfg.fred_delay,
            "reddit": cfg.reddit_delay,
            "rss": cfg.rss_delay,
        }

    @property
    def watchlist(self) -> list[str]:
        """Default tickers to track."""
        return self._config.watchlist

    @property
    def pe_high_threshold(self) -> float:
        """PE above this = expensive."""
        return self._config.thresholds.valuation.pe_high

    @property
    def pe_low_threshold(self) -> float:
        """PE below this = cheap."""
        return self._config.thresholds.valuation.pe_low

    @property
    def sentiment_bullish_threshold(self) -> float:
        """Sentiment above this = bullish."""
        return 0.6  # TODO: Add to config schema

    @property
    def sentiment_bearish_threshold(self) -> float:
        """Sentiment below this = bearish."""
        return 0.4  # TODO: Add to config schema

    @property
    def request_timeout(self) -> float:
        """HTTP request timeout in seconds."""
        return self._config.http.timeout_seconds

    @property
    def user_agent(self) -> str:
        """HTTP User-Agent header."""
        return self._config.http.user_agent

    # New properties exposing full config
    @property
    def config(self) -> FintelConfig:
        """Access the full configuration object."""
        return self._config


@lru_cache
def get_settings() -> Settings:
    """Get singleton settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings from config file."""
    from .loader import reload_config
    reload_config()
    get_settings.cache_clear()
    return get_settings()


# Re-export for convenience
__all__ = ["Settings", "get_settings", "reload_settings", "ConfigError"]
