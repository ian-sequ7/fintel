"""
FRED (Federal Reserve Economic Data) adapter.

Provides macroeconomic indicators:
- GDP, Unemployment rate, Inflation
- Interest rates (Fed Funds, Treasury yields)
- Leading indicators

Uses CSV endpoint (no API key required).
"""

import csv
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from io import StringIO

from domain import Observation, Category
from ports import FetchError
from config import get_settings

from .base import BaseAdapter


@dataclass
class MacroIndicator:
    """Typed macro indicator data."""
    series_id: str
    name: str
    value: float
    date: datetime
    unit: str


# Key FRED series for macro analysis
MACRO_SERIES = {
    "UNRATE": ("Unemployment Rate", "%"),
    "CPIAUCSL": ("CPI (Inflation)", "Index"),
    "GDP": ("Gross Domestic Product", "Billions USD"),
    "FEDFUNDS": ("Federal Funds Rate", "%"),
    "T10Y2Y": ("10Y-2Y Treasury Spread", "%"),
    "UMCSENT": ("Consumer Sentiment", "Index"),
    "INDPRO": ("Industrial Production", "Index"),
    "HOUST": ("Housing Starts", "Thousands"),
}


class FredAdapter(BaseAdapter):
    """
    FRED macroeconomic data adapter.

    Uses CSV endpoint - no API key required.
    """

    BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    @property
    def source_name(self) -> str:
        return "fred"

    @property
    def category(self) -> Category:
        return Category.MACRO

    @property
    def reliability(self) -> float:
        return 0.95  # Official government data

    def _request_csv(self, series_id: str) -> list[tuple[str, str]]:
        """Fetch CSV data for a series."""
        settings = get_settings()
        url = f"{self.BASE_URL}?id={series_id}"
        headers = {"User-Agent": settings.user_agent}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=settings.request_timeout) as resp:
                content = resp.read().decode("utf-8")
                reader = csv.reader(StringIO(content))
                next(reader)  # Skip header
                return [(row[0], row[1]) for row in reader if len(row) >= 2 and row[1] != "."]
        except urllib.error.HTTPError as e:
            raise FetchError(self.source_name, f"HTTP {e.code} for {series_id}")
        except urllib.error.URLError as e:
            raise FetchError(self.source_name, f"Connection error: {e.reason}")

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Fetch macro indicators."""
        series_ids = kwargs.get("series", list(MACRO_SERIES.keys()))

        if isinstance(series_ids, str):
            series_ids = [series_ids]

        observations = []

        for series_id in series_ids:
            if series_id not in MACRO_SERIES:
                continue

            name, unit = MACRO_SERIES[series_id]

            try:
                data = self._request_csv(series_id)
            except FetchError:
                continue  # Skip failed series, try others

            if not data:
                continue

            # Get latest value
            date_str, value_str = data[-1]

            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                value = float(value_str)
            except (ValueError, TypeError):
                continue

            indicator = MacroIndicator(
                series_id=series_id,
                name=name,
                value=value,
                date=date,
                unit=unit,
            )

            observations.append(Observation(
                source=self.source_name,
                timestamp=date,
                category=Category.MACRO,
                data={
                    "series_id": indicator.series_id,
                    "name": indicator.name,
                    "value": indicator.value,
                    "unit": indicator.unit,
                },
                ticker=None,
                reliability=self.reliability,
            ))

        if not observations:
            raise FetchError(self.source_name, "No macro data retrieved")

        return observations

    def get_unemployment(self) -> list[Observation]:
        """Get unemployment rate."""
        return self.fetch(series="UNRATE")

    def get_inflation(self) -> list[Observation]:
        """Get CPI inflation data."""
        return self.fetch(series="CPIAUCSL")

    def get_fed_rate(self) -> list[Observation]:
        """Get Federal Funds rate."""
        return self.fetch(series="FEDFUNDS")

    def get_yield_curve(self) -> list[Observation]:
        """Get 10Y-2Y Treasury spread (yield curve)."""
        return self.fetch(series="T10Y2Y")

    def get_all_indicators(self) -> list[Observation]:
        """Get all tracked macro indicators."""
        return self.fetch(series=list(MACRO_SERIES.keys()))
