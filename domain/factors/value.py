"""
Value Factor Module.

Implements academic value factors:
- Earnings Yield (E/P) - inverse of P/E, more intuitive
- Book-to-Market (B/M) - inverse of P/B
- Free Cash Flow Yield (FCF/Market Cap)

All scores returned on 0-100 scale.
"""

from dataclasses import dataclass
from typing import NamedTuple


class ValueComponent(NamedTuple):
    """Individual value factor component."""
    name: str
    score: float  # 0-100
    weight: float
    raw_value: float | None
    description: str


@dataclass(frozen=True)
class ValueFactorResult:
    """Result of value factor computation."""
    score: float  # 0-100 composite score
    components: list[ValueComponent]
    data_completeness: float  # 0-1, fraction of data available

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def compute_earnings_yield(eps: float | None, price: float | None) -> tuple[float, str]:
    """
    Compute Earnings Yield (E/P) score.

    Earnings Yield = EPS / Price (inverse of P/E).
    Higher earnings yield = more value = higher score.

    Thresholds (typical market ranges):
    - > 8%: Very attractive (P/E < 12.5)
    - 5-8%: Attractive (P/E 12.5-20)
    - 3-5%: Fair value (P/E 20-33)
    - < 3%: Expensive (P/E > 33)
    - Negative: Loss-making

    Args:
        eps: Earnings per share (trailing 12M)
        price: Current stock price

    Returns:
        (score 0-100, description)
    """
    if eps is None or price is None or price <= 0:
        return 50.0, "Earnings yield unavailable"

    earnings_yield = eps / price

    if eps <= 0:
        # Loss-making company
        pe_equivalent = "N/A (loss)"
        score = max(10, 30 + earnings_yield * 200)  # Penalize losses
        desc = f"Negative earnings (E/P: {earnings_yield:.1%})"
        return _clamp(score), desc

    pe_equivalent = price / eps

    if earnings_yield >= 0.10:
        score = 90.0 + min(10, (earnings_yield - 0.10) * 100)
        desc = f"Very high earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"
    elif earnings_yield >= 0.08:
        score = 80.0 + (earnings_yield - 0.08) / 0.02 * 10
        desc = f"High earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"
    elif earnings_yield >= 0.05:
        score = 60.0 + (earnings_yield - 0.05) / 0.03 * 20
        desc = f"Attractive earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"
    elif earnings_yield >= 0.03:
        score = 40.0 + (earnings_yield - 0.03) / 0.02 * 20
        desc = f"Fair earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"
    elif earnings_yield >= 0.02:
        score = 25.0 + (earnings_yield - 0.02) / 0.01 * 15
        desc = f"Low earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"
    else:
        score = max(10, earnings_yield / 0.02 * 25)
        desc = f"Very low earnings yield of {earnings_yield:.1%} (P/E: {pe_equivalent:.1f})"

    return _clamp(score), desc


def _compute_book_to_market_score(
    book_value: float | None,
    market_cap: float | None,
) -> tuple[float, str]:
    """
    Compute Book-to-Market score.

    B/M = Book Value / Market Cap (inverse of P/B).
    Higher B/M = more value = higher score.

    Thresholds:
    - > 1.0: Trading below book value (deep value)
    - 0.5-1.0: Value range
    - 0.2-0.5: Fair to growth
    - < 0.2: Very expensive relative to book
    """
    if book_value is None or market_cap is None or market_cap <= 0:
        return 50.0, "Book-to-market unavailable"

    if book_value <= 0:
        return 25.0, f"Negative book value"

    btm = book_value / market_cap
    pb = market_cap / book_value  # For description

    if btm >= 1.5:
        score = 95.0
        desc = f"Deep value: B/M {btm:.2f} (P/B: {pb:.2f})"
    elif btm >= 1.0:
        score = 80.0 + (btm - 1.0) / 0.5 * 15
        desc = f"Below book value: B/M {btm:.2f} (P/B: {pb:.2f})"
    elif btm >= 0.5:
        score = 55.0 + (btm - 0.5) / 0.5 * 25
        desc = f"Value territory: B/M {btm:.2f} (P/B: {pb:.2f})"
    elif btm >= 0.3:
        score = 40.0 + (btm - 0.3) / 0.2 * 15
        desc = f"Fair value: B/M {btm:.2f} (P/B: {pb:.2f})"
    elif btm >= 0.2:
        score = 25.0 + (btm - 0.2) / 0.1 * 15
        desc = f"Growth premium: B/M {btm:.2f} (P/B: {pb:.2f})"
    else:
        score = max(10, btm / 0.2 * 25)
        desc = f"High premium: B/M {btm:.2f} (P/B: {pb:.2f})"

    return _clamp(score), desc


