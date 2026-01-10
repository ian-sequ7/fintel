# HANDOFF

## Current Work

### Goal
Improve Fintel's stock picking methodology to institutional-grade standards based on quant audit findings.

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. A quant audit revealed gaps between current implementation and institutional standards.

### Implementation Status

**Completed (January 2026)**:

| Task | Status | Details |
|------|--------|---------|
| Multi-period momentum (12-1M) | ✅ DONE | `_score_momentum_12_1()` with Jegadeesh-Titman 50% weight |
| Gross profitability | ✅ DONE | `_score_gross_profitability()` Novy-Marx factor 35% of quality |
| Asset growth (negative) | ✅ DONE | `_score_asset_growth()` Fama-French CMA 15% of quality |
| Days-to-Cover signal | ✅ DONE | `_score_days_to_cover()` 15% of momentum score |
| 13F ownership changes | ✅ DONE | `_score_13f_holdings()` with fund reputation weights |
| Sector concentration limits | ✅ DONE | `RiskOverlayConfig.max_picks_per_sector=2` |
| Liquidity filter | ✅ DONE | `RiskOverlayConfig.min_daily_liquidity=$10M` |
| DTC risk cap | ✅ DONE | `RiskOverlayConfig.max_days_to_cover=10` |
| Timeframe-specific weights | ✅ DONE | `TimeframeWeights.for_short/medium/long()` |
| Signal attribution output | ✅ DONE | `PickSummary`, `format_pick_with_attribution()` |
| Smart money 13F scoring | ✅ DONE | `InstitutionalHolding`, `FUND_REPUTATION`, `holdings_to_institutional()` |
| **Insider transactions** | ✅ DONE | Extended FinnhubAdapter with `/stock/insider-transactions` (free tier) |

**Remaining Work**:

| Task | Status | Notes |
|------|--------|-------|
| IV skew integration | not started | Requires new options adapter |
| Earnings revision tracking | not started | Needs IBES/FactSet integration |
| Backtest validation | not started | Validate new weights historically |

### Insider Transactions (Completed)

**Implementation summary:**
1. Finnhub provides `/stock/insider-transactions` on free tier
2. Extended `FinnhubAdapter` with `get_insider_transactions(ticker, days=90)`
3. Added `InsiderTransaction` DB model and table
4. Created converters: `observations_to_insider_transactions()`, `db_transactions_to_insider()`
5. Scoring logic `_score_insider_cluster()` now has data source

**Files modified:**
- `adapters/finnhub.py` - Added `_fetch_insider_transactions()`, `get_insider_transactions()`
- `db/models.py` - Added `InsiderTransaction` dataclass
- `db/database.py` - Added `insider_transactions` table + CRUD methods
- `domain/scoring.py` - Added converter functions for pipeline integration

### Scoring Weights (Implemented)

**New weights** (in `domain/scoring.py`):
```
Momentum: 25% | Quality: 25% | Valuation: 20% | Growth: 15% | Analyst: 10% | Smart Money: 5%
```

**Timeframe-Specific** (`TimeframeWeights`):
```
SHORT:  Momentum 35% | Quality 15% | Valuation 15% | Growth 15% | Analyst 10% | Smart Money 10%
MEDIUM: Momentum 25% | Quality 20% | Valuation 20% | Growth 15% | Analyst 12% | Smart Money 8%
LONG:   Momentum 10% | Quality 30% | Valuation 30% | Growth 15% | Analyst 10% | Smart Money 5%
```

### Key Files

**Scoring Algorithm** (Updated Jan 2026):
- `domain/scoring.py` (~1900 lines) - Core scoring with institutional-grade signals
  - `score_stock()` - Main entry point (accepts `institutional_holdings`, `insider_transactions`)
  - `compute_momentum_score()` - 12-1M momentum, DTC, volume
  - `compute_quality_score()` - Gross profitability, asset growth, margins
  - `compute_smart_money_score()` - 13F holdings + insider clusters
  - `_score_13f_holdings()` - Fund reputation-weighted institutional activity
  - `_score_insider_cluster()` - C-suite cluster detection
  - `apply_risk_overlay()` - Sector limits, liquidity, DTC caps
  - `holdings_to_institutional()` - Convert DB holdings to scoring format
  - `observations_to_insider_transactions()` - Convert Finnhub data to scoring format
  - `db_transactions_to_insider()` - Convert DB transactions to scoring format
  - `InstitutionalHolding`, `InsiderTransaction` - Input dataclasses
  - `FUND_REPUTATION` - Berkshire 1.0, Bridgewater 0.9, etc.

- `domain/analysis_types.py` - `StockMetrics` with computed properties:
  - `momentum_12_1`, `days_to_cover`, `gross_profitability`

**Adapters**:
- `adapters/finnhub.py` - Quote, profile, and **insider transactions** (Form 4 data)
  - `get_insider_transactions(ticker, days=90)` - Fetches from Finnhub free tier
  - `FinnhubInsiderTransaction` dataclass for typed response
- `adapters/sec_13f.py` - 13F institutional holdings
- `adapters/sec.py` - 8-K material event filings

**Database**:
- `db/models.py` - `InsiderTransaction` model for SEC Form 4 data
- `db/database.py` - `insider_transactions` table with cluster detection methods:
  - `get_insider_transactions(ticker, days)` - General query
  - `get_c_suite_buys(ticker, days)` - Cluster detection filter

### Research Sources

- [Insider Cluster Buying (2IQ Research)](https://www.2iqresearch.com/blog/what-is-cluster-buying-and-why-is-it-such-a-powerful-insider-signal)
- [Days to Cover (NBER)](https://www.nber.org/system/files/working_papers/w21166/w21166.pdf)

---

## History

- 00f445f: docs: add README and .env.example
- e0d7451: chore: refresh market data with historical reactions [skip ci]
- d32433d: feat: Phase 3-4 historical comparison + portfolio analytics
- f7a38b7: fix: integrate SEC 13F adapter for hedge fund holdings
- (uncommitted): Institutional-grade scoring rebuild - momentum 12-1M, gross profitability, DTC, 13F scoring, risk overlay, timeframe weights
- (uncommitted): Insider transactions via Finnhub - Form 4 data, cluster detection, DB table

---

## Anti-Patterns

### 1. Data Fetched But Not Used
**Problem:** Adapters fetch data (13F, Congress, options) that is displayed but not used in scoring
**Resolution:** Integrated 13F changes into scoring; removed Congress/Reddit from scoring consideration
**Prevention:** Define upfront whether data sources are display-only or scoring-eligible

### 2. Single-Period Momentum
**Problem:** Only 1-month momentum when academic evidence supports 12-1 month (skip recent month reversal)
**Resolution:** Added `_score_momentum_12_1()` with 50% weight in momentum scoring
**Prevention:** Research academic evidence before implementing quant signals

### 3. Check Finnhub First
**Problem:** Created new adapters when existing ones may have the endpoint
**Prevention:** Before creating new adapter, check if Finnhub/Yahoo already provides the data

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| (scoring) | Data fetched not used | Integrate into scoring or mark display-only |
| (scoring) | 1M momentum only | Use 12-1 month per Jegadeesh-Titman |
| (briefing) | Finnhub calendar 403 | Check API tier before assuming free |
| (adapters) | New adapter before checking existing | Check Finnhub/Yahoo first |
