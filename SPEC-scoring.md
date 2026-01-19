# SPEC: Enhanced Stock Picking Algorithm

## Overview

Improve the multi-factor stock scoring algorithm to consistently achieve 5-10% alpha over S&P 500 benchmark using only free data sources. Target all-weather performance across bull, bear, and sideways markets with weekly rebalancing.

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Alpha (annualized) | 5-10% vs SPY | Backtest + live tracking |
| Win Rate | ≥55% | Picks that outperform sector |
| Sharpe Ratio | ≥1.0 | Risk-adjusted returns |
| Max Drawdown | ≤20% | Worst peak-to-trough |
| Regime Adaptability | Positive returns in ≥2/3 regimes | Bull/bear/sideways |

## User Parameters

- **Alpha Target**: Moderate (5-10%)
- **Rebalance Frequency**: Weekly
- **Data Budget**: Free only (SEC EDGAR, Yahoo Finance, Finnhub free tier)
- **Market Regime**: All-weather operation

---

## Current State Analysis

### Existing Algorithm (`domain/scoring.py`)

**Current Factor Weights:**
```
valuation:   20%  → PE, PB, PS, EV/EBITDA
growth:      15%  → revenue, earnings, margin expansion
quality:     25%  → ROE, debt/equity, margins
momentum:    25%  → price momentum, RSI, volume
analyst:     10%  → ratings, price targets
smart_money:  5%  → 13F holdings, insider trades
```

**Current Gaps Identified:**

1. **Data Gaps**
   - Form 4 insider transactions: incomplete/404 errors for many CIKs
   - Gross profitability (Novy-Marx): not calculated (uses basic ROE instead)
   - Earnings revisions: not tracked (strong alpha signal)
   - Short interest dynamics: missing days-to-cover trends

2. **Methodological Gaps**
   - No market regime detection (same weights in all conditions)
   - No position sizing optimization (equal weight assumed)
   - No correlation-aware portfolio construction
   - Weak sector rotation logic
   - No catalyst identification (earnings dates, macro events)

3. **Signal Gaps**
   - Options flow not integrated into scoring
   - Congress trades not weighted by recency/conviction
   - No earnings surprise momentum factor

---

## Proposed Algorithm Design

### Factor Model: Academic + Practitioner Hybrid

Based on research of successful quantitative hedge fund strategies (AQR, Two Sigma, Renaissance), implement a hybrid factor model:

```
CORE FACTORS (80% of signal):
├── Quality Factor (30%)
│   ├── Gross Profitability (Novy-Marx)     12%
│   ├── ROE (trailing 12M)                    8%
│   ├── Debt/Equity ratio                     5%
│   └── Margin Stability (3Y std)             5%
│
├── Value Factor (20%)
│   ├── Earnings Yield (E/P)                  8%
│   ├── Book-to-Market                        6%
│   └── Free Cash Flow Yield                  6%
│
├── Momentum Factor (20%)
│   ├── 12-1 Month Price Momentum            10%
│   ├── Earnings Revision Momentum            6%
│   └── Volume-Weighted Momentum              4%
│
└── Low Volatility Factor (10%)
    ├── 252-day Realized Volatility           5%
    └── Beta (vs SPY)                         5%

ALPHA SIGNALS (20% of signal):
├── Smart Money (12%)
│   ├── 13F Institutional Accumulation        4%
│   ├── Insider Cluster Buys (Form 4)         4%
│   └── Congress Trades (recency-weighted)    4%
│
└── Catalyst Awareness (8%)
    ├── Earnings Date Proximity               4%
    └── Sector Momentum (rotation)            4%
```

### Timeframe Differentiation

| Factor | SHORT (1-4 wks) | MEDIUM (1-3 mo) | LONG (3-12 mo) |
|--------|-----------------|-----------------|----------------|
| Quality | 20% | 30% | 35% |
| Value | 10% | 20% | 30% |
| Momentum | 35% | 25% | 15% |
| Low Vol | 10% | 10% | 10% |
| Smart Money | 15% | 10% | 8% |
| Catalyst | 10% | 5% | 2% |

### Market Regime Detection

Implement simple regime classification using free data:

```python
class MarketRegime(Enum):
    BULL = "bull"        # SPY > 200 SMA, VIX < 20
    BEAR = "bear"        # SPY < 200 SMA, VIX > 25
    SIDEWAYS = "sideways" # else
    HIGH_VOL = "high_vol" # VIX > 30 (defensive mode)
```

**Regime-Adjusted Weights:**

| Regime | Quality | Value | Momentum | Low Vol | Smart Money |
|--------|---------|-------|----------|---------|-------------|
| Bull | 25% | 15% | 30% | 10% | 20% |
| Bear | 35% | 25% | 10% | 20% | 10% |
| Sideways | 30% | 20% | 20% | 15% | 15% |
| High Vol | 40% | 20% | 5% | 25% | 10% |

### Position Sizing

Implement fractional Kelly criterion for position sizing:

