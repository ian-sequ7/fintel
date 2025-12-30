"""
Fintel CLI - Financial Intelligence Command Line Interface.

Usage:
    fintel report [--output FILE] [--format FORMAT] [--dry-run] [--verbose]
    fintel picks [--timeframe TIMEFRAME] [--count N]
    fintel news [--category CATEGORY] [--limit N]
    fintel macro
    fintel status

Examples:
    fintel report                          # Full markdown report to stdout
    fintel report -o report.md             # Save to file
    fintel report -f json --dry-run        # JSON with mock data
    fintel report --verbose                # Debug data flow
    fintel picks --timeframe short -n 3    # Top 3 short-term picks
    fintel news --category market          # Market-wide news only
"""

import argparse
import json
import sys
import logging
from datetime import datetime
from pathlib import Path

from orchestration.pipeline import Pipeline, PipelineConfig, run_pipeline, SourceStatus
from domain import Strategy, StrategyType
from presentation.report import ReportData, generate_markdown_report, write_report
from presentation.json_api import to_json
from presentation.export import export_all


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_report(args: argparse.Namespace) -> int:
    """Generate full report."""
    setup_logging(args.verbose)

    # Parse tickers
    tickers = args.tickers.split(",") if args.tickers else None

    # Parse strategy
    strategy = None
    if args.strategy:
        strategy_map = {
            "value": Strategy.value_strategy(),
            "growth": Strategy.growth_strategy(),
            "dividend": Strategy.dividend_strategy(),
            "balanced": Strategy(),
        }
        strategy = strategy_map.get(args.strategy, Strategy())

    # Show mode
    if args.dry_run:
        print("Running in DRY-RUN mode (using mock data)...", file=sys.stderr)
    if args.verbose:
        print("VERBOSE mode enabled", file=sys.stderr)

    # Run pipeline
    print("Generating report...", file=sys.stderr)
    data = run_pipeline(
        watchlist=tickers,
        dry_run=args.dry_run,
        verbose=args.verbose,
        strategy=strategy,
    )

    # Output
    if args.format == "json":
        output = json.dumps(to_json(data), indent=2, default=str)
        if args.output:
            Path(args.output).write_text(output)
            print(f"JSON report written to {args.output}", file=sys.stderr)
        else:
            print(output)

    elif args.format == "all":
        if not args.output:
            print("Error: --output directory required for 'all' format", file=sys.stderr)
            return 1
        files = export_all(data, args.output)
        print(f"Exported files:", file=sys.stderr)
        for fmt, path in files.items():
            print(f"  - {fmt}: {path}", file=sys.stderr)

    else:  # markdown
        content = generate_markdown_report(data)
        if args.output:
            Path(args.output).write_text(content)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(content)

    # Summary
    total_picks = len(data.short_term_picks) + len(data.medium_term_picks) + len(data.long_term_picks)
    total_news = len(data.market_news) + len(data.company_news)
    print(f"\nSummary: {total_picks} picks, {len(data.macro_risks)} risks, {total_news} news items", file=sys.stderr)

    return 0


