from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
import time
import logging

from domain import Observation, Category
from ports import RateLimitError, FetchError
from config import get_settings

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL tracking."""

    __slots__ = ("data", "created_at", "ttl")

    def __init__(self, data: list[Observation], ttl: timedelta):
        self.data = data
        self.created_at = datetime.now()
        self.ttl = ttl

    def is_valid(self) -> bool:
        return datetime.now() - self.created_at < self.ttl


class RateLimiter:
    """Token bucket rate limiter."""

    __slots__ = ("max_requests", "window_seconds", "requests")

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[float] = []

    def acquire(self) -> None:
        """
        Acquire a request slot.

        Raises:
            RateLimitError: If rate limit exceeded
        """
        now = time.monotonic()

        # Prune old requests outside window
        cutoff = now - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]

        if len(self.requests) >= self.max_requests:
            oldest = min(self.requests)
            retry_after = timedelta(seconds=oldest + self.window_seconds - now)
            raise RateLimitError(retry_after=retry_after)

        self.requests.append(now)


class BaseAdapter(ABC):
    """
    Base class for all data source adapters.

    Provides:
    - Response caching with configurable TTL
    - Rate limiting
    - Error handling boilerplate
    """

    def __init__(self):
        settings = get_settings()
        self._cache: dict[str, CacheEntry] = {}
        self._rate_limiter = RateLimiter(
            max_requests=settings.rate_limits.get(self.source_name, 60)
        )
        self._settings = settings

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        ...

    @property
    @abstractmethod
    def category(self) -> Category:
        """Primary category of data this source provides."""
        ...

    @property
    def reliability(self) -> float:
        """Reliability score 0-1. Override in subclass if needed."""
        return 0.8

    def _cache_key(self, **kwargs) -> str:
        """Generate cache key from fetch parameters."""
        parts = [self.source_name]
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v}")
        return ":".join(parts)

    def _get_cached(self, key: str) -> list[Observation] | None:
        """Get cached observations if valid."""
        entry = self._cache.get(key)
        if entry and entry.is_valid():
            logger.debug(f"Cache hit: {key}")
            return entry.data
        return None

    def _set_cached(self, key: str, data: list[Observation]) -> None:
        """Cache observations with TTL."""
        ttl = self._settings.cache_ttl.get(self.category, timedelta(hours=1))
        self._cache[key] = CacheEntry(data, ttl)
        logger.debug(f"Cached: {key} (TTL={ttl})")

    def is_cache_valid(self) -> bool:
        """Check if any cached data is still valid."""
        return any(entry.is_valid() for entry in self._cache.values())

    def fetch(self, **kwargs) -> list[Observation]:
        """
        Fetch observations with caching and rate limiting.

        Raises:
            RateLimitError: If rate limit exceeded
            FetchError: If fetch fails
        """
        cache_key = self._cache_key(**kwargs)

        # Check cache first
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Rate limit check
        self._rate_limiter.acquire()

        # Delegate to subclass implementation
        try:
            observations = self._fetch_impl(**kwargs)
        except RateLimitError:
            raise
        except Exception as e:
            raise FetchError(self.source_name, str(e)) from e

        # Cache and return
        self._set_cached(cache_key, observations)
        return observations

    @abstractmethod
    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """
        Implementation-specific fetch logic.

        Subclasses implement this instead of fetch() to get
        automatic caching and rate limiting.
        """
        ...

    def _create_observation(self, data: dict[str, Any], ticker: str | None = None) -> Observation:
        """Helper to create an Observation with common fields."""
        return Observation(
            source=self.source_name,
            timestamp=datetime.now(),
            category=self.category,
            data=data,
            ticker=ticker,
            reliability=self.reliability,
        )
