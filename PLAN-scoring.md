# PLAN: Enhanced Stock Picking Algorithm

**Spec Reference**: `SPEC-scoring.md`
**Target**: 5-10% alpha, weekly rebalance, free data, all-weather

---

## Implementation Phases

### Phase 1: Factor Computation Modules (Foundation)
**Complexity**: M | **Parallel**: Yes (all modules independent)

These modules can be implemented and tested in parallel as they have no interdependencies.

#### Module 1.1: Quality Factor
**Complexity**: S
**File**: `domain/factors/quality.py` (new)

```python
# Signatures
def compute_gross_profitability(revenue: float, cogs: float, total_assets: float) -> float:
    """Novy-Marx gross profitability = (Revenue - COGS) / Total Assets. Returns 0-100."""

def compute_quality_score(
    gross_profit_margin: float,
    roe: float,
    debt_equity: float,
    margin_stability: float  # 3Y standard deviation
) -> float:
    """Composite quality factor. Returns 0-100."""

# Dependencies
- Yahoo Finance fundamentals (existing)

# Done Criteria
- [ ] Unit tests with known values (AAPL, MSFT quality scores)
- [ ] Gross profitability matches manual calculation within 1%
- [ ] Score distribution: mean ~50, std ~15-25
```

#### Module 1.2: Value Factor
**Complexity**: S
**File**: `domain/factors/value.py` (new)

```python
# Signatures
def compute_earnings_yield(eps: float, price: float) -> float:
    """E/P ratio as percentage. Returns 0-100 normalized."""

def compute_fcf_yield(fcf: float, market_cap: float) -> float:
    """Free cash flow yield. Returns 0-100 normalized."""

def compute_value_score(
    earnings_yield: float,
    book_to_market: float,
    fcf_yield: float
) -> float:
    """Composite value factor. Returns 0-100."""

# Done Criteria
- [ ] Unit tests with value stocks (BRK.B, JPM) vs growth (TSLA, NVDA)
- [ ] Value stocks score >60, growth stocks score <40
- [ ] Handles negative earnings gracefully (score 0, not error)
```

#### Module 1.3: Momentum Factor
**Complexity**: M
**File**: `domain/factors/momentum.py` (new)

```python
# Signatures
def compute_price_momentum_12_1(prices: list[float]) -> float:
    """Jegadeesh-Titman 12-1 month momentum. Returns 0-100."""

def compute_volume_weighted_momentum(
    prices: list[float],
    volumes: list[float],
    window: int = 20
) -> float:
    """Volume-weighted price momentum. Returns 0-100."""

def compute_momentum_score(
    price_momentum: float,
    volume_momentum: float,
    earnings_revision: float | None = None  # Phase 2
) -> float:
    """Composite momentum factor. Returns 0-100."""

# Dependencies
- Price history (252 days minimum)

# Done Criteria
- [ ] 12-1 momentum excludes most recent month (avoid reversal)
- [ ] Unit tests with trending vs mean-reverting stocks
- [ ] Volume weighting increases score for high-volume moves
```

#### Module 1.4: Low Volatility Factor
**Complexity**: S
**File**: `domain/factors/low_volatility.py` (new)

```python
# Signatures
def compute_realized_volatility(returns: list[float], window: int = 252) -> float:
    """Annualized realized volatility. Returns raw percentage."""

def compute_beta(stock_returns: list[float], market_returns: list[float]) -> float:
    """CAPM beta vs SPY. Returns raw beta value."""

def compute_low_vol_score(volatility: float, beta: float) -> float:
    """Low volatility factor (inverted - lower vol = higher score). Returns 0-100."""

# Dependencies
- Stock prices (252 days)
- SPY prices (252 days)

# Done Criteria
- [ ] Utilities (XLU sector) score >70
- [ ] Tech/Growth stocks score <40
- [ ] Beta calculation matches Yahoo Finance within 0.1
```

---

### Phase 2: Alpha Signal Modules
**Complexity**: M | **Parallel**: Yes (independent of Phase 1)

Can run in parallel with Phase 1.

#### Module 2.1: Smart Money Signal Enhancement
**Complexity**: M
**File**: `domain/factors/smart_money.py` (new, refactor from scoring.py)

