"""
Low Volatility Factor Module.

Implements the low volatility anomaly factors:
- Realized Volatility (252-day annualized)
- Beta (vs SPY market benchmark)

The low volatility anomaly is one of the strongest market anomalies:
lower volatility stocks historically deliver equal or higher returns
with significantly less risk. This contradicts traditional finance theory.

All scores returned on 0-100 scale.
INVERTED: Lower volatility = Higher score
"""

from dataclasses import dataclass
from typing import NamedTuple
import math


class LowVolComponent(NamedTuple):
    """Individual low volatility factor component."""
    name: str
    score: float  # 0-100
    weight: float
    raw_value: float | None
    description: str


@dataclass(frozen=True)
class LowVolFactorResult:
    """Result of low volatility factor computation."""
    score: float  # 0-100 composite score
    components: list[LowVolComponent]
    data_completeness: float  # 0-1, fraction of data available

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def _calculate_returns(prices: list[float]) -> list[float]:
    """Calculate daily returns from price series."""
    returns = []
    for i in range(len(prices) - 1):
        if prices[i + 1] > 0:
            ret = (prices[i] - prices[i + 1]) / prices[i + 1]
            returns.append(ret)
    return returns


def compute_realized_volatility(
    prices: list[float] | None = None,
    returns: list[float] | None = None,
    window: int = 252,
) -> tuple[float, float | None, str]:
    """
    Compute annualized realized volatility.

    Realized volatility is the standard deviation of daily returns,
    annualized by multiplying by sqrt(252).

    Thresholds (typical S&P 500 ranges):
    - < 15%: Low volatility (utilities, staples)
    - 15-25%: Average volatility
    - 25-40%: Above average (tech, small caps)
    - > 40%: High volatility (biotech, meme stocks)

    Args:
        prices: List of prices, most recent first
        returns: Pre-computed returns (alternative to prices)
        window: Lookback window in trading days

    Returns:
        (score 0-100, raw_volatility, description)
    """
    # Get returns
    if returns is not None and len(returns) >= window // 2:
        daily_returns = returns[:window]
    elif prices is not None and len(prices) > window // 2:
        daily_returns = _calculate_returns(prices[:min(len(prices), window + 1)])
    else:
        return 50.0, None, "Insufficient price history for volatility"

    if len(daily_returns) < 20:
        return 50.0, None, "Insufficient returns for volatility calculation"

    # Calculate standard deviation of returns
    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    daily_vol = math.sqrt(variance)

    # Annualize: multiply by sqrt(252 trading days)
    annualized_vol = daily_vol * math.sqrt(252)

    # Score: LOWER volatility = HIGHER score (inverted)
    vol_pct = annualized_vol * 100

    if annualized_vol <= 0.12:
        score = 90.0 + min(10, (0.12 - annualized_vol) * 100)
        desc = f"Very low volatility of {vol_pct:.1f}%"
    elif annualized_vol <= 0.18:
        score = 75.0 + (0.18 - annualized_vol) / 0.06 * 15
        desc = f"Low volatility of {vol_pct:.1f}%"
    elif annualized_vol <= 0.25:
        score = 55.0 + (0.25 - annualized_vol) / 0.07 * 20
        desc = f"Moderate volatility of {vol_pct:.1f}%"
    elif annualized_vol <= 0.35:
        score = 35.0 + (0.35 - annualized_vol) / 0.10 * 20
        desc = f"Above average volatility of {vol_pct:.1f}%"
    elif annualized_vol <= 0.50:
        score = 15.0 + (0.50 - annualized_vol) / 0.15 * 20
        desc = f"High volatility of {vol_pct:.1f}%"
    else:
        score = max(5, 15 - (annualized_vol - 0.50) * 30)
        desc = f"Very high volatility of {vol_pct:.1f}%"

    return _clamp(score), annualized_vol, desc


