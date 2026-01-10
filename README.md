# Fintel

Personal financial intelligence dashboard with institutional-grade stock scoring, smart money tracking, and comprehensive market analysis.

## Overview

Fintel is a full-stack financial analysis platform that combines:
- **Multi-factor stock scoring** using academic research (Jegadeesh-Titman momentum, Novy-Marx quality, Fama-French factors)
- **Smart money tracking** (hedge fund 13F filings, insider Form 4 transactions, Congressional trades)
- **Macro risk analysis** across 8 categories with 22+ economic indicators
- **Daily market briefing** with economic calendar and historical reaction patterns

## Features

### Stock Analysis
- AI-scored stock picks (SHORT/MEDIUM/LONG timeframes) with conviction ratings (0-100)
- Interactive price charts with TradingView Lightweight Charts
- S&P 500 heatmap visualization
- Multi-stock comparison tool
- Thesis generation and risk identification

### Scoring Algorithm
The scoring engine uses 6 weighted factors based on academic research:

| Factor | Weight | Components |
|--------|--------|------------|
| Momentum | 25% | 12-1 month returns (Jegadeesh-Titman), days-to-cover, volume |
| Quality | 25% | Gross profitability (Novy-Marx), asset growth (Fama-French CMA) |
| Valuation | 20% | P/E, P/B, PEG ratios |
| Growth | 15% | Revenue growth, earnings growth |
| Analyst | 10% | Consensus estimates, price targets |
| Smart Money | 5% | 13F changes, insider clusters |

### Smart Money Tracking
- **13F Holdings**: Institutional position changes (new, increased, decreased, sold)
- **Insider Transactions**: SEC Form 4 data with C-suite cluster detection (~7.8% alpha signal)
- **Congress Trades**: Capitol Trades data for politician stock activity
- **Options Flow**: Unusual options activity with volume/OI analysis

### Daily Briefing
- Economic calendar (NFP, CPI, GDP, FOMC) with impact ratings
- Historical event reactions ("Last NFP beat → SPY +1.2%")
- Pre-market movers and earnings calendar
- Impact-scored news from multiple sources

### Macro Risk Analysis
8 risk categories with severity scoring:
1. **Credit & Debt** - High-yield spreads, consumer delinquency
2. **Housing** - Mortgage rates, home prices
3. **Recession Probability** - Yield curve, Sahm rule
4. **Financial Stress** - Fed stress index, VIX, TED spread
5. **Inflation** - CPI, PCE, expectations
6. **Labor Market** - Unemployment, claims, job openings
7. **Market Valuation** - Buffett indicator (market cap/GDP)
8. **Global & Currency** - Dollar index, trade balance

### Portfolio Analytics
- Paper trading with P&L tracking
- Portfolio beta and Sharpe ratio
- Sector allocation breakdown
- Tax-loss harvesting opportunities
- Mean reversion alerts

## Architecture

```
fintel/
├── adapters/           # Data source integrations (11 adapters)
├── config/             # Pydantic configuration & validation
├── db/                 # SQLite database layer
├── domain/             # Business logic & scoring algorithms
├── frontend/           # Astro + React + TailwindCSS UI
├── orchestration/      # Pipeline coordination
├── ports/              # Abstract interface definitions
├── presentation/       # Report generation & exports
├── scripts/            # Data refresh utilities
└── tests/              # Unit & integration tests
```

### Data Sources

| Adapter | Source | Data |
|---------|--------|------|
| `yahoo.py` | Yahoo Finance | Prices, fundamentals, historical data |
| `finnhub.py` | Finnhub API | Earnings, insider transactions, company data |
| `fred.py` | Federal Reserve | 22+ macroeconomic indicators |
| `sec_13f.py` | SEC EDGAR | Institutional 13F holdings |
| `sec.py` | SEC EDGAR | 8-K material event filings |
| `finviz.py` | Finviz | Ticker-specific news |
| `calendar.py` | Finnhub | Economic & earnings calendars |
| `rss.py` | RSS feeds | Market news aggregation |
| `congress.py` | Capitol Trades | Congressional stock trades |
| `universe.py` | Wikipedia | S&P 500 constituents |

### Database

SQLite with 12 main tables:
- `stock_picks` - Recommendations with conviction scores
- `stock_metrics` - Fundamentals (PE, PB, margins, growth)
- `price_history` - Historical OHLCV data
- `macro_indicators` - FRED economic data
- `macro_risks` - Risk assessments
- `news_items` - Aggregated articles
- `pick_performance` - Performance tracking
- `hedge_funds` / `hedge_fund_holdings` - 13F data
- `insider_transactions` - SEC Form 4 data
- `congress_trades` - Congressional trades
- `options_activity` - Unusual options signals

## Tech Stack

**Backend**
- Python 3.11+ with Pydantic validation
- httpx for async HTTP
- SQLite with WAL mode
- BeautifulSoup for web scraping

**Frontend**
- Astro 5 (static site generation)
- React 19 (interactive islands)
- TailwindCSS 4
- TradingView Lightweight Charts
- TypeScript

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys (see below)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/fintel.git
cd fintel

# Backend setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Generate data
python scripts/generate_frontend_data.py

