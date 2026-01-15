# HANDOFF

## Current Work

### Goal
Website optimization (January 15, 2026) - All major optimizations complete (Groups A, B, C).

### Context
Fintel is a financial intelligence dashboard. This session completed backend caching (Group A) and JSON splitting (Group B).

### Session Summary - ALL OPTIMIZATIONS COMPLETE

**Performance improvements:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Pipeline (cold) | 3:55 | 42s | **82% faster** |
| Pipeline (warm) | 3:55 | 12s | **95% faster** |
| Core bundle | 1.3 MB | 87 KB | **93% smaller** |

**Backend caching (Group A):**

| Cache | File | TTL |
|-------|------|-----|
| Backtest scores | `domain/backtest.py:697-770` | 24h |
| SPY historical | `adapters/calendar.py:728-763` | 7d |
| FRED releases | `adapters/calendar.py:864-995` | 24h |

**JSON splitting (Group B):**

| File | Size | Loaded |
|------|------|--------|
| Core report.json | 87 KB | Always (SSG) |
| stockDetails.json | 439 KB | Portfolio/Compare/Watchlist pages |
| allStocks.json | 112 KB | Heatmap page |
| smartMoney.json | 121 KB | Smart money section |

**Implementation:** Components lazy-load data via `frontend/src/data/lazy.ts`:
- `getStockDetails()` - fetches `/data/stockDetails.json`
- `getAllStocksLazy()` - fetches `/data/allStocks.json`
- `getSmartMoney()` - fetches `/data/smartMoney.json`

### Current State
- All Group A (backend caching) complete
- All Group B (JSON splitting) complete
- All Group C (frontend memoization) complete
- Pipeline time: 12s (warm) / 42s (cold)
- Core bundle: 87 KB
- Build verified

### Next Steps - GROUP D (Optional)

**Group D - HTTP cache headers:**
- Add Cache-Control headers to static JSON
- Browser caching for repeat visits

### PLAN.md Summary

| Group | Description | Status |
|-------|-------------|--------|
| A | Backend caching (scores, SPY, FRED) | **complete** |
| B | Split report.json (1.3MB → 87KB core) | **complete** |
| C | Frontend React memoization | **complete** |
| D | HTTP cache headers, vectorization | optional |

### Subtasks Status

| Task | Status |
|------|--------|
| WatchlistView useMemo | complete |
| WatchlistView useCallback | complete |
| HeatMapTile React.memo | complete |
| PortfolioView useMemo | complete |
| Sparkline client:visible fix | complete |
| Backtest score caching | complete |
| SPY historical caching | complete |
| FRED release caching | complete |
| Split report.json | **complete** |

### Key Files Modified This Session

**Backend:**
- `domain/backtest.py:652,691-770` - Backtest score caching
- `adapters/calendar.py:47,728-763,864-995` - SPY + FRED caching
- `scripts/generate_frontend_data.py:1075-1111` - JSON splitting

**Frontend:**
- `src/data/lazy.ts` - New lazy-loading utilities
- `src/data/types.ts` - Made split fields optional
- `src/data/report.ts` - Handle optional fields
- `src/components/islands/PortfolioView.tsx` - Lazy load stockDetails
- `src/components/islands/WatchlistView.tsx` - Lazy load stockDetails
- `src/components/islands/CompareView.tsx` - Lazy load stockDetails
- `src/pages/portfolio.astro` - Removed stockDetails prop
- `src/pages/watchlist.astro` - Removed stockDetails prop
- `src/pages/compare.astro` - Removed stockDetails prop

---

## History

- (uncommitted): Frontend React memoization + Sparkline lazy load fix
- 1e9920c: docs: update HANDOFF with full optimization summary
- cce71ec: perf: parallelize backtests + batch stock details
- 8262e71: fix: correct backtest display format (was -1000% instead of -10%)
- 7e58b58: docs: update HANDOFF with parallel fetching results
- 1ff305d: perf: parallelize news, options, and insider fetching
- d1a01a3: perf: parallelize 13F hedge fund fetching
- 34c76d8: fix: align batch fundamentals keys with non-batch method
- 3866601: feat: batch optimization for prices + fundamentals

---

## Anti-Patterns

### 1. client:load for Heavy Libraries
**Problem:** Sparkline used `client:load` causing 164KB lightweight-charts to load on homepage
**Resolution:** Changed to `client:visible` - only loads when scrolled into view
**Prevention:** Use `client:visible` or `client:idle` for heavy React islands; reserve `client:load` for critical above-fold content

### 2. Serial API Calls (Performance)
**Problem:** Pipeline made 260+ serial API calls taking 150-300s
**Resolution:** Added batch methods and ThreadPoolExecutor parallelization
**Prevention:** Profile pipeline; use batch methods for O(n) operations

### 3. Inconsistent Dict Keys Between Batch/Non-Batch Methods
**Problem:** `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"`
**Resolution:** Aligned batch method to use same keys as non-batch
**Prevention:** When adding batch methods, copy return dict structure exactly from non-batch version

### 4. Python Percent Format on Already-Percent Values
**Problem:** Using `:.1%` format on values like -10.9 gave -1090.0% (multiplies by 100)
**Resolution:** Changed to `:.1f}%` format (no auto-multiplication)
**Prevention:** Use `:.1f}%` for values already in percentage form; `:.1%` only for decimals (0.109)

### 5. @lru_cache Before Environment Loaded
**Problem:** `get_config()` cached before `load_dotenv()` ran due to import chain
**Resolution:** Added `reload_settings()` call immediately after `load_dotenv()`
**Prevention:** Always reload settings after loading .env

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| (uncommitted) | client:load for heavy libs | client:visible for lazy loading |
| cce71ec | Serial backtest loop | ThreadPoolExecutor for 3 timeframes |
| 8262e71 | :.1% on percentage values | Use :.1f}% instead |
| 1ff305d | Serial news/options/insider loops | _fetch_sources_parallel() helper |
| d1a01a3 | Serial 13F fund fetching | _fetch_single_fund() + ThreadPoolExecutor |
| 34c76d8 | Batch/non-batch key mismatch | Copy exact key structure from non-batch |
| 2dd8548 | @lru_cache before env loaded | reload_settings() after load_dotenv() |
