# Fintel Frontend Improvements

Identified on 2025-12-31 via Playwright browser analysis.

## Phase 1: Critical Bugs

- [x] **1.1 Inflation Data Display Bug** (FIXED)
  - Macro page shows "Inflation at 325.031% above Fed target"
  - CPI value (325.03) is an index, not a percentage
  - Fix: Calculate actual YoY inflation rate (~2.7%)
  - Location: `adapters/fred.py`, `domain/analysis.py`

- [x] **1.2 Company Names Missing** (FIXED)
  - Stock pages show ticker as company name (e.g., "GOOGL" instead of "Alphabet Inc.")
  - Fix: Fetch company name from Yahoo fundamentals
  - Location: `adapters/yahoo.py`, `scripts/generate_frontend_data.py`

## Phase 2: Data Quality Issues

- [x] **2.1 Related News Not Linking** (FIXED)
  - Stock pages show "No recent news" despite news existing
  - Fix: Pass source_ticker through news pipeline
  - Location: `domain/news.py`, `orchestration/pipeline.py`, `orchestration/news_aggregator.py`

- [x] **2.2 Irrelevant News in Feed** (FIXED)
  - Non-financial articles appearing (e.g., MarketWatch lifestyle content)
  - Fix: Added IRRELEVANT_KEYWORDS filter
  - Location: `domain/news.py`

- [x] **2.3 News Category Mislabeling** (FIXED)
  - All news labeled "Company" even when it's general market news
  - Fix: Use actual NewsCategory from ScoredNewsItem
  - Location: `scripts/generate_frontend_data.py`

- [x] **2.4 Formulaic Thesis Text** (FIXED)
  - Every thesis reads "Solid [timeframe] opportunity. Strong..."
  - Fix: Varied openings based on conviction level and dominant factor
  - Location: `domain/scoring.py`

## Phase 3: UX Improvements

- [ ] **3.1 Add Search Functionality**
  - Can't search for specific stocks
  - Add search input in header with autocomplete

- [ ] **3.2 Sector Filtering on Picks Page**
  - Add filter chips/dropdown to filter by sector
  - Location: `frontend/src/pages/picks/index.astro`

- [x] **3.3 Missing Stop Loss on Stock Pages** (FIXED)
  - Entry and Target shown, but Stop Loss missing
  - Fix: Calculate stop loss based on conviction level
  - Location: `domain/models.py`, `orchestration/pipeline.py`, `scripts/generate_frontend_data.py`

- [x] **3.4 Narrow Conviction Range** (FIXED)
  - All scores 4-7/10, not differentiating
  - Fix: Applied power transformation to spread scores
  - Location: `domain/scoring.py`

- [x] **3.5 Risk Score Inconsistency** (FIXED)
  - Macro shows "8 out of 10 Elevated Risk" but only 1 high + 1 medium
  - Fix: Use absolute risk thresholds instead of relative
  - Location: `frontend/src/pages/macro.astro`

## Phase 4: Polish/Enhancements

- [ ] **4.1 Add Sparklines to Picks**
  - Mini price charts next to each pick for quick trend visualization

- [ ] **4.2 Comparison View**
  - Allow comparing 2-3 stocks side-by-side

- [ ] **4.3 Portfolio/Watchlist**
  - Let users save stocks (localStorage)

- [ ] **4.4 Market Status Indicator**
  - Show if market is open/closed/pre-market

- [ ] **4.5 Historical Performance Tracking**
  - Show how past picks performed

---

## What's Working Well

- Mobile responsiveness (tested at 375px)
- Dark/light theme toggle
- Price charts with candlesticks
- Daily gains accuracy (fixed)
- Clean card-based design
- Relative timestamps ("5m ago")
- Company names showing correctly
- Inflation displaying as YoY percentage
- Related news linking to stocks
- Stop loss displayed on stock pages
- Varied thesis text
- Better conviction score distribution
