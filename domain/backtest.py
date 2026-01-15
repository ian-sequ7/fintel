"""
Backtesting Framework for Stock Picking Strategy Validation.

Point-in-time simulation that scores stocks using historical data and tracks
performance against benchmark (SPY). Calculates alpha, Sharpe ratio, hit rate,
and other performance metrics.

Key Design Decisions:
1. Monthly rebalance on 1st trading day
2. Equal-weight picks (no position sizing)
3. No transaction costs modeled (conservative bias)
4. Uses current fundamentals (lookahead bias for value/quality - documented limitation)

Academic references:
- Jegadeesh & Titman (1993): 12-1 month momentum
- Novy-Marx (2013): Gross profitability
- Fama & French (2015): Five-factor model

Usage:
    from domain.backtest import run_backtest

    result = run_backtest(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        timeframe="medium",
    )
    print(result.summary())
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Literal

from .analysis_types import ConvictionScore, MacroContext, StockMetrics
from .models import Timeframe


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for backtest execution."""

    # Pick selection
    top_n_picks: int = 5  # Number of picks per rebalance
    min_conviction: float = 0.6  # Minimum conviction score (0-1)

    # Holding period
    holding_days: int = 21  # ~1 month trading days

    # Risk management
    max_sector_concentration: float = 0.40  # Max 40% in one sector
    min_liquidity_usd: float = 10_000_000  # $10M daily volume

    # Benchmark
    benchmark_ticker: str = "SPY"


# ============================================================================
# Data Types
# ============================================================================


class TradeOutcome(str, Enum):
    """Outcome of a completed trade."""
    WIN = "win"       # Positive return
    LOSS = "loss"     # Negative return
    FLAT = "flat"     # ~0% return (within ±0.5%)


@dataclass
class BacktestTrade:
    """Record of a single trade in the backtest."""

    ticker: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    conviction: float
    timeframe: str
    sector: str | None

    # Benchmark comparison
    benchmark_entry: float
    benchmark_exit: float

    @property
    def return_pct(self) -> float:
        """Percentage return on trade."""
        if self.entry_price <= 0:
            return 0.0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    @property
    def benchmark_return_pct(self) -> float:
        """Benchmark return over same period."""
        if self.benchmark_entry <= 0:
            return 0.0
        return ((self.benchmark_exit - self.benchmark_entry) / self.benchmark_entry) * 100

    @property
    def alpha(self) -> float:
        """Excess return over benchmark."""
        return self.return_pct - self.benchmark_return_pct

    @property
    def outcome(self) -> TradeOutcome:
        """Classify trade outcome."""
        if self.return_pct > 0.5:
            return TradeOutcome.WIN
        elif self.return_pct < -0.5:
            return TradeOutcome.LOSS
        return TradeOutcome.FLAT

    @property
    def beat_benchmark(self) -> bool:
        """Did this trade beat the benchmark?"""
        return self.return_pct > self.benchmark_return_pct


@dataclass
class MonthlyReturn:
    """Returns for a single month."""
    month: date  # First day of month
    portfolio_return: float  # Percentage
    benchmark_return: float  # Percentage
    num_picks: int
    top_performer: str | None
    worst_performer: str | None


