"""
Database module for Fintel.

Provides SQLite persistence for all pipeline data.
"""

from .database import Database, get_db
from .models import (
    CongressTrade,
    OptionsActivity,
    ScrapeRun,
    StockPick,
    StockMetrics,
    PricePoint,
    MacroIndicator,
    MacroRisk,
    NewsItem,
)

__all__ = [
    "Database",
    "get_db",
    "CongressTrade",
    "OptionsActivity",
    "ScrapeRun",
    "StockPick",
    "StockMetrics",
    "PricePoint",
    "MacroIndicator",
    "MacroRisk",
    "NewsItem",
]
