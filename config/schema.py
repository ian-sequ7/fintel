"""
Configuration schema with validation.

All configuration is validated at load time using Pydantic.
"""

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ApiKeysConfig(BaseModel):
    """API key configuration (loaded from environment)."""

    # Optional keys - system works without them
    alpha_vantage: str | None = Field(default=None, description="Alpha Vantage API key")
    finnhub: str | None = Field(default=None, description="Finnhub API key")

    # Future expansion
    polygon: str | None = None
    quandl: str | None = None


class CacheTtlConfig(BaseModel):
    """Cache TTL configuration by data category."""

    price_minutes: int = Field(default=1, ge=1, le=60)
    fundamental_hours: int = Field(default=24, ge=1, le=168)  # Up to 1 week
    macro_hours: int = Field(default=168, ge=24, le=720)  # 1-30 days
    news_minutes: int = Field(default=60, ge=5, le=240)
    sentiment_hours: int = Field(default=4, ge=1, le=24)

    def get_timedelta(self, category: str) -> timedelta:
        """Get timedelta for a category."""
        mapping = {
            "price": timedelta(minutes=self.price_minutes),
            "fundamental": timedelta(hours=self.fundamental_hours),
            "macro": timedelta(hours=self.macro_hours),
            "news": timedelta(minutes=self.news_minutes),
            "sentiment": timedelta(hours=self.sentiment_hours),
        }
        return mapping.get(category, timedelta(hours=1))


class RateLimitsConfig(BaseModel):
    """Rate limits per source (requests per minute)."""

    yahoo: int = Field(default=60, ge=1, le=200)
    fred: int = Field(default=30, ge=1, le=120)
    reddit: int = Field(default=30, ge=1, le=60)
    rss: int = Field(default=60, ge=1, le=120)


class HttpConfig(BaseModel):
    """HTTP client configuration."""

    timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    user_agent: str = Field(default="FintelBot/1.0", min_length=1)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.5, le=10.0)


class ValuationThresholdsConfig(BaseModel):
    """Valuation analysis thresholds."""

    pe_low: float = Field(default=15.0, ge=1.0, le=50.0, description="PE below = cheap")
    pe_high: float = Field(default=30.0, ge=10.0, le=100.0, description="PE above = expensive")
    peg_fair: float = Field(default=1.0, ge=0.5, le=3.0, description="PEG below = undervalued")
    pb_low: float = Field(default=1.0, ge=0.1, le=5.0)
    pb_high: float = Field(default=5.0, ge=1.0, le=20.0)

    @field_validator("pe_high")
    @classmethod
    def pe_high_gt_low(cls, v: float, info) -> float:
        pe_low = info.data.get("pe_low", 15.0)
        if v <= pe_low:
            raise ValueError("pe_high must be greater than pe_low")
        return v


class GrowthThresholdsConfig(BaseModel):
    """Growth analysis thresholds."""

    revenue_high: float = Field(default=0.20, ge=0.05, le=1.0, description="Revenue growth % for high growth")
    revenue_low: float = Field(default=0.05, ge=0.0, le=0.20)
    earnings_high: float = Field(default=0.25, ge=0.05, le=1.0)


class QualityThresholdsConfig(BaseModel):
    """Quality analysis thresholds."""

    profit_margin_good: float = Field(default=0.15, ge=0.05, le=0.50)
    roe_good: float = Field(default=0.15, ge=0.05, le=0.50)


class MacroThresholdsConfig(BaseModel):
    """Macro environment thresholds."""

    unemployment_high: float = Field(default=5.0, ge=3.0, le=10.0)
    inflation_high: float = Field(default=4.0, ge=2.0, le=10.0)
    vix_high: float = Field(default=25.0, ge=15.0, le=50.0)
    consumer_sentiment_low: float = Field(default=60.0, ge=40.0, le=80.0)