@dataclass
class BacktestResult:
    """Complete results from a backtest run."""

    # Configuration
    start_date: date
    end_date: date
    timeframe: str
    config: BacktestConfig

    # Raw data
    trades: list[BacktestTrade] = field(default_factory=list)
    monthly_returns: list[MonthlyReturn] = field(default_factory=list)

    # Execution metadata
    executed_at: datetime = field(default_factory=datetime.now)
    tickers_analyzed: int = 0

    # -------------------------------------------------------------------------
    # Aggregate Metrics
    # -------------------------------------------------------------------------

    @property
    def total_trades(self) -> int:
        """Total number of trades executed."""
        return len(self.trades)

    @property
    def total_return(self) -> float:
        """Total portfolio return (compounded)."""
        if not self.monthly_returns:
            return 0.0
        cumulative = 1.0
        for mr in self.monthly_returns:
            cumulative *= (1 + mr.portfolio_return / 100)
        return (cumulative - 1) * 100

    @property
    def benchmark_return(self) -> float:
        """Total benchmark return (compounded)."""
        if not self.monthly_returns:
            return 0.0
        cumulative = 1.0
        for mr in self.monthly_returns:
            cumulative *= (1 + mr.benchmark_return / 100)
        return (cumulative - 1) * 100

    @property
    def alpha(self) -> float:
        """Total excess return over benchmark."""
        return self.total_return - self.benchmark_return

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
        wins = sum(1 for t in self.trades if t.outcome == TradeOutcome.WIN)
        return (wins / len(self.trades)) * 100

    @property
    def avg_trade_return(self) -> float:
        """Average return per trade."""
        if not self.trades:
            return 0.0
        return statistics.mean(t.return_pct for t in self.trades)

    @property
    def avg_alpha_per_trade(self) -> float:
        """Average excess return per trade."""
        if not self.trades:
            return 0.0
        return statistics.mean(t.alpha for t in self.trades)

    @property
    def sharpe_ratio(self) -> float:
        """
        Sharpe ratio based on monthly returns.

        Annualized: (mean - risk_free) / std * sqrt(12)
        Assumes risk-free rate of 4% (Treasury rate environment).
        """
        if len(self.monthly_returns) < 2:
            return 0.0

        monthly_returns = [mr.portfolio_return for mr in self.monthly_returns]
        monthly_rf = 4.0 / 12  # ~0.33% monthly risk-free

        excess_returns = [r - monthly_rf for r in monthly_returns]
        mean_excess = statistics.mean(excess_returns)
        std_dev = statistics.stdev(excess_returns) if len(excess_returns) > 1 else 1.0

        if std_dev == 0:
            return 0.0

        return (mean_excess / std_dev) * math.sqrt(12)  # Annualize

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough decline in portfolio value."""
        if not self.monthly_returns:
            return 0.0

        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0

        for mr in self.monthly_returns:
            cumulative *= (1 + mr.portfolio_return / 100)
            peak = max(peak, cumulative)
            drawdown = (peak - cumulative) / peak * 100
            max_dd = max(max_dd, drawdown)

        return max_dd

    @property
    def win_loss_ratio(self) -> float:
        """Average winner size / average loser size."""
        winners = [t.return_pct for t in self.trades if t.return_pct > 0]
        losers = [abs(t.return_pct) for t in self.trades if t.return_pct < 0]

        if not winners or not losers:
            return 0.0

        avg_win = statistics.mean(winners)
        avg_loss = statistics.mean(losers)

        if avg_loss == 0:
            return float('inf')

        return avg_win / avg_loss

    @property
    def best_trade(self) -> BacktestTrade | None:
        """Highest returning trade."""
        if not self.trades:
            return None
        return max(self.trades, key=lambda t: t.return_pct)

    @property
    def worst_trade(self) -> BacktestTrade | None:
        """Lowest returning trade."""
        if not self.trades:
            return None
        return min(self.trades, key=lambda t: t.return_pct)

    # -------------------------------------------------------------------------
    # Output Methods
    # -------------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable summary of backtest results."""
        lines = [
            "=" * 60,
            f"BACKTEST RESULTS: {self.timeframe.upper()} PICKS",
            "=" * 60,
            f"Period: {self.start_date} to {self.end_date}",
            f"Total Trades: {self.total_trades}",
            f"Tickers Analyzed: {self.tickers_analyzed}",
            "",
            "PERFORMANCE",
            "-" * 40,
            f"Total Return:     {self.total_return:+.2f}%",
            f"Benchmark (SPY):  {self.benchmark_return:+.2f}%",
            f"Alpha:            {self.alpha:+.2f}%",
            "",
            f"Hit Rate:         {self.hit_rate:.1f}% (beat benchmark)",
            f"Win Rate:         {self.win_rate:.1f}% (positive return)",
            f"Avg Trade Return: {self.avg_trade_return:+.2f}%",
            f"Avg Alpha/Trade:  {self.avg_alpha_per_trade:+.2f}%",
            "",
            "RISK METRICS",
            "-" * 40,
            f"Sharpe Ratio:     {self.sharpe_ratio:.2f}",
            f"Max Drawdown:     {self.max_drawdown:.2f}%",
            f"Win/Loss Ratio:   {self.win_loss_ratio:.2f}",
            "",
        ]

        if self.best_trade:
            lines.append(f"Best Trade:  {self.best_trade.ticker} {self.best_trade.return_pct:+.1f}%")
        if self.worst_trade:
            lines.append(f"Worst Trade: {self.worst_trade.ticker} {self.worst_trade.return_pct:+.1f}%")

        lines.extend([
            "",
            "LIMITATIONS",
            "-" * 40,
            "• Uses current fundamentals (lookahead bias for value/quality)",
            "• No transaction costs modeled",
            "• Survivorship bias if universe changed",
            "=" * 60,
        ])

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "timeframe": self.timeframe,
            "total_trades": self.total_trades,
            "tickers_analyzed": self.tickers_analyzed,
            "performance": {
                "total_return": round(self.total_return, 2),
                "benchmark_return": round(self.benchmark_return, 2),
                "alpha": round(self.alpha, 2),
                "hit_rate": round(self.hit_rate, 1),
                "win_rate": round(self.win_rate, 1),
                "avg_trade_return": round(self.avg_trade_return, 2),
                "avg_alpha_per_trade": round(self.avg_alpha_per_trade, 2),
            },
            "risk": {
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "max_drawdown": round(self.max_drawdown, 2),
                "win_loss_ratio": round(self.win_loss_ratio, 2),
            },
            "best_trade": {
                "ticker": self.best_trade.ticker,
                "return_pct": round(self.best_trade.return_pct, 2),
            } if self.best_trade else None,
            "worst_trade": {
                "ticker": self.worst_trade.ticker,
                "return_pct": round(self.worst_trade.return_pct, 2),
            } if self.worst_trade else None,
            "monthly_returns": [
                {
                    "month": mr.month.isoformat(),
                    "portfolio": round(mr.portfolio_return, 2),
                    "benchmark": round(mr.benchmark_return, 2),
                    "picks": mr.num_picks,
                }
                for mr in self.monthly_returns
            ],
            "limitations": [
                "Uses current fundamentals (lookahead bias for value/quality)",
                "No transaction costs modeled",
                "Survivorship bias if universe changed",
            ],
            "executed_at": self.executed_at.isoformat(),
        }


