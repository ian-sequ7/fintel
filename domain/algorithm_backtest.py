"""
Algorithm backtest engine for validating trading strategies.
Default period: 1 year of historical data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any

from domain.algorithm_signals import (
    AlgorithmSignal,
    AlgorithmSignalType,
    IndicatorSnapshot,
)
from domain.strategies.base import StrategyInput, TradingStrategy


class PositionState(Enum):
    """Current position state."""

    FLAT = auto()
    LONG = auto()
    SHORT = auto()


@dataclass
class BacktestTrade:
    """Record of a completed trade."""

    ticker: str
    entry_date: str
    entry_price: float
    entry_signal: AlgorithmSignalType
    exit_date: str
    exit_price: float
    exit_signal: AlgorithmSignalType
    return_pct: float
    holding_days: int
    pnl: float
    indicators_at_entry: IndicatorSnapshot


@dataclass
class BacktestMetrics:
    """Performance metrics from backtest."""

    total_return: float
    benchmark_return: float
    alpha: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_days: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float


@dataclass
class EquityCurvePoint:
    """Point on the equity curve."""

    date: str
    equity: float
    drawdown: float


@dataclass
class BacktestConfig:
    """Configuration for running a backtest."""

    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    position_size_pct: float = 0.2  # 20% per trade
    commission_pct: float = 0.001  # 0.1% per trade
    slippage_pct: float = 0.0005  # 0.05% slippage


@dataclass
class BacktestResult:
    """Complete backtest results."""

    algorithm_id: str
    algorithm_name: str
    config: BacktestConfig
    tickers_tested: list[str]
    metrics: BacktestMetrics
    trades: list[BacktestTrade]
    equity_curve: list[EquityCurvePoint]
    signal_breakdown: dict[str, int]
    executed_at: datetime = field(default_factory=datetime.now)


@dataclass
class _Position:
    """Internal position tracking."""

    state: PositionState
    ticker: str
    entry_date: str
    entry_price: float
    entry_signal: AlgorithmSignalType
    shares: float
    indicators_at_entry: IndicatorSnapshot


def create_default_config(lookback_days: int = 365) -> BacktestConfig:
    """Create default backtest config for 1 year lookback."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    return BacktestConfig(start_date=start_date, end_date=end_date)


