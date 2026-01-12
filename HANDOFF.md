# HANDOFF

## Current Work

### Goal
Economic calendar improvements and documentation updates (January 2026).

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
| **Insider transactions** | ✅ DONE | Pipeline fully wired: Finnhub → fetch → transform → score |
| **Expanded universe** | ✅ DONE | S&P 500 + Dow 30 + NASDAQ-100 (516 unique tickers) |
| **UI Navigation redesign** | ✅ DONE | Grouped dropdowns: Markets | Analysis | My Stocks |
| **Backtest validation** | ✅ DONE | +15% alpha (medium), +5% (short), +4% (long) |
| **Performance page** | ✅ DONE | Frontend page at `/performance` with backtest results |
| **Economic calendar docs** | ✅ DONE | Clarified tracked events, FRED API key requirement |

**Remaining Work**:

| Task | Status | Notes |
|------|--------|-------|
| IV skew integration | not started | Requires new options adapter |
| Earnings revision tracking | not started | Needs IBES/FactSet integration |

### UI Redesign (Completed Jan 2026)

**Problem:** 9 flat navigation tabs were cramped on desktop and unusable on tablets.

**Solution:** Grouped dropdown navigation (Bloomberg/MarketWatch style):
```
Before: Overview | Briefing | Picks | Heat Map | Smart Money | Macro | News | Watchlist | Portfolio
After:  Markets ▾ | Analysis ▾ | My Stocks ▾
```

**Groupings:**
- **Markets**: Overview, Heat Map, Stock Picks
- **Analysis**: Daily Briefing, Smart Money, Macro Indicators, Market News
- **My Stocks**: Watchlist, Portfolio

**Files modified:**
- `frontend/src/components/sections/Header.astro` - Complete rewrite:
  - Replaced flat `navItems` array with grouped `navGroups: NavGroup[]`
  - Added hover-to-open dropdowns (CSS `group-hover:visible`)
  - Added collapsible accordion groups for mobile
  - Red underline on active group, red left-border on active item in dropdown
  - Proper ARIA attributes for accessibility

**Styling audit confirmed existing standards are professional:**
- Typography: Libre Baskerville (serif headlines), Source Sans 3 (body), DM Mono (data)
- Colors: Monochrome base, red accent (`#cc0000`), green/red for price changes only
- Dark mode: CSS custom properties with `[data-theme="dark"]`
- Config: `frontend/src/styles/global.css` (Tailwind 4.x @theme)

### Insider Transactions (Completed)

**Implementation summary:**
1. Finnhub provides `/stock/insider-transactions` on free tier
2. Extended `FinnhubAdapter` with `get_insider_transactions(ticker, days=90)`
3. Added `InsiderTransaction` DB model and table
4. Created converters: `observations_to_insider_transactions()`, `db_transactions_to_insider()`
5. Scoring logic `_score_insider_cluster()` detects 3+ C-suite buys in 60 days
6. **Pipeline fully wired** - insider data flows from fetch → transform → score

**Pipeline integration (`orchestration/pipeline.py`):**
- `DataFetcher.fetch_all()` fetches insider txns for top 35 tickers
- `Analyzer.analyze_stocks_v2()` accepts `insider_transactions` parameter
- `Pipeline.run()` converts observations via `observations_to_insider_transactions()`
- `InsiderTransaction` dataclass has `ticker` field for per-stock filtering

### Backtest Framework (Completed Jan 2026)

**Implementation:**
- `domain/backtest.py` - Core backtest engine with point-in-time simulation
- CLI command: `fintel backtest --start DATE --end DATE --timeframe TF`
- Monthly rebalancing, equal-weight picks, SPY benchmark comparison

**Validation Results (Aug 2024 - Dec 2025):**

| Timeframe | Alpha | Hit Rate | Sharpe | Max DD |
|-----------|-------|----------|--------|--------|
| SHORT     | +5.0% | 54.8%    | 1.04   | 13.5%  |
| MEDIUM    | +15.0%| 56.9%    | 1.41   | 12.7%  |
| LONG      | +4.0% | 54.0%    | 1.07   | 13.9%  |

**Conclusion:** MEDIUM timeframe performs best (+15% alpha), consistent with academic research on 3-12 month momentum horizon.

**Known Limitations:**
- Uses current fundamentals (lookahead bias for value/quality factors)
- No transaction costs modeled
- Survivorship bias if universe changed over time

### Performance Page (Completed Jan 2026)

**Implementation:**
- `frontend/src/pages/performance.astro` - Full-featured performance dashboard
- `frontend/src/data/report.ts` - Added `getBacktestData()`, `getBacktestByTimeframe()`, `getBestBacktestTimeframe()`
- `scripts/generate_frontend_data.py` - Added `generate_backtest_data()`, `backtest_result_to_frontend()`

**Features:**
- Best performer highlight with alpha display
- Summary metric cards (Total Return, Alpha, Sharpe, Hit Rate)
- Timeframe comparison table with all metrics
- Best/worst trades by timeframe
- Monthly returns table with top/worst performers
- Methodology & limitations disclosure

**Navigation:** Added under Analysis dropdown (`Analysis > Performance`)

### Key Files

