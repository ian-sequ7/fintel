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


def generate_report_json(result, config: PipelineConfig, stock_details: dict) -> dict:
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
            "lastUpdated": now,
        },
        "summary": {
            "totalPicks": len(all_picks_list),
            "avgConviction": round(avg_conviction, 3),
            "topSector": top_sector,
            "highRiskCount": len([r for r in risks if r["severity"] == "high"]),
            "newsCount": len(market_news) + len(company_news),
            "marketTrend": market_trend,
            "smartMoneySignals": len(smart_money_signals),
            "congressTrades": len(congress_signals),
            "unusualOptions": len(options_signals),
        },
    }


def main():
    print("Running fintel pipeline...")

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

    # Get unique tickers from all picks
    all_tickers = set()
    for pick in result.short_term_picks + result.medium_term_picks + result.long_term_picks:
        all_tickers.add(pick.ticker)

    # Fetch detailed stock data (price history, fundamentals)
    stock_details = fetch_stock_details(list(all_tickers))

    # Convert to frontend format
    report = generate_report_json(result, config, stock_details)

    # Write to frontend data directory
    output_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote report to {output_path}")
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


if __name__ == "__main__":
    main()
