"""
Risk Overlay and Position Sizing Module.

Implements portfolio-level risk management:
- Risk Filters (liquidity, leverage, crowded shorts, sector concentration)
- Position Sizing (fractional Kelly criterion)
- Portfolio Construction constraints

Per PLAN-scoring.md:
- Max single position: 8%
- Max sector exposure: 25%
- Min positions: 15 (diversification)
- Max positions: 30 (concentration)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import NamedTuple

from .models import Timeframe


class FilterReason(str, Enum):
    """Reasons for filtering out a stock."""
    LOW_CONVICTION = "low_conviction"
    LOW_LIQUIDITY = "low_liquidity"
    HIGH_LEVERAGE = "high_leverage"
    CROWDED_SHORT = "crowded_short"
    SECTOR_LIMIT = "sector_limit"
    PENNY_STOCK = "penny_stock"
    LOW_CURRENT_RATIO = "low_current_ratio"
    MARKET_CAP_TOO_SMALL = "market_cap_too_small"


class FilterResult(NamedTuple):
    """Result of applying a single filter."""
    passes: bool
    reason: FilterReason | None
    detail: str | None


@dataclass(frozen=True)
class RiskFilters:
    """
    Configuration for risk filters.

    Per SPEC-scoring.md enhanced risk overlay.
    """
    min_market_cap: float = 2e9           # $2B minimum
    min_avg_volume: float = 500_000       # 500K shares/day
    min_daily_liquidity: float = 10e6     # $10M daily dollar volume
    max_days_to_cover: float = 5.0        # DTC limit (was 10, tightened to 5)
    max_debt_equity: float = 2.0          # Leverage limit
    min_current_ratio: float = 1.0        # Liquidity ratio
    min_price: float = 5.0                # No penny stocks
    min_conviction: int = 5               # Minimum conviction score (1-10)


@dataclass(frozen=True)
class PortfolioConstraints:
    """
    Portfolio-level constraints.

    Per SPEC-scoring.md position limits.
    """
    max_single_position: float = 0.08     # 8% max per stock
    min_single_position: float = 0.01     # 1% min per stock
    max_sector_exposure: float = 0.25     # 25% max per sector
    min_positions: int = 15               # Diversification floor
    max_positions: int = 30               # Concentration ceiling
    max_picks_per_sector: int = 3         # Within each timeframe


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    ticker: str
    raw_kelly: float          # Uncapped Kelly fraction
    adjusted_kelly: float     # After safety fraction (0.25x)
    final_size: float         # After constraints (0.01-0.08)
    conviction: int           # Original conviction score
    win_rate_used: float      # Win rate assumption used
    detail: str


@dataclass
class FilteredStock:
    """A stock with filter and sizing results."""
    ticker: str
    sector: str
    timeframe: Timeframe
    conviction: int
    score: float
    included: bool
    filter_reason: FilterReason | None = None
    filter_detail: str | None = None
    position_size: float | None = None


def check_market_cap(
    market_cap: float | None,
    min_cap: float = 2e9,
) -> FilterResult:
    """Check if market cap meets minimum."""
    if market_cap is None:
        return FilterResult(True, None, None)  # Pass if unknown

    if market_cap < min_cap:
        return FilterResult(
            False,
            FilterReason.MARKET_CAP_TOO_SMALL,
            f"Market cap ${market_cap/1e9:.1f}B < ${min_cap/1e9:.0f}B minimum"
        )
    return FilterResult(True, None, None)


def check_price(
    price: float | None,
    min_price: float = 5.0,
) -> FilterResult:
    """Check if price is above penny stock threshold."""
    if price is None:
        return FilterResult(True, None, None)

    if price < min_price:
        return FilterResult(
            False,
            FilterReason.PENNY_STOCK,
            f"Price ${price:.2f} < ${min_price:.2f} minimum"
        )
    return FilterResult(True, None, None)


def check_liquidity(
    avg_volume: float | None,
    price: float | None,
    min_dollar_volume: float = 10e6,
) -> FilterResult:
    """Check daily dollar volume liquidity."""
    if avg_volume is None or price is None:
        return FilterResult(True, None, None)

    dollar_volume = avg_volume * price
    if dollar_volume < min_dollar_volume:
        return FilterResult(
            False,
            FilterReason.LOW_LIQUIDITY,
            f"Daily volume ${dollar_volume/1e6:.1f}M < ${min_dollar_volume/1e6:.0f}M minimum"
        )
    return FilterResult(True, None, None)


def check_days_to_cover(
    dtc: float | None,
    max_dtc: float = 5.0,
) -> FilterResult:
    """Check days-to-cover (short squeeze risk)."""
    if dtc is None:
        return FilterResult(True, None, None)

    if dtc > max_dtc:
        return FilterResult(
            False,
            FilterReason.CROWDED_SHORT,
            f"Days-to-cover {dtc:.1f} > {max_dtc:.0f} (crowded short risk)"
        )
    return FilterResult(True, None, None)


def check_leverage(
    debt_equity: float | None,
    max_de: float = 2.0,
) -> FilterResult:
    """Check debt-to-equity ratio."""
    if debt_equity is None:
        return FilterResult(True, None, None)

    if debt_equity > max_de:
        return FilterResult(
            False,
            FilterReason.HIGH_LEVERAGE,
            f"Debt/Equity {debt_equity:.2f} > {max_de:.1f} (high leverage)"
        )
    return FilterResult(True, None, None)


def check_current_ratio(
    current_ratio: float | None,
    min_ratio: float = 1.0,
) -> FilterResult:
    """Check current ratio (short-term liquidity)."""
    if current_ratio is None:
        return FilterResult(True, None, None)

    if current_ratio < min_ratio:
        return FilterResult(
            False,
            FilterReason.LOW_CURRENT_RATIO,
            f"Current ratio {current_ratio:.2f} < {min_ratio:.1f} (liquidity risk)"
        )
    return FilterResult(True, None, None)


def apply_risk_filters(
    ticker: str,
    market_cap: float | None = None,
    price: float | None = None,
    avg_volume: float | None = None,
    days_to_cover: float | None = None,
    debt_equity: float | None = None,
    current_ratio: float | None = None,
    conviction: int | None = None,
    filters: RiskFilters | None = None,
) -> tuple[bool, FilterReason | None, str | None]:
    """
    Apply all risk filters to a stock.

    Returns:
        (passes_all, first_failure_reason, detail)
    """
    filters = filters or RiskFilters()

    # Conviction filter (if provided)
    if conviction is not None and conviction < filters.min_conviction:
        return (
            False,
            FilterReason.LOW_CONVICTION,
            f"Conviction {conviction} < {filters.min_conviction} minimum"
        )

    # Apply each filter in order
    checks = [
        check_market_cap(market_cap, filters.min_market_cap),
        check_price(price, filters.min_price),
        check_liquidity(avg_volume, price, filters.min_daily_liquidity),
        check_days_to_cover(days_to_cover, filters.max_days_to_cover),
        check_leverage(debt_equity, filters.max_debt_equity),
        check_current_ratio(current_ratio, filters.min_current_ratio),
    ]

    for result in checks:
        if not result.passes:
            return (False, result.reason, result.detail)

    return (True, None, None)


def compute_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    safety_fraction: float = 0.25,
) -> float:
    """
    Compute fractional Kelly criterion for position sizing.

    Kelly formula: f* = (bp - q) / b
    where:
        b = avg_win / avg_loss (win/loss ratio)
        p = probability of winning
        q = 1 - p = probability of losing

    We use fractional Kelly (default 0.25x) for safety.

    Args:
        win_rate: Historical or expected win rate (0-1)
        avg_win: Average winning trade return
        avg_loss: Average losing trade return (positive number)
        safety_fraction: Kelly fraction (0.25 = quarter Kelly)

    Returns:
        Position size fraction (0.0 to ~0.2 typically)
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    b = avg_win / avg_loss  # Win/loss ratio
    p = win_rate
    q = 1 - p

    # Kelly formula
    kelly = (b * p - q) / b

    # Apply safety fraction and floor at 0
    fractional_kelly = max(0.0, kelly * safety_fraction)

    return fractional_kelly