```python
# Signatures
def compute_institutional_accumulation(
    current_holdings: list[Filing13F],
    previous_holdings: list[Filing13F]
) -> float:
    """QoQ change in institutional ownership. Returns 0-100."""

def compute_insider_cluster_score(
    insider_trades: list[Form4Trade],
    lookback_days: int = 90
) -> float:
    """Cluster buy detection (3+ insiders buying). Returns 0-100."""

def compute_congress_trade_score(
    trades: list[CongressTrade],
    lookback_days: int = 60
) -> float:
    """Recency-weighted congress trades. Returns 0-100."""

def compute_smart_money_score(
    institutional: float,
    insider: float,
    congress: float
) -> float:
    """Composite smart money signal. Returns 0-100."""

# Dependencies
- adapters/sec_13f.py (existing, needs error handling)
- adapters/finnhub.py (congress trades)

# Done Criteria
- [ ] Handles 404 errors gracefully (returns None, not crash)
- [ ] Recency weighting: trades <30 days = 1.0x, 30-60 days = 0.5x, >60 days = 0.25x
- [ ] Cluster detection requires 3+ unique insiders
```

#### Module 2.2: Catalyst Awareness
**Complexity**: S
**File**: `domain/factors/catalyst.py` (new)

```python
# Signatures
def compute_earnings_proximity_score(
    next_earnings_date: date | None,
    today: date
) -> float:
    """Score based on days to earnings (higher = closer). Returns 0-100."""

def compute_sector_rotation_score(
    sector: str,
    sector_performance: dict[str, float],  # 1-month returns
    regime: MarketRegime
) -> float:
    """Sector momentum relative to market. Returns 0-100."""

# Dependencies
- Yahoo Finance earnings calendar
- Sector ETF prices (XLK, XLF, XLV, etc.)

# Done Criteria
- [ ] Earnings within 2 weeks = score >80
- [ ] Leading sectors in regime get >70
- [ ] Handles missing earnings dates (returns 50 neutral)
```

---

### Phase 3: Market Regime Detection
**Complexity**: S | **Parallel**: No (needed before Phase 4)

#### Module 3.1: Regime Classifier
**Complexity**: S
**File**: `domain/regime.py` (new)

```python
# Signatures
class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_vol"

def detect_market_regime(
    spy_prices: list[float],  # 252 days
    vix_current: float
) -> MarketRegime:
    """
    Classify current market regime.
    - BULL: SPY > 200 SMA and VIX < 20
    - BEAR: SPY < 200 SMA and VIX > 25
    - HIGH_VOL: VIX > 30 (overrides others)
    - SIDEWAYS: else
    """

def get_regime_weights(
    regime: MarketRegime,
    timeframe: Timeframe
) -> FactorWeights:
    """Return regime-adjusted factor weights."""

# Dependencies
- SPY price history
- VIX current value (^VIX)

# Done Criteria
- [ ] March 2020 detected as HIGH_VOL
- [ ] 2021 detected as BULL
- [ ] Unit tests for each regime condition
```

---

### Phase 4: Scoring Engine Refactor
**Complexity**: L | **Parallel**: No (depends on Phases 1-3)

**⚠️ Flag**: Large module - consider decomposition if >500 lines.

#### Module 4.1: Score Aggregator
**Complexity**: M
**File**: `domain/scoring.py` (refactor existing)

```python
# Signatures (changes to existing)
@dataclass
class EnhancedScore:
    value: float  # 0-100
    factors: dict[str, float]  # Individual factor scores
    weights_used: FactorWeights
    regime: MarketRegime
    conviction: float  # 0-100
    position_size: float  # 0.0-0.08 (max 8%)
    filtered: bool
    filter_reason: str | None

def score_stock(
    ticker: str,
    timeframe: Timeframe,
    regime: MarketRegime,
    fundamentals: Fundamentals,
    prices: PriceHistory,
    smart_money: SmartMoneyData
) -> EnhancedScore:
    """Main scoring function with regime-aware weighting."""

def differentiate_scores(scores: list[EnhancedScore]) -> list[EnhancedScore]:
    """Spread score distribution for better pick differentiation."""

# Breaking Changes
- compute_overall_score() → score_stock() (new signature)
- Score returns 0-100 instead of 0-1
- New EnhancedScore dataclass replaces raw float

# Done Criteria
- [ ] All existing unit tests pass (with scale adjustment)
- [ ] Score distribution: mean ~50, std 15-25, min >10, max <90
- [ ] Regime changes weights correctly
- [ ] Position sizes sum to ≤100% for top 20 picks
```

