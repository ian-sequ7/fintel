"""
Persistent file-based cache for reducing API calls.

Provides disk-backed caching that survives restarts.
Uses SQLite for thread-safe, efficient storage.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import hashlib

logger = logging.getLogger(__name__)

# Default cache location
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DB = CACHE_DIR / "api_cache.db"


class PersistentCache:
    """
    SQLite-backed persistent cache for API responses.

    Features:
    - Survives process restarts
    - Thread-safe
    - Automatic expiration
    - Grouped by source for easy invalidation
    - Automatic fallback to in-memory cache on SQLite errors
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, tuple[Any, datetime]] = {}
        self._sqlite_available = True
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON cache(source)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
                conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"SQLite initialization failed: {e}. Falling back to in-memory cache.")
            self._sqlite_available = False

    def _make_key(self, source: str, **kwargs) -> str:
        """Generate cache key from source and parameters."""
        parts = [source]
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v}")
        key_str = ":".join(parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, source: str, allow_stale: bool = False, **kwargs) -> Any | None:
        """
        Get cached data if not expired.

        Args:
            source: Data source name
            allow_stale: If True, return expired data if no fresh data exists
            **kwargs: Cache key parameters

        Returns:
            Cached data or None if not found/expired
        """
        key = self._make_key(source, **kwargs)
        now = datetime.now()

        # Try in-memory cache first if SQLite is unavailable
        if not self._sqlite_available:
            if key in self._memory_cache:
                data, expires_at = self._memory_cache[key]
                if expires_at > now:
                    logger.debug(f"Memory cache hit: {source} {kwargs}")
                    return data
                elif allow_stale:
                    logger.debug(f"Memory cache stale hit: {source} {kwargs}")
                    return data
                else:
                    # Clean up expired entry
                    del self._memory_cache[key]
            return None

        # Try SQLite cache
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                # First try fresh data
                row = conn.execute(
                    "SELECT data FROM cache WHERE key = ? AND expires_at > ?",
                    (key, now.isoformat())
                ).fetchone()

                if row:
                    logger.debug(f"Cache hit: {source} {kwargs}")
                    return json.loads(row[0])

                # If allow_stale, try expired data
                if allow_stale:
                    row = conn.execute(
                        "SELECT data FROM cache WHERE key = ?",
                        (key,)
                    ).fetchone()

                    if row:
                        logger.debug(f"Stale cache hit: {source} {kwargs}")
                        return json.loads(row[0])
        except sqlite3.Error as e:
            logger.warning(f"Cache read failed for {key}: {e}. Returning None.")
            # Don't disable SQLite entirely on read errors - they might be transient
            return None

        return None

    def set(
        self,
        source: str,
        data: Any,
        ttl: timedelta,
        **kwargs
    ) -> None:
        """
        Store data in cache.

        Args:
            source: Data source name
            data: Data to cache (must be JSON-serializable)
            ttl: Time-to-live for cache entry
            **kwargs: Cache key parameters
        """
        key = self._make_key(source, **kwargs)
        now = datetime.now()
        expires = now + ttl

        # Use in-memory cache if SQLite is unavailable
        if not self._sqlite_available:
            self._memory_cache[key] = (data, expires)
            logger.debug(f"Cached in memory: {source} {kwargs} (TTL={ttl})")
            return

        # Try SQLite cache
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache (key, source, data, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, source, json.dumps(data), now.isoformat(), expires.isoformat())
                )
                conn.commit()
            logger.debug(f"Cached: {source} {kwargs} (TTL={ttl})")
        except sqlite3.Error as e:
            logger.warning(f"Cache write failed for {key}: {e}. Skipping cache write.")
            # Don't crash - caching is not critical to app functionality

    def invalidate(self, source: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            source: If provided, only invalidate entries from this source.
                   If None, invalidate all entries.

        Returns:
            Number of entries deleted
        """
        deleted = 0

        # Handle in-memory cache
        if not self._sqlite_available:
            if source is None:
                deleted = len(self._memory_cache)
                self._memory_cache.clear()
            else:
                # Need to track source in memory cache - for now, clear all
                deleted = len(self._memory_cache)
                self._memory_cache.clear()
                logger.warning("In-memory cache cannot filter by source, clearing all entries")
            logger.info(f"Invalidated {deleted} memory cache entries" + (f" for {source}" if source else ""))
            return deleted

        # Handle SQLite cache
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                if source:
                    result = conn.execute("DELETE FROM cache WHERE source = ?", (source,))
                else:
                    result = conn.execute("DELETE FROM cache")

                deleted = result.rowcount
                conn.commit()

            logger.info(f"Invalidated {deleted} cache entries" + (f" for {source}" if source else ""))
        except sqlite3.Error as e:
            logger.error(f"Cache invalidation failed: {e}")

        return deleted

    def cleanup(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries deleted
        """
        now = datetime.now()
        deleted = 0

        # Handle in-memory cache
        if not self._sqlite_available:
            expired_keys = [k for k, (_, exp) in self._memory_cache.items() if exp < now]
            for key in expired_keys:
                del self._memory_cache[key]
            deleted = len(expired_keys)
            if deleted:
                logger.info(f"Cleaned up {deleted} expired memory cache entries")
            return deleted

        # Handle SQLite cache
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                result = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now.isoformat(),))
                deleted = result.rowcount
                conn.commit()

            if deleted:
                logger.info(f"Cleaned up {deleted} expired cache entries")
        except sqlite3.Error as e:
            logger.error(f"Cache cleanup failed: {e}")

        return deleted

    def stats(self) -> dict:
        """Get cache statistics."""
        now = datetime.now()

        # Handle in-memory cache
        if not self._sqlite_available:
            total = len(self._memory_cache)
            valid = sum(1 for _, exp in self._memory_cache.values() if exp > now)
            return {
                "cache_type": "memory",
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": total - valid,
                "by_source": {},  # Not tracked in memory cache
            }

        # Handle SQLite cache
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                valid = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now.isoformat(),)
                ).fetchone()[0]

                # By source
                by_source = {}
                for row in conn.execute(
                    "SELECT source, COUNT(*) FROM cache WHERE expires_at > ? GROUP BY source",
                    (now.isoformat(),)
                ):
                    by_source[row[0]] = row[1]

            return {
                "cache_type": "sqlite",
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": total - valid,
                "by_source": by_source,
            }
        except sqlite3.Error as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "cache_type": "sqlite",
                "error": str(e),
                "total_entries": 0,
                "valid_entries": 0,
                "expired_entries": 0,
                "by_source": {},
            }


# Singleton instance
_cache: PersistentCache | None = None


def get_cache() -> PersistentCache:
    """Get singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = PersistentCache()
    return _cache
