# PLAN: Website Optimization

## Executive Summary

**Current State:** Pipeline runs in ~3:55 (after previous parallelization work)
**Target State:** ~1:30-2:00 total runtime + faster frontend loading

**Optimization Categories:**
| Category | Current | Target | Savings |
|----------|---------|--------|---------|
| Backend Pipeline | 3:55 | ~1:30 | ~60% |
| Frontend Bundle | 1.3MB JSON | <400KB | ~70% |
| Rendering | Unoptimized | Memoized | ~40% faster interactions |

---

## Phase 1: Backend Scoring Cache (HIGH PRIORITY)

**Goal:** Reduce backtest runtime from ~2min to ~45s

### Module 1.1: Backtest Score Caching
**Files:**
- `domain/backtest.py:492-650` - Add cache lookups
- `adapters/cache.py` - Reuse PersistentCache

**Symbols:**
```python
def _get_cached_score(ticker: str, date: str, timeframe: str) -> Optional[dict]:
    """Lookup cached score from PersistentCache. TTL: 24h."""

def _cache_score(ticker: str, date: str, timeframe: str, score: dict) -> None:
    """Store score in PersistentCache."""
```

**Done Criteria:**
- [ ] Second pipeline run completes backtests in <45s
- [ ] Cache hit rate >90% for same-day runs
- [ ] No change to scoring results (verify via diff)

**Complexity:** S (reuse existing cache infrastructure)

---

### Module 1.2: Scoring Vectorization (Optional)
**Files:**
- `domain/scoring.py:564-731` - Vectorize _score_* functions

**Done Criteria:**
- [ ] Score 50 tickers in <5s (vs current ~15s)
- [ ] Results match non-vectorized version (assert)

**Complexity:** M (NumPy refactor of scoring functions)

---

## Phase 2: Briefing Data Caching (MEDIUM PRIORITY)

**Goal:** Reduce briefing generation from ~25s to ~6s

### Module 2.1: SPY Historical Data Cache
**Files:**
- `adapters/calendar.py:728-746` - Cache SPY download
- `adapters/cache.py` - Add TTL=7 days key

**Symbols:**
```python
def _get_spy_historical_cached(start: date, end: date) -> pd.DataFrame:
    """Fetch SPY data with 7-day cache. Key: spy_historical:{start}:{end}"""
```

**Done Criteria:**
- [ ] SPY data fetched from cache on subsequent runs
- [ ] Cache invalidated after 7 days
- [ ] Reaction calculations unchanged

**Complexity:** S

---

### Module 2.2: FRED Release History Cache
**Files:**
- `adapters/calendar.py:744-799` - Cache FRED series
- Key pattern: `fred_release:{series_id}:{lookback_months}`

**Done Criteria:**
- [ ] FRED data cached for 24h
- [ ] 6 fewer API calls per run

**Complexity:** S

---

### Module 2.3: Parallel Calendar Fetching
**Files:**
- `adapters/calendar.py:548-625` - Parallelize 3 calendar sources

**Symbols:**
```python
def _fetch_calendars_parallel() -> tuple[EarningsCalendar, IPOCalendar, EconomicCalendar]:
    """Fetch all 3 calendars concurrently with ThreadPoolExecutor."""
```

**Done Criteria:**
- [ ] 3 calendar fetches run in parallel
- [ ] Total calendar fetch time <3s

**Complexity:** S (copy pattern from pipeline.py:633-678)

---

## Phase 3: Frontend Bundle Optimization (HIGH PRIORITY)

**Goal:** Reduce initial bundle from 1.3MB to <400KB

### Module 3.1: Split report.json
**Files:**
- `scripts/generate_frontend_data.py` - Generate split files
- `frontend/src/data/report.ts` - Dynamic imports

**New File Structure:**
```
frontend/src/data/
├── report-picks.json      (~50KB)
├── report-macro.json      (~100KB)
├── report-news.json       (~200KB)
├── report-smartmoney.json (~100KB)
└── report-briefing.json   (~50KB)
```

**Symbols:**
```typescript
// frontend/src/data/report.ts
export async function getPicks(): Promise<Pick[]> {
    const data = await import("./report-picks.json");
    return data.default.picks;
}

export async function getMacro(): Promise<MacroData> {
    const data = await import("./report-macro.json");
    return data.default;
}
```

**Done Criteria:**
- [ ] Each split file <200KB
- [ ] Dynamic imports lazy-load only needed data
- [ ] Homepage loads picks + macro only (<150KB)
- [ ] No functionality changes

**Complexity:** M

---

### Module 3.2: Code-Split Heavy Components
**Files:**
- `frontend/src/components/islands/PriceChart.tsx` (189KB)
- `frontend/src/components/islands/HeatMap.tsx` (12KB)

**Done Criteria:**
- [ ] PriceChart only loads on /stock/[ticker] pages
- [ ] HeatMap only loads on heatmap page
- [ ] Verify `client:visible` directive working

**Complexity:** S

---

## Phase 4: React Rendering Optimization (MEDIUM PRIORITY)

**Goal:** Reduce re-renders and improve interaction responsiveness

### Module 4.1: WatchlistView Memoization
**Files:**
- `frontend/src/components/islands/WatchlistView.tsx:108-122`

**Changes:**
```tsx
// Before (lines 108-122)
const totalValue = watchlist.reduce(...);

// After
const { totalValue, totalChange, avgConviction } = useMemo(() => ({
    totalValue: watchlist.reduce(...),
    totalChange: watchlist.reduce(...),
    avgConviction: watchlist.reduce(...),
}), [watchlist, stockDetails]);
```

**Done Criteria:**
- [ ] Summary calculations only recompute when data changes
- [ ] No visible behavior change

