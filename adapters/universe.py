"""
Stock universe providers.

Provides lists of tickers for analysis:
- S&P 500 constituents
- Dow Jones Industrial Average (30 stocks)
- NASDAQ-100 constituents
- Combined universe (deduplicated)
- Sector-based filtering
- Custom watchlists

Data sources:
- Primary: yfiua/index-constituents GitHub (updated monthly)
- Fallback: Wikipedia tables

Caches constituents for 24 hours (they rarely change).
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from io import StringIO
from typing import ClassVar

from .base import BaseAdapter, CacheEntry
from domain import Category, Observation
from ports import FetchError

logger = logging.getLogger(__name__)


class Index(Enum):
    """Stock market indices."""
    SP500 = "sp500"
    DOW = "dow"
    NASDAQ100 = "nasdaq100"


@dataclass
class StockInfo:
    """Basic stock information with index membership."""
    ticker: str
    name: str
    sector: str
    industry: str
    indices: list[Index] = field(default_factory=list)

    @property
    def in_sp500(self) -> bool:
        return Index.SP500 in self.indices

    @property
    def in_dow(self) -> bool:
        return Index.DOW in self.indices

    @property
    def in_nasdaq100(self) -> bool:
        return Index.NASDAQ100 in self.indices

    @property
    def index_badges(self) -> list[str]:
        """Return display-friendly index badges."""
        badges = []
        if self.in_sp500:
            badges.append("S&P 500")
        if self.in_dow:
            badges.append("Dow 30")
        if self.in_nasdaq100:
            badges.append("NASDAQ-100")
        return badges


# Sector mapping for normalization
SECTOR_NORMALIZE = {
    "information technology": "technology",
    "communication services": "communication services",
    "consumer discretionary": "consumer discretionary",
    "consumer staples": "consumer staples",
    "health care": "healthcare",
    "financials": "financials",
    "industrials": "industrials",
    "materials": "materials",
    "real estate": "real estate",
    "utilities": "utilities",
    "energy": "energy",
}


class UniverseProvider(BaseAdapter):
    """
    Provides stock universe (S&P 500 + Dow 30 + NASDAQ-100).

    Primary source: yfiua/index-constituents GitHub (CSV, updated monthly)
    Fallback: Wikipedia tables

    Caches for 24 hours since constituents rarely change.
    """

    # Primary data source: yfiua/index-constituents (monthly updates, Yahoo-compatible symbols)
    YFIUA_SP500_URL = "https://yfiua.github.io/index-constituents/constituents-sp500.csv"
    YFIUA_DOW_URL = "https://yfiua.github.io/index-constituents/constituents-dowjones.csv"
    YFIUA_NASDAQ100_URL = "https://yfiua.github.io/index-constituents/constituents-nasdaq100.csv"

    # Fallback: Wikipedia tables
    WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    WIKI_DOW_URL = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    WIKI_NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

    # Legacy alias
    WIKI_URL = WIKI_SP500_URL

    # Cache TTL for universe data (24 hours)
    UNIVERSE_CACHE_TTL: ClassVar[timedelta] = timedelta(hours=24)

    # Fallback static list (top 100 by market cap, updated periodically)
    FALLBACK_TICKERS: ClassVar[list[str]] = [
        # Top 50 by market cap
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "XOM",
        "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "LLY",
        "PEP", "KO", "COST", "AVGO", "TMO", "MCD", "WMT", "CSCO", "ACN", "ABT",
        "DHR", "CRM", "BAC", "PFE", "CMCSA", "VZ", "ADBE", "NFLX", "INTC", "NKE",
        "TXN", "AMD", "PM", "UNP", "RTX", "NEE", "HON", "BMY", "T", "QCOM",
        # Next 50
        "UPS", "SPGI", "LOW", "MS", "IBM", "ELV", "CAT", "GS", "SBUX", "DE",
        "INTU", "BLK", "MDT", "GILD", "AXP", "LMT", "ISRG", "SYK", "CVS", "BKNG",
        "ADI", "MDLZ", "AMT", "TJX", "VRTX", "ADP", "REGN", "MMC", "CI", "ZTS",
        "PLD", "MO", "CB", "SO", "SCHW", "DUK", "LRCX", "BDX", "CME", "EOG",
        "EQIX", "CL", "ITW", "SLB", "NOC", "PNC", "PYPL", "USB", "WM", "GD",
    ]

    # Static sector mapping for fallback
    FALLBACK_SECTORS: ClassVar[dict[str, str]] = {
        "AAPL": "technology", "MSFT": "technology", "GOOGL": "communication services",
        "AMZN": "consumer discretionary", "NVDA": "technology", "META": "communication services",
        "TSLA": "consumer discretionary", "BRK-B": "financials", "UNH": "healthcare",
        "XOM": "energy", "JNJ": "healthcare", "JPM": "financials", "V": "financials",
        "PG": "consumer staples", "MA": "financials", "HD": "consumer discretionary",
        "CVX": "energy", "MRK": "healthcare", "ABBV": "healthcare", "LLY": "healthcare",
        "PEP": "consumer staples", "KO": "consumer staples", "COST": "consumer staples",
        "AVGO": "technology", "TMO": "healthcare", "MCD": "consumer discretionary",
        "WMT": "consumer staples", "CSCO": "technology", "ACN": "technology",
        "ABT": "healthcare", "DHR": "healthcare", "CRM": "technology", "BAC": "financials",
        "PFE": "healthcare", "CMCSA": "communication services", "VZ": "communication services",
        "ADBE": "technology", "NFLX": "communication services", "INTC": "technology",
        "NKE": "consumer discretionary", "TXN": "technology", "AMD": "technology",
        "PM": "consumer staples", "UNP": "industrials", "RTX": "industrials",
        "NEE": "utilities", "HON": "industrials", "BMY": "healthcare", "T": "communication services",
        "QCOM": "technology",
    }

    def __init__(self):
        super().__init__()
        self._universe_cache: dict[str, StockInfo] | None = None
        self._universe_cached_at: datetime | None = None
        # Per-index caches for raw ticker lists
        self._index_cache: dict[Index, set[str]] = {}

    @property
    def source_name(self) -> str:
        return "universe"

    @property
    def category(self) -> Category:
        return Category.PRICE  # Not really used, just required by base

    @property
    def reliability(self) -> float:
        return 0.95  # Wikipedia is generally reliable for this

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Not used - universe provider doesn't return observations."""
        return []

    def _parse_wikipedia_table(self, html: str) -> dict[str, StockInfo]:
        """Parse S&P 500 table from Wikipedia HTML."""
        stocks = {}

        # Find the table with S&P 500 data
        # The table has columns: Symbol, Security, GICS Sector, GICS Sub-Industry, ...
        import re

        # Extract table rows - look for the wikitable with stock data
        table_pattern = r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)

        if not tables:
            logger.warning("No wikitable found in Wikipedia HTML")
            return stocks

        # First table should be the S&P 500 constituents
        table_html = tables[0]

        # Extract rows
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        rows = re.findall(row_pattern, table_html, re.DOTALL)

        for row in rows[1:]:  # Skip header row
            # Extract cells
            cell_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'
            cells = re.findall(cell_pattern, row, re.DOTALL)

            if len(cells) >= 4:
                # Clean cell content (remove HTML tags, links)
                def clean_cell(cell: str) -> str:
                    # Extract text from links
                    link_match = re.search(r'title="([^"]*)"', cell)
                    if link_match:
                        return link_match.group(1).strip()
                    # Remove HTML tags
                    text = re.sub(r'<[^>]+>', '', cell)
                    return text.strip()

                ticker = clean_cell(cells[0]).upper()
                name = clean_cell(cells[1])
                sector_raw = clean_cell(cells[2]).lower()
                industry = clean_cell(cells[3])

                # Normalize sector
                sector = SECTOR_NORMALIZE.get(sector_raw, sector_raw)

                # Validate ticker format
                if ticker and re.match(r'^[A-Z]{1,5}$', ticker):
                    stocks[ticker] = StockInfo(
                        ticker=ticker,
                        name=name,
                        sector=sector,
                        industry=industry,
                    )

        logger.info(f"Parsed {len(stocks)} stocks from Wikipedia")
        return stocks

    def _normalize_ticker(self, ticker: str) -> str:
        """Normalize ticker for Yahoo Finance compatibility.

        Yahoo uses '-' instead of '.' for share classes (BRK-B, BF-B).
        """
        return ticker.replace(".", "-").upper()

    def _fetch_index_from_yfiua(self, index: Index) -> set[str]:
        """Fetch index constituents from yfiua GitHub CSV."""
        url_map = {
            Index.SP500: self.YFIUA_SP500_URL,
            Index.DOW: self.YFIUA_DOW_URL,
            Index.NASDAQ100: self.YFIUA_NASDAQ100_URL,
        }
        url = url_map[index]

        try:
            csv_text = self._http_get_text(url)
            reader = csv.DictReader(StringIO(csv_text))
            tickers = set()
            for row in reader:
                symbol = row.get("Symbol", "").strip()
                if symbol:
                    tickers.add(self._normalize_ticker(symbol))
            logger.info(f"Fetched {len(tickers)} tickers for {index.value} from yfiua")
            return tickers
        except Exception as e:
            logger.warning(f"Failed to fetch {index.value} from yfiua: {e}")
            return set()

    def _fetch_combined_universe(self) -> dict[str, StockInfo]:
        """
        Fetch combined universe from all indices with membership tracking.

        Returns dict with all unique tickers, each tagged with index membership.
        Sector data comes from S&P 500 Wikipedia (most comprehensive).
        """
        # Fetch each index from yfiua
        sp500_tickers = self._fetch_index_from_yfiua(Index.SP500)
        dow_tickers = self._fetch_index_from_yfiua(Index.DOW)
        nasdaq100_tickers = self._fetch_index_from_yfiua(Index.NASDAQ100)

        # Cache for filter_by_index
        self._index_cache = {
            Index.SP500: sp500_tickers,
            Index.DOW: dow_tickers,
            Index.NASDAQ100: nasdaq100_tickers,
        }

        # Get sector data from Wikipedia (fallback to S&P 500 page)
        sp500_data = self._fetch_sp500()

        # Build combined universe
        all_tickers = sp500_tickers | dow_tickers | nasdaq100_tickers
        universe: dict[str, StockInfo] = {}

        for ticker in all_tickers:
            # Determine index membership
            indices = []
            if ticker in sp500_tickers:
                indices.append(Index.SP500)
            if ticker in dow_tickers:
                indices.append(Index.DOW)
            if ticker in nasdaq100_tickers:
                indices.append(Index.NASDAQ100)

            # Get sector from S&P 500 data, fallback to static mapping
            if ticker in sp500_data:
                info = sp500_data[ticker]
                universe[ticker] = StockInfo(
                    ticker=ticker,
                    name=info.name,
                    sector=info.sector,
                    industry=info.industry,
                    indices=indices,
                )
            else:
                # Not in S&P 500 - use fallback sector or "unknown"
                sector = self.FALLBACK_SECTORS.get(ticker, "technology")  # Most NASDAQ-only are tech
                universe[ticker] = StockInfo(
                    ticker=ticker,
                    name=ticker,
                    sector=sector,
                    industry="",
                    indices=indices,
                )

        logger.info(
            f"Combined universe: {len(universe)} unique tickers "
            f"(SP500: {len(sp500_tickers)}, Dow: {len(dow_tickers)}, NASDAQ-100: {len(nasdaq100_tickers)})"
        )
        return universe

    def _fetch_sp500(self) -> dict[str, StockInfo]:
        """Fetch S&P 500 constituents from Wikipedia."""
        try:
            html = self._http_get_text(self.WIKI_URL)
            stocks = self._parse_wikipedia_table(html)

            if len(stocks) < 400:  # Should be ~500, warn if much less
                logger.warning(f"Only parsed {len(stocks)} stocks, expected ~500")

            return stocks

        except Exception as e:
            logger.warning(f"Failed to fetch S&P 500 from Wikipedia: {e}")
            return {}

    def _get_fallback(self) -> dict[str, StockInfo]:
        """Return fallback static list with S&P 500 membership."""
        stocks = {}
        for ticker in self.FALLBACK_TICKERS:
            sector = self.FALLBACK_SECTORS.get(ticker, "unknown")
            stocks[ticker] = StockInfo(
                ticker=ticker,
                name=ticker,  # Name unknown in fallback
                sector=sector,
                industry="",
                indices=[Index.SP500],  # Fallback are all S&P 500
            )
        return stocks

    def get_universe(
        self,
        force_refresh: bool = False,
        indices: list[Index] | None = None,
    ) -> dict[str, StockInfo]:
        """
        Get stock universe with caching.

        Args:
            force_refresh: Bypass cache and fetch fresh data
            indices: Filter to specific indices (default: all)

        Returns:
            Dict of ticker -> StockInfo
        """
        # Check cache
        if not force_refresh and self._universe_cache:
            age = datetime.now() - (self._universe_cached_at or datetime.min)
            if age < self.UNIVERSE_CACHE_TTL:
                universe = self._universe_cache
                if indices:
                    return self._filter_universe_by_indices(universe, indices)
                return universe

        # Fetch combined universe from all indices
        universe = self._fetch_combined_universe()

        # Fallback if fetch failed
        if not universe:
            logger.info("Using fallback universe")
            universe = self._get_fallback()

        # Update cache
        self._universe_cache = universe
        self._universe_cached_at = datetime.now()

        if indices:
            return self._filter_universe_by_indices(universe, indices)
        return universe

    def _filter_universe_by_indices(
        self,
        universe: dict[str, StockInfo],
        indices: list[Index],
    ) -> dict[str, StockInfo]:
        """Filter universe to only include stocks in specified indices."""
        return {
            ticker: info
            for ticker, info in universe.items()
            if any(idx in info.indices for idx in indices)
        }

    def filter_by_index(
        self,
        index: Index,
        force_refresh: bool = False,
    ) -> list[str]:
        """Get tickers in a specific index."""
        universe = self.get_universe(force_refresh)
        return [
            ticker for ticker, info in universe.items()
            if index in info.indices
        ]

    def get_sp500_tickers(self, force_refresh: bool = False) -> list[str]:
        """Get S&P 500 tickers only."""
        return self.filter_by_index(Index.SP500, force_refresh)

    def get_dow_tickers(self, force_refresh: bool = False) -> list[str]:
        """Get Dow 30 tickers only."""
        return self.filter_by_index(Index.DOW, force_refresh)

    def get_nasdaq100_tickers(self, force_refresh: bool = False) -> list[str]:
        """Get NASDAQ-100 tickers only."""
        return self.filter_by_index(Index.NASDAQ100, force_refresh)

    def get_tickers(self, force_refresh: bool = False) -> list[str]:
        """Get list of tickers in universe."""
        return list(self.get_universe(force_refresh).keys())

    def get_sectors(self, force_refresh: bool = False) -> dict[str, list[str]]:
        """Get tickers grouped by sector."""
        universe = self.get_universe(force_refresh)

        sectors: dict[str, list[str]] = {}
        for ticker, info in universe.items():
            sector = info.sector or "unknown"
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(ticker)

        return sectors

    def get_sector_for_ticker(self, ticker: str) -> str:
        """Get sector for a specific ticker."""
        universe = self.get_universe()
        info = universe.get(ticker.upper())
        return info.sector if info else "unknown"

    def filter_by_sector(
        self,
        sectors: list[str],
        force_refresh: bool = False,
    ) -> list[str]:
        """Get tickers in specific sectors."""
        universe = self.get_universe(force_refresh)
        normalized_sectors = [s.lower() for s in sectors]

        return [
            ticker for ticker, info in universe.items()
            if info.sector.lower() in normalized_sectors
        ]


# Module-level singleton for convenience
_provider: UniverseProvider | None = None


def get_universe_provider() -> UniverseProvider:
    """Get singleton universe provider."""
    global _provider
    if _provider is None:
        _provider = UniverseProvider()
    return _provider


def get_all_tickers() -> list[str]:
    """Get all tickers in combined universe (S&P 500 + Dow + NASDAQ-100)."""
    return get_universe_provider().get_tickers()


def get_sp500_tickers() -> list[str]:
    """Get S&P 500 tickers only."""
    return get_universe_provider().get_sp500_tickers()


def get_dow_tickers() -> list[str]:
    """Get Dow 30 tickers only."""
    return get_universe_provider().get_dow_tickers()


def get_nasdaq100_tickers() -> list[str]:
    """Get NASDAQ-100 tickers only."""
    return get_universe_provider().get_nasdaq100_tickers()


def get_sector_for_ticker(ticker: str) -> str:
    """Get sector for a ticker."""
    return get_universe_provider().get_sector_for_ticker(ticker)


def get_index_membership(ticker: str) -> list[str]:
    """Get index membership badges for a ticker."""
    universe = get_universe_provider().get_universe()
    info = universe.get(ticker.upper())
    return info.index_badges if info else []
