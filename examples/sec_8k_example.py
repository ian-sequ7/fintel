"""
Example: Fetching SEC 8-K filings.

This script demonstrates how to use the SEC EDGAR adapter
to fetch material event disclosures (8-K filings).
"""

from adapters import SECAdapter


def main():
    """Demonstrate SEC 8-K adapter usage."""
    adapter = SECAdapter()

    print(f"SEC Adapter: {adapter.source_name}")
    print(f"Category: {adapter.category}")
    print(f"Reliability: {adapter.reliability}")
    print()

    # Example 1: Get recent 8-K filings
    print("Fetching recent 8-K filings...")
    try:
        filings = adapter.get_recent_filings(limit=10)
        print(f"Found {len(filings)} recent filings")

        for i, filing in enumerate(filings[:5], 1):
            data = filing.data
            print(f"\n{i}. {data['title']}")
            print(f"   Company: {data['company_name']}")
            print(f"   Date: {filing.timestamp.strftime('%Y-%m-%d')}")
            print(f"   Items: {', '.join(data['item_descriptions'])}")
            print(f"   URL: {data['url'][:80]}...")
            if data.get('is_high_priority'):
                print("   ⚠️  HIGH PRIORITY EVENT")
    except Exception as e:
        print(f"Error fetching recent filings: {e}")

    print("\n" + "="*80 + "\n")

    # Example 2: Get filings for a specific ticker
    ticker = "AAPL"
    print(f"Fetching 8-K filings for {ticker}...")
    try:
        ticker_filings = adapter.get_filings_for_ticker(ticker, limit=5)
        print(f"Found {len(ticker_filings)} filings for {ticker}")

        for i, filing in enumerate(ticker_filings, 1):
            data = filing.data
            print(f"\n{i}. {data['title']}")
            print(f"   Date: {filing.timestamp.strftime('%Y-%m-%d')}")
            print(f"   Items: {', '.join(data['item_descriptions'])}")
    except Exception as e:
        print(f"Error fetching {ticker} filings: {e}")

    print("\n" + "="*80 + "\n")

    # Example 3: Get recent earnings announcements
    print("Fetching recent earnings announcements (Item 2.02)...")
    try:
        earnings = adapter.get_earnings_announcements(limit=5)
        print(f"Found {len(earnings)} earnings announcements")

        for i, filing in enumerate(earnings, 1):
            data = filing.data
            print(f"\n{i}. {data['company_name']}: Earnings Announcement")
            print(f"   Date: {filing.timestamp.strftime('%Y-%m-%d')}")
            print(f"   URL: {data['url'][:80]}...")
    except Exception as e:
        print(f"Error fetching earnings: {e}")

    print("\n" + "="*80 + "\n")

    # Example 4: Get management changes
    print("Fetching recent management changes (Item 5.02)...")
    try:
        mgmt = adapter.get_management_changes(limit=5)
        print(f"Found {len(mgmt)} management change filings")

        for i, filing in enumerate(mgmt, 1):
            data = filing.data
            print(f"\n{i}. {data['company_name']}: Management Change")
            print(f"   Date: {filing.timestamp.strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"Error fetching management changes: {e}")


if __name__ == "__main__":
    main()
