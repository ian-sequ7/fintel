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
    PickPerformance,
    HedgeFund,
    HedgeFundHolding,
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

    -- Pick performance tracking
    CREATE TABLE IF NOT EXISTS pick_performance (
        id TEXT PRIMARY KEY,
        pick_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        entry_price REAL NOT NULL,
        entry_date DATE NOT NULL,
        target_price REAL,
        stop_loss REAL,
        price_7d REAL,
        return_7d REAL,
        price_30d REAL,
        return_30d REAL,
        price_90d REAL,
        return_90d REAL,
        target_hit INTEGER DEFAULT 0,
        target_hit_date DATE,
        stop_hit INTEGER DEFAULT 0,
        stop_hit_date DATE,
        status TEXT DEFAULT 'active',
        final_return REAL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_perf_ticker ON pick_performance(ticker);
    CREATE INDEX IF NOT EXISTS idx_perf_timeframe ON pick_performance(timeframe);
    CREATE INDEX IF NOT EXISTS idx_perf_status ON pick_performance(status);
    CREATE INDEX IF NOT EXISTS idx_perf_entry_date ON pick_performance(entry_date);

    -- Hedge funds tracked for 13F filings
    CREATE TABLE IF NOT EXISTS hedge_funds (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        cik TEXT NOT NULL UNIQUE,
        manager TEXT NOT NULL,
        aum REAL,
        style TEXT,
        is_active INTEGER DEFAULT 1,
        last_filing_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_hf_cik ON hedge_funds(cik);
    CREATE INDEX IF NOT EXISTS idx_hf_manager ON hedge_funds(manager);

    -- Hedge fund holdings from 13F filings
    CREATE TABLE IF NOT EXISTS hedge_fund_holdings (
        id TEXT PRIMARY KEY,
        fund_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        cusip TEXT NOT NULL,
        issuer_name TEXT NOT NULL,
        shares INTEGER NOT NULL,
        value INTEGER NOT NULL,
        filing_date DATE NOT NULL,
        report_date DATE NOT NULL,
        prev_shares INTEGER,
        prev_value INTEGER,
        shares_change INTEGER,
        shares_change_pct REAL,
        action TEXT DEFAULT 'hold',
        portfolio_pct REAL,
        rank INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (fund_id) REFERENCES hedge_funds(id)
    );

    CREATE INDEX IF NOT EXISTS idx_hfh_fund ON hedge_fund_holdings(fund_id);
    CREATE INDEX IF NOT EXISTS idx_hfh_ticker ON hedge_fund_holdings(ticker);
    CREATE INDEX IF NOT EXISTS idx_hfh_filing ON hedge_fund_holdings(filing_date);
    CREATE INDEX IF NOT EXISTS idx_hfh_action ON hedge_fund_holdings(action);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_hfh_fund_cusip_report ON hedge_fund_holdings(fund_id, cusip, report_date);
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
    # Pick Performance
    # =========================================================================

    def upsert_pick_performance(self, perf: PickPerformance) -> bool:
        """Insert or update pick performance. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM pick_performance WHERE id = ?", (perf.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE pick_performance SET
                        price_7d=?, return_7d=?, price_30d=?, return_30d=?,
                        price_90d=?, return_90d=?, target_hit=?, target_hit_date=?,
                        stop_hit=?, stop_hit_date=?, status=?, final_return=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (perf.price_7d, perf.return_7d, perf.price_30d, perf.return_30d,
                     perf.price_90d, perf.return_90d, perf.target_hit, perf.target_hit_date,
                     perf.stop_hit, perf.stop_hit_date, perf.status, perf.final_return,
                     perf.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO pick_performance
                (id, pick_id, ticker, timeframe, entry_price, entry_date,
                 target_price, stop_loss, price_7d, return_7d, price_30d, return_30d,
                 price_90d, return_90d, target_hit, target_hit_date, stop_hit,
                 stop_hit_date, status, final_return)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (perf.id, perf.pick_id, perf.ticker, perf.timeframe, perf.entry_price,
                 perf.entry_date, perf.target_price, perf.stop_loss, perf.price_7d,
                 perf.return_7d, perf.price_30d, perf.return_30d, perf.price_90d,
                 perf.return_90d, perf.target_hit, perf.target_hit_date, perf.stop_hit,
                 perf.stop_hit_date, perf.status, perf.final_return)
            )
            return True

    def get_pick_performance(self, pick_id: str) -> Optional[PickPerformance]:
        """Get performance for a specific pick."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM pick_performance WHERE pick_id = ?", (pick_id,)
            ).fetchone()
            return self._row_to_pick_performance(row) if row else None

    def get_all_performance(
        self,
        timeframe: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500
    ) -> list[PickPerformance]:
        """Get all pick performance records."""
        query = "SELECT * FROM pick_performance WHERE 1=1"
        params = []

        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY entry_date DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_pick_performance(row) for row in rows]

    def get_active_picks_for_update(self) -> list[PickPerformance]:
        """Get active picks that need performance updates."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pick_performance
                WHERE status = 'active'
                ORDER BY entry_date ASC
                """
            ).fetchall()
            return [self._row_to_pick_performance(row) for row in rows]

    def _row_to_pick_performance(self, row: sqlite3.Row) -> PickPerformance:
        return PickPerformance(
            id=row["id"],
            pick_id=row["pick_id"],
            ticker=row["ticker"],
            timeframe=row["timeframe"],
            entry_price=row["entry_price"],
            entry_date=row["entry_date"],
            target_price=row["target_price"],
            stop_loss=row["stop_loss"],
            price_7d=row["price_7d"],
            return_7d=row["return_7d"],
            price_30d=row["price_30d"],
            return_30d=row["return_30d"],
            price_90d=row["price_90d"],
            return_90d=row["return_90d"],
            target_hit=bool(row["target_hit"]),
            target_hit_date=row["target_hit_date"],
            stop_hit=bool(row["stop_hit"]),
            stop_hit_date=row["stop_hit_date"],
            status=row["status"],
            final_return=row["final_return"],
            updated_at=row["updated_at"] or datetime.now(),
        )

    def get_performance_summary(self, timeframe: Optional[str] = None) -> dict:
        """Get aggregate performance statistics."""
        with self._connection() as conn:
            where = "WHERE 1=1"
            params = []

            if timeframe:
                where += " AND timeframe = ?"
                params.append(timeframe)

            # Total picks tracked
            total = conn.execute(
                f"SELECT COUNT(*) FROM pick_performance {where}", params
            ).fetchone()[0]

            if total == 0:
                return {
                    "total_picks": 0,
                    "win_rate": 0,
                    "avg_return_7d": 0,
                    "avg_return_30d": 0,
                    "avg_return_90d": 0,
                    "best_pick": None,
                    "worst_pick": None,
                    "active": 0,
                    "won": 0,
                    "lost": 0,
                }

            # Win rate (positive return or target hit)
            winners = conn.execute(
                f"""
                SELECT COUNT(*) FROM pick_performance
                {where} AND (target_hit = 1 OR
                    COALESCE(return_90d, return_30d, return_7d, 0) > 0)
                """, params
            ).fetchone()[0]

            # Average returns
            avg_7d = conn.execute(
                f"SELECT AVG(return_7d) FROM pick_performance {where} AND return_7d IS NOT NULL",
                params
            ).fetchone()[0] or 0

            avg_30d = conn.execute(
                f"SELECT AVG(return_30d) FROM pick_performance {where} AND return_30d IS NOT NULL",
                params
            ).fetchone()[0] or 0

            avg_90d = conn.execute(
                f"SELECT AVG(return_90d) FROM pick_performance {where} AND return_90d IS NOT NULL",
                params
            ).fetchone()[0] or 0

            # Best and worst picks
            best = conn.execute(
                f"""
                SELECT ticker, COALESCE(return_90d, return_30d, return_7d) as ret
                FROM pick_performance {where}
                ORDER BY ret DESC LIMIT 1
                """, params
            ).fetchone()

            worst = conn.execute(
                f"""
                SELECT ticker, COALESCE(return_90d, return_30d, return_7d) as ret
                FROM pick_performance {where}
                ORDER BY ret ASC LIMIT 1
                """, params
            ).fetchone()

            # Status counts
            active = conn.execute(
                f"SELECT COUNT(*) FROM pick_performance {where} AND status = 'active'",
                params
            ).fetchone()[0]

            won = conn.execute(
                f"SELECT COUNT(*) FROM pick_performance {where} AND status = 'won'",
                params
            ).fetchone()[0]

            lost = conn.execute(
                f"SELECT COUNT(*) FROM pick_performance {where} AND status = 'lost'",
                params
            ).fetchone()[0]

            return {
                "total_picks": total,
                "win_rate": round(winners / total * 100, 1) if total > 0 else 0,
                "avg_return_7d": round(avg_7d, 2),
                "avg_return_30d": round(avg_30d, 2),
                "avg_return_90d": round(avg_90d, 2),
                "best_pick": {"ticker": best[0], "return": round(best[1], 2)} if best and best[1] else None,
                "worst_pick": {"ticker": worst[0], "return": round(worst[1], 2)} if worst and worst[1] else None,
                "active": active,
                "won": won,
                "lost": lost,
            }

    # =========================================================================
    # Hedge Funds
    # =========================================================================

    def upsert_hedge_fund(self, fund: HedgeFund) -> bool:
        """Insert or update a hedge fund. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM hedge_funds WHERE id = ?", (fund.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE hedge_funds SET
                        name=?, cik=?, manager=?, aum=?, style=?,
                        is_active=?, last_filing_date=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (fund.name, fund.cik, fund.manager, fund.aum, fund.style,
                     fund.is_active, fund.last_filing_date, fund.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO hedge_funds
                (id, name, cik, manager, aum, style, is_active, last_filing_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fund.id, fund.name, fund.cik, fund.manager, fund.aum,
                 fund.style, fund.is_active, fund.last_filing_date)
            )
            return True

    def get_hedge_fund(self, fund_id: str) -> Optional[HedgeFund]:
        """Get a hedge fund by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM hedge_funds WHERE id = ?", (fund_id,)
            ).fetchone()
            return self._row_to_hedge_fund(row) if row else None

    def get_hedge_fund_by_cik(self, cik: str) -> Optional[HedgeFund]:
        """Get a hedge fund by CIK."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM hedge_funds WHERE cik = ?", (cik.zfill(10),)
            ).fetchone()
            return self._row_to_hedge_fund(row) if row else None

    def get_all_hedge_funds(self, active_only: bool = True) -> list[HedgeFund]:
        """Get all tracked hedge funds."""
        query = "SELECT * FROM hedge_funds"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"

        with self._connection() as conn:
            rows = conn.execute(query).fetchall()
            return [self._row_to_hedge_fund(row) for row in rows]

    def _row_to_hedge_fund(self, row: sqlite3.Row) -> HedgeFund:
        return HedgeFund(
            id=row["id"],
            name=row["name"],
            cik=row["cik"],
            manager=row["manager"],
            aum=row["aum"],
            style=row["style"] or "",
            is_active=bool(row["is_active"]),
            last_filing_date=row["last_filing_date"],
            created_at=row["created_at"] or datetime.now(),
            updated_at=row["updated_at"] or datetime.now(),
        )

    # =========================================================================
    # Hedge Fund Holdings
    # =========================================================================

    def upsert_hedge_fund_holding(self, holding: HedgeFundHolding) -> bool:
        """Insert or update a hedge fund holding. Returns True if inserted."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM hedge_fund_holdings WHERE id = ?", (holding.id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE hedge_fund_holdings SET
                        shares=?, value=?, prev_shares=?, prev_value=?,
                        shares_change=?, shares_change_pct=?, action=?,
                        portfolio_pct=?, rank=?
                    WHERE id=?
                    """,
                    (holding.shares, holding.value, holding.prev_shares,
                     holding.prev_value, holding.shares_change, holding.shares_change_pct,
                     holding.action, holding.portfolio_pct, holding.rank, holding.id)
                )
                return False

            conn.execute(
                """
                INSERT INTO hedge_fund_holdings
                (id, fund_id, ticker, cusip, issuer_name, shares, value,
                 filing_date, report_date, prev_shares, prev_value, shares_change,
                 shares_change_pct, action, portfolio_pct, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (holding.id, holding.fund_id, holding.ticker, holding.cusip,
                 holding.issuer_name, holding.shares, holding.value, holding.filing_date,
                 holding.report_date, holding.prev_shares, holding.prev_value,
                 holding.shares_change, holding.shares_change_pct, holding.action,
                 holding.portfolio_pct, holding.rank)
            )
            return True

    def get_holdings_for_fund(
        self,
        fund_id: str,
        report_date: Optional[date] = None,
        limit: int = 100
    ) -> list[HedgeFundHolding]:
        """Get holdings for a specific fund, optionally for a specific quarter."""
        query = "SELECT * FROM hedge_fund_holdings WHERE fund_id = ?"
        params: list = [fund_id]

        if report_date:
            query += " AND report_date = ?"
            params.append(report_date)
        else:
            # Get latest report date
            query += " AND report_date = (SELECT MAX(report_date) FROM hedge_fund_holdings WHERE fund_id = ?)"
            params.append(fund_id)

        query += " ORDER BY value DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_hedge_fund_holding(row) for row in rows]

    def get_holdings_for_ticker(self, ticker: str, limit: int = 50) -> list[HedgeFundHolding]:
        """Get all hedge fund holdings for a specific ticker."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT h.*, f.name as fund_name, f.manager
                FROM hedge_fund_holdings h
                JOIN hedge_funds f ON h.fund_id = f.id
                WHERE h.ticker = ?
                AND h.report_date = (
                    SELECT MAX(report_date) FROM hedge_fund_holdings WHERE fund_id = h.fund_id
                )
                ORDER BY h.value DESC LIMIT ?
                """,
                (ticker.upper(), limit)
            ).fetchall()
            return [self._row_to_hedge_fund_holding(row) for row in rows]

    def get_recent_hedge_fund_activity(
        self,
        action: Optional[str] = None,
        limit: int = 100
    ) -> list[HedgeFundHolding]:
        """Get recent hedge fund activity (new positions, increases, decreases)."""
        query = """
            SELECT h.*, f.name as fund_name, f.manager
            FROM hedge_fund_holdings h
            JOIN hedge_funds f ON h.fund_id = f.id
            WHERE h.action != 'hold'
        """
        params: list = []

        if action:
            query += " AND h.action = ?"
            params.append(action)

        query += " ORDER BY h.filing_date DESC, h.value DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_hedge_fund_holding(row) for row in rows]

    def get_previous_holding(
        self,
        fund_id: str,
        ticker: str,
        before_date: date
    ) -> Optional[HedgeFundHolding]:
        """Get the previous quarter's holding for comparison."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM hedge_fund_holdings
                WHERE fund_id = ? AND ticker = ? AND report_date < ?
                ORDER BY report_date DESC LIMIT 1
                """,
                (fund_id, ticker, before_date)
            ).fetchone()
            return self._row_to_hedge_fund_holding(row) if row else None

    def _row_to_hedge_fund_holding(self, row: sqlite3.Row) -> HedgeFundHolding:
        return HedgeFundHolding(
            id=row["id"],
            fund_id=row["fund_id"],
            ticker=row["ticker"],
            cusip=row["cusip"],
            issuer_name=row["issuer_name"],
            shares=row["shares"],
            value=row["value"],
            filing_date=row["filing_date"],
            report_date=row["report_date"],
            prev_shares=row["prev_shares"],
            prev_value=row["prev_value"],
            shares_change=row["shares_change"],
            shares_change_pct=row["shares_change_pct"],
            action=row["action"] or "hold",
            portfolio_pct=row["portfolio_pct"],
            rank=row["rank"],
            created_at=row["created_at"] or datetime.now(),
        )

    def get_hedge_fund_summary(self) -> dict:
        """Get summary statistics for hedge fund tracking."""
        with self._connection() as conn:
            funds = conn.execute("SELECT COUNT(*) FROM hedge_funds WHERE is_active = 1").fetchone()[0]

            # Get unique tickers across all funds
            tickers = conn.execute(
                """
                SELECT COUNT(DISTINCT ticker) FROM hedge_fund_holdings
                WHERE report_date = (SELECT MAX(report_date) FROM hedge_fund_holdings)
                """
            ).fetchone()[0]

            # Recent activity
            new_positions = conn.execute(
                "SELECT COUNT(*) FROM hedge_fund_holdings WHERE action = 'new'"
            ).fetchone()[0]

            increased = conn.execute(
                "SELECT COUNT(*) FROM hedge_fund_holdings WHERE action = 'increased'"
            ).fetchone()[0]

            decreased = conn.execute(
                "SELECT COUNT(*) FROM hedge_fund_holdings WHERE action = 'decreased'"
            ).fetchone()[0]

            sold = conn.execute(
                "SELECT COUNT(*) FROM hedge_fund_holdings WHERE action = 'sold'"
            ).fetchone()[0]

            return {
                "funds_tracked": funds,
                "unique_tickers": tickers,
                "new_positions": new_positions,
                "increased": increased,
                "decreased": decreased,
                "sold": sold,
            }

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
                "pick_performance": count("pick_performance"),
                "hedge_funds": count("hedge_funds"),
                "hedge_fund_holdings": count("hedge_fund_holdings"),
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
