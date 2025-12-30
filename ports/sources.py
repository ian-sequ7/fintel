from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from domain import Observation, Category


class AdapterError(Exception):
    """Base exception for adapter failures."""
    pass


class RateLimitError(AdapterError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: timedelta | None = None):
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after.total_seconds():.0f}s"
        super().__init__(msg)


class FetchError(AdapterError):
    """Raised when data fetch fails."""

    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"[{source}] {reason}")


@runtime_checkable
class DataSource(Protocol):
    """
    Protocol for all data source adapters.

    Implementations must:
    - Handle rate limiting (raise RateLimitError)
    - Cache responses with TTL
    - Return typed Observations, not raw dicts
    - Fail explicitly with FetchError, no silent fallbacks
    """

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        ...

    @property
    def category(self) -> Category:
        """Primary category of data this source provides."""
        ...

    @property
    def reliability(self) -> float:
        """Reliability score 0-1 for observations from this source."""
        ...

    @abstractmethod
    def fetch(self, **kwargs) -> list[Observation]:
        """
        Fetch observations from the data source.

        Raises:
            RateLimitError: If rate limit exceeded
            FetchError: If fetch fails for any other reason
        """
        ...

    def is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        ...
