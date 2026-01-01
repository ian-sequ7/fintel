"""
Integration tests for fintel pipeline.

Tests the full pipeline with mocked adapters to avoid external API calls.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from domain import Observation, Category
from ports import FetchError, RateLimitError, DataError, ValidationError, ErrorCode
from adapters import YahooAdapter, FredAdapter, RedditAdapter, RssAdapter
from orchestration.pipeline import (
    Pipeline,
    PipelineConfig,
    DataFetcher,
    DataTransformer,
    Analyzer,
    SourceStatus,
    run_pipeline,
)
from presentation.report import ReportData


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_price_observation():
    """Create a mock price observation."""
    return Observation(
        source="yahoo",
        timestamp=datetime.now(),
        category=Category.PRICE,
        ticker="AAPL",
        data={
            "price": 250.00,
            "previous_close": 245.00,
            "change": 5.00,
            "change_percent": 2.04,
            "volume": 50000000,
            "market_cap": 3000000000000,
        },
        reliability=0.9,
    )


@pytest.fixture
def mock_fundamental_observation():
    """Create a mock fundamental observation."""
    return Observation(
        source="yahoo",
        timestamp=datetime.now(),
        category=Category.FUNDAMENTAL,
        ticker="AAPL",
        data={
            "pe_trailing": 28.5,
            "pe_forward": 25.0,
            "peg_ratio": 1.2,
            "price_to_book": 45.0,
            "revenue_growth": 0.08,
            "profit_margin": 0.26,
            "recommendation": "hold",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "roe": 0.45,
            "analyst_rating": 2.0,
            "fifty_day_average": 245.0,
            "average_volume": 50000000,
        },
        reliability=0.9,
    )


@pytest.fixture
def mock_macro_observations():
    """Create mock macro observations."""
    return [
        Observation(
            source="fred",
            timestamp=datetime.now(),
            category=Category.MACRO,
            ticker=None,
            data={
                "series_id": "UNRATE",
                "name": "Unemployment Rate",
                "value": 4.2,
                "unit": "%",
            },
            reliability=0.95,
        ),
        Observation(
            source="fred",
            timestamp=datetime.now(),
            category=Category.MACRO,
            ticker=None,
            data={
                "series_id": "FEDFUNDS",
                "name": "Federal Funds Rate",
                "value": 5.25,
                "unit": "%",
            },
            reliability=0.95,
        ),
    ]


@pytest.fixture
def mock_news_observations():
    """Create mock news observations."""
    return [
        Observation(
            source="rss",
            timestamp=datetime.now(),
            category=Category.NEWS,
            ticker=None,
            data={
                "title": "Fed signals rate cuts ahead",
                "url": "https://example.com/1",
                "source": "Reuters",
                "description": "Federal Reserve hints at policy changes",
            },
            reliability=0.85,
        ),
    ]


@pytest.fixture
def pipeline_config():
    """Create test pipeline config."""
    return PipelineConfig(
        watchlist=["AAPL", "MSFT"],
        max_picks_per_timeframe=3,
        max_news_items=5,
        fail_fast=False,
    )


# ============================================================================
# Adapter Tests
# ============================================================================

class TestYahooAdapter:
    """Tests for Yahoo Finance adapter."""

    def test_validate_ticker_valid(self):
        """Valid tickers should be normalized to uppercase."""
        adapter = YahooAdapter()
        assert adapter._validate_ticker("aapl") == "AAPL"
        assert adapter._validate_ticker("BRK-B") == "BRK-B"
        assert adapter._validate_ticker("BRK.B") == "BRK.B"

    def test_validate_ticker_invalid(self):
        """Invalid tickers should raise ValidationError."""
        adapter = YahooAdapter()

        with pytest.raises(ValidationError) as exc_info:
            adapter._validate_ticker("")
        assert exc_info.value.code == ErrorCode.VALIDATION_TICKER

        with pytest.raises(ValidationError):
            adapter._validate_ticker("TOOLONGTICKERHERE")

    def test_fetch_requires_ticker(self):
        """Fetch without ticker should raise FetchError wrapping ValidationError."""
        adapter = YahooAdapter()

        with pytest.raises(FetchError) as exc_info:
            adapter.fetch(data_type="price")
        # The wrapped error message should mention ticker
        assert "ticker" in str(exc_info.value)

    def test_fetch_invalid_data_type(self):
        """Invalid data_type should raise FetchError wrapping ValidationError."""
        adapter = YahooAdapter()

        with pytest.raises(FetchError) as exc_info:
            adapter.fetch(ticker="AAPL", data_type="invalid")
        # The wrapped error message should mention data_type
        assert "data_type" in str(exc_info.value)


class TestErrorTypes:
    """Tests for error type functionality."""

    def test_fetch_error_from_http_error(self):
        """FetchError should categorize HTTP errors correctly."""
        # 404 error
        error = FetchError.from_http_error("yahoo", 404, "https://api.example.com")
        assert error.code == ErrorCode.HTTP_NOT_FOUND
        assert error.status_code == 404

        # 401 error
        error = FetchError.from_http_error("yahoo", 401)
        assert error.code == ErrorCode.HTTP_UNAUTHORIZED

        # 500 error
        error = FetchError.from_http_error("yahoo", 500)
        assert error.code == ErrorCode.HTTP_SERVER_ERROR

    def test_rate_limit_error(self):
        """RateLimitError should be raised for 429."""
        with pytest.raises(RateLimitError):
            FetchError.from_http_error("yahoo", 429)

    def test_data_error_helpers(self):
        """DataError class methods should create correct errors."""
        # Missing field
        error = DataError.missing("yahoo", "price")
        assert error.code == ErrorCode.DATA_MISSING
        assert "price" in error.message

        # Empty data
        error = DataError.empty("yahoo", "No results")
        assert error.code == ErrorCode.DATA_EMPTY

        # Stale data
        error = DataError.stale(
            "yahoo",
            age=timedelta(hours=5),
            max_age=timedelta(hours=1),
        )
        assert error.code == ErrorCode.DATA_STALE

    def test_error_to_dict(self):
        """Errors should serialize to dict properly."""
        error = FetchError(
            source="yahoo",
            reason="Test error",
            url="https://example.com",
        )
        d = error.to_dict()

        assert "code" in d
        assert "message" in d
        assert "source" in d
        assert "timestamp" in d
        assert d["source"] == "yahoo"


# ============================================================================
# DataFetcher Tests
# ============================================================================

class TestDataFetcher:
    """Tests for DataFetcher with mocked adapters."""

    def test_dry_run_returns_mock_data(self, pipeline_config):
        """Dry run should return mock data without API calls."""
        fetcher = DataFetcher(pipeline_config, dry_run=True)
        result = fetcher.fetch_all()

        assert "prices" in result
        assert "fundamentals" in result
        assert "macro" in result
        assert "news" in result

        # Check mock data was generated
        assert len(result["prices"]) > 0
        assert all(obs.source == "yahoo" for obs in result["prices"])

    def test_fetch_handles_partial_failures(self, pipeline_config):
        """Fetcher should continue when some sources fail."""
        fetcher = DataFetcher(pipeline_config, dry_run=False)

        # Create mock adapters
        mock_yahoo = Mock()
        mock_yahoo.get_price.side_effect = FetchError("yahoo", "API error")
        mock_yahoo.get_fundamentals.side_effect = FetchError("yahoo", "API error")
        mock_yahoo.get_news.side_effect = FetchError("yahoo", "API error")

        mock_fred = Mock()
        mock_fred.get_all_indicators.return_value = []

        mock_rss = Mock()
        mock_rss.get_market_news.return_value = []

        mock_reddit = Mock()
        mock_reddit.get_all.return_value = []

        # Inject mocks using private attributes
        fetcher._yahoo = mock_yahoo
        fetcher._fred = mock_fred
        fetcher._rss = mock_rss
        fetcher._reddit = mock_reddit

        result = fetcher.fetch_all()

        # Should not raise, should have warnings
        assert len(fetcher.status.warnings) > 0

    def test_status_tracking(self, pipeline_config):
        """Fetcher should track source status correctly."""
        fetcher = DataFetcher(pipeline_config, dry_run=True)
        fetcher.fetch_all()

        status = fetcher.status
        assert status.completed_at is not None
        assert len(status.sources) > 0
        assert status.is_healthy


# ============================================================================
# DataTransformer Tests
# ============================================================================

class TestDataTransformer:
    """Tests for DataTransformer."""

    def test_transform_to_metrics(
        self,
        pipeline_config,
        mock_price_observation,
        mock_fundamental_observation,
    ):
        """Transformer should create StockMetrics from observations."""
        transformer = DataTransformer(pipeline_config)
        metrics, sectors = transformer.transform_to_metrics(
            prices=[mock_price_observation],
            fundamentals=[mock_fundamental_observation],
        )

        assert "AAPL" in metrics
        aapl = metrics["AAPL"]
        assert aapl.price == 250.00
        assert aapl.pe_trailing == 28.5
        assert "AAPL" in sectors
        assert sectors["AAPL"] == "technology"

    def test_transform_to_macro_context(
        self,
        pipeline_config,
        mock_macro_observations,
    ):
        """Transformer should create MacroContext from observations."""
        transformer = DataTransformer(pipeline_config)
        context, indicators = transformer.transform_to_macro_context(
            mock_macro_observations
        )

        assert len(indicators) == 2
        assert context.unemployment_rate == 4.2


# ============================================================================
# Analyzer Tests
# ============================================================================

class TestAnalyzer:
    """Tests for Analyzer."""

    def test_analyze_stocks_generates_picks(
        self,
        pipeline_config,
        mock_price_observation,
        mock_fundamental_observation,
    ):
        """Analyzer should generate stock picks."""
        transformer = DataTransformer(pipeline_config)
        metrics, sectors = transformer.transform_to_metrics(
            prices=[mock_price_observation],
            fundamentals=[mock_fundamental_observation],
        )
        context, _ = transformer.transform_to_macro_context([])

        analyzer = Analyzer(pipeline_config)
        picks, scores = analyzer.analyze_stocks(metrics, context)

        assert len(picks) == 1
        assert picks[0].ticker == "AAPL"
        assert 0 <= picks[0].conviction_score <= 1
        assert "AAPL" in scores


# ============================================================================
# Full Pipeline Tests
# ============================================================================

class TestPipeline:
    """Integration tests for full pipeline."""

    def test_pipeline_dry_run(self, pipeline_config):
        """Pipeline dry run should produce valid report."""
        pipeline = Pipeline(pipeline_config, dry_run=True)
        report = pipeline.run()

        assert isinstance(report, ReportData)
        assert report.generated_at is not None
        assert len(report.watchlist) > 0

    def test_pipeline_returns_report_data(self, pipeline_config):
        """Pipeline should return complete ReportData."""
        pipeline = Pipeline(pipeline_config, dry_run=True)
        report = pipeline.run()

        # Check all required fields
        assert hasattr(report, "generated_at")
        assert hasattr(report, "macro_indicators")
        assert hasattr(report, "macro_risks")
        assert hasattr(report, "short_term_picks")
        assert hasattr(report, "medium_term_picks")
        assert hasattr(report, "long_term_picks")
        assert hasattr(report, "market_news")
        assert hasattr(report, "company_news")

    def test_run_pipeline_convenience_function(self):
        """run_pipeline convenience function should work."""
        report = run_pipeline(
            watchlist=["AAPL"],
            dry_run=True,
        )

        assert isinstance(report, ReportData)
        assert "AAPL" in report.watchlist

    def test_pipeline_status_accessible(self, pipeline_config):
        """Pipeline status should be accessible after run."""
        pipeline = Pipeline(pipeline_config, dry_run=True)
        pipeline.run()

        status = pipeline.get_status()
        assert status.completed_at is not None
        assert status.duration is not None


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfiguration:
    """Tests for configuration system."""

    def test_config_loads_defaults(self):
        """Config should load with sensible defaults."""
        from config import get_config

        config = get_config()
        assert len(config.watchlist) > 0
        assert config.http.timeout_seconds > 0
        assert config.thresholds.valuation.pe_low < config.thresholds.valuation.pe_high

    def test_config_validation(self):
        """Invalid config should raise validation error."""
        from config.schema import ValuationThresholdsConfig
        from pydantic import ValidationError as PydanticValidationError

        # pe_high must be > pe_low
        with pytest.raises(PydanticValidationError):
            ValuationThresholdsConfig(pe_low=30.0, pe_high=15.0)

    def test_settings_backward_compat(self):
        """Settings should maintain backward compatibility."""
        from config import get_settings

        settings = get_settings()
        assert hasattr(settings, "watchlist")
        assert hasattr(settings, "cache_ttl")
        assert hasattr(settings, "rate_limits")
        assert hasattr(settings, "request_timeout")


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling throughout the system."""

    def test_adapter_error_has_context(self):
        """Adapter errors should include context for debugging."""
        error = FetchError(
            source="yahoo",
            reason="API timeout",
            url="https://api.yahoo.com/v1/quote",
        )

        assert error.source == "yahoo"
        assert "url" in error.context
        assert error.code is not None

    def test_pipeline_continues_on_adapter_failure(self, pipeline_config):
        """Pipeline should continue when individual adapters fail."""
        pipeline = Pipeline(pipeline_config, dry_run=False)

        # Create mock adapters
        mock_yahoo = Mock()
        mock_yahoo.get_price.side_effect = FetchError("yahoo", "Timeout")
        mock_yahoo.get_fundamentals.side_effect = FetchError("yahoo", "Timeout")
        mock_yahoo.get_news.side_effect = FetchError("yahoo", "Timeout")

        mock_fred = Mock()
        mock_fred.get_all_indicators.return_value = []

        mock_rss = Mock()
        mock_rss.get_market_news.return_value = []

        mock_reddit = Mock()
        mock_reddit.get_all.return_value = []

        # Inject mocks using private attributes
        pipeline.fetcher._yahoo = mock_yahoo
        pipeline.fetcher._fred = mock_fred
        pipeline.fetcher._rss = mock_rss
        pipeline.fetcher._reddit = mock_reddit

        # Should not raise
        report = pipeline.run()

        assert isinstance(report, ReportData)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
