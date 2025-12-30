"""
Data export utilities.

Export report data to CSV, JSON, and other formats.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from domain import StockPick, ScoredNewsItem, MacroIndicator, Risk
from .report import ReportData
from .json_api import to_json


# ============================================================================
# CSV Export
# ============================================================================

def export_picks_csv(
    picks: list[StockPick],
    filepath: str | Path,
    include_header: bool = True,
) -> None:
    """
    Export stock picks to CSV.

    Args:
        picks: List of stock picks
        filepath: Output file path
        include_header: Include header row
    """
    fieldnames = [
        "ticker",
        "timeframe",
        "conviction_score",
        "thesis",
        "risk_factors",
        "entry_price",
        "target_price",
        "upside_percent",
        "generated_at",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if include_header:
            writer.writeheader()

        for pick in picks:
            upside = None
            if pick.entry_price and pick.target_price:
                upside = ((pick.target_price - pick.entry_price) / pick.entry_price) * 100

            writer.writerow({
                "ticker": pick.ticker,
                "timeframe": pick.timeframe.value,
                "conviction_score": f"{pick.conviction_score:.4f}",
                "thesis": pick.thesis,
                "risk_factors": "; ".join(pick.risk_factors),
                "entry_price": f"{pick.entry_price:.2f}" if pick.entry_price else "",
                "target_price": f"{pick.target_price:.2f}" if pick.target_price else "",
                "upside_percent": f"{upside:.2f}" if upside else "",
                "generated_at": pick.generated_at.isoformat(),
            })


def export_news_csv(
    news: list[ScoredNewsItem],
    filepath: str | Path,
    include_header: bool = True,
) -> None:
    """
    Export news items to CSV.

    Args:
        news: List of news items
        filepath: Output file path
        include_header: Include header row
    """
    fieldnames = [
        "title",
        "source",
        "url",
        "published",
        "relevance_score",
        "priority",
        "category",
        "sector",
        "tickers_mentioned",
        "keywords",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if include_header:
            writer.writeheader()

        for item in news:
            # Handle timezone-aware datetime
            pub = item.published
            if pub.tzinfo is not None:
                pub = pub.replace(tzinfo=None)

            writer.writerow({
                "title": item.title,
                "source": item.source,
                "url": item.url or "",
                "published": pub.isoformat(),
                "relevance_score": f"{item.relevance_score:.4f}",
                "priority": item.priority.value,
                "category": item.category.value,
                "sector": item.sector or "",
                "tickers_mentioned": ", ".join(item.tickers_mentioned),
                "keywords": ", ".join(item.keywords_found),
            })


def export_macro_csv(
    indicators: list[MacroIndicator],
    risks: list[Risk],
    filepath: str | Path,
) -> None:
    """
    Export macro data to CSV (two sections).

    Args:
        indicators: Macro indicators
        risks: Identified risks
        filepath: Output file path
    """
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Indicators section
        f.write("# Macro Indicators\n")
        ind_writer = csv.DictWriter(f, fieldnames=[
            "name", "series_id", "current_value", "previous_value",
            "unit", "trend", "impact", "as_of_date"
        ])
        ind_writer.writeheader()

        for ind in indicators:
            ind_writer.writerow({
                "name": ind.name,
                "series_id": ind.series_id or "",
                "current_value": f"{ind.current_value:.4f}",
                "previous_value": f"{ind.previous_value:.4f}" if ind.previous_value else "",
                "unit": ind.unit,
                "trend": ind.trend.value,
                "impact": ind.impact_assessment.value,
                "as_of_date": ind.as_of_date.isoformat(),
            })

        f.write("\n# Macro Risks\n")
        risk_writer = csv.DictWriter(f, fieldnames=[
            "name", "category", "description", "severity",
            "probability", "risk_score", "source_indicator"
        ])
        risk_writer.writeheader()

        for risk in risks:
            risk_writer.writerow({
                "name": risk.name,
                "category": risk.category.value,
                "description": risk.description,
                "severity": f"{risk.severity:.4f}",
                "probability": f"{risk.probability:.4f}",
                "risk_score": f"{risk.risk_score:.4f}",
                "source_indicator": risk.source_indicator or "",
            })


# ============================================================================
# JSON Export
# ============================================================================

def export_full_report_json(
    data: ReportData,
    filepath: str | Path,
    indent: int = 2,
) -> None:
    """
    Export full report to JSON.

    Args:
        data: Report data
        filepath: Output file path
        indent: JSON indentation
    """
    json_data = to_json(data)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=indent, default=str)


def export_picks_json(
    picks: list[StockPick],
    filepath: str | Path,
    indent: int = 2,
) -> None:
    """
    Export stock picks to JSON.

    Args:
        picks: List of stock picks
        filepath: Output file path
        indent: JSON indentation
    """
    data = []
    for pick in picks:
        upside = None
        if pick.entry_price and pick.target_price:
            upside = ((pick.target_price - pick.entry_price) / pick.entry_price) * 100

        data.append({
            "ticker": pick.ticker,
            "timeframe": pick.timeframe.value,
            "conviction_score": pick.conviction_score,
            "thesis": pick.thesis,
            "risk_factors": pick.risk_factors,
            "entry_price": pick.entry_price,
            "target_price": pick.target_price,
            "upside_percent": round(upside, 2) if upside else None,
            "generated_at": pick.generated_at.isoformat(),
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)


# ============================================================================
# Convenience Functions
# ============================================================================

def export_all(
    data: ReportData,
    output_dir: str | Path,
    base_name: str | None = None,
) -> dict[str, Path]:
    """
    Export report in all formats.

    Args:
        data: Report data
        output_dir: Output directory
        base_name: Base filename (default: report_{date})

    Returns:
        Dict of format -> filepath
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if base_name is None:
        date_str = data.generated_at.strftime("%Y%m%d_%H%M")
        base_name = f"report_{date_str}"

    files = {}

    # JSON
    json_path = output_dir / f"{base_name}.json"
    export_full_report_json(data, json_path)
    files["json"] = json_path

    # CSV - picks
    all_picks = data.short_term_picks + data.medium_term_picks + data.long_term_picks
    if all_picks:
        picks_path = output_dir / f"{base_name}_picks.csv"
        export_picks_csv(all_picks, picks_path)
        files["picks_csv"] = picks_path

    # CSV - news
    all_news = data.market_news + data.company_news
    if all_news:
        news_path = output_dir / f"{base_name}_news.csv"
        export_news_csv(all_news, news_path)
        files["news_csv"] = news_path

    # CSV - macro
    if data.macro_indicators or data.macro_risks:
        macro_path = output_dir / f"{base_name}_macro.csv"
        export_macro_csv(data.macro_indicators, data.macro_risks, macro_path)
        files["macro_csv"] = macro_path

    return files
