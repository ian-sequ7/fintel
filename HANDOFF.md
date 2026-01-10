# HANDOFF

## Current Work

### Goal
Daily Market Briefing page (`/briefing`) for Fintel - a Bloomberg-style morning summary with economic calendar, pre-market movers, earnings, and news with impact scoring.

### Context
Fintel is a financial intelligence dashboard with stock picks, smart money tracking, macro indicators, news, and portfolio features. The briefing page provides a morning summary combining multiple data sources.

### Progress

**Phase 1: Core Briefing Infrastructure - COMPLETE**

| Subtask | Status |
|---------|--------|
| Create `adapters/calendar.py` - Finnhub calendar adapter | complete |
| Create `domain/briefing.py` - domain models + generation | complete |
| Update exports in `adapters/__init__.py`, `domain/__init__.py` | complete |
| Update `frontend/src/data/types.ts` - briefing types | complete |
| Create `frontend/src/pages/briefing.astro` | complete |
| Update `Header.astro` - add nav link | complete |
| Update `scripts/generate_frontend_data.py` - pipeline integration | complete |

**Phase 2A: Pre-Market Movers - COMPLETE**

| Subtask | Status |
|---------|--------|
| Add `get_premarket_movers()` to Yahoo adapter | complete |
| Add `PreMarketMover` model to `domain/briefing.py` | complete |
| Update `DailyBriefing` with `premarket_gainers`, `premarket_losers` | complete |
| Update `briefing_to_dict()` serialization | complete |
| Add `PreMarketMover` TypeScript type | complete |
| Update `briefing.astro` with pre-market section | complete |
| Add `to_camel_case()` conversion for frontend compatibility | complete |

**Phase 2B: Enhanced Economic Calendar - COMPLETE**

| Subtask | Status |
|---------|--------|
| Add hybrid calendar approach (FRED + Finnhub earnings) | complete |
| Add `EarningsAnnouncement` model to `domain/briefing.py` | complete |
| Update `DailyBriefing` with `earnings_today`, `earnings_before_open`, `earnings_after_close` | complete |
| Add `EarningsAnnouncement` TypeScript type | complete |
| Update `briefing.astro` with earnings section | complete |
| Add FRED API key support to `config/schema.py` and `config/loader.py` | complete |

**Phase 2C: News Impact Scoring & Tagging - COMPLETE**

| Subtask | Status |
|---------|--------|
| Add `NewsPriority` enum to `domain/briefing.py` | complete |
| Update `BriefingNewsItem` with priority, relevance_score, keywords, tickers | complete |
| Implement scoring in `_observation_to_news()` using existing `domain/news.py` functions | complete |
| Update `briefing_to_dict()` to serialize new fields | complete |
| Add `NewsPriority`, `NewsImpactCategory` TypeScript types | complete |
| Update `briefing.astro` with priority badges (ALERT/HIGH tags) | complete |

**Phase 3: Historical Comparison - COMPLETE**

| Subtask | Status |
|---------|--------|
| Add `SurpriseDirection`, `HistoricalReaction` models to `domain/briefing.py` | complete |
| Add `historical_context` field to `DailyBriefing` model | complete |
| Add `get_historical_event_reactions()` to `CalendarAdapter` | complete |
| Add FRED series history fetching + SPY reaction calculation | complete |
| Update `briefing_to_dict()` serialization | complete |
| Add `SurpriseDirection`, `HistoricalReaction` TypeScript types | complete |
| Add "Past Event Reactions" section to `briefing.astro` | complete |
| Integrate into `generate_frontend_data.py` pipeline | complete |
| Add more event types (Retail, Housing, PMI) | complete |
| Show 5-day reactions alongside 1-day | complete |

**Phase 4: Portfolio Analytics - COMPLETE**