def run_backtest(
    strategy: TradingStrategy,
    price_data: dict[str, list[dict[str, Any]]],
    config: BacktestConfig,
    benchmark_data: list[dict[str, Any]] | None = None,
) -> BacktestResult:
    """
    Main entry point for backtesting a trading strategy.

    Args:
        strategy: TradingStrategy instance to test
        price_data: Dictionary mapping tickers to OHLCV data
            Format: {"AAPL": [{"date": "2024-01-01", "open": 100.0, "high": 101.0,
                               "low": 99.0, "close": 100.5, "volume": 1000000}, ...]}
        config: BacktestConfig with test parameters
        benchmark_data: Optional SPY benchmark data in same format as price_data values

    Returns:
        BacktestResult with complete performance analysis
    """
    equity = config.initial_capital
    position: _Position | None = None
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityCurvePoint] = []
    signal_breakdown: dict[str, int] = {}

    # Build date-indexed data structure
    all_dates = _get_sorted_dates(price_data)
    date_data = _build_date_index(price_data, all_dates)

    # Filter dates within backtest period
    test_dates = [
        d
        for d in all_dates
        if config.start_date <= datetime.strptime(d, "%Y-%m-%d") <= config.end_date
    ]

    # WHY: Pre-build historical cache to avoid O(n²) repeated array building
    # Converts 12,600 calls (252 days × 50 tickers) to 252 incremental updates
    historical_cache = _initialize_historical_cache(price_data.keys())

    peak_equity = equity

    for i, date in enumerate(test_dates):
        if date not in date_data:
            continue

        # Update historical cache with today's data for all tickers
        _update_historical_cache(historical_cache, date_data[date])

        # Generate signals for each ticker on this date
        for ticker, bar in date_data[date].items():
            # Use pre-built historical data (O(1) lookup vs O(n) rebuild)
            hist_data = historical_cache[ticker]

            if not hist_data["closes"]:
                continue

            # Create strategy input
            strategy_input = StrategyInput(
                ticker=ticker,
                opens=hist_data["opens"].copy(),
                highs=hist_data["highs"].copy(),
                lows=hist_data["lows"].copy(),
                closes=hist_data["closes"].copy(),
                volumes=hist_data["volumes"].copy(),
            )

            # Generate signal
            signal = strategy.generate_signal(strategy_input)

            if signal:
                signal_key = signal.signal_type.name
                signal_breakdown[signal_key] = signal_breakdown.get(signal_key, 0) + 1

                # Process signal
                if position is None and signal.signal_type == AlgorithmSignalType.LONG_ENTRY:
                    # Open long position
                    executed_price, commission = _execute_trade(
                        PositionState.FLAT, signal, bar["close"], config
                    )
                    shares = (equity * config.position_size_pct) / executed_price
                    position = _Position(
                        state=PositionState.LONG,
                        ticker=ticker,
                        entry_date=date,
                        entry_price=executed_price,
                        entry_signal=signal.signal_type,
                        shares=shares,
                        indicators_at_entry=signal.indicators,
                    )
                    equity -= commission

                elif (
                    position
                    and position.ticker == ticker
                    and position.state == PositionState.LONG
                    and signal.signal_type
                    in [
                        AlgorithmSignalType.LONG_EXIT,
                        AlgorithmSignalType.STOP_LOSS,
                        AlgorithmSignalType.TAKE_PROFIT,
                    ]
                ):
                    # Close long position
                    executed_price, commission = _execute_trade(
                        position.state, signal, bar["close"], config
                    )
                    pnl = (executed_price - position.entry_price) * position.shares
                    equity += pnl - commission
                    return_pct = (executed_price - position.entry_price) / position.entry_price

                    entry_dt = datetime.strptime(position.entry_date, "%Y-%m-%d")
                    exit_dt = datetime.strptime(date, "%Y-%m-%d")
                    holding_days = (exit_dt - entry_dt).days

                    trades.append(
                        BacktestTrade(
                            ticker=ticker,
                            entry_date=position.entry_date,
                            entry_price=position.entry_price,
                            entry_signal=position.entry_signal,
                            exit_date=date,
                            exit_price=executed_price,
                            exit_signal=signal.signal_type,
                            return_pct=return_pct,
                            holding_days=holding_days,
                            pnl=pnl,
                            indicators_at_entry=position.indicators_at_entry,
                        )
                    )
                    position = None

                elif position is None and signal.signal_type == AlgorithmSignalType.SHORT_ENTRY:
                    # Open short position
                    executed_price, commission = _execute_trade(
                        PositionState.FLAT, signal, bar["close"], config
                    )
                    shares = (equity * config.position_size_pct) / executed_price
                    position = _Position(
                        state=PositionState.SHORT,
                        ticker=ticker,
                        entry_date=date,
                        entry_price=executed_price,
                        entry_signal=signal.signal_type,
                        shares=shares,
                        indicators_at_entry=signal.indicators,
                    )
                    equity -= commission

                elif (
                    position
                    and position.ticker == ticker
                    and position.state == PositionState.SHORT
                    and signal.signal_type
                    in [
                        AlgorithmSignalType.SHORT_EXIT,
                        AlgorithmSignalType.STOP_LOSS,
                        AlgorithmSignalType.TAKE_PROFIT,
                    ]
                ):
                    # Close short position
                    executed_price, commission = _execute_trade(
                        position.state, signal, bar["close"], config
                    )
                    pnl = (position.entry_price - executed_price) * position.shares
                    equity += pnl - commission
                    return_pct = (position.entry_price - executed_price) / position.entry_price

                    entry_dt = datetime.strptime(position.entry_date, "%Y-%m-%d")
                    exit_dt = datetime.strptime(date, "%Y-%m-%d")
                    holding_days = (exit_dt - entry_dt).days

                    trades.append(
                        BacktestTrade(
                            ticker=ticker,
                            entry_date=position.entry_date,
                            entry_price=position.entry_price,
                            entry_signal=position.entry_signal,
                            exit_date=date,
                            exit_price=executed_price,
                            exit_signal=signal.signal_type,
                            return_pct=return_pct,
                            holding_days=holding_days,
                            pnl=pnl,
                            indicators_at_entry=position.indicators_at_entry,
                        )
                    )
                    position = None

        # Update equity curve
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
        equity_curve.append(
            EquityCurvePoint(date=date, equity=equity, drawdown=drawdown)
        )

    # Calculate benchmark returns
    benchmark_returns = _calculate_benchmark_returns(
        benchmark_data, test_dates, config
    ) if benchmark_data else []

    # Calculate metrics
    metrics = _calculate_metrics(trades, equity_curve, config, benchmark_returns)

    return BacktestResult(
        algorithm_id=strategy.algorithm_id,
        algorithm_name=strategy.name,
        config=config,
        tickers_tested=list(price_data.keys()),
        metrics=metrics,
        trades=trades,
        equity_curve=equity_curve,
        signal_breakdown=signal_breakdown,
    )


