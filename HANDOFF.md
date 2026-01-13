# HANDOFF

## Current Work

### Goal
Full site audit with real-world data validation and pipeline fixes (January 13, 2026).

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. A quant audit revealed gaps between current implementation and institutional standards.

### Session Summary (Jan 13, 2026)

**Completed this session:**
- ✅ TimeframeWeights now recalculates scores per timeframe (commit `3b6ec49`)
- ✅ Risk overlay enforces sector limits, liquidity, DTC caps (commit `3b6ec49`)
- ✅ Insider transaction DB persistence wired in Finnhub adapter
- ✅ Finnhub API key added to `.env`
- ✅ Code quality: Fixed 5 bare except clauses in sec_13f.py, database.py, models.py
- ✅ Full audit verification of all 7 original issues

**Audit Verification Results:**
| Component | Status | Evidence |
|-----------|--------|----------|
| Insider DB persistence | ✅ | `finnhub.py:379-402` persists via `upsert_insider_transaction()` |
| Risk overlay | ✅ | `pipeline.py:1157` - sector=2, liquidity=$10M, DTC=10 |
| Timeframe weights | ✅ | `scoring.py:122-167` - SHORT/MEDIUM/LONG weights applied |
| FRED/calendar | ✅ | ConfigLoader reads key from `.env` |
| Options activity | ✅ | 568 records in DB, flows to frontend |

**Blockers resolved:**
- ✅ `FINTEL_FINNHUB_KEY` added to `.env`

**Remaining:**
- ⚠️ Pipeline takes 150-300s (could be 30-50s with batch methods) - optional optimization
- ⚠️ Frontend data stale since Dec 29, 2025 - needs pipeline run

### Next Steps

1. **Run pipeline** to refresh data
   ```bash
   source .venv/bin/activate && python scripts/generate_frontend_data.py
   ```

2. **Commit all changes** after pipeline success

3. **Optional: Optimize pipeline performance**
   - Use `yahoo.get_prices_batch()` instead of per-ticker calls (8-16x speedup)

### Uncommitted Changes

```
M  HANDOFF.md              (audit results, session update)
M  adapters/finnhub.py     (insider DB persistence)
M  adapters/sec_13f.py     (bare except → except Exception)
M  db/database.py          (bare except → except Exception)
M  db/models.py            (bare except → specific exceptions)
```

### Data Validation Status

| Area | Status | Finding |
|------|--------|---------|
| Stock Prices | ⚠️ STALE | Dec 29 data, 2+ weeks old |
| Economic Calendar | ✅ READY | FRED key configured, will work on next run |
| Macro Indicators | ✅ ACCURATE | Matches real-world sources |
| News Headlines | ✅ CURRENT | Jan 12, 2026 headlines verified |
| Insider Transactions | ✅ FIXED | DB persistence wired, needs API key |
| Options Activity | ✅ WORKING | 568 records in DB |

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
| Insider transactions | ✅ | Finnhub → fetch → transform → score → **persist** |
| Expanded universe | ✅ | S&P 500 + Dow 30 + NASDAQ-100 (516 tickers) |
| UI Navigation redesign | ✅ | Grouped dropdowns: Markets \| Analysis \| My Stocks |
| Backtest validation | ✅ | +15% alpha (medium), +5% (short), +4% (long) |
| Performance page | ✅ | Frontend at `/performance` with backtest results |
| Pipeline fixes | ✅ | TimeframeWeights + risk overlay enforced |
| Real-world data audit | ✅ | Jan 13 audit with findings |

**Remaining Work**:

| Task | Status | Notes |
|------|--------|-------|
| IV skew integration | not started | Requires new options adapter |
| Earnings revision tracking | not started | Needs IBES/FactSet integration |

### Key Files

**Scoring Algorithm** (`domain/scoring.py` ~1900 lines):
- `score_stock()` - Main entry, uses timeframe-specific weights
- `compute_momentum_score()` - 12-1M momentum, DTC, volume
- `compute_quality_score()` - Gross profitability, asset growth
- `compute_smart_money_score()` - 13F holdings + insider clusters

**Adapters**:
- `adapters/finnhub.py` - Quote, profile, insider transactions (Form 4) + **DB persist**
- `adapters/yahoo.py` - Prices, fundamentals, options (with batch methods)
- `adapters/sec_13f.py` - 13F institutional holdings

**Pipeline**:
- `orchestration/pipeline.py` - Main pipeline with risk overlay
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

- (uncommitted): fix: wire insider transaction DB persistence in Finnhub adapter
- 3b6ec49: fix: apply TimeframeWeights and risk overlay in pipeline
- 00f445f: docs: add README and .env.example
- e0d7451: chore: refresh market data with historical reactions
- d32433d: feat: Phase 3-4 historical comparison + portfolio analytics
- f7a38b7: fix: integrate SEC 13F adapter for hedge fund holdings
- e656cb6: fix: pass indices field in heatmap stock conversion

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
**Resolution:** Batch methods exist (`yahoo.get_prices_batch()`) but not used in main pipeline
**Prevention:** Profile pipeline; use batch methods for O(n) operations

### 4. Stale Frontend Data
**Problem:** Frontend shows Dec 29 prices while market is 2+ weeks ahead
**Prevention:** Automate `generate_frontend_data.py` via cron or pre-commit hook

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

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| 3b6ec49 | Defined but not used | TimeframeWeights now applied in score_stock() |
| (uncommit) | Fetch but don't persist | Added upsert_insider_transaction() calls |
| (scoring) | 1M momentum only | Use 12-1 month per Jegadeesh-Titman |
| (pipeline) | Serial API calls | Use batch methods (yahoo.get_prices_batch) |
| (nav) | Flat tabs don't scale | Grouped dropdowns for >5 items |