# ============================================================================
# Backtest Engine
# ============================================================================


def run_backtest(
    start_date: date,
    end_date: date,
    timeframe: Literal["short", "medium", "long"] = "medium",
    config: BacktestConfig | None = None,
    *,
    universe: list[str] | None = None,
    verbose: bool = False,
) -> BacktestResult:
    """
    Run historical backtest of stock picking strategy.

    Simulates monthly rebalancing where:
    1. On 1st trading day of month, score all stocks in universe
    2. Select top N picks by conviction score
    3. Hold for 1 month, then measure returns
    4. Compare against SPY benchmark

    Args:
        start_date: Backtest start date
        end_date: Backtest end date
        timeframe: Pick timeframe ("short", "medium", "long")
        config: Backtest configuration (uses defaults if None)
        universe: List of tickers to backtest (uses default if None)
        verbose: Print progress messages

    Returns:
        BacktestResult with all trades and metrics

    Example:
        result = run_backtest(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            timeframe="medium",
        )
        print(result.summary())
    """
    # Lazy imports to avoid circular dependencies
    from adapters import YahooAdapter
    from db import get_db

    if config is None:
        config = BacktestConfig()

    # Get universe if not provided
    if universe is None:
        universe = _get_backtest_universe()

    if verbose:
        print(f"Backtesting {len(universe)} tickers from {start_date} to {end_date}")

    # Initialize result
    result = BacktestResult(
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        config=config,
        tickers_analyzed=len(universe),
    )

    # Get price history from database
    db = get_db()
    yahoo = YahooAdapter()

    # Get benchmark prices - always fetch fresh from Yahoo for full coverage
    benchmark_prices = _fetch_benchmark_prices(yahoo, config.benchmark_ticker, start_date, end_date)

    # Fall back to DB if Yahoo fails
    if not benchmark_prices:
        benchmark_prices = _get_price_series(db, config.benchmark_ticker, start_date, end_date)

    if not benchmark_prices:
        raise ValueError(f"No benchmark data for {config.benchmark_ticker}")

    # Get all stock prices
    all_prices: dict[str, dict[date, float]] = {}
    for ticker in universe:
        prices = _get_price_series(db, ticker, start_date, end_date)
        if prices:
            all_prices[ticker] = prices

    if verbose:
        print(f"Loaded price data for {len(all_prices)} tickers")

    # Iterate through months
    current = _first_trading_day_of_month(start_date)

    while current < end_date:
        next_month = _first_trading_day_of_month(
            (current.replace(day=28) + timedelta(days=5)).replace(day=1)
        )

        if next_month > end_date:
            break

        # Score stocks at this point in time
        picks = _score_stocks_point_in_time(
            tickers=list(all_prices.keys()),
            prices=all_prices,
            as_of_date=current,
            timeframe=timeframe,
            config=config,
            verbose=verbose,
        )

        if not picks:
            current = next_month
            continue

        # Get benchmark prices for this month
        bench_entry = _get_price_at_date(benchmark_prices, current)
        bench_exit = _get_price_at_date(benchmark_prices, next_month)

        if bench_entry is None or bench_exit is None:
            current = next_month
            continue

        # Create trades for top picks
        month_trades: list[BacktestTrade] = []

        for pick in picks[:config.top_n_picks]:
            ticker = pick["ticker"]

            if ticker not in all_prices:
                continue

            entry_price = _get_price_at_date(all_prices[ticker], current)
            exit_price = _get_price_at_date(all_prices[ticker], next_month)

            if entry_price is None or exit_price is None:
                continue

            trade = BacktestTrade(
                ticker=ticker,
                entry_date=current,
                exit_date=next_month,
                entry_price=entry_price,
                exit_price=exit_price,
                conviction=pick["conviction"],
                timeframe=timeframe,
                sector=pick.get("sector"),
                benchmark_entry=bench_entry,
                benchmark_exit=bench_exit,
            )

            month_trades.append(trade)
            result.trades.append(trade)

        # Calculate monthly return (equal-weighted portfolio)
        if month_trades:
            portfolio_return = statistics.mean(t.return_pct for t in month_trades)
            benchmark_return = ((bench_exit - bench_entry) / bench_entry) * 100

            best = max(month_trades, key=lambda t: t.return_pct)
            worst = min(month_trades, key=lambda t: t.return_pct)

            result.monthly_returns.append(MonthlyReturn(
                month=current,
                portfolio_return=portfolio_return,
                benchmark_return=benchmark_return,
                num_picks=len(month_trades),
                top_performer=best.ticker,
                worst_performer=worst.ticker,
            ))

        if verbose:
            print(f"  {current}: {len(month_trades)} trades")

        current = next_month

    return result