```python
def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly criterion with 0.25x fraction for safety."""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss  # win/loss ratio
    p = win_rate
    q = 1 - p
    kelly = (b * p - q) / b
    return max(0, kelly * 0.25)  # quarter Kelly for safety
```

**Position Limits:**
- Max single position: 8% of portfolio
- Max sector exposure: 25%
- Min positions: 15 (diversification)
- Max positions: 30 (concentration)

### Risk Overlay (Enhanced)

```python
@dataclass
class RiskFilters:
    min_market_cap: float = 2e9      # $2B minimum
    min_avg_volume: float = 500_000  # 500K shares/day
    max_days_to_cover: float = 5.0   # short squeeze risk
    max_debt_equity: float = 2.0     # leverage limit
    min_current_ratio: float = 1.0   # liquidity
    exclude_penny_stocks: bool = True # price > $5
```

---

## Data Sources & Availability

| Data Point | Source | Status | Notes |
|------------|--------|--------|-------|
| Price/Volume | Yahoo Finance | ✅ Working | Free, reliable |
| Fundamentals | Yahoo Finance | ✅ Working | Quarterly lag |
| 13F Holdings | SEC EDGAR | ✅ Working | 45-day lag |
| Form 4 Insider | SEC EDGAR | ⚠️ Partial | 404s for some CIKs |
| Congress Trades | Quiver Quant | ✅ Working | Via existing adapter |
| Options Flow | Finnhub | ⚠️ Limited | Free tier limits |
| Earnings Dates | Yahoo Finance | ✅ Working | earnings_dates endpoint |
| VIX | Yahoo Finance | ✅ Working | ^VIX ticker |
| Short Interest | Finnhub | ⚠️ Limited | Free tier limits |

---

## Algorithm Pseudocode

```python
def score_stock(ticker: str, timeframe: Timeframe, regime: MarketRegime) -> Score:
    # 1. Fetch all data
    fundamentals = fetch_fundamentals(ticker)
    prices = fetch_price_history(ticker, days=252)
    smart_money = fetch_smart_money_signals(ticker)

    # 2. Compute factor scores (0-100 scale)
    quality = compute_quality_factor(fundamentals)
    value = compute_value_factor(fundamentals)
    momentum = compute_momentum_factor(prices)
    low_vol = compute_low_volatility_factor(prices)
    alpha_signals = compute_alpha_signals(smart_money, fundamentals)

    # 3. Get regime-adjusted weights
    weights = get_weights(timeframe, regime)

    # 4. Compute composite score
    raw_score = (
        quality * weights.quality +
        value * weights.value +
        momentum * weights.momentum +
        low_vol * weights.low_vol +
        alpha_signals * weights.smart_money
    )

    # 5. Apply risk filters
    if not passes_risk_filters(ticker, fundamentals):
        return Score(value=0, filtered=True)

    # 6. Differentiate scores (spread distribution)
    final_score = differentiate_score(raw_score)

    return Score(
        value=final_score,
        factors={...},
        conviction=compute_conviction(factors),
        position_size=kelly_fraction(...)
    )
```

---

## Validation & Backtesting

### Backtest Requirements

1. **Period**: 5 years (2019-2024) including COVID crash
2. **Benchmark**: SPY total return
3. **Transaction costs**: 0.1% per trade (slippage + commission)
4. **Rebalance**: Weekly (Fridays)

### Validation Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Alpha | Portfolio return - Benchmark return | 5-10% |
| Beta | Covariance / Benchmark variance | 0.8-1.2 |
| Sharpe | (Return - Rf) / Std Dev | ≥1.0 |
| Sortino | (Return - Rf) / Downside Dev | ≥1.5 |
| Max Drawdown | Worst peak-to-trough | ≤20% |
| Win Rate | % of picks outperforming | ≥55% |
| Turnover | Annual position changes | ≤200% |

### Out-of-Sample Testing

1. Train on 2019-2022 data
2. Validate on 2023 data
3. Test on 2024 data (true out-of-sample)

---

## Breaking Changes

1. **Score scale change**: Current 0-1 → 0-100 internally
2. **Weight redistribution**: Significant changes to factor weights
3. **New required fields**: `gross_profitability`, `earnings_revision`
4. **Database schema**: New `market_regime` table

---

## Non-Goals (Out of Scope)

- Real-time intraday trading
- Paid data sources (Bloomberg, Refinitiv)
- Options strategies (calls/puts)
- Cryptocurrency
- International stocks (non-US)
- Machine learning models (neural nets, etc.)

---

## Open Questions

1. **Earnings revision data**: Yahoo Finance provides earnings estimates - sufficient for revision momentum?
2. **Form 4 reliability**: Current 404 rate ~40% - acceptable or need alternative source?
3. **Backtest framework**: Build custom or use existing (backtrader, zipline)?

---

## Dependencies

- `domain/scoring.py` - Main scoring logic (refactor)
- `adapters/sec_13f.py` - 13F data (enhance error handling)
- `adapters/finnhub.py` - Market data (add earnings dates)
- `config/schema.py` - Configuration (add regime config)
- `orchestration/pipeline.py` - Pipeline (add regime detection step)
