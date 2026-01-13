# HANDOFF

## Current Work

### Goal
Pipeline performance optimization via batch API methods (January 13, 2026).

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. Previous audit resolved 7 issues. Current session focused on implementing batch optimization to reduce pipeline runtime from ~5 minutes to ~1 minute.

### Session Summary (Jan 13, 2026) - BATCH OPTIMIZATION + BUG FIX

**Batch optimization complete and verified:**

| File | Change | Status |
|------|--------|--------|
| `adapters/yahoo.py:693-783` | Added `get_fundamentals_batch()` with ThreadPoolExecutor | complete |
| `adapters/yahoo.py:765` | Fixed key mismatch: `avg_volume` → `average_volume` | complete |
| `orchestration/pipeline.py:460-506` | Replaced serial price/fundamental loops with batch calls | complete |

**Changes made:**

1. **`adapters/yahoo.py`** - Added `get_fundamentals_batch()`:
   - Uses `ThreadPoolExecutor(max_workers=20)` for parallel I/O
   - Leverages existing 24h cache for fundamentals
   - Returns `dict[str, dict]` with all fundamental metrics
   - ~500 tickers in ~15-20 seconds vs ~8+ minutes serial

2. **`orchestration/pipeline.py`** - Rewired data fetching:
   - Replaced price loop (lines 462-468) with `yahoo.get_prices_batch(tickers)`
   - Replaced fundamentals loop (lines 471-478) with `yahoo.get_fundamentals_batch(tickers)`
   - Converts batch results to Observation objects for downstream compatibility
   - Added proper error handling and status logging

### Bug Fix: 0 Picks Regression

**Root cause identified and fixed:**

The batch `get_fundamentals_batch()` returned `"avg_volume"` but the transformer expected `"average_volume"`. This key mismatch caused `volume_avg` to be `None` for all stocks, making ALL stocks fail the liquidity filter ("Volume data unavailable").

**Fix:** Changed line 765 in `adapters/yahoo.py` from `"avg_volume"` to `"average_volume"` to match the non-batch method.

**Before fix:** 0 short / 0 medium / 0 long picks
**After fix:** 3 short / 7 medium / 7 long picks (17 total, 71% avg conviction)

### Verified Performance

```
Batch prices (516 tickers): 10.9s
Batch market caps (516 tickers): +8.3s
Total for full universe: ~19s
```

**Pipeline now generates 17 picks with batch optimization working correctly.**

### Current State
- Batch optimization code complete and verified
- Bug fix applied: `avg_volume` → `average_volume` key alignment
- Changes in: `adapters/yahoo.py`, `orchestration/pipeline.py`
- Ready for commit

### Next Steps

| Task | Priority | Notes |
|------|----------|-------|
| Commit batch optimization + fix | high | Ready to commit |
| Add more batch methods | low | `get_news_batch()`, `get_unusual_options_batch()` |

### Subtasks Status

| Task | Status |
|------|--------|
| Search pipeline for serial API call patterns | complete |
| Identify batch method integration points | complete |
| Add get_fundamentals_batch() to yahoo.py | complete |
| Wire pipeline.py to use batch methods | complete |
| Test pipeline performance improvement | complete |
| Investigate 0 picks regression | complete |
| Fix avg_volume key mismatch | complete |

---

### Implementation Status

**Completed (January 2026)**:

| Task | Status | Details |
|------|--------|---------|
| Multi-period momentum (12-1M) | ✅ | `_score_momentum_12_1()` with Jegadeesh-Titman |
| Gross profitability | ✅ | `_score_gross_profitability()` Novy-Marx factor |
| Asset growth (negative) | ✅ | `_score_asset_growth()` Fama-French CMA |
| Days-to-Cover signal | ✅ | `_score_days_to_cover()` 15% of momentum |
| 13F ownership changes | ✅ | `_score_13f_holdings()` with fund reputation |
| Sector concentration limits | ✅ | `RiskOverlayConfig.max_picks_per_sector=2` |
| Liquidity filter | ✅ | `RiskOverlayConfig.min_daily_liquidity=$10M` |
| DTC risk cap | ✅ | `RiskOverlayConfig.max_days_to_cover=10` |
| Timeframe-specific weights | ✅ | `TimeframeWeights.for_short/medium/long()` |
| Insider transactions | ✅ | Finnhub → fetch → transform → score → persist |
| Expanded universe | ✅ | S&P 500 + Dow 30 + NASDAQ-100 (516 tickers) |
| UI Navigation redesign | ✅ | Grouped dropdowns: Markets \| Analysis \| My Stocks |
| Backtest validation | ✅ | +15% alpha (medium), +5% (short), +4% (long) |
| Performance page | ✅ | Frontend at `/performance` with backtest results |
| Pipeline fixes | ✅ | TimeframeWeights + risk overlay enforced |
| Real-world data audit | ✅ | All 7 issues verified fixed |
| FRED calendar fix | ✅ | reload_settings() after load_dotenv() |
| Batch price fetching | ✅ | `get_prices_batch()` in pipeline |
| Batch fundamentals fetching | ✅ | `get_fundamentals_batch()` added + wired |

### Key Files

