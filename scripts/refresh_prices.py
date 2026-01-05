#!/usr/bin/env python3
"""
Fast price refresh script.

Updates ONLY current prices in report.json without regenerating everything.
Designed to run frequently (every 5-15 min) without hitting rate limits.

Target: <30 seconds, minimal API calls (batch queries via yfinance)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

REPORT_PATH = Path(__file__).parent.parent / "frontend" / "src" / "data" / "report.json"


def load_report() -> dict:
    """Load current report.json."""
    if not REPORT_PATH.exists():
        print(f"Error: {REPORT_PATH} not found. Run generate_frontend_data.py first.")
        sys.exit(1)

    with open(REPORT_PATH) as f:
        return json.load(f)


def save_report(report: dict) -> None:
    """Save updated report.json."""
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, default=str)


def get_active_tickers(report: dict) -> list[str]:
    """Get tickers that need price updates.

    Sources:
    - All picks (short/medium/long)
    - Watchlist
    - Stock details keys
    """
    tickers = set()

    # From picks
    for timeframe in ["short", "medium", "long"]:
        for pick in report.get("picks", {}).get(timeframe, []):
            tickers.add(pick["ticker"])

    # From watchlist
    for ticker in report.get("watchlist", []):
        tickers.add(ticker)

    # From stock details
    for ticker in report.get("stockDetails", {}).keys():
        tickers.add(ticker)

    return sorted(tickers)


def fetch_batch_prices(tickers: list[str]) -> dict[str, dict]:
    """Fetch prices for multiple tickers using yfinance batch download.

    yfinance handles batching internally and is efficient for multiple tickers.
    Returns dict of ticker -> price data.
    """
    if not tickers:
        return {}

    results = {}

    try:
        # yfinance batch download - gets latest prices efficiently
        # period="1d" gets just today's data
        data = yf.download(
            tickers,
            period="2d",  # 2 days to get previous close
            progress=False,
            threads=True,
        )

        if data.empty:
            print("  No data returned from yfinance")
            return {}

        # Handle single vs multiple ticker response format
        if len(tickers) == 1:
            # Single ticker: columns are just 'Open', 'High', etc.
            ticker = tickers[0]
            if len(data) >= 1:
                latest = data.iloc[-1]
                prev = data.iloc[-2] if len(data) >= 2 else latest

                price = float(latest["Close"])
                prev_close = float(prev["Close"])
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0

                results[ticker] = {
                    "price": round(price, 2),
                    "previous_close": round(prev_close, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "volume": int(latest["Volume"]) if latest["Volume"] else None,
                }
        else:
            # Multiple tickers: columns are MultiIndex (metric, ticker)
            for ticker in tickers:
                try:
                    if ticker not in data["Close"].columns:
                        continue

                    ticker_data = data["Close"][ticker].dropna()
                    if len(ticker_data) < 1:
                        continue

                    price = float(ticker_data.iloc[-1])
                    prev_close = float(ticker_data.iloc[-2]) if len(ticker_data) >= 2 else price

                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    volume = None
                    if "Volume" in data.columns.get_level_values(0):
                        vol_data = data["Volume"][ticker].dropna()
                        if len(vol_data) >= 1:
                            volume = int(vol_data.iloc[-1])

                    results[ticker] = {
                        "price": round(price, 2),
                        "previous_close": round(prev_close, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                        "volume": volume,
                    }
                except Exception as e:
                    # Skip individual ticker errors
                    continue

    except Exception as e:
        print(f"  Error fetching prices: {e}")
        return {}

    return results


def update_report_prices(report: dict, prices: dict[str, dict]) -> int:
    """Update prices in report.json structure.

    Updates:
    - picks[timeframe][].currentPrice, priceChange, priceChangePercent
    - stockDetails[ticker].currentPrice, priceChange, priceChangePercent

    Returns count of updated tickers.
    """
    updated = 0

    # Update picks
    for timeframe in ["short", "medium", "long"]:
        for pick in report.get("picks", {}).get(timeframe, []):
            ticker = pick["ticker"]
            if ticker in prices:
                p = prices[ticker]
                pick["currentPrice"] = p["price"]
                pick["priceChange"] = p["change"]
                pick["priceChangePercent"] = p["change_percent"]
                if p.get("volume"):
                    pick["volume"] = p["volume"]
                updated += 1

    # Update stock details
    for ticker, detail in report.get("stockDetails", {}).items():
        if ticker in prices:
            p = prices[ticker]
            detail["currentPrice"] = p["price"]
            detail["priceChange"] = p["change"]
            detail["priceChangePercent"] = p["change_percent"]
            if p.get("volume"):
                detail["volume"] = p["volume"]

    # Add/update timestamp
    now = datetime.now().isoformat()
    report["pricesUpdatedAt"] = now

    # Also update generatedAt if we're doing a price refresh
    # (keeps "last updated" visible in UI)
    if "meta" not in report:
        report["meta"] = {}
    report["meta"]["pricesUpdatedAt"] = now
    report["meta"]["priceUpdateMethod"] = "incremental"

    return updated


def main():
    start = time.time()
    print("Refreshing prices...")

    # Load current report
    report = load_report()

    # Get active tickers
    tickers = get_active_tickers(report)
    print(f"Found {len(tickers)} tickers to update")

    if not tickers:
        print("No tickers to update")
        return

    # Fetch prices (yfinance handles batching internally)
    print(f"  Fetching prices for {len(tickers)} tickers...")
    all_prices = fetch_batch_prices(tickers)
    print(f"  Got prices for {len(all_prices)}/{len(tickers)} tickers")

    # Update report
    updated = update_report_prices(report, all_prices)

    # Save
    save_report(report)

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Tickers updated: {updated}")
    print(f"  Report: {REPORT_PATH}")

    # Show sample
    if all_prices:
        sample_ticker = list(all_prices.keys())[0]
        sample = all_prices[sample_ticker]
        print(f"\nSample ({sample_ticker}):")
        print(f"  Price: ${sample['price']:.2f}")
        print(f"  Change: {sample['change']:+.2f} ({sample['change_percent']:+.2f}%)")


if __name__ == "__main__":
    main()
