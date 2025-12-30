"""
Data source ports and error types.

This module defines the protocol for data source adapters
and comprehensive error types with context-rich messages.
"""

from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol, runtime_checkable, Any

from domain import Observation, Category


# ============================================================================
# Error Codes
# ============================================================================

class ErrorCode(str, Enum):
    """Error codes for structured error handling."""

    # Network errors (1xx)
    NETWORK_TIMEOUT = "E101"
    NETWORK_CONNECTION = "E102"
    NETWORK_DNS = "E103"
    NETWORK_SSL = "E104"

    # HTTP errors (2xx)
    HTTP_CLIENT_ERROR = "E201"
    HTTP_SERVER_ERROR = "E202"
    HTTP_RATE_LIMITED = "E203"
    HTTP_UNAUTHORIZED = "E204"
    HTTP_FORBIDDEN = "E205"
    HTTP_NOT_FOUND = "E206"

    # Parse errors (3xx)
    PARSE_JSON = "E301"
    PARSE_XML = "E302"
    PARSE_CSV = "E303"
    PARSE_DATE = "E304"

    # Data errors (4xx)
    DATA_MISSING = "E401"
    DATA_INVALID = "E402"
    DATA_STALE = "E403"
    DATA_EMPTY = "E404"

    # Validation errors (5xx)
    VALIDATION_TICKER = "E501"
    VALIDATION_PARAM = "E502"
    VALIDATION_CONFIG = "E503"

    # Internal errors (9xx)
    INTERNAL = "E901"
    UNKNOWN = "E999"


# ============================================================================
# Error Classes
# ============================================================================