| Subtask | Status |
|---------|--------|
| Add Portfolio Beta calculation (value-weighted) | complete |
| Add Sector Allocation breakdown with visual bars | complete |
| Add Concentration Warnings (>20% position alert) | complete |
| Add Position Duration tracking (days held) | complete |
| Add Tax-Loss Harvesting identifier (negative P&L) | complete |
| Add Holding Period tracking (short-term vs long-term) | complete |
| Add Sharpe Ratio calculation | complete |
| Add Mean Reversion scanner (>10% from 50-day MA) | complete |
| Add "Insights" tab to PortfolioView | complete |

### Key Files Created/Modified

**Backend (Python):**
- `adapters/calendar.py` - Hybrid calendar: FRED release dates + Finnhub earnings + historical reactions
- `adapters/yahoo.py` - Added `get_premarket_movers()` for top gainers/losers
- `domain/briefing.py` - Full domain models: `EconomicEvent`, `PreMarketMover`, `EarningsAnnouncement`, `BriefingNewsItem`, `DailyBriefing`, `NewsPriority`, `SurpriseDirection`, `HistoricalReaction`
- `config/schema.py` - Added `fred` API key field
- `config/loader.py` - Added `FINTEL_FRED_KEY` environment loading
- `scripts/generate_frontend_data.py` - Added `fetch_briefing_data()`, `to_camel_case()`, historical reactions integration

**Frontend (Astro/TS):**
- `frontend/src/pages/briefing.astro` - Full briefing page with all sections including historical context
- `frontend/src/data/types.ts` - Added all briefing types including `NewsPriority`, `NewsImpactCategory`, `SurpriseDirection`, `HistoricalReaction`
- `frontend/src/data/report.ts` - Added `getBriefingData()`, helper functions
- `frontend/src/components/islands/PortfolioView.tsx` - Added Insights tab with full portfolio analytics

### Key Implementation Details

**Pre-Market Movers:**
- Uses Yahoo Finance `screener/predefined/saved` endpoint
- Returns top 10 gainers and top 10 losers
- Fetches company names via batch quotes
- snake_case → camelCase conversion for frontend

**Earnings Calendar:**
- Finnhub FREE tier `/calendar/ipo` and `/calendar/earnings` work (unlike `/calendar/economic` which is PAID)
- Filters to today's earnings
- Splits by timing: BMO (before open), AMC (after close)

**News Impact Scoring:**
- Relevance = (source_credibility × 0.3) + (keyword_score × 0.5) + (has_tickers × 0.2)
- Priority levels: CRITICAL (fed/crash/rate keywords or relevance ≥ 0.8), HIGH (earnings/merger keywords or relevance ≥ 0.6), MEDIUM, LOW
- Display: ALERT badge (red) for critical, HIGH badge (yellow) for high priority

**Historical Comparison:**
- Fetches FRED historical series data (NFP, CPI, GDP, Unemployment, Retail, Housing, PMI) via CSV endpoint (FREE)
- Calculates SPY price reaction using Yahoo Finance historical data (1-day and 5-day)
- Determines surprise direction: beat (actual > forecast by threshold), miss, in-line
- Inverse metrics (CPI, Unemployment): lower is better (beat = actual < forecast)
- Normal metrics (NFP, GDP, Retail): higher is better (beat = actual > forecast)
- Displays "NFP beat → +1.2% (5d: +2.3%)" style cards in briefing
- 6-month lookback for historical data

**Portfolio Analytics (Insights Tab):**
- **Portfolio Beta**: Value-weighted average of stock betas (requires >50% coverage)
- **Sharpe Ratio**: (portfolio return - 5% risk-free) / volatility
- **Sector Allocation**: Visual breakdown with colored progress bars
- **Concentration Warnings**: Alert when any position >20% of portfolio
- **Tax-Loss Harvesting**: Identifies positions with unrealized losses, shows holding period
- **Holding Period Tracking**: Short-term (<1 year) vs long-term (>1 year) classification
- **Mean Reversion Alerts**: Flags positions >10% from 50-day moving average

### Current State

