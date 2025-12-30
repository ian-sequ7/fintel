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
)
from domain.models import Timeframe
from domain.analysis_types import RiskCategory
from adapters import YahooAdapter, FredAdapter, RedditAdapter, RssAdapter
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

    # Tickers to analyze
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

    # Limits
    max_picks_per_timeframe: int = 5
    max_news_items: int = 20

    # Behavior
    fail_fast: bool = False  # If True, stop on first error
    include_social: bool = True
    verbose: bool = False


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
            "AAPL": {"pe_trailing": 32.5, "revenue_growth": 0.08, "profit_margin": 0.26},
            "MSFT": {"pe_trailing": 38.0, "revenue_growth": 0.15, "profit_margin": 0.35},
            "GOOGL": {"pe_trailing": 25.0, "revenue_growth": 0.12, "profit_margin": 0.22},
            "NVDA": {"pe_trailing": 65.0, "revenue_growth": 0.85, "profit_margin": 0.55},
            "AMZN": {"pe_trailing": 45.0, "revenue_growth": 0.10, "profit_margin": 0.08},
        },
        "macro": [
            {"series_id": "UNRATE", "name": "Unemployment Rate", "value": 4.2, "unit": "%"},
            {"series_id": "FEDFUNDS", "name": "Federal Funds Rate", "value": 5.25, "unit": "%"},
            {"series_id": "T10Y2Y", "name": "10Y-2Y Treasury Spread", "value": -0.25, "unit": "%"},
            {"series_id": "CPIAUCSL", "name": "CPI (Inflation)", "value": 3.5, "unit": "%"},
        ],
        "news": [
            {"title": "Fed signals rate cuts ahead", "source": "Reuters", "category": "market_wide"},
            {"title": "NVDA announces next-gen GPUs", "source": "CNBC", "category": "company"},
            {"title": "Tech sector leads market rally", "source": "MarketWatch", "category": "sector"},
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

    def _log(self, msg: str) -> None:
        """Log if verbose mode enabled."""
        if self.config.verbose:
            logger.info(msg)
            print(f"  [VERBOSE] {msg}")

    def fetch_all(self) -> dict[str, list[Observation]]:
        """
        Fetch data from all sources.

        Returns dict of source_name -> observations.
        Handles errors gracefully, continues on partial failures.
        """
        if self.dry_run:
            return self._fetch_mock_data()

        results: dict[str, list[Observation]] = {
            "prices": [],
            "fundamentals": [],
            "macro": [],
            "news": [],
            "social": [],
        }

        # Fetch prices
        self._log("Fetching price data...")
        for ticker in self.config.watchlist:
            result = self._fetch_source(
                f"yahoo_price_{ticker}",
                lambda t=ticker: self.yahoo.get_price(t),
            )
            if result.status == SourceStatus.OK:
                results["prices"].extend(result.observations)

        # Fetch fundamentals
        self._log("Fetching fundamental data...")
        for ticker in self.config.watchlist:
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

        # Fetch company news
        for ticker in self.config.watchlist[:5]:  # Limit API calls
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

        self.status.completed_at = datetime.now()
        return results

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

    def _fetch_mock_data(self) -> dict[str, list[Observation]]:
        """Generate mock observations for dry-run testing."""
        self._log("Using mock data (dry-run mode)")
        mock = _generate_mock_data()
        now = datetime.now()

        results: dict[str, list[Observation]] = {
            "prices": [],
            "fundamentals": [],
            "macro": [],
            "news": [],
            "social": [],
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

        self.status.completed_at = datetime.now()
        return results


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
    ) -> dict[str, StockMetrics]:
        """Transform price and fundamental observations to StockMetrics."""
        metrics: dict[str, StockMetrics] = {}

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

            try:
                metrics[ticker] = StockMetrics(
                    ticker=ticker,
                    price=price_data.get("price", 0),
                    market_cap=price_data.get("market_cap"),
                    pe_trailing=fund_data.get("pe_trailing"),
                    pe_forward=fund_data.get("pe_forward"),
                    peg_ratio=fund_data.get("peg_ratio"),
                    price_to_book=fund_data.get("price_to_book"),
                    revenue_growth=fund_data.get("revenue_growth"),
                    earnings_growth=fund_data.get("earnings_growth"),
                    profit_margin=fund_data.get("profit_margin"),
                    roe=fund_data.get("roe"),
                    price_change_1d=price_data.get("change_percent", 0) / 100 if price_data.get("change_percent") else None,
                    volume_current=price_data.get("volume"),
                    analyst_rating=fund_data.get("analyst_rating"),
                    price_target=fund_data.get("price_target"),
                    dividend_yield=fund_data.get("dividend_yield"),
                )
                self._log(f"  Transformed metrics for {ticker}")
            except Exception as e:
                self._log(f"  Failed to transform {ticker}: {e}")

        return metrics

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
        """Analyze stocks and generate picks."""
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

            # Create pick
            pick = StockPick(
                ticker=ticker,
                timeframe=timeframe,
                conviction_score=score.overall,
                thesis=thesis,
                risk_factors=risk_factors,
                entry_price=m.price,
                target_price=m.price * (1 + score.overall * 0.3) if score.overall > 0.5 else None,
            )
            picks.append(pick)

        return picks, scores

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

    def run(self) -> ReportData:
        """
        Execute the full pipeline.

        Returns ReportData ready for presentation layer.
        """
        self._log("Starting pipeline...")

        # Phase 1: Fetch data
        self._log("Phase 1: Fetching data...")
        raw_data = self.fetcher.fetch_all()

        # Check data health
        status = self.fetcher.status
        if not status.is_healthy and not self.dry_run:
            self._log(f"WARNING: Pipeline unhealthy - only {len([s for s in status.sources.values() if s.status == SourceStatus.OK])} sources OK")

        # Phase 2: Transform data
        self._log("Phase 2: Transforming data...")
        metrics = self.transformer.transform_to_metrics(
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
        picks, scores = self.analyzer.analyze_stocks(metrics, macro_context)
        macro_risks = self.analyzer.analyze_macro(macro_indicators)

        # Phase 4: Organize picks by timeframe
        self._log("Phase 4: Organizing results...")
        short_picks = [p for p in picks if p.timeframe == Timeframe.SHORT]
        medium_picks = [p for p in picks if p.timeframe == Timeframe.MEDIUM]
        long_picks = [p for p in picks if p.timeframe == Timeframe.LONG]

        # Rank by conviction
        short_picks = rank_picks(short_picks, self.config.strategy, scores)
        medium_picks = rank_picks(medium_picks, self.config.strategy, scores)
        long_picks = rank_picks(long_picks, self.config.strategy, scores)

        # Apply limits
        max_picks = self.config.max_picks_per_timeframe
        max_news = self.config.max_news_items

        # Build report data
        report = ReportData(
            generated_at=datetime.now(),
            macro_indicators=macro_indicators[:8],
            macro_risks=macro_risks[:5],
            short_term_picks=short_picks[:max_picks],
            medium_term_picks=medium_picks[:max_picks],
            long_term_picks=long_picks[:max_picks],
            market_news=market_news[:max_news],
            company_news=company_news[:max_news],
            watchlist=self.config.watchlist,
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
) -> ReportData:
    """
    Convenience function to run the full pipeline.

    Args:
        watchlist: Tickers to analyze
        dry_run: Use mock data instead of live
        verbose: Enable debug output
        strategy: Investment strategy

    Returns:
        ReportData ready for presentation
    """
    config = PipelineConfig()
    if watchlist:
        config.watchlist = watchlist
    if strategy:
        config.strategy = strategy

    pipeline = Pipeline(config, dry_run=dry_run, verbose=verbose)
    return pipeline.run()