**Scoring Algorithm** (Updated Jan 2026):
- `domain/scoring.py` (~1900 lines) - Core scoring with institutional-grade signals
  - `score_stock()` - Main entry point (accepts `institutional_holdings`, `insider_transactions`)
  - `compute_momentum_score()` - 12-1M momentum, DTC, volume
  - `compute_quality_score()` - Gross profitability, asset growth, margins
  - `compute_smart_money_score()` - 13F holdings + insider clusters
  - `_score_13f_holdings()` - Fund reputation-weighted institutional activity
  - `_score_insider_cluster()` - C-suite cluster detection (returns 0.85 for 3+ buys in 60 days)
  - `InstitutionalHolding`, `InsiderTransaction` - Input dataclasses

**Frontend Navigation:**
- `frontend/src/components/sections/Header.astro` - Grouped dropdown navigation
- `frontend/src/styles/global.css` - CNN Business-style theme (Tailwind 4.x)

**Backtesting:**
- `domain/backtest.py` - Backtest engine with `run_backtest()`, `BacktestResult`
- `cli.py` - CLI command `fintel backtest` for running backtests

**Adapters**:
- `adapters/finnhub.py` - Quote, profile, insider transactions (Form 4 data)
- `adapters/sec_13f.py` - 13F institutional holdings
- `adapters/universe.py` - S&P 500 + Dow + NASDAQ-100 combined universe

### Scoring Weights

**Base weights** (in `domain/scoring.py`):
```
Momentum: 25% | Quality: 25% | Valuation: 20% | Growth: 15% | Analyst: 10% | Smart Money: 5%
```

**Timeframe-Specific** (`TimeframeWeights`):
```
SHORT:  Momentum 35% | Quality 15% | Valuation 15% | Growth 15% | Analyst 10% | Smart Money 10%
MEDIUM: Momentum 25% | Quality 20% | Valuation 20% | Growth 15% | Analyst 12% | Smart Money 8%
LONG:   Momentum 10% | Quality 30% | Valuation 30% | Growth 15% | Analyst 10% | Smart Money 5%
```

---

### Economic Calendar (January 2026)

**Issue:** Calendar showed "No economic events scheduled" even when events existed (e.g., CB Employment Trends Index, FOMC speeches, Treasury auctions on Jan 12, 2026).

**Root Cause Analysis:**
1. **FRED API key not configured** - `get_fred_release_dates()` returns empty list without API key
2. **Limited event coverage** - Only tracks 7 major FRED releases (NFP, CPI, GDP, PCE, Retail, Housing, PMI)
3. **Missing event types**:
   - CB Employment Trends Index (Conference Board - no free API)
   - FOMC Member Speeches (Fed calendar - manual only, frequently change)
   - Treasury Auctions (Treasury operations, not economic data releases)

**Resolution:**
1. **Documentation updates**:
   - Added comprehensive docstring to `adapters/calendar.py` listing tracked vs. not-tracked events
   - Updated README.md to clarify calendar limitations and FRED API key requirement
   - Enhanced `get_fred_release_dates()` docstring with setup instructions

2. **Improved error messaging**:
   - FRED API key warning now includes setup instructions
   - `get_hybrid_calendar()` logs clear warning when both FRED and Finnhub fail
   - Error message explicitly states which events require premium sources

3. **Files modified**:
   - `adapters/calendar.py`: Enhanced documentation, improved logging
   - `README.md`: Added economic calendar limitations note, FRED API key setup section

**Expected Behavior:**
- With FRED API key configured: Shows 7 major releases (NFP, CPI, GDP, PCE, Retail, Housing, PMI)
- Without FRED API key: Empty calendar with clear error message explaining setup
- Events like CB Employment Trends, Fed speeches, Treasury auctions: Not tracked (requires premium APIs)

---

## History

- (uncommitted): docs: clarify economic calendar tracked events and FRED API requirement
- 00f445f: docs: add README and .env.example
- e0d7451: chore: refresh market data with historical reactions [skip ci]
- d32433d: feat: Phase 3-4 historical comparison + portfolio analytics
- f7a38b7: fix: integrate SEC 13F adapter for hedge fund holdings
- e656cb6: fix: pass indices field in heatmap stock conversion
- (uncommitted): Institutional-grade scoring rebuild - momentum 12-1M, gross profitability, DTC, 13F scoring
- (uncommitted): Insider transactions via Finnhub - Form 4 data, cluster detection, pipeline wiring
- (uncommitted): UI navigation redesign - grouped dropdowns (Markets | Analysis | My Stocks)
- (uncommitted): Backtest framework - validates +15% alpha for medium timeframe picks

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

### 4. Flat Navigation Doesn't Scale
**Problem:** 9 flat tabs in header became cramped and unusable as features grew
**Resolution:** Grouped dropdown navigation (Markets | Analysis | My Stocks)
**Prevention:** Plan navigation hierarchy upfront; use dropdowns for >5 top-level items

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| (scoring) | Data fetched not used | Integrate into scoring or mark display-only |
| (scoring) | 1M momentum only | Use 12-1 month per Jegadeesh-Titman |
| (briefing) | Finnhub calendar 403 | Check API tier before assuming free |
| (adapters) | New adapter before checking existing | Check Finnhub/Yahoo first |
| (nav) | Flat tabs don't scale | Use grouped dropdowns for >5 items |