# ============================================================================
# Helper Functions
# ============================================================================


def _get_backtest_universe() -> list[str]:
    """Get default universe for backtesting."""
    from adapters.universe import get_combined_universe
    return get_combined_universe()


def _get_price_series(db, ticker: str, start: date, end: date) -> dict[date, float]:
    """Get price series from database."""
    try:
        points = db.get_price_history(ticker, days=730)  # ~2 years
        return {
            datetime.strptime(p.date, "%Y-%m-%d").date() if isinstance(p.date, str) else p.date: p.close
            for p in points
            if start <= (datetime.strptime(p.date, "%Y-%m-%d").date() if isinstance(p.date, str) else p.date) <= end
        }
    except Exception:
        return {}


def _fetch_benchmark_prices(yahoo, ticker: str, start: date, end: date) -> dict[date, float]:
    """Fetch benchmark prices from Yahoo if not in DB."""
    try:
        # Yahoo returns most recent N days from today
        # Calculate days from today back to start date
        today = date.today()
        days_from_start = (today - start).days + 60  # Extra buffer

        history = yahoo.get_price_history(ticker, days=days_from_start)

        result = {}
        for h in history:
            try:
                d = datetime.strptime(h["time"], "%Y-%m-%d").date()
                if start <= d <= end:
                    result[d] = float(h["close"])
            except (KeyError, ValueError):
                continue

        return result
    except Exception:
        return {}


