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


def news_to_frontend(item, idx: int, category: str) -> dict:
    """Convert ScoredNewsItem to frontend NewsItem format."""
    return {
        "id": f"{category[0]}{idx}",
        "headline": item.title,
        "source": item.source,
        "url": item.url or "",
        "publishedAt": item.published.isoformat() if item.published else datetime.now().isoformat(),
        "category": category,
        "relevanceScore": round(item.relevance_score, 2),
        "tickersMentioned": item.tickers_mentioned[:5] if item.tickers_mentioned else [],
        "excerpt": item.title[:200] if item.title else "",
    }


def generate_report_json(result, config: PipelineConfig) -> dict:
    """Convert pipeline ReportData to frontend FinancialReport format."""
    now = datetime.now().isoformat()

    # Get metrics lookup
    metrics = result.stock_metrics or {}

    # Convert picks
    short_picks = [pick_to_frontend(p, metrics.get(p.ticker)) for p in result.short_term_picks]
    medium_picks = [pick_to_frontend(p, metrics.get(p.ticker)) for p in result.medium_term_picks]
    long_picks = [pick_to_frontend(p, metrics.get(p.ticker)) for p in result.long_term_picks]

    # Convert indicators
    indicators = [indicator_to_frontend(i) for i in result.macro_indicators]

    # Convert risks
    risks = [risk_to_frontend(r) for r in result.macro_risks]

    # Convert news
    market_news = [news_to_frontend(n, i, "market") for i, n in enumerate(result.market_news[:50])]
    company_news = [news_to_frontend(n, i, "company") for i, n in enumerate(result.company_news[:50])]

    # Build stock details (simplified - no price history for now)
    stock_details = {}
    all_picks = short_picks + medium_picks + long_picks
    for pick in all_picks:
        ticker = pick["ticker"]
        if ticker not in stock_details:
            stock_details[ticker] = {
                **pick,
                "priceHistory": [],  # Would need historical data
                "relatedNews": [],
                "fundamentals": {
                    "peTrailing": pick.get("peRatio"),
                    "avgVolume": pick.get("volume"),
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
        "stockDetails": stock_details,
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
        "summary": {
            "totalPicks": len(all_picks_list),
            "avgConviction": round(avg_conviction, 3),
            "topSector": top_sector,
            "highRiskCount": len([r for r in risks if r["severity"] == "high"]),
            "newsCount": len(market_news) + len(company_news),
            "marketTrend": market_trend,
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

    # Convert to frontend format
    report = generate_report_json(result, config)

    # Write to frontend data directory
    output_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote report to {output_path}")
    print(f"Total picks: {report['summary']['totalPicks']}")
    print(f"Avg conviction: {report['summary']['avgConviction']:.0%}")
    print(f"Top sector: {report['summary']['topSector']}")


if __name__ == "__main__":
    main()
