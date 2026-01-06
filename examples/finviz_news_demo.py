#!/usr/bin/env python3
"""
Finviz news adapter demo.

Demonstrates how to:
1. Fetch ticker-specific news from Finviz
2. Convert to RawNewsItem for news aggregation
3. Aggregate and score news with the domain layer

Usage:
    python examples/finviz_news_demo.py AAPL
"""

import sys
from datetime import datetime

from adapters import FinvizAdapter
from domain import aggregate_news, filter_by_priority, NewsPriority


def main():
    if len(sys.argv) < 2:
        print("Usage: python finviz_news_demo.py <TICKER>")
        print("Example: python finviz_news_demo.py AAPL")
        sys.exit(1)

    ticker = sys.argv[1].upper()

    print(f"\n=== Fetching Finviz news for {ticker} ===\n")

    # Create adapter
    adapter = FinvizAdapter()

    try:
        # Fetch news (returns Observations)
        observations = adapter.get_ticker_news(ticker)

        if not observations:
            print(f"No news found for {ticker}")
            return

        print(f"✓ Fetched {len(observations)} news items\n")

        # Convert to RawNewsItem for aggregation
        raw_news_items = adapter.get_raw_news_items(ticker)

        # Aggregate and score news
        scored_news = aggregate_news(raw_news_items)

        print(f"✓ Aggregated and scored: {len(scored_news)} items\n")

        # Display high-priority news
        high_priority = filter_by_priority(scored_news, NewsPriority.HIGH)

        if high_priority:
            print(f"🔥 HIGH PRIORITY NEWS ({len(high_priority)} items):\n")
            for item in high_priority[:5]:
                print(f"  [{item.priority.value.upper()}] {item.title}")
                print(f"  Source: {item.source} | Score: {item.relevance_score:.2f}")
                print(f"  Published: {item.published.strftime('%Y-%m-%d %H:%M')}")
                if item.tickers_mentioned:
                    print(f"  Tickers: {', '.join(item.tickers_mentioned)}")
                print()

        # Display all news
        print(f"\n📰 ALL NEWS ({len(scored_news)} items):\n")
        for i, item in enumerate(scored_news[:10], 1):
            print(f"{i}. [{item.priority.value}] {item.title}")
            print(f"   {item.source} | {item.published.strftime('%Y-%m-%d %H:%M')} | Score: {item.relevance_score:.2f}")
            if item.url:
                print(f"   URL: {item.url}")
            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