def _get_price_at_date(prices: dict[date, float], target: date, max_lookback: int = 5) -> float | None:
    """Get price at date, allowing for lookback on non-trading days."""
    for i in range(max_lookback):
        d = target - timedelta(days=i)
        if d in prices:
            return prices[d]
    return None


def _first_trading_day_of_month(d: date) -> date:
    """Get first trading day of the month (approximate - skip weekends)."""
    first = d.replace(day=1)

    # Skip weekends
    while first.weekday() >= 5:  # Saturday=5, Sunday=6
        first += timedelta(days=1)

    return first


def _score_stocks_point_in_time(
    tickers: list[str],
    prices: dict[str, dict[date, float]],
    as_of_date: date,
    timeframe: str,
    config: BacktestConfig,
    verbose: bool = False,
) -> list[dict]:
    """
    Score stocks using data available at point in time.

    NOTE: This uses current fundamentals (lookahead bias for value/quality factors).
    Historical fundamentals would require IBES/FactSet data.
    """
    from adapters import YahooAdapter
    from adapters.cache import get_cache
    from domain.scoring import (
        score_stock,
        ScoringWeights,
        TimeframeWeights,
        ScoringThresholds,
    )
    from domain.analysis_types import MacroContext

    # Get timeframe-specific weights
    if timeframe == "short":
        weights = TimeframeWeights.for_short()
    elif timeframe == "long":
        weights = TimeframeWeights.for_long()
    else:
        weights = TimeframeWeights.for_medium()

    # Create neutral macro context (we don't have historical macro data)
    macro = MacroContext()

    # Sector P/E averages for relative valuation
    sector_pe_averages = {
        "technology": 28.0,
        "healthcare": 22.0,
        "financials": 12.0,
        "consumer discretionary": 20.0,
        "consumer staples": 18.0,
        "industrials": 18.0,
        "energy": 10.0,
        "utilities": 15.0,
        "materials": 14.0,
        "real estate": 35.0,
        "communication services": 20.0,
    }

    yahoo = YahooAdapter()
    scored: list[dict] = []

    # Initialize cache for score results
    cache = get_cache()
    cache_ttl = timedelta(hours=24)

    for ticker in tickers:
        try:
            # Check cache first
            cached = cache.get(
                "backtest_score",
                ticker=ticker,
                date=as_of_date.isoformat(),
                timeframe=timeframe
            )
            if cached is not None:
                scored.append(cached)
                continue

            # Get price at this date
            ticker_prices = prices.get(ticker, {})
            current_price = _get_price_at_date(ticker_prices, as_of_date)

            if current_price is None:
                continue

            # Calculate momentum using historical prices
            momentum_data = _calculate_momentum_at_date(ticker_prices, as_of_date)

            # Get fundamentals (LIMITATION: current data, not point-in-time)
            fund_data = {}
            try:
                fund_obs = yahoo.get_fundamentals(ticker)
                if fund_obs and len(fund_obs) > 0:
                    fund_data = fund_obs[0].data
            except Exception:
                pass

            # Get sector
            sector = fund_data.get('sector', 'technology')
            sector = sector.lower() if sector else 'technology'
            sector_avg_pe = sector_pe_averages.get(sector, 20.0)

            # Build StockMetrics
            from domain.analysis_types import StockMetrics

            metrics = StockMetrics(
                ticker=ticker,
                price=current_price,
                market_cap=fund_data.get('market_cap'),
                pe_trailing=fund_data.get('pe_trailing'),
                pe_forward=fund_data.get('pe_forward'),
                price_change_1m=momentum_data.get("change_1m"),
                price_change_3m=momentum_data.get("change_3m"),
                price_change_6m=momentum_data.get("change_6m"),
                price_change_12m=momentum_data.get("change_12m"),
                profit_margin=fund_data.get('profit_margin'),
            )

            # Score the stock
            pick = score_stock(
                metrics=metrics,
                macro=macro,
                sector=sector,
                sector_avg_pe=sector_avg_pe,
                weights=weights,
            )

            if pick.conviction_normalized >= config.min_conviction:
                result = {
                    "ticker": ticker,
                    "conviction": pick.conviction_normalized,
                    "sector": pick.sector,
                }
                # Cache the score result
                cache.set(
                    "backtest_score",
                    result,
                    cache_ttl,
                    ticker=ticker,
                    date=as_of_date.isoformat(),
                    timeframe=timeframe
                )
                scored.append(result)

        except Exception as e:
            if verbose:
                print(f"    Error scoring {ticker}: {e}")
            continue

    # Sort by conviction descending
    scored.sort(key=lambda x: x["conviction"], reverse=True)

    return scored


