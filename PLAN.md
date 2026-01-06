# Fintel Production Scale Expansion Plan

**STATUS: COMPLETE** ✓

---

# Phase 1 Quick Wins - Pre-Deployment Fixes

**STATUS: COMPLETE** ✓

## Overview

**Goal**: Fix critical issues identified in the pre-deployment audit to stabilize the application before scaling.

**Scope**: 5 quick wins that can be completed in 1-2 days with minimal risk.

**Success Criteria**: All TypeScript errors resolved, SQLite concurrent read performance improved, React errors contained, health monitoring enabled, and environment setup documented.

---

## Module Dependency Graph

```
[M1: TypeScript Fixes] ──┐
                         ├──> [M6: E2E Validation]
[M2: SQLite WAL]         │
                         │
[M3: Error Boundary] ────┤
                         │
[M4: Health Endpoint] ───┤
                         │
[M5: .env.example] ──────┘
```

**Parallel Groups**:
- **Group 1** (can run concurrently): M1, M2, M4, M5
- **Group 2** (depends on M1): M3 (needs clean TS build)
- **Group 3** (final): M6 (E2E validation of all modules)

---

## Modules

### M1: Fix TypeScript Errors
**Complexity**: S (Small) | **Time**: ~15 min
**Files**: `frontend/src/data/types.ts`, `frontend/src/data/report.ts`
**Dependencies**: None | **Parallel**: Yes

#### Changes Required

| Symbol | File:Line | Current | Change |
|--------|-----------|---------|--------|
| `Fundamentals.pegRatio` | `types.ts:72` | `number \| undefined` | `number \| null \| undefined` |
| `Fundamentals.priceToBook` | `types.ts:73` | `number \| undefined` | `number \| null \| undefined` |
| `Fundamentals.beta` | `types.ts:78` | `number \| undefined` | `number \| null \| undefined` |
| `SmartMoneyContext` | `report.ts:896` | missing `hedgeFunds` | add `hedgeFunds: []` |
| `ReportSummary` | `report.ts:902` | missing `totalStocks` | add `totalStocks: 0` |

#### Done Criteria
- [ ] `cd frontend && npx tsc --noEmit` exits with code 0
- [ ] `npm run build` completes successfully

---

### M2: Enable SQLite WAL Mode
**Complexity**: S (Small) | **Time**: ~10 min
**Files**: `db/database.py:294`
**Dependencies**: None | **Parallel**: Yes

#### Implementation
```python
# Add after line 294: conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

#### Done Criteria
- [ ] Database connection enables WAL mode
- [ ] Existing functionality unaffected

---

### M3: Add React Error Boundary
**Complexity**: M (Medium) | **Time**: ~30 min
**Files**: `frontend/src/components/ErrorBoundary.tsx` (new), `frontend/src/layouts/Layout.astro`
**Dependencies**: M1 | **Parallel**: No

#### Symbols to Create
```typescript
// frontend/src/components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error): State;
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void;
  render(): React.ReactNode;
}
```

#### Done Criteria
- [ ] Component created and exports correctly
- [ ] Layout.astro wraps content with ErrorBoundary
- [ ] Errors show fallback UI instead of white screen

---

### M4: Add Health Endpoint
**Complexity**: M (Medium) | **Time**: ~30 min
**Files**: `frontend/src/pages/api/health.ts` (new)
**Dependencies**: None | **Parallel**: Yes

#### Symbols to Create
```typescript
// frontend/src/pages/api/health.ts
interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
  timestamp: string;
  checks: { data: { status: string; lastUpdated?: string } };
}
export async function GET(): Promise<Response>;
```

#### Done Criteria
- [ ] GET /api/health returns JSON
- [ ] Returns 200 when healthy, 503 when critical failure

---

### M5: Create .env.example
**Complexity**: S (Small) | **Time**: ~10 min
**Files**: `.env.example` (new)
**Dependencies**: None | **Parallel**: Yes

#### Done Criteria
- [ ] Documents all env vars: FINNHUB_API_KEY, FINTEL_* keys
- [ ] Includes links to get API keys
- [ ] Committed to repo (not in .gitignore)

---

### M6: E2E Validation
**Complexity**: S (Small) | **Time**: ~15 min
**Dependencies**: M1-M5 complete

#### Validation Checklist
- [ ] `cd frontend && npx tsc --noEmit` - Exit 0
- [ ] `cd frontend && npm run build` - Exit 0
- [ ] SQLite WAL mode active
- [ ] `curl localhost:4321/api/health` - Returns OK
- [ ] Error boundary catches thrown errors

---

## Implementation Order

```
GROUP 1 (Parallel):     M1, M2, M4, M5    (~30 min)
GROUP 2 (Sequential):   M3                (~30 min)
GROUP 3 (Final):        M6                (~15 min)
                                    Total: ~1.5 hours
```

---

## External/Destructive Actions

| Action | Risk | Notes |
|--------|------|-------|
| SQLite WAL mode | Low | Backward compatible, creates `-wal` file |
| New API endpoint | None | No existing routes affected |
| Type changes | Low | Only makes types more permissive |

**No destructive actions. All changes are additive.**

---

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

**STATUS: COMPLETE** ✓

### Goal
Replace hardcoded 10-stock watchlist with dynamic S&P 500 constituents.

### Implementation (All Done)

1. ✓ **Universe provider** (`adapters/universe.py`):
   - Fetches S&P 500 constituents from Wikipedia
   - 24-hour cache with fallback to 100-stock static list
   - Sector mapping included

2. ✓ **Config** (`config/schema.py`):
   - `UniverseConfig` with `source`, `max_tickers`, `sectors`
   - Supports "watchlist", "sp500", "sector" modes

3. ✓ **Pipeline** (`orchestration/pipeline.py`):
   - Universe loading integrated
   - Batch fetching with rate limit awareness

**Verification**: Health endpoint shows 501 stocks being analyzed.

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