#### Module 4.2: Risk Overlay Enhancement
**Complexity**: S
**File**: `domain/risk.py` (new, extract from scoring.py)

```python
# Signatures
@dataclass
class RiskFilters:
    min_market_cap: float = 2e9
    min_avg_volume: float = 500_000
    max_days_to_cover: float = 5.0
    max_debt_equity: float = 2.0
    min_current_ratio: float = 1.0
    min_price: float = 5.0

def apply_risk_filters(
    ticker: str,
    fundamentals: Fundamentals,
    filters: RiskFilters
) -> tuple[bool, str | None]:
    """Returns (passes, reason_if_failed)."""

def compute_position_size(
    score: float,
    conviction: float,
    win_rate: float = 0.55,
    avg_win_loss_ratio: float = 1.5
) -> float:
    """Quarter-Kelly position sizing. Returns 0.0-0.08."""

# Done Criteria
- [ ] Penny stocks (<$5) filtered
- [ ] High leverage (D/E > 2) filtered
- [ ] Position sizes: max 8%, min 1%
```

---

### Phase 5: Pipeline Integration
**Complexity**: M | **Parallel**: No (depends on Phase 4)

#### Module 5.1: Pipeline Updates
**Complexity**: M
**File**: `orchestration/pipeline.py` (modify existing)

```python
# New Steps to Add
async def detect_regime_step(self) -> MarketRegime:
    """Fetch SPY/VIX and classify regime."""

async def compute_enhanced_scores_step(
    self,
    stocks: list[str],
    regime: MarketRegime
) -> list[EnhancedScore]:
    """Score all stocks with new algorithm."""

# Pipeline Order Changes
# Before: fetch_data → score → filter → pick
# After:  fetch_data → detect_regime → score → filter → size → pick

# Done Criteria
- [ ] Regime detection runs before scoring
- [ ] Position sizes included in output
- [ ] report.json includes regime and factor breakdown
```

#### Module 5.2: Database Schema Updates
**Complexity**: S
**File**: `migrations/add_regime_table.sql` (new)

```sql
-- New table for regime history
CREATE TABLE IF NOT EXISTS market_regime (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    regime TEXT NOT NULL,
    spy_price REAL,
    spy_sma_200 REAL,
    vix REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add columns to stock_picks
ALTER TABLE stock_picks ADD COLUMN regime TEXT;
ALTER TABLE stock_picks ADD COLUMN position_size REAL;
ALTER TABLE stock_picks ADD COLUMN factor_scores TEXT;  -- JSON
```

**⚠️ External Action**: Database migration required.

```
# Done Criteria
- [ ] Migration runs without error
- [ ] Existing data preserved
- [ ] New columns queryable
```

---

### Phase 6: Validation & Backtesting
**Complexity**: L | **Parallel**: Partially (backtest can start while fine-tuning)

#### Module 6.1: Backtest Framework
**Complexity**: M
**File**: `domain/backtest.py` (new)

```python
# Signatures
@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float = 100_000
    transaction_cost: float = 0.001  # 0.1%
    rebalance_freq: str = "weekly"

@dataclass
class BacktestResult:
    total_return: float
    alpha: float
    beta: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    turnover: float
    trades: list[Trade]

async def run_backtest(
    config: BacktestConfig,
    scoring_fn: Callable
) -> BacktestResult:
    """Run historical backtest with given scoring function."""

def compare_to_benchmark(
    portfolio_returns: list[float],
    benchmark_returns: list[float]
) -> dict[str, float]:
    """Compute alpha, beta, information ratio."""

# Done Criteria
- [ ] Backtest 2019-2024 completes without error
- [ ] Transaction costs applied correctly
- [ ] Alpha calculation matches manual spot-check
```

#### Module 6.2: Performance Tracker Enhancement
**Complexity**: S
**File**: `domain/performance.py` (modify existing)

```python
# Add to existing
def track_factor_attribution(
    pick: StockPick,
    actual_return: float
) -> dict[str, float]:
    """Which factors contributed to return."""

def compute_regime_performance(
    picks: list[PickPerformance],
    regime: MarketRegime
) -> dict[str, float]:
    """Performance breakdown by regime."""

# Done Criteria
- [ ] Factor attribution sums to ~100% of explained return
- [ ] Regime breakdown shows all-weather capability
```

---

## Implementation Groups

