"""
Congress trading adapter.

Fetches congressional stock transactions from public disclosure data.
Uses House Stock Watcher JSON feed (no API key required).

Source: https://housestockwatcher.com
Data: https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from domain import Observation, Category
from ports import FetchError, ParseError

from .base import BaseAdapter

logger = logging.getLogger(__name__)


# Transaction type mapping
TRANSACTION_TYPES = {
    "purchase": "buy",
    "sale_full": "sell",
    "sale_partial": "sell",
    "sale": "sell",
    "exchange": "exchange",
}

# Amount range mapping (from disclosure format)
AMOUNT_RANGES = {
    "$1,001 - $15,000": (1001, 15000),
    "$15,001 - $50,000": (15001, 50000),
    "$50,001 - $100,000": (50001, 100000),
    "$100,001 - $250,000": (100001, 250000),
    "$250,001 - $500,000": (250001, 500000),
    "$500,001 - $1,000,000": (500001, 1000000),
    "$1,000,001 - $5,000,000": (1000001, 5000000),
    "$5,000,001 - $25,000,000": (5000001, 25000000),
    "$25,000,001 - $50,000,000": (25000001, 50000000),
    "Over $50,000,000": (50000001, 100000000),
}


@dataclass
class CongressTrade:
    """Typed congress trade data."""
    politician: str
    party: str
    chamber: str
    ticker: str
    transaction_type: str
    amount_range: tuple[int, int]
    disclosure_date: datetime
    transaction_date: datetime | None
    asset_description: str
    district: str


class CongressAdapter(BaseAdapter):
    """
    Congressional trading disclosure adapter.

    Fetches stock transactions disclosed by members of Congress
    from public disclosure data sources.
    """

    # Multiple data sources for redundancy
    DATA_SOURCES = [
        # Primary: House Stock Watcher (may have rate limits)
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
        # Fallback: Senate Stock Watcher
        "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
    ]

    @property
    def source_name(self) -> str:
        return "congress"

    @property
    def category(self) -> Category:
        return Category.SENTIMENT

    @property
    def reliability(self) -> float:
        return 0.9  # Official disclosures, high reliability

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """
        Fetch recent congressional trades.

        Args:
            days_back: Number of days to look back (default 60)
            limit: Maximum number of trades to return (default 100)
            tickers: Optional list of tickers to filter

        Returns:
            List of Observations containing congress trade data
        """
        days_back = kwargs.get("days_back", 60)
        limit = kwargs.get("limit", 100)
        tickers = kwargs.get("tickers", None)

        logger.info(f"Fetching congress trades (days_back={days_back}, limit={limit})")

        # Try each data source until one works
        data = None
        last_error = None
        for url in self.DATA_SOURCES:
            try:
                logger.debug(f"Trying congress data source: {url}")
                data = self._http_get_json(url)
                if data:
                    logger.info(f"Successfully fetched congress data from {url}")
                    break
            except Exception as e:
                logger.warning(f"Congress source failed ({url}): {e}")
                last_error = e
                continue

        if data is None:
            logger.error(f"All congress data sources failed: {last_error}")
            # Return empty instead of raising - smart money is optional
            return []

        if not isinstance(data, list):
            raise ParseError(
                source=self.source_name,
                format_type="json",
                reason="Expected list of transactions",
                raw_content=str(data)[:200],
            )

        # Filter and process trades
        cutoff_date = datetime.now() - timedelta(days=days_back)
        trades = []

        for item in data:
            trade = self._parse_trade(item)
            if trade is None:
                continue

            # Filter by date
            if trade.disclosure_date < cutoff_date:
                continue

            # Filter by ticker if specified
            if tickers and trade.ticker not in tickers:
                continue

            # Skip non-stock trades (options, bonds, etc.)
            if not self._is_stock_trade(trade):
                continue

            trades.append(trade)

        # Sort by disclosure date (newest first)
        trades.sort(key=lambda t: t.disclosure_date, reverse=True)

        # Apply limit
        trades = trades[:limit]

        logger.info(f"Found {len(trades)} congress trades")

        # Convert to observations
        observations = []
        for trade in trades:
            obs = self._trade_to_observation(trade)
            observations.append(obs)

        return observations

    def _parse_trade(self, item: dict) -> CongressTrade | None:
        """Parse a single trade from raw JSON."""
        try:
            # Parse disclosure date
            disclosure_str = item.get("disclosure_date", "")
            if not disclosure_str:
                return None

            try:
                disclosure_date = datetime.strptime(disclosure_str, "%m/%d/%Y")
            except ValueError:
                try:
                    disclosure_date = datetime.strptime(disclosure_str, "%Y-%m-%d")
                except ValueError:
                    return None

            # Parse transaction date (optional)
            transaction_date = None
            trans_str = item.get("transaction_date", "")
            if trans_str:
                try:
                    transaction_date = datetime.strptime(trans_str, "%Y-%m-%d")
                except ValueError:
                    pass

            # Get ticker
            ticker = item.get("ticker", "").upper().strip()
            if not ticker or ticker == "--" or len(ticker) > 10:
                return None

            # Get transaction type
            tx_type = item.get("type", "").lower()
            direction = TRANSACTION_TYPES.get(tx_type, "buy")

            # Get amount range
            amount_str = item.get("amount", "$1,001 - $15,000")
            amount_range = AMOUNT_RANGES.get(amount_str, (1001, 15000))

            # Get politician info
            representative = item.get("representative", "Unknown")
            party = self._extract_party(item.get("party", ""))
            district = item.get("district", "")
            chamber = "House" if district else "Senate"

            return CongressTrade(
                politician=representative,
                party=party,
                chamber=chamber,
                ticker=ticker,
                transaction_type=direction,
                amount_range=amount_range,
                disclosure_date=disclosure_date,
                transaction_date=transaction_date,
                asset_description=item.get("asset_description", "")[:200],
                district=district,
            )

        except Exception as e:
            logger.debug(f"Failed to parse trade: {e}")
            return None

    def _extract_party(self, party_str: str) -> str:
        """Extract party letter from party string."""
        party_str = party_str.upper()
        if "REPUBLICAN" in party_str or party_str == "R":
            return "R"
        if "DEMOCRAT" in party_str or party_str == "D":
            return "D"
        if "INDEPENDENT" in party_str or party_str == "I":
            return "I"
        return "I"  # Default to Independent

    def _is_stock_trade(self, trade: CongressTrade) -> bool:
        """Check if this is a stock trade (vs options, bonds, etc.)."""
        desc = trade.asset_description.lower()

        # Exclude options
        if "option" in desc or "call" in desc or "put" in desc:
            return False

        # Exclude bonds
        if "bond" in desc or "treasury" in desc or "note" in desc:
            return False

        # Exclude funds that aren't ETFs
        if "mutual fund" in desc:
            return False

        return True

    def _trade_to_observation(self, trade: CongressTrade) -> Observation:
        """Convert trade to observation."""
        # Generate unique ID
        id_str = f"{trade.politician}:{trade.ticker}:{trade.disclosure_date.isoformat()}"
        trade_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

        # Calculate signal strength based on amount
        strength = self._calculate_strength(trade)

        # Generate summary
        summary = self._generate_summary(trade)

        return Observation(
            source=self.source_name,
            timestamp=trade.disclosure_date,
            category=Category.SENTIMENT,
            data={
                "id": trade_id,
                "signal_type": "congress",
                "ticker": trade.ticker,
                "direction": trade.transaction_type,
                "strength": strength,
                "summary": summary,
                "details": {
                    "politician": trade.politician,
                    "party": trade.party,
                    "chamber": trade.chamber,
                    "amount_low": trade.amount_range[0],
                    "amount_high": trade.amount_range[1],
                    "asset_description": trade.asset_description,
                    "transaction_date": trade.transaction_date.isoformat() if trade.transaction_date else None,
                    "disclosure_date": trade.disclosure_date.isoformat(),
                },
            },
            ticker=trade.ticker,
            reliability=self.reliability,
        )

    def _calculate_strength(self, trade: CongressTrade) -> float:
        """
        Calculate signal strength based on trade size.

        Higher amounts = stronger signal (more conviction from politician).
        """
        low, high = trade.amount_range
        mid = (low + high) / 2

        # Log scale strength: $15k = 0.3, $100k = 0.5, $1M = 0.7, $5M+ = 0.9
        if mid <= 15000:
            return 0.3
        elif mid <= 50000:
            return 0.4
        elif mid <= 100000:
            return 0.5
        elif mid <= 250000:
            return 0.6
        elif mid <= 500000:
            return 0.7
        elif mid <= 1000000:
            return 0.8
        else:
            return 0.9

    def _generate_summary(self, trade: CongressTrade) -> str:
        """Generate human-readable summary."""
        action = "bought" if trade.transaction_type == "buy" else "sold"
        amount_str = f"${trade.amount_range[0]:,} - ${trade.amount_range[1]:,}"

        return (
            f"{trade.politician} ({trade.party}-{trade.chamber}) {action} "
            f"{trade.ticker} ({amount_str})"
        )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_recent(self, days: int = 30, limit: int = 50) -> list[Observation]:
        """Get recent congressional trades."""
        return self.fetch(days_back=days, limit=limit)

    def get_for_ticker(self, ticker: str, days: int = 90) -> list[Observation]:
        """Get trades for a specific ticker."""
        ticker = ticker.upper().strip()
        return self.fetch(days_back=days, tickers=[ticker], limit=100)

    def get_buys(self, days: int = 30, limit: int = 50) -> list[Observation]:
        """Get recent buy transactions only."""
        all_trades = self.fetch(days_back=days, limit=limit * 2)
        return [t for t in all_trades if t.data.get("direction") == "buy"][:limit]

    def get_sells(self, days: int = 30, limit: int = 50) -> list[Observation]:
        """Get recent sell transactions only."""
        all_trades = self.fetch(days_back=days, limit=limit * 2)
        return [t for t in all_trades if t.data.get("direction") == "sell"][:limit]
