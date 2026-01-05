#!/usr/bin/env python3
"""
Generate frontend report data from pipeline.

Runs the pipeline and exports data in the format expected by the Astro frontend.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.pipeline import Pipeline, PipelineConfig
from domain import Timeframe, Trend, Impact
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
            except Exception:
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
    Fetch prices for ALL S&P 500 tickers using efficient batch download.

    This is extremely fast (~6 seconds for 500 tickers) and uses only ~2 API calls.
    Returns minimal price data suitable for heatmap and overview displays.
    """
    from adapters.yahoo import YahooAdapter
    from adapters.universe import get_universe_provider
    import time

    print("Fetching S&P 500 batch prices...")
    start = time.time()

    # Get S&P 500 tickers
    universe = get_universe_provider()
    sp500_info = universe.get_universe()
    tickers = list(sp500_info.keys())

    print(f"  Found {len(tickers)} S&P 500 tickers")

    # Batch fetch prices
    yahoo = YahooAdapter()
    prices = yahoo.get_prices_batch(tickers)
    price_time = time.time() - start

    # Batch fetch market caps (threaded, ~10s for 500 tickers)
    print(f"  Fetched {len(prices)} prices in {price_time:.1f}s, fetching market caps...")
    cap_start = time.time()
    market_caps = yahoo.get_market_caps_batch(tickers)
    cap_time = time.time() - cap_start

    # Merge with sector info from universe
    result = {}
    for ticker, price_data in prices.items():
        info = sp500_info.get(ticker)
        result[ticker] = {
            "ticker": ticker,
            "companyName": info.name if info else ticker,
            "sector": map_sector(info.sector) if info else "other",
            "currentPrice": price_data["price"],
            "priceChange": price_data["change"],
            "priceChangePercent": price_data["change_percent"],
            "volume": price_data.get("volume"),
            "marketCap": market_caps.get(ticker),
            # Flag that this is lite data (no fundamentals)
            "isLite": True,
        }

    elapsed = time.time() - start
    caps_found = sum(1 for v in market_caps.values() if v is not None)
    print(f"  Fetched {len(result)} stocks ({caps_found} with market cap) in {elapsed:.1f}s")

    return result


def fetch_stock_details(tickers: list[str]) -> dict:
    """Fetch detailed stock data including price history and fundamentals."""
    from adapters.yahoo import YahooAdapter
    import time

    yahoo = YahooAdapter()
    details = {}

    print(f"Fetching detailed data for {len(tickers)} stocks...")

    for i, ticker in enumerate(tickers):
        try:
            # Rate limit
            time.sleep(0.3)

            # Get fundamentals (includes 52W high/low, PE forward, etc.)
            fund_obs = yahoo.get_fundamentals(ticker)
            fund_data = fund_obs[0].data if fund_obs else {}

            # Get price history for charts
            price_history = yahoo.get_price_history(ticker, days=365)

            # Get current price data
            price_obs = yahoo.get_price(ticker)
            price_data = price_obs[0].data if price_obs else {}

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

            if (i + 1) % 10 == 0:
                print(f"  Fetched {i + 1}/{len(tickers)} stocks...")

        except Exception as e:
            print(f"  Warning: Could not fetch details for {ticker}: {e}")
            details[ticker] = {}

    return details


def generate_report_json(result, config: PipelineConfig, stock_details: dict, sp500_prices: dict | None = None) -> dict:
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
    indicators = [indicator_to_frontend(i) for i in result.macro_indicators]

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

            stock_details_export[ticker] = {
                **pick,
                "priceHistory": d.get("price_history", []),
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
    for ind in indicators:
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
            "indicators": indicators,
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

    # Convert to frontend format
    report = generate_report_json(result, config, stock_details, sp500_prices)

    # Write to frontend data directory
    output_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote report to {output_path}")
    print(f"Total S&P 500 stocks: {report['summary']['totalStocks']}")
    print(f"Total picks: {report['summary']['totalPicks']}")
    print(f"Avg conviction: {report['summary']['avgConviction']:.0%}")
    print(f"Top sector: {report['summary']['topSector']}")

    # Show sample stock detail
    sample_ticker = list(report["stockDetails"].keys())[0] if report["stockDetails"] else None
    if sample_ticker:
        detail = report["stockDetails"][sample_ticker]
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
