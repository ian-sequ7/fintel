"""
Markdown report generator.

Transforms domain objects into formatted markdown reports.
Pure formatting logic - no I/O except final file writing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TextIO
import sys

from domain import (
    StockPick,
    Risk,
    Timeframe,
    ScoredNewsItem,
    NewsCategory,
    MacroIndicator,
    Trend,
    Impact,
    ConvictionScore,
)
from domain.models import Timeframe as ModelTimeframe


@dataclass
class ReportData:
    """
    All data needed to generate a report.

    Collected from various analyzers and aggregators.
    """
    generated_at: datetime = field(default_factory=datetime.now)

    # Macro data
    macro_indicators: list[MacroIndicator] = field(default_factory=list)
    macro_risks: list[Risk] = field(default_factory=list)

    # Stock picks by timeframe
    short_term_picks: list[StockPick] = field(default_factory=list)
    medium_term_picks: list[StockPick] = field(default_factory=list)
    long_term_picks: list[StockPick] = field(default_factory=list)

    # News
    market_news: list[ScoredNewsItem] = field(default_factory=list)
    company_news: list[ScoredNewsItem] = field(default_factory=list)

    # Metadata
    title: str = "Stock Picks Report"
    watchlist: list[str] = field(default_factory=list)

    # Stock metrics (for frontend enrichment)
    stock_metrics: dict = field(default_factory=dict)
    conviction_scores: dict = field(default_factory=dict)  # ticker -> ConvictionScore

    # Smart money signals (congress trades, unusual options)
    smart_money_signals: list = field(default_factory=list)


def _format_date(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime("%B %d, %Y")


def _format_datetime(dt: datetime) -> str:
    """Format datetime with time."""
    return dt.strftime("%Y-%m-%d %H:%M")


def _conviction_bar(score: float, width: int = 10) -> str:
    """Create ASCII bar for conviction score."""
    filled = int(score * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score:.0%}"


def _trend_arrow(trend: Trend) -> str:
    """Get arrow for trend direction."""
    return {
        Trend.RISING: "↑",
        Trend.FALLING: "↓",
        Trend.STABLE: "→",
    }.get(trend, "?")


def _impact_emoji(impact: Impact) -> str:
    """Get emoji for impact assessment."""
    return {
        Impact.POSITIVE: "🟢",
        Impact.NEGATIVE: "🔴",
        Impact.NEUTRAL: "🟡",
    }.get(impact, "⚪")


def _priority_badge(priority: str) -> str:
    """Get badge for priority level."""
    return {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "📌",
        "low": "📎",
    }.get(priority, "")


# ============================================================================
# Section Generators
# ============================================================================

def generate_header(data: ReportData) -> str:
    """Generate report header."""
    lines = [
        f"# {data.title} - {_format_date(data.generated_at)}",
        "",
        f"*Generated: {_format_datetime(data.generated_at)}*",
        "",
    ]

    if data.watchlist:
        lines.append(f"**Watchlist:** {', '.join(data.watchlist[:10])}")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def generate_macro_section(data: ReportData) -> str:
    """Generate macroeconomic headwinds section."""
    lines = [
        "## Macroeconomic Environment",
        "",
    ]

    # Current indicators
    if data.macro_indicators:
        lines.append("### Key Indicators")
        lines.append("")
        lines.append("| Indicator | Value | Trend | Impact |")
        lines.append("|-----------|-------|-------|--------|")

        for ind in data.macro_indicators[:20]:  # Show up to 20 indicators
            trend = _trend_arrow(ind.trend)
            impact = _impact_emoji(ind.impact_assessment)
            value = f"{ind.current_value:.2f}{ind.unit}" if ind.unit else f"{ind.current_value:.2f}"
            lines.append(f"| {ind.name} | {value} | {trend} | {impact} |")

        lines.append("")

    # Identified risks
    if data.macro_risks:
        lines.append("### Headwinds & Risks")
        lines.append("")

        for i, risk in enumerate(data.macro_risks[:10], 1):  # Show up to 10 risks
            severity_bar = _conviction_bar(risk.severity, 5)
            lines.append(f"**{i}. {risk.name}** ({risk.category.value})")
            lines.append(f"   - Severity: {severity_bar}")
            lines.append(f"   - {risk.description}")
            lines.append("")
    else:
        lines.append("*No significant macro headwinds identified.*")
        lines.append("")

    return "\n".join(lines)


def generate_picks_section(
    picks: list[StockPick],
    timeframe_label: str,
    timeframe_desc: str,
) -> str:
    """Generate stock picks section for a timeframe."""
    lines = [
        f"## {timeframe_label} ({timeframe_desc})",
        "",
    ]

    if not picks:
        lines.append("*No picks for this timeframe.*")
        lines.append("")
        return "\n".join(lines)

    for i, pick in enumerate(picks[:15], 1):  # Show up to 15 picks per timeframe
        conviction = _conviction_bar(pick.conviction_score)

        lines.append(f"### {i}. {pick.ticker}")
        lines.append("")
        lines.append(f"**Conviction:** {conviction}")
        lines.append("")
        lines.append(f"**Thesis:** {pick.thesis}")
        lines.append("")

        if pick.entry_price or pick.target_price:
            entry = f"${pick.entry_price:.2f}" if pick.entry_price else "N/A"
            target = f"${pick.target_price:.2f}" if pick.target_price else "N/A"
            if pick.entry_price and pick.target_price:
                upside = ((pick.target_price - pick.entry_price) / pick.entry_price) * 100
                lines.append(f"**Entry:** {entry} → **Target:** {target} ({upside:+.1f}%)")
            else:
                lines.append(f"**Entry:** {entry} | **Target:** {target}")
            lines.append("")

        if pick.risk_factors:
            lines.append("**Risks:**")
            for risk in pick.risk_factors[:3]:
                lines.append(f"- {risk}")
            lines.append("")

    return "\n".join(lines)


def generate_news_section(
    news: list[ScoredNewsItem],
    title: str,
    show_tickers: bool = False,
) -> str:
    """Generate news section."""
    lines = [
        f"## {title}",
        "",
    ]

    if not news:
        lines.append("*No significant news.*")
        lines.append("")
        return "\n".join(lines)

    for item in news[:10]:
        badge = _priority_badge(item.priority.value)
        age = _format_relative_time(item.published)

        lines.append(f"{badge} **{item.title}**")
        lines.append(f"   *{item.source} • {age}*")

        if show_tickers and item.tickers_mentioned:
            tickers = ", ".join(item.tickers_mentioned[:5])
            lines.append(f"   Tickers: {tickers}")

        if item.url:
            lines.append(f"   [Read more]({item.url})")

        lines.append("")

    return "\n".join(lines)


def _format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2 hours ago')."""
    now = datetime.now()

    # Handle timezone
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins} min{'s' if mins > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"


def generate_footer(data: ReportData) -> str:
    """Generate report footer."""
    lines = [
        "---",
        "",
        "*This report is for informational purposes only and does not constitute investment advice.*",
        "",
        f"*Report generated by Fintel on {_format_datetime(data.generated_at)}*",
    ]
    return "\n".join(lines)


# ============================================================================
# Main Report Generation
# ============================================================================

def generate_section(section_name: str, data: ReportData) -> str:
    """Generate a specific section of the report."""
    generators = {
        "header": generate_header,
        "macro": generate_macro_section,
        "short": lambda d: generate_picks_section(
            d.short_term_picks, "Short-Term Picks", "1-3 months"
        ),
        "medium": lambda d: generate_picks_section(
            d.medium_term_picks, "Medium-Term Picks", "3-12 months"
        ),
        "long": lambda d: generate_picks_section(
            d.long_term_picks, "Long-Term Picks", "1-3 years"
        ),
        "market_news": lambda d: generate_news_section(
            d.market_news, "Market News Highlights", show_tickers=False
        ),
        "company_news": lambda d: generate_news_section(
            d.company_news, "Company News", show_tickers=True
        ),
        "footer": generate_footer,
    }

    generator = generators.get(section_name)
    if generator:
        return generator(data)
    else:
        return f"<!-- Unknown section: {section_name} -->\n"


def generate_markdown_report(
    data: ReportData,
    sections: list[str] | None = None,
) -> str:
    """
    Generate full markdown report.

    Args:
        data: Report data from analyzers
        sections: Optional list of sections to include (default: all)

    Returns:
        Formatted markdown string
    """
    default_sections = [
        "header",
        "macro",
        "short",
        "medium",
        "long",
        "market_news",
        "company_news",
        "footer",
    ]

    sections = sections or default_sections

    parts = []
    for section in sections:
        content = generate_section(section, data)
        if content:
            parts.append(content)

    return "\n".join(parts)


def write_report(
    data: ReportData,
    output: TextIO | None = None,
    filepath: str | None = None,
) -> str:
    """
    Generate and write report.

    Args:
        data: Report data
        output: File-like object to write to (default: stdout)
        filepath: Optional file path to write to

    Returns:
        Generated markdown content
    """
    content = generate_markdown_report(data)

    if filepath:
        with open(filepath, "w") as f:
            f.write(content)
    elif output:
        output.write(content)
    else:
        sys.stdout.write(content)

    return content