class AdapterError(Exception):
    """
    Base exception for adapter failures.

    Provides structured error information for debugging and monitoring.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        source: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        self.code = code
        self.source = source
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.now()

        # Build detailed message
        parts = [f"[{code.value}]"]
        if source:
            parts.append(f"[{source}]")
        parts.append(message)

        self.message = message
        full_message = " ".join(parts)
        super().__init__(full_message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "code": self.code.value,
            "message": self.message,
            "source": self.source,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }

    def with_context(self, **kwargs: Any) -> "AdapterError":
        """Add additional context and return self for chaining."""
        self.context.update(kwargs)
        return self


class RateLimitError(AdapterError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        retry_after: timedelta | None = None,
        source: str | None = None,
        limit: int | None = None,
    ):
        self.retry_after = retry_after
        self.limit = limit

        msg = "Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after.total_seconds():.0f}s"

        context = {}
        if retry_after:
            context["retry_after_seconds"] = retry_after.total_seconds()
        if limit:
            context["limit"] = limit

        super().__init__(
            message=msg,
            code=ErrorCode.HTTP_RATE_LIMITED,
            source=source,
            context=context,
        )


class FetchError(AdapterError):
    """Raised when data fetch fails."""

    def __init__(
        self,
        source: str,
        reason: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        url: str | None = None,
        status_code: int | None = None,
        cause: Exception | None = None,
    ):
        self.reason = reason
        self.url = url
        self.status_code = status_code

        context = {"reason": reason}
        if url:
            context["url"] = url
        if status_code:
            context["status_code"] = status_code

        super().__init__(
            message=reason,
            code=code,
            source=source,
            context=context,
            cause=cause,
        )

    @classmethod
    def from_http_error(
        cls,
        source: str,
        status_code: int,
        url: str | None = None,
        response_body: str | None = None,
    ) -> "FetchError":
        """Create FetchError from HTTP error response."""
        if status_code == 429:
            raise RateLimitError(source=source)

        if 400 <= status_code < 500:
            code = ErrorCode.HTTP_CLIENT_ERROR
            if status_code == 401:
                code = ErrorCode.HTTP_UNAUTHORIZED
            elif status_code == 403:
                code = ErrorCode.HTTP_FORBIDDEN
            elif status_code == 404:
                code = ErrorCode.HTTP_NOT_FOUND
        else:
            code = ErrorCode.HTTP_SERVER_ERROR

        reason = f"HTTP {status_code}"
        if response_body:
            reason += f": {response_body[:100]}"

        return cls(
            source=source,
            reason=reason,
            code=code,
            url=url,
            status_code=status_code,
        )

    @classmethod
    def from_network_error(
        cls,
        source: str,
        error: Exception,
        url: str | None = None,
    ) -> "FetchError":
        """Create FetchError from network exception."""
        error_str = str(error).lower()

        if "timeout" in error_str:
            code = ErrorCode.NETWORK_TIMEOUT
            reason = "Request timed out"
        elif "ssl" in error_str or "certificate" in error_str:
            code = ErrorCode.NETWORK_SSL
            reason = "SSL/TLS error"
        elif "dns" in error_str or "name resolution" in error_str:
            code = ErrorCode.NETWORK_DNS
            reason = "DNS resolution failed"
        else:
            code = ErrorCode.NETWORK_CONNECTION
            reason = f"Connection error: {error}"

        return cls(
            source=source,
            reason=reason,
            code=code,
            url=url,
            cause=error,
        )


class ParseError(AdapterError):
    """Raised when response parsing fails."""

    def __init__(
        self,
        source: str,
        format_type: str,
        reason: str,
        raw_content: str | None = None,
        cause: Exception | None = None,
    ):
        code_map = {
            "json": ErrorCode.PARSE_JSON,
            "xml": ErrorCode.PARSE_XML,
            "csv": ErrorCode.PARSE_CSV,
            "date": ErrorCode.PARSE_DATE,
        }
        code = code_map.get(format_type, ErrorCode.UNKNOWN)

        context = {"format": format_type}
        if raw_content:
            context["raw_preview"] = raw_content[:200]

        super().__init__(
            message=f"Failed to parse {format_type}: {reason}",
            code=code,
            source=source,
            context=context,
            cause=cause,
        )


class DataError(AdapterError):
    """Raised when data is missing, invalid, or stale."""

    def __init__(
        self,
        source: str,
        reason: str,
        code: ErrorCode = ErrorCode.DATA_INVALID,
        field: str | None = None,
        expected: Any = None,
        actual: Any = None,
    ):
        context = {"reason": reason}
        if field:
            context["field"] = field
        if expected is not None:
            context["expected"] = str(expected)
        if actual is not None:
            context["actual"] = str(actual)

        super().__init__(
            message=reason,
            code=code,
            source=source,
            context=context,
        )

    @classmethod
    def missing(cls, source: str, field: str) -> "DataError":
        """Create error for missing required field."""
        return cls(
            source=source,
            reason=f"Missing required field: {field}",
            code=ErrorCode.DATA_MISSING,
            field=field,
        )

    @classmethod
    def empty(cls, source: str, description: str = "No data") -> "DataError":
        """Create error for empty result set."""
        return cls(
            source=source,
            reason=description,
            code=ErrorCode.DATA_EMPTY,
        )

    @classmethod
    def stale(cls, source: str, age: timedelta, max_age: timedelta) -> "DataError":
        """Create error for stale data."""
        return cls(
            source=source,
            reason=f"Data is stale (age: {age}, max: {max_age})",
            code=ErrorCode.DATA_STALE,
            expected=f"<{max_age}",
            actual=str(age),
        )


class ValidationError(AdapterError):
    """Raised when input validation fails."""

    def __init__(
        self,
        reason: str,
        field: str,
        value: Any = None,
        source: str | None = None,
    ):
        context = {"field": field}
        if value is not None:
            context["value"] = str(value)[:50]

        super().__init__(
            message=reason,
            code=ErrorCode.VALIDATION_PARAM,
            source=source,
            context=context,
        )

    @classmethod
    def invalid_ticker(cls, ticker: str, reason: str = "Invalid format") -> "ValidationError":
        """Create error for invalid ticker symbol."""
        error = cls(
            reason=f"Invalid ticker '{ticker}': {reason}",
            field="ticker",
            value=ticker,
        )
        error.code = ErrorCode.VALIDATION_TICKER
        return error


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
