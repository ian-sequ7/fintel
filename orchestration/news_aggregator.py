"""
News aggregator service.

Combines news from multiple adapters, scores, classifies, and deduplicates.
This is the orchestration layer that coordinates adapters with domain logic.

Note: X/Twitter API requires $100/mo - not viable for free tier.
Reddit serves as the social sentiment source instead.
"""

from datetime import datetime
from dataclasses import dataclass, field
import logging

from domain.news import (
    RawNewsItem,
    ScoredNewsItem,
    NewsCategory,
    NewsPriority,
    NewsAggregatorConfig,
    aggregate_news,
    filter_by_category,
    filter_by_ticker,
    filter_by_priority,
)
from domain import Observation, Category
from adapters import YahooAdapter, RssAdapter, RedditAdapter
from ports import FetchError

logger = logging.getLogger(__name__)


@dataclass
class NewsAggregator:
    """
    Aggregates news from multiple sources.

    Coordinates:
    - YahooAdapter: Company-specific news
    - RssAdapter: Market/general news
    - RedditAdapter: Social sentiment (replaces Twitter)
    """

    config: NewsAggregatorConfig = field(default_factory=NewsAggregatorConfig)
    known_tickers: set[str] = field(default_factory=lambda: {
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
        "BRK.A", "BRK.B", "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "MA",
        "PG", "HD", "CVX", "MRK", "ABBV", "KO", "PEP", "COST", "AVGO",
        "LLY", "MCD", "CSCO", "TMO", "ACN", "ABT", "DHR", "NKE", "TXN",
        "AMD", "INTC", "QCOM", "CRM", "NFLX", "ADBE", "PYPL", "UBER",
        "DIS", "VZ", "T", "BA", "GE", "CAT", "IBM", "GS", "MS", "C",
        "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI",
    })

    # Lazy-initialized adapters
    _yahoo: YahooAdapter | None = field(default=None, repr=False)
    _rss: RssAdapter | None = field(default=None, repr=False)
    _reddit: RedditAdapter | None = field(default=None, repr=False)

    @property
    def yahoo(self) -> YahooAdapter:
        if self._yahoo is None:
            self._yahoo = YahooAdapter()
        return self._yahoo

    @property
    def rss(self) -> RssAdapter:
        if self._rss is None:
            self._rss = RssAdapter()
        return self._rss

    @property
    def reddit(self) -> RedditAdapter:
        if self._reddit is None:
            self._reddit = RedditAdapter()
        return self._reddit

    def _observation_to_raw(self, obs: Observation) -> RawNewsItem:
        """Convert adapter Observation to RawNewsItem."""
        data = obs.data

        # Handle different adapter formats
        title = data.get("title") or data.get("headline", "")
        url = data.get("url") or data.get("link")
        source = data.get("source") or data.get("publisher") or obs.source
        description = data.get("description") or data.get("text", "")[:200]

        return RawNewsItem(
            title=title,
            url=url,
            source=source,
            published=obs.timestamp,
            description=description,
            category_hint=data.get("subreddit"),  # For Reddit
        )

    def fetch_company_news(self, tickers: list[str]) -> list[RawNewsItem]:
        """Fetch company-specific news from Yahoo."""
        raw_items = []

        for ticker in tickers:
            try:
                observations = self.yahoo.get_news(ticker)
                for obs in observations:
                    raw_items.append(self._observation_to_raw(obs))
            except FetchError as e:
                logger.warning(f"Failed to fetch news for {ticker}: {e}")

        return raw_items

    def fetch_market_news(self, limit: int = 50) -> list[RawNewsItem]:
        """Fetch market-wide news from RSS feeds."""
        try:
            observations = self.rss.get_market_news(limit=limit)
            return [self._observation_to_raw(obs) for obs in observations]
        except FetchError as e:
            logger.warning(f"Failed to fetch market news: {e}")
            return []

    def fetch_social_sentiment(self, limit: int = 25) -> list[RawNewsItem]:
        """Fetch social sentiment from Reddit."""
        raw_items = []

        try:
            observations = self.reddit.get_all(limit=limit)
            for obs in observations:
                raw = self._observation_to_raw(obs)
                raw_items.append(raw)
        except FetchError as e:
            logger.warning(f"Failed to fetch Reddit sentiment: {e}")

        return raw_items

    def aggregate(
        self,
        tickers: list[str] | None = None,
        include_market: bool = True,
        include_social: bool = True,
        market_limit: int = 50,
        social_limit: int = 25,
        now: datetime | None = None,
    ) -> list[ScoredNewsItem]:
        """
        Aggregate news from all sources.

        Args:
            tickers: Specific tickers to fetch company news for
            include_market: Include market-wide news
            include_social: Include Reddit sentiment
            market_limit: Max market news items
            social_limit: Max social items per subreddit
            now: Current time for scoring

        Returns:
            Scored, classified, deduplicated news sorted by relevance
        """
        all_raw: list[RawNewsItem] = []

        # Fetch company news
        if tickers:
            all_raw.extend(self.fetch_company_news(tickers))

        # Fetch market news
        if include_market:
            all_raw.extend(self.fetch_market_news(limit=market_limit))

        # Fetch social sentiment
        if include_social:
            all_raw.extend(self.fetch_social_sentiment(limit=social_limit))

        logger.info(f"Fetched {len(all_raw)} raw news items")

        # Score, classify, deduplicate using pure domain functions
        scored = aggregate_news(
            items=all_raw,
            config=self.config,
            known_tickers=self.known_tickers,
            now=now,
        )

        logger.info(f"After processing: {len(scored)} items")

        return scored

    def get_market_news(self, limit: int = 20) -> list[ScoredNewsItem]:
        """Get market-wide news only."""
        all_news = self.aggregate(include_market=True, include_social=False)
        market_news = filter_by_category(all_news, NewsCategory.MARKET_WIDE)
        return market_news[:limit]

    def get_company_news(self, ticker: str, limit: int = 10) -> list[ScoredNewsItem]:
        """Get news for a specific company."""
        all_news = self.aggregate(tickers=[ticker], include_market=False, include_social=False)
        company_news = filter_by_ticker(all_news, ticker)
        return company_news[:limit]

    def get_sector_news(self, sector: str | None = None, limit: int = 20) -> list[ScoredNewsItem]:
        """Get sector-specific news."""
        all_news = self.aggregate(include_market=True, include_social=False)
        sector_news = filter_by_category(all_news, NewsCategory.SECTOR)

        if sector:
            sector_news = [n for n in sector_news if n.sector == sector]

        return sector_news[:limit]

    def get_high_priority(self, limit: int = 10) -> list[ScoredNewsItem]:
        """Get high priority news across all categories."""
        all_news = self.aggregate()
        high_priority = filter_by_priority(all_news, NewsPriority.HIGH)
        return high_priority[:limit]

    def get_social_sentiment(self, limit: int = 20) -> list[ScoredNewsItem]:
        """Get social media sentiment."""
        all_news = self.aggregate(include_market=False, include_social=True)
        social_news = filter_by_category(all_news, NewsCategory.SOCIAL)
        return social_news[:limit]


# Singleton for convenience
_aggregator: NewsAggregator | None = None


def get_news_aggregator() -> NewsAggregator:
    """Get singleton news aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = NewsAggregator()
    return _aggregator
