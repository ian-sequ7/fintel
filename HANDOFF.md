# HANDOFF

## Current Work

### Goal
Pipeline performance optimization (January 13, 2026).

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. This session focused on comprehensive pipeline parallelization to reduce runtime.

### Session Summary - PIPELINE OPTIMIZATION COMPLETE

**Performance progression:**
| Optimization | Time | Cumulative Savings |
|--------------|------|-------------------|
| Baseline | 9:22 | - |
| + Batch prices/fundamentals | 9:22 | (internal: 8min→20s) |
| + Parallel 13F fetching | 7:20 | -2 min |
| + Parallel news/options/insider | 6:03 | -1 min |
| + Parallel backtests + batch stock details | **3:55** | -2 min |

**Total improvement: 9:22 → 3:55 (~58% faster)**

### Changes Made

**1. Batch methods in `adapters/yahoo.py`:**
- `get_fundamentals_batch()` with ThreadPoolExecutor (20 workers)
- Fixed key mismatch: `avg_volume` → `average_volume`
- Added 11 missing keys for batch/non-batch parity

**2. Parallel 13F in `adapters/sec_13f.py`:**
- `_fetch_single_fund()` helper for parallel execution
- ThreadPoolExecutor with 6 workers
- Also parallelized `refresh_all_funds()`

**3. Parallel fetching in `orchestration/pipeline.py`:**
- Added `_fetch_sources_parallel()` helper method
- News: 10 tickers in parallel
- Options: 10 tickers in parallel
- Insider transactions: 35 tickers with 5 workers (respects Finnhub rate limits)

**4. Optimizations in `scripts/generate_frontend_data.py`:**
- Backtests: 3 timeframes run in parallel with ThreadPoolExecutor
- Stock details: Uses batch methods instead of serial loop with 0.2s delay
- Fixed backtest display format (was showing -1000% instead of -10%)

### Bug Fixes Applied

1. **0 Picks Regression**: `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"` → all stocks failed liquidity filter
2. **Missing Scoring Keys**: Batch method missing 11 keys (analyst_rating, price_target, etc.) → degraded analyst scoring
3. **Backtest Display**: Python `:.1%` format multiplied already-percentage values by 100 → showed -1094% instead of -10.9%

### Current State
- All parallelization complete and verified
- Pipeline time reduced from 9:22 to 3:55 (~58% faster)
- 18 picks generated
- Frontend running at localhost:4321

### Remaining Bottlenecks (if further optimization needed)

| Component | Time | Notes |
|-----------|------|-------|
| Backtests (3 parallel) | ~2 min | Scoring calculations are CPU-bound |
| Batch prices + market caps | ~25s | Already parallelized |
| Briefing generation | ~25s | Calendar + historical reactions |
| Pipeline analysis | ~30s | Transformer + scorer |

### Next Steps

| Task | Priority | Notes |
|------|----------|-------|
| Profile backtest scoring | low | Main remaining bottleneck |
| Async/await refactor | low | Could replace threading for more parallelism |
| Cache scoring calculations | low | Avoid recomputing for same ticker/date |

### Subtasks Status

| Task | Status |
|------|--------|
| Batch prices/fundamentals (yahoo.py) | complete |
| Parallel 13F fetching (sec_13f.py) | complete |
| Parallel news/options/insider (pipeline.py) | complete |
| Parallel backtests (generate_frontend_data.py) | complete |
| Batch stock details (generate_frontend_data.py) | complete |
| Fix backtest display format | complete |

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
| Batch price fetching | ✅ | `get_prices_batch()` ~10s for 516 tickers |
| Batch fundamentals fetching | ✅ | `get_fundamentals_batch()` ~10s for 516 tickers |
| Parallel 13F fetching | ✅ | 6 workers, ~10s for 15 funds |
| Parallel news/options/insider | ✅ | 10/10/5 workers respectively |
| Parallel backtests | ✅ | 3 timeframes concurrent |
| Batch stock details | ✅ | Removed 0.2s serial delay |

### Key Files

