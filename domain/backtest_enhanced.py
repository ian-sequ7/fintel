"""
Enhanced Backtesting Framework for V3 Scoring System.

Extends the existing backtest framework with:
- Regime-aware scoring using v3 enhanced factors
- Factor attribution tracking
- Weekly rebalancing support
- Transaction cost modeling
- Performance breakdown by regime

Usage:
    from domain.backtest_enhanced import run_enhanced_backtest

    result = run_enhanced_backtest(
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        rebalance_freq="weekly",
    )
    print(result.summary())
    print(result.factor_attribution_summary())
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Literal, Callable

from .models import Timeframe
from .regime import MarketRegime, RegimeContext, detect_market_regime
from .score_aggregator import EnhancedScore


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class EnhancedBacktestConfig:
    """Configuration for enhanced backtest execution."""

    # Pick selection
    top_n_picks: int = 10
    min_conviction: int = 5  # 1-10 scale
    min_score: float = 50.0  # 0-100 scale

    # Rebalancing
    rebalance_freq: Literal["weekly", "monthly"] = "weekly"
    holding_days: int = 7  # Default for weekly

    # Transaction costs
    transaction_cost_bps: float = 10.0  # 10 basis points (0.1%)
    slippage_bps: float = 5.0  # 5 basis points

    # Risk management
    max_sector_weight: float = 0.25  # 25% max per sector
    max_position_weight: float = 0.08  # 8% max per position
    min_position_weight: float = 0.02  # 2% min per position

    # Benchmark
    benchmark_ticker: str = "SPY"

    # Capital
    initial_capital: float = 100_000

    @property
    def total_cost_bps(self) -> float:
        """Total round-trip cost in basis points."""
        return (self.transaction_cost_bps + self.slippage_bps) * 2


# ============================================================================
# Trade Records with Factor Attribution
# ============================================================================


@dataclass
class EnhancedBacktestTrade:
    """Trade record with full factor attribution."""

    ticker: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    position_size: float  # 0-1 weight in portfolio

    # Scoring details
    score: float  # 0-100
    conviction: int  # 1-10
    timeframe: Timeframe
    sector: str
    regime_at_entry: MarketRegime

    # Factor breakdown at entry
    factor_scores: dict[str, float]
    factor_weights: dict[str, float]

    # Benchmark
    benchmark_entry: float
    benchmark_exit: float

    # Transaction costs
    transaction_cost: float = 0.0

    @property
    def gross_return_pct(self) -> float:
        """Gross percentage return (before costs)."""
        if self.entry_price <= 0:
            return 0.0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    @property
    def net_return_pct(self) -> float:
        """Net percentage return (after costs)."""
        return self.gross_return_pct - (self.transaction_cost / self.entry_price * 100)

    @property
    def benchmark_return_pct(self) -> float:
        """Benchmark return over same period."""
        if self.benchmark_entry <= 0:
            return 0.0
        return ((self.benchmark_exit - self.benchmark_entry) / self.benchmark_entry) * 100

    @property
    def alpha(self) -> float:
        """Excess return over benchmark (after costs)."""
        return self.net_return_pct - self.benchmark_return_pct

    @property
    def is_winner(self) -> bool:
        """Positive net return."""
        return self.net_return_pct > 0

    @property
    def beat_benchmark(self) -> bool:
        """Outperformed benchmark."""
        return self.net_return_pct > self.benchmark_return_pct

    def factor_contribution(self) -> dict[str, float]:
        """
        Estimate factor contribution to return.

        Uses weighted factor scores to attribute the trade's alpha
        proportionally to each factor's influence.
        """
        total_weighted = sum(
            self.factor_scores.get(f, 50) * self.factor_weights.get(f, 0)
            for f in self.factor_scores
        )

        if total_weighted <= 0:
            return {f: 0.0 for f in self.factor_scores}

        contributions = {}
        for factor, score in self.factor_scores.items():
            weight = self.factor_weights.get(factor, 0)
            weighted_score = score * weight
            contribution_pct = weighted_score / total_weighted
            contributions[factor] = self.alpha * contribution_pct

        return contributions


@dataclass
class PeriodReturn:
    """Returns for a single period (week or month)."""
    period_start: date
    period_end: date
    portfolio_return: float  # Net percentage
    benchmark_return: float
    regime: MarketRegime
    num_picks: int
    num_trades: int  # Trades executed (rebalancing)
    transaction_costs: float
    top_performer: str | None
    worst_performer: str | None


# ============================================================================
# Performance Attribution
# ============================================================================


@dataclass
class FactorAttribution:
    """Factor contribution analysis."""
    factor: str
    avg_score: float  # Average factor score across picks
    contribution_to_alpha: float  # Estimated alpha contribution
    correlation_with_returns: float  # Factor score vs return correlation
    winners_avg: float  # Avg factor score for winning trades
    losers_avg: float  # Avg factor score for losing trades


@dataclass
class RegimePerformance:
    """Performance breakdown by market regime."""
    regime: MarketRegime
    num_periods: int
    num_trades: int
    total_return: float
    avg_return: float
    hit_rate: float  # % beating benchmark
    win_rate: float  # % positive return
    avg_alpha: float
    sharpe_ratio: float


# ============================================================================
# Backtest Result
# ============================================================================


@dataclass
class EnhancedBacktestResult:
    """Complete results from enhanced backtest."""

    # Configuration
    start_date: date
    end_date: date
    config: EnhancedBacktestConfig

    # Raw data
    trades: list[EnhancedBacktestTrade] = field(default_factory=list)
    period_returns: list[PeriodReturn] = field(default_factory=list)

    # Execution metadata
    executed_at: datetime = field(default_factory=datetime.now)
    tickers_analyzed: int = 0
    scoring_errors: int = 0

    # -------------------------------------------------------------------------
    # Aggregate Metrics
    # -------------------------------------------------------------------------

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def total_return(self) -> float:
        """Total portfolio return (compounded, net of costs)."""
        if not self.period_returns:
            return 0.0
        cumulative = 1.0
        for pr in self.period_returns:
            cumulative *= (1 + pr.portfolio_return / 100)
        return (cumulative - 1) * 100

    @property
    def benchmark_return(self) -> float:
        """Total benchmark return (compounded)."""
        if not self.period_returns:
            return 0.0
        cumulative = 1.0
        for pr in self.period_returns:
            cumulative *= (1 + pr.benchmark_return / 100)
        return (cumulative - 1) * 100

    @property
    def alpha(self) -> float:
        """Total excess return over benchmark."""
        return self.total_return - self.benchmark_return

    @property
    def annualized_alpha(self) -> float:
        """Annualized alpha."""
        if not self.period_returns:
            return 0.0
        days = (self.end_date - self.start_date).days
        if days <= 0:
            return 0.0
        years = days / 365.25
        if years <= 0:
            return 0.0
        # Simple annualization
        return self.alpha / years

    @property
    def hit_rate(self) -> float:
        """Percentage of trades that beat the benchmark."""
        if not self.trades:
            return 0.0
        beats = sum(1 for t in self.trades if t.beat_benchmark)
        return (beats / len(self.trades)) * 100

    @property
    def win_rate(self) -> float:
        """Percentage of trades with positive return."""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.is_winner)
        return (wins / len(self.trades)) * 100

    @property
    def avg_trade_return(self) -> float:
        """Average net return per trade."""
        if not self.trades:
            return 0.0
        return statistics.mean(t.net_return_pct for t in self.trades)

    @property
    def avg_alpha_per_trade(self) -> float:
        """Average excess return per trade."""
        if not self.trades:
            return 0.0
        return statistics.mean(t.alpha for t in self.trades)

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio."""
        if len(self.period_returns) < 2:
            return 0.0

        returns = [pr.portfolio_return for pr in self.period_returns]

        # Determine periods per year
        if self.config.rebalance_freq == "weekly":
            periods_per_year = 52
            rf_per_period = 4.0 / 52  # ~0.08% weekly
        else:
            periods_per_year = 12
            rf_per_period = 4.0 / 12  # ~0.33% monthly

        excess_returns = [r - rf_per_period for r in returns]
        mean_excess = statistics.mean(excess_returns)
        std_dev = statistics.stdev(excess_returns) if len(excess_returns) > 1 else 1.0

        if std_dev == 0:
            return 0.0

        return (mean_excess / std_dev) * math.sqrt(periods_per_year)

    @property
    def sortino_ratio(self) -> float:
        """Sortino ratio (penalizes downside volatility only)."""
        if len(self.period_returns) < 2:
            return 0.0

        returns = [pr.portfolio_return for pr in self.period_returns]

        # Periods per year
        if self.config.rebalance_freq == "weekly":
            periods_per_year = 52
            rf_per_period = 4.0 / 52
        else:
            periods_per_year = 12
            rf_per_period = 4.0 / 12

        excess_returns = [r - rf_per_period for r in returns]
        downside_returns = [min(0, r) for r in excess_returns]

        mean_excess = statistics.mean(excess_returns)
        downside_dev = statistics.stdev(downside_returns) if len(downside_returns) > 1 else 1.0

        if downside_dev == 0:
            return 0.0

        return (mean_excess / downside_dev) * math.sqrt(periods_per_year)

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough decline."""
        if not self.period_returns:
            return 0.0

        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0

        for pr in self.period_returns:
            cumulative *= (1 + pr.portfolio_return / 100)
            peak = max(peak, cumulative)
            drawdown = (peak - cumulative) / peak * 100
            max_dd = max(max_dd, drawdown)

        return max_dd

    @property
    def total_transaction_costs(self) -> float:
        """Total transaction costs paid."""
        return sum(pr.transaction_costs for pr in self.period_returns)

    @property
    def turnover(self) -> float:
        """Average portfolio turnover per period."""
        if not self.period_returns:
            return 0.0
        total_trades = sum(pr.num_trades for pr in self.period_returns)
        return total_trades / len(self.period_returns)

    # -------------------------------------------------------------------------
    # Factor Attribution
    # -------------------------------------------------------------------------

    def compute_factor_attribution(self) -> list[FactorAttribution]:
        """Compute contribution of each factor to returns."""
        if not self.trades:
            return []

        factors = ["quality", "value", "momentum", "low_vol", "smart_money", "catalyst"]
        attributions = []

        for factor in factors:
            # Gather data
            scores = [t.factor_scores.get(factor, 50) for t in self.trades]
            returns = [t.net_return_pct for t in self.trades]
            contributions = [t.factor_contribution().get(factor, 0) for t in self.trades]

            winners = [t for t in self.trades if t.is_winner]
            losers = [t for t in self.trades if not t.is_winner]

            # Correlation
            if len(scores) > 1:
                corr = _compute_correlation(scores, returns)
            else:
                corr = 0.0

            attr = FactorAttribution(
                factor=factor,
                avg_score=statistics.mean(scores) if scores else 50.0,
                contribution_to_alpha=sum(contributions),
                correlation_with_returns=corr,
                winners_avg=statistics.mean(t.factor_scores.get(factor, 50) for t in winners) if winners else 50.0,
                losers_avg=statistics.mean(t.factor_scores.get(factor, 50) for t in losers) if losers else 50.0,
            )
            attributions.append(attr)

        # Sort by contribution
        attributions.sort(key=lambda a: abs(a.contribution_to_alpha), reverse=True)
        return attributions

    # -------------------------------------------------------------------------
    # Regime Performance
    # -------------------------------------------------------------------------

    def compute_regime_performance(self) -> list[RegimePerformance]:
        """Breakdown performance by market regime."""
        regime_trades: dict[MarketRegime, list[EnhancedBacktestTrade]] = {}
        regime_periods: dict[MarketRegime, list[PeriodReturn]] = {}

        for trade in self.trades:
            if trade.regime_at_entry not in regime_trades:
                regime_trades[trade.regime_at_entry] = []
            regime_trades[trade.regime_at_entry].append(trade)

        for pr in self.period_returns:
            if pr.regime not in regime_periods:
                regime_periods[pr.regime] = []
            regime_periods[pr.regime].append(pr)

        results = []
        for regime in MarketRegime:
            trades = regime_trades.get(regime, [])
            periods = regime_periods.get(regime, [])

            if not periods:
                continue

            # Calculate regime metrics
            returns = [pr.portfolio_return for pr in periods]
            total_ret = 0.0
            cumulative = 1.0
            for r in returns:
                cumulative *= (1 + r / 100)
            total_ret = (cumulative - 1) * 100

            # Sharpe for this regime
            if len(returns) > 1:
                mean_ret = statistics.mean(returns)
                std_ret = statistics.stdev(returns)
                sharpe = (mean_ret / std_ret * math.sqrt(52)) if std_ret > 0 else 0.0
            else:
                sharpe = 0.0

            results.append(RegimePerformance(
                regime=regime,
                num_periods=len(periods),
                num_trades=len(trades),
                total_return=total_ret,
                avg_return=statistics.mean(returns) if returns else 0.0,
                hit_rate=(sum(1 for t in trades if t.beat_benchmark) / len(trades) * 100) if trades else 0.0,
                win_rate=(sum(1 for t in trades if t.is_winner) / len(trades) * 100) if trades else 0.0,
                avg_alpha=statistics.mean(t.alpha for t in trades) if trades else 0.0,
                sharpe_ratio=sharpe,
            ))

        return results

    # -------------------------------------------------------------------------
    # Output Methods
    # -------------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "=" * 70,
            "ENHANCED BACKTEST RESULTS (V3 Scoring)",
            "=" * 70,
            f"Period: {self.start_date} to {self.end_date}",
            f"Rebalance: {self.config.rebalance_freq}",
            f"Total Trades: {self.total_trades}",
            f"Tickers Analyzed: {self.tickers_analyzed}",
            "",
            "PERFORMANCE (Net of Costs)",
            "-" * 50,
            f"Total Return:       {self.total_return:+.2f}%",
            f"Benchmark (SPY):    {self.benchmark_return:+.2f}%",
            f"Alpha:              {self.alpha:+.2f}%",
            f"Annualized Alpha:   {self.annualized_alpha:+.2f}%",
            "",
            f"Hit Rate:           {self.hit_rate:.1f}% (beat benchmark)",
            f"Win Rate:           {self.win_rate:.1f}% (positive return)",
            f"Avg Trade Return:   {self.avg_trade_return:+.2f}%",
            f"Avg Alpha/Trade:    {self.avg_alpha_per_trade:+.2f}%",
            "",
            "RISK METRICS",
            "-" * 50,
            f"Sharpe Ratio:       {self.sharpe_ratio:.2f}",
            f"Sortino Ratio:      {self.sortino_ratio:.2f}",
            f"Max Drawdown:       {self.max_drawdown:.2f}%",
            "",
            "COSTS",
            "-" * 50,
            f"Total Costs:        ${self.total_transaction_costs:,.2f}",
            f"Avg Turnover:       {self.turnover:.1f} trades/period",
            "=" * 70,
        ]
        return "\n".join(lines)

    def factor_attribution_summary(self) -> str:
        """Factor attribution summary."""
        attrs = self.compute_factor_attribution()
        if not attrs:
            return "No factor attribution data available."

        lines = [
            "",
            "FACTOR ATTRIBUTION",
            "-" * 50,
            f"{'Factor':<15} {'Avg Score':<12} {'Alpha Contrib':<15} {'Correlation':<12}",
            "-" * 50,
        ]

        for a in attrs:
            lines.append(
                f"{a.factor:<15} {a.avg_score:>8.1f}     {a.contribution_to_alpha:>+10.2f}%    {a.correlation_with_returns:>+8.3f}"
            )

        lines.extend([
            "",
            "Winner vs Loser Factor Scores:",
            f"{'Factor':<15} {'Winners':<12} {'Losers':<12} {'Delta':<12}",
            "-" * 50,
        ])

        for a in attrs:
            delta = a.winners_avg - a.losers_avg
            lines.append(
                f"{a.factor:<15} {a.winners_avg:>8.1f}     {a.losers_avg:>8.1f}     {delta:>+8.1f}"
            )

        return "\n".join(lines)

    def regime_performance_summary(self) -> str:
        """Regime performance summary."""
        regimes = self.compute_regime_performance()
        if not regimes:
            return "No regime performance data available."

        lines = [
            "",
            "PERFORMANCE BY MARKET REGIME",
            "-" * 70,
            f"{'Regime':<12} {'Periods':<10} {'Return':<12} {'Hit Rate':<12} {'Win Rate':<12} {'Sharpe':<10}",
            "-" * 70,
        ]

        for r in regimes:
            lines.append(
                f"{r.regime.value:<12} {r.num_periods:<10} {r.total_return:>+8.2f}%   "
                f"{r.hit_rate:>8.1f}%    {r.win_rate:>8.1f}%    {r.sharpe_ratio:>+6.2f}"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "config": {
                "rebalance_freq": self.config.rebalance_freq,
                "top_n_picks": self.config.top_n_picks,
                "transaction_cost_bps": self.config.transaction_cost_bps,
            },
            "performance": {
                "total_return": round(self.total_return, 2),
                "benchmark_return": round(self.benchmark_return, 2),
                "alpha": round(self.alpha, 2),
                "annualized_alpha": round(self.annualized_alpha, 2),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "max_drawdown": round(self.max_drawdown, 2),
                "hit_rate": round(self.hit_rate, 1),
                "win_rate": round(self.win_rate, 1),
            },
            "factor_attribution": [
                {
                    "factor": a.factor,
                    "avg_score": round(a.avg_score, 1),
                    "contribution": round(a.contribution_to_alpha, 2),
                    "correlation": round(a.correlation_with_returns, 3),
                }
                for a in self.compute_factor_attribution()
            ],
            "regime_performance": [
                {
                    "regime": r.regime.value,
                    "periods": r.num_periods,
                    "return": round(r.total_return, 2),
                    "hit_rate": round(r.hit_rate, 1),
                    "sharpe": round(r.sharpe_ratio, 2),
                }
                for r in self.compute_regime_performance()
            ],
            "total_trades": self.total_trades,
            "tickers_analyzed": self.tickers_analyzed,
            "executed_at": self.executed_at.isoformat(),
        }


# ============================================================================
# Backtest Engine
# ============================================================================


def run_enhanced_backtest(
    start_date: date,
    end_date: date,
    config: EnhancedBacktestConfig | None = None,
    *,
    universe: list[str] | None = None,
    verbose: bool = False,
) -> EnhancedBacktestResult:
    """
    Run enhanced backtest using v3 scoring system.

    Uses regime-aware scoring with full factor attribution tracking.

    Args:
        start_date: Backtest start date
        end_date: Backtest end date
        config: Backtest configuration
        universe: Stock universe (uses default if None)
        verbose: Print progress

    Returns:
        EnhancedBacktestResult with full analysis
    """
    # Lazy imports
    from adapters import YahooAdapter
    from db import get_db

    if config is None:
        config = EnhancedBacktestConfig()

    if universe is None:
        universe = _get_backtest_universe()

    if verbose:
        print(f"Enhanced backtest: {len(universe)} tickers, {start_date} to {end_date}")
        print(f"Rebalance: {config.rebalance_freq}, Top {config.top_n_picks} picks")

    result = EnhancedBacktestResult(
        start_date=start_date,
        end_date=end_date,
        config=config,
        tickers_analyzed=len(universe),
    )

    # Initialize data sources
    db = get_db()
    yahoo = YahooAdapter()

    # Get benchmark prices
    benchmark_prices = _fetch_prices(yahoo, db, config.benchmark_ticker, start_date, end_date)
    if not benchmark_prices:
        raise ValueError(f"No benchmark data for {config.benchmark_ticker}")

    # Get all stock prices
    all_prices: dict[str, dict[date, float]] = {}
    for ticker in universe:
        prices = _fetch_prices(yahoo, db, ticker, start_date, end_date)
        if prices:
            all_prices[ticker] = prices

    if verbose:
        print(f"Loaded price data for {len(all_prices)} tickers")

    # Iterate through periods
    if config.rebalance_freq == "weekly":
        period_delta = timedelta(days=7)
    else:
        period_delta = timedelta(days=30)

    current = _next_trading_day(start_date)

    while current < end_date:
        next_period = _next_trading_day(current + period_delta)
        if next_period > end_date:
            next_period = end_date

        # Detect regime at this point
        spy_prices_list = _get_price_list_at_date(benchmark_prices, current, 252)
        vix_current = _get_vix_at_date(current)  # Simplified - uses current VIX

        regime_context = detect_market_regime(
            spy_prices=spy_prices_list,
            vix_current=vix_current,
        )

        # Score stocks using v3 enhanced scoring
        picks = _score_stocks_enhanced(
            tickers=list(all_prices.keys()),
            prices=all_prices,
            as_of_date=current,
            regime_context=regime_context,
            config=config,
            verbose=verbose,
        )

        result.scoring_errors += len(all_prices) - len(picks) - _count_no_price(all_prices, current)

        if not picks:
            current = next_period
            continue

        # Get benchmark prices
        bench_entry = _get_price_at_date(benchmark_prices, current)
        bench_exit = _get_price_at_date(benchmark_prices, next_period)

        if bench_entry is None or bench_exit is None:
            current = next_period
            continue

        # Create trades for top picks
        period_trades: list[EnhancedBacktestTrade] = []
        total_position_value = config.initial_capital

        for pick in picks[:config.top_n_picks]:
            ticker = pick["ticker"]
            if ticker not in all_prices:
                continue

            entry_price = _get_price_at_date(all_prices[ticker], current)
            exit_price = _get_price_at_date(all_prices[ticker], next_period)

            if entry_price is None or exit_price is None:
                continue

            # Position size from enhanced scoring
            position_size = min(pick["position_size"], config.max_position_weight)
            position_size = max(position_size, config.min_position_weight)

            # Transaction cost
            position_value = total_position_value * position_size
            tx_cost = position_value * (config.total_cost_bps / 10000)

            trade = EnhancedBacktestTrade(
                ticker=ticker,
                entry_date=current,
                exit_date=next_period,
                entry_price=entry_price,
                exit_price=exit_price,
                position_size=position_size,
                score=pick["score"],
                conviction=pick["conviction"],
                timeframe=pick["timeframe"],
                sector=pick["sector"],
                regime_at_entry=regime_context.regime,
                factor_scores=pick["factor_scores"],
                factor_weights=pick["factor_weights"],
                benchmark_entry=bench_entry,
                benchmark_exit=bench_exit,
                transaction_cost=tx_cost,
            )

            period_trades.append(trade)
            result.trades.append(trade)

        # Calculate period return (position-weighted)
        if period_trades:
            total_weight = sum(t.position_size for t in period_trades)
            if total_weight > 0:
                portfolio_return = sum(
                    t.net_return_pct * (t.position_size / total_weight)
                    for t in period_trades
                )
            else:
                portfolio_return = 0.0

            benchmark_return = ((bench_exit - bench_entry) / bench_entry) * 100
            total_costs = sum(t.transaction_cost for t in period_trades)

            best = max(period_trades, key=lambda t: t.net_return_pct)
            worst = min(period_trades, key=lambda t: t.net_return_pct)

            result.period_returns.append(PeriodReturn(
                period_start=current,
                period_end=next_period,
                portfolio_return=portfolio_return,
                benchmark_return=benchmark_return,
                regime=regime_context.regime,
                num_picks=len(period_trades),
                num_trades=len(period_trades),
                transaction_costs=total_costs,
                top_performer=best.ticker,
                worst_performer=worst.ticker,
            ))

        if verbose:
            print(f"  {current}: {len(period_trades)} trades, regime={regime_context.regime.value}")

        current = next_period

    return result


# ============================================================================
# Helper Functions
# ============================================================================


def _get_backtest_universe() -> list[str]:
    """Get default universe for backtesting."""
    from adapters.universe import get_combined_universe
    return get_combined_universe()


def _fetch_prices(yahoo, db, ticker: str, start: date, end: date) -> dict[date, float]:
    """Fetch prices from Yahoo or database."""
    try:
        # Try Yahoo first for fresh data
        today = date.today()
        days_needed = (today - start).days + 60
        history = yahoo.get_price_history(ticker, days=days_needed)

        result = {}
        for h in history:
            try:
                d = datetime.strptime(h["time"], "%Y-%m-%d").date()
                if start <= d <= end:
                    result[d] = float(h["close"])
            except (KeyError, ValueError):
                continue

        if result:
            return result
    except Exception:
        pass

    # Fallback to database
    try:
        points = db.get_price_history(ticker, days=730)
        return {
            datetime.strptime(p.date, "%Y-%m-%d").date() if isinstance(p.date, str) else p.date: p.close
            for p in points
            if start <= (datetime.strptime(p.date, "%Y-%m-%d").date() if isinstance(p.date, str) else p.date) <= end
        }
    except Exception:
        return {}


def _get_price_at_date(prices: dict[date, float], target: date, max_lookback: int = 5) -> float | None:
    """Get price at date with lookback for non-trading days."""
    for i in range(max_lookback):
        d = target - timedelta(days=i)
        if d in prices:
            return prices[d]
    return None


def _get_price_list_at_date(prices: dict[date, float], target: date, days: int = 252) -> list[float]:
    """Get price list ending at target date (most recent first)."""
    result = []
    current = target
    for _ in range(days + 30):  # Extra buffer
        if len(result) >= days:
            break
        if current in prices:
            result.append(prices[current])
        current -= timedelta(days=1)
    return result


def _next_trading_day(d: date) -> date:
    """Get next trading day (skip weekends)."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _get_vix_at_date(d: date) -> float:
    """Get VIX at date. Returns default if unavailable."""
    # Simplified - in production, would fetch historical VIX
    # For backtest, use moderate default
    return 18.0


