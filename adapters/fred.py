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


# Key FRED series for macro analysis (20 total)
MACRO_SERIES = {
    # Labor market (3)
    "UNRATE": ("Unemployment Rate", "%"),
    "PAYEMS": ("Nonfarm Payrolls", "Thousands"),
    "ICSA": ("Initial Jobless Claims", "Thousands"),

    # Inflation (2) - Note: These are index values, YoY change calculated separately
    "CPIAUCSL": ("CPI (Inflation)", "Index"),
    "PCEPI": ("PCE Price Index", "Index"),

    # GDP & Production (2)
    "GDP": ("Gross Domestic Product", "Billions USD"),
    "INDPRO": ("Industrial Production", "Index"),

    # Interest Rates (4)
    "FEDFUNDS": ("Federal Funds Rate", "%"),
    "DGS10": ("10-Year Treasury Yield", "%"),
    "DGS2": ("2-Year Treasury Yield", "%"),
    "T10Y2Y": ("10Y-2Y Treasury Spread", "%"),

    # Credit & Risk (2)
    "BAMLH0A0HYM2": ("High Yield Spread", "%"),
    "VIXCLS": ("VIX Volatility Index", "Index"),

    # Consumer (2)
    "UMCSENT": ("Consumer Sentiment", "Index"),
    "RSXFS": ("Retail Sales", "Millions USD"),

    # Housing (2)
    "HOUST": ("Housing Starts", "Thousands"),
    "MORTGAGE30US": ("30-Year Mortgage Rate", "%"),

    # Commodities (2)
    "DCOILWTICO": ("WTI Crude Oil Price", "USD/Barrel"),
    "GOLDAMGBD228NLBM": ("Gold Price", "USD/Oz"),

    # Fed Balance Sheet (1)
    "WALCL": ("Fed Balance Sheet", "Millions USD"),
}

# Series that need YoY change calculation (index-based inflation measures)
INFLATION_INDEX_SERIES = {"CPIAUCSL", "PCEPI"}


def _calculate_yoy_change(data: list[tuple[str, str]]) -> float | None:
    """Calculate year-over-year percentage change from historical data."""
    if len(data) < 13:  # Need at least 13 months of data
        return None

    try:
        current_value = float(data[-1][1])
        # Find value from ~12 months ago (monthly data)
        year_ago_value = float(data[-13][1])

        if year_ago_value <= 0:
            return None

        return ((current_value - year_ago_value) / year_ago_value) * 100
    except (ValueError, IndexError):
        return None


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

            # For inflation indices, calculate YoY change rate
            yoy_change = None
            display_value = value
            display_unit = unit

            if series_id in INFLATION_INDEX_SERIES:
                yoy_change = _calculate_yoy_change(data)
                if yoy_change is not None:
                    # Use the YoY rate as the primary display value
                    display_value = round(yoy_change, 1)
                    display_unit = "% YoY"

            indicator = MacroIndicator(
                series_id=series_id,
                name=name,
                value=display_value,
                date=date,
                unit=display_unit,
            )

            obs_data = {
                "series_id": indicator.series_id,
                "name": indicator.name,
                "value": indicator.value,
                "unit": indicator.unit,
            }

            # Include raw index value for inflation series
            if series_id in INFLATION_INDEX_SERIES:
                obs_data["index_value"] = value
                obs_data["yoy_change"] = yoy_change

            observations.append(Observation(
                source=self.source_name,
                timestamp=date,
                category=Category.MACRO,
                data=obs_data,
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