def compute_position_size(
    ticker: str,
    conviction: int,
    score: float,
    historical_win_rate: float = 0.55,
    avg_win_return: float = 0.15,
    avg_loss_return: float = 0.10,
    constraints: PortfolioConstraints | None = None,
) -> PositionSizeResult:
    """
    Compute position size using conviction-adjusted fractional Kelly.

    The position size is influenced by:
    1. Base Kelly fraction from win rate and win/loss ratio
    2. Conviction adjustment (higher conviction = closer to Kelly)
    3. Constraints (min 1%, max 8%)

    Args:
        ticker: Stock ticker
        conviction: Conviction score (1-10)
        score: Factor composite score (0-100)
        historical_win_rate: Historical win rate for sizing
        avg_win_return: Average winning return
        avg_loss_return: Average losing return
        constraints: Portfolio constraints

    Returns:
        PositionSizeResult with sizing details
    """
    constraints = constraints or PortfolioConstraints()

    # Compute base Kelly
    raw_kelly = compute_kelly_fraction(
        win_rate=historical_win_rate,
        avg_win=avg_win_return,
        avg_loss=avg_loss_return,
        safety_fraction=0.25,  # Quarter Kelly
    )

    # Conviction adjustment: scale Kelly by conviction/10
    # High conviction (10) = full quarter Kelly
    # Low conviction (5) = half of quarter Kelly
    conviction_multiplier = conviction / 10.0
    adjusted_kelly = raw_kelly * conviction_multiplier

    # Apply constraints
    final_size = max(
        constraints.min_single_position,
        min(constraints.max_single_position, adjusted_kelly)
    )

    # Generate detail
    if final_size >= constraints.max_single_position:
        detail = f"Max position size (capped from {adjusted_kelly:.1%})"
    elif final_size <= constraints.min_single_position:
        detail = f"Min position size (floored from {adjusted_kelly:.1%})"
    else:
        detail = f"Kelly-based size (conviction {conviction}/10)"

    return PositionSizeResult(
        ticker=ticker,
        raw_kelly=raw_kelly,
        adjusted_kelly=adjusted_kelly,
        final_size=round(final_size, 4),
        conviction=conviction,
        win_rate_used=historical_win_rate,
        detail=detail,
    )