def _count_no_price(prices: dict[str, dict[date, float]], d: date) -> int:
    """Count tickers with no price at date."""
    return sum(1 for p in prices.values() if _get_price_at_date(p, d) is None)


def _score_stocks_enhanced(
    tickers: list[str],
    prices: dict[str, dict[date, float]],
    as_of_date: date,
    regime_context: RegimeContext,
    config: EnhancedBacktestConfig,
    verbose: bool = False,
) -> list[dict]:
    """
    Score stocks using v3 enhanced scoring.

    Returns list of dicts with scoring details for each qualifying stock.
    """
    from adapters import YahooAdapter
    from domain.score_aggregator import StockData, score_stock
    from domain.risk import RiskFilters, PortfolioConstraints

    yahoo = YahooAdapter()
    scored: list[dict] = []

    risk_filters = RiskFilters(min_conviction=config.min_conviction)
    constraints = PortfolioConstraints(
        max_single_position=config.max_position_weight,
        min_single_position=config.min_position_weight,
        max_sector_exposure=config.max_sector_weight,
    )

    for ticker in tickers:
        try:
            ticker_prices = prices.get(ticker, {})
            current_price = _get_price_at_date(ticker_prices, as_of_date)

            if current_price is None:
                continue

            # Get fundamentals (limitation: current, not point-in-time)
            fund_data = {}
            try:
                fund_obs = yahoo.get_fundamentals(ticker)
                if fund_obs and len(fund_obs) > 0:
                    fund_data = fund_obs[0].data
            except Exception:
                pass

            sector = fund_data.get('sector', 'Technology')
            if sector is None:
                sector = 'Technology'

            # Calculate momentum from historical prices
            momentum_data = _calculate_momentum(ticker_prices, as_of_date)

            # Build StockData for v3 scoring
            stock_data = StockData(
                ticker=ticker,
                sector=sector,
                price=current_price,
                market_cap=fund_data.get('market_cap'),
                price_change_1m=momentum_data.get("change_1m"),
                price_change_12m=momentum_data.get("change_12m"),
                roe=fund_data.get('roe'),
                avg_volume=fund_data.get('volume_avg'),
            )

            # Score using v3
            enhanced = score_stock(
                data=stock_data,
                regime_context=regime_context,
                risk_filters=risk_filters,
                portfolio_constraints=constraints,
                today=as_of_date,
            )

            if enhanced.passes_filters and enhanced.conviction >= config.min_conviction:
                scored.append({
                    "ticker": ticker,
                    "score": enhanced.score,
                    "conviction": enhanced.conviction,
                    "position_size": enhanced.position_size,
                    "timeframe": enhanced.timeframe,
                    "sector": enhanced.sector,
                    "factor_scores": enhanced.factor_scores,
                    "factor_weights": {
                        "quality": enhanced.weights_used.quality,
                        "value": enhanced.weights_used.value,
                        "momentum": enhanced.weights_used.momentum,
                        "low_vol": enhanced.weights_used.low_vol,
                        "smart_money": enhanced.weights_used.smart_money,
                        "catalyst": enhanced.weights_used.catalyst,
                    },
                })

        except Exception as e:
            if verbose:
                print(f"    Error scoring {ticker}: {e}")
            continue

    # Sort by score descending
    scored.sort(key=lambda x: (x["score"], x["conviction"]), reverse=True)
    return scored


