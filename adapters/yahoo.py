"""
Yahoo Finance adapter.

Most reliable free source for:
- Price data (real-time quotes, historical)
- Fundamentals (PE, market cap, revenue)
- Company news
- Analyst recommendations

Uses yfinance library for fundamentals as the raw API now requires auth.
Uses persistent cache to reduce API calls for expensive operations.
"""

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any

import yfinance as yf

from domain import Observation, Category
from ports import FetchError, DataError, ValidationError
from db import get_db, OptionsActivity as DBOptionsActivity

from .base import BaseAdapter
from .cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Typed price data from Yahoo."""
    symbol: str
    price: float
    previous_close: float
    change: float
    change_percent: float
    volume: int
    market_cap: float | None = None


@dataclass
class FundamentalData:
    """Typed fundamental data from Yahoo."""
    symbol: str
    pe_trailing: float | None
    pe_forward: float | None
    peg_ratio: float | None
    price_to_book: float | None
    revenue_growth: float | None
    profit_margin: float | None
    recommendation: str | None  # buy, hold, sell
    sector: str | None = None
    industry: str | None = None


@dataclass
class NewsItem:
    """Typed news item from Yahoo."""
    title: str
    url: str
    published: datetime | None
    source: str | None


class YahooAdapter(BaseAdapter):
    """
    Yahoo Finance data adapter.

    Provides price, fundamental, and news data.
    No API key required.
    """

    BASE_URL = "https://query1.finance.yahoo.com"

    @property
    def source_name(self) -> str:
        return "yahoo"

    @property
    def category(self) -> Category:
        return Category.PRICE  # Primary category

    @property
    def reliability(self) -> float:
        return 0.9  # Very reliable

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Route to specific fetch method based on data_type."""
        data_type = kwargs.get("data_type", "price")
        ticker = kwargs.get("ticker")

        # Input validation
        if not ticker:
            raise ValidationError(
                reason="ticker parameter is required",
                field="ticker",
                source=self.source_name,
            )

        ticker = self._validate_ticker(ticker)

        valid_types = ("price", "fundamentals", "news")
        if data_type not in valid_types:
            raise ValidationError(
                reason=f"data_type must be one of {valid_types}, got '{data_type}'",
                field="data_type",
                value=data_type,
                source=self.source_name,
            )

        if data_type == "price":
            return self._fetch_price(ticker)
        elif data_type == "fundamentals":
            return self._fetch_fundamentals(ticker)
        else:  # news
            return self._fetch_news(ticker)

    def _fetch_price(self, ticker: str) -> list[Observation]:
        """Fetch current price data."""
        url = f"{self.BASE_URL}/v8/finance/chart/{ticker}?interval=1d&range=1d"
        data = self._http_get_json(url)

        result = data.get("chart", {}).get("result", [])
        if not result:
            raise DataError.empty(
                source=self.source_name,
                description=f"No price data returned for {ticker}",
            )

        meta = result[0].get("meta", {})
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]

        price = meta.get("regularMarketPrice")
        if price is None:
            raise DataError.missing(self.source_name, field="regularMarketPrice")

        # Try previousClose first, then chartPreviousClose as fallback
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose") or price

        price_data = PriceData(
            symbol=meta.get("symbol", ticker),
            price=price,
            previous_close=prev_close,
            change=price - prev_close,
            change_percent=((price - prev_close) / prev_close * 100) if prev_close else 0,
            volume=quote.get("volume", [0])[-1] if quote.get("volume") else 0,
            market_cap=meta.get("marketCap"),
        )

        logger.debug(
            f"Fetched price for {ticker}: ${price_data.price:.2f}",
            extra={
                "ticker": ticker,
                "price": price_data.price,
                "change_percent": price_data.change_percent,
            },
        )

        return [self._create_observation(
            data={
                "price": price_data.price,
                "previous_close": price_data.previous_close,
                "change": price_data.change,
                "change_percent": price_data.change_percent,
                "volume": price_data.volume,
                "market_cap": price_data.market_cap,
            },
            ticker=ticker,
        )]

    def _fetch_fundamentals(self, ticker: str) -> list[Observation]:
        """Fetch fundamental data (PE, growth, etc.) using yfinance library.

        Uses persistent cache to avoid redundant API calls - fundamentals
        don't change frequently, so caching for 24h is safe.
        """
        cache = get_cache()
        cache_ttl = timedelta(hours=24)  # Fundamentals are stable

        # Check persistent cache first
        cached_info = cache.get("yahoo_fundamentals", ticker=ticker)
        if cached_info is not None:
            logger.debug(f"Using cached fundamentals for {ticker}")
            info = cached_info
        else:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # Cache successful response
                if info and info.get("regularMarketPrice") is not None:
                    cache.set("yahoo_fundamentals", info, cache_ttl, ticker=ticker)
            except Exception as e:
                logger.warning(f"Failed to fetch fundamentals for {ticker}: {e}")
                info = None

        try:
            if not info or info.get("regularMarketPrice") is None:
                raise DataError.empty(
                    source=self.source_name,
                    description=f"No fundamental data returned for {ticker}",
                )

            # Extract fundamental metrics
            fundamental_data = FundamentalData(
                symbol=ticker,
                pe_trailing=info.get("trailingPE"),
                pe_forward=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                revenue_growth=info.get("revenueGrowth"),
                profit_margin=info.get("profitMargins"),
                recommendation=info.get("recommendationKey", "hold"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )

            # Extract additional metrics for richer analysis
            additional_data = {
                "pe_trailing": fundamental_data.pe_trailing,
                "pe_forward": fundamental_data.pe_forward,
                "peg_ratio": fundamental_data.peg_ratio,
                "price_to_book": fundamental_data.price_to_book,
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "revenue_growth": fundamental_data.revenue_growth,
                "earnings_growth": info.get("earningsGrowth"),
                "profit_margin": fundamental_data.profit_margin,
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "recommendation": fundamental_data.recommendation,
                "analyst_rating": info.get("recommendationMean"),
                "price_target": info.get("targetMeanPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "beta": info.get("beta"),
                # Company info
                "company_name": info.get("shortName") or info.get("longName") or ticker,
                # Sector and industry for scoring
                "sector": fundamental_data.sector,
                "industry": fundamental_data.industry,
                # Technical data for momentum scoring
                "fifty_day_average": info.get("fiftyDayAverage"),
                "two_hundred_day_average": info.get("twoHundredDayAverage"),
                "average_volume": info.get("averageVolume"),
                "current_price": info.get("regularMarketPrice"),
            }

            logger.debug(
                f"Fetched fundamentals for {ticker}: PE={fundamental_data.pe_trailing}",
                extra={
                    "ticker": ticker,
                    "pe_trailing": fundamental_data.pe_trailing,
                    "pe_forward": fundamental_data.pe_forward,
                },
            )

            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.FUNDAMENTAL,
                data=additional_data,
                ticker=ticker,
                reliability=self.reliability,
            )]

        except Exception as e:
            logger.warning(
                f"Fundamentals unavailable for {ticker}: {e}",
                extra={"ticker": ticker},
            )
            raise FetchError(
                code="E999",
                message=f"Failed to fetch fundamentals for {ticker}: {e}",
                source=self.source_name,
            )

    def _fetch_news(self, ticker: str) -> list[Observation]:
        """Fetch company news."""
        # Get news count from config
        news_count = self._settings.config.data_sources.yahoo_news_count
        url = f"{self.BASE_URL}/v1/finance/search?q={ticker}&newsCount={news_count}"
        data = self._http_get_json(url)

        news_items = data.get("news", [])
        if not news_items:
            logger.debug(f"No news found for {ticker}")
            return []

        observations = []
        for item in news_items:
            pub_time = item.get("providerPublishTime")
            published = datetime.fromtimestamp(pub_time) if pub_time else None

            news = NewsItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                published=published,
                source=item.get("publisher"),
            )

            observations.append(Observation(
                source=self.source_name,
                timestamp=published or datetime.now(),
                category=Category.NEWS,
                data={
                    "title": news.title,
                    "url": news.url,
                    "publisher": news.source,
                },
                ticker=ticker,
                reliability=self.reliability,
            ))

        logger.debug(
            f"Fetched {len(observations)} news items for {ticker}",
            extra={"ticker": ticker, "count": len(observations)},
        )

        return observations

    def _fetch_price_history(self, ticker: str, days: int = 30) -> list[Observation]:
        """Fetch historical price data for charting.

        Uses persistent cache to reduce API calls. Price history is cached
        for 4 hours since it only changes once per trading day.
        """
        cache = get_cache()
        cache_ttl = timedelta(hours=4)  # Update a few times per day

        # Check persistent cache first
        cache_key = f"{ticker}:{days}"
        cached_history = cache.get("yahoo_price_history", key=cache_key)
        if cached_history is not None:
            logger.debug(f"Using cached price history for {ticker}")
            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.PRICE,
                data={"price_history": cached_history},
                ticker=ticker,
                reliability=self.reliability,
            )]

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{days}d")

            if hist.empty:
                logger.debug(f"No price history for {ticker}")
                return []

            price_points = []
            for dt, row in hist.iterrows():
                price_points.append({
                    "time": dt.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })

            # Cache the result
            if price_points:
                cache.set("yahoo_price_history", price_points, cache_ttl, key=cache_key)

            logger.debug(f"Fetched {len(price_points)} price points for {ticker}")

            return [Observation(
                source=self.source_name,
                timestamp=datetime.now(),
                category=Category.PRICE,
                data={"price_history": price_points},
                ticker=ticker,
                reliability=self.reliability,
            )]

        except Exception as e:
            logger.warning(f"Price history unavailable for {ticker}: {e}")
            return []

    # Convenience methods for cleaner API
    def get_price(self, ticker: str) -> list[Observation]:
        """Get current price for a ticker."""
        return self.fetch(ticker=ticker, data_type="price")

    def get_fundamentals(self, ticker: str) -> list[Observation]:
        """Get fundamental data for a ticker."""
        return self.fetch(ticker=ticker, data_type="fundamentals")

    def get_news(self, ticker: str) -> list[Observation]:
        """Get news for a ticker."""
        return self.fetch(ticker=ticker, data_type="news")

    def get_price_history(self, ticker: str, days: int = 30) -> list[dict]:
        """Get historical price data for charting."""
        obs = self._fetch_price_history(ticker, days)
        if obs and "price_history" in obs[0].data:
            return obs[0].data["price_history"]
        return []

    # ========================================================================
    # Batch Price Fetching (Efficient for large ticker lists)
    # ========================================================================

    def get_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """
        Fetch current prices for multiple tickers efficiently using yf.download().

        This is MUCH more efficient than calling get_price() individually:
        - 500 tickers in ~6 seconds vs ~8+ minutes
        - Uses ~2 API calls vs 500 individual calls

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict of ticker -> price data:
            {
                "AAPL": {
                    "price": 150.0,
                    "previous_close": 149.0,
                    "change": 1.0,
                    "change_percent": 0.67,
                    "volume": 50000000,
                },
                ...
            }
        """
        if not tickers:
            return {}

        # Normalize tickers
        tickers = [t.upper().strip() for t in tickers]
        results = {}

        try:
            # yf.download batches internally - very efficient
            # period="5d" gives us enough data for change calculation
            data = yf.download(
                tickers,
                period="5d",
                progress=False,
                threads=True,
            )

            if data.empty:
                logger.warning("No data returned from yf.download batch")
                return {}

            # Handle single vs multiple ticker response format
            if len(tickers) == 1:
                ticker = tickers[0]
                if len(data) >= 1:
                    latest = data.iloc[-1]
                    prev = data.iloc[-2] if len(data) >= 2 else latest

                    price = float(latest["Close"])
                    prev_close = float(prev["Close"])
                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    results[ticker] = {
                        "price": round(price, 2),
                        "previous_close": round(prev_close, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                        "volume": int(latest["Volume"]) if latest["Volume"] else None,
                    }
            else:
                # Multiple tickers: columns are MultiIndex (metric, ticker)
                for ticker in tickers:
                    try:
                        if ticker not in data["Close"].columns:
                            continue

                        ticker_data = data["Close"][ticker].dropna()
                        if len(ticker_data) < 1:
                            continue

                        price = float(ticker_data.iloc[-1])
                        prev_close = float(ticker_data.iloc[-2]) if len(ticker_data) >= 2 else price

                        change = price - prev_close
                        change_pct = (change / prev_close * 100) if prev_close else 0

                        volume = None
                        if "Volume" in data.columns.get_level_values(0):
                            vol_data = data["Volume"][ticker].dropna()
                            if len(vol_data) >= 1:
                                volume = int(vol_data.iloc[-1])

                        results[ticker] = {
                            "price": round(price, 2),
                            "previous_close": round(prev_close, 2),
                            "change": round(change, 2),
                            "change_percent": round(change_pct, 2),
                            "volume": volume,
                        }
                    except Exception as e:
                        logger.debug(f"Skipping {ticker} in batch: {e}")
                        continue

            logger.info(f"Batch fetched prices for {len(results)}/{len(tickers)} tickers")

        except Exception as e:
            logger.error(f"Batch price fetch failed: {e}")

        return results

    # ========================================================================
    # Unusual Options Activity Detection
    # ========================================================================

    def get_unusual_options(
        self,
        ticker: str,
        threshold: float = 3.0,
        min_volume: int = 100,
        store_in_db: bool = True,
    ) -> list[Observation]:
        """
        Detect unusual options activity for a ticker.

        Flags options where volume/OI ratio exceeds threshold,
        indicating unusual interest/activity.

        Args:
            ticker: Stock ticker symbol
            threshold: Volume/OI ratio threshold (default 3.0)
            min_volume: Minimum volume to consider (default 100)
            store_in_db: Whether to store results in database (default True)

        Returns:
            List of Observations for unusual options
        """
        ticker = self._validate_ticker(ticker)
        db = get_db() if store_in_db else None
        run = db.start_scrape_run("options") if db else None

        try:
            stock = yf.Ticker(ticker)

            # Get available expiration dates
            expirations = stock.options
            if not expirations:
                logger.debug(f"No options data for {ticker}")
                if run:
                    db.complete_scrape_run(run)
                return []

            unusual_options = []
            added = 0
            skipped = 0

            # Check first 3 expiration dates (near-term activity is most relevant)
            for expiry in expirations[:3]:
                try:
                    chain = stock.option_chain(expiry)
                except Exception as e:
                    logger.debug(f"Failed to get options chain for {ticker} {expiry}: {e}")
                    continue

                # Check calls
                for _, row in chain.calls.iterrows():
                    unusual = self._check_unusual_option(
                        row, "call", ticker, expiry, threshold, min_volume
                    )
                    if unusual:
                        unusual_options.append(unusual)
                        # Store in database
                        if db:
                            db_activity = self._observation_to_db_options(unusual)
                            if db.upsert_options_activity(db_activity):
                                added += 1
                            else:
                                skipped += 1

                # Check puts
                for _, row in chain.puts.iterrows():
                    unusual = self._check_unusual_option(
                        row, "put", ticker, expiry, threshold, min_volume
                    )
                    if unusual:
                        unusual_options.append(unusual)
                        # Store in database
                        if db:
                            db_activity = self._observation_to_db_options(unusual)
                            if db.upsert_options_activity(db_activity):
                                added += 1
                            else:
                                skipped += 1

            # Sort by volume/OI ratio (most unusual first) and limit
            unusual_options.sort(
                key=lambda x: x.data.get("details", {}).get("volume_oi_ratio", 0),
                reverse=True,
            )

            if run:
                db.complete_scrape_run(run, records_added=added, records_skipped=skipped)

            logger.info(f"Found {len(unusual_options)} unusual options for {ticker} (added={added}, skipped={skipped})")
            return unusual_options[:10]  # Limit to top 10 most unusual

        except Exception as e:
            logger.warning(f"Failed to get options for {ticker}: {e}")
            if run:
                db.complete_scrape_run(run, error=str(e))
            return []

    def get_options_from_database(self, ticker: str | None = None, hours: int = 24, limit: int = 100) -> list[Observation]:
        """
        Fetch options activity from database.

        Args:
            ticker: Optional ticker to filter by
            hours: Look back this many hours (default 24)
            limit: Maximum records to return

        Returns:
            List of Observations from stored options activity
        """
        db = get_db()
        activities = db.get_options_activity(ticker=ticker, hours=hours, limit=limit)

        observations = []
        for activity in activities:
            observations.append(self._db_options_to_observation(activity))

        logger.info(f"Loaded {len(observations)} options activities from database")
        return observations

    def _observation_to_db_options(self, obs: Observation) -> DBOptionsActivity:
        """Convert Observation to database OptionsActivity model."""
        details = obs.data.get("details", {})
        expiry_str = details.get("expiry", "")

        # Parse expiry date
        if expiry_str:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        else:
            expiry = date.today()

        return DBOptionsActivity(
            id=obs.data.get("id", ""),
            ticker=obs.ticker,
            option_type=details.get("option_type", "call"),
            strike=details.get("strike", 0.0),
            expiry=expiry,
            volume=details.get("volume", 0),
            open_interest=details.get("open_interest", 0),
            volume_oi_ratio=details.get("volume_oi_ratio", 0.0),
            implied_volatility=details.get("implied_volatility"),
            premium_total=details.get("premium_total"),
            direction=obs.data.get("direction", "buy"),
            strength=obs.data.get("strength", 0.5),
        )

    def _db_options_to_observation(self, activity: DBOptionsActivity) -> Observation:
        """Convert database OptionsActivity to Observation."""
        summary = (
            f"Unusual {activity.option_type.upper()} activity on {activity.ticker}: "
            f"${activity.strike:.0f} {activity.expiry}, Volume/OI={activity.volume_oi_ratio:.1f}x"
        )
        if activity.premium_total:
            summary += f", ${activity.premium_total/1000:.0f}K premium"

        return Observation(
            source=self.source_name,
            timestamp=activity.created_at,
            category=Category.SENTIMENT,
            data={
                "id": activity.id,
                "signal_type": "options",
                "ticker": activity.ticker,
                "direction": activity.direction,
                "strength": activity.strength,
                "summary": summary,
                "details": {
                    "option_type": activity.option_type,
                    "strike": activity.strike,
                    "expiry": activity.expiry.isoformat() if activity.expiry else None,
                    "volume": activity.volume,
                    "open_interest": activity.open_interest,
                    "volume_oi_ratio": activity.volume_oi_ratio,
                    "implied_volatility": activity.implied_volatility,
                    "premium_total": activity.premium_total,
                },
            },
            ticker=activity.ticker,
            reliability=0.7,
        )

    def _check_unusual_option(
        self,
        row,
        option_type: str,
        ticker: str,
        expiry: str,
        threshold: float,
        min_volume: int,
    ) -> Observation | None:
        """Check if an option contract shows unusual activity."""

        # Safely convert volume and OI, handling NaN values
        volume_raw = row.get("volume", 0)
        if volume_raw is None or (isinstance(volume_raw, float) and math.isnan(volume_raw)):
            volume = 0
        else:
            volume = int(volume_raw)

        oi_raw = row.get("openInterest", 0)
        if oi_raw is None or (isinstance(oi_raw, float) and math.isnan(oi_raw)):
            open_interest = 0
        else:
            open_interest = int(oi_raw)

        # Skip if below minimum volume
        if volume < min_volume:
            return None

        # Calculate volume/OI ratio
        if open_interest <= 0:
            # High volume with no OI is very unusual
            if volume >= min_volume * 5:
                vol_oi_ratio = 10.0  # Cap at 10x
            else:
                return None
        else:
            vol_oi_ratio = volume / open_interest

        # Check if unusual
        if vol_oi_ratio < threshold:
            return None

        # This option is unusual - create observation
        strike = float(row.get("strike", 0))
        last_price = float(row.get("lastPrice", 0) or 0)
        implied_vol = row.get("impliedVolatility")
        if implied_vol is not None:
            implied_vol = float(implied_vol)

        # Calculate premium total
        premium_total = volume * last_price * 100 if last_price else None

        # Determine direction (calls = bullish, puts = bearish)
        direction = "buy" if option_type == "call" else "sell"

        # Calculate signal strength based on vol/oi ratio and premium
        strength = min(0.9, 0.3 + (vol_oi_ratio / 20))  # Scale up to 0.9
        if premium_total and premium_total > 1000000:
            strength = min(0.95, strength + 0.1)  # Boost for large premium

        # Generate summary
        summary = (
            f"Unusual {option_type.upper()} activity on {ticker}: "
            f"${strike:.0f} {expiry}, Volume/OI={vol_oi_ratio:.1f}x"
        )
        if premium_total:
            summary += f", ${premium_total/1000:.0f}K premium"

        # Generate unique ID
        id_str = f"{ticker}:{option_type}:{strike}:{expiry}"
        option_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

        return Observation(
            source=self.source_name,
            timestamp=datetime.now(),
            category=Category.SENTIMENT,
            data={
                "id": option_id,
                "signal_type": "options",
                "ticker": ticker,
                "direction": direction,
                "strength": round(strength, 2),
                "summary": summary,
                "details": {
                    "option_type": option_type,
                    "strike": strike,
                    "expiry": expiry,
                    "volume": volume,
                    "open_interest": open_interest,
                    "volume_oi_ratio": round(vol_oi_ratio, 2),
                    "implied_volatility": round(implied_vol, 4) if implied_vol else None,
                    "premium_total": round(premium_total, 2) if premium_total else None,
                },
            },
            ticker=ticker,
            reliability=0.7,  # Lower reliability for options signals
        )
