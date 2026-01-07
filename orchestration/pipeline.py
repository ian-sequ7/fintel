"""
Main orchestration pipeline.

Coordinates all components:
1. Data fetching (adapters)
2. Transformation (raw → domain objects)
3. Analysis (scoring, classification)
4. Report generation

Handles partial failures gracefully - never crashes on single source failure.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from domain import (
    Observation,
    Category,
    StockPick,
    MacroIndicator,
    Risk,
    Trend,
    Impact,
    StockMetrics,
    MacroContext,
    ConvictionScore,
    ScoringConfig,
    Strategy,
    score_stock,
    classify_timeframe,
    identify_headwinds,
    identify_stock_risks,
    rank_picks,
    generate_thesis,
    ScoredNewsItem,
    NewsCategory,
    aggregate_news,
    RawNewsItem,
    # V2 Scoring
    ScoredPick,
    ScoringThresholds,
    ScoringWeights,
    SectorSensitivities,
    TimeframeRules,
    score_stock_v2,
    score_stocks,
)
from domain.models import Timeframe
from domain.analysis_types import RiskCategory
from adapters import YahooAdapter, FredAdapter, RedditAdapter, RssAdapter, CongressAdapter, SEC13FAdapter, get_universe_provider
from ports import FetchError, RateLimitError
from presentation.report import ReportData

logger = logging.getLogger(__name__)


# ============================================================================
# Pipeline Status Tracking
# ============================================================================

class SourceStatus(str, Enum):
    """Status of a data source."""
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    STALE = "stale"


@dataclass
class SourceResult:
    """Result from fetching a single source."""
    source: str
    status: SourceStatus
    observations: list[Observation] = field(default_factory=list)
    error: str | None = None
    fetch_time: datetime = field(default_factory=datetime.now)
    is_cached: bool = False


@dataclass
class PipelineStatus:
    """Overall pipeline execution status."""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    sources: dict[str, SourceResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Check if pipeline has enough data."""
        ok_count = sum(1 for r in self.sources.values() if r.status == SourceStatus.OK)
        return ok_count >= 2  # At least 2 sources working

    @property
    def duration(self) -> timedelta | None:
        """Pipeline execution duration."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None

    def add_warning(self, msg: str) -> None:
        logger.warning(msg)
        self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        logger.error(msg)
        self.errors.append(msg)


# ============================================================================
# Pipeline Configuration
# ============================================================================

@dataclass
class PipelineConfig:
    """Configuration for the orchestration pipeline."""

    # Universe configuration
    universe_source: str = "watchlist"  # "watchlist", "sp500", "sector"
    universe_max_tickers: int = 100
    universe_sectors: list[str] = field(default_factory=lambda: [
        "technology", "healthcare", "financials"
    ])

    # Custom watchlist (used when universe_source="watchlist")
    watchlist: list[str] = field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "JPM", "V",
    ])

    # Data staleness thresholds
    price_stale_minutes: int = 30
    macro_stale_days: int = 7
    news_stale_hours: int = 24

    # Analysis settings
    scoring_config: ScoringConfig = field(default_factory=ScoringConfig)
    strategy: Strategy = field(default_factory=Strategy)

    # V2 Scoring settings
    scoring_thresholds: ScoringThresholds = field(default_factory=ScoringThresholds)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    sector_sensitivities: SectorSensitivities = field(default_factory=lambda: SectorSensitivities(
        rate_sensitivity={
            "technology": -0.2, "financials": 0.3, "utilities": -0.2,
            "real estate": -0.3, "consumer discretionary": -0.15,
            "communication services": -0.1, "healthcare": 0.0,
            "consumer staples": 0.0, "industrials": -0.1, "materials": -0.1, "energy": 0.1,
        },
        inflation_sensitivity={
            "energy": 0.4, "materials": 0.3, "financials": 0.1, "real estate": 0.2,
            "consumer staples": 0.1, "healthcare": 0.0, "industrials": 0.0,
            "technology": -0.1, "consumer discretionary": -0.2, "utilities": -0.1,
            "communication services": -0.1,
        },
        recession_sensitivity={
            "consumer staples": 0.3, "healthcare": 0.3, "utilities": 0.25,
            "communication services": 0.1, "technology": -0.1, "financials": -0.2,
            "industrials": -0.25, "materials": -0.25, "consumer discretionary": -0.3,
            "energy": -0.2, "real estate": -0.15,
        },
    ))
    timeframe_rules: TimeframeRules = field(default_factory=TimeframeRules)

    # Sector average P/E ratios for relative valuation
    sector_pe_averages: dict[str, float] = field(default_factory=lambda: {
        "technology": 28.0,
        "healthcare": 22.0,
        "financials": 12.0,
        "financial services": 12.0,
        "consumer discretionary": 20.0,
        "consumer cyclical": 20.0,
        "consumer staples": 22.0,
        "consumer defensive": 22.0,
        "industrials": 18.0,
        "materials": 15.0,
        "basic materials": 15.0,
        "energy": 12.0,
        "utilities": 18.0,
        "real estate": 35.0,
        "communication services": 18.0,
    })

    # Limits (updated for production scale)
    max_picks_per_timeframe: int = 15
    max_news_items: int = 100
    max_macro_indicators: int = 20
    max_risks_displayed: int = 10

    # Behavior
    fail_fast: bool = False  # If True, stop on first error
    include_social: bool = True
    include_smart_money: bool = True  # Include Congress trades & unusual options
    verbose: bool = False
    use_v2_scoring: bool = True  # Use new systematic scoring

    def get_tickers(self) -> list[str]:
        """
        Resolve tickers based on universe configuration.

        Returns list of tickers to analyze, respecting max_tickers limit.
        """
        if self.universe_source == "watchlist":
            return self.watchlist[:self.universe_max_tickers]

        provider = get_universe_provider()

        if self.universe_source == "sp500":
            tickers = provider.get_tickers()
        elif self.universe_source == "sector":
            tickers = provider.filter_by_sector(self.universe_sectors)
        else:
            # Fallback to watchlist
            return self.watchlist[:self.universe_max_tickers]

        return tickers[:self.universe_max_tickers]


# ============================================================================
# Mock Data for Dry Run
# ============================================================================

def _generate_mock_data() -> dict:
    """Generate mock data for dry-run testing."""
    now = datetime.now()

    return {
        "prices": {
            "AAPL": {"price": 250.00, "change_percent": 1.2, "volume": 45000000},
            "MSFT": {"price": 430.00, "change_percent": 0.8, "volume": 22000000},
            "GOOGL": {"price": 195.00, "change_percent": -0.5, "volume": 18000000},
            "NVDA": {"price": 140.00, "change_percent": 2.5, "volume": 55000000},
            "AMZN": {"price": 225.00, "change_percent": 1.0, "volume": 35000000},
        },
        "fundamentals": {
            "AAPL": {
                "pe_trailing": 32.5, "pe_forward": 28.0, "peg_ratio": 1.8,
                "revenue_growth": 0.08, "earnings_growth": 0.12,
                "profit_margin": 0.26, "roe": 0.45,
                "analyst_rating": 2.0, "price_target": 280.0,
                "sector": "Technology", "industry": "Consumer Electronics",
                "fifty_day_average": 245.0, "average_volume": 50000000,
            },
            "MSFT": {
                "pe_trailing": 38.0, "pe_forward": 32.0, "peg_ratio": 2.2,
                "revenue_growth": 0.15, "earnings_growth": 0.18,
                "profit_margin": 0.35, "roe": 0.38,
                "analyst_rating": 1.8, "price_target": 480.0,
                "sector": "Technology", "industry": "Software",
                "fifty_day_average": 420.0, "average_volume": 25000000,
            },
            "GOOGL": {
                "pe_trailing": 25.0, "pe_forward": 22.0, "peg_ratio": 1.2,
                "revenue_growth": 0.12, "earnings_growth": 0.15,
                "profit_margin": 0.22, "roe": 0.28,
                "analyst_rating": 1.9, "price_target": 220.0,
                "sector": "Communication Services", "industry": "Internet",
                "fifty_day_average": 190.0, "average_volume": 20000000,
            },
            "NVDA": {
                "pe_trailing": 65.0, "pe_forward": 45.0, "peg_ratio": 1.0,
                "revenue_growth": 0.85, "earnings_growth": 1.20,
                "profit_margin": 0.55, "roe": 0.65,
                "analyst_rating": 1.5, "price_target": 180.0,
                "sector": "Technology", "industry": "Semiconductors",
                "fifty_day_average": 130.0, "average_volume": 60000000,
            },
            "AMZN": {
                "pe_trailing": 45.0, "pe_forward": 35.0, "peg_ratio": 1.5,
                "revenue_growth": 0.10, "earnings_growth": 0.25,
                "profit_margin": 0.08, "roe": 0.18,
                "analyst_rating": 1.7, "price_target": 260.0,
                "sector": "Consumer Discretionary", "industry": "Internet Retail",
                "fifty_day_average": 220.0, "average_volume": 40000000,
            },
        },
        "macro": [
            {"series_id": "UNRATE", "name": "Unemployment Rate", "value": 4.2, "unit": "%"},
            {"series_id": "FEDFUNDS", "name": "Federal Funds Rate", "value": 5.25, "unit": "%"},
            {"series_id": "T10Y2Y", "name": "10Y-2Y Treasury Spread", "value": -0.25, "unit": "%"},
            {"series_id": "CPIAUCSL", "name": "CPI (Inflation)", "value": 3.5, "unit": "%"},
            {"series_id": "UMCSENT", "name": "Consumer Sentiment", "value": 68.0, "unit": "Index"},
        ],
        "news": [
            {"title": "Fed signals rate cuts ahead", "source": "Reuters", "category": "market_wide"},
            {"title": "NVDA announces next-gen GPUs", "source": "CNBC", "category": "company"},
            {"title": "Tech sector leads market rally", "source": "MarketWatch", "category": "sector"},
        ],
        "smart_money": [
            {
                "id": "mock_congress_1",
                "signal_type": "congress",
                "ticker": "NVDA",
                "direction": "buy",
                "strength": 0.8,
                "summary": "Nancy Pelosi (D-House) bought NVDA ($100,001 - $250,000)",
                "details": {
                    "politician": "Nancy Pelosi",
                    "party": "D",
                    "chamber": "House",
                    "amount_low": 100001,
                    "amount_high": 250000,
                    "disclosure_date": now.isoformat(),
                },
            },
            {
                "id": "mock_congress_2",
                "signal_type": "congress",
                "ticker": "AAPL",
                "direction": "sell",
                "strength": 0.5,
                "summary": "Dan Crenshaw (R-House) sold AAPL ($15,001 - $50,000)",
                "details": {
                    "politician": "Dan Crenshaw",
                    "party": "R",
                    "chamber": "House",
                    "amount_low": 15001,
                    "amount_high": 50000,
                    "disclosure_date": now.isoformat(),
                },
            },
            {
                "id": "mock_options_1",
                "signal_type": "options",
                "ticker": "NVDA",
                "direction": "buy",
                "strength": 0.75,
                "summary": "Unusual CALL activity on NVDA: $150 2025-02-21, Volume/OI=5.2x",
                "details": {
                    "option_type": "call",
                    "strike": 150.0,
                    "expiry": "2025-02-21",
                    "volume": 5200,
                    "open_interest": 1000,
                    "volume_oi_ratio": 5.2,
                    "implied_volatility": 0.45,
                    "premium_total": 520000.0,
                },
            },
        ],
    }


# ============================================================================
# Data Fetching Layer
# ============================================================================

class DataFetcher:
    """
    Fetches data from all sources with error handling.

    Handles partial failures - continues if one source fails.
    """

    def __init__(self, config: PipelineConfig, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.status = PipelineStatus()

        # Lazy adapter initialization
        self._yahoo: YahooAdapter | None = None
        self._fred: FredAdapter | None = None
        self._reddit: RedditAdapter | None = None
        self._rss: RssAdapter | None = None
        self._congress: CongressAdapter | None = None
        self._sec_13f: SEC13FAdapter | None = None

    @property
    def yahoo(self) -> YahooAdapter:
        if self._yahoo is None:
            self._yahoo = YahooAdapter()
        return self._yahoo

    @property
    def fred(self) -> FredAdapter:
        if self._fred is None:
            self._fred = FredAdapter()
        return self._fred

    @property
    def reddit(self) -> RedditAdapter:
        if self._reddit is None:
            self._reddit = RedditAdapter()
        return self._reddit

    @property
    def rss(self) -> RssAdapter:
        if self._rss is None:
            self._rss = RssAdapter()
        return self._rss

    @property
    def congress(self) -> CongressAdapter:
        if self._congress is None:
            self._congress = CongressAdapter()
        return self._congress

    @property
    def sec_13f(self) -> SEC13FAdapter:
        if self._sec_13f is None:
            self._sec_13f = SEC13FAdapter()
        return self._sec_13f

    def _log(self, msg: str) -> None:
        """Log if verbose mode enabled."""
        if self.config.verbose:
            logger.info(msg)
            print(f"  [VERBOSE] {msg}")

    def fetch_all(
        self,
        offset: int = 0,
        limit: int | None = None,
    ) -> dict[str, list[Observation]]:
        """
        Fetch data from all sources.

        Args:
            offset: Number of items to skip in each result list
            limit: Maximum number of items to return in each result list (None = all)

        Returns dict of source_name -> observations.
        Handles errors gracefully, continues on partial failures.
        """
        if self.dry_run:
            return self._fetch_mock_data(offset, limit)

        results: dict[str, list[Observation]] = {
            "prices": [],
            "fundamentals": [],
            "macro": [],
            "news": [],
            "social": [],
            "smart_money": [],
        }

        # Resolve universe
        tickers = self.config.get_tickers()
        self._log(f"Analyzing {len(tickers)} tickers (source: {self.config.universe_source})")

        # Fetch prices
        self._log("Fetching price data...")
        for ticker in tickers:
            result = self._fetch_source(
                f"yahoo_price_{ticker}",
                lambda t=ticker: self.yahoo.get_price(t),
            )
            if result.status == SourceStatus.OK:
                results["prices"].extend(result.observations)

        # Fetch fundamentals
        self._log("Fetching fundamental data...")
        for ticker in tickers:
            result = self._fetch_source(
                f"yahoo_fund_{ticker}",
                lambda t=ticker: self.yahoo.get_fundamentals(t),
            )
            if result.status == SourceStatus.OK:
                results["fundamentals"].extend(result.observations)

        # Fetch macro
        self._log("Fetching macro indicators...")
        result = self._fetch_source("fred", lambda: self.fred.get_all_indicators())
        if result.status == SourceStatus.OK:
            results["macro"] = result.observations

        # Fetch news from RSS
        self._log("Fetching market news...")
        result = self._fetch_source("rss", lambda: self.rss.get_market_news(limit=50))
        if result.status == SourceStatus.OK:
            results["news"].extend(result.observations)

        # Fetch company news (limit to top 10 tickers to avoid rate limits)
        for ticker in tickers[:10]:
            result = self._fetch_source(
                f"yahoo_news_{ticker}",
                lambda t=ticker: self.yahoo.get_news(t),
            )
            if result.status == SourceStatus.OK:
                results["news"].extend(result.observations)

        # Fetch social sentiment
        if self.config.include_social:
            self._log("Fetching social sentiment...")
            result = self._fetch_source("reddit", lambda: self.reddit.get_all(limit=25))
            if result.status == SourceStatus.OK:
                results["social"] = result.observations

        # Fetch smart money signals (congress trades + unusual options)
        if self.config.include_smart_money:
            self._log("Fetching smart money signals...")

            # Congress trades
            result = self._fetch_source(
                "congress",
                lambda: self.congress.get_recent(days=60, limit=50),
            )
            if result.status == SourceStatus.OK:
                results["smart_money"].extend(result.observations)

            # 13F hedge fund holdings
            result = self._fetch_source(
                "sec_13f",
                lambda: self.sec_13f.get_top_holdings(limit=100),
            )
            if result.status == SourceStatus.OK:
                results["smart_money"].extend(result.observations)
                self._log(f"  sec_13f: {len(result.observations)} observations")

            # Unusual options activity (top 10 tickers)
            for ticker in tickers[:10]:
                result = self._fetch_source(
                    f"options_{ticker}",
                    lambda t=ticker: self.yahoo.get_unusual_options(t),
                )
                if result.status == SourceStatus.OK:
                    results["smart_money"].extend(result.observations)

        self.status.completed_at = datetime.now()

        # Apply pagination to all result lists
        paginated_results = {}
        for key, obs_list in results.items():
            end_idx = offset + limit if limit else None
            paginated_results[key] = obs_list[offset:end_idx]

        return paginated_results

    def _fetch_source(
        self,
        source_name: str,
        fetcher: Callable[[], list[Observation]],
    ) -> SourceResult:
        """Fetch from a single source with error handling."""
        try:
            observations = fetcher()
            result = SourceResult(
                source=source_name,
                status=SourceStatus.OK,
                observations=observations,
            )
            self._log(f"  {source_name}: {len(observations)} observations")

        except RateLimitError as e:
            self.status.add_warning(f"{source_name}: Rate limited - {e}")
            result = SourceResult(
                source=source_name,
                status=SourceStatus.FAILED,
                error=str(e),
            )

        except FetchError as e:
            self.status.add_warning(f"{source_name}: Fetch failed - {e}")
            result = SourceResult(
                source=source_name,
                status=SourceStatus.FAILED,
                error=str(e),
            )

        except Exception as e:
            self.status.add_error(f"{source_name}: Unexpected error - {e}")
            result = SourceResult(
                source=source_name,
                status=SourceStatus.FAILED,
                error=str(e),
            )
            if self.config.fail_fast:
                raise

        self.status.sources[source_name] = result
        return result

    def _fetch_mock_data(
        self,
        offset: int = 0,
        limit: int | None = None,
    ) -> dict[str, list[Observation]]:
        """
        Generate mock observations for dry-run testing.

        Args:
            offset: Number of items to skip in each result list
            limit: Maximum number of items to return in each result list (None = all)
        """
        self._log("Using mock data (dry-run mode)")
        mock = _generate_mock_data()
        now = datetime.now()

        results: dict[str, list[Observation]] = {
            "prices": [],
            "fundamentals": [],
            "macro": [],
            "news": [],
            "social": [],
            "smart_money": [],
        }

        # Mock prices
        for ticker, data in mock["prices"].items():
            results["prices"].append(Observation(
                source="yahoo",
                timestamp=now,
                category=Category.PRICE,
                ticker=ticker,
                data=data,
                reliability=0.9,
            ))
            self.status.sources[f"yahoo_price_{ticker}"] = SourceResult(
                source=f"yahoo_price_{ticker}",
                status=SourceStatus.OK,
                observations=[],
            )

        # Mock fundamentals
        for ticker, data in mock["fundamentals"].items():
            results["fundamentals"].append(Observation(
                source="yahoo",
                timestamp=now,
                category=Category.FUNDAMENTAL,
                ticker=ticker,
                data=data,
                reliability=0.9,
            ))

        # Mock macro
        for data in mock["macro"]:
            results["macro"].append(Observation(
                source="fred",
                timestamp=now,
                category=Category.MACRO,
                ticker=None,
                data=data,
                reliability=0.95,
            ))
        self.status.sources["fred"] = SourceResult(
            source="fred",
            status=SourceStatus.OK,
            observations=results["macro"],
        )

        # Mock news
        for data in mock["news"]:
            results["news"].append(Observation(
                source="rss",
                timestamp=now,
                category=Category.NEWS,
                ticker=None,
                data=data,
                reliability=0.8,
            ))

        # Mock smart money
        for data in mock["smart_money"]:
            source = "congress" if data["signal_type"] == "congress" else "yahoo"
            results["smart_money"].append(Observation(
                source=source,
                timestamp=now,
                category=Category.SENTIMENT,
                ticker=data.get("ticker"),
                data=data,
                reliability=0.85,
            ))
        self.status.sources["congress"] = SourceResult(
            source="congress",
            status=SourceStatus.OK,
            observations=[],
        )

        self.status.completed_at = datetime.now()

        # Apply pagination to all result lists
        paginated_results = {}
        for key, obs_list in results.items():
            end_idx = offset + limit if limit else None
            paginated_results[key] = obs_list[offset:end_idx]

        return paginated_results


# ============================================================================
# Data Transformation Layer
# ============================================================================

class DataTransformer:
    """
    Transforms raw observations into domain objects.

    Handles missing/incomplete data gracefully.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config

    def _log(self, msg: str) -> None:
        if self.config.verbose:
            print(f"  [VERBOSE] {msg}")

    def transform_to_metrics(
        self,
        prices: list[Observation],
        fundamentals: list[Observation],
    ) -> tuple[dict[str, StockMetrics], dict[str, str]]:
        """
        Transform price and fundamental observations to StockMetrics.

        Returns:
            (metrics_by_ticker, sectors_by_ticker)
        """
        metrics: dict[str, StockMetrics] = {}
        sectors: dict[str, str] = {}

        # Group by ticker
        price_by_ticker = {obs.ticker: obs for obs in prices if obs.ticker}
        fund_by_ticker = {obs.ticker: obs for obs in fundamentals if obs.ticker}

        for ticker in set(price_by_ticker.keys()) | set(fund_by_ticker.keys()):
            price_obs = price_by_ticker.get(ticker)
            fund_obs = fund_by_ticker.get(ticker)

            if not price_obs:
                continue

            price_data = price_obs.data
            fund_data = fund_obs.data if fund_obs else {}

            # Extract sector
            sector = fund_data.get("sector", "").lower() if fund_data.get("sector") else "technology"
            sectors[ticker] = sector

            # Calculate price change from moving averages if available
            current_price = fund_data.get("current_price") or price_data.get("price", 0)
            fifty_day_avg = fund_data.get("fifty_day_average")
            two_hundred_day_avg = fund_data.get("two_hundred_day_average")

            # Estimate monthly change from 50-day MA comparison
            price_change_1m = None
            if fifty_day_avg and current_price:
                # Approximate: current vs 50-day avg gives rough monthly momentum
                price_change_1m = (current_price - fifty_day_avg) / fifty_day_avg

            try:
                metrics[ticker] = StockMetrics(
                    ticker=ticker,
                    price=price_data.get("price", 0),
                    market_cap=price_data.get("market_cap") or fund_data.get("market_cap"),
                    pe_trailing=fund_data.get("pe_trailing"),
                    pe_forward=fund_data.get("pe_forward"),
                    peg_ratio=fund_data.get("peg_ratio"),
                    price_to_book=fund_data.get("price_to_book"),
                    price_to_sales=fund_data.get("price_to_sales"),
                    revenue_growth=fund_data.get("revenue_growth"),
                    earnings_growth=fund_data.get("earnings_growth"),
                    profit_margin=fund_data.get("profit_margin"),
                    roe=fund_data.get("roe"),
                    roa=fund_data.get("roa"),
                    price_change_1d=price_data.get("change_percent", 0) / 100 if price_data.get("change_percent") else None,
                    price_change_1m=price_change_1m,
                    volume_current=price_data.get("volume"),
                    volume_avg=fund_data.get("average_volume"),
                    analyst_rating=fund_data.get("analyst_rating"),
                    price_target=fund_data.get("price_target"),
                    dividend_yield=fund_data.get("dividend_yield"),
                )
                self._log(f"  Transformed metrics for {ticker} (sector: {sector})")
            except Exception as e:
                self._log(f"  Failed to transform {ticker}: {e}")

        return metrics, sectors

    def transform_to_macro_context(
        self,
        macro_obs: list[Observation],
    ) -> tuple[MacroContext, list[MacroIndicator]]:
        """Transform macro observations to MacroContext and indicators."""
        indicators = []

        # Extract indicator values
        values: dict[str, float] = {}
        for obs in macro_obs:
            series_id = obs.data.get("series_id", "")
            value = obs.data.get("value", 0)
            values[series_id] = value

            # Create MacroIndicator
            indicators.append(MacroIndicator(
                name=obs.data.get("name", series_id),
                series_id=series_id,
                current_value=value,
                unit=obs.data.get("unit", ""),
                trend=Trend.STABLE,  # Would need history for real trend
                impact_assessment=self._assess_macro_impact(series_id, value),
            ))

        # Build context
        context = MacroContext(
            fed_funds_rate=values.get("FEDFUNDS"),
            treasury_10y=values.get("GS10"),
            treasury_2y=values.get("GS2"),
            unemployment_rate=values.get("UNRATE"),
            inflation_rate=values.get("CPIAUCSL"),
            gdp_growth=values.get("GDP"),
            consumer_sentiment=values.get("UMCSENT"),
        )

        return context, indicators

    def _assess_macro_impact(self, series_id: str, value: float) -> Impact:
        """Assess impact of a macro indicator value."""
        thresholds = {
            "UNRATE": (4.0, 5.5),  # < good, > bad
            "FEDFUNDS": (3.0, 5.0),
            "T10Y2Y": (0.0, 0.0),  # Negative = bad (inverted)
        }

        if series_id not in thresholds:
            return Impact.NEUTRAL

        low, high = thresholds[series_id]
        if value < low:
            return Impact.POSITIVE
        elif value > high:
            return Impact.NEGATIVE
        return Impact.NEUTRAL

    def transform_news(
        self,
        news_obs: list[Observation],
        social_obs: list[Observation],
    ) -> tuple[list[ScoredNewsItem], list[ScoredNewsItem]]:
        """Transform news observations to ScoredNewsItems."""
        raw_items = []

        # Convert news observations
        for obs in news_obs:
            raw_items.append(RawNewsItem(
                title=obs.data.get("title", ""),
                url=obs.data.get("url"),
                source=obs.data.get("source") or obs.data.get("publisher") or obs.source,
                published=obs.timestamp,
                description=obs.data.get("description"),
                source_ticker=obs.ticker,  # Link news to ticker it was fetched for
            ))

        # Convert social observations
        for obs in social_obs:
            raw_items.append(RawNewsItem(
                title=obs.data.get("title", ""),
                url=obs.data.get("url"),
                source=f"r/{obs.data.get('subreddit', 'unknown')}",
                published=obs.timestamp,
                description=obs.data.get("text", "")[:200],
            ))

        # Score and classify
        scored = aggregate_news(raw_items)

        # Split by category
        market_news = [n for n in scored if n.category == NewsCategory.MARKET_WIDE]
        company_news = [n for n in scored if n.category in [NewsCategory.COMPANY, NewsCategory.SECTOR]]

        return market_news, company_news


