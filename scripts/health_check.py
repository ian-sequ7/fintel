#!/usr/bin/env python3
"""
Fintel Health Check Script

Verifies system health before running data pipelines:
- Yahoo Finance API reachability
- Cache directory writability
- Database accessibility
- API key configuration (FRED, Finnhub)

Usage:
    python scripts/health_check.py

Exit codes:
    0: All critical checks passed
    1: One or more critical checks failed
"""

import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yfinance as yf
    from adapters.cache import CACHE_DIR, CACHE_DB
    from adapters.fred import FredAdapter
    from adapters.finnhub import FinnhubAdapter
    from config import get_settings
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Make sure you're in the project virtual environment.")
    sys.exit(1)


class HealthCheck:
    """System health checker."""

    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.checks_skipped = 0

    def run_all(self) -> int:
        """Run all health checks and return exit code."""
        print("Fintel Health Check")
        print("=" * 50)
        print()

        # Critical checks (must pass)
        self._check_yahoo_finance()
        self._check_cache_directory()
        self._check_database()

        # Optional checks (warnings only)
        self._check_fred_api()
        self._check_finnhub_api()

        print()
        print("=" * 50)

        # Summary
        total_checks = self.checks_passed + self.checks_failed
        critical_checks = 3  # Yahoo, Cache, Database

        if self.checks_failed == 0:
            print(f"Status: HEALTHY ({self.checks_passed}/{total_checks} checks passed)")
            if self.checks_skipped > 0:
                print(f"Note: {self.checks_skipped} optional checks skipped")
            return 0
        else:
            print(f"Status: UNHEALTHY ({self.checks_failed}/{total_checks} checks failed)")
            return 1

    def _check_yahoo_finance(self):
        """Verify Yahoo Finance API is reachable."""
        check_name = "Yahoo Finance API"
        try:
            # Try fetching AAPL price
            ticker = yf.Ticker("AAPL")
            data = ticker.history(period="1d")

            if data.empty:
                self._fail(check_name, "No data returned for AAPL")
                return

            price = data["Close"].iloc[-1]
            if price <= 0:
                self._fail(check_name, f"Invalid price: ${price}")
                return

            self._pass(check_name, f"OK (AAPL: ${price:.2f})")

        except Exception as e:
            self._fail(check_name, str(e))

    def _check_cache_directory(self):
        """Verify cache directory is writable."""
        check_name = "Cache directory"
        try:
            # Ensure directory exists
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Test write permission
            test_file = CACHE_DIR / f".health_check_{datetime.now().timestamp()}"
            test_file.write_text("test")
            test_file.unlink()

            self._pass(check_name, f"OK (writable at {CACHE_DIR})")

        except Exception as e:
            self._fail(check_name, f"Not writable: {e}")

    def _check_database(self):
        """Verify database is accessible."""
        check_name = "Database"
        try:
            # Check if database file exists
            if not CACHE_DB.exists():
                self._skip(check_name, "Database not initialized (run data pipeline first)")
                return

            # Try connecting and querying
            with sqlite3.connect(CACHE_DB, timeout=5.0) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache")
                count = cursor.fetchone()[0]

            self._pass(check_name, f"OK ({count} cache entries)")

        except sqlite3.Error as e:
            self._fail(check_name, f"SQLite error: {e}")
        except Exception as e:
            self._fail(check_name, str(e))

    def _check_fred_api(self):
        """Verify FRED API is accessible (optional)."""
        check_name = "FRED API"
        try:
            # FRED CSV endpoint doesn't require API key
            adapter = FredAdapter()
            observations = adapter.fetch(series="GDP")

            if observations:
                gdp_data = observations[0].data
                value = gdp_data.get("value")
                unit = gdp_data.get("unit")
                self._pass(check_name, f"OK (GDP: {value} {unit})")
            else:
                self._skip(check_name, "No data available")

        except Exception as e:
            self._skip(check_name, f"Error: {e}")

    def _check_finnhub_api(self):
        """Verify Finnhub API key is configured (optional)."""
        check_name = "Finnhub API"
        try:
            adapter = FinnhubAdapter()

            if not adapter.is_configured():
                self._skip(check_name, "No API key configured")
                return

            # Try fetching a quote
            observations = adapter.get_quote("AAPL")

            if observations:
                price = observations[0].data.get("price")
                self._pass(check_name, f"OK (AAPL: ${price:.2f})")
            else:
                self._fail(check_name, "No data returned")

        except Exception as e:
            self._skip(check_name, f"Error: {e}")

    def _pass(self, check_name: str, message: str):
        """Mark check as passed."""
        print(f"[✓] {check_name}: {message}")
        self.checks_passed += 1

    def _fail(self, check_name: str, message: str):
        """Mark check as failed."""
        print(f"[✗] {check_name}: {message}")
        self.checks_failed += 1

    def _skip(self, check_name: str, message: str):
        """Mark check as skipped."""
        print(f"[!] {check_name}: SKIPPED ({message})")
        self.checks_skipped += 1


def main():
    """Run health checks and exit with appropriate code."""
    checker = HealthCheck()
    exit_code = checker.run_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