def cmd_picks(args: argparse.Namespace) -> int:
    """Show stock picks."""
    setup_logging(args.verbose)

    tickers = args.tickers.split(",") if args.tickers else None

    print("Analyzing stocks...", file=sys.stderr)
    data = run_pipeline(
        watchlist=tickers,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    all_picks = []
    if args.timeframe in ["short", "all"]:
        all_picks.extend(data.short_term_picks)
    if args.timeframe in ["medium", "all"]:
        all_picks.extend(data.medium_term_picks)
    if args.timeframe in ["long", "all"]:
        all_picks.extend(data.long_term_picks)

    all_picks = sorted(all_picks, key=lambda x: x.conviction_score, reverse=True)[:args.count]

    if not all_picks:
        print("No picks found.", file=sys.stderr)
        return 0

    print(f"\n{'='*60}")
    print(f"  STOCK PICKS ({args.timeframe.upper()} TERM)")
    print(f"{'='*60}")

    for i, pick in enumerate(all_picks, 1):
        conviction_pct = int(pick.conviction_score * 100)
        bar = "█" * (conviction_pct // 10) + "░" * (10 - conviction_pct // 10)

        print(f"\n{i}. {pick.ticker} ({pick.timeframe.value})")
        print(f"   Conviction: [{bar}] {conviction_pct}%")
        print(f"   {pick.thesis}")

        if pick.entry_price and pick.target_price:
            upside = ((pick.target_price - pick.entry_price) / pick.entry_price) * 100
            print(f"   Entry: ${pick.entry_price:.2f} → Target: ${pick.target_price:.2f} ({upside:+.1f}%)")

        if pick.risk_factors:
            print(f"   Risks: {', '.join(pick.risk_factors[:2])}")

    print()
    return 0


def cmd_news(args: argparse.Namespace) -> int:
    """Show news."""
    setup_logging(args.verbose)

    from orchestration.news_aggregator import NewsAggregator
    from domain import NewsCategory

    print("Fetching news...", file=sys.stderr)
    aggregator = NewsAggregator()

    if args.category == "market":
        news = aggregator.get_market_news(limit=args.limit)
    elif args.category == "social":
        news = aggregator.get_social_sentiment(limit=args.limit)
    elif args.category == "company":
        news = [n for n in aggregator.aggregate()[:args.limit * 2]
                if n.category in [NewsCategory.COMPANY, NewsCategory.SECTOR]][:args.limit]
    else:
        news = aggregator.aggregate()[:args.limit]

    if not news:
        print("No news found.", file=sys.stderr)
        return 0

    print(f"\n{'='*60}")
    print(f"  NEWS ({args.category.upper()})")
    print(f"{'='*60}")

    priority_icons = {
        "critical": "🚨",
        "high": "⚠️ ",
        "medium": "📌",
        "low": "📎",
    }

    for item in news:
        icon = priority_icons.get(item.priority.value, "  ")
        score = int(item.relevance_score * 100)

        print(f"\n{icon} {item.title}")
        print(f"   {item.source} | {item.category.value} | Relevance: {score}%")

        if item.tickers_mentioned:
            print(f"   Tickers: {', '.join(item.tickers_mentioned[:5])}")
        if item.url:
            print(f"   {item.url}")

    print()
    return 0


def cmd_macro(args: argparse.Namespace) -> int:
    """Show macro environment."""
    setup_logging(args.verbose)

    from adapters import FredAdapter
    from domain import identify_headwinds, MacroIndicator, Trend, Impact

    print("Fetching macro data...", file=sys.stderr)
    fred = FredAdapter()

    try:
        observations = fred.get_all_indicators()
    except Exception as e:
        print(f"Error fetching macro data: {e}", file=sys.stderr)
        return 1

    print(f"\n{'='*60}")
    print("  MACROECONOMIC ENVIRONMENT")
    print(f"{'='*60}")

    print("\n### Key Indicators\n")
    print(f"{'Indicator':<30} {'Value':>12} {'Unit':<10}")
    print("-" * 55)

    indicators = []
    for obs in observations:
        name = obs.data.get("name", "Unknown")
        value = obs.data.get("value", 0)
        unit = obs.data.get("unit", "")

        print(f"{name:<30} {value:>12.2f} {unit:<10}")

        indicators.append(MacroIndicator(
            name=name,
            series_id=obs.data.get("series_id"),
            current_value=value,
            unit=unit,
            trend=Trend.STABLE,
            impact_assessment=Impact.NEUTRAL,
        ))

    # Identify risks
    risks = identify_headwinds(indicators)

    if risks:
        print("\n### Headwinds & Risks\n")
        for i, risk in enumerate(risks[:5], 1):
            severity_pct = int(risk.severity * 100)
            print(f"{i}. {risk.name} (severity: {severity_pct}%)")
            print(f"   {risk.description}")
            print()

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show pipeline status and data source health."""
    setup_logging(args.verbose)

    print("Checking data sources...", file=sys.stderr)

    config = PipelineConfig(watchlist=["AAPL"])  # Just test one ticker
    pipeline = Pipeline(config, dry_run=False, verbose=args.verbose)

    # Run minimal pipeline to check sources
    try:
        pipeline.run()
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)

    status = pipeline.get_status()

    print(f"\n{'='*60}")
    print("  DATA SOURCE STATUS")
    print(f"{'='*60}\n")

    # Group by source type
    source_health = {
        "yahoo": [],
        "fred": [],
        "reddit": [],
        "rss": [],
    }

    for name, result in status.sources.items():
        for src_type in source_health.keys():
            if name.startswith(src_type) or src_type in name:
                source_health[src_type].append(result)
                break

    status_icons = {
        SourceStatus.OK: "✅",
        SourceStatus.PARTIAL: "⚠️",
        SourceStatus.FAILED: "❌",
        SourceStatus.SKIPPED: "⏭️",
        SourceStatus.STALE: "🕐",
    }

    for src_type, results in source_health.items():
        if not results:
            continue

        ok_count = sum(1 for r in results if r.status == SourceStatus.OK)
        total = len(results)

        overall = "✅" if ok_count == total else ("⚠️" if ok_count > 0 else "❌")
        print(f"{overall} {src_type.upper()}: {ok_count}/{total} endpoints OK")

        if args.verbose:
            for r in results:
                icon = status_icons.get(r.status, "?")
                error_msg = f" - {r.error}" if r.error else ""
                print(f"   {icon} {r.source}{error_msg}")

    print()

    if status.warnings:
        print("Warnings:")
        for w in status.warnings[:5]:
            print(f"  ⚠️ {w}")
        print()

    if status.errors:
        print("Errors:")
        for e in status.errors[:5]:
            print(f"  ❌ {e}")
        print()

    # Overall health
    if status.is_healthy:
        print("Overall: ✅ Pipeline healthy")
    else:
        print("Overall: ⚠️ Pipeline degraded (some sources unavailable)")

    if status.duration:
        print(f"Check duration: {status.duration.total_seconds():.1f}s")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fintel",
        description="Financial Intelligence System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fintel report                      Generate markdown report
  fintel report -o report.md         Save to file
  fintel report --dry-run            Use mock data
  fintel report --verbose            Debug output
  fintel report -f json              JSON output
  fintel picks --timeframe short     Short-term picks only
  fintel news --category market      Market-wide news
  fintel macro                       Macro indicators
  fintel status                      Check data sources
        """,
    )

    # Global flags
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug output",
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
    report_parser.add_argument(
        "--strategy",
        choices=["value", "growth", "dividend", "balanced"],
        default="balanced",
        help="Investment strategy",
    )
    report_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock data instead of live data",
    )
    report_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
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
    picks_parser.add_argument("-t", "--tickers", help="Comma-separated tickers")
    picks_parser.add_argument("--dry-run", action="store_true", help="Use mock data")
    picks_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    picks_parser.set_defaults(func=cmd_picks)

    # News command
    news_parser = subparsers.add_parser("news", help="Show news")
    news_parser.add_argument(
        "-c", "--category",
        choices=["all", "market", "company", "social"],
        default="all",
        help="News category",
    )
    news_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of items")
    news_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    news_parser.set_defaults(func=cmd_news)

    # Macro command
    macro_parser = subparsers.add_parser("macro", help="Show macro environment")
    macro_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    macro_parser.set_defaults(func=cmd_macro)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check data source health")
    status_parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