# ============================================================================
# Analysis Layer
# ============================================================================

class Analyzer:
    """
    Runs analysis pipeline on transformed data.

    Produces stock picks, risk assessments, and signals.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config

    def _log(self, msg: str) -> None:
        if self.config.verbose:
            print(f"  [VERBOSE] {msg}")

    def analyze_stocks(
        self,
        metrics: dict[str, StockMetrics],
        macro_context: MacroContext,
    ) -> tuple[list[StockPick], dict[str, ConvictionScore]]:
        """Analyze stocks and generate picks (legacy v1)."""
        picks = []
        scores: dict[str, ConvictionScore] = {}

        for ticker, m in metrics.items():
            self._log(f"  Analyzing {ticker}...")

            # Score stock
            score = score_stock(m, macro_context, self.config.scoring_config)
            scores[ticker] = score

            # Classify timeframe
            timeframe = classify_timeframe(m, self.config.scoring_config)

            # Identify stock-specific risks
            risks = identify_stock_risks(m, self.config.scoring_config)
            risk_factors = [r.name for r in risks[:3]]

            # Generate thesis
            thesis = generate_thesis(m, score, risks)

            # Calculate stop loss based on conviction (8% default for legacy path)
            stop_loss = m.price * 0.92 if m.price else None

            # Create pick
            pick = StockPick(
                ticker=ticker,
                timeframe=timeframe,
                conviction_score=score.overall,
                thesis=thesis,
                risk_factors=risk_factors,
                entry_price=m.price,
                target_price=m.price * (1 + score.overall * 0.3) if score.overall > 0.5 else None,
                stop_loss=stop_loss,
            )
            picks.append(pick)

        return picks, scores

    def analyze_stocks_v2(
        self,
        metrics: dict[str, StockMetrics],
        sectors: dict[str, str],
        macro_context: MacroContext,
    ) -> tuple[list[StockPick], dict[str, ConvictionScore], list[ScoredPick]]:
        """
        Analyze stocks using the v2 systematic scoring algorithm.

        Returns:
            (picks, scores, scored_picks) - StockPick for report compatibility,
            ConvictionScore for enrichment, ScoredPick for detailed breakdown
        """
        picks: list[StockPick] = []
        scores: dict[str, ConvictionScore] = {}
        scored_picks: list[ScoredPick] = []

        for ticker, m in metrics.items():
            self._log(f"  Scoring {ticker} (v2)...")

            # Get sector and sector average PE
            sector = sectors.get(ticker, "technology")
            sector_avg_pe = self.config.sector_pe_averages.get(
                sector.lower(), 20.0  # Default PE if sector unknown
            )

            # Score using v2 algorithm
            scored = score_stock_v2(
                metrics=m,
                macro=macro_context,
                sector=sector,
                sector_avg_pe=sector_avg_pe,
                thresholds=self.config.scoring_thresholds,
                weights=self.config.scoring_weights,
                sensitivities=self.config.sector_sensitivities,
                timeframe_rules=self.config.timeframe_rules,
            )
            scored_picks.append(scored)

            # Store conviction score for enrichment
            scores[ticker] = scored.score_breakdown

            # Calculate stop loss (wider for lower conviction, tighter for higher)
            # High conviction (8-10): 5% stop, Medium (5-7): 8% stop, Low (1-4): 12% stop
            if scored.conviction >= 8:
                stop_pct = 0.05
            elif scored.conviction >= 5:
                stop_pct = 0.08
            else:
                stop_pct = 0.12
            stop_loss = m.price * (1 - stop_pct) if m.price else None

            # Convert ScoredPick to StockPick for report compatibility
            pick = StockPick(
                ticker=ticker,
                timeframe=scored.timeframe,
                conviction_score=scored.conviction_normalized,  # 0-1 scale
                thesis=scored.thesis,
                risk_factors=scored.risks[:3],
                entry_price=m.price,
                target_price=m.price * (1 + scored.conviction_normalized * 0.3) if scored.conviction > 5 else None,
                stop_loss=stop_loss,
            )
            picks.append(pick)

            self._log(
                f"    {ticker}: conviction={scored.conviction}/10, "
                f"timeframe={scored.timeframe.value}, sector={sector}"
            )

        # Sort by conviction (descending)
        picks.sort(key=lambda p: p.conviction_score, reverse=True)
        scored_picks.sort(key=lambda p: p.conviction, reverse=True)

        return picks, scores, scored_picks

    def analyze_macro(
        self,
        indicators: list[MacroIndicator],
    ) -> list[Risk]:
        """Analyze macro environment for headwinds."""
        self._log("Analyzing macro headwinds...")
        return identify_headwinds(indicators, self.config.scoring_config)


# ============================================================================
# Main Pipeline
# ============================================================================

class Pipeline:
    """
    Main orchestration pipeline.

    Coordinates fetching, transformation, analysis, and report generation.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        self.config = config or PipelineConfig()
        self.config.verbose = verbose or self.config.verbose
        self.dry_run = dry_run

        self.fetcher = DataFetcher(self.config, dry_run=dry_run)
        self.transformer = DataTransformer(self.config)
        self.analyzer = Analyzer(self.config)

    def _log(self, msg: str) -> None:
        if self.config.verbose:
            print(f"[PIPELINE] {msg}")

    def run(
        self,
        offset: int = 0,
        limit: int | None = None,
    ) -> ReportData:
        """
        Execute the full pipeline.

        Args:
            offset: Number of items to skip in result lists (stocks, news, etc.)
            limit: Maximum number of items to return in result lists (None = all)

        Returns ReportData ready for presentation layer.
        """
        self._log("Starting pipeline...")

        # Phase 1: Fetch data
        self._log("Phase 1: Fetching data...")
        raw_data = self.fetcher.fetch_all(offset, limit)

        # Check data health
        status = self.fetcher.status
        if not status.is_healthy and not self.dry_run:
            self._log(f"WARNING: Pipeline unhealthy - only {len([s for s in status.sources.values() if s.status == SourceStatus.OK])} sources OK")

        # Phase 2: Transform data
        self._log("Phase 2: Transforming data...")
        metrics, sectors = self.transformer.transform_to_metrics(
            raw_data.get("prices", []),
            raw_data.get("fundamentals", []),
        )
        macro_context, macro_indicators = self.transformer.transform_to_macro_context(
            raw_data.get("macro", [])
        )
        market_news, company_news = self.transformer.transform_news(
            raw_data.get("news", []),
            raw_data.get("social", []),
        )

        # Phase 3: Analyze
        self._log("Phase 3: Running analysis...")

        if self.config.use_v2_scoring:
            # Use v2 systematic scoring
            self._log("Using v2 systematic scoring algorithm...")
            picks, scores, scored_picks = self.analyzer.analyze_stocks_v2(
                metrics, sectors, macro_context
            )
        else:
            # Use legacy v1 scoring
            picks, scores = self.analyzer.analyze_stocks(metrics, macro_context)

        macro_risks = self.analyzer.analyze_macro(macro_indicators)

        # Phase 4: Organize picks by timeframe
        self._log("Phase 4: Organizing results...")
        short_picks = [p for p in picks if p.timeframe == Timeframe.SHORT]
        medium_picks = [p for p in picks if p.timeframe == Timeframe.MEDIUM]
        long_picks = [p for p in picks if p.timeframe == Timeframe.LONG]

        # V2 scoring already sorts by conviction, v1 needs ranking
        if not self.config.use_v2_scoring:
            short_picks = rank_picks(short_picks, self.config.strategy, scores)
            medium_picks = rank_picks(medium_picks, self.config.strategy, scores)
            long_picks = rank_picks(long_picks, self.config.strategy, scores)

        # Apply limits (now configurable for production scale)
        max_picks = self.config.max_picks_per_timeframe
        max_news = self.config.max_news_items
        max_macro = self.config.max_macro_indicators
        max_risks = self.config.max_risks_displayed

        # Transform smart money observations to signals
        smart_money_signals = []
        for obs in raw_data.get("smart_money", []):
            # Observations already contain structured data from adapters
            signal_data = obs.data
            if isinstance(signal_data, dict) and "signal_type" in signal_data:
                smart_money_signals.append(signal_data)

        # Sort by strength (strongest signals first)
        smart_money_signals.sort(key=lambda s: s.get("strength", 0), reverse=True)

        # Build report data
        report = ReportData(
            generated_at=datetime.now(),
            macro_indicators=macro_indicators[:max_macro],
            macro_risks=macro_risks[:max_risks],
            short_term_picks=short_picks[:max_picks],
            medium_term_picks=medium_picks[:max_picks],
            long_term_picks=long_picks[:max_picks],
            market_news=market_news[:max_news],
            company_news=company_news[:max_news],
            watchlist=self.config.get_tickers(),
            stock_metrics=metrics,
            conviction_scores=scores,
            smart_money_signals=smart_money_signals[:50],  # Limit to top 50 signals
        )

        # Add warnings to report if needed
        if status.warnings:
            self._log(f"Pipeline completed with {len(status.warnings)} warnings")

        self._log(f"Pipeline complete. Duration: {status.duration}")
        return report

    def get_status(self) -> PipelineStatus:
        """Get pipeline execution status."""
        return self.fetcher.status


def run_pipeline(
    watchlist: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    strategy: Strategy | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> ReportData:
    """
    Convenience function to run the full pipeline.

    Args:
        watchlist: Tickers to analyze
        dry_run: Use mock data instead of live
        verbose: Enable debug output
        strategy: Investment strategy
        offset: Number of items to skip in result lists
        limit: Maximum number of items to return in result lists (None = all)

    Returns:
        ReportData ready for presentation
    """
    config = PipelineConfig()
    if watchlist:
        config.watchlist = watchlist
    if strategy:
        config.strategy = strategy

    pipeline = Pipeline(config, dry_run=dry_run, verbose=verbose)
    return pipeline.run(offset, limit)
