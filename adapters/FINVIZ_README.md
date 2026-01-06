# Finviz News Adapter

## Overview

The Finviz adapter scrapes ticker-specific news from [Finviz](https://finviz.com) quote pages. It provides real-time financial news headlines with proper source attribution, timestamps, and URLs.

## Features

- **Ticker-specific news**: Fetches news for individual stocks
- **Structured parsing**: Extracts headline, source, timestamp, and URL
- **Rate limiting**: 1.5s delay between requests (configurable) to avoid IP blocks
- **Caching**: 30-minute TTL for news data (via Category.NEWS config)
- **News aggregation**: Converts to `RawNewsItem` for use with domain news aggregator
- **Error handling**: Proper error messages for blocking, parsing failures

## Architecture

```
FinvizAdapter (scraper)
    ↓
  Observation(category=NEWS) containing RawNewsItem
    ↓
  domain.aggregate_news() → ScoredNewsItem
    ↓
  News relevance scoring, deduplication, classification
```

## Usage

### Basic Usage

```python
from adapters import FinvizAdapter

adapter = FinvizAdapter()

# Fetch news for a ticker
observations = adapter.get_ticker_news("AAPL")

# Get RawNewsItem objects for news aggregation
raw_news = adapter.get_raw_news_items("AAPL")
```

### With News Aggregation

```python
from adapters import FinvizAdapter
from domain import aggregate_news, filter_by_priority, NewsPriority

adapter = FinvizAdapter()

# Fetch raw news
raw_news = adapter.get_raw_news_items("NVDA")

# Aggregate, score, deduplicate, and classify
scored_news = aggregate_news(raw_news)

# Filter by priority
high_priority = filter_by_priority(scored_news, NewsPriority.HIGH)

for item in high_priority:
    print(f"{item.title} (score: {item.relevance_score})")
```

### Demo Script

```bash
python examples/finviz_news_demo.py AAPL
```

## Configuration

### Rate Limiting (config.toml)

```toml
[rate_limits]
finviz = 30              # Max 30 requests per minute
finviz_delay = 1.5       # 1.5 second delay between requests
```

**Why these limits?**
- Finviz has no official API
- Aggressive scraping triggers IP blocks (403 Forbidden)
- 1.5s delay is respectful and avoids detection

### Cache TTL

News caching is controlled by the global `NEWS` category TTL:

```toml
[cache_ttl]
news_minutes = 30  # News cached for 30 minutes
```

## Data Structure

### Finviz News Table

The adapter parses this HTML structure:

```html
<table class="fullview-news-outer">
    <tr>
        <td class="news_date-cell">Jan-03-26 04:30PM</td>
        <td class="news-link-left">
            <a href="https://..." class="tab-link-news">Headline here</a>
            <span class="news-link-right">
                <span class="news-source">Source Name</span>
            </span>
        </td>
    </tr>
</table>
```

### Output Format

Each news item is converted to `RawNewsItem`:

```python
RawNewsItem(
    title="Apple announces new product",
    url="https://example.com/article",
    source="Reuters",
    published=datetime(2026, 1, 3, 16, 30),
    description=None,  # Not provided by Finviz
    category_hint=None,
    source_ticker="AAPL"  # Tagged with source ticker
)
```

## Date Parsing

Finviz uses multiple date formats:

| Format | Example | Handling |
|--------|---------|----------|
| Standard | `Jan-03-26 04:30PM` | Parsed via strptime |
| Date only | `Jan-03-26` | Defaults to 12:00 PM |
| Today | `Today 04:30PM` | Current date + time |
| Yesterday | `Yesterday` | Current date - 1 day |

## Source Credibility

Finviz itself scores **0.70** (Tier 4: Aggregator) in the domain news scoring system. Individual article sources (Reuters, Bloomberg, etc.) retain their original credibility when present.

## Error Handling

### Common Errors

**403 Forbidden (IP blocked)**
```
Finviz blocked request (403 Forbidden).
Possible causes: too many requests, User-Agent blocked, IP rate limit.
Try increasing rate_delays.finviz in config.
```

**Solution**: Increase `finviz_delay` to 2.0-3.0 seconds

**ParseError (HTML structure changed)**
```
Failed to parse news table: ...
```

**Solution**: Finviz may have changed their HTML. Check `_parse_news_table()` implementation.

**No news found**
```
News table not found for TICKER (HTML structure may have changed)
```

**Solution**: Check if ticker is valid or if Finviz updated their page structure.

## Limitations

1. **No API**: Scraping-based, may break if HTML changes
2. **Rate limiting required**: Too many requests → IP block
3. **Limited history**: Only shows recent news (typically 10-20 items)
4. **No descriptions**: Finviz provides headlines only, no article summaries
5. **Ticker-specific only**: Cannot fetch market-wide news

## Comparison with Other News Adapters

| Adapter | Type | Coverage | API | Rate Limit |
|---------|------|----------|-----|------------|
| Finviz | Scraper | Ticker-specific | No | 1.5s delay |
| RSS | RSS feeds | Market-wide | No | 0.1s delay |
| Yahoo | API | Ticker-specific | Yes | 0.5s delay |

**When to use Finviz:**
- Need ticker-specific news
- Want real-time headlines
- Prefer aggregated sources

**When to use RSS:**
- Need market-wide news
- Fed, economy, sector news
- Higher volume acceptable

## Implementation Details

### Key Methods

**`_fetch_ticker_news(ticker: str) -> list[FinvizNewsItem]`**
- Fetches and parses HTML from Finviz quote page
- Extracts news table rows
- Returns structured news items

**`_parse_news_table(html: str, ticker: str) -> list[FinvizNewsItem]`**
- Uses BeautifulSoup to parse HTML
- Finds `fullview-news-outer` table
- Extracts: timestamp, headline, URL, source

**`_parse_finviz_date(date_str: str) -> datetime | None`**
- Handles multiple date formats
- Relative dates (Today, Yesterday)
- Standard format (MMM-DD-YY HH:MMAM/PM)

**`get_raw_news_items(ticker: str) -> list[RawNewsItem]`**
- Convenience method for direct news aggregation
- Returns `RawNewsItem` objects instead of `Observation`

## Testing

### Manual Test

```python
from adapters import FinvizAdapter

adapter = FinvizAdapter()
news = adapter.get_ticker_news("AAPL")

for obs in news:
    print(obs.data["headline"])
    print(obs.data["source"])
    print(obs.data["published"])
    print()
```

### Integration Test

The adapter integrates with the domain news aggregator:

```python
from adapters import FinvizAdapter
from domain import aggregate_news

adapter = FinvizAdapter()
raw_news = adapter.get_raw_news_items("AAPL")
scored = aggregate_news(raw_news)

assert len(scored) > 0
assert all(item.source_ticker == "AAPL" for item in scored)
```

## Future Enhancements

1. **Playwright scraping**: More robust against blocking
2. **Proxy support**: Rotate IPs for higher volume
3. **Full article fetching**: Parse article content from URLs
4. **Sentiment analysis**: Analyze headline sentiment
5. **Multi-ticker batching**: Fetch news for multiple tickers efficiently

## Maintenance

**If Finviz changes their HTML:**
1. Inspect the quote page HTML
2. Update CSS selectors in `_parse_news_table()`
3. Test date parsing with new formats
4. Update this README with new structure

**Monitor for:**
- 403 errors increasing → adjust rate limits
- ParseError exceptions → HTML structure changed
- Empty results → ticker format or page structure changed