def _execute_trade(
    position_state: PositionState,
    signal: AlgorithmSignal,
    current_price: float,
    config: BacktestConfig,
) -> tuple[float, float]:
    """
    Apply commission and slippage to a trade.

    Args:
        position_state: Current position state
        signal: Trading signal being executed
        current_price: Current market price
        config: Backtest configuration

    Returns:
        (executed_price, commission_cost)
    """
    # WHY: Slippage direction depends on whether buying or selling
    if signal.signal_type in [
        AlgorithmSignalType.LONG_ENTRY,
        AlgorithmSignalType.SHORT_EXIT,
    ]:
        # Buying: slippage increases price
        slippage_multiplier = 1.0 + config.slippage_pct
    else:
        # Selling: slippage decreases price
        slippage_multiplier = 1.0 - config.slippage_pct

    executed_price = current_price * slippage_multiplier
    commission = executed_price * config.commission_pct

    return executed_price, commission


def _calculate_metrics(
    trades: list[BacktestTrade],
    equity_curve: list[EquityCurvePoint],
    config: BacktestConfig,
    benchmark_returns: list[float],
) -> BacktestMetrics:
    """
    Compute performance metrics from backtest results.

    Args:
        trades: List of completed trades
        equity_curve: Daily equity values
        config: Backtest configuration
        benchmark_returns: Daily benchmark returns

    Returns:
        BacktestMetrics with all computed metrics
    """
    if not trades:
        return BacktestMetrics(
            total_return=0.0,
            benchmark_return=0.0,
            alpha=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            avg_holding_days=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            best_trade=0.0,
            worst_trade=0.0,
        )

    # Total return
    final_equity = equity_curve[-1].equity if equity_curve else config.initial_capital
    total_return = (final_equity - config.initial_capital) / config.initial_capital

    # Benchmark return
    benchmark_return = sum(benchmark_returns) if benchmark_returns else 0.0

    # Alpha
    alpha = total_return - benchmark_return

    # Daily returns
    daily_returns = []
    for i in range(1, len(equity_curve)):
        ret = (
            (equity_curve[i].equity - equity_curve[i - 1].equity)
            / equity_curve[i - 1].equity
        )
        daily_returns.append(ret)

    # Sharpe ratio
    if daily_returns:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(
            daily_returns
        )
        std_dev = variance**0.5
        sharpe_ratio = (
            (mean_return / std_dev) * (252**0.5) if std_dev > 0 else 0.0
        )
    else:
        sharpe_ratio = 0.0

    # Sortino ratio
    downside_returns = [r for r in daily_returns if r < 0]
    if downside_returns:
        mean_return = sum(daily_returns) / len(daily_returns)
        downside_variance = sum(r**2 for r in downside_returns) / len(
            downside_returns
        )
        downside_std = downside_variance**0.5
        sortino_ratio = (
            (mean_return / downside_std) * (252**0.5) if downside_std > 0 else 0.0
        )
    else:
        sortino_ratio = sharpe_ratio

    # Max drawdown
    max_drawdown = max((point.drawdown for point in equity_curve), default=0.0)

    # Trade statistics
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl < 0]

    win_rate = len(winning_trades) / len(trades) if trades else 0.0

    gross_profit = sum(t.pnl for t in winning_trades)
    gross_loss = abs(sum(t.pnl for t in losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    avg_holding_days = (
        sum(t.holding_days for t in trades) / len(trades) if trades else 0.0
    )

    avg_win = (
        sum(t.pnl for t in winning_trades) / len(winning_trades)
        if winning_trades
        else 0.0
    )
    avg_loss = (
        sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0.0
    )

    best_trade = max((t.pnl for t in trades), default=0.0)
    worst_trade = min((t.pnl for t in trades), default=0.0)

    return BacktestMetrics(
        total_return=total_return,
        benchmark_return=benchmark_return,
        alpha=alpha,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=len(trades),
        avg_holding_days=avg_holding_days,
        avg_win=avg_win,
        avg_loss=avg_loss,
        best_trade=best_trade,
        worst_trade=worst_trade,
    )


def _get_sorted_dates(price_data: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Extract and sort all unique dates from price data."""
    all_dates = set()
    for ticker_data in price_data.values():
        for bar in ticker_data:
            all_dates.add(bar["date"])
    return sorted(all_dates)


def _build_date_index(
    price_data: dict[str, list[dict[str, Any]]], all_dates: list[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Build date -> ticker -> bar mapping for efficient lookup."""
    date_index: dict[str, dict[str, dict[str, Any]]] = {}
    for ticker, bars in price_data.items():
        for bar in bars:
            date = bar["date"]
            if date not in date_index:
                date_index[date] = {}
            date_index[date][ticker] = bar
    return date_index


def _initialize_historical_cache(
    tickers: Any,
) -> dict[str, dict[str, list[float]]]:
    """
    Initialize empty historical data cache for each ticker.

    Returns:
        Dictionary mapping ticker to OHLCV arrays that will be built incrementally
    """
    cache: dict[str, dict[str, list[float]]] = {}
    for ticker in tickers:
        cache[ticker] = {
            "opens": [],
            "highs": [],
            "lows": [],
            "closes": [],
            "volumes": [],
        }
    return cache


def _update_historical_cache(
    cache: dict[str, dict[str, list[float]]],
    date_bars: dict[str, dict[str, Any]],
) -> None:
    """
    Update historical cache with new bar data for current date.

    WHY: Incremental append is O(1) vs rebuilding entire array which is O(n)

    Args:
        cache: Historical cache to update in-place
        date_bars: Ticker -> bar mapping for current date
    """
    for ticker, bar in date_bars.items():
        if ticker in cache:
            cache[ticker]["opens"].append(bar["open"])
            cache[ticker]["highs"].append(bar["high"])
            cache[ticker]["lows"].append(bar["low"])
            cache[ticker]["closes"].append(bar["close"])
            cache[ticker]["volumes"].append(bar["volume"])


def _build_historical_data(
    ticker: str,
    ticker_data: list[dict[str, Any]],
    all_dates: list[str],
    current_idx: int,
) -> dict[str, list[float]]:
    """Build historical OHLCV arrays up to current date."""
    hist = {"opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}

    # Get all bars for this ticker up to current date
    ticker_bars = {bar["date"]: bar for bar in ticker_data}
    for date in all_dates[: current_idx + 1]:
        if date in ticker_bars:
            bar = ticker_bars[date]
            hist["opens"].append(bar["open"])
            hist["highs"].append(bar["high"])
            hist["lows"].append(bar["low"])
            hist["closes"].append(bar["close"])
            hist["volumes"].append(bar["volume"])

    return hist


def _calculate_benchmark_returns(
    benchmark_data: list[dict[str, Any]],
    test_dates: list[str],
    config: BacktestConfig,
) -> list[float]:
    """Calculate daily benchmark returns."""
    benchmark_dict = {bar["date"]: bar["close"] for bar in benchmark_data}
    returns = []
    prev_close = None

    for date in test_dates:
        if date in benchmark_dict:
            close = benchmark_dict[date]
            if prev_close is not None:
                ret = (close - prev_close) / prev_close
                returns.append(ret)
            prev_close = close

    return returns