**Scoring Algorithm** (`domain/scoring.py` ~1900 lines):
- `score_stock()` - Main entry, uses timeframe-specific weights
- `compute_momentum_score()` - 12-1M momentum, DTC, volume
- `compute_quality_score()` - Gross profitability, asset growth
- `compute_smart_money_score()` - 13F holdings + insider clusters

**Adapters**:
- `adapters/finnhub.py` - Quote, profile, insider transactions (Form 4) + DB persist
- `adapters/yahoo.py` - Prices, fundamentals, options (with batch methods)
- `adapters/sec_13f.py` - 13F institutional holdings
- `adapters/calendar.py` - FRED releases + Finnhub earnings

**Pipeline**:
- `orchestration/pipeline.py` - Main pipeline with risk overlay + batch fetching
- `scripts/generate_frontend_data.py` - Frontend data generation (includes reload_settings fix)

### Scoring Weights

**Timeframe-Specific** (`TimeframeWeights`):
```
SHORT:  Momentum 35% | Quality 15% | Valuation 15% | Growth 15% | Analyst 10% | Smart Money 10%
MEDIUM: Momentum 25% | Quality 20% | Valuation 20% | Growth 15% | Analyst 12% | Smart Money 8%
LONG:   Momentum 10% | Quality 30% | Valuation 30% | Growth 15% | Analyst 10% | Smart Money 5%
```

---

## History

- (uncommitted): feat: batch optimization for prices and fundamentals
- 2dd8548: fix: reload settings after dotenv to fix FRED calendar
- 3f2de89: fix: complete audit fixes + refresh market data
- 98f44e7: fix: wire timeframe weights + enforce risk overlay limits
- b8d7336: chore: refresh market data
- 2308d28: chore: refresh market data with corrected historical reactions
- 8d843c7: docs: FRED API setup + economic calendar limitations
- 0f2e513: feat: backtest framework + pipeline improvements
- ecdd55e: fix: performance page display + navigation improvements

---

## Anti-Patterns

### 1. Adapter Fetches But Doesn't Persist
**Problem:** Finnhub adapter fetched insider transactions but never called `db.upsert_insider_transaction()`
**Resolution:** Added DB persistence in `_fetch_insider_transactions()` like Yahoo does for options
**Prevention:** Compare new adapters to working ones (e.g., Yahoo options); ensure fetch→persist pattern

### 2. Defined But Not Used
**Problem:** `TimeframeWeights` class existed but `score_stocks()` never applied it
**Resolution:** Added recalculation in `score_stock()` after `classify_timeframe()`
**Prevention:** Trace data flow from definition → usage; unit test that weights affect output

### 3. Serial API Calls (Performance)
**Problem:** Pipeline makes 260+ serial API calls taking 150-300s
**Resolution:** Added `get_fundamentals_batch()`, wired pipeline to use batch methods
**Prevention:** Profile pipeline; use batch methods for O(n) operations

### 4. @lru_cache Before Environment Loaded
**Problem:** `get_config()` cached before `load_dotenv()` ran due to import chain
**Resolution:** Added `reload_settings()` call immediately after `load_dotenv()` in generate_frontend_data.py
**Prevention:** Always reload settings after loading .env; or load .env before any project imports

### 5. Data Fetched But Not Used
**Problem:** Adapters fetch data (13F, Congress, options) that is displayed but not used in scoring
**Resolution:** Integrated 13F changes into scoring; removed Congress/Reddit from scoring
**Prevention:** Define upfront whether data sources are display-only or scoring-eligible

### 6. Single-Period Momentum
**Problem:** Only 1-month momentum when academic evidence supports 12-1 month
**Resolution:** Added `_score_momentum_12_1()` with 50% weight in momentum scoring
**Prevention:** Research academic evidence before implementing quant signals

### 7. Flat Navigation Doesn't Scale
**Problem:** 9 flat tabs in header became cramped and unusable
**Resolution:** Grouped dropdown navigation (Markets | Analysis | My Stocks)
**Prevention:** Plan navigation hierarchy upfront; use dropdowns for >5 top-level items

### 8. Isolated Tests Don't Load .env
**Problem:** Running `python3 -c "..."` tests don't load .env, causing API key errors
**Resolution:** Use generate_frontend_data.py which has proper dotenv loading
**Prevention:** Always test via scripts that load .env, or manually load in test code

### 9. Inconsistent Dict Keys Between Batch/Non-Batch Methods
**Problem:** `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"`
**Resolution:** Aligned batch method to use same keys as non-batch: `"avg_volume"` → `"average_volume"`
**Prevention:** When adding batch methods, copy the return dict structure exactly from the non-batch version

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| 2dd8548 | @lru_cache before env loaded | reload_settings() after load_dotenv() |
| 3f2de89 | Fetch but don't persist | Added upsert_insider_transaction() calls |
| 98f44e7 | Defined but not used | TimeframeWeights now applied in score_stock() |
| (scoring) | 1M momentum only | Use 12-1 month per Jegadeesh-Titman |
| (pipeline) | Serial API calls | Use batch methods (yahoo.get_prices_batch, get_fundamentals_batch) |
| (batch) | Inconsistent dict keys | Align batch/non-batch return structures |