def compute_fcf_yield(fcf: float | None, market_cap: float | None) -> tuple[float, str]:
    """
    Compute Free Cash Flow Yield score.

    FCF Yield = FCF / Market Cap.
    Higher FCF yield = more value = higher score.

    FCF is often considered more reliable than earnings
    as it's harder to manipulate.

    Thresholds:
    - > 10%: Exceptional
    - 7-10%: Strong
    - 5-7%: Attractive
    - 3-5%: Fair
    - < 3%: Expensive or capital-intensive
    - Negative: Cash burn

    Args:
        fcf: Free cash flow (trailing 12M)
        market_cap: Current market capitalization

    Returns:
        (score 0-100, description)
    """
    if fcf is None or market_cap is None or market_cap <= 0:
        return 50.0, "FCF yield unavailable"

    fcf_yield = fcf / market_cap

    if fcf < 0:
        # Cash burning
        score = max(5, 25 + fcf_yield * 100)
        desc = f"Negative FCF yield of {fcf_yield:.1%} (cash burn)"
        return _clamp(score), desc

    if fcf_yield >= 0.12:
        score = 95.0
        desc = f"Exceptional FCF yield of {fcf_yield:.1%}"
    elif fcf_yield >= 0.10:
        score = 85.0 + (fcf_yield - 0.10) / 0.02 * 10
        desc = f"Very strong FCF yield of {fcf_yield:.1%}"
    elif fcf_yield >= 0.07:
        score = 70.0 + (fcf_yield - 0.07) / 0.03 * 15
        desc = f"Strong FCF yield of {fcf_yield:.1%}"
    elif fcf_yield >= 0.05:
        score = 55.0 + (fcf_yield - 0.05) / 0.02 * 15
        desc = f"Attractive FCF yield of {fcf_yield:.1%}"
    elif fcf_yield >= 0.03:
        score = 40.0 + (fcf_yield - 0.03) / 0.02 * 15
        desc = f"Fair FCF yield of {fcf_yield:.1%}"
    elif fcf_yield >= 0.01:
        score = 25.0 + (fcf_yield - 0.01) / 0.02 * 15
        desc = f"Low FCF yield of {fcf_yield:.1%}"
    else:
        score = max(15, fcf_yield / 0.01 * 25)
        desc = f"Very low FCF yield of {fcf_yield:.1%}"

    return _clamp(score), desc


def compute_value_score(
    eps: float | None = None,
    price: float | None = None,
    book_value: float | None = None,
    market_cap: float | None = None,
    fcf: float | None = None,
    price_to_book: float | None = None,
) -> ValueFactorResult:
    """
    Compute composite value factor score.

    Weights (per PLAN-scoring.md):
    - Earnings Yield (E/P): 40%
    - Book-to-Market: 30%
    - FCF Yield: 30%

    Args:
        eps: Earnings per share
        price: Current stock price
        book_value: Total book value (equity)
        market_cap: Market capitalization
        fcf: Free cash flow (trailing 12M)
        price_to_book: Pre-computed P/B ratio (optional, for convenience)

    Returns:
        ValueFactorResult with score 0-100 and component breakdown
    """
    components: list[ValueComponent] = []
    data_points = 0
    total_points = 3

    # 1. Earnings Yield (40% weight)
    ey_score, ey_desc = compute_earnings_yield(eps, price)
    if eps is not None and price is not None and price > 0:
        data_points += 1
        ey_raw = eps / price if eps > 0 else eps / price
    else:
        ey_raw = None

    components.append(ValueComponent(
        name="Earnings Yield",
        score=ey_score,
        weight=0.40,
        raw_value=ey_raw,
        description=ey_desc,
    ))

    # 2. Book-to-Market (30% weight)
    if price_to_book is not None and price_to_book > 0:
        # Convert P/B to B/M score
        btm = 1.0 / price_to_book
        if btm >= 1.0:
            btm_score = 80.0 + min(15, (btm - 1.0) * 30)
        elif btm >= 0.5:
            btm_score = 55.0 + (btm - 0.5) / 0.5 * 25
        elif btm >= 0.2:
            btm_score = 25.0 + (btm - 0.2) / 0.3 * 30
        else:
            btm_score = max(10, btm / 0.2 * 25)
        btm_score = _clamp(btm_score)
        btm_desc = f"P/B of {price_to_book:.2f}"
        btm_raw = btm
        data_points += 1
    else:
        btm_score, btm_desc = _compute_book_to_market_score(book_value, market_cap)
        if book_value is not None and market_cap is not None and market_cap > 0:
            data_points += 1
            btm_raw = book_value / market_cap if book_value > 0 else None
        else:
            btm_raw = None

    components.append(ValueComponent(
        name="Book-to-Market",
        score=btm_score,
        weight=0.30,
        raw_value=btm_raw if 'btm_raw' in dir() else None,
        description=btm_desc,
    ))

    # 3. FCF Yield (30% weight)
    fcf_score, fcf_desc = compute_fcf_yield(fcf, market_cap)
    if fcf is not None and market_cap is not None and market_cap > 0:
        data_points += 1
        fcf_raw = fcf / market_cap
    else:
        fcf_raw = None

    components.append(ValueComponent(
        name="FCF Yield",
        score=fcf_score,
        weight=0.30,
        raw_value=fcf_raw,
        description=fcf_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return ValueFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
    )
