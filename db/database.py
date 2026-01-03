"""
SQLite database for Fintel.

Provides persistent storage for smart money signals and market data.
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional

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

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "fintel.db"


class Database:
    """SQLite database for Fintel data persistence."""

    SCHEMA = """
    -- Congress trades from Capitol Trades
    CREATE TABLE IF NOT EXISTS congress_trades (
        id TEXT PRIMARY KEY,
        politician TEXT NOT NULL,
        party TEXT NOT NULL,
        chamber TEXT NOT NULL,
        state TEXT,
        ticker TEXT NOT NULL,
        issuer TEXT,
        transaction_type TEXT NOT NULL,
        amount_low INTEGER NOT NULL,
        amount_high INTEGER NOT NULL,
        traded_date DATE,
        disclosed_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_congress_ticker ON congress_trades(ticker);
    CREATE INDEX IF NOT EXISTS idx_congress_politician ON congress_trades(politician);
    CREATE INDEX IF NOT EXISTS idx_congress_disclosed ON congress_trades(disclosed_date);

    -- Unusual options activity
    CREATE TABLE IF NOT EXISTS options_activity (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        option_type TEXT NOT NULL,
        strike REAL NOT NULL,
        expiry DATE NOT NULL,
        volume INTEGER NOT NULL,
        open_interest INTEGER NOT NULL,
        volume_oi_ratio REAL NOT NULL,
        implied_volatility REAL,
        premium_total REAL,
        direction TEXT NOT NULL,
        strength REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_options_ticker ON options_activity(ticker);
    CREATE INDEX IF NOT EXISTS idx_options_created ON options_activity(created_at);

    -- Stock picks (recommendations)
    CREATE TABLE IF NOT EXISTS stock_picks (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        conviction_score REAL NOT NULL,
        thesis TEXT NOT NULL,
        entry_price REAL,
        target_price REAL,
        stop_loss REAL,
        risk_factors TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_picks_ticker ON stock_picks(ticker);
    CREATE INDEX IF NOT EXISTS idx_picks_timeframe ON stock_picks(timeframe);
    CREATE INDEX IF NOT EXISTS idx_picks_created ON stock_picks(created_at);

    -- Stock metrics (fundamentals)
    CREATE TABLE IF NOT EXISTS stock_metrics (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sector TEXT,
        industry TEXT,
        price REAL,
        previous_close REAL,
        change REAL,
        change_percent REAL,
        volume INTEGER,
        market_cap REAL,
        pe_trailing REAL,
        pe_forward REAL,
        peg_ratio REAL,
        price_to_book REAL,
        revenue_growth REAL,
        profit_margin REAL,
        dividend_yield REAL,
        beta REAL,
        fifty_two_week_high REAL,
        fifty_two_week_low REAL,
        avg_volume INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_metrics_sector ON stock_metrics(sector);

    -- Price history
    CREATE TABLE IF NOT EXISTS price_history (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_history(ticker);
    CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_price_ticker_date ON price_history(ticker, date);

    -- Macro indicators
    CREATE TABLE IF NOT EXISTS macro_indicators (
        id TEXT PRIMARY KEY,
        series_id TEXT NOT NULL,
        name TEXT NOT NULL,
        value REAL NOT NULL,
        previous_value REAL,
        unit TEXT,
        trend TEXT DEFAULT 'flat',
        source TEXT DEFAULT 'FRED',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_macro_series ON macro_indicators(series_id);

    -- Macro risks
    CREATE TABLE IF NOT EXISTS macro_risks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        severity TEXT NOT NULL,
        description TEXT NOT NULL,
        likelihood REAL DEFAULT 0.5,
        affected_sectors TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- News items
    CREATE TABLE IF NOT EXISTS news_items (
        id TEXT PRIMARY KEY,
        headline TEXT NOT NULL,
        source TEXT NOT NULL,
        url TEXT,
        category TEXT NOT NULL,
        published_at TIMESTAMP,
        relevance_score REAL DEFAULT 0.5,
        tickers_mentioned TEXT,
        excerpt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);
    CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at);

    -- Track scrape/pipeline runs
    CREATE TABLE IF NOT EXISTS scrape_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        records_added INTEGER DEFAULT 0,
        records_skipped INTEGER DEFAULT 0,
        error TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_scrape_source ON scrape_runs(source);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        with self._connection() as conn:
            conn.executescript(self.SCHEMA)
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    # =========================================================================
    # Congress Trades
    # =========================================================================

    def upsert_congress_trade(self, trade: CongressTrade) -> bool:
        """
        Insert or update a congress trade.

        Returns True if inserted, False if already existed.
        """
        with self._connection() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM congress_trades WHERE id = ?",
                (trade.id,)
            ).fetchone()

            if existing:
                return False

            conn.execute(
                """
                INSERT INTO congress_trades
                (id, politician, party, chamber, state, ticker, issuer,
                 transaction_type, amount_low, amount_high, traded_date, disclosed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.id,
                    trade.politician,
                    trade.party,
                    trade.chamber,
                    trade.state,
                    trade.ticker,
                    trade.issuer,
                    trade.transaction_type,
                    trade.amount_low,
                    trade.amount_high,
                    trade.traded_date,
                    trade.disclosed_date,
                )
            )
            return True

    def get_congress_trades(
        self,
        ticker: Optional[str] = None,
        politician: Optional[str] = None,
        days: int = 90,
        limit: int = 100,
    ) -> list[CongressTrade]:
        """Get congress trades with optional filters."""
        query = """
            SELECT * FROM congress_trades
            WHERE disclosed_date >= date('now', ?)
        """
        params: list = [f"-{days} days"]

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())

        if politician:
            query += " AND politician LIKE ?"
            params.append(f"%{politician}%")

        query += " ORDER BY disclosed_date DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_congress_trade(row) for row in rows]

    def get_all_congress_trades(self, limit: int = 1000) -> list[CongressTrade]:
        """Get all congress trades, most recent first."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM congress_trades
                ORDER BY disclosed_date DESC, created_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [self._row_to_congress_trade(row) for row in rows]

    def _row_to_congress_trade(self, row: sqlite3.Row) -> CongressTrade:
        """Convert database row to CongressTrade."""
        return CongressTrade(
            id=row["id"],
            politician=row["politician"],
            party=row["party"],
            chamber=row["chamber"],
            state=row["state"] or "",
            ticker=row["ticker"],
            issuer=row["issuer"] or "",
            transaction_type=row["transaction_type"],
            amount_low=row["amount_low"],
            amount_high=row["amount_high"],
            traded_date=row["traded_date"],
            disclosed_date=row["disclosed_date"],
            created_at=row["created_at"] or datetime.now(),
        )

    # =========================================================================
    # Options Activity
    # =========================================================================

    def upsert_options_activity(self, activity: OptionsActivity) -> bool:
        """
        Insert or update options activity.

        Returns True if inserted, False if already existed.
        """
        with self._connection() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM options_activity WHERE id = ?",
                (activity.id,)
            ).fetchone()

            if existing:
                return False

            conn.execute(
                """
                INSERT INTO options_activity
                (id, ticker, option_type, strike, expiry, volume, open_interest,
                 volume_oi_ratio, implied_volatility, premium_total, direction, strength)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity.id,
                    activity.ticker,
                    activity.option_type,
                    activity.strike,
                    activity.expiry,
                    activity.volume,
                    activity.open_interest,
                    activity.volume_oi_ratio,
                    activity.implied_volatility,
                    activity.premium_total,
                    activity.direction,
                    activity.strength,
                )
            )
            return True

    def get_options_activity(
        self,
        ticker: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[OptionsActivity]:
        """Get recent options activity with optional filters."""
        query = """
            SELECT * FROM options_activity
            WHERE created_at >= datetime('now', ?)
        """
        params: list = [f"-{hours} hours"]

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())

        query += " ORDER BY strength DESC, volume_oi_ratio DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_options_activity(row) for row in rows]

    def get_all_options_activity(self, limit: int = 1000) -> list[OptionsActivity]:
        """Get all options activity, most recent first."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM options_activity
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [self._row_to_options_activity(row) for row in rows]

    def _row_to_options_activity(self, row: sqlite3.Row) -> OptionsActivity:
        """Convert database row to OptionsActivity."""
        return OptionsActivity(
            id=row["id"],
            ticker=row["ticker"],
            option_type=row["option_type"],
            strike=row["strike"],
            expiry=row["expiry"],
            volume=row["volume"],
            open_interest=row["open_interest"],
            volume_oi_ratio=row["volume_oi_ratio"],
            implied_volatility=row["implied_volatility"],
            premium_total=row["premium_total"],
            direction=row["direction"],
            strength=row["strength"],
            created_at=row["created_at"] or datetime.now(),
        )

    # =========================================================================
    # Scrape Runs
    # =========================================================================

    def start_scrape_run(self, source: str) -> ScrapeRun:
        """Start a new scrape run and return it."""
        run = ScrapeRun(source=source, started_at=datetime.now())
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scrape_runs (source, started_at)
                VALUES (?, ?)
                """,
                (run.source, run.started_at)
            )
            run.id = cursor.lastrowid
        return run

    def complete_scrape_run(
        self,
        run: ScrapeRun,
        records_added: int = 0,
        records_skipped: int = 0,
        error: Optional[str] = None,
    ):
        """Mark a scrape run as completed."""
        run.completed_at = datetime.now()
        run.records_added = records_added
        run.records_skipped = records_skipped
        run.error = error

        with self._connection() as conn:
            conn.execute(
                """
                UPDATE scrape_runs
                SET completed_at = ?, records_added = ?, records_skipped = ?, error = ?
                WHERE id = ?
                """,
                (run.completed_at, run.records_added, run.records_skipped, run.error, run.id)
            )

    def get_last_scrape_run(self, source: str) -> Optional[ScrapeRun]:
        """Get the most recent scrape run for a source."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM scrape_runs
                WHERE source = ? AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (source,)
            ).fetchone()

            if not row:
                return None

            return ScrapeRun(
                id=row["id"],
                source=row["source"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                records_added=row["records_added"],
                records_skipped=row["records_skipped"],
                error=row["error"],
            )

    # =========================================================================
    # Stock Picks
    # =========================================================================

    def upsert_stock_pick(self, pick: StockPick) -> bool:
        """Insert or update a stock pick. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM stock_picks WHERE id = ?", (pick.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE stock_picks SET
                        ticker=?, timeframe=?, conviction_score=?, thesis=?,
                        entry_price=?, target_price=?, stop_loss=?, risk_factors=?
                    WHERE id=?
                    """,
                    (pick.ticker, pick.timeframe, pick.conviction_score, pick.thesis,
                     pick.entry_price, pick.target_price, pick.stop_loss,
                     pick.risk_factors, pick.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO stock_picks
                (id, ticker, timeframe, conviction_score, thesis, entry_price,
                 target_price, stop_loss, risk_factors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pick.id, pick.ticker, pick.timeframe, pick.conviction_score,
                 pick.thesis, pick.entry_price, pick.target_price, pick.stop_loss,
                 pick.risk_factors)
            )
            return True

    def get_stock_picks(self, timeframe: Optional[str] = None, limit: int = 100) -> list[StockPick]:
        """Get stock picks, optionally filtered by timeframe."""
        query = "SELECT * FROM stock_picks"
        params = []

        if timeframe:
            query += " WHERE timeframe = ?"
            params.append(timeframe)

        query += " ORDER BY conviction_score DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_stock_pick(row) for row in rows]

    def _row_to_stock_pick(self, row: sqlite3.Row) -> StockPick:
        return StockPick(
            id=row["id"],
            ticker=row["ticker"],
            timeframe=row["timeframe"],
            conviction_score=row["conviction_score"],
            thesis=row["thesis"],
            entry_price=row["entry_price"],
            target_price=row["target_price"],
            stop_loss=row["stop_loss"],
            risk_factors=row["risk_factors"] or "",
            created_at=row["created_at"] or datetime.now(),
        )

    def clear_stock_picks(self):
        """Clear all stock picks (for fresh generation)."""
        with self._connection() as conn:
            conn.execute("DELETE FROM stock_picks")

    # =========================================================================
    # Stock Metrics
    # =========================================================================

    def upsert_stock_metrics(self, metrics: StockMetrics) -> bool:
        """Insert or update stock metrics. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT ticker FROM stock_metrics WHERE ticker = ?", (metrics.ticker,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE stock_metrics SET
                        name=?, sector=?, industry=?, price=?, previous_close=?,
                        change=?, change_percent=?, volume=?, market_cap=?,
                        pe_trailing=?, pe_forward=?, peg_ratio=?, price_to_book=?,
                        revenue_growth=?, profit_margin=?, dividend_yield=?, beta=?,
                        fifty_two_week_high=?, fifty_two_week_low=?, avg_volume=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE ticker=?
                    """,
                    (metrics.name, metrics.sector, metrics.industry, metrics.price,
                     metrics.previous_close, metrics.change, metrics.change_percent,
                     metrics.volume, metrics.market_cap, metrics.pe_trailing,
                     metrics.pe_forward, metrics.peg_ratio, metrics.price_to_book,
                     metrics.revenue_growth, metrics.profit_margin, metrics.dividend_yield,
                     metrics.beta, metrics.fifty_two_week_high, metrics.fifty_two_week_low,
                     metrics.avg_volume, metrics.ticker)
                )
                return False

            conn.execute(
                """
                INSERT INTO stock_metrics
                (ticker, name, sector, industry, price, previous_close, change,
                 change_percent, volume, market_cap, pe_trailing, pe_forward,
                 peg_ratio, price_to_book, revenue_growth, profit_margin,
                 dividend_yield, beta, fifty_two_week_high, fifty_two_week_low, avg_volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (metrics.ticker, metrics.name, metrics.sector, metrics.industry,
                 metrics.price, metrics.previous_close, metrics.change,
                 metrics.change_percent, metrics.volume, metrics.market_cap,
                 metrics.pe_trailing, metrics.pe_forward, metrics.peg_ratio,
                 metrics.price_to_book, metrics.revenue_growth, metrics.profit_margin,
                 metrics.dividend_yield, metrics.beta, metrics.fifty_two_week_high,
                 metrics.fifty_two_week_low, metrics.avg_volume)
            )
            return True

    def get_stock_metrics(self, ticker: str) -> Optional[StockMetrics]:
        """Get metrics for a single stock."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM stock_metrics WHERE ticker = ?", (ticker.upper(),)
            ).fetchone()
            return self._row_to_stock_metrics(row) if row else None

    def get_all_stock_metrics(self, limit: int = 500) -> list[StockMetrics]:
        """Get all stock metrics."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM stock_metrics ORDER BY ticker LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_stock_metrics(row) for row in rows]

    def _row_to_stock_metrics(self, row: sqlite3.Row) -> StockMetrics:
        return StockMetrics(
            ticker=row["ticker"],
            name=row["name"],
            sector=row["sector"],
            industry=row["industry"],
            price=row["price"],
            previous_close=row["previous_close"],
            change=row["change"],
            change_percent=row["change_percent"],
            volume=row["volume"],
            market_cap=row["market_cap"],
            pe_trailing=row["pe_trailing"],
            pe_forward=row["pe_forward"],
            peg_ratio=row["peg_ratio"],
            price_to_book=row["price_to_book"],
            revenue_growth=row["revenue_growth"],
            profit_margin=row["profit_margin"],
            dividend_yield=row["dividend_yield"],
            beta=row["beta"],
            fifty_two_week_high=row["fifty_two_week_high"],
            fifty_two_week_low=row["fifty_two_week_low"],
            avg_volume=row["avg_volume"],
            updated_at=row["updated_at"] or datetime.now(),
        )

    # =========================================================================
    # Price History
    # =========================================================================

    def upsert_price_point(self, point: PricePoint) -> bool:
        """Insert or update a price point. Returns True if inserted."""
        with self._connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO price_history
                    (id, ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (point.id, point.ticker, point.date, point.open, point.high,
                     point.low, point.close, point.volume)
                )
                return True
            except:
                return False

    def get_price_history(self, ticker: str, days: int = 365) -> list[PricePoint]:
        """Get price history for a ticker."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM price_history
                WHERE ticker = ? AND date >= date('now', ?)
                ORDER BY date ASC
                """,
                (ticker.upper(), f"-{days} days")
            ).fetchall()
            return [self._row_to_price_point(row) for row in rows]

    def _row_to_price_point(self, row: sqlite3.Row) -> PricePoint:
        return PricePoint(
            id=row["id"],
            ticker=row["ticker"],
            date=row["date"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            created_at=row["created_at"] or datetime.now(),
        )

    # =========================================================================
    # Macro Indicators
    # =========================================================================

    def upsert_macro_indicator(self, indicator: MacroIndicator) -> bool:
        """Insert or update a macro indicator. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM macro_indicators WHERE id = ?", (indicator.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE macro_indicators SET
                        series_id=?, name=?, value=?, previous_value=?,
                        unit=?, trend=?, source=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (indicator.series_id, indicator.name, indicator.value,
                     indicator.previous_value, indicator.unit, indicator.trend,
                     indicator.source, indicator.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO macro_indicators
                (id, series_id, name, value, previous_value, unit, trend, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (indicator.id, indicator.series_id, indicator.name, indicator.value,
                 indicator.previous_value, indicator.unit, indicator.trend, indicator.source)
            )
            return True

    def get_macro_indicators(self) -> list[MacroIndicator]:
        """Get all macro indicators."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM macro_indicators ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_macro_indicator(row) for row in rows]

    def _row_to_macro_indicator(self, row: sqlite3.Row) -> MacroIndicator:
        return MacroIndicator(
            id=row["id"],
            series_id=row["series_id"],
            name=row["name"],
            value=row["value"],
            previous_value=row["previous_value"],
            unit=row["unit"] or "",
            trend=row["trend"] or "flat",
            source=row["source"] or "FRED",
            updated_at=row["updated_at"] or datetime.now(),
        )

    # =========================================================================
    # Macro Risks
    # =========================================================================

    def upsert_macro_risk(self, risk: MacroRisk) -> bool:
        """Insert or update a macro risk. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM macro_risks WHERE id = ?", (risk.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE macro_risks SET
                        name=?, severity=?, description=?, likelihood=?, affected_sectors=?
                    WHERE id=?
                    """,
                    (risk.name, risk.severity, risk.description, risk.likelihood,
                     risk.affected_sectors, risk.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO macro_risks
                (id, name, severity, description, likelihood, affected_sectors)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (risk.id, risk.name, risk.severity, risk.description,
                 risk.likelihood, risk.affected_sectors)
            )
            return True

    def get_macro_risks(self) -> list[MacroRisk]:
        """Get all macro risks."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM macro_risks ORDER BY likelihood DESC"
            ).fetchall()
            return [self._row_to_macro_risk(row) for row in rows]

    def _row_to_macro_risk(self, row: sqlite3.Row) -> MacroRisk:
        return MacroRisk(
            id=row["id"],
            name=row["name"],
            severity=row["severity"],
            description=row["description"],
            likelihood=row["likelihood"],
            affected_sectors=row["affected_sectors"] or "",
            created_at=row["created_at"] or datetime.now(),
        )

    def clear_macro_risks(self):
        """Clear all macro risks."""
        with self._connection() as conn:
            conn.execute("DELETE FROM macro_risks")

    # =========================================================================
    # News Items
    # =========================================================================

    def upsert_news_item(self, item: NewsItem) -> bool:
        """Insert or update a news item. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM news_items WHERE id = ?", (item.id,)
            ).fetchone()

            if existing:
                return False

            conn.execute(
                """
                INSERT INTO news_items
                (id, headline, source, url, category, published_at,
                 relevance_score, tickers_mentioned, excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item.id, item.headline, item.source, item.url, item.category,
                 item.published_at, item.relevance_score, item.tickers_mentioned,
                 item.excerpt)
            )
            return True

    def get_news_items(self, category: Optional[str] = None, hours: int = 48, limit: int = 100) -> list[NewsItem]:
        """Get recent news items."""
        query = "SELECT * FROM news_items WHERE created_at >= datetime('now', ?)"
        params: list = [f"-{hours} hours"]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY published_at DESC, relevance_score DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_news_item(row) for row in rows]

    def get_news_for_ticker(self, ticker: str, limit: int = 20) -> list[NewsItem]:
        """Get news mentioning a specific ticker."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM news_items
                WHERE tickers_mentioned LIKE ?
                ORDER BY published_at DESC LIMIT ?
                """,
                (f'%"{ticker.upper()}"%', limit)
            ).fetchall()
            return [self._row_to_news_item(row) for row in rows]

    def _row_to_news_item(self, row: sqlite3.Row) -> NewsItem:
        return NewsItem(
            id=row["id"],
            headline=row["headline"],
            source=row["source"],
            url=row["url"] or "",
            category=row["category"],
            published_at=row["published_at"],
            relevance_score=row["relevance_score"],
            tickers_mentioned=row["tickers_mentioned"] or "",
            excerpt=row["excerpt"] or "",
            created_at=row["created_at"] or datetime.now(),
        )

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._connection() as conn:
            def count(table): return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

            return {
                "congress_trades": count("congress_trades"),
                "options_activity": count("options_activity"),
                "stock_picks": count("stock_picks"),
                "stock_metrics": count("stock_metrics"),
                "price_history": count("price_history"),
                "macro_indicators": count("macro_indicators"),
                "macro_risks": count("macro_risks"),
                "news_items": count("news_items"),
                "scrape_runs": conn.execute(
                    "SELECT COUNT(*) FROM scrape_runs WHERE completed_at IS NOT NULL"
                ).fetchone()[0],
                "db_path": str(self.db_path),
                "db_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2)
                if self.db_path.exists() else 0,
            }


# Singleton instance
_db_instance: Optional[Database] = None


def get_db(db_path: Optional[Path] = None) -> Database:
    """Get the database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
