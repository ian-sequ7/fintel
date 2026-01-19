"""
Smart Money Factor Module.

Implements signals from institutional investors and insiders:
- 13F Institutional Accumulation (quarter-over-quarter changes)
- Insider Cluster Buys (Form 4 - 3+ C-suite buying)
- Congress Trade Signals (recency-weighted)

Academic research shows:
- Insider cluster buys generate ~7.8% annual alpha
- 13F tracking can generate 3-5% alpha when done correctly
- Congressional trades have historically shown abnormal returns

All scores returned on 0-100 scale.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import NamedTuple, Protocol


class SmartMoneyComponent(NamedTuple):
    """Individual smart money factor component."""
    name: str
    score: float  # 0-100
    weight: float
    signal_count: int
    description: str


@dataclass(frozen=True)
class SmartMoneyFactorResult:
    """Result of smart money factor computation."""
    score: float  # 0-100 composite score
    components: list[SmartMoneyComponent]
    data_completeness: float  # 0-1, fraction of data available

    @property
    def normalized(self) -> float:
        """Score on 0-1 scale for compatibility."""
        return self.score / 100.0


# Protocol for type hints without importing actual types
class Filing13F(Protocol):
    """Protocol for 13F filing data."""
    ticker: str
    shares: int
    value: float
    fund_name: str
    report_date: date


class Form4Trade(Protocol):
    """Protocol for Form 4 insider trade."""
    ticker: str
    insider_name: str
    insider_title: str
    transaction_type: str  # 'P' for purchase, 'S' for sale
    shares: int
    price: float
    transaction_date: date


class CongressTrade(Protocol):
    """Protocol for congressional trade."""
    ticker: str
    representative: str
    transaction_type: str  # 'purchase' or 'sale'
    amount_range: tuple[float, float]  # min, max
    transaction_date: date


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


# Top hedge funds with their reputation weights
FUND_REPUTATION = {
    "berkshire hathaway": 1.0,
    "bridgewater": 0.95,
    "renaissance technologies": 0.95,
    "two sigma": 0.90,
    "citadel": 0.85,
    "de shaw": 0.85,
    "aqr capital": 0.85,
    "millennium": 0.80,
    "point72": 0.80,
    "viking global": 0.80,
    "tiger global": 0.75,
    "coatue": 0.75,
    "third point": 0.75,
    "pershing square": 0.75,
    "baupost": 0.70,
    "greenlight capital": 0.70,
    "elliott management": 0.70,
}


def _get_fund_weight(fund_name: str) -> float:
    """Get reputation weight for a fund."""
    fund_lower = fund_name.lower()
    for known_fund, weight in FUND_REPUTATION.items():
        if known_fund in fund_lower:
            return weight
    return 0.5  # Default weight for unknown funds


def compute_institutional_accumulation(
    current_holdings: list[dict] | None,
    previous_holdings: list[dict] | None,
) -> tuple[float, int, str]:
    """
    Compute institutional accumulation score from 13F changes.

    Tracks quarter-over-quarter changes in institutional holdings,
    weighted by fund reputation.

    Signals:
    - New position by top fund: Strong bullish
    - Increased position by top fund: Bullish
    - Decreased position by top fund: Bearish
    - Closed position by top fund: Strong bearish

    Args:
        current_holdings: List of current 13F holdings
            Each dict: {fund_name, shares, value}
        previous_holdings: List of previous quarter's holdings
            Each dict: {fund_name, shares, value}

    Returns:
        (score 0-100, signal_count, description)
    """
    if current_holdings is None:
        return 50.0, 0, "13F data unavailable"

    if not current_holdings:
        return 40.0, 0, "No institutional holders found"

    # Build lookup for previous holdings
    prev_by_fund = {}
    if previous_holdings:
        for h in previous_holdings:
            fund = h.get("fund_name", "").lower()
            prev_by_fund[fund] = h.get("shares", 0)

    # Calculate weighted accumulation signal
    total_weight = 0.0
    weighted_signal = 0.0
    new_positions = 0
    increased = 0
    decreased = 0
    closed = 0

    for holding in current_holdings:
        fund_name = holding.get("fund_name", "")
        current_shares = holding.get("shares", 0)
        fund_weight = _get_fund_weight(fund_name)

        prev_shares = prev_by_fund.get(fund_name.lower(), 0)

        if prev_shares == 0 and current_shares > 0:
            # New position
            signal = 1.0
            new_positions += 1
        elif current_shares > prev_shares:
            # Increased
            pct_increase = (current_shares - prev_shares) / prev_shares if prev_shares > 0 else 1.0
            signal = min(1.0, pct_increase)  # Cap at 1.0
            increased += 1
        elif current_shares < prev_shares:
            # Decreased
            pct_decrease = (prev_shares - current_shares) / prev_shares
            signal = -min(1.0, pct_decrease)
            decreased += 1
        else:
            # Unchanged
            signal = 0.0

        weighted_signal += signal * fund_weight
        total_weight += fund_weight

    # Check for closed positions
    if previous_holdings:
        current_funds = {h.get("fund_name", "").lower() for h in current_holdings}
        for h in previous_holdings:
            fund = h.get("fund_name", "").lower()
            if fund not in current_funds and h.get("shares", 0) > 0:
                fund_weight = _get_fund_weight(fund)
                weighted_signal -= fund_weight  # Strong negative signal
                total_weight += fund_weight
                closed += 1

    if total_weight == 0:
        return 50.0, 0, "No weighted signals"

    # Normalize signal to -1 to 1
    normalized_signal = weighted_signal / total_weight

    # Convert to 0-100 score
    # Signal of +1 = score 90, signal of -1 = score 10, signal of 0 = score 50
    score = 50.0 + normalized_signal * 40.0

    signal_count = new_positions + increased + decreased + closed

    # Generate description
    parts = []
    if new_positions > 0:
        parts.append(f"{new_positions} new positions")
    if increased > 0:
        parts.append(f"{increased} increased")
    if decreased > 0:
        parts.append(f"{decreased} decreased")
    if closed > 0:
        parts.append(f"{closed} closed")

    if normalized_signal > 0.3:
        sentiment = "Strong institutional accumulation"
    elif normalized_signal > 0.1:
        sentiment = "Net institutional buying"
    elif normalized_signal < -0.3:
        sentiment = "Strong institutional distribution"
    elif normalized_signal < -0.1:
        sentiment = "Net institutional selling"
    else:
        sentiment = "Mixed institutional activity"

    desc = f"{sentiment}: {', '.join(parts)}" if parts else sentiment

    return _clamp(score), signal_count, desc


def compute_insider_cluster_score(
    insider_trades: list[dict] | None,
    lookback_days: int = 90,
    today: date | None = None,
) -> tuple[float, int, str]:
    """
    Compute insider cluster buy score from Form 4 filings.

    A "cluster buy" is when 3+ different insiders purchase shares
    within a period. This is one of the strongest predictive signals,
    generating ~7.8% annual alpha according to academic research.

    Weighting:
    - CEO, CFO, Chairman: 1.0x
    - Other officers: 0.7x
    - Directors: 0.5x
    - 10% owners: 0.3x

    Recency weighting:
    - < 30 days: 1.0x
    - 30-60 days: 0.7x
    - 60-90 days: 0.4x

    Args:
        insider_trades: List of Form 4 trades
            Each dict: {insider_name, insider_title, transaction_type,
                       shares, price, transaction_date}
        lookback_days: How far back to look for clusters
        today: Reference date (defaults to today)

    Returns:
        (score 0-100, buy_count, description)
    """
    if insider_trades is None:
        return 50.0, 0, "Insider trading data unavailable"

    if today is None:
        today = date.today()

    cutoff_date = today - timedelta(days=lookback_days)

    # Title weights
    title_weights = {
        "ceo": 1.0, "chief executive": 1.0,
        "cfo": 1.0, "chief financial": 1.0,
        "chairman": 1.0, "chair": 0.9,
        "president": 0.9,
        "coo": 0.8, "chief operating": 0.8,
        "cto": 0.8, "chief technology": 0.8,
        "evp": 0.7, "svp": 0.7, "vp": 0.6,
        "director": 0.5,
        "10%": 0.3, "owner": 0.3,
    }

    def get_title_weight(title: str) -> float:
        title_lower = title.lower()
        for key, weight in title_weights.items():
            if key in title_lower:
                return weight
        return 0.5  # Default

    def get_recency_weight(trade_date: date) -> float:
        days_ago = (today - trade_date).days
        if days_ago <= 30:
            return 1.0
        elif days_ago <= 60:
            return 0.7
        elif days_ago <= 90:
            return 0.4
        return 0.2

    # Process trades
    buys = []
    sells = []
    unique_buyers = set()

    for trade in insider_trades:
        trade_date = trade.get("transaction_date")
        if isinstance(trade_date, str):
            try:
                trade_date = date.fromisoformat(trade_date)
            except (ValueError, TypeError):
                continue

        if trade_date is None or trade_date < cutoff_date:
            continue

        tx_type = trade.get("transaction_type", "").upper()
        insider_name = trade.get("insider_name", "Unknown")
        insider_title = trade.get("insider_title", "")
        shares = trade.get("shares", 0)
        price = trade.get("price", 0)

        title_weight = get_title_weight(insider_title)
        recency_weight = get_recency_weight(trade_date)

        trade_value = shares * price if shares and price else 0
        weighted_value = trade_value * title_weight * recency_weight

        if tx_type == "P" or tx_type == "BUY" or "purchase" in tx_type.lower():
            buys.append(weighted_value)
            unique_buyers.add(insider_name)
        elif tx_type == "S" or tx_type == "SELL" or "sale" in tx_type.lower():
            sells.append(weighted_value)

    total_buys = sum(buys)
    total_sells = sum(sells)
    num_unique_buyers = len(unique_buyers)

    # Score calculation
    if num_unique_buyers >= 3:
        # Cluster detected - strong signal
        base_score = 80.0 + min(15, (num_unique_buyers - 3) * 5)
    elif num_unique_buyers == 2:
        base_score = 65.0
    elif num_unique_buyers == 1:
        base_score = 55.0
    else:
        base_score = 50.0

    # Adjust for net buy/sell
    if total_buys + total_sells > 0:
        net_ratio = (total_buys - total_sells) / (total_buys + total_sells)
        base_score += net_ratio * 15  # Adjust by up to ±15

    # Adjust for sells
    if len(sells) > len(buys):
        base_score -= 10  # Penalty for more sells than buys

    # Generate description
    if num_unique_buyers >= 3:
        desc = f"CLUSTER BUY: {num_unique_buyers} insiders purchasing"
    elif num_unique_buyers > 0:
        desc = f"{num_unique_buyers} insider(s) buying"
    elif len(sells) > 0:
        desc = f"Insider selling activity ({len(sells)} sales)"
    else:
        desc = "No recent insider activity"

    return _clamp(base_score), num_unique_buyers, desc


def compute_congress_trade_score(
    trades: list[dict] | None,
    lookback_days: int = 60,
    today: date | None = None,
) -> tuple[float, int, str]:
    """
    Compute congressional trade signal score.

    Congressional trades have historically shown abnormal returns,
    likely due to information advantages from committee work.

    Recency weighting:
    - < 30 days: 1.0x
    - 30-60 days: 0.5x
    - > 60 days: 0.25x

    Args:
        trades: List of congressional trades
            Each dict: {representative, transaction_type,
                       amount_min, amount_max, transaction_date}
        lookback_days: How far back to consider
        today: Reference date

    Returns:
        (score 0-100, trade_count, description)
    """
    if trades is None:
        return 50.0, 0, "Congressional trade data unavailable"

    if today is None:
        today = date.today()

    cutoff_date = today - timedelta(days=lookback_days)

    def get_recency_weight(trade_date: date) -> float:
        days_ago = (today - trade_date).days
        if days_ago <= 30:
            return 1.0
        elif days_ago <= 60:
            return 0.5
        return 0.25

    weighted_buys = 0.0
    weighted_sells = 0.0
    buy_count = 0
    sell_count = 0
    representatives = set()

    for trade in trades:
        trade_date = trade.get("transaction_date")
        if isinstance(trade_date, str):
            try:
                trade_date = date.fromisoformat(trade_date)
            except (ValueError, TypeError):
                continue

        if trade_date is None or trade_date < cutoff_date:
            continue

        tx_type = trade.get("transaction_type", "").lower()
        representative = trade.get("representative", "Unknown")

        # Estimate trade size from range
        amount_min = trade.get("amount_min", 0)
        amount_max = trade.get("amount_max", 0)
        amount_est = (amount_min + amount_max) / 2 if amount_max > 0 else amount_min

        recency_weight = get_recency_weight(trade_date)
        weighted_amount = amount_est * recency_weight

        if "purchase" in tx_type or "buy" in tx_type:
            weighted_buys += weighted_amount
            buy_count += 1
            representatives.add(representative)
        elif "sale" in tx_type or "sell" in tx_type:
            weighted_sells += weighted_amount
            sell_count += 1

    total_weighted = weighted_buys + weighted_sells

    if total_weighted == 0:
        if buy_count + sell_count == 0:
            return 50.0, 0, "No recent congressional trades"
        # Have trades but no amounts
        net_trades = buy_count - sell_count
        score = 50.0 + net_trades * 5
        return _clamp(score), buy_count, f"{buy_count} purchases, {sell_count} sales"

    # Net signal
    net_ratio = (weighted_buys - weighted_sells) / total_weighted

    # Base score from net direction
    score = 50.0 + net_ratio * 30  # Up to ±30 points

    # Bonus for multiple representatives buying
    if len(representatives) >= 2 and buy_count > sell_count:
        score += min(10, len(representatives) * 3)

    # Generate description
    if net_ratio > 0.3:
        sentiment = "Strong congressional buying"
    elif net_ratio > 0:
        sentiment = "Net congressional buying"
    elif net_ratio < -0.3:
        sentiment = "Strong congressional selling"
    elif net_ratio < 0:
        sentiment = "Net congressional selling"
    else:
        sentiment = "Mixed congressional activity"

    desc = f"{sentiment}: {buy_count} purchases, {sell_count} sales"

    return _clamp(score), buy_count + sell_count, desc


def compute_smart_money_score(
    current_13f_holdings: list[dict] | None = None,
    previous_13f_holdings: list[dict] | None = None,
    insider_trades: list[dict] | None = None,
    congress_trades: list[dict] | None = None,
    today: date | None = None,
) -> SmartMoneyFactorResult:
    """
    Compute composite smart money factor score.

    Weights (per PLAN-scoring.md):
    - 13F Institutional Accumulation: 40%
    - Insider Cluster Buys (Form 4): 35%
    - Congress Trades: 25%

    Args:
        current_13f_holdings: Current quarter 13F holdings
        previous_13f_holdings: Previous quarter 13F holdings
        insider_trades: Recent Form 4 insider trades
        congress_trades: Recent congressional trades
        today: Reference date

    Returns:
        SmartMoneyFactorResult with score 0-100 and component breakdown
    """
    components: list[SmartMoneyComponent] = []
    data_points = 0
    total_points = 3

    # 1. 13F Institutional Accumulation (40% weight)
    inst_score, inst_count, inst_desc = compute_institutional_accumulation(
        current_13f_holdings, previous_13f_holdings
    )
    if current_13f_holdings is not None:
        data_points += 1

    components.append(SmartMoneyComponent(
        name="Institutional Accumulation",
        score=inst_score,
        weight=0.40,
        signal_count=inst_count,
        description=inst_desc,
    ))

    # 2. Insider Cluster Buys (35% weight)
    insider_score, insider_count, insider_desc = compute_insider_cluster_score(
        insider_trades, lookback_days=90, today=today
    )
    if insider_trades is not None:
        data_points += 1

    components.append(SmartMoneyComponent(
        name="Insider Clusters",
        score=insider_score,
        weight=0.35,
        signal_count=insider_count,
        description=insider_desc,
    ))

    # 3. Congress Trades (25% weight)
    cong_score, cong_count, cong_desc = compute_congress_trade_score(
        congress_trades, lookback_days=60, today=today
    )
    if congress_trades is not None:
        data_points += 1

    components.append(SmartMoneyComponent(
        name="Congress Trades",
        score=cong_score,
        weight=0.25,
        signal_count=cong_count,
        description=cong_desc,
    ))

    # Compute weighted average
    composite_score = sum(c.score * c.weight for c in components)
    data_completeness = data_points / total_points

    return SmartMoneyFactorResult(
        score=round(composite_score, 2),
        components=components,
        data_completeness=data_completeness,
    )
