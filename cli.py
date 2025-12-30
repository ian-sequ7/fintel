"""
Fintel CLI - Financial Intelligence Command Line Interface.

Usage:
    python -m fintel report [--output FILE] [--format FORMAT]
    python -m fintel picks [--timeframe TIMEFRAME] [--count N]
    python -m fintel news [--category CATEGORY] [--limit N]
    python -m fintel macro
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from domain import (
    StockPick,
    MacroIndicator,
    Risk,
    Trend,
    Impact,
    ScoredNewsItem,
    NewsCategory,
    identify_headwinds,
)
from domain.models import Timeframe
from domain.analysis_types import RiskCategory
from adapters import YahooAdapter, FredAdapter
from orchestration.news_aggregator import NewsAggregator
from presentation.report import ReportData, generate_markdown_report, write_report
from presentation.json_api import to_json
from presentation.export import export_all


def build_report_data(
    tickers: list[str] | None = None,
    include_news: bool = True,
) -> ReportData:
    """
    Build report data by fetching from all sources.

    This is the main orchestration function that coordinates
    adapters, analyzers, and aggregators.
    """
    tickers = tickers or ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

    print("Fetching data...", file=sys.stderr)

    # Fetch macro data
    print("  - Macro indicators", file=sys.stderr)
    fred = FredAdapter()
    try:
        macro_obs = fred.get_all_indicators()
        macro_indicators = []
        for obs in macro_obs:
            macro_indicators.append(MacroIndicator(
                name=obs.data.get("name", "Unknown"),
                series_id=obs.data.get("series_id"),
                current_value=obs.data.get("value", 0),
                unit=obs.data.get("unit", ""),
                trend=Trend.STABLE,  # Would need historical data for trend
                impact_assessment=Impact.NEUTRAL,
            ))
    except Exception as e:
        print(f"  ! Macro fetch failed: {e}", file=sys.stderr)
        macro_indicators = []

    # Identify macro risks
    macro_risks = identify_headwinds(macro_indicators)

    # Fetch news
    market_news = []
    company_news = []

    if include_news:
        print("  - News aggregation", file=sys.stderr)
        aggregator = NewsAggregator()

        try:
            all_news = aggregator.aggregate(
                tickers=tickers,
                include_market=True,
                include_social=True,
            )

            # Separate by category
            for item in all_news:
                if item.category == NewsCategory.MARKET_WIDE:
                    market_news.append(item)
                elif item.category in [NewsCategory.COMPANY, NewsCategory.SECTOR]:
                    company_news.append(item)
        except Exception as e:
            print(f"  ! News fetch failed: {e}", file=sys.stderr)

    # Generate stock picks (simplified - in production would use full analysis)
    print("  - Generating picks", file=sys.stderr)
    yahoo = YahooAdapter()

    short_picks = []
    medium_picks = []
    long_picks = []

    for ticker in tickers[:5]:  # Limit for demo
        try:
            price_obs = yahoo.get_price(ticker)
            if not price_obs:
                continue

            price_data = price_obs[0].data

            # Simple scoring based on available data
            change_pct = price_data.get("change_percent", 0)

            # Classify by momentum
            if change_pct > 2:
                timeframe = Timeframe.SHORT
            elif change_pct < -2:
                timeframe = Timeframe.LONG  # Contrarian
            else:
                timeframe = Timeframe.MEDIUM

            # Create pick
            pick = StockPick(
                ticker=ticker,
                timeframe=timeframe,
                conviction_score=0.6 + (change_pct / 100) if -40 < change_pct < 40 else 0.5,
                thesis=f"{ticker} trading at ${price_data.get('price', 0):.2f} with {change_pct:.1f}% recent change.",
                risk_factors=["Market volatility", "Sector rotation"],
                entry_price=price_data.get("price"),
            )

            if timeframe == Timeframe.SHORT:
                short_picks.append(pick)
            elif timeframe == Timeframe.MEDIUM:
                medium_picks.append(pick)
            else:
                long_picks.append(pick)

        except Exception as e:
            print(f"  ! Failed to analyze {ticker}: {e}", file=sys.stderr)

    print("Done.", file=sys.stderr)

    return ReportData(
        generated_at=datetime.now(),
        macro_indicators=macro_indicators,
        macro_risks=macro_risks,
        short_term_picks=sorted(short_picks, key=lambda x: x.conviction_score, reverse=True),
        medium_term_picks=sorted(medium_picks, key=lambda x: x.conviction_score, reverse=True),
        long_term_picks=sorted(long_picks, key=lambda x: x.conviction_score, reverse=True),
        market_news=market_news[:10],
        company_news=company_news[:10],
        watchlist=tickers,
    )


def cmd_report(args: argparse.Namespace) -> int:
    """Generate full report."""
    data = build_report_data(
        tickers=args.tickers.split(",") if args.tickers else None,
        include_news=not args.no_news,
    )

    if args.format == "json":
        import json
        output = json.dumps(to_json(data), indent=2, default=str)
        if args.output:
            Path(args.output).write_text(output)
        else:
            print(output)
    elif args.format == "all":
        if not args.output:
            print("Error: --output directory required for 'all' format", file=sys.stderr)
            return 1
        files = export_all(data, args.output)
        print(f"Exported to: {list(files.values())}", file=sys.stderr)
    else:  # markdown
        content = generate_markdown_report(data)
        if args.output:
            Path(args.output).write_text(content)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(content)

    return 0


def cmd_picks(args: argparse.Namespace) -> int:
    """Show stock picks."""
    data = build_report_data(
        tickers=args.tickers.split(",") if args.tickers else None,
        include_news=False,
    )

    all_picks = []
    if args.timeframe in ["short", "all"]:
        all_picks.extend(data.short_term_picks)
    if args.timeframe in ["medium", "all"]:
        all_picks.extend(data.medium_term_picks)
    if args.timeframe in ["long", "all"]:
        all_picks.extend(data.long_term_picks)

    all_picks = sorted(all_picks, key=lambda x: x.conviction_score, reverse=True)[:args.count]

    for pick in all_picks:
        print(f"\n{pick.ticker} ({pick.timeframe.value})")
        print(f"  Conviction: {pick.conviction_score:.0%}")
        print(f"  {pick.thesis}")
        if pick.risk_factors:
            print(f"  Risks: {', '.join(pick.risk_factors[:2])}")

    return 0


def cmd_news(args: argparse.Namespace) -> int:
    """Show news."""
    aggregator = NewsAggregator()

    if args.category == "market":
        news = aggregator.get_market_news(limit=args.limit)
    elif args.category == "social":
        news = aggregator.get_social_sentiment(limit=args.limit)
    else:
        news = aggregator.aggregate()[:args.limit]

    for item in news:
        priority = {"critical": "🚨", "high": "⚠️", "medium": "📌", "low": "📎"}.get(
            item.priority.value, ""
        )
        print(f"\n{priority} {item.title}")
        print(f"   {item.source} | {item.category.value} | Score: {item.relevance_score:.2f}")
        if item.tickers_mentioned:
            print(f"   Tickers: {', '.join(item.tickers_mentioned[:5])}")

    return 0


def cmd_macro(args: argparse.Namespace) -> int:
    """Show macro environment."""
    fred = FredAdapter()

    print("\n## Macro Indicators\n")

    try:
        observations = fred.get_all_indicators()
        for obs in observations:
            name = obs.data.get("name", "Unknown")
            value = obs.data.get("value", 0)
            unit = obs.data.get("unit", "")
            print(f"  {name}: {value}{unit}")
    except Exception as e:
        print(f"Error fetching macro data: {e}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fintel",
        description="Financial Intelligence System",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate full report")
    report_parser.add_argument("-o", "--output", help="Output file path")
    report_parser.add_argument(
        "-f", "--format",
        choices=["markdown", "json", "all"],
        default="markdown",
        help="Output format",
    )
    report_parser.add_argument("-t", "--tickers", help="Comma-separated tickers")
    report_parser.add_argument("--no-news", action="store_true", help="Skip news")
    report_parser.set_defaults(func=cmd_report)

    # Picks command
    picks_parser = subparsers.add_parser("picks", help="Show stock picks")
    picks_parser.add_argument(
        "--timeframe",
        choices=["short", "medium", "long", "all"],
        default="all",
        help="Timeframe filter",
    )
    picks_parser.add_argument("-n", "--count", type=int, default=10, help="Number of picks")
    picks_parser.add_argument("-t", "--tickers", help="Comma-separated tickers to analyze")
    picks_parser.set_defaults(func=cmd_picks)

    # News command
    news_parser = subparsers.add_parser("news", help="Show news")
    news_parser.add_argument(
        "-c", "--category",
        choices=["all", "market", "social"],
        default="all",
        help="News category",
    )
    news_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of items")
    news_parser.set_defaults(func=cmd_news)

    # Macro command
    macro_parser = subparsers.add_parser("macro", help="Show macro environment")
    macro_parser.set_defaults(func=cmd_macro)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