**Adapters**:
- `adapters/yahoo.py` - Prices, fundamentals, options (with batch methods)
- `adapters/sec_13f.py` - 13F institutional holdings (parallel fetching)
- `adapters/finnhub.py` - Quote, profile, insider transactions

**Pipeline**:
- `orchestration/pipeline.py` - Main pipeline with `_fetch_sources_parallel()`
- `scripts/generate_frontend_data.py` - Frontend data generation with parallel backtests

### Scoring Weights

**Timeframe-Specific** (`TimeframeWeights`):
```
SHORT:  Momentum 35% | Quality 15% | Valuation 15% | Growth 15% | Analyst 10% | Smart Money 10%
MEDIUM: Momentum 25% | Quality 20% | Valuation 20% | Growth 15% | Analyst 12% | Smart Money 8%
LONG:   Momentum 10% | Quality 30% | Valuation 30% | Growth 15% | Analyst 10% | Smart Money 5%
```

---

## History

- cce71ec: perf: parallelize backtests + batch stock details
- 8262e71: fix: correct backtest display format (was -1000% instead of -10%)
- 1ff305d: perf: parallelize news, options, and insider fetching
- d1a01a3: perf: parallelize 13F hedge fund fetching
- 34c76d8: fix: align batch fundamentals keys with non-batch method
- 3866601: feat: batch optimization for prices + fundamentals
- 2dd8548: fix: reload settings after dotenv to fix FRED calendar
- 3f2de89: fix: complete audit fixes + refresh market data
- cfb7313: fix: wire timeframe weights + enforce risk overlay limits

---

## Anti-Patterns

### 1. Serial API Calls (Performance)
**Problem:** Pipeline made 260+ serial API calls taking 150-300s
**Resolution:** Added batch methods and ThreadPoolExecutor parallelization
**Prevention:** Profile pipeline; use batch methods for O(n) operations

### 2. Inconsistent Dict Keys Between Batch/Non-Batch Methods
**Problem:** `get_fundamentals_batch()` returned `"avg_volume"` but transformer expected `"average_volume"`
**Resolution:** Aligned batch method to use same keys as non-batch
**Prevention:** When adding batch methods, copy return dict structure exactly from non-batch version

### 3. Missing Keys in Batch Method
**Problem:** `get_fundamentals_batch()` missing 11 keys that non-batch version had
**Resolution:** Added all missing keys to batch method for scoring parity
**Prevention:** Diff batch vs non-batch return dicts; ensure 1:1 key alignment

### 4. Python Percent Format on Already-Percent Values
**Problem:** Using `:.1%` format on values like -10.9 gave -1090.0% (multiplies by 100)
**Resolution:** Changed to `:.1f}%` format (no auto-multiplication)
**Prevention:** Use `:.1f}%` for values already in percentage form; `:.1%` only for decimals (0.109)

### 5. Serial Loop with Hardcoded Delay
**Problem:** `fetch_stock_details()` had `time.sleep(0.2)` per ticker in serial loop
**Resolution:** Replaced with batch methods that handle rate limiting internally
**Prevention:** Use batch methods; don't add artificial delays when parallelization available

### 6. @lru_cache Before Environment Loaded
**Problem:** `get_config()` cached before `load_dotenv()` ran due to import chain
**Resolution:** Added `reload_settings()` call immediately after `load_dotenv()`
**Prevention:** Always reload settings after loading .env

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| cce71ec | Serial backtest loop | ThreadPoolExecutor for 3 timeframes |
| cce71ec | Serial stock details with delay | Batch methods (get_fundamentals_batch, get_prices_batch) |
| 8262e71 | :.1% on percentage values | Use :.1f}% instead |
| 1ff305d | Serial news/options/insider loops | _fetch_sources_parallel() helper |
| d1a01a3 | Serial 13F fund fetching | _fetch_single_fund() + ThreadPoolExecutor |
| 34c76d8 | Batch/non-batch key mismatch | Copy exact key structure from non-batch |
| 2dd8548 | @lru_cache before env loaded | reload_settings() after load_dotenv() |