def apply_sector_concentration(
    stocks: list[FilteredStock],
    max_per_sector: int = 3,
) -> list[FilteredStock]:
    """
    Apply sector concentration limits.

    Stocks should be pre-sorted by conviction (highest first).
    After limit reached, remaining stocks from that sector are filtered.

    Args:
        stocks: List of FilteredStock (already filtered by other criteria)
        max_per_sector: Maximum stocks per sector

    Returns:
        Updated list with sector-filtered stocks marked
    """
    sector_counts: dict[str, int] = {}
    result: list[FilteredStock] = []

    for stock in stocks:
        if not stock.included:
            # Already filtered out
            result.append(stock)
            continue

        sector = stock.sector.lower()
        count = sector_counts.get(sector, 0)

        if count >= max_per_sector:
            # Sector limit reached
            result.append(FilteredStock(
                ticker=stock.ticker,
                sector=stock.sector,
                timeframe=stock.timeframe,
                conviction=stock.conviction,
                score=stock.score,
                included=False,
                filter_reason=FilterReason.SECTOR_LIMIT,
                filter_detail=f"Sector limit ({max_per_sector} {sector} stocks already)",
                position_size=None,
            ))
        else:
            sector_counts[sector] = count + 1
            result.append(stock)

    return result


def normalize_position_sizes(
    sizes: list[PositionSizeResult],
    target_invested: float = 1.0,
) -> list[tuple[str, float]]:
    """
    Normalize position sizes to sum to target (typically 100%).

    Args:
        sizes: List of position sizing results
        target_invested: Target total investment (1.0 = 100%)

    Returns:
        List of (ticker, normalized_size) tuples
    """
    if not sizes:
        return []

    total_raw = sum(s.final_size for s in sizes)

    if total_raw <= 0:
        # Equal weight fallback
        equal_weight = target_invested / len(sizes)
        return [(s.ticker, equal_weight) for s in sizes]

    # Scale to target
    scale_factor = target_invested / total_raw

    return [
        (s.ticker, round(s.final_size * scale_factor, 4))
        for s in sizes
    ]
