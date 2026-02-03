#!/usr/bin/env python3
"""
Generate frontend report data from pipeline.

Runs the pipeline and exports data in the format expected by the Astro frontend.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env BEFORE any other imports
# (imports may trigger config loading which caches env vars)
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Force reload settings to pick up .env vars (clears @lru_cache)
from config import reload_settings
reload_settings()

from orchestration.pipeline import Pipeline, PipelineConfig
from domain import Timeframe, Trend, Impact
from domain.briefing import generate_daily_briefing, briefing_to_dict
from adapters import CalendarAdapter, RssAdapter
from db import (
    get_db,
    StockPick as DBStockPick,
    StockMetrics as DBStockMetrics,
    PricePoint as DBPricePoint,
    MacroIndicator as DBMacroIndicator,
    MacroRisk as DBMacroRisk,
    NewsItem as DBNewsItem,
    HedgeFundHolding,
)
from domain.backtest import run_backtest, BacktestConfig, BacktestResult
from domain.indicators import rsi, macd, bollinger_bands, sma


def compute_indicators_for_history(price_history: list[dict]) -> dict | None:
    """
    Compute all technical indicators for a stock's price history.

    Returns dict with pre-computed indicator arrays, or None if insufficient data.
    """
    if not price_history or len(price_history) < 50:
        return None

    # Extract close prices
    closes = [float(p["close"]) for p in price_history]

    # Compute indicators using domain layer
    rsi_values = rsi(closes, 14)
    macd_line, macd_signal_line, macd_histogram = macd(closes, 12, 26, 9)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes, 20, 2.0)
    sma50_values = sma(closes, 50)
    sma200_values = sma(closes, 200)

    return {
        "rsi": rsi_values,
        "macdLine": macd_line,
        "macdSignal": macd_signal_line,
        "macdHistogram": macd_histogram,
        "bbUpper": bb_upper,
        "bbMiddle": bb_middle,
        "bbLower": bb_lower,
        "sma50": sma50_values,
        "sma200": sma200_values,
    }


def map_sector(sector: str | None) -> str:
    """Map domain sector to frontend sector type."""
    mapping = {
        "technology": "technology",
        "healthcare": "healthcare",
        "financial services": "finance",
        "financials": "finance",
        "consumer discretionary": "consumer",
        "consumer staples": "consumer",
        "consumer cyclical": "consumer",
        "consumer defensive": "consumer",
        "energy": "energy",
        "industrials": "industrials",
        "basic materials": "materials",
        "materials": "materials",
        "utilities": "utilities",
        "real estate": "real_estate",
        "communication services": "communications",
        "communications": "communications",
    }
    if not sector:
        return "technology"
    return mapping.get(sector.lower(), "technology")


def map_trend(trend: Trend) -> str:
    """Map domain Trend to frontend trend type."""
    return {
        Trend.RISING: "up",
        Trend.FALLING: "down",
        Trend.STABLE: "flat",
    }.get(trend, "flat")


def backtest_result_to_frontend(result: BacktestResult) -> dict:
    """Convert BacktestResult to frontend format."""
    return {
        "startDate": result.start_date.isoformat(),
        "endDate": result.end_date.isoformat(),
        "timeframe": result.timeframe,
        "totalTrades": result.total_trades,
        "tickersAnalyzed": result.tickers_analyzed,
        "performance": {
            "totalReturn": round(result.total_return, 2),
            "benchmarkReturn": round(result.benchmark_return, 2),
            "alpha": round(result.alpha, 2),
            "hitRate": round(result.hit_rate, 1),
            "winRate": round(result.win_rate, 1),
            "avgTradeReturn": round(result.avg_trade_return, 2),
            "avgAlphaPerTrade": round(result.avg_alpha_per_trade, 2),
            "sharpeRatio": round(result.sharpe_ratio, 2),
            "maxDrawdown": round(result.max_drawdown, 2),
            "winLossRatio": round(result.win_loss_ratio, 2),
        },
        "bestTrade": {
            "ticker": result.best_trade.ticker,
            "returnPct": round(result.best_trade.return_pct, 2),
        } if result.best_trade else None,
        "worstTrade": {
            "ticker": result.worst_trade.ticker,
            "returnPct": round(result.worst_trade.return_pct, 2),
        } if result.worst_trade else None,
        "monthlyReturns": [
            {
                "month": mr.month.isoformat(),
                "portfolioReturn": round(mr.portfolio_return, 2),
                "benchmarkReturn": round(mr.benchmark_return, 2),
                "numPicks": mr.num_picks,
                "topPerformer": mr.top_performer,
                "worstPerformer": mr.worst_performer,
            }
            for mr in result.monthly_returns
        ],
        "limitations": [
            "Uses current fundamentals (lookahead bias for value/quality)",
            "No transaction costs modeled",
            "Survivorship bias if universe changed",
        ],
        "executedAt": result.executed_at.isoformat(),
    }


def generate_backtest_data(universe: list[str]) -> dict | None:
    """
    Run backtests for all timeframes in parallel and return frontend-formatted data.

    Returns None if backtest fails or insufficient data.
    """
    from datetime import date

    # Define backtest period - use available historical data
    # Data range: July 2024 to present
    start_date = date(2024, 8, 1)
    end_date = date(2025, 12, 31)

    config = BacktestConfig(
        top_n_picks=5,
        min_conviction=0.4,
    )

    results = {}
    now = datetime.now().isoformat()

    def _run_single_backtest(timeframe: str) -> tuple[str, dict | None, str | None]:
        """Run backtest for a single timeframe. Returns (timeframe, result, error)."""
        try:
            # Use different universe slices per timeframe for varied results
            if timeframe == "short":
                backtest_universe = universe[:40]  # Momentum-focused: broader, more volatile
            elif timeframe == "long":
                backtest_universe = universe[20:60]  # Value-focused: different slice
            else:  # medium
                backtest_universe = universe[10:50]  # Balanced: overlapping middle

            result = run_backtest(
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                config=config,
                universe=backtest_universe,
                verbose=False,
            )
            return timeframe, backtest_result_to_frontend(result), f"{result.alpha:+.1f}% alpha, {result.hit_rate:.0f}% hit rate"
        except Exception as e:
            return timeframe, None, str(e)

    # Run all 3 backtests in parallel
    timeframes = ["short", "medium", "long"]
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_run_single_backtest, tf): tf for tf in timeframes}

        for future in as_completed(futures):
            timeframe, result, info = future.result()
            results[timeframe] = result
            if result:
                print(f"    {timeframe}: {info}")
            else:
                print(f"    {timeframe} backtest failed: {info}")

    # Return None if all failed
    if all(r is None for r in results.values()):
        return None

    return {
        "short": results.get("short"),
        "medium": results.get("medium"),
        "long": results.get("long"),
        "lastUpdated": now,
    }


def pick_to_frontend(pick, metrics=None) -> dict:
    """Convert StockPick to frontend StockPick format."""
    # Handle StockMetrics object or dict
    if metrics is not None:
        current_price = getattr(metrics, "price", None) or pick.entry_price or 100.0
        prev_close = getattr(metrics, "previous_close", current_price)
        name = getattr(metrics, "name", pick.ticker)
        sector = getattr(metrics, "sector", None)
        market_cap = getattr(metrics, "market_cap", None)
        pe_trailing = getattr(metrics, "pe_trailing", None)
        volume = getattr(metrics, "volume", None)
    else:
        current_price = pick.entry_price or 100.0
        prev_close = current_price
        name = pick.ticker
        sector = None
        market_cap = None
        pe_trailing = None
        volume = None

    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "ticker": pick.ticker,
        "companyName": name,
        "currentPrice": round(current_price, 2),
        "priceChange": round(change, 2),
        "priceChangePercent": round(change_pct, 2),
        "convictionScore": round(pick.conviction_score, 3),
        "timeframe": pick.timeframe.value if hasattr(pick.timeframe, 'value') else str(pick.timeframe),
        "thesis": pick.thesis,
        "riskFactors": pick.risk_factors[:5] if pick.risk_factors else [],
        "sector": map_sector(sector),
        "entryPrice": round(pick.entry_price, 2) if pick.entry_price else None,
        "targetPrice": round(pick.target_price, 2) if pick.target_price else None,
        "marketCap": market_cap,
        "peRatio": pe_trailing,
        "volume": volume,
    }


def indicator_to_frontend(ind) -> dict:
    """Convert MacroIndicator to frontend format."""
    return {
        "id": ind.series_id or ind.name.lower().replace(" ", "_"),
        "name": ind.name,
        "value": round(ind.current_value, 2) if ind.current_value else 0,
        "previousValue": round(ind.previous_value, 2) if ind.previous_value else None,
        "unit": ind.unit or "",
        "trend": map_trend(ind.trend),
        "source": "FRED",
        "updatedAt": datetime.now().isoformat(),
        "description": f"{ind.name} indicator",
    }


def risk_to_frontend(risk) -> dict:
    """Convert Risk to frontend MacroRisk format."""
    severity = "low"
    if risk.severity >= 0.7:
        severity = "high"
    elif risk.severity >= 0.4:
        severity = "medium"

    return {
        "id": risk.name.lower().replace(" ", "_"),
        "name": risk.name,
        "severity": severity,
        "description": risk.description,
        "affectedSectors": ["technology", "finance"],  # Default affected sectors
        "likelihood": round(risk.probability, 2),
        "potentialImpact": f"Risk score: {risk.risk_score:.0%}",
    }


def news_to_frontend(item, idx: int, fallback_category: str) -> dict:
    """Convert ScoredNewsItem to frontend NewsItem format."""
    # Use item's actual category if available, otherwise fallback
    category_map = {
        "market_wide": "Market",
        "sector": "Sector",
        "company": "Company",
        "social": "Social",
        "unknown": fallback_category.title(),
    }
    actual_category = getattr(item.category, 'value', fallback_category) if hasattr(item, 'category') else fallback_category
    display_category = category_map.get(actual_category, fallback_category.title())

    return {
        "id": f"{fallback_category[0]}{idx}",
        "headline": item.title,
        "source": item.source,
        "url": item.url or "",
        "publishedAt": item.published.isoformat() if item.published else datetime.now().isoformat(),
        "category": display_category,
        "relevanceScore": round(item.relevance_score, 2),
        "tickersMentioned": item.tickers_mentioned[:5] if item.tickers_mentioned else [],
        "excerpt": item.title[:200] if item.title else "",
    }


def store_pipeline_data_in_db(result, stock_details: dict):
    """Store all pipeline data in SQLite database."""
    import hashlib
    import json

    db = get_db()
    run = db.start_scrape_run("pipeline")

    added = 0
    total = 0

    # Clear old picks (regenerate each run)
    db.clear_stock_picks()

    # Store stock picks
    for timeframe, picks in [
        ("short", result.short_term_picks),
        ("medium", result.medium_term_picks),
        ("long", result.long_term_picks),
    ]:
        for pick in picks:
            total += 1
            pick_id = hashlib.md5(f"{pick.ticker}:{timeframe}".encode()).hexdigest()[:12]
            db_pick = DBStockPick(
                id=pick_id,
                ticker=pick.ticker,
                timeframe=timeframe,
                conviction_score=pick.conviction_score,
                thesis=pick.thesis,
                entry_price=pick.entry_price,
                target_price=pick.target_price,
                stop_loss=pick.stop_loss,
                risk_factors=json.dumps(pick.risk_factors[:5] if pick.risk_factors else []),
            )
            if db.upsert_stock_pick(db_pick):
                added += 1

    # Store stock metrics and price history
    for ticker, details in stock_details.items():
        total += 1
        db_metrics = DBStockMetrics(
            ticker=ticker,
            name=details.get("company_name") or ticker,
            sector=details.get("sector"),
            industry=None,
            price=details.get("price"),
            previous_close=details.get("previous_close"),
            change=details.get("change"),
            change_percent=details.get("change_percent"),
            volume=details.get("volume"),
            market_cap=details.get("market_cap"),
            pe_trailing=details.get("pe_trailing"),
            pe_forward=details.get("pe_forward"),
            peg_ratio=details.get("peg_ratio"),
            price_to_book=details.get("price_to_book"),
            revenue_growth=details.get("revenue_growth"),
            profit_margin=details.get("profit_margin"),
            dividend_yield=details.get("dividend_yield"),
            beta=details.get("beta"),
            fifty_two_week_high=details.get("fifty_two_week_high"),
            fifty_two_week_low=details.get("fifty_two_week_low"),
            avg_volume=details.get("avg_volume"),
        )
        if db.upsert_stock_metrics(db_metrics):
            added += 1

        # Store price history
        for point in details.get("price_history", []):
            point_id = hashlib.md5(f"{ticker}:{point['time']}".encode()).hexdigest()[:12]
            try:
                point_date = datetime.strptime(point["time"], "%Y-%m-%d").date()
                db_point = DBPricePoint(
                    id=point_id,
                    ticker=ticker,
                    date=point_date,
                    open=point["open"],
                    high=point["high"],
                    low=point["low"],
                    close=point["close"],
                    volume=point["volume"],
                )
                db.upsert_price_point(db_point)
            except Exception as e:
                print(f"  Warning: Failed to store price point for {ticker} at {point.get('time', 'unknown date')}: {e}")
                pass

    # Store macro indicators
    for ind in result.macro_indicators:
        total += 1
        ind_id = ind.series_id or ind.name.lower().replace(" ", "_")
        trend_str = {Trend.RISING: "up", Trend.FALLING: "down", Trend.STABLE: "flat"}.get(ind.trend, "flat")
        db_ind = DBMacroIndicator(
            id=ind_id,
            series_id=ind.series_id or ind_id,
            name=ind.name,
            value=ind.current_value or 0,
            previous_value=ind.previous_value,
            unit=ind.unit or "",
            trend=trend_str,
            source="FRED",
        )
        if db.upsert_macro_indicator(db_ind):
            added += 1

    # Store macro risks
    db.clear_macro_risks()
    for risk in result.macro_risks:
        total += 1
        risk_id = risk.name.lower().replace(" ", "_")
        severity = "low"
        if risk.severity >= 0.7:
            severity = "high"
        elif risk.severity >= 0.4:
            severity = "medium"

        db_risk = DBMacroRisk(
            id=risk_id,
            name=risk.name,
            severity=severity,
            description=risk.description,
            likelihood=risk.probability,
            affected_sectors=json.dumps(["technology", "finance"]),
        )
        if db.upsert_macro_risk(db_risk):
            added += 1

    # Store news items
    for category, news_list in [("market", result.market_news), ("company", result.company_news)]:
        for i, item in enumerate(news_list[:50]):
            total += 1
            news_id = hashlib.md5(f"{item.url or item.title}".encode()).hexdigest()[:12]
            db_news = DBNewsItem(
                id=news_id,
                headline=item.title,
                source=item.source or "Unknown",
                url=item.url or "",
                category=category,
                published_at=item.published,
                relevance_score=item.relevance_score,
                tickers_mentioned=json.dumps(item.tickers_mentioned[:5] if item.tickers_mentioned else []),
                excerpt=item.title[:200] if item.title else "",
            )
            if db.upsert_news_item(db_news):
                added += 1

    db.complete_scrape_run(run, records_added=added, records_skipped=total - added)
    print(f"Stored {added} new records in database (skipped {total - added} existing)")


def smart_money_to_frontend(signal: dict) -> dict:
    """Convert SmartMoneySignal dict to frontend format."""
    details = signal.get("details", {})

    return {
        "id": signal.get("id", ""),
        "type": signal.get("signal_type", "congress"),
        "ticker": signal.get("ticker", ""),
        "direction": signal.get("direction", "buy"),
        "strength": round(signal.get("strength", 0.5), 2),
        "summary": signal.get("summary", ""),
        "timestamp": details.get("disclosure_date") or details.get("expiry") or datetime.now().isoformat(),
        "source": signal.get("source", ""),
        "details": details,
    }


def hedge_fund_holding_to_frontend(holding: HedgeFundHolding, fund_name: str, manager: str) -> dict:
    """Convert HedgeFundHolding to frontend SmartMoneySignal format."""
    # Determine direction based on action
    direction = "buy"
    if holding.action in ("sold", "decreased"):
        direction = "sell"

    # Calculate strength based on action and magnitude
    strength = 0.5
    if holding.action == "new":
        strength = 0.85
    elif holding.action == "increased" and holding.shares_change_pct:
        strength = min(0.9, 0.6 + abs(holding.shares_change_pct) / 200)
    elif holding.action == "decreased" and holding.shares_change_pct:
        strength = min(0.8, 0.5 + abs(holding.shares_change_pct) / 200)
    elif holding.action == "sold":
        strength = 0.75

    # Build summary
    ticker = holding.ticker or holding.issuer_name[:12]
    value_str = f"${holding.value / 1e6:.1f}M" if holding.value >= 1e6 else f"${holding.value / 1e3:.0f}K"

    if holding.action == "new":
        summary = f"{fund_name} opened new position in {ticker} ({value_str})"
    elif holding.action == "increased":
        pct = f"+{holding.shares_change_pct:.1f}%" if holding.shares_change_pct else ""
        summary = f"{fund_name} increased {ticker} {pct} ({value_str})"
    elif holding.action == "decreased":
        pct = f"{holding.shares_change_pct:.1f}%" if holding.shares_change_pct else ""
        summary = f"{fund_name} reduced {ticker} {pct} ({value_str})"
    elif holding.action == "sold":
        summary = f"{fund_name} sold entire position in {ticker}"
    else:
        summary = f"{fund_name} holds {ticker} ({value_str})"

    # Get quarter string
    report_date = holding.report_date
    if isinstance(report_date, str):
        try:
            report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except Exception:
            report_date = None

    if report_date:
        quarter = f"Q{(report_date.month - 1) // 3 + 1} {report_date.year}"
    else:
        quarter = "N/A"

    return {
        "id": f"13f_{holding.id}",
        "type": "13f",
        "ticker": holding.ticker or "",
        "direction": direction,
        "strength": round(strength, 2),
        "summary": summary,
        "timestamp": holding.filing_date.isoformat() if hasattr(holding.filing_date, 'isoformat') else str(holding.filing_date),
        "source": "sec_13f",
        "details": {
            "fund_name": fund_name,
            "manager": manager,
            "shares": holding.shares,
            "value": holding.value,
            "action": holding.action,
            "shares_change": holding.shares_change,
            "shares_change_pct": holding.shares_change_pct,
            "value_change": (holding.value - holding.prev_value) if holding.prev_value else None,
            "portfolio_pct": holding.portfolio_pct,
            "filing_date": holding.filing_date.isoformat() if hasattr(holding.filing_date, 'isoformat') else str(holding.filing_date),
            "quarter": quarter,
        },
    }


def fetch_sp500_batch_prices() -> dict[str, dict]:
    """
    Fetch comprehensive data for combined universe (S&P 500 + Dow + NASDAQ-100).

    Fetches:
    - Current prices (~10 seconds for ~516 tickers)
    - Market caps (~10 seconds)
    - 90-day price history for charts (~15-20 seconds)
    - Full fundamentals (P/E, dividend yield, beta, 52W high/low, etc.) (~60-90 seconds)

    Returns stock data with price history and fundamentals suitable for charts,
    heatmap, Key Metrics display, and overview displays.
    Includes index membership badges for each stock.
    """
    from adapters.yahoo import YahooAdapter
    from adapters.universe import get_universe_provider
    import time

    print("Fetching combined universe batch prices...")
    start = time.time()

    # Get combined universe (S&P 500 + Dow + NASDAQ-100, deduplicated)
    universe = get_universe_provider()
    universe_info = universe.get_universe()
    tickers = list(universe_info.keys())

    print(f"  Found {len(tickers)} tickers (S&P 500 + Dow + NASDAQ-100)")

    # Batch fetch prices
    yahoo = YahooAdapter()
    prices = yahoo.get_prices_batch(tickers)
    price_time = time.time() - start

    # Batch fetch market caps (threaded, ~10s for 500 tickers)
    print(f"  Fetched {len(prices)} prices in {price_time:.1f}s, fetching market caps...")
    cap_start = time.time()
    market_caps = yahoo.get_market_caps_batch(tickers)
    cap_time = time.time() - cap_start

    # Batch fetch 90-day price history for charts (efficient batch operation)
    print(f"  Fetched {len(market_caps)} market caps in {cap_time:.1f}s, fetching price history...")
    history_start = time.time()
    price_histories = yahoo.get_price_history_batch(tickers, days=90)
    history_time = time.time() - history_start
    print(f"  Fetched price history for {len(price_histories)}/{len(tickers)} stocks in {history_time:.1f}s")

    # Batch fetch fundamentals for ALL stocks (P/E, dividend yield, beta, 52W high/low, etc.)
    print(f"  Fetching fundamentals for {len(tickers)} stocks (this may take 60-90 seconds)...")
    fund_start = time.time()
    fundamentals = yahoo.get_fundamentals_batch(tickers)
    fund_time = time.time() - fund_start
    fund_found = sum(1 for v in fundamentals.values() if v and v.get("pe_trailing") is not None)
    print(f"  Fetched fundamentals for {fund_found}/{len(tickers)} stocks in {fund_time:.1f}s")

    # Merge with sector info, index membership, price history, and fundamentals
    result = {}
    for ticker, price_data in prices.items():
        info = universe_info.get(ticker)
        fund = fundamentals.get(ticker, {})

        result[ticker] = {
            "ticker": ticker,
            "companyName": info.name if info else ticker,
            "sector": map_sector(info.sector) if info else "other",
            "currentPrice": price_data["price"],
            "priceChange": price_data["change"],
            "priceChangePercent": price_data["change_percent"],
            "volume": price_data.get("volume"),
            "marketCap": market_caps.get(ticker) or fund.get("market_cap"),
            # Index membership badges (e.g., ["S&P 500", "Dow 30", "NASDAQ-100"])
            "indices": info.index_badges if info else [],
            # 90-day price history for charts
            "priceHistory": price_histories.get(ticker, []),
            # Full fundamentals for Key Metrics display
            "fundamentals": {
                "peTrailing": fund.get("pe_trailing"),
                "peForward": fund.get("pe_forward"),
                "pegRatio": fund.get("peg_ratio"),
                "priceToBook": fund.get("price_to_book"),
                "revenueGrowth": fund.get("revenue_growth"),
                "profitMargin": fund.get("profit_margin"),
                "dividendYield": fund.get("dividend_yield"),
                "beta": fund.get("beta"),
                "fiftyTwoWeekHigh": fund.get("fifty_two_week_high"),
                "fiftyTwoWeekLow": fund.get("fifty_two_week_low"),
                "avgVolume": fund.get("average_volume"),
            } if fund else None,
        }

    elapsed = time.time() - start
    caps_found = sum(1 for v in market_caps.values() if v is not None)
    history_found = sum(1 for v in price_histories.values() if v)
    print(f"  Fetched {len(result)} stocks ({caps_found} with market cap, {history_found} with price history, {fund_found} with fundamentals) in {elapsed:.1f}s")

    return result


def fetch_stock_details(tickers: list[str]) -> dict:
    """Fetch detailed stock data using batch methods for speed."""
    from adapters.yahoo import YahooAdapter

    yahoo = YahooAdapter()
    details = {}

    print(f"Fetching detailed data for {len(tickers)} stocks...")

    # Batch fetch all data in parallel
    print("  Fetching price history (batch)...")
    price_history_batch = yahoo.get_price_history_batch(tickers, days=365)
    print(f"  Got price history for {len(price_history_batch)}/{len(tickers)} stocks")

    # Batch fetch fundamentals and prices (parallel, much faster than serial)
    fund_batch = yahoo.get_fundamentals_batch(tickers)
    price_batch = yahoo.get_prices_batch(tickers)

    # Combine all data
    for ticker in tickers:
        try:
            fund_data = fund_batch.get(ticker, {})
            price_data = price_batch.get(ticker, {})
            price_history = price_history_batch.get(ticker, [])

            details[ticker] = {
                "price": price_data.get("price") or fund_data.get("current_price"),
                "previous_close": price_data.get("previous_close"),
                "change": price_data.get("change", 0),
                "change_percent": price_data.get("change_percent", 0),
                "volume": price_data.get("volume"),
                "market_cap": fund_data.get("market_cap"),
                "pe_trailing": fund_data.get("pe_trailing"),
                "pe_forward": fund_data.get("pe_forward"),
                "peg_ratio": fund_data.get("peg_ratio"),
                "price_to_book": fund_data.get("price_to_book"),
                "fifty_two_week_high": fund_data.get("fifty_two_week_high"),
                "fifty_two_week_low": fund_data.get("fifty_two_week_low"),
                "revenue_growth": fund_data.get("revenue_growth"),
                "profit_margin": fund_data.get("profit_margin"),
                "dividend_yield": fund_data.get("dividend_yield"),
                "beta": fund_data.get("beta"),
                "avg_volume": fund_data.get("average_volume"),
                "sector": fund_data.get("sector"),
                "company_name": fund_data.get("company_name") or ticker,
                "price_history": price_history,
            }

        except Exception as e:
            print(f"  Warning: Could not fetch details for {ticker}: {e}")
            details[ticker] = {"price_history": price_history_batch.get(ticker, [])}

    print(f"  Fetched {len(details)}/{len(tickers)} stocks")
    return details


def fetch_premarket_movers(tickers: list[str]) -> tuple[list[dict], list[dict]]:
    """Fetch pre-market movers from a list of tickers."""
    from adapters.yahoo import YahooAdapter

    try:
        yahoo = YahooAdapter()
        gainers, losers = yahoo.get_premarket_movers(
            tickers,
            min_change_pct=0.5,  # Lower threshold to capture more movers
            top_n=10,
        )
        return gainers, losers
    except Exception as e:
        print(f"  Warning: Pre-market fetch failed: {e}")
        return [], []


def fetch_briefing_data(sp500_tickers: list[str] | None = None) -> dict | None:
    """Fetch economic calendar, news, earnings, and pre-market movers to generate daily briefing."""
    from datetime import date, timedelta

    calendar_obs = []
    news_obs = []
    premarket_gainers = []
    premarket_losers = []
    earnings_data = {
        "today": [],
        "before_open": [],
        "after_close": [],
    }

    calendar = CalendarAdapter()

    # Try hybrid calendar (FRED releases + Finnhub earnings, all FREE tier)
    print("  Fetching hybrid calendar (FRED + earnings)...")
    try:
        today = date.today()
        hybrid = calendar.get_hybrid_calendar(
            from_date=today,
            to_date=today + timedelta(days=7),
            include_earnings=True,
            include_ipos=False,
            include_economic=True,
        )

        # Convert economic events to observations
        for event_data in hybrid.get("economic_events", []):
            from domain import Observation, Category
            obs = Observation(
                source="hybrid_calendar",
                timestamp=datetime.fromisoformat(event_data["time"]),
                category=Category.MACRO,
                data=event_data,
                ticker=None,
                reliability=0.9,
            )
            calendar_obs.append(obs)

        print(f"  Got {len(calendar_obs)} economic events from: {hybrid.get('sources_used', [])}")

        # Process earnings data
        earnings_list = hybrid.get("earnings", [])
        if earnings_list:
            today_str = today.isoformat()
            for e in earnings_list:
                # Convert to frontend format
                earnings_item = {
                    "symbol": e["symbol"],
                    "date": e["date"],
                    "hour": e["hour"],
                    "timingDisplay": {"bmo": "Before Open", "amc": "After Close", "": "TBD"}.get(e["hour"], "TBD"),
                    "year": e["year"],
                    "quarter": e["quarter"],
                    "epsEstimate": e["eps_estimate"],
                    "epsActual": e["eps_actual"],
                    "revenueEstimate": e["revenue_estimate"],
                    "revenueActual": e["revenue_actual"],
                    "isReported": e["eps_actual"] is not None,
                }

                # Categorize by timing for today
                if e["date"] == today_str:
                    earnings_data["today"].append(earnings_item)
                    if e["hour"] == "bmo":
                        earnings_data["before_open"].append(earnings_item)
                    elif e["hour"] == "amc":
                        earnings_data["after_close"].append(earnings_item)

            print(f"  Got {len(earnings_list)} earnings events ({len(earnings_data['today'])} today)")

    except Exception as e:
        print(f"  Warning: Hybrid calendar fetch failed: {e}")
        # Fallback to legacy method
        try:
            calendar_obs = calendar.get_week_events()
            print(f"  Got {len(calendar_obs)} calendar events (legacy)")
        except Exception as e2:
            if "403" in str(e2) or "Forbidden" in str(e2):
                print("  Note: Economic calendar requires paid Finnhub subscription (skipping)")
            else:
                print(f"  Warning: Calendar fetch failed: {e2}")

    # Fetch news from RSS (always available)
    try:
        rss = RssAdapter()
        news_obs = rss.get_all(limit=30)
        print(f"  Got {len(news_obs)} news items")
    except Exception as e:
        print(f"  Warning: News fetch failed: {e}")

    # Fetch pre-market movers if we have tickers
    if sp500_tickers:
        print("  Fetching pre-market movers...")
        premarket_gainers, premarket_losers = fetch_premarket_movers(sp500_tickers)
        print(f"  Got {len(premarket_gainers)} gainers, {len(premarket_losers)} losers")

    # Fetch historical event reactions
    historical_reactions = {}
    try:
        print("  Fetching historical event reactions...")
        historical_reactions = calendar.get_historical_event_reactions(lookback_months=6)
        print(f"  Got {len(historical_reactions)} historical reactions")
    except Exception as e:
        print(f"  Warning: Historical reactions fetch failed: {e}")

    # Generate briefing (works with just news if calendar unavailable)
    if not calendar_obs and not news_obs and not earnings_data["today"]:
        print("  Warning: No briefing data available")
        return None

    try:
        briefing = generate_daily_briefing(
            calendar_observations=calendar_obs,
            news_observations=news_obs,
            max_news=10,
        )
        briefing_dict = briefing_to_dict(briefing)

        # Convert pre-market movers to camelCase for frontend
        def to_camel_case(mover: dict) -> dict:
            return {
                "ticker": mover.get("ticker", ""),
                "companyName": mover.get("company_name", mover.get("ticker", "")),
                "price": mover.get("price", 0),
                "change": mover.get("change", 0),
                "changePercent": mover.get("change_percent", 0),
                "volume": mover.get("volume", 0),
                "previousClose": mover.get("previous_close", 0),
                "isGainer": mover.get("is_gainer", True),
            }

        # Add pre-market movers to briefing
        briefing_dict["premarketGainers"] = [to_camel_case(m) for m in premarket_gainers]
        briefing_dict["premarketLosers"] = [to_camel_case(m) for m in premarket_losers]

        # Add earnings data to briefing
        briefing_dict["earningsToday"] = earnings_data["today"]
        briefing_dict["earningsBeforeOpen"] = earnings_data["before_open"]
        briefing_dict["earningsAfterClose"] = earnings_data["after_close"]
        briefing_dict["hasEarningsToday"] = len(earnings_data["today"]) > 0

        # Add historical context (convert to camelCase for frontend)
        def reaction_to_camel_case(reaction: dict) -> dict:
            return {
                "eventType": reaction.get("event_type", ""),
                "eventName": reaction.get("event_name", ""),
                "eventDate": reaction.get("event_date", ""),
                "actual": reaction.get("actual"),
                "forecast": reaction.get("forecast"),
                "surpriseDirection": reaction.get("surprise_direction", "in_line"),
                "spyReaction1d": reaction.get("spy_reaction_1d", 0.0),
                "spyReaction5d": reaction.get("spy_reaction_5d"),
                "summary": f"Last {reaction.get('event_type', '')} {reaction.get('surprise_direction', 'in_line')} → SPY {'+' if reaction.get('spy_reaction_1d', 0) >= 0 else ''}{reaction.get('spy_reaction_1d', 0):.1f}%",
            }

        briefing_dict["historicalContext"] = {
            event_type: reaction_to_camel_case(reaction)
            for event_type, reaction in historical_reactions.items()
        }

        return briefing_dict
    except Exception as e:
        print(f"  Warning: Could not generate briefing: {e}")
        return None


def generate_report_json(result, config: PipelineConfig, stock_details: dict, sp500_prices: dict | None = None, briefing_data: dict | None = None, backtest_data: dict | None = None) -> dict:
    """Convert pipeline ReportData to frontend FinancialReport format."""
    now = datetime.now().isoformat()

    # Get metrics lookup
    metrics = result.stock_metrics or {}

    def enhance_pick(pick, details: dict) -> dict:
        """Enhance pick with detailed stock data."""
        d = details.get(pick.ticker, {})
        m = metrics.get(pick.ticker)

        # Get price data
        current_price = d.get("price") or (getattr(m, "price", None) if m else None) or pick.entry_price or 100.0
        prev_close = d.get("previous_close") or current_price
        change = d.get("change") or (current_price - prev_close)
        change_pct = d.get("change_percent") or ((change / prev_close * 100) if prev_close else 0)

        # Get sector
        sector = d.get("sector") or (getattr(m, "sector", None) if m else None)

        # Get company name from details, metrics, or fall back to ticker
        company_name = d.get("company_name") or (getattr(m, "name", None) if m else None) or pick.ticker

        return {
            "ticker": pick.ticker,
            "companyName": company_name,
            "currentPrice": round(current_price, 2),
            "priceChange": round(change, 2),
            "priceChangePercent": round(change_pct, 2),
            "convictionScore": round(pick.conviction_score, 3),
            "timeframe": pick.timeframe.value if hasattr(pick.timeframe, 'value') else str(pick.timeframe),
            "thesis": pick.thesis,
            "riskFactors": pick.risk_factors[:5] if pick.risk_factors else [],
            "sector": map_sector(sector),
            "entryPrice": round(pick.entry_price, 2) if pick.entry_price else None,
            "targetPrice": round(pick.target_price, 2) if pick.target_price else None,
            "stopLoss": round(pick.stop_loss, 2) if pick.stop_loss else None,
            "marketCap": d.get("market_cap"),
            "peRatio": d.get("pe_trailing"),
            "volume": d.get("volume"),
        }

    # Convert picks with enhanced data
    short_picks = [enhance_pick(p, stock_details) for p in result.short_term_picks]
    medium_picks = [enhance_pick(p, stock_details) for p in result.medium_term_picks]
    long_picks = [enhance_pick(p, stock_details) for p in result.long_term_picks]

    # Convert indicators
    macro_indicators = [indicator_to_frontend(i) for i in result.macro_indicators]

    # Convert risks
    risks = [risk_to_frontend(r) for r in result.macro_risks]

    # Convert news
    market_news = [news_to_frontend(n, i, "market") for i, n in enumerate(result.market_news[:50])]
    company_news = [news_to_frontend(n, i, "company") for i, n in enumerate(result.company_news[:50])]

    # Convert smart money signals
    smart_money_signals = [smart_money_to_frontend(s) for s in result.smart_money_signals[:50]]
    congress_signals = [s for s in smart_money_signals if s["type"] == "congress"]
    options_signals = [s for s in smart_money_signals if s["type"] == "options"]

    # Fetch 13F hedge fund holdings from database
    db = get_db()
    hedge_fund_holdings = db.get_recent_hedge_fund_activity(limit=100)
    funds_cache = {}  # Cache fund info lookups

    hedge_fund_signals = []
    for holding in hedge_fund_holdings:
        if holding.fund_id not in funds_cache:
            fund = db.get_hedge_fund(holding.fund_id)
            funds_cache[holding.fund_id] = (fund.name, fund.manager) if fund else ("Unknown Fund", "Unknown")
        fund_name, manager = funds_cache[holding.fund_id]
        hedge_fund_signals.append(hedge_fund_holding_to_frontend(holding, fund_name, manager))

    # Add 13F signals to all smart money signals
    smart_money_signals = smart_money_signals + hedge_fund_signals
    # Sort by strength
    smart_money_signals.sort(key=lambda x: x["strength"], reverse=True)

    # Build stock details with price history and fundamentals
    stock_details_export = {}
    all_picks = short_picks + medium_picks + long_picks
    for pick in all_picks:
        ticker = pick["ticker"]
        if ticker not in stock_details_export:
            d = stock_details.get(ticker, {})

            # Find related news
            related = [n for n in company_news if ticker in n.get("tickersMentioned", [])]

            price_history = d.get("price_history", [])
            indicators = compute_indicators_for_history(price_history)

            stock_details_export[ticker] = {
                **pick,
                "priceHistory": price_history,
                "relatedNews": related[:5],
                "fundamentals": {
                    "peTrailing": d.get("pe_trailing"),
                    "peForward": d.get("pe_forward"),
                    "pegRatio": d.get("peg_ratio"),
                    "priceToBook": d.get("price_to_book"),
                    "revenueGrowth": d.get("revenue_growth"),
                    "profitMargin": d.get("profit_margin"),
                    "dividendYield": d.get("dividend_yield"),
                    "beta": d.get("beta"),
                    "fiftyTwoWeekHigh": d.get("fifty_two_week_high"),
                    "fiftyTwoWeekLow": d.get("fifty_two_week_low"),
                    "avgVolume": d.get("avg_volume"),
                },
                "indicators": indicators,
            }

    # Calculate summary
    all_picks_list = short_picks + medium_picks + long_picks
    avg_conviction = sum(p["convictionScore"] for p in all_picks_list) / len(all_picks_list) if all_picks_list else 0

    # Count sectors
    sector_counts = {}
    for p in all_picks_list:
        s = p["sector"]
        sector_counts[s] = sector_counts.get(s, 0) + 1
    top_sector = max(sector_counts.items(), key=lambda x: x[1])[0] if sector_counts else "technology"

    # Determine market trend from indicators
    market_trend = "flat"
    for ind in macro_indicators:
        if "vix" in ind["id"].lower():
            if ind["value"] < 20:
                market_trend = "up"
            elif ind["value"] > 30:
                market_trend = "down"
            break

    return {
        "generatedAt": now,
        "version": "1.0.0",
        "watchlist": list(metrics.keys())[:20],
        "picks": {
            "short": short_picks,
            "medium": medium_picks,
            "long": long_picks,
        },
        "stockDetails": stock_details_export,
        # All S&P 500 stocks with just prices (for heatmap)
        "allStocks": list(sp500_prices.values()) if sp500_prices else [],
        "macro": {
            "indicators": macro_indicators,
            "risks": risks,
            "marketSentiment": market_trend,
            "lastUpdated": now,
        },
        "news": {
            "market": market_news,
            "company": company_news,
        },
        "smartMoney": {
            "signals": smart_money_signals,
            "congress": congress_signals,
            "options": options_signals,
            "hedgeFunds": hedge_fund_signals,
            "lastUpdated": now,
        },
        "briefing": briefing_data,
        "backtest": backtest_data,
        "summary": {
            "totalPicks": len(all_picks_list),
            "totalStocks": len(sp500_prices) if sp500_prices else 0,
            "avgConviction": round(avg_conviction, 3),
            "topSector": top_sector,
            "highRiskCount": len([r for r in risks if r["severity"] == "high"]),
            "newsCount": len(market_news) + len(company_news),
            "marketTrend": market_trend,
            "smartMoneySignals": len(smart_money_signals),
            "congressTrades": len(congress_signals),
            "unusualOptions": len(options_signals),
            "hedgeFundSignals": len(hedge_fund_signals),
        },
    }


def main():
    print("Running fintel pipeline...")

    # Get database reference
    db = get_db()

    # Configure pipeline
    config = PipelineConfig(
        universe_source="sp500",
        universe_max_tickers=50,
        max_picks_per_timeframe=15,
        max_news_items=100,
    )

    # Run pipeline
    pipeline = Pipeline(config)
    result = pipeline.run()

    print(f"Analyzed {len(result.stock_metrics)} stocks")
    print(f"Generated {len(result.short_term_picks)} short / {len(result.medium_term_picks)} medium / {len(result.long_term_picks)} long picks")
    print(f"Collected {len(result.macro_indicators)} macro indicators")
    print(f"Found {len(result.market_news) + len(result.company_news)} news items")
    print(f"Found {len(result.smart_money_signals)} smart money signals")

    # Count 13F holdings
    hedge_fund_holdings_count = len(db.get_recent_hedge_fund_activity(limit=100))
    print(f"Found {hedge_fund_holdings_count} 13F hedge fund holdings")

    # Fetch S&P 500 batch prices (fast - ~6 seconds for 500 tickers)
    sp500_prices = fetch_sp500_batch_prices()

    # Get unique tickers from all picks
    all_tickers = set()
    for pick in result.short_term_picks + result.medium_term_picks + result.long_term_picks:
        all_tickers.add(pick.ticker)

    # Fetch detailed stock data (price history, fundamentals) - only for picks
    stock_details = fetch_stock_details(list(all_tickers))

    # Store all data in SQLite database
    print("\nStoring data in SQLite database...")
    store_pipeline_data_in_db(result, stock_details)

    # Fetch daily briefing data (economic calendar + news + pre-market movers)
    print("\nGenerating daily briefing...")
    sp500_tickers = list(sp500_prices.keys()) if sp500_prices else []
    briefing_data = fetch_briefing_data(sp500_tickers)
    if briefing_data:
        events_today = len(briefing_data.get("eventsToday", []))
        events_upcoming = len(briefing_data.get("eventsUpcoming", []))
        print(f"  {events_today} events today, {events_upcoming} upcoming high-impact")
    else:
        print("  Briefing unavailable (check Finnhub API key)")

    # Generate backtest data (historical performance validation)
    print("\nGenerating backtest data...")
    backtest_data = generate_backtest_data(sp500_tickers)
    if backtest_data:
        for tf in ["short", "medium", "long"]:
            if backtest_data.get(tf):
                perf = backtest_data[tf]["performance"]
                print(f"  {tf.upper()}: {perf['alpha']:+.1f}% alpha, {perf['hitRate']:.0f}% hit rate")
    else:
        print("  Backtest data unavailable")

    # Convert to frontend format
    report = generate_report_json(result, config, stock_details, sp500_prices, briefing_data, backtest_data)

    # Write split JSON files for lazy loading (heavy data to public/)
    public_data_dir = Path(__file__).parent.parent / "frontend" / "public" / "data"
    public_data_dir.mkdir(parents=True, exist_ok=True)

    # Extract heavy sections for lazy loading
    # Note: stockDetails is removed from core (too large ~430KB)
    # allStocks and smartMoney are kept in core for SSG pages (heatmap, smart money)
    stock_details = report.pop("stockDetails", {})
    all_stocks = report.get("allStocks", [])  # Keep in core for heatmap SSG
    smart_money = report.get("smartMoney", {})  # Keep in core for smart money SSG

    # Write split files (minified for smaller size)
    with open(public_data_dir / "stockDetails.json", "w") as f:
        json.dump(stock_details, f, separators=(',', ':'), default=str)
    with open(public_data_dir / "allStocks.json", "w") as f:
        json.dump(all_stocks, f, separators=(',', ':'), default=str)
    with open(public_data_dir / "smartMoney.json", "w") as f:
        json.dump(smart_money, f, separators=(',', ':'), default=str)

    # Calculate sizes
    core_size = len(json.dumps(report, default=str))
    details_size = len(json.dumps(stock_details, default=str))
    stocks_size = len(json.dumps(all_stocks, default=str))
    smart_size = len(json.dumps(smart_money, default=str))

    print(f"\nSplit JSON sizes:")
    print(f"  Core report: {core_size/1024:.1f} KB")
    print(f"  stockDetails: {details_size/1024:.1f} KB")
    print(f"  allStocks: {stocks_size/1024:.1f} KB")
    print(f"  smartMoney: {smart_size/1024:.1f} KB")

    # Write core report to src/data (for SSG imports)
    output_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote core report to {output_path}")
    print(f"Total S&P 500 stocks: {report['summary']['totalStocks']}")
    print(f"Total picks: {report['summary']['totalPicks']}")
    print(f"Avg conviction: {report['summary']['avgConviction']:.0%}")
    print(f"Top sector: {report['summary']['topSector']}")

    # Show sample stock detail (from the split file)
    sample_ticker = list(stock_details.keys())[0] if stock_details else None
    if sample_ticker:
        detail = stock_details[sample_ticker]
        print(f"\nSample stock ({sample_ticker}):")
        print(f"  Price: ${detail['currentPrice']} ({detail['priceChange']:+.2f}, {detail['priceChangePercent']:+.2f}%)")
        print(f"  Price history points: {len(detail.get('priceHistory', []))}")
        print(f"  52W High: {detail['fundamentals'].get('fiftyTwoWeekHigh')}")
        print(f"  52W Low: {detail['fundamentals'].get('fiftyTwoWeekLow')}")

    # Show database stats
    db = get_db()
    stats = db.get_stats()
    print(f"\nDatabase stats ({stats['db_path']}):")
    print(f"  Stock picks: {stats['stock_picks']}")
    print(f"  Stock metrics: {stats['stock_metrics']}")
    print(f"  Price history: {stats['price_history']}")
    print(f"  Congress trades: {stats['congress_trades']}")
    print(f"  Options activity: {stats['options_activity']}")
    print(f"  Macro indicators: {stats['macro_indicators']}")
    print(f"  Macro risks: {stats['macro_risks']}")
    print(f"  News items: {stats['news_items']}")
    print(f"  Pick performance: {stats['pick_performance']}")
    print(f"  Pipeline runs: {stats['scrape_runs']}")
    print(f"  DB size: {stats['db_size_mb']} MB")

    # Show performance summary if tracking exists
    perf_summary = db.get_performance_summary()
    if perf_summary['total_picks'] > 0:
        print(f"\nPerformance tracking:")
        print(f"  Picks tracked: {perf_summary['total_picks']}")
        print(f"  Win rate: {perf_summary['win_rate']}%")
        print(f"  Active: {perf_summary['active']} | Won: {perf_summary['won']} | Lost: {perf_summary['lost']}")


if __name__ == "__main__":
    main()