# Frontend setup
cd frontend
npm install
npm run dev
```

### API Keys

| API | Required | Purpose | Get Key |
|-----|----------|---------|---------|
| Finnhub | Yes | Earnings, insider data, company info | [finnhub.io](https://finnhub.io/register) |
| FRED | Optional | 22+ economic indicators | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |

### Configuration

Create `fintel.toml` from the example:

```toml
# Watchlist (default stocks to track)
watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

# Cache settings (minutes/hours)
[cache_ttl]
price_minutes = 1
fundamental_hours = 24
macro_hours = 168
news_minutes = 60

# Rate limits (requests/minute)
[rate_limits]
yahoo = 30
finnhub = 60
fred = 30
```

## Usage

### CLI Commands

```bash
# Generate full report
fintel report

# Get top picks by timeframe
fintel picks --timeframe short -n 5

# Market news
fintel news --category market

# Macro risks
fintel macro

# Pipeline status
fintel status
```

### Scripts

```bash
# Main data generation (runs full pipeline)
python scripts/generate_frontend_data.py

# Refresh historical prices
python scripts/refresh_prices.py

# Update 13F holdings
python scripts/update_13f.py

# Track pick performance
python scripts/update_performance.py
```

### Frontend Development

```bash
cd frontend
npm run dev      # Development server
npm run build    # Production build
npm run preview  # Preview production build
```

## Project Structure Details

### Domain Layer (`domain/`)

Core business logic with pure functions:

- `scoring.py` (~1,900 LOC) - Multi-factor stock scoring
  - `score_stock()` - Main entry point
  - `compute_momentum_score()` - 12-1M momentum, DTC
  - `compute_quality_score()` - Gross profitability, asset growth
  - `compute_smart_money_score()` - 13F + insider clusters
  - `apply_risk_overlay()` - Sector limits, liquidity filters

- `analysis.py` - Thesis generation, risk identification
- `briefing.py` - Daily market briefing
- `news.py` - News aggregation with deduplication
- `smart_money.py` - 13F holdings analysis

### Frontend (`frontend/`)

Astro + React architecture:

**Pages** (`src/pages/`)
- `index.astro` - Dashboard with top picks
- `picks/` - Stock picks explorer
- `smartmoney.astro` - 13F, insider, Congress data
- `macro.astro` - Macro risks dashboard
- `briefing.astro` - Daily calendar
- `portfolio.astro` - Paper trading
- `heatmap.astro` - S&P 500 visualization

**Components** (`src/components/`)
- Interactive: `PriceChart`, `HeatMap`, `PaperTradeForm`
- Cards: `PickCard`, `NewsCard`, `RiskCard`, `SmartMoneyCard`
- UI: `ConvictionBar`, `Badge`, `MetricCard`

### Orchestration (`orchestration/`)

Pipeline coordination:

```python
from orchestration import Pipeline

pipeline = Pipeline()
report = pipeline.run_pipeline(
    watchlist=["AAPL", "MSFT"],
    dry_run=False
)
```

## Scoring Methodology

### Timeframe-Specific Weights

Different timeframes emphasize different factors:

| Factor | SHORT | MEDIUM | LONG |
|--------|-------|--------|------|
| Momentum | 35% | 25% | 10% |
| Quality | 15% | 20% | 30% |
| Valuation | 15% | 20% | 30% |
| Growth | 15% | 15% | 15% |
| Analyst | 10% | 12% | 10% |
| Smart Money | 10% | 8% | 5% |

### Risk Overlay

Picks are filtered through risk controls:
- Maximum 2 picks per sector
- Minimum $10M daily liquidity
- Days-to-cover cap of 10 days
- Exclude stocks with >50% short interest

### Insider Cluster Detection

Based on 2IQ Research findings:
- 3+ C-suite buys in 30-60 days = "cluster buy" signal
- Cluster buys show ~7.8% annual alpha
- Single insider buys are weak signals (often compensation-related)

## Data Refresh

The main pipeline (`generate_frontend_data.py`) performs:

1. **Fetch** - Prices, fundamentals, macro data
2. **Score** - Apply multi-factor algorithm to all stocks
3. **Analyze** - Generate theses, identify risks
4. **Aggregate** - Deduplicate and score news
5. **Export** - Write to `frontend/src/data/report.json`

Recommended refresh schedule:
- Prices: Every 1-5 minutes during market hours
- Fundamentals: Daily after market close
- Macro indicators: Weekly
- 13F holdings: After SEC filing deadlines (45 days post-quarter)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Jegadeesh & Titman](https://www.jstor.org/stable/2329053) - Momentum research (12-1 month effect)
- [Novy-Marx](https://www.nber.org/papers/w15940) - Gross profitability factor
- [Fama & French](https://www.sciencedirect.com/science/article/abs/pii/S0304405X14002323) - Five-factor model (CMA)
- [2IQ Research](https://www.2iqresearch.com/blog/what-is-cluster-buying-and-why-is-it-such-a-powerful-insider-signal) - Insider cluster buying
- [Hong et al. (NBER)](https://www.nber.org/papers/w21166) - Days-to-cover signal