### Group A (Parallel - Start First)
- Module 1.1: Quality Factor (S)
- Module 1.2: Value Factor (S)
- Module 1.3: Momentum Factor (M)
- Module 1.4: Low Volatility Factor (S)
- Module 2.1: Smart Money Enhancement (M)
- Module 2.2: Catalyst Awareness (S)

**Total**: 6 modules, can implement in parallel

### Group B (Sequential - After Group A)
- Module 3.1: Regime Classifier (S)
- Module 4.1: Score Aggregator (M)
- Module 4.2: Risk Overlay (S)

**Dependencies**: Requires Group A complete

### Group C (Sequential - After Group B)
- Module 5.1: Pipeline Updates (M)
- Module 5.2: Database Schema (S)

**Dependencies**: Requires Group B complete
**⚠️ External Action**: Database migration

### Group D (Final - After Group C)
- Module 6.1: Backtest Framework (M)
- Module 6.2: Performance Tracker (S)

**Dependencies**: Full algorithm working

---

## Blocking Unknowns

| Unknown | Resolution | Status |
|---------|------------|--------|
| Earnings revision data availability | Test Yahoo Finance `analyst_price_targets` endpoint | 🔍 Spike needed |
| Form 4 404 error rate | Log failures for 1 week, assess fallback strategy | 🔍 Monitor |
| Backtest framework choice | Start custom, consider backtrader if complex | ✅ Decided |

**Technical Spike Required**:
```python
# Test earnings revision data availability
# File: spikes/earnings_revision_test.py
async def test_earnings_data():
    """Verify Yahoo Finance provides historical estimates."""
    # Need: current estimate, estimate 30 days ago, estimate 90 days ago
    # For revision momentum calculation
```

---

## Destructive Actions

| Action | Risk | Mitigation |
|--------|------|------------|
| Database migration | Data loss | Backup before, use ALTER TABLE (preserves data) |
| Score scale change (0-1 → 0-100) | Breaking existing consumers | Update all consumers in same PR |
| Weight redistribution | Different picks | A/B test for 2 weeks before full rollout |

**Recommended Approach**:
1. Database backup before migration
2. Feature flag for new algorithm (`USE_ENHANCED_SCORING=true`)
3. Run both algorithms in parallel for 2 weeks
4. Compare performance before switching default

---

## Validation Points

### Unit Test Validation
| Module | Test Type | Tool |
|--------|-----------|------|
| Factor modules | Unit tests with known values | pytest |
| Score aggregator | Integration test with mock data | pytest |
| Risk filters | Boundary tests | pytest |

### Integration Validation
| Component | Validation Method |
|-----------|-------------------|
| Pipeline | End-to-end run, check report.json |
| Database | Query new columns after migration |
| API | Frontend displays new fields |

### Backtest Validation
| Metric | Validation |
|--------|------------|
| Alpha | Manual calculation spot-check |
| Sharpe | Compare to known benchmark |
| Drawdown | Plot equity curve, verify max |

---

## E2E Success Criteria

The feature is complete when:

1. **Algorithm Correctness**
   - [ ] All factor modules have passing unit tests
   - [ ] Score aggregator produces differentiated scores (std > 15)
   - [ ] Regime detection correctly classifies historical periods

2. **Integration**
   - [ ] Pipeline runs without error
   - [ ] report.json includes regime, factor breakdown, position sizes
   - [ ] Frontend displays enhanced pick information

3. **Performance**
   - [ ] Backtest shows 5-10% alpha over 5-year period
   - [ ] Sharpe ratio ≥ 1.0
   - [ ] Positive returns in at least 2/3 market regimes
   - [ ] Max drawdown ≤ 20%

4. **Production Readiness**
   - [ ] Feature flag allows rollback
   - [ ] 2-week parallel run shows improvement
   - [ ] No regressions in existing functionality

---

## Estimated Effort

| Phase | Complexity | Modules |
|-------|------------|---------|
| Phase 1 | 4S + 1M = M | 4 |
| Phase 2 | 1S + 1M = M | 2 |
| Phase 3 | S | 1 |
| Phase 4 | L (decompose) | 2 |
| Phase 5 | M + S = M | 2 |
| Phase 6 | M + S = M | 2 |

**Total**: 13 modules, estimated 2-3 sprints

---

## Next Steps

1. **Immediate**: Run technical spike for earnings revision data
2. **This Sprint**: Implement Group A (parallel factor modules)
3. **Next Sprint**: Group B + C (scoring engine + pipeline)
4. **Following Sprint**: Group D (backtest + validation)
