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
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
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

    def _make_key(self, source: str, **kwargs) -> str:
        """Generate cache key from source and parameters."""
        parts = [source]
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v}")
        key_str = ":".join(parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, source: str, **kwargs) -> Any | None:
        """
        Get cached data if not expired.

        Args:
            source: Data source name
            **kwargs: Cache key parameters

        Returns:
            Cached data or None if not found/expired
        """
        key = self._make_key(source, **kwargs)
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM cache WHERE key = ? AND expires_at > ?",
                (key, now)
            ).fetchone()

            if row:
                logger.debug(f"Cache hit: {source} {kwargs}")
                return json.loads(row[0])

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

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, source, data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, source, json.dumps(data), now.isoformat(), expires.isoformat())
            )
            conn.commit()

        logger.debug(f"Cached: {source} {kwargs} (TTL={ttl})")

    def invalidate(self, source: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            source: If provided, only invalidate entries from this source.
                   If None, invalidate all entries.

        Returns:
            Number of entries deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            if source:
                result = conn.execute("DELETE FROM cache WHERE source = ?", (source,))
            else:
                result = conn.execute("DELETE FROM cache")

            deleted = result.rowcount
            conn.commit()

        logger.info(f"Invalidated {deleted} cache entries" + (f" for {source}" if source else ""))
        return deleted

    def cleanup(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries deleted
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
            deleted = result.rowcount
            conn.commit()

        if deleted:
            logger.info(f"Cleaned up {deleted} expired cache entries")
        return deleted

    def stats(self) -> dict:
        """Get cache statistics."""
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]

            # By source
            by_source = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) FROM cache WHERE expires_at > ? GROUP BY source",
                (now,)
            ):
                by_source[row[0]] = row[1]

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
            "by_source": by_source,
        }


# Singleton instance
_cache: PersistentCache | None = None


def get_cache() -> PersistentCache:
    """Get singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = PersistentCache()
    return _cache