def compute_beta(
    stock_returns: list[float] | None = None,
    market_returns: list[float] | None = None,
    stock_prices: list[float] | None = None,
    market_prices: list[float] | None = None,
) -> tuple[float, float | None, str]:
    """
    Compute CAPM Beta vs market (SPY).

    Beta = Covariance(stock, market) / Variance(market)

    Beta interpretation:
    - < 0.5: Very defensive
    - 0.5-0.8: Defensive
    - 0.8-1.2: Market-like
    - 1.2-1.5: Aggressive
    - > 1.5: Very aggressive

    For low volatility factor, lower beta = higher score.

    Args:
        stock_returns: Daily returns for the stock
        market_returns: Daily returns for SPY
        stock_prices: Stock prices (alternative, will compute returns)
        market_prices: SPY prices (alternative, will compute returns)

    Returns:
        (score 0-100, raw_beta, description)
    """
    # Get returns
    if stock_returns is None:
        if stock_prices is not None and len(stock_prices) > 60:
            stock_returns = _calculate_returns(stock_prices[:253])
        else:
            return 50.0, None, "Insufficient stock data for beta"

    if market_returns is None:
        if market_prices is not None and len(market_prices) > 60:
            market_returns = _calculate_returns(market_prices[:253])
        else:
            return 50.0, None, "Insufficient market data for beta"

    # Align lengths
    n = min(len(stock_returns), len(market_returns))
    if n < 60:
        return 50.0, None, "Insufficient overlapping data for beta"

    stock_rets = stock_returns[:n]
    market_rets = market_returns[:n]

    # Calculate means
    stock_mean = sum(stock_rets) / n
    market_mean = sum(market_rets) / n

    # Calculate covariance and variance
    covariance = sum(
        (s - stock_mean) * (m - market_mean)
        for s, m in zip(stock_rets, market_rets)
    ) / n

    market_variance = sum((m - market_mean) ** 2 for m in market_rets) / n

    if market_variance <= 0:
        return 50.0, None, "Invalid market variance"

    beta = covariance / market_variance

    # Score: LOWER beta = HIGHER score (inverted for low vol factor)
    if beta <= 0.5:
        score = 90.0 + min(10, (0.5 - beta) * 20)
        desc = f"Very defensive beta of {beta:.2f}"
    elif beta <= 0.8:
        score = 70.0 + (0.8 - beta) / 0.3 * 20
        desc = f"Defensive beta of {beta:.2f}"
    elif beta <= 1.0:
        score = 55.0 + (1.0 - beta) / 0.2 * 15
        desc = f"Below-market beta of {beta:.2f}"
    elif beta <= 1.2:
        score = 45.0 + (1.2 - beta) / 0.2 * 10
        desc = f"Market-like beta of {beta:.2f}"
    elif beta <= 1.5:
        score = 25.0 + (1.5 - beta) / 0.3 * 20
        desc = f"Aggressive beta of {beta:.2f}"
    else:
        score = max(5, 25 - (beta - 1.5) * 15)
        desc = f"Very aggressive beta of {beta:.2f}"

    return _clamp(score), beta, desc


def compute_low_vol_score(
    stock_prices: list[float] | None = None,
    market_prices: list[float] | None = None,
    stock_returns: list[float] | None = None,
    market_returns: list[float] | None = None,
    pre_computed_volatility: float | None = None,
    pre_computed_beta: float | None = None,
) -> LowVolFactorResult:
    """
    Compute composite low volatility factor score.

    Weights (per PLAN-scoring.md):
    - 252-day Realized Volatility: 50%
    - Beta (vs SPY): 50%

    Lower volatility and lower beta = higher scores.

    Args:
        stock_prices: Stock price history (most recent first)
        market_prices: SPY price history (most recent first)
        stock_returns: Pre-computed stock returns
        market_returns: Pre-computed market returns
        pre_computed_volatility: Skip volatility calculation
        pre_computed_beta: Skip beta calculation

    Returns:
        LowVolFactorResult with score 0-100 and component breakdown
    """
    components: list[LowVolComponent] = []
    data_points = 0
    total_points = 2

    # 1. Realized Volatility (50% weight)
    if pre_computed_volatility is not None:
        vol_pct = pre_computed_volatility * 100
        # Score from pre-computed value
        if pre_computed_volatility <= 0.15:
            vol_score = 85.0 + (0.15 - pre_computed_volatility) / 0.15 * 15
            vol_desc = f"Low volatility of {vol_pct:.1f}%"
        elif pre_computed_volatility <= 0.25:
            vol_score = 55.0 + (0.25 - pre_computed_volatility) / 0.10 * 30
            vol_desc = f"Moderate volatility of {vol_pct:.1f}%"
        else:
            vol_score = max(15, 55 - (pre_computed_volatility - 0.25) * 100)
            vol_desc = f"High volatility of {vol_pct:.1f}%"
        vol_score = _clamp(vol_score)
        vol_raw = pre_computed_volatility
        data_points += 1
    else:
        vol_score, vol_raw, vol_desc = compute_realized_volatility(
            prices=stock_prices, returns=stock_returns
        )
        if vol_raw is not None:
            data_points += 1

    components.append(LowVolComponent(
        name="Realized Volatility",
        score=vol_score,
        weight=0.50,
        raw_value=vol_raw,
        description=vol_desc,
    ))

    # 2. Beta (50% weight)
    if pre_computed_beta is not None:
        # Score from pre-computed value
        if pre_computed_beta <= 0.8:
            beta_score = 70.0 + (0.8 - pre_computed_beta) / 0.8 * 30
            beta_desc = f"Defensive beta of {pre_computed_beta:.2f}"
        elif pre_computed_beta <= 1.2:
            beta_score = 45.0 + (1.2 - pre_computed_beta) / 0.4 * 25
            beta_desc = f"Market-like beta of {pre_computed_beta:.2f}"
        else:
            beta_score = max(10, 45 - (pre_computed_beta - 1.2) * 25)
            beta_desc = f"Aggressive beta of {pre_computed_beta:.2f}"
        beta_score = _clamp(beta_score)
        beta_raw = pre_computed_beta
        data_points += 1
    else:
        beta_score, beta_raw, beta_desc = compute_beta(
            stock_returns=stock_returns,
            market_returns=market_returns,
            stock_prices=stock_prices,
            market_prices=market_prices,
        )
        if beta_raw is not None:
            data_points += 1

    components.append(LowVolComponent(
        name="Beta",
        score=beta_score,
        weight=0.50,
        raw_value=beta_raw,
        description=beta_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return LowVolFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
    )