def _calculate_momentum(prices: dict[date, float], as_of_date: date) -> dict[str, float | None]:
    """Calculate momentum metrics at date."""
    result = {"change_1m": None, "change_12m": None}

    current = _get_price_at_date(prices, as_of_date)
    if current is None:
        return result

    price_1m = _get_price_at_date(prices, as_of_date - timedelta(days=30))
    if price_1m and price_1m > 0:
        result["change_1m"] = (current - price_1m) / price_1m

    price_12m = _get_price_at_date(prices, as_of_date - timedelta(days=365))
    if price_12m and price_12m > 0:
        result["change_12m"] = (current - price_12m) / price_12m

    return result


def _compute_correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x == 0 or denom_y == 0:
        return 0.0

    return num / (denom_x * denom_y)


# ============================================================================
# Performance Tracking Functions (Module 6.2)
# ============================================================================


def track_pick_performance(
    pick: EnhancedScore,
    entry_price: float,
    exit_price: float,
    holding_days: int,
) -> dict:
    """
    Track performance of a single pick.

    Returns dict with performance metrics and factor attribution.
    """
    return_pct = ((exit_price - entry_price) / entry_price) * 100

    # Factor contributions (proportional to weighted score contribution)
    total_weighted = sum(
        pick.factor_scores.get(f, 50) * getattr(pick.weights_used, f, 0)
        for f in ["quality", "value", "momentum", "low_vol", "smart_money", "catalyst"]
    )

    factor_contributions = {}
    for factor in ["quality", "value", "momentum", "low_vol", "smart_money", "catalyst"]:
        score = pick.factor_scores.get(factor, 50)
        weight = getattr(pick.weights_used, factor, 0)
        if total_weighted > 0:
            contribution_pct = (score * weight) / total_weighted
            factor_contributions[factor] = return_pct * contribution_pct
        else:
            factor_contributions[factor] = 0.0

    return {
        "ticker": pick.ticker,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "return_pct": return_pct,
        "holding_days": holding_days,
        "conviction": pick.conviction,
        "score": pick.score,
        "regime": pick.regime.value,
        "timeframe": pick.timeframe.value,
        "factor_scores": pick.factor_scores,
        "factor_contributions": factor_contributions,
        "is_winner": return_pct > 0,
    }


