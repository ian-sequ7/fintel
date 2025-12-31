"""
Frontend-compatible JSON export.

Transforms backend data into the format expected by the Astro frontend.
Merges price data, adds company names, and structures data correctly.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from domain import StockPick, MacroIndicator, Risk, ScoredNewsItem, ConvictionScore
from domain.analysis_types import StockMetrics
from .report import ReportData


# Company name mapping (ticker -> name)
COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "BRK-B": "Berkshire Hathaway Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth Group Inc.",
    "XOM": "Exxon Mobil Corp.",
    "CVX": "Chevron Corp.",
    "PG": "Procter & Gamble Co.",
    "HD": "The Home Depot Inc.",
    "MA": "Mastercard Inc.",
    "COST": "Costco Wholesale Corp.",
    "ABBV": "AbbVie Inc.",
    "KO": "The Coca-Cola Co.",
    "PEP": "PepsiCo Inc.",
    "WMT": "Walmart Inc.",
    "MRK": "Merck & Co. Inc.",
    "LLY": "Eli Lilly and Co.",
    "BAC": "Bank of America Corp.",
    "AVGO": "Broadcom Inc.",
    "TMO": "Thermo Fisher Scientific Inc.",
    "ORCL": "Oracle Corp.",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce Inc.",
    "AMD": "Advanced Micro Devices Inc.",
    "NFLX": "Netflix Inc.",
    "DIS": "The Walt Disney Co.",
    "INTC": "Intel Corp.",
    "CSCO": "Cisco Systems Inc.",
    "VZ": "Verizon Communications Inc.",
    "T": "AT&T Inc.",
    "NKE": "Nike Inc.",
    "MCD": "McDonald's Corp.",
    "IBM": "International Business Machines Corp.",
}

# Sector mapping (ticker -> sector)
SECTOR_MAP: dict[str, str] = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "communications",
    "AMZN": "consumer",
    "NVDA": "technology",
    "META": "communications",
    "TSLA": "consumer",
    "BRK-B": "finance",
    "JPM": "finance",
    "V": "finance",
    "JNJ": "healthcare",
    "UNH": "healthcare",
    "XOM": "energy",
    "CVX": "energy",
    "PG": "consumer",
    "HD": "consumer",
    "MA": "finance",
    "COST": "consumer",
    "ABBV": "healthcare",
    "KO": "consumer",
    "PEP": "consumer",
    "WMT": "consumer",
    "MRK": "healthcare",
    "LLY": "healthcare",
    "BAC": "finance",
    "AVGO": "technology",
    "TMO": "healthcare",
    "ORCL": "technology",
    "ADBE": "technology",
    "CRM": "technology",
    "AMD": "technology",
    "NFLX": "communications",
    "DIS": "communications",
    "INTC": "technology",
    "CSCO": "technology",
    "VZ": "communications",
    "T": "communications",
    "NKE": "consumer",
    "MCD": "consumer",
    "IBM": "technology",
}


def _get_company_name(ticker: str) -> str:
    """Get company name for ticker, with fallback."""
    return COMPANY_NAMES.get(ticker.upper(), f"{ticker.upper()} Inc.")


def _get_sector(ticker: str) -> str:
    """Get sector for ticker, with fallback."""
    return SECTOR_MAP.get(ticker.upper(), "technology")


def _pick_to_frontend(
    pick: StockPick,
    metrics: dict[str, StockMetrics],
) -> dict[str, Any]:
    """Convert StockPick to frontend format, enriched with price data."""
    ticker = pick.ticker.upper()
    stock_metrics = metrics.get(ticker)

    # Get price data from metrics if available
    current_price = stock_metrics.price if stock_metrics else 0.0
    price_change_1d = stock_metrics.price_change_1d if stock_metrics and stock_metrics.price_change_1d is not None else 0.0

    # Calculate price change percent: (change / previous_price) * 100
    # If we have current price and change, previous = current - change
    previous_price = current_price - price_change_1d if current_price else 0.0
    price_change_percent = (price_change_1d / previous_price * 100) if previous_price and previous_price != 0 else 0.0

    market_cap = stock_metrics.market_cap if stock_metrics else None

    return {
        "ticker": ticker,
        "companyName": _get_company_name(ticker),
        "currentPrice": round(current_price, 2),
        "priceChange": round(price_change_1d, 2),
        "priceChangePercent": round(price_change_percent, 2),
        "convictionScore": pick.conviction_score,
        "timeframe": pick.timeframe.value,
        "thesis": pick.thesis,
        "riskFactors": pick.risk_factors,
        "sector": _get_sector(ticker),
        "entryPrice": pick.entry_price,
        "targetPrice": pick.target_price,
        "stopLoss": None,  # Not in backend yet
        "marketCap": market_cap,
    }


def _indicator_to_frontend(ind: MacroIndicator) -> dict[str, Any]:
    """Convert MacroIndicator to frontend format."""
    # Map backend trend to frontend trend
    trend_map = {
        "rising": "up",
        "falling": "down",
        "stable": "flat",
    }

    return {
        "id": ind.series_id or ind.name.lower().replace(" ", "_"),
        "name": ind.name,
        "value": ind.current_value,
        "previousValue": ind.previous_value,
        "unit": ind.unit or "%",
        "trend": trend_map.get(ind.trend.value, "flat"),
        "source": "FRED",
        "updatedAt": ind.as_of_date.isoformat(),
        "description": ind.impact_reason or None,
    }


def _risk_to_frontend(risk: Risk) -> dict[str, Any]:
    """Convert Risk to frontend format."""
    # Map severity score to category
    if risk.severity >= 0.7:
        severity = "high"
    elif risk.severity >= 0.4:
        severity = "medium"
    else:
        severity = "low"

    return {
        "id": risk.name.lower().replace(" ", "_"),
        "name": risk.name,
        "severity": severity,
        "description": risk.description,
        "affectedSectors": [],  # Not in backend risk model
        "likelihood": risk.probability,
        "potentialImpact": None,
    }


def _news_to_frontend(item: ScoredNewsItem, category: str) -> dict[str, Any]:
    """Convert ScoredNewsItem to frontend format."""
    return {
        "id": f"{category}_{hash(item.title) % 10000}",
        "headline": item.title,
        "source": item.source,
        "url": item.url or "",
        "publishedAt": item.published.isoformat(),
        "category": category,
        "relevanceScore": item.relevance_score,
        "tickersMentioned": item.tickers_mentioned,
        "excerpt": None,
    }


def _determine_market_sentiment(
    indicators: list[MacroIndicator],
    risks: list[Risk],
) -> str:
    """Determine overall market sentiment from indicators and risks."""
    if not indicators:
        return "flat"

    # Count positive vs negative trends
    positive = sum(1 for i in indicators if i.trend.value == "rising")
    negative = sum(1 for i in indicators if i.trend.value == "falling")

    # Adjust for high risks
    high_risks = sum(1 for r in risks if r.severity >= 0.7)
    if high_risks >= 2:
        return "down"

    if positive > negative:
        return "up"
    elif negative > positive:
        return "down"
    return "flat"


def export_for_frontend(
    data: ReportData,
    metrics: dict[str, StockMetrics],
    filepath: str | Path,
) -> None:
    """
    Export report data in frontend-compatible format.

    Args:
        data: Report data from pipeline
        metrics: Stock metrics with price data (deprecated - use data.stock_metrics)
        filepath: Output path for JSON file
    """
    # Use metrics from data if available, fall back to parameter
    stock_metrics = data.stock_metrics if data.stock_metrics else metrics
    conviction_scores = data.conviction_scores if hasattr(data, 'conviction_scores') else {}

    # Convert picks with enriched price data
    short_picks = [_pick_to_frontend(p, stock_metrics) for p in data.short_term_picks]
    medium_picks = [_pick_to_frontend(p, stock_metrics) for p in data.medium_term_picks]
    long_picks = [_pick_to_frontend(p, stock_metrics) for p in data.long_term_picks]

    all_picks = short_picks + medium_picks + long_picks

    # Build stock details (for individual stock pages)
    stock_details: dict[str, Any] = {}
    for pick_data in all_picks:
        ticker = pick_data["ticker"]
        stock_details[ticker] = {
            **pick_data,
            "priceHistory": [],  # Would need historical data fetch
            "relatedNews": [],   # Populated below
            "fundamentals": _get_fundamentals(stock_metrics.get(ticker)),
            "convictionBreakdown": _conviction_breakdown(conviction_scores.get(ticker)),
        }

    # Convert macro data
    macro_indicators = [_indicator_to_frontend(i) for i in data.macro_indicators]
    macro_risks = [_risk_to_frontend(r) for r in data.macro_risks]
    market_sentiment = _determine_market_sentiment(data.macro_indicators, data.macro_risks)

    # Convert news
    market_news = [_news_to_frontend(n, "market") for n in data.market_news[:20]]
    company_news = [_news_to_frontend(n, "company") for n in data.company_news[:20]]

    # Link news to stock details
    for news in company_news:
        for ticker in news["tickersMentioned"]:
            if ticker in stock_details:
                stock_details[ticker]["relatedNews"].append(news)

    # Calculate summary
    avg_conviction = (
        sum(p["convictionScore"] for p in all_picks) / len(all_picks)
        if all_picks else 0
    )
    high_risk_count = sum(1 for r in macro_risks if r["severity"] == "high")

    # Build final structure
    output = {
        "generatedAt": data.generated_at.isoformat(),
        "version": "1.0.0",
        "watchlist": data.watchlist,
        "picks": {
            "short": short_picks,
            "medium": medium_picks,
            "long": long_picks,
        },
        "stockDetails": stock_details,
        "macro": {
            "indicators": macro_indicators,
            "risks": macro_risks,
            "marketSentiment": market_sentiment,
            "lastUpdated": data.generated_at.isoformat(),
        },
        "news": {
            "market": market_news,
            "company": company_news,
        },
        "summary": {
            "totalPicks": len(all_picks),
            "avgConviction": round(avg_conviction, 2),
            "topSector": _get_top_sector(all_picks),
            "highRiskCount": high_risk_count,
            "newsCount": len(market_news) + len(company_news),
            "marketTrend": market_sentiment,
        },
    }

    # Write to file
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)


def _conviction_breakdown(score: ConvictionScore | None) -> dict[str, Any] | None:
    """Convert ConvictionScore to frontend format."""
    if not score:
        return None

    return {
        "valuationScore": round(score.valuation_score, 2),
        "growthScore": round(score.growth_score, 2),
        "qualityScore": round(score.quality_score, 2),
        "momentumScore": round(score.momentum_score, 2),
        "macroAdjustment": round(score.macro_adjustment, 2),
        "confidence": round(score.confidence, 2),
        "factorsUsed": score.factors_used,
        "factorsMissing": score.factors_missing,
    }


def _get_fundamentals(metrics: StockMetrics | None) -> dict[str, Any]:
    """Extract fundamentals from stock metrics."""
    if not metrics:
        return {}

    return {
        # Valuation metrics
        "peTrailing": metrics.pe_trailing,
        "peForward": metrics.pe_forward,
        "pegRatio": metrics.peg_ratio,
        "priceToBook": metrics.price_to_book,
        "priceToSales": metrics.price_to_sales,

        # Growth metrics
        "revenueGrowth": metrics.revenue_growth,
        "earningsGrowth": metrics.earnings_growth,

        # Profitability
        "profitMargin": metrics.profit_margin,
        "roe": metrics.roe,
        "roa": metrics.roa,

        # Technical
        "priceChange1d": metrics.price_change_1d,
        "priceChange1w": metrics.price_change_1w,
        "priceChange1m": metrics.price_change_1m,
        "priceChange3m": metrics.price_change_3m,
        "volumeAvg": metrics.volume_avg,
        "volumeCurrent": metrics.volume_current,
        "volumeRatio": metrics.volume_ratio,

        # Dividend
        "dividendYield": metrics.dividend_yield,
        "payoutRatio": metrics.payout_ratio,

        # Analyst
        "analystRating": metrics.analyst_rating,
        "priceTarget": metrics.price_target,
        "upsidePotential": metrics.upside_potential,

        # Fields not yet available in backend
        "beta": None,
        "fiftyTwoWeekHigh": None,
        "fiftyTwoWeekLow": None,
    }


def _get_top_sector(picks: list[dict[str, Any]]) -> str:
    """Get the most common sector from picks."""
    if not picks:
        return "technology"

    sector_counts: dict[str, int] = {}
    for pick in picks:
        sector = pick.get("sector", "technology")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    return max(sector_counts, key=sector_counts.get)