class ScoringWeightsConfig(BaseModel):
    """Weights for overall conviction score."""

    valuation: float = Field(default=0.25, ge=0.0, le=1.0)
    growth: float = Field(default=0.25, ge=0.0, le=1.0)
    quality: float = Field(default=0.20, ge=0.0, le=1.0)
    momentum: float = Field(default=0.15, ge=0.0, le=1.0)
    analyst: float = Field(default=0.15, ge=0.0, le=1.0)

    @field_validator("analyst")
    @classmethod
    def weights_sum_to_one(cls, v: float, info) -> float:
        total = sum([
            info.data.get("valuation", 0.25),
            info.data.get("growth", 0.25),
            info.data.get("quality", 0.20),
            info.data.get("momentum", 0.15),
            v,
        ])
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        return v


class AnalysisThresholdsConfig(BaseModel):
    """Combined analysis thresholds configuration."""

    valuation: ValuationThresholdsConfig = Field(default_factory=ValuationThresholdsConfig)
    growth: GrowthThresholdsConfig = Field(default_factory=GrowthThresholdsConfig)
    quality: QualityThresholdsConfig = Field(default_factory=QualityThresholdsConfig)
    macro: MacroThresholdsConfig = Field(default_factory=MacroThresholdsConfig)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)


class DataSourcesConfig(BaseModel):
    """Data sources configuration."""

    # FRED series to fetch
    macro_series: list[str] = Field(default_factory=lambda: [
        "UNRATE", "CPIAUCSL", "GDP", "FEDFUNDS",
        "T10Y2Y", "UMCSENT", "INDPRO", "HOUST",
    ])

    # Reddit subreddits for sentiment
    reddit_subreddits: list[str] = Field(default_factory=lambda: [
        "stocks", "wallstreetbets", "investing",
    ])

    # RSS feeds
    rss_feeds: dict[str, str] = Field(default_factory=lambda: {
        "google_market": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
        "google_economy": "https://news.google.com/rss/search?q=economy+finance&hl=en-US&gl=US&ceid=US:en",
        "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    })

    # Yahoo news count per ticker
    yahoo_news_count: int = Field(default=10, ge=1, le=50)


class OutputConfig(BaseModel):
    """Output preferences."""

    max_picks_per_timeframe: int = Field(default=5, ge=1, le=20)
    max_news_items: int = Field(default=20, ge=5, le=100)
    date_format: str = Field(default="%Y-%m-%d %H:%M")
    include_social_news: bool = Field(default=True)


class PipelineConfig(BaseModel):
    """Pipeline execution configuration."""

    # Staleness thresholds
    price_stale_minutes: int = Field(default=30, ge=5, le=120)
    macro_stale_days: int = Field(default=7, ge=1, le=30)
    news_stale_hours: int = Field(default=24, ge=1, le=72)

    # Behavior
    fail_fast: bool = Field(default=False, description="Stop on first error")
    min_healthy_sources: int = Field(default=2, ge=1, le=5)


class FintelConfig(BaseModel):
    """
    Root configuration model.

    All settings are validated on load.
    """

    # Default tickers to track
    watchlist: list[str] = Field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "JPM", "V",
    ])

    # Subsections
    api_keys: ApiKeysConfig = Field(default_factory=ApiKeysConfig)
    cache_ttl: CacheTtlConfig = Field(default_factory=CacheTtlConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    thresholds: AnalysisThresholdsConfig = Field(default_factory=AnalysisThresholdsConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @field_validator("watchlist")
    @classmethod
    def validate_tickers(cls, v: list[str]) -> list[str]:
        """Validate ticker format."""
        validated = []
        for ticker in v:
            # Normalize to uppercase
            ticker = ticker.upper().strip()
            # Basic validation: 1-5 uppercase letters, optionally with dash/dot
            if not ticker or len(ticker) > 10:
                raise ValueError(f"Invalid ticker format: {ticker}")
            validated.append(ticker)
        return validated