def analyze_picks_by_regime(
    picks_performance: list[dict],
) -> dict[str, dict]:
    """
    Analyze pick performance grouped by market regime.

    Returns performance stats for each regime.
    """
    by_regime: dict[str, list[dict]] = {}

    for p in picks_performance:
        regime = p.get("regime", "sideways")
        if regime not in by_regime:
            by_regime[regime] = []
        by_regime[regime].append(p)

    results = {}
    for regime, picks in by_regime.items():
        returns = [p["return_pct"] for p in picks]
        winners = [p for p in picks if p["is_winner"]]

        results[regime] = {
            "num_picks": len(picks),
            "total_return": sum(returns),
            "avg_return": statistics.mean(returns) if returns else 0.0,
            "win_rate": (len(winners) / len(picks) * 100) if picks else 0.0,
            "best_pick": max(picks, key=lambda p: p["return_pct"])["ticker"] if picks else None,
            "worst_pick": min(picks, key=lambda p: p["return_pct"])["ticker"] if picks else None,
        }

    return results


def analyze_factor_effectiveness(
    picks_performance: list[dict],
) -> dict[str, dict]:
    """
    Analyze which factors best predicted returns.

    Returns effectiveness metrics for each factor.
    """
    factors = ["quality", "value", "momentum", "low_vol", "smart_money", "catalyst"]
    results = {}

    for factor in factors:
        scores = []
        returns = []
        contributions = []

        for p in picks_performance:
            factor_scores = p.get("factor_scores", {})
            factor_contribs = p.get("factor_contributions", {})

            if factor in factor_scores:
                scores.append(factor_scores[factor])
                returns.append(p["return_pct"])
                contributions.append(factor_contribs.get(factor, 0))

        if len(scores) < 2:
            results[factor] = {"correlation": 0.0, "contribution": 0.0, "avg_score": 50.0}
            continue

        corr = _compute_correlation(scores, returns)

        results[factor] = {
            "correlation": corr,
            "contribution": sum(contributions),
            "avg_score": statistics.mean(scores),
            "score_std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        }

    return results
