# SPEC: Daily Market Briefing Page

## Intent Crystal

```
surface_request: "Add daily market briefing page with economic calendar, pre-market data, world news"
underlying_need: Quick morning summary of market-moving events before trading hours
success_looks_like: Single page at /briefing showing today's events + market-moving news
constraints: Free data sources only, US-only for v1, user local timezone
```

## Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Timezone | User local (browser) | User in PDT, wants local relevance |
| Scope | US-only | Simplify v1, global events (ECB/BOJ) in future |
| Pre-market movers | Phase 2 | Requires Yahoo adapter extension, not blocking |

## Sharp Problem Gate: PROCEED (23/30)

- **Pain (8/10)**: No "today" view — must check multiple sources for FOMC, jobs, earnings
- **Workarounds (7/10)**: Users check Bloomberg, Yahoo calendar, CNBC separately
- **Demand (8/10)**: "Morning briefing" is standard at every trading desk/fintech

## Architecture

### Data Sources

| Source | Use Case | Status |
|--------|----------|--------|
| Finnhub `/calendar/economic` | Economic events (GDP, CPI, FOMC) | New adapter needed |
| Existing RSS feeds | Market-moving news | Already implemented |
| Yahoo pre-market | Pre-market movers | Phase 2 |

### New Components

```
adapters/calendar.py          # Finnhub economic calendar adapter
domain/briefing.py            # DailyBriefing model + generation logic
frontend/src/pages/briefing.astro  # Briefing page
```

### Schema: EconomicEvent

```python
class EventImpact(str, Enum):
    HIGH = "high"      # FOMC, NFP, CPI - market movers
    MEDIUM = "medium"  # Housing starts, consumer sentiment
    LOW = "low"        # Minor regional data

class EconomicEvent(BaseModel):
    """Economic calendar event from Finnhub."""
    event: str              # "Nonfarm Payrolls", "FOMC Meeting"
    country: str            # "US" (filtered)
    time: datetime          # Release time (UTC, converted to local on frontend)
    impact: EventImpact     # High/Medium/Low
    actual: float | None    # Released value (None if pending)
    forecast: float | None  # Consensus estimate
    previous: float | None  # Prior period value
    unit: str               # "%", "K", "B"
```

Maps directly to Finnhub response — minimal transformation.

### Schema: DailyBriefing

```python
class DailyBriefing(BaseModel):
    """Daily market briefing combining calendar + news."""
    date: date
    generated_at: datetime

    # Economic calendar
    events_today: list[EconomicEvent]      # Today's releases
    events_upcoming: list[EconomicEvent]   # Next 3 days, HIGH impact only
    next_major_event: EconomicEvent | None # Countdown target

    # Market news (from existing RSS)
    market_news: list[NewsItem]            # Top 10 market-moving
    fed_news: list[NewsItem]               # Fed/policy specific
```

## Implementation Phases

### Phase 1: Core Briefing (this PR)
1. `adapters/calendar.py` — Finnhub economic calendar
2. `domain/briefing.py` — DailyBriefing model + `generate_daily_briefing()`
3. `frontend/src/pages/briefing.astro` — Clean layout with sections
4. Pipeline integration — add to daily refresh
5. Header nav — add "Briefing" link

### Phase 2: Enhanced (future)
- Pre-market movers (Yahoo extension)
- News impact scoring/tagging
- Historical comparison ("last NFP beat → SPY +1.2%")
- Earnings calendar integration

## Frontend Layout

```
┌─────────────────────────────────────────────────────────┐
│ Daily Market Briefing                                   │
│ Wednesday, Jan 8, 2025 • Generated 5:45 AM PT          │
├─────────────────────────────────────────────────────────┤
│ ⏱️ NEXT MAJOR EVENT: FOMC Minutes in 2d 4h             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 📅 TODAY'S CALENDAR                                     │
│ ┌─────────┬──────────────────┬────────┬───────────────┐│
│ │ 8:30 AM │ Initial Claims   │ 🔴 HIGH│ Est: 215K     ││
│ │ 10:00AM │ Consumer Sent.   │ 🟡 MED │ Est: 74.0     ││
│ └─────────┴──────────────────┴────────┴───────────────┘│
│                                                         │
│ 📰 MARKET-MOVING NEWS                                   │
│ • Fed officials signal patience on rate cuts            │
│ • China PMI contracts for third month                   │
│ • Tech earnings week: AAPL, MSFT, GOOGL report         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Finnhub API Details

**Endpoint**: `GET https://finnhub.io/api/v1/calendar/economic`

**Parameters**:
- `from`: Start date (YYYY-MM-DD)
- `to`: End date (YYYY-MM-DD)
- `token`: API key

**Response fields**: `event`, `time`, `country`, `impact`, `actual`, `estimate`, `prev`, `unit`

**Rate limit**: 60 req/min (free tier) — single daily call is fine

## Done Criteria

- [ ] `/briefing` page loads with today's economic events
- [ ] Events filtered to US-only
- [ ] Times displayed in user's local timezone
- [ ] HIGH impact events visually highlighted
- [ ] Market news section shows top 10 stories
- [ ] "Next major event" countdown displays correctly
- [ ] Pipeline generates briefing data in daily refresh
- [ ] Header nav includes Briefing link

## Robustness Criteria

- [ ] Graceful fallback if Finnhub API unavailable (show news only)
- [ ] Handle events with null actual/forecast values
- [ ] Cache briefing data (1 hour TTL during market hours)
- [ ] Mobile-responsive layout