- **Briefing page working** at http://localhost:4321/briefing
- **Pre-market movers** showing 10 gainers + 10 losers with % changes
- **Earnings section** showing 30 earnings today (BMO/AMC split)
- **News with scoring** showing priority badges and relevance keywords
- **Historical context** showing 7 event types with 1-day and 5-day SPY reactions
- **Economic calendar** populated via FRED API (NFP, CPI, GDP, FOMC, etc.)
- **Portfolio Insights tab** with beta, Sharpe, sector allocation, tax-loss harvesting, mean reversion
- Build passes, pipeline generates data successfully

### API Key Status

| API | Status | Notes |
|-----|--------|-------|
| Finnhub | Configured | FREE tier: earnings/IPO work, economic calendar 403 |
| FRED | Uses CSV endpoint | No key needed for historical data |
| Yahoo Finance | No key needed | Pre-market movers + SPY reactions work |

### Next Steps (if continuing)

1. **FRED API integration** - Configure key for economic release dates calendar
2. **Fed speech calendar** - Add upcoming Fed speeches
3. **User preferences** - News category filters, watchlist integration
4. **Enhanced historical context** - Add more event types, average historical reactions

### Bug Fixes During Implementation

**Phase 1:**
1. **Pydantic field name clash** - `date: date = Field(...)` shadowed type. Fixed with `from datetime import date as date_type`
2. **Timezone-aware datetime sorting** - RSS feeds have mixed tz-aware/naive. Fixed with normalizer in sort key
3. **Missing dotenv loading** - Added `python-dotenv` and explicit load

**Phase 2:**
4. **ApiKeysConfig missing `fred` attribute** - Config schema didn't have FRED key. Fixed by adding to `config/schema.py` and `config/loader.py`
5. **Pre-market movers snake_case vs camelCase** - Yahoo adapter returned `company_name`, `change_percent`, etc. but frontend expected camelCase. Fixed with `to_camel_case()` conversion function

---

## History

- e69c339: chore: refresh market data [skip ci]
- f7a38b7: fix: integrate SEC 13F adapter for hedge fund holdings
- 5ea1816: feat: Phase 4 - Add pagination support to pipeline and presentation layer
- 565a821: feat: Phase 3 - Expanded data sources

---

## Anti-Patterns

### 1. Finnhub Economic Calendar Free Tier Assumption
**Problem:** Assumed Finnhub economic calendar was free (docs say "free" but `/calendar/economic` requires paid plan)
**Symptom:** HTTP 403 Forbidden
**Resolution:** Graceful degradation to news-only; use earnings calendar (FREE) instead
**Prevention:** Always test API endpoints; check pricing for endpoint-specific restrictions

### 2. Pydantic Field Name Shadowing Type
**Problem:** `date: date = Field(...)` shadows the type with the field name
**Symptom:** `PydanticUserError: Error when building FieldInfo`
**Resolution:** Import as alias: `from datetime import date as date_type`

### 3. Config Schema Mismatch
**Problem:** Added new API key to adapter but not to config schema
**Symptom:** `AttributeError: 'ApiKeysConfig' object has no attribute 'fred'`
**Resolution:** Add field to both `config/schema.py` (Pydantic model) and `config/loader.py` (env loading)

### 4. Backend/Frontend Case Convention Mismatch
**Problem:** Python adapters return snake_case, TypeScript expects camelCase
**Symptom:** Frontend shows undefined values
**Resolution:** Add conversion function at serialization boundary (`to_camel_case()`)

---

## Anti-Pattern Cache

| Hash | Pattern | Resolution |
|------|---------|------------|
| (briefing) | Finnhub calendar 403 | Use earnings calendar (FREE) instead |
| (briefing) | date: date Pydantic | Use `date_type` alias |
| (briefing) | Config schema mismatch | Update both schema.py and loader.py |
| (briefing) | snake_case/camelCase | Conversion at serialization boundary |
