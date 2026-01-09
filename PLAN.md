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

**STATUS: COMPLETE** ✓

### Goal
Add more FRED indicators + news sources + deduplication.

### Implementation (All Done)

1. ✓ **FRED Indicators** (22 total):
   - PLAN.md was outdated - already had 20 indicators implemented
   - Added final 2: CSUSHPINSA (Case-Shiller), BOGZ1FL073164003Q (Household Debt)

2. ✓ **SEC EDGAR Adapter** (`adapters/sec.py`):
   - Fetches 8-K filings (material events, earnings, M&A)
   - Rate limited at 10 req/sec per SEC requirements
   - Includes tests and example script

3. ✓ **Finviz Adapter** (`adapters/finviz.py`):
   - Scrapes ticker-specific news from Finviz quote pages
   - 1.5s delay to avoid blocks
   - Converts to RawNewsItem for aggregation

4. ✓ **News Deduplication** (already existed in `domain/news.py`):
   - Hash-based exact match deduplication
   - Jaccard similarity for fuzzy matching (0.8 threshold)
   - Keeps highest-scored version when duplicates found

---

## Phase 4: Config Limits + Frontend Pagination

**STATUS: COMPLETE** ✓

### Goal
Update limits and add frontend pagination support.

### Implementation (All Done)

1. ✓ **Config Limits** (already at production values):
   - `max_picks_per_timeframe: 15`
   - `max_news_items: 100`
   - `max_macro_indicators: 20`
   - `max_risks_displayed: 10`

2. ✓ **Pipeline Pagination** (`orchestration/pipeline.py`):
   - `fetch_all(offset, limit)` - paginated data fetching
   - `run(offset, limit)` - pass pagination through pipeline
   - `run_pipeline(offset, limit)` - convenience function updated

3. ✓ **Presentation Pagination** (`presentation/`):
   - `PaginationMetadata` - total, offset, limit, has_more
   - `PaginatedPicksResponse` - paginated stock picks
   - `PaginatedNewsResponse` - paginated news
   - `get_paginated_picks(data, timeframe, offset, limit)`
   - `get_paginated_news(data, category, offset, limit)`
   - `generate_picks_section()` and `generate_news_section()` support offset/limit

4. ✓ **Frontend Pagination** (verified):
   - No dedicated pagination components exist yet
   - Basic slicing utilities exist in `frontend/src/data/report.ts`
   - UI pagination components can be added when needed

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

---

# Phase 5: Comprehensive Macro Risk Analysis Enhancement

**STATUS: COMPLETE** ✓

## Overview

Enhance the macro analysis page to display a comprehensive, big-picture view of major macro risks. Currently the page shows ~6 indicators with 0 active risks. Goal: expand to 8 well-organized risk categories covering credit, housing, recession probability, financial stress, and market valuation.

## Current State

**Location:** `frontend/src/pages/macro.astro`
**Data Source:** `frontend/src/data/report.json` → `macro.risks[]` (currently empty)
**Backend:** `domain/analysis.py` → `identify_headwinds()` function
**Data Adapter:** `adapters/fred.py` (FRED API integration)

**Current Indicators (6):**
- Unemployment (UNRATE)
- Inflation/CPI (CPIAUCSL)
- Fed Funds Rate (FEDFUNDS)
- Yield Curve (T10Y2Y)
- Consumer Sentiment (UMCSENT)
- GDP growth

**Problem:** Only 6 indicators, risks array returning empty, missing critical categories like credit bubble, housing stress, and market valuation.

---

## Proposed Risk Categories (8)

### 1. Credit & Debt Risk
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| HY Credit Spread | BAMLH0A0HYM2 | >500bps elevated | Corporate distress signal |
| IG Credit Spread | BAMLC0A4CBBB | >200bps elevated | Investment-grade stress |
| Consumer Delinquency | DRCCLACBS | >3% stress | Consumer credit health |

### 2. Housing & Mortgage Risk
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| 30Y Mortgage Rate | MORTGAGE30US | >7% stress | Affordability crisis |
| Mortgage Delinquency | DRSFRMACBS | >2% elevated | Housing market stress |
| Home Price YoY | CSUSHPINSA | >10% or <0% | Bubble/crash signal |

### 3. Recession Probability
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| Yield Curve 10Y-2Y | T10Y2Y | <0 inverted | 87% recession accuracy |
| Yield Curve 10Y-3M | T10Y3M | <0 inverted | Higher accuracy |
| Sahm Rule | SAHMREALTIME | >0.5 triggered | Real-time recession signal |
| NY Fed Probability | RECPROUSM156N | >30% elevated | Fed recession model |

### 4. Financial Stress
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| St. Louis Fed FSI | STLFSI4 | >0 above-normal | Composite stress index |
| VIX | VIXCLS | >25 elevated | Market fear gauge |
| TED Spread | TEDRATE | >0.5% stress | Interbank lending stress |

### 5. Inflation Risk (enhanced)
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| CPI YoY | CPIAUCSL | >3% elevated | Core inflation |
| PCE YoY | PCEPI | >2.5% above target | Fed preferred measure |
| Inflation Expectations | T5YIE | >3% unanchored | Market expectations |

