"""
News aggregation and relevance scoring - pure domain logic.

Components:
1. News classification (market-wide, sector, company-specific)
2. Relevance scoring (source, recency, keywords, tickers)
3. Deduplication across sources
4. Ticker extraction from headlines

All functions are pure - no I/O, fully testable.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable
from collections import defaultdict

from pydantic import BaseModel, Field


# ============================================================================
# Enums and Constants
# ============================================================================

class NewsCategory(str, Enum):
    """News category for routing to analysis components."""
    MARKET_WIDE = "market_wide"    # Macro, fed, economic data
    SECTOR = "sector"              # Industry-specific
    COMPANY = "company"            # Earnings, management, products
    SOCIAL = "social"              # Reddit, social sentiment
    UNKNOWN = "unknown"


class NewsPriority(str, Enum):
    """Priority level for news items."""
    CRITICAL = "critical"  # Breaking, market-moving
    HIGH = "high"          # Important, actionable
    MEDIUM = "medium"      # Relevant, informational
    LOW = "low"            # Background, noise


# Source credibility scores (0-1)
SOURCE_CREDIBILITY = {
    # Tier 1: Major financial news
    "reuters": 0.95,
    "bloomberg": 0.95,
    "wsj": 0.92,
    "wall street journal": 0.92,
    "financial times": 0.92,
    "ft": 0.92,
    "cnbc": 0.88,
    "marketwatch": 0.85,
    "yahoo finance": 0.82,
    "yahoo": 0.82,

    # Tier 2: Business news
    "barron's": 0.85,
    "investor's business daily": 0.82,
    "seeking alpha": 0.70,
    "motley fool": 0.65,
    "benzinga": 0.65,

    # Tier 3: General news with finance coverage
    "ap": 0.88,
    "associated press": 0.88,
    "nyt": 0.85,
    "new york times": 0.85,
    "washington post": 0.82,

    # Tier 4: Aggregators and misc
    "google news": 0.70,
    "finviz": 0.70,  # Aggregator with varied sources
    "rss": 0.60,

    # Social/user-generated
    "reddit": 0.45,
    "r/stocks": 0.50,
    "r/wallstreetbets": 0.35,
    "r/investing": 0.50,
}

# Market-moving keywords with impact scores
MARKET_KEYWORDS = {
    # Fed/monetary policy (high impact)
    "federal reserve": 0.9,
    "fed": 0.85,
    "interest rate": 0.85,
    "rate hike": 0.9,
    "rate cut": 0.9,
    "powell": 0.8,
    "fomc": 0.85,
    "quantitative": 0.75,
    "inflation": 0.8,
    "cpi": 0.8,

    # Economic data
    "gdp": 0.75,
    "jobs report": 0.8,
    "unemployment": 0.75,
    "nonfarm payroll": 0.8,
    "retail sales": 0.7,
    "housing": 0.65,

    # Market events
    "crash": 0.95,
    "correction": 0.8,
    "bear market": 0.85,
    "bull market": 0.7,
    "recession": 0.9,
    "rally": 0.7,
    "selloff": 0.8,
    "sell-off": 0.8,
    "all-time high": 0.7,
    "record high": 0.7,

    # Corporate events
    "earnings": 0.75,
    "quarterly results": 0.75,
    "guidance": 0.7,
    "merger": 0.8,
    "acquisition": 0.8,
    "ipo": 0.75,
    "bankruptcy": 0.9,
    "layoffs": 0.7,
    "ceo": 0.65,
    "dividend": 0.6,
    "stock split": 0.7,
    "buyback": 0.65,

    # Geopolitical
    "trade war": 0.85,
    "tariff": 0.8,
    "sanction": 0.75,
    "china": 0.7,
    "ukraine": 0.7,
    "opec": 0.75,
    "oil": 0.7,
}

# Sector keywords for classification
SECTOR_KEYWORDS = {
    "technology": ["tech", "software", "ai", "artificial intelligence", "semiconductor", "chip", "cloud", "saas"],
    "healthcare": ["pharma", "drug", "fda", "biotech", "hospital", "healthcare", "medical"],
    "financial": ["bank", "banking", "insurance", "fintech", "credit", "loan", "mortgage"],
    "energy": ["oil", "gas", "renewable", "solar", "wind", "energy", "petroleum", "opec"],
    "consumer": ["retail", "consumer", "shopping", "e-commerce", "amazon", "walmart"],
    "industrial": ["manufacturing", "industrial", "factory", "supply chain", "logistics"],
    "real_estate": ["real estate", "reit", "housing", "property", "mortgage"],
    "utilities": ["utility", "utilities", "electric", "power", "water"],
    "materials": ["mining", "steel", "aluminum", "copper", "gold", "commodity"],
    "telecom": ["telecom", "5g", "wireless", "carrier", "broadband"],
}

# Common stock tickers to avoid false positives
COMMON_WORDS = {
    "A", "I", "IT", "AT", "ON", "AN", "AS", "IS", "OR", "BY", "TO", "IN",
    "FOR", "THE", "AND", "ARE", "CEO", "CFO", "USA", "GDP", "CPI", "IPO",
    "ETF", "SEC", "FDA", "FED", "NYSE", "CEO", "ALL", "NEW", "NOW", "OUT",
    "HAS", "BIG", "TOP", "LOW", "KEY", "MAY", "CAN", "OUR", "ANY",
}

# Keywords indicating non-financial/lifestyle content to filter out
IRRELEVANT_KEYWORDS = {
    # Personal finance advice (not market-relevant)
    "gift my", "gift your", "grandchildren", "fixed budget",
    "steal my money", "cautionary tales", "financial adviser",
    # Lifestyle/entertainment
    "movie", "film", "actor", "actress", "celebrity", "hollywood",
    "restaurant", "recipe", "cooking", "travel", "vacation",
    "wedding", "dating", "relationship",
    # Sports (unless betting-related)
    "nfl", "nba", "mlb", "nhl", "football", "basketball", "soccer",
    # Health/wellness (non-pharma)
    "diet", "weight loss", "exercise", "workout", "yoga",
    # General lifestyle
    "horoscope", "zodiac", "astrology",
}


# ============================================================================
# Data Types
# ============================================================================

class RawNewsItem(BaseModel):
    """Raw news item from adapters before processing."""
    model_config = {"frozen": True}

    title: str
    url: str | None = None
    source: str
    published: datetime
    description: str | None = None
    category_hint: str | None = None  # From adapter if available
    source_ticker: str | None = None  # Ticker this news was fetched for


class ScoredNewsItem(BaseModel):
    """News item with relevance scoring and classification."""
    model_config = {"frozen": True}

    # Original data
    title: str
    url: str | None = None
    source: str
    published: datetime
    description: str | None = None

    # Scoring
    relevance_score: float = Field(ge=0, le=1)
    source_credibility: float = Field(ge=0, le=1)
    recency_score: float = Field(ge=0, le=1)
    keyword_score: float = Field(ge=0, le=1)

    # Classification
    category: NewsCategory
    priority: NewsPriority
    sector: str | None = None

    # Extracted data
    tickers_mentioned: list[str] = Field(default_factory=list)
    keywords_found: list[str] = Field(default_factory=list)

    # Deduplication
    content_hash: str = ""  # For deduplication


@dataclass(frozen=True)
class NewsAggregatorConfig:
    """Configuration for news aggregation."""

    # Recency scoring
    max_age_hours: float = 24.0  # News older than this gets 0 recency score
    critical_age_hours: float = 1.0  # News within this is highest priority

    # Score weights
    weight_source: float = 0.25
    weight_recency: float = 0.30
    weight_keywords: float = 0.25
    weight_tickers: float = 0.20

    # Thresholds
    min_relevance_score: float = 0.3  # Below this, filter out
    high_priority_threshold: float = 0.7
    critical_priority_threshold: float = 0.85

    # Ticker extraction
    min_ticker_length: int = 1
    max_ticker_length: int = 5

    # Deduplication
    similarity_threshold: float = 0.8  # Title similarity for dedup


# ============================================================================
# Ticker Extraction
# ============================================================================

def extract_tickers(text: str, known_tickers: set[str] | None = None) -> list[str]:
    """
    Extract stock ticker symbols from text.

    Pure function - identifies potential tickers using patterns.

    Args:
        text: Text to extract tickers from
        known_tickers: Optional set of valid tickers for validation

    Returns:
        List of extracted ticker symbols (uppercase, deduplicated)
    """
    tickers = []

    # Pattern 1: $TICKER format (most reliable)
    dollar_pattern = r'\$([A-Z]{1,5})\b'
    for match in re.finditer(dollar_pattern, text.upper()):
        ticker = match.group(1)
        if ticker not in COMMON_WORDS:
            tickers.append(ticker)

    # Pattern 2: (TICKER) in parentheses
    paren_pattern = r'\(([A-Z]{1,5})\)'
    for match in re.finditer(paren_pattern, text.upper()):
        ticker = match.group(1)
        if ticker not in COMMON_WORDS:
            tickers.append(ticker)

    # Pattern 3: Known tickers if provided
    if known_tickers:
        words = set(re.findall(r'\b([A-Z]{1,5})\b', text.upper()))
        for word in words:
            if word in known_tickers and word not in COMMON_WORDS:
                tickers.append(word)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            result.append(t)

    return result


# ============================================================================
# Scoring Functions
# ============================================================================

def score_source_credibility(source: str) -> float:
    """
    Score source credibility.

    Pure function - returns credibility score 0-1.
    """
    source_lower = source.lower().strip()

    # Check exact match first
    if source_lower in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[source_lower]

    # Check partial match
    for key, score in SOURCE_CREDIBILITY.items():
        if key in source_lower or source_lower in key:
            return score

    # Unknown source gets moderate score
    return 0.5


def score_recency(
    published: datetime,
    now: datetime | None = None,
    config: NewsAggregatorConfig | None = None,
) -> float:
    """
    Score news recency.

    Pure function - returns recency score 0-1 (1 = just published).
    """
    config = config or NewsAggregatorConfig()
    now = now or datetime.now()

    # Handle timezone-aware vs naive datetime comparison
    if published.tzinfo is not None and now.tzinfo is None:
        published = published.replace(tzinfo=None)
    elif published.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    age = now - published
    age_hours = age.total_seconds() / 3600

    if age_hours < 0:
        return 1.0  # Future date (probably timezone issue), treat as fresh

    if age_hours >= config.max_age_hours:
        return 0.0

    # Exponential decay
    decay_rate = 3.0 / config.max_age_hours  # Decay to ~5% at max age
    score = pow(0.5, age_hours * decay_rate / 3)

    return round(min(1.0, score), 4)


def score_keywords(text: str) -> tuple[float, list[str]]:
    """
    Score text for market-moving keywords.

    Pure function - returns (score, keywords_found).
    """
    text_lower = text.lower()
    found_keywords = []
    scores = []

    for keyword, impact in MARKET_KEYWORDS.items():
        if keyword in text_lower:
            found_keywords.append(keyword)
            scores.append(impact)

    if not scores:
        return 0.0, []

    # Use max score + bonus for multiple keywords
    max_score = max(scores)
    multi_bonus = min(0.15, len(scores) * 0.03)

    return round(min(1.0, max_score + multi_bonus), 4), found_keywords


def is_irrelevant_content(title: str, description: str | None = None) -> bool:
    """
    Check if content is irrelevant lifestyle/non-financial news.

    Pure function - returns True if content should be filtered out.
    """
    text = f"{title} {description or ''}".lower()

    for keyword in IRRELEVANT_KEYWORDS:
        if keyword in text:
            return True

    return False


def compute_relevance_score(
    source_score: float,
    recency_score: float,
    keyword_score: float,
    ticker_count: int,
    config: NewsAggregatorConfig | None = None,
) -> float:
    """
    Compute overall relevance score.

    Pure function - weighted combination of component scores.
    """
    config = config or NewsAggregatorConfig()

    # Ticker score: having tickers increases relevance
    ticker_score = min(1.0, ticker_count * 0.3)

    relevance = (
        source_score * config.weight_source +
        recency_score * config.weight_recency +
        keyword_score * config.weight_keywords +
        ticker_score * config.weight_tickers
    )

    return round(min(1.0, relevance), 4)


# ============================================================================
# Classification Functions
# ============================================================================

def classify_category(
    title: str,
    description: str | None,
    tickers: list[str],
    keywords: list[str],
    source: str,
) -> NewsCategory:
    """
    Classify news into category.

    Pure function - determines if market-wide, sector, or company news.
    """
    text = f"{title} {description or ''}".lower()
    source_lower = source.lower()

    # Social sources
    if "reddit" in source_lower or any(x in source_lower for x in ["r/stocks", "r/wallstreetbets"]):
        return NewsCategory.SOCIAL

    # Company-specific: has tickers mentioned
    if len(tickers) == 1:
        return NewsCategory.COMPANY

    # Market-wide: macro/fed keywords without specific tickers
    market_keywords = ["fed", "federal reserve", "interest rate", "inflation", "gdp",
                       "unemployment", "cpi", "fomc", "recession", "economy"]
    if any(kw in text for kw in market_keywords) and len(tickers) <= 1:
        return NewsCategory.MARKET_WIDE

    # Sector: industry-specific keywords
    for sector, sector_kws in SECTOR_KEYWORDS.items():
        if any(kw in text for kw in sector_kws):
            return NewsCategory.SECTOR

    # Multiple tickers mentioned = likely market-wide or sector
    if len(tickers) > 2:
        return NewsCategory.MARKET_WIDE

    # Default
    return NewsCategory.UNKNOWN


def detect_sector(title: str, description: str | None) -> str | None:
    """
    Detect sector from text.

    Pure function - returns sector name or None.
    """
    text = f"{title} {description or ''}".lower()

    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return sector

    return None


def determine_priority(
    relevance_score: float,
    recency_score: float,
    keywords: list[str],
    config: NewsAggregatorConfig | None = None,
) -> NewsPriority:
    """
    Determine news priority level.

    Pure function - assigns priority based on scores and keywords.
    """
    config = config or NewsAggregatorConfig()

    # Critical keywords trigger high priority
    critical_keywords = {"crash", "bankruptcy", "rate cut", "rate hike", "recession"}
    if any(kw in critical_keywords for kw in keywords):
        if recency_score > 0.5:
            return NewsPriority.CRITICAL
        return NewsPriority.HIGH

    # Score-based priority
    if relevance_score >= config.critical_priority_threshold:
        return NewsPriority.CRITICAL
    elif relevance_score >= config.high_priority_threshold:
        return NewsPriority.HIGH
    elif relevance_score >= config.min_relevance_score:
        return NewsPriority.MEDIUM
    else:
        return NewsPriority.LOW


# ============================================================================
# Deduplication
# ============================================================================

def compute_content_hash(title: str, url: str | None) -> str:
    """
    Compute hash for deduplication.

    Pure function - creates identifier for similar content detection.
    """
    # Normalize title: lowercase, remove punctuation, sort words
    normalized = re.sub(r'[^\w\s]', '', title.lower())
    words = sorted(normalized.split())
    content = " ".join(words[:10])  # First 10 words sorted

    # Simple hash
    return hex(hash(content) & 0xFFFFFFFF)[2:]


def title_similarity(title1: str, title2: str) -> float:
    """
    Compute similarity between two titles.

    Pure function - returns similarity score 0-1.
    """
    # Normalize
    def normalize(t):
        return set(re.sub(r'[^\w\s]', '', t.lower()).split())

    words1 = normalize(title1)
    words2 = normalize(title2)

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def deduplicate_news(
    items: list[ScoredNewsItem],
    config: NewsAggregatorConfig | None = None,
) -> list[ScoredNewsItem]:
    """
    Deduplicate news items.

    Pure function - removes duplicates, keeps highest-scored version.
    """
    config = config or NewsAggregatorConfig()

    if not items:
        return []

    # Group by content hash first
    by_hash: dict[str, list[ScoredNewsItem]] = defaultdict(list)
    for item in items:
        by_hash[item.content_hash].append(item)

    # Keep best from each hash group
    best_by_hash = []
    for group in by_hash.values():
        best = max(group, key=lambda x: (x.source_credibility, x.relevance_score))
        best_by_hash.append(best)

    # Check title similarity for remaining items
    result = []
    for item in sorted(best_by_hash, key=lambda x: x.relevance_score, reverse=True):
        is_duplicate = False
        for existing in result:
            if title_similarity(item.title, existing.title) >= config.similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            result.append(item)

    return result


# ============================================================================
# Main Processing Functions
# ============================================================================

def score_news_item(
    item: RawNewsItem,
    config: NewsAggregatorConfig | None = None,
    known_tickers: set[str] | None = None,
    now: datetime | None = None,
) -> ScoredNewsItem:
    """
    Score and classify a single news item.

    Pure function - transforms raw news into scored/classified item.
    """
    config = config or NewsAggregatorConfig()
    now = now or datetime.now()

    text = f"{item.title} {item.description or ''}"

    # Extract tickers from text
    tickers = extract_tickers(text, known_tickers)

    # Include source ticker if provided (news fetched for a specific ticker)
    if item.source_ticker and item.source_ticker.upper() not in tickers:
        tickers.insert(0, item.source_ticker.upper())

    # Score components
    source_score = score_source_credibility(item.source)
    recency_score = score_recency(item.published, now, config)
    keyword_score, keywords = score_keywords(text)

    # Overall relevance
    relevance = compute_relevance_score(
        source_score, recency_score, keyword_score, len(tickers), config
    )

    # Classification
    category = classify_category(item.title, item.description, tickers, keywords, item.source)
    sector = detect_sector(item.title, item.description)
    priority = determine_priority(relevance, recency_score, keywords, config)

    # Content hash for dedup
    content_hash = compute_content_hash(item.title, item.url)

    return ScoredNewsItem(
        title=item.title,
        url=item.url,
        source=item.source,
        published=item.published,
        description=item.description,
        relevance_score=relevance,
        source_credibility=source_score,
        recency_score=recency_score,
        keyword_score=keyword_score,
        category=category,
        priority=priority,
        sector=sector,
        tickers_mentioned=tickers,
        keywords_found=keywords,
        content_hash=content_hash,
    )


def aggregate_news(
    items: list[RawNewsItem],
    config: NewsAggregatorConfig | None = None,
    known_tickers: set[str] | None = None,
    now: datetime | None = None,
) -> list[ScoredNewsItem]:
    """
    Aggregate, score, classify, and deduplicate news items.

    Pure function - main entry point for news processing.

    Args:
        items: Raw news items from adapters
        config: Aggregation configuration
        known_tickers: Valid ticker symbols for extraction
        now: Current time for recency scoring

    Returns:
        Scored, classified, deduplicated news items sorted by relevance
    """
    config = config or NewsAggregatorConfig()
    now = now or datetime.now()

    # Filter out irrelevant content first (lifestyle, non-financial)
    relevant_items = [
        item for item in items
        if not is_irrelevant_content(item.title, item.description)
    ]

    # Score remaining items
    scored = [
        score_news_item(item, config, known_tickers, now)
        for item in relevant_items
    ]

    # Filter by minimum relevance
    filtered = [s for s in scored if s.relevance_score >= config.min_relevance_score]

    # Deduplicate
    deduped = deduplicate_news(filtered, config)

    # Sort by relevance (descending)
    return sorted(deduped, key=lambda x: x.relevance_score, reverse=True)


def filter_by_category(
    items: list[ScoredNewsItem],
    category: NewsCategory,
) -> list[ScoredNewsItem]:
    """Filter news by category."""
    return [i for i in items if i.category == category]


def filter_by_ticker(
    items: list[ScoredNewsItem],
    ticker: str,
) -> list[ScoredNewsItem]:
    """Filter news mentioning a specific ticker."""
    ticker = ticker.upper()
    return [i for i in items if ticker in i.tickers_mentioned]


def filter_by_priority(
    items: list[ScoredNewsItem],
    min_priority: NewsPriority,
) -> list[ScoredNewsItem]:
    """Filter news by minimum priority level."""
    priority_order = {
        NewsPriority.LOW: 0,
        NewsPriority.MEDIUM: 1,
        NewsPriority.HIGH: 2,
        NewsPriority.CRITICAL: 3,
    }
    min_level = priority_order[min_priority]
    return [i for i in items if priority_order[i.priority] >= min_level]
