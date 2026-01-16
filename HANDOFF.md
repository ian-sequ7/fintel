# HANDOFF

## Current Work

### Goal
Website optimization complete (January 15, 2026) - All optimization groups (A, B, C, D) finished. Custom server with cache headers deployed.

### Context
Fintel is a financial intelligence dashboard with Python backend (data pipeline) and Astro/React frontend. Optimization journey:
- Original pipeline: 9:22
- After parallelization: 3:55
- After caching: 12s (warm) / 42s (cold)
- Bundle: 1.3MB → 87KB core

### Final Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Pipeline (cold) | 3:55 | 42s | **82% faster** |
| Pipeline (warm) | 3:55 | 12s | **95% faster** |
| Core bundle | 1.3 MB | 87 KB | **93% smaller** |

### Completed Optimizations

**Group A - Backend Caching:**

| Cache | File | TTL |
|-------|------|-----|
| Backtest scores | `domain/backtest.py:697-770` | 24h |
| SPY historical | `adapters/calendar.py:728-763` | 7d |
| FRED releases | `adapters/calendar.py:864-995` | 24h |

Pattern: `cache.get("source", key=value)` → miss → work → `cache.set("source", data, ttl, key=value)`

**Group B - JSON Splitting:**

| File | Size | Loaded By |
|------|------|-----------|
| Core report.json | 87 KB | Always (SSG) |
| stockDetails.json | 439 KB | Portfolio/Compare/Watchlist |
| allStocks.json | 112 KB | Heatmap |
| smartMoney.json | 121 KB | Smart money section |

Lazy-load via `frontend/src/data/lazy.ts`:
- `getStockDetails()` → `/data/stockDetails.json`
- `getAllStocksLazy()` → `/data/allStocks.json`
- `getSmartMoney()` → `/data/smartMoney.json`

**Group C - Frontend Memoization:**
- HeatMapTile: `React.memo` with custom comparison
- PortfolioView/WatchlistView: `useMemo` + `useCallback`
- Sparkline: `client:visible` (was `client:load`, saved 164KB)

**Group D - HTTP Cache Headers:**
Custom server (`frontend/server.mjs`) with cache control:

| Path | Cache-Control | Purpose |
|------|---------------|---------|
| `/data/*.json` | `max-age=3600, stale-while-revalidate=86400` | Data refreshed daily |
| `/_astro/*` | `max-age=31536000, immutable` | Hashed assets (forever) |
| Other static | `max-age=3600` | Default 1 hour |

Implementation:
- Switched Node adapter to `middleware` mode (was `standalone`)
- Added `frontend/server.mjs` - custom HTTP server wrapping Astro handler
- Run with: `npm run start` (added to package.json)

### Current State
- All Groups A, B, C, D complete
- Build verified, server tested
- All pages loading correctly
- Cache headers verified with curl

### Subtasks Status

| Task | Status |
|------|--------|
| Backtest score caching | complete |
| SPY historical caching | complete |
| FRED release caching | complete |
| Split report.json | complete |
| Lazy-load helpers | complete |
| Component updates | complete |
| HTTP cache headers | complete |
| Server test | complete |

### Key Files

**Backend caching:**
- `adapters/cache.py` - PersistentCache (SQLite-backed)
- `domain/backtest.py:652,691-770` - Backtest score cache
- `adapters/calendar.py:47,728-763,864-995` - SPY + FRED cache

**JSON splitting:**
- `scripts/generate_frontend_data.py:1075-1111` - Split generation
- `frontend/public/data/` - Split JSON files

**Lazy loading:**
- `frontend/src/data/lazy.ts` - Fetch helpers with caching
- `frontend/src/data/types.ts` - Made split fields optional
- `frontend/src/components/islands/PortfolioView.tsx` - Lazy load
- `frontend/src/components/islands/WatchlistView.tsx` - Lazy load
- `frontend/src/components/islands/CompareView.tsx` - Lazy load

**HTTP caching:**
- `frontend/server.mjs` - Custom server with cache headers
- `frontend/astro.config.mjs` - Node adapter in middleware mode

---

## History

- 04e2cb2: perf: split report.json for lazy loading (1.3MB → 87KB core)
- ec7224c: perf: add backend caching for backtest scores, SPY, and FRED data
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

### 1. Passing Heavy Data as Astro Props
**Problem:** Astro serializes props to React islands into HTML - 1.3MB stockDetails bundled into every page
**Resolution:** Split into `/data/*.json`, lazy-load in components via `useEffect`
**Prevention:** Never pass >50KB data as props to `client:*` components; use fetch instead

### 2. client:load for Heavy Libraries
**Problem:** Sparkline used `client:load` causing 164KB lightweight-charts to load on homepage
**Resolution:** Changed to `client:visible` - only loads when scrolled into view
**Prevention:** Use `client:visible` or `client:idle` for heavy React islands

### 3. Serial API Calls (Performance)
**Problem:** Pipeline made 260+ serial API calls taking 150-300s
**Resolution:** Added batch methods and ThreadPoolExecutor parallelization
**Prevention:** Profile pipeline; use batch methods for O(n) operations

### 4. Inconsistent Dict Keys Between Batch/Non-Batch Methods
**Problem:** `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"`
**Resolution:** Aligned batch method to use same keys as non-batch
**Prevention:** When adding batch methods, copy return dict structure exactly from non-batch version

### 5. Python Percent Format on Already-Percent Values
**Problem:** Using `:.1%` format on values like -10.9 gave -1090.0% (multiplies by 100)
**Resolution:** Changed to `:.1f}%` format (no auto-multiplication)
**Prevention:** Use `:.1f}%` for values already in percentage form; `:.1%` only for decimals (0.109)

### 6. @lru_cache Before Environment Loaded
**Problem:** `get_config()` cached before `load_dotenv()` ran due to import chain
**Resolution:** Added `reload_settings()` call immediately after `load_dotenv()`
**Prevention:** Always reload settings after loading .env

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| 04e2cb2 | Heavy data as Astro props | Split JSON + lazy-load in components |
| ec7224c | Uncached expensive API calls | PersistentCache with TTL |
| cce71ec | Serial backtest loop | ThreadPoolExecutor for 3 timeframes |
| 8262e71 | :.1% on percentage values | Use :.1f}% instead |
| 1ff305d | Serial news/options/insider loops | _fetch_sources_parallel() helper |
| d1a01a3 | Serial 13F fund fetching | _fetch_single_fund() + ThreadPoolExecutor |
| 34c76d8 | Batch/non-batch key mismatch | Copy exact key structure from non-batch |
