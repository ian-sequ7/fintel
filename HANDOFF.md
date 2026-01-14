# HANDOFF

## Current Work

### Goal
Pipeline performance optimization via batch API methods (January 13, 2026).

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. Current session focused on implementing batch optimization to reduce pipeline runtime.

### Session Summary (Jan 13, 2026) - BATCH OPTIMIZATION COMPLETE

**Batch optimization implemented and verified:**

| File | Change | Status |
|------|--------|--------|
| `adapters/yahoo.py:693-783` | Added `get_fundamentals_batch()` with ThreadPoolExecutor | complete |
| `adapters/yahoo.py:765` | Fixed key mismatch: `avg_volume` → `average_volume` | complete |
| `adapters/yahoo.py:765-779` | Added 11 missing keys for batch/non-batch parity | complete |
| `orchestration/pipeline.py:460-506` | Replaced serial price/fundamental loops with batch calls | complete |

**Changes made:**

1. **`adapters/yahoo.py`** - Added `get_fundamentals_batch()`:
   - Uses `ThreadPoolExecutor(max_workers=20)` for parallel I/O
   - Leverages existing 24h cache for fundamentals
   - Returns `dict[str, dict]` with all fundamental metrics
   - Added 11 keys for parity: analyst_rating, price_target, target_high/low, company_name, current_price, fifty_day_average, two_hundred_day_average, fifty_two_week_high/low, short_percent_of_float

2. **`orchestration/pipeline.py`** - Rewired data fetching:
   - Replaced price loop with `yahoo.get_prices_batch(tickers)`
   - Replaced fundamentals loop with `yahoo.get_fundamentals_batch(tickers)`
   - Converts batch results to Observation objects for downstream compatibility

### Bug Fixes Applied

1. **0 Picks Regression**: `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"` → caused all stocks to fail liquidity filter
2. **Degraded Analyst Scoring**: Batch method was missing 11 keys used by scoring → added all missing keys

### Performance Results

**Batch fetching phase (working correctly):**
```
Batch prices (516 tickers): 10.1s
Batch market caps: +10.4s
Total batch phase: ~20.5s
```

**Full pipeline timing (9:22 total):**
| Phase | Time | Notes |
|-------|------|-------|
| Batch prices + fundamentals | 20.5s | ✅ Optimized |
| 13F SEC fetching | ~60s+ | Serial, HTTP 404 retries |
| Detailed data (21 stocks) | ~60s+ | Serial news/options/insiders |
| Calendar + historical | Variable | Network dependent |
| Backtest calculations | ~30s | CPU bound |

**Bottleneck**: Batch optimization achieved its goal (20s vs 8+ minutes for prices/fundamentals), but total pipeline time dominated by other serial operations not in original scope.

### Current State
- Batch optimization code complete and verified
- All fixes committed and pushed to origin/main
- 21 picks generated (7 short / 7 medium / 7 long)
- Frontend running at localhost:4321 (background task bba31ca)

### Next Steps

| Task | Priority | Notes |
|------|----------|-------|
| Optimize 13F fetching | medium | Parallel SEC requests, better 404 handling |
| Add news/options/insider batch | low | `get_news_batch()`, `get_unusual_options_batch()` |
| Profile remaining bottlenecks | low | Calendar, backtest, historical reactions |

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
| Add 11 missing keys to batch method | complete |
| Full pipeline timing test | complete |

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
| Batch price fetching | ✅ | `get_prices_batch()` ~10s for 516 tickers |
| Batch fundamentals fetching | ✅ | `get_fundamentals_batch()` ~10s for 516 tickers |

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
- `scripts/generate_frontend_data.py` - Frontend data generation

### Scoring Weights

**Timeframe-Specific** (`TimeframeWeights`):
```
SHORT:  Momentum 35% | Quality 15% | Valuation 15% | Growth 15% | Analyst 10% | Smart Money 10%
MEDIUM: Momentum 25% | Quality 20% | Valuation 20% | Growth 15% | Analyst 12% | Smart Money 8%
LONG:   Momentum 10% | Quality 30% | Valuation 30% | Growth 15% | Analyst 10% | Smart Money 5%
```

---

## History

- 2a16859: docs: update HANDOFF with batch optimization completion
- 34c76d8: fix: align batch fundamentals keys with non-batch method (11 keys added)
- 8d75f0e: chore: refresh market data [automated]
- 3866601: feat: batch optimization for prices + fundamentals
- 2dd8548: fix: reload settings after dotenv to fix FRED calendar
- 3f2de89: fix: complete audit fixes + refresh market data
- cfb7313: fix: wire timeframe weights + enforce risk overlay limits
- b8d7336: chore: refresh market data
- 2308d28: chore: refresh market data with corrected historical reactions
- 8d843c7: docs: FRED API setup + economic calendar limitations
- 0f2e513: feat: backtest framework + pipeline improvements

---

## Anti-Patterns

### 1. Adapter Fetches But Doesn't Persist
**Problem:** Finnhub adapter fetched insider transactions but never called `db.upsert_insider_transaction()`
**Resolution:** Added DB persistence in `_fetch_insider_transactions()` like Yahoo does for options
**Prevention:** Compare new adapters to working ones; ensure fetch→persist pattern

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
**Resolution:** Added `reload_settings()` call immediately after `load_dotenv()`
**Prevention:** Always reload settings after loading .env

### 5. Inconsistent Dict Keys Between Batch/Non-Batch Methods
**Problem:** `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"`
**Resolution:** Aligned batch method to use same keys as non-batch
**Prevention:** When adding batch methods, copy return dict structure exactly from non-batch version

### 6. Missing Keys in Batch Method
**Problem:** `get_fundamentals_batch()` was missing 11 keys that non-batch version had (analyst_rating, price_target, etc.)
**Resolution:** Added all missing keys to batch method for scoring parity
**Prevention:** Diff batch vs non-batch return dicts; ensure 1:1 key alignment

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| 2dd8548 | @lru_cache before env loaded | reload_settings() after load_dotenv() |
| 3f2de89 | Fetch but don't persist | Added upsert_insider_transaction() calls |
| cfb7313 | Defined but not used | TimeframeWeights now applied in score_stock() |
| 3866601 | Serial API calls | Use batch methods (get_prices_batch, get_fundamentals_batch) |
| 34c76d8 | Inconsistent dict keys | Align batch/non-batch return structures |
| 34c76d8 | Missing batch keys | Copy all keys from non-batch to batch method |
