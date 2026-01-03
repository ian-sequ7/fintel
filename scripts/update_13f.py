#!/usr/bin/env python3
"""
13F Holdings Updater.

Fetches latest 13F filings from SEC EDGAR for tracked hedge funds.
Updates database with new holdings and calculates changes from previous quarter.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import SEC13FAdapter
from db import get_db


def print_header():
    """Print script header."""
    print("=" * 60)
    print("13F HOLDINGS UPDATER")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


def print_fund_summary(db):
    """Print summary of tracked funds."""
    funds = db.get_all_hedge_funds()
    print(f"\n📊 TRACKED FUNDS ({len(funds)})")

    for fund in funds:
        filing_str = fund.last_filing_date.isoformat() if fund.last_filing_date else "Never"
        print(f"   {fund.name:<30} ({fund.manager}) - Last: {filing_str}")


def print_activity_summary(db):
    """Print activity summary."""
    summary = db.get_hedge_fund_summary()

    print("\n📈 ACTIVITY SUMMARY")
    print(f"   Unique tickers: {summary['unique_tickers']}")
    print(f"   New positions: {summary['new_positions']}")
    print(f"   Increased: {summary['increased']}")
    print(f"   Decreased: {summary['decreased']}")
    print(f"   Sold: {summary['sold']}")


def print_recent_activity(db, limit: int = 10):
    """Print recent activity."""
    holdings = db.get_recent_hedge_fund_activity(limit=limit)

    if not holdings:
        print("\n   No recent activity")
        return

    print(f"\n🔔 RECENT ACTIVITY (top {limit})")

    for h in holdings:
        fund = db.get_hedge_fund(h.fund_id)
        fund_name = fund.name if fund else "Unknown"
        ticker = h.ticker or h.issuer_name[:15]

        if h.action == "new":
            icon = "🆕"
            action = "NEW"
        elif h.action == "increased":
            icon = "📈"
            action = f"+{h.shares_change_pct:.1f}%" if h.shares_change_pct else "UP"
        elif h.action == "decreased":
            icon = "📉"
            action = f"{h.shares_change_pct:.1f}%" if h.shares_change_pct else "DOWN"
        elif h.action == "sold":
            icon = "🚫"
            action = "SOLD"
        else:
            icon = "➡️"
            action = "HOLD"

        print(f"   {icon} {ticker:<12} | {fund_name:<20} | {action}")


def main():
    """Run 13F update."""
    print_header()

    # Initialize adapter
    adapter = SEC13FAdapter()
    db = get_db()

    # Show current state
    print("\n[1/3] Current fund tracking status...")
    print_fund_summary(db)

    # Refresh all funds
    print("\n[2/3] Fetching latest 13F filings...")
    results = adapter.refresh_all_funds()

    print(f"\n   Funds processed: {results['funds_processed']}")
    print(f"   Holdings updated: {results['holdings_updated']}")

    if results['errors']:
        print(f"\n   Errors ({len(results['errors'])}):")
        for err in results['errors'][:5]:
            print(f"      - {err}")

    # Show summary
    print("\n[3/3] Generating activity report...")
    print_activity_summary(db)
    print_recent_activity(db, limit=15)

    # Database stats
    stats = db.get_stats()
    print("\n" + "=" * 60)
    print(f"Database: {stats['hedge_funds']} funds, {stats['hedge_fund_holdings']} holdings")
    print("=" * 60)


if __name__ == "__main__":
    main()
