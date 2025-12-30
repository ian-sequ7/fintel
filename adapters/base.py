"""
Base adapter with caching, rate limiting, and structured logging.

All adapters should inherit from BaseAdapter to get:
- Response caching with configurable TTL
- Rate limiting per source
- Structured logging at boundaries
- Common HTTP request handling
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
import json
import time
import logging
import urllib.request
import urllib.error

from domain import Observation, Category
from ports import RateLimitError, FetchError, ParseError, DataError, ErrorCode
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

    # ========================================================================
    # HTTP Helpers (shared by all adapters)
    # ========================================================================

    def _http_get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        """
        Make HTTP GET request with standardized error handling.

        Args:
            url: URL to fetch
            headers: Additional headers (User-Agent added automatically)
            timeout: Request timeout (defaults to config value)

        Returns:
            Response body as bytes

        Raises:
            RateLimitError: On 429 response
            FetchError: On other HTTP or network errors
        """
        settings = self._settings
        timeout = timeout or settings.request_timeout

        req_headers = {"User-Agent": settings.user_agent}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, headers=req_headers)

        # Log request
        logger.debug(
            f"HTTP GET {url}",
            extra={"source": self.source_name, "url": url},
        )
        start_time = time.monotonic()

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                elapsed = time.monotonic() - start_time

                # Log response
                logger.debug(
                    f"HTTP 200 OK ({len(data)} bytes, {elapsed:.2f}s)",
                    extra={
                        "source": self.source_name,
                        "url": url,
                        "status": 200,
                        "size": len(data),
                        "elapsed_ms": int(elapsed * 1000),
                    },
                )
                return data

        except urllib.error.HTTPError as e:
            elapsed = time.monotonic() - start_time
            logger.warning(
                f"HTTP {e.code} from {url} ({elapsed:.2f}s)",
                extra={
                    "source": self.source_name,
                    "url": url,
                    "status": e.code,
                    "elapsed_ms": int(elapsed * 1000),
                },
            )
            raise FetchError.from_http_error(
                source=self.source_name,
                status_code=e.code,
                url=url,
                response_body=e.reason,
            )

        except urllib.error.URLError as e:
            elapsed = time.monotonic() - start_time
            logger.warning(
                f"Network error for {url}: {e.reason} ({elapsed:.2f}s)",
                extra={
                    "source": self.source_name,
                    "url": url,
                    "error": str(e.reason),
                    "elapsed_ms": int(elapsed * 1000),
                },
            )
            raise FetchError.from_network_error(
                source=self.source_name,
                error=e,
                url=url,
            )

    def _http_get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP GET request and parse JSON response.

        Args:
            url: URL to fetch
            headers: Additional headers

        Returns:
            Parsed JSON as dict

        Raises:
            FetchError: On HTTP or network errors
            ParseError: On JSON parse errors
        """
        data = self._http_get(url, headers)

        try:
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(
                f"JSON parse error for {url}: {e}",
                extra={
                    "source": self.source_name,
                    "url": url,
                    "error": str(e),
                },
            )
            raise ParseError(
                source=self.source_name,
                format_type="json",
                reason=str(e),
                raw_content=data.decode("utf-8", errors="replace")[:500],
                cause=e,
            )

    def _http_get_text(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> str:
        """
        Make HTTP GET request and return text.

        Args:
            url: URL to fetch
            headers: Additional headers
            encoding: Text encoding

        Returns:
            Response as string
        """
        data = self._http_get(url, headers)
        return data.decode(encoding)

    # ========================================================================
    # Input Validation Helpers
    # ========================================================================

    def _validate_ticker(self, ticker: str) -> str:
        """
        Validate and normalize ticker symbol.

        Args:
            ticker: Ticker to validate

        Returns:
            Normalized ticker (uppercase)

        Raises:
            ValidationError: If ticker is invalid
        """
        from ports import ValidationError

        if not ticker:
            raise ValidationError.invalid_ticker(ticker, "Ticker cannot be empty")

        ticker = ticker.upper().strip()

        # Basic format validation: 1-10 chars, letters/numbers/dash/dot
        import re
        if not re.match(r'^[A-Z0-9.\-]{1,10}$', ticker):
            raise ValidationError.invalid_ticker(
                ticker,
                "Must be 1-10 uppercase letters, numbers, dots, or dashes"
            )

        return ticker

    def _validate_limit(self, limit: int, max_limit: int = 100) -> int:
        """
        Validate a limit parameter.

        Args:
            limit: Limit value to validate
            max_limit: Maximum allowed limit

        Returns:
            Validated limit

        Raises:
            ValidationError: If limit is invalid
        """
        from ports import ValidationError

        if limit < 1:
            raise ValidationError(
                reason=f"Limit must be >= 1, got {limit}",
                field="limit",
                value=limit,
                source=self.source_name,
            )
        if limit > max_limit:
            raise ValidationError(
                reason=f"Limit must be <= {max_limit}, got {limit}",
                field="limit",
                value=limit,
                source=self.source_name,
            )
        return limit
