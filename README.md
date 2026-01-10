# Fintel

Personal financial intelligence dashboard with AI-driven stock picks, smart money tracking, and market analysis.

## Features

**Stock Analysis**
- AI-scored stock picks (short/medium/long-term) with conviction ratings
- Interactive price charts and fundamentals
- S&P 500 heatmap visualization

**Daily Briefing**
- Economic calendar (NFP, CPI, GDP, FOMC)
- Historical event reactions ("Last NFP beat → SPY +1.2%")
- Pre-market movers and earnings calendar
- News with impact scoring

**Smart Money Tracking**
- Hedge fund 13F holdings
- Unusual options activity
- Congress trades

**Portfolio Analytics**
- Paper trading with P&L tracking
- Portfolio beta and Sharpe ratio
- Sector allocation breakdown
- Tax-loss harvesting opportunities
- Mean reversion alerts

## Tech Stack

- **Backend**: Python (adapters for Yahoo Finance, FRED, Finnhub, SEC)
- **Frontend**: Astro + React + TailwindCSS
- **Data**: SQLite + JSON

## Quick Start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add API keys

# Generate data
python scripts/generate_frontend_data.py

# Frontend
cd frontend && npm install && npm run dev
```

## API Keys

| API | Required | Purpose |
|-----|----------|---------|
| Finnhub | Yes | Earnings calendar, company data |
| FRED | Optional | Economic release calendar |

## License

MIT
