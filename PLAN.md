# Fintel Production Scale Expansion Plan

**STATUS: COMPLETE** ✓

## Overview
Expand fintel from MVP (10 stocks, 8 macro indicators) to production scale (S&P 500, 20+ indicators, multi-source news).

## Current State Analysis

### Existing Infrastructure (Phase 1 - Already Done)
- `BaseAdapter` in `adapters/base.py` already has:
  - `RateLimiter` class with token bucket algorithm (line 41-69)
  - `CacheEntry` class with TTL tracking (line 27-38)
  - Per-adapter caching via `_cache` dict (line 84)
  - Rate limits configurable in `config/schema.py` (lines 46-52)
  - Cache TTL configurable per category (lines 32-43)

**Phase 1 Status: COMPLETE** - Rate limiting and caching infrastructure exists.

---

## Phase 2: S&P 500 Universe

### Goal
Replace hardcoded 10-stock watchlist with dynamic S&P 500 constituents.

### Implementation

1. **Create universe provider** (`adapters/universe.py`):
   - Fetch S&P 500 constituents from Wikipedia table
   - Cache for 24 hours (constituents rarely change)
   - Return list of tickers with sector mapping
   - Fallback to static list if fetch fails

2. **Update config** (`config/schema.py`):
   - Add `universe: str = "sp500"` option
   - Keep `watchlist` for custom overrides
   - Add `max_universe_size: int = 500`

3. **Update pipeline** (`orchestration/pipeline.py`):
   - Load universe on startup
   - Batch fetching with progress tracking
   - Parallel fetching with rate limit awareness

### Files to Create/Modify
- CREATE: `adapters/universe.py`
- MODIFY: `config/schema.py`
- MODIFY: `orchestration/pipeline.py`

---

## Phase 3: Expanded Data Sources

### Goal
Add 12 more FRED indicators + 3 news sources + deduplication.

### New FRED Indicators (20 total)
Current (8):
- UNRATE, CPIAUCSL, GDP, FEDFUNDS, T10Y2Y, UMCSENT, INDPRO, HOUST

Add (12):
- DGS10 (10-Year Treasury)
- DGS2 (2-Year Treasury)
- VIXCLS (VIX)
- BAMLH0A0HYM2 (High Yield Spread)
- DCOILWTICO (Oil Price)
- GOLDAMGBD228NLBM (Gold Price)
- PAYEMS (Nonfarm Payrolls)
- RSXFS (Retail Sales)
- MORTGAGE30US (30-Year Mortgage Rate)
- CSUSHPINSA (Case-Shiller Home Price)
- BOGZ1FL073164003Q (Household Debt)
- WALCL (Fed Balance Sheet)

### New News Sources
- SEC EDGAR (8-K filings, earnings)
- Finviz news feed
- Yahoo Finance company news (already partial)

### Deduplication
- Hash-based dedup on (title + source)
- Similarity check for near-duplicates

### Files to Modify
- MODIFY: `adapters/fred.py` - Add 12 indicators
- CREATE: `adapters/sec.py` - SEC EDGAR adapter
- CREATE: `adapters/finviz.py` - Finviz news adapter
- MODIFY: `domain/news.py` - Add deduplication logic

---

## Phase 4: Config Limits + Frontend Pagination

### Goal
Update limits and add frontend pagination support.

### Config Changes
```python
# config/schema.py
max_picks_per_timeframe: int = 15  # was 5
max_news_items: int = 100          # was 50
max_macro_indicators: int = 20     # was 8
max_risks_displayed: int = 10      # was 5
```

### Pagination Support
- Add `offset` and `limit` to report generation
- Frontend already has pagination components (verify)
- API responses include total counts

### Files to Modify
- MODIFY: `config/schema.py`
- MODIFY: `orchestration/pipeline.py`
- MODIFY: `presentation/report.py`
- MODIFY: `presentation/json_api.py`

---

## Execution Order

1. **Phase 2** - S&P 500 Universe (most impactful)
2. **Phase 3** - More indicators + news sources
3. **Phase 4** - Config limits + pagination

Phase 1 is already complete (existing caching/rate limiting).

---

## Risk Mitigation

- **API Rate Limits**: Stagger requests, respect 429s, exponential backoff
- **Data Freshness**: Cache aggressively, background refresh
- **Partial Failures**: Continue on single-ticker failures (already implemented)
- **Memory**: Stream large datasets, don't load all 500 stocks at once