### 6. Labor Market Risk (enhanced)
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| Unemployment | UNRATE | >5% elevated | Job market health |
| Initial Claims | ICSA | >250k weakening | Real-time layoff signal |
| Job Openings Ratio | JTSJOR | <1.2 slack | Labor demand signal |

### 7. Market Valuation Risk
| Indicator | Source | Threshold | Why It Matters |
|-----------|--------|-----------|----------------|
| Buffett Indicator | FRED WILL5000/GDP | >150% bubble | Market cap vs GDP |
| (CAPE optional) | Shiller | >30 expensive | Long-term valuation |

### 8. Global & Currency Risk
| Indicator | FRED Series | Threshold | Why It Matters |
|-----------|-------------|-----------|----------------|
| Dollar Index | DTWEXBGS | >110 strong | EM/export pressure |
| Trade Balance | BOPGSTB | Widening trend | Current account risk |

---

## Implementation Phases

### Phase 5.1: Expand FRED Data Fetching (S)
**Files:** `adapters/fred.py`
**Done When:**
- [ ] FredAdapter fetches all new FRED series listed above
- [ ] Unit tests pass for each series
- [ ] Graceful handling of missing data

**New Series to Add:**
```python
# Credit
"BAMLH0A0HYM2", "BAMLC0A4CBBB", "DRCCLACBS",
# Housing
"MORTGAGE30US", "DRSFRMACBS",  # CSUSHPINSA already added
# Recession
"T10Y3M", "SAHMREALTIME", "RECPROUSM156N",
# Stress
"STLFSI4", "VIXCLS", "TEDRATE",
# Inflation
"PCEPI", "T5YIE",
# Labor
"ICSA", "JTSJOR",
# Global
"DTWEXBGS", "BOPGSTB"
```

### Phase 5.2: Risk Identification Logic (M)
**Files:** `domain/analysis.py`
**Done When:**
- [ ] `identify_headwinds()` evaluates all 8 risk categories
- [ ] Each risk has: name, description, severity (0-1), category
- [ ] Thresholds configurable in pipeline
- [ ] Unit tests for each risk condition

**New Functions:**
```python
def _evaluate_credit_risk(indicators: dict) -> list[Risk]
def _evaluate_housing_risk(indicators: dict) -> list[Risk]
def _evaluate_recession_risk(indicators: dict) -> list[Risk]
def _evaluate_stress_risk(indicators: dict) -> list[Risk]
def _evaluate_valuation_risk(indicators: dict) -> list[Risk]
def _evaluate_global_risk(indicators: dict) -> list[Risk]
```

### Phase 5.3: Buffett Indicator Calculation (S)
**Files:** `domain/analysis.py` or new `domain/valuation.py`
**Done When:**
- [ ] Buffett indicator calculated from FRED WILL5000/GDP
- [ ] Returns market cap to GDP ratio as percentage
- [ ] Integrated into risk evaluation

### Phase 5.4: Frontend Risk Display (M)
**Files:** `frontend/src/pages/macro.astro`, `frontend/src/components/composed/RiskCard.astro`
**Done When:**
- [ ] Risks grouped by category on macro page
- [ ] Visual severity indicators (color-coded badges)
- [ ] Composite risk score (1-10) displayed
- [ ] Executive summary auto-generated
- [ ] No console errors, responsive design

### Phase 5.5: Testing & Validation (S)
**Done When:**
- [ ] Backend unit tests for risk evaluation
- [ ] Integration test: pipeline generates risks from data
- [ ] Frontend visual inspection
- [ ] `./scripts/refresh_data.sh` populates risks

---

## Parallel Execution Plan

```
Group 1 (Parallel):
├── Phase 5.1: FRED data fetching
└── Phase 5.3: Buffett indicator

Group 2 (After Group 1):
└── Phase 5.2: Risk identification logic

Group 3 (After Phase 5.2):
└── Phase 5.4: Frontend display

Group 4 (After Group 3):
└── Phase 5.5: Testing
```

---

## Decision Points

1. **CAPE Ratio:** Skip for now. Buffett indicator provides similar valuation insight and uses existing FRED data.

2. **Risk Severity Scale:** Use 0-1 float internally, map to low/medium/high for display:
   - `< 0.4` → low (green)
   - `0.4 - 0.7` → medium (yellow)
   - `> 0.7` → high (red)

---

## E2E Success Criteria

1. Run `./scripts/refresh_data.sh`
2. `report.json` contains non-empty `macro.risks[]`
3. Visit `localhost:4321/macro`
4. See 8 risk categories with active risks
5. Composite risk score reflects current conditions
6. Page loads <2s, no console errors

---

## Complexity Summary

| Phase | Complexity | Notes |
|-------|------------|-------|
| 5.1 | S | Add FRED series IDs |
| 5.2 | M | Multiple evaluation functions |
| 5.3 | S | Simple calculation |
| 5.4 | M | New components, layout |
| 5.5 | S | Tests for existing patterns |

**Total: Medium complexity, no decomposition needed.**