def _calculate_momentum_at_date(
    prices: dict[date, float],
    as_of_date: date,
) -> dict[str, float | None]:
    """Calculate momentum metrics using prices available at date."""
    result = {
        "change_1m": None,
        "change_3m": None,
        "change_6m": None,
        "change_12m": None,
    }

    current_price = _get_price_at_date(prices, as_of_date)
    if current_price is None:
        return result

    # 1 month ago (~21 trading days)
    price_1m = _get_price_at_date(prices, as_of_date - timedelta(days=30))
    if price_1m:
        result["change_1m"] = (current_price - price_1m) / price_1m

    # 3 months ago (~63 trading days)
    price_3m = _get_price_at_date(prices, as_of_date - timedelta(days=90))
    if price_3m:
        result["change_3m"] = (current_price - price_3m) / price_3m

    # 6 months ago (~126 trading days)
    price_6m = _get_price_at_date(prices, as_of_date - timedelta(days=180))
    if price_6m:
        result["change_6m"] = (current_price - price_6m) / price_6m

    # 12 months ago (~252 trading days)
    price_12m = _get_price_at_date(prices, as_of_date - timedelta(days=365))
    if price_12m:
        result["change_12m"] = (current_price - price_12m) / price_12m

    return result


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    """CLI entry point for running backtests."""
    import argparse

    parser = argparse.ArgumentParser(description="Backtest stock picking strategy")
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=date(2024, 7, 1),
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        default=date(2025, 12, 31),
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--timeframe",
        choices=["short", "medium", "long"],
        default="medium",
        help="Pick timeframe",
    )
    parser.add_argument(
        "--picks",
        type=int,
        default=5,
        help="Number of picks per month",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print progress",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    config = BacktestConfig(top_n_picks=args.picks)

    result = run_backtest(
        start_date=args.start,
        end_date=args.end,
        timeframe=args.timeframe,
        config=config,
        verbose=args.verbose,
    )

    if args.json:
        import json
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary())


if __name__ == "__main__":
    main()
