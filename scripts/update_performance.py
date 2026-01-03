#!/usr/bin/env python3
"""
Pick Performance Tracker.

Tracks the performance of stock picks over time:
- Initializes performance records for new picks
- Updates prices at 7/30/90 day intervals
- Detects target hits and stop losses
- Calculates win rates and returns
"""

import hashlib
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf

from db import get_db, PickPerformance


def get_current_price(ticker: str) -> float | None:
    """Fetch current price for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get("regularMarketPrice") or info.get("currentPrice")
    except Exception as e:
        print(f"  Warning: Could not fetch price for {ticker}: {e}")
        return None


def get_historical_price(ticker: str, target_date: date) -> float | None:
    """Fetch historical closing price for a specific date."""
    try:
        stock = yf.Ticker(ticker)
        # Get a small range around the target date
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)
        hist = stock.history(start=start, end=end)

        if hist.empty:
            return None

        # Find the closest date
        hist.index = hist.index.date
        if target_date in hist.index:
            return float(hist.loc[target_date]["Close"])

        # Return closest available
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def calculate_return(entry_price: float, current_price: float) -> float:
    """Calculate percentage return."""
    if entry_price <= 0:
        return 0
    return round((current_price - entry_price) / entry_price * 100, 2)


def initialize_new_picks():
    """Create performance records for picks that don't have them."""
    db = get_db()
    picks = db.get_stock_picks(limit=500)

    initialized = 0
    for pick in picks:
        # Check if already has performance record
        existing = db.get_pick_performance(pick.id)
        if existing:
            continue

        # Need entry price
        if not pick.entry_price:
            continue

        # Create performance record
        perf_id = hashlib.md5(f"perf:{pick.id}".encode()).hexdigest()[:12]
        perf = PickPerformance(
            id=perf_id,
            pick_id=pick.id,
            ticker=pick.ticker,
            timeframe=pick.timeframe,
            entry_price=pick.entry_price,
            entry_date=pick.created_at.date() if pick.created_at else date.today(),
            target_price=pick.target_price,
            stop_loss=pick.stop_loss,
            status="active",
        )

        db.upsert_pick_performance(perf)
        initialized += 1
        print(f"  Initialized: {pick.ticker} ({pick.timeframe}) @ ${pick.entry_price:.2f}")

    return initialized


def update_active_picks():
    """Update performance for all active picks."""
    db = get_db()
    active_picks = db.get_active_picks_for_update()

    if not active_picks:
        print("No active picks to update.")
        return 0

    print(f"Updating {len(active_picks)} active picks...")
    updated = 0

    for perf in active_picks:
        current_price = get_current_price(perf.ticker)
        if not current_price:
            continue

        today = date.today()
        days_held = (today - perf.entry_date).days

        # Calculate current return
        current_return = calculate_return(perf.entry_price, current_price)

        # Update appropriate time bucket
        if days_held >= 7 and perf.return_7d is None:
            perf.price_7d = current_price
            perf.return_7d = current_return

        if days_held >= 30 and perf.return_30d is None:
            perf.price_30d = current_price
            perf.return_30d = current_return

        if days_held >= 90 and perf.return_90d is None:
            perf.price_90d = current_price
            perf.return_90d = current_return

        # Check for target hit
        if perf.target_price and current_price >= perf.target_price and not perf.target_hit:
            perf.target_hit = True
            perf.target_hit_date = today
            perf.status = "won"
            perf.final_return = current_return
            print(f"  🎯 TARGET HIT: {perf.ticker} @ ${current_price:.2f} (+{current_return:.1f}%)")

        # Check for stop hit
        if perf.stop_loss and current_price <= perf.stop_loss and not perf.stop_hit:
            perf.stop_hit = True
            perf.stop_hit_date = today
            perf.status = "lost"
            perf.final_return = current_return
            print(f"  🛑 STOP HIT: {perf.ticker} @ ${current_price:.2f} ({current_return:.1f}%)")

        # Check for expiration (90+ days without target/stop)
        if days_held >= 90 and perf.status == "active":
            perf.status = "expired"
            perf.final_return = current_return

        db.upsert_pick_performance(perf)
        updated += 1

        # Log progress
        status_icon = "🟢" if current_return > 0 else "🔴"
        print(f"  {status_icon} {perf.ticker}: ${perf.entry_price:.2f} → ${current_price:.2f} ({current_return:+.1f}%) [{days_held}d]")

    return updated


def print_performance_summary():
    """Print aggregate performance statistics."""
    db = get_db()

    print("\n" + "=" * 60)
    print("PICK PERFORMANCE TRACKER")
    print("=" * 60)

    # Overall summary
    summary = db.get_performance_summary()
    print(f"\n📊 OVERALL PERFORMANCE")
    print(f"   Total picks tracked: {summary['total_picks']}")
    print(f"   Win rate: {summary['win_rate']}%")
    print(f"   Active: {summary['active']} | Won: {summary['won']} | Lost: {summary['lost']}")

    if summary['avg_return_7d']:
        print(f"\n📈 AVERAGE RETURNS")
        print(f"   7-day:  {summary['avg_return_7d']:+.2f}%")
        print(f"   30-day: {summary['avg_return_30d']:+.2f}%")
        print(f"   90-day: {summary['avg_return_90d']:+.2f}%")

    if summary['best_pick']:
        print(f"\n🏆 BEST PICK: {summary['best_pick']['ticker']} ({summary['best_pick']['return']:+.1f}%)")
    if summary['worst_pick']:
        print(f"📉 WORST PICK: {summary['worst_pick']['ticker']} ({summary['worst_pick']['return']:+.1f}%)")

    # By timeframe
    for tf in ["short", "medium", "long"]:
        tf_summary = db.get_performance_summary(timeframe=tf)
        if tf_summary['total_picks'] > 0:
            print(f"\n📋 {tf.upper()} TERM ({tf_summary['total_picks']} picks)")
            print(f"   Win rate: {tf_summary['win_rate']}%")
            if tf_summary['avg_return_30d']:
                print(f"   Avg 30-day return: {tf_summary['avg_return_30d']:+.2f}%")

    print("\n" + "=" * 60)


def main():
    """Run performance tracking update."""
    import time

    print("=" * 60)
    print("PICK PERFORMANCE TRACKER")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Initialize new picks
    print("\n[1/3] Initializing new picks...")
    initialized = initialize_new_picks()
    print(f"Initialized {initialized} new picks for tracking")

    # Step 2: Update active picks
    print("\n[2/3] Updating active picks...")
    time.sleep(0.5)  # Rate limit
    updated = update_active_picks()
    print(f"Updated {updated} active picks")

    # Step 3: Print summary
    print("\n[3/3] Generating performance report...")
    print_performance_summary()

    # Database stats
    db = get_db()
    stats = db.get_stats()
    print(f"\nDatabase: {stats['pick_performance']} performance records")


if __name__ == "__main__":
    main()
