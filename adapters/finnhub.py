"""
Finnhub adapter for stock data.

Alternative/fallback data source for:
- Real-time quotes
- Company profile
- Basic fundamentals

Free tier: 60 API calls/minute.
Requires free API key from: https://finnhub.io/register

Setup:
1. Register at https://finnhub.io/register (free)
2. Get API key from dashboard
3. Set in config.toml: [api_keys] finnhub = "your_key"
   Or environment: export FINNHUB_API_KEY="your_key"

API docs: https://finnhub.io/docs/api
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import hashlib

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError
from db import get_db
from db.models import InsiderTransaction as DBInsiderTransaction

from .base import BaseAdapter
from .cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class FinnhubQuote:
    """Typed quote data from Finnhub."""
    symbol: str
    current: float
    high: float
    low: float
    open: float
    previous_close: float
    change: float
    change_percent: float
    timestamp: int


@dataclass
class FinnhubProfile:
    """Typed company profile from Finnhub."""
    symbol: str
    name: str
    country: str | None
    currency: str | None
    exchange: str | None
    ipo: str | None
    market_cap: float | None
    industry: str | None
    sector: str | None
    website: str | None


@dataclass
class FinnhubInsiderTransaction:
    """
    Typed insider transaction from Finnhub.

    Data sourced from SEC Form 3, 4, 5 filings.
    Endpoint: /stock/insider-transactions
    """
    symbol: str
    name: str  # Insider's name
    share: int  # Shares held after transaction
    change: int  # Net share change (+ = buy, - = sell)
    filing_date: str  # Date filing submitted (YYYY-MM-DD)
    transaction_date: str  # Date transaction occurred (YYYY-MM-DD)
    transaction_code: str  # SEC Form 4 code (P=Purchase, S=Sale, etc.)
    transaction_price: float | None  # Average price per share


class FinnhubAdapter(BaseAdapter):
    """
    Finnhub data adapter.

    Provides real-time quotes and company profiles.
    No API key required for basic quote endpoint.

    Rate limit: 60 calls/min (free tier)
    """

    BASE_URL = "https://finnhub.io/api/v1"

    @property
    def source_name(self) -> str:
        return "finnhub"

    @property
    def category(self) -> Category:
        return Category.PRICE

    @property
    def reliability(self) -> float:
        return 0.85

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Route to specific fetch method based on data_type."""
        data_type = kwargs.get("data_type", "quote")
        ticker = kwargs.get("ticker")

        if not ticker:
            raise ValidationError(
                reason="ticker parameter is required",
                field="ticker",
                source=self.source_name,
            )

        ticker = self._validate_ticker(ticker)

        if data_type == "quote":
            return self._fetch_quote(ticker)
        elif data_type == "profile":
            return self._fetch_profile(ticker)
        elif data_type == "insider_transactions":
            from_date = kwargs.get("from_date")
            to_date = kwargs.get("to_date")
            return self._fetch_insider_transactions(ticker, from_date, to_date)
        else:
            raise ValidationError(
                reason=f"data_type must be 'quote', 'profile', or 'insider_transactions', got '{data_type}'",
                field="data_type",
                value=data_type,
                source=self.source_name,
            )

    def _fetch_quote(self, ticker: str) -> list[Observation]:
        """Fetch real-time quote from Finnhub.

        Endpoint: /quote?symbol={ticker}
        Returns: c, h, l, o, pc (current, high, low, open, previous close)
        """
        api_key = self._get_api_key()
        url = f"{self.BASE_URL}/quote?symbol={ticker}"
        if api_key:
            url += f"&token={api_key}"

        data = self._http_get_json(url)

        # Check for valid response (c = current price)
        if data.get("c") is None or data.get("c") == 0:
            raise DataError.empty(
                source=self.source_name,
                description=f"No quote data for {ticker}",
            )

        current = data["c"]
        previous_close = data.get("pc", current)

        quote = FinnhubQuote(
            symbol=ticker,
            current=current,
            high=data.get("h", current),
            low=data.get("l", current),
            open=data.get("o", current),
            previous_close=previous_close,
            change=current - previous_close,
            change_percent=((current - previous_close) / previous_close * 100) if previous_close else 0,
            timestamp=data.get("t", 0),
        )

        logger.debug(f"Fetched Finnhub quote for {ticker}: ${quote.current:.2f}")

        return [self._create_observation(
            data={
                "price": quote.current,
                "previous_close": quote.previous_close,
                "change": round(quote.change, 4),
                "change_percent": round(quote.change_percent, 2),
                "high": quote.high,
                "low": quote.low,
                "open": quote.open,
            },
            ticker=ticker,
        )]

    def _fetch_profile(self, ticker: str) -> list[Observation]:
        """Fetch company profile from Finnhub.

        Uses persistent cache (profiles rarely change).
        """
        cache = get_cache()
        cache_ttl = timedelta(days=7)  # Profiles are very stable

        # Check cache first
        cached = cache.get("finnhub_profile", ticker=ticker)
        if cached is not None:
            logger.debug(f"Using cached Finnhub profile for {ticker}")
            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.FUNDAMENTAL,
                data=cached,
                ticker=ticker,
                reliability=self.reliability,
            )]

        api_key = self._get_api_key()
        url = f"{self.BASE_URL}/stock/profile2?symbol={ticker}"
        if api_key:
            url += f"&token={api_key}"

        data = self._http_get_json(url)

        if not data or not data.get("name"):
            raise DataError.empty(
                source=self.source_name,
                description=f"No profile data for {ticker}",
            )

        profile = FinnhubProfile(
            symbol=ticker,
            name=data.get("name", ticker),
            country=data.get("country"),
            currency=data.get("currency"),
            exchange=data.get("exchange"),
            ipo=data.get("ipo"),
            market_cap=data.get("marketCapitalization"),
            industry=data.get("finnhubIndustry"),
            sector=None,  # Finnhub uses industry, not sector
            website=data.get("weburl"),
        )

        result = {
            "company_name": profile.name,
            "country": profile.country,
            "currency": profile.currency,
            "exchange": profile.exchange,
            "ipo_date": profile.ipo,
            "market_cap": profile.market_cap * 1_000_000 if profile.market_cap else None,  # Convert to full value
            "industry": profile.industry,
            "website": profile.website,
        }

        # Cache the result
        cache.set("finnhub_profile", result, cache_ttl, ticker=ticker)

        logger.debug(f"Fetched Finnhub profile for {ticker}: {profile.name}")

        return [Observation(
            source=self.source_name,
            timestamp=datetime.now(),
            category=Category.FUNDAMENTAL,
            data=result,
            ticker=ticker,
            reliability=self.reliability,
        )]

    def _fetch_insider_transactions(
        self,
        ticker: str,
        from_date: str | None = None,
        to_date: str | None = None,
        store_in_db: bool = True,
    ) -> list[Observation]:
        """
        Fetch insider transactions from Finnhub.

        Endpoint: /stock/insider-transactions?symbol={ticker}
        Data sourced from SEC Form 3, 4, 5 filings.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            from_date: Optional start date (YYYY-MM-DD)
            to_date: Optional end date (YYYY-MM-DD)
            store_in_db: Whether to persist to database (default True)

        Returns:
            List of Observations with insider transaction data.
            Each observation contains one insider transaction.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise DataError.empty(
                source=self.source_name,
                description="Finnhub API key required for insider transactions",
            )

        url = f"{self.BASE_URL}/stock/insider-transactions?symbol={ticker}"
        url += f"&token={api_key}"
        if from_date:
            url += f"&from={from_date}"
        if to_date:
            url += f"&to={to_date}"

        data = self._http_get_json(url)

        if not data or "data" not in data:
            raise DataError.empty(
                source=self.source_name,
                description=f"No insider transaction data for {ticker}",
            )

        transactions = data.get("data", [])
        if not transactions:
            logger.debug(f"No insider transactions found for {ticker}")
            return []

        # Get database reference if storing
        db = get_db() if store_in_db else None
        added = 0
        skipped = 0

        observations = []
        for txn in transactions:
            try:
                # Parse transaction
                insider_txn = FinnhubInsiderTransaction(
                    symbol=txn.get("symbol", ticker),
                    name=txn.get("name", "Unknown"),
                    share=int(txn.get("share", 0)),
                    change=int(txn.get("change", 0)),
                    filing_date=txn.get("filingDate", ""),
                    transaction_date=txn.get("transactionDate", ""),
                    transaction_code=txn.get("transactionCode", ""),
                    transaction_price=txn.get("transactionPrice"),
                )

                # Determine transaction type from change sign
                txn_type = "buy" if insider_txn.change > 0 else "sell"

                # Check if C-suite based on transaction patterns
                # Note: Finnhub doesn't provide officer title directly.
                # We mark all as potential C-suite for now; the scoring
                # function uses cluster detection which doesn't require title.
                is_c_suite = self._is_likely_c_suite(insider_txn.name, insider_txn.change)

                obs_data = {
                    "insider_name": insider_txn.name,
                    "shares_after": insider_txn.share,
                    "shares_change": abs(insider_txn.change),
                    "transaction_type": txn_type,
                    "filing_date": insider_txn.filing_date,
                    "transaction_date": insider_txn.transaction_date,
                    "transaction_code": insider_txn.transaction_code,
                    "transaction_price": insider_txn.transaction_price,
                    "is_c_suite": is_c_suite,
                    # For scoring pipeline compatibility
                    "officer_title": "Unknown",  # Not provided by Finnhub
                }

                # Parse transaction date for observation timestamp
                try:
                    txn_dt = datetime.strptime(insider_txn.transaction_date, "%Y-%m-%d")
                    txn_date = txn_dt.date()
                except ValueError:
                    txn_dt = datetime.now()
                    txn_date = None

                # Parse filing date
                try:
                    filing_date = datetime.strptime(insider_txn.filing_date, "%Y-%m-%d").date()
                except ValueError:
                    filing_date = None

                observations.append(Observation(
                    source=self.source_name,
                    timestamp=txn_dt,
                    category=Category.FUNDAMENTAL,
                    data=obs_data,
                    ticker=ticker,
                    reliability=self.reliability,
                ))

                # Store in database
                if db:
                    # Generate unique ID from ticker + name + date + shares
                    id_str = f"{ticker}:{insider_txn.name}:{insider_txn.transaction_date}:{insider_txn.change}"
                    txn_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

                    db_txn = DBInsiderTransaction(
                        id=txn_id,
                        ticker=ticker,
                        insider_name=insider_txn.name,
                        transaction_type=txn_type,
                        shares=abs(insider_txn.change),
                        shares_after=insider_txn.share if insider_txn.share > 0 else None,
                        transaction_date=txn_date,
                        filing_date=filing_date,
                        transaction_code=insider_txn.transaction_code,
                        transaction_price=insider_txn.transaction_price,
                        officer_title="Unknown",
                        is_c_suite=is_c_suite,
                    )
                    if db.upsert_insider_transaction(db_txn):
                        added += 1
                    else:
                        skipped += 1

            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping malformed insider transaction: {e}")
                continue

        logger.debug(f"Fetched {len(observations)} insider transactions for {ticker} (added={added}, skipped={skipped})")
        return observations

    def _is_likely_c_suite(self, name: str, change: int) -> bool:
        """
        Heuristic to identify likely C-suite executives.

        Since Finnhub doesn't provide officer title, we use transaction size
        as a proxy. Large buys (>$100k at typical prices) are more likely
        from executives with significant compensation.

        This is a rough heuristic - the cluster detection algorithm in
        scoring.py handles the actual signal detection.
        """
        # Large transactions (>10k shares) more likely from executives
        if abs(change) > 10000:
            return True
        return False

    def _get_api_key(self) -> str | None:
        """Get Finnhub API key from config or environment."""
        # Check config first
        key = self._settings.config.api_keys.finnhub
        if key:
            return key
        # Fall back to environment variables (check both naming conventions)
        return os.environ.get("FINNHUB_API_KEY") or os.environ.get("FINNHUB_KEY")

    def is_configured(self) -> bool:
        """Check if Finnhub adapter has API key configured."""
        return self._get_api_key() is not None

    # Convenience methods
    def get_quote(self, ticker: str) -> list[Observation]:
        """Get real-time quote for a ticker."""
        return self.fetch(ticker=ticker, data_type="quote")

    def get_profile(self, ticker: str) -> list[Observation]:
        """Get company profile for a ticker."""
        return self.fetch(ticker=ticker, data_type="profile")

    def get_insider_transactions(
        self,
        ticker: str,
        days: int = 90,
        store_in_db: bool = True,
    ) -> list[Observation]:
        """
        Get insider transactions for a ticker.

        Args:
            ticker: Stock symbol
            days: Number of days of history (default 90 for cluster detection)
            store_in_db: Whether to persist to database (default True)

        Returns:
            List of Observations with insider transaction data
        """
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        return self._fetch_insider_transactions(
            ticker=ticker,
            from_date=from_date,
            to_date=to_date,
            store_in_db=store_in_db,
        )

    # ========================================================================
    # Congressional Trading Endpoint
    # ========================================================================

    def get_congressional_trading(
        self,
        symbol: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 100,
    ) -> list[Observation]:
        """
        Fetch congressional stock trading data from Finnhub.

        Endpoint: /stock/congressional-trading
        Returns trades by US Congress members disclosed via STOCK Act filings.

        Args:
            symbol: Optional stock symbol to filter (e.g., "AAPL")
            from_date: Optional start date (YYYY-MM-DD)
            to_date: Optional end date (YYYY-MM-DD)
            limit: Maximum number of trades to return (default 100)

        Returns:
            List of Observations with congressional trade data.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise DataError.empty(
                source=self.source_name,
                description="Finnhub API key required for congressional trading",
            )

        url = f"{self.BASE_URL}/stock/congressional-trading?token={api_key}"
        if symbol:
            url += f"&symbol={symbol.upper()}"
        if from_date:
            url += f"&from={from_date}"
        if to_date:
            url += f"&to={to_date}"

        data = self._http_get_json(url)

        if not data or "data" not in data:
            logger.debug(f"No congressional trading data returned")
            return []

        trades = data.get("data", [])
        if not trades:
            logger.debug(f"No congressional trades found")
            return []

        observations = []
        for trade in trades[:limit]:
            try:
                # Parse transaction type
                tx_type = trade.get("transactionType", "").lower()
                if "purchase" in tx_type or "buy" in tx_type:
                    direction = "buy"
                elif "sale" in tx_type or "sell" in tx_type:
                    direction = "sell"
                else:
                    direction = "exchange"

                # Parse amount range
                amount_from = trade.get("amountFrom", 0) or 0
                amount_to = trade.get("amountTo", 0) or amount_from

                # Calculate signal strength based on amount
                mid_amount = (amount_from + amount_to) / 2
                if mid_amount <= 15000:
                    strength = 0.3
                elif mid_amount <= 50000:
                    strength = 0.4
                elif mid_amount <= 100000:
                    strength = 0.5
                elif mid_amount <= 250000:
                    strength = 0.6
                elif mid_amount <= 500000:
                    strength = 0.7
                elif mid_amount <= 1000000:
                    strength = 0.8
                else:
                    strength = 0.9

                # Parse representative name and position
                rep_name = trade.get("name", "Unknown")
                position = trade.get("position", "")

                # Determine chamber from position
                chamber = "Senate" if "senator" in position.lower() else "House"

                # Get party from position if available
                party = "I"  # Default to Independent
                if "democrat" in position.lower() or "(d)" in position.lower():
                    party = "D"
                elif "republican" in position.lower() or "(r)" in position.lower():
                    party = "R"

                ticker = trade.get("symbol", "")
                asset_name = trade.get("assetName", "")

                # Generate summary
                action = "bought" if direction == "buy" else "sold"
                amount_str = f"${amount_from:,.0f} - ${amount_to:,.0f}"
                summary = f"{rep_name} ({party}-{chamber}) {action} {ticker or asset_name} ({amount_str})"

                # Generate unique ID
                filing_date = trade.get("filingDate", "")
                id_str = f"{rep_name}:{ticker}:{filing_date}"
                trade_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

                # Parse filing date for timestamp
                try:
                    timestamp = datetime.strptime(filing_date, "%Y-%m-%d")
                except ValueError:
                    timestamp = datetime.now()

                obs_data = {
                    "id": trade_id,
                    "signal_type": "congress",
                    "ticker": ticker,
                    "direction": direction,
                    "strength": strength,
                    "summary": summary,
                    "details": {
                        "politician": rep_name,
                        "party": party,
                        "chamber": chamber,
                        "position": position,
                        "amount_low": amount_from,
                        "amount_high": amount_to,
                        "asset_description": asset_name,
                        "transaction_date": trade.get("transactionDate"),
                        "disclosure_date": filing_date,
                        "owner_type": trade.get("ownerType", ""),
                    },
                }

                observations.append(Observation(
                    source="congress_finnhub",
                    timestamp=timestamp,
                    category=Category.SENTIMENT,
                    data=obs_data,
                    ticker=ticker if ticker else None,
                    reliability=0.9,  # Official STOCK Act disclosures
                ))

            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping malformed congressional trade: {e}")
                continue

        logger.info(f"Fetched {len(observations)} congressional trades from Finnhub")
        return observations

    def get_recent_congressional_trades(
        self,
        days: int = 60,
        limit: int = 100,
    ) -> list[Observation]:
        """Get recent congressional trades from the past N days."""
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        return self.get_congressional_trading(
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