**Complexity:** S (5 min)

---

### Module 4.2: WatchlistView useCallback
**Files:**
- `frontend/src/components/islands/WatchlistView.tsx:64-77`

**Changes:**
```tsx
const handleRemove = useCallback((ticker: string) => {
    // existing logic
}, [watchlist]);
```

**Done Criteria:**
- [ ] Event handlers stable across renders
- [ ] Child components don't re-render unnecessarily

**Complexity:** S (5 min)

---

### Module 4.3: HeatMapTile Memoization
**Files:**
- `frontend/src/components/islands/HeatMap.tsx:504-554`

**Changes:**
```tsx
const HeatMapTile = React.memo(({ stock, layout, onClick }) => {
    // existing render logic
});
```

**Done Criteria:**
- [ ] 500+ tiles don't all re-render on filter change
- [ ] Only changed tiles update

**Complexity:** S (10 min)

---

### Module 4.4: PortfolioView Analytics Memoization
**Files:**
- `frontend/src/components/islands/PortfolioView.tsx:39-145`

**Changes:**
```tsx
const analytics = useMemo(() =>
    calculatePortfolioAnalytics(portfolio, stockDetails),
    [portfolio, stockDetails]
);
```

**Done Criteria:**
- [ ] Analytics only recalculated when portfolio changes
- [ ] Sharpe ratio, beta calculations cached

**Complexity:** S (10 min)

---

## Phase 5: HTTP Caching (LOW PRIORITY)

**Goal:** Reduce repeated network transfers by 50-70%

### Module 5.1: Static Asset Headers
**Files:**
- `frontend/astro.config.mjs` - Add response middleware

**Headers:**
```javascript
// JS/CSS with content hash in filename
Cache-Control: public, max-age=31536000, immutable

// report.json (dynamic)
Cache-Control: public, max-age=300
ETag: [content-hash]
```

**Done Criteria:**
- [ ] Browser caches static assets for 1 year
- [ ] 304 Not Modified for unchanged report.json

**Complexity:** S

---

## Implementation Groups (Parallelization)

### Group A (Can Run in Parallel)
| Module | Complexity | Est. Time |
|--------|------------|-----------|
| 1.1 Backtest Score Cache | S | 30 min |
| 2.1 SPY Historical Cache | S | 20 min |
| 2.2 FRED Release Cache | S | 20 min |

### Group B (After Group A)
| Module | Complexity | Est. Time |
|--------|------------|-----------|
| 2.3 Parallel Calendar Fetch | S | 20 min |
| 3.1 Split report.json | M | 1-2 hr |

### Group C (Frontend - Independent)
| Module | Complexity | Est. Time |
|--------|------------|-----------|
| 4.1 WatchlistView useMemo | S | 5 min |
| 4.2 WatchlistView useCallback | S | 5 min |
| 4.3 HeatMapTile memo | S | 10 min |
| 4.4 PortfolioView memo | S | 10 min |
| 3.2 Code-split components | S | 20 min |

### Group D (Optional/Lower Priority)
| Module | Complexity | Est. Time |
|--------|------------|-----------|
| 1.2 Scoring Vectorization | M | 2-3 hr |
| 5.1 HTTP Cache Headers | S | 30 min |

---

## E2E Success Criteria

### Backend Performance
- [ ] Full pipeline run: <2:00 (vs current 3:55)
- [ ] Incremental run (cached): <1:30
- [ ] No regression in pick quality (18 picks, same scoring)

### Frontend Performance
- [ ] Initial bundle: <500KB (vs current 1.3MB)
- [ ] Time to interactive: <2s on 3G
- [ ] Lighthouse performance score: >90

### Functional Verification
- [ ] All existing pages render correctly
- [ ] Watchlist/portfolio features work
- [ ] Stock detail pages load charts
- [ ] No console errors in production build

---

## Blocking Unknowns

| Unknown | Status | Resolution |
|---------|--------|------------|
| Cache key collisions? | ✅ Resolved | PersistentCache uses unique keys with TTL |
| Dynamic import support in Astro? | ✅ Resolved | Supported via `await import()` |
| React.memo compatibility? | ✅ Resolved | Standard React pattern |

---

## Decision Points for User

### 1. report.json Split Strategy
**Options:**
- **A) By data type** (picks, macro, news, smartmoney) - Recommended
- **B) By page** (homepage-data, stock-data, etc.)
- **C) Keep monolithic** (no change)

### 2. Cache TTL Strategy
**Options:**
- **A) Conservative** (24h for scores, 7d for SPY) - Recommended
- **B) Aggressive** (1h for scores, 24h for SPY)
- **C) Manual invalidation** (clear cache on demand)

### 3. Vectorization Scope
**Options:**
- **A) Skip for now** (caching gives 60%+ gains) - Recommended
- **B) Vectorize momentum scoring only**
- **C) Full vectorization refactor**

---

## Estimated Total Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Pipeline runtime | 3:55 | ~1:30 | 62% faster |
| Frontend bundle | 1.3MB | <400KB | 70% smaller |
| Interaction lag | Unoptimized | Memoized | 40% faster |
| Cache hit rate | 0% | >90% | N/A |

---

## Summary

**High-impact optimizations identified:**

1. **Backend caching** (Phase 1-2): Score caching + SPY/FRED caching = ~75s savings
2. **Frontend bundle split** (Phase 3): 1.3MB → <400KB = 70% smaller
3. **React memoization** (Phase 4): Quick wins for interaction responsiveness

**Recommended implementation order:**
1. Group C (frontend memos) - 30 min, immediate UX improvement
2. Group A (backend caches) - parallel work, biggest pipeline gains
3. Group B (report split) - medium effort, big bundle size win
4. Group D (optional) - if further optimization needed
