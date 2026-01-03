"""
Capitol Trades web scraper.

Scrapes congressional trading data from capitoltrades.com using Playwright.
This is a fallback when the S3 JSON feeds are unavailable.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ScrapedTrade:
    """Raw trade data from Capitol Trades."""
    politician: str
    party: str
    chamber: str
    state: str
    issuer: str
    ticker: str | None
    transaction_type: str
    published_date: datetime | None
    traded_date: datetime | None
    size: str
    amount_range: tuple[int, int]


def _parse_party_info(party_info: str) -> tuple[str, str, str]:
    """Parse party info string like 'Republican|House|IN' or 'Democrat|House|NJ'."""
    parts = party_info.replace('|', ' ').split()

    party = "I"
    chamber = "House"
    state = ""

    for part in parts:
        part_lower = part.lower()
        if "republican" in part_lower:
            party = "R"
        elif "democrat" in part_lower:
            party = "D"
        elif "independent" in part_lower:
            party = "I"
        elif part_lower in ("house", "senate"):
            chamber = part.capitalize()
        elif len(part) == 2 and part.isupper():
            state = part

    return party, chamber, state


def _parse_date(date_str: str) -> datetime | None:
    """Parse date string like '31 Dec 2025' to datetime."""
    if not date_str:
        return None

    # Clean up the string
    date_str = ' '.join(date_str.strip().split())

    formats = [
        "%d %b %Y",   # 31 Dec 2025
        "%d %B %Y",   # 31 December 2025
        "%b %d %Y",   # Dec 31 2025
        "%Y-%m-%d",   # 2025-12-31
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def _parse_amount_range(size_str: str) -> tuple[int, int]:
    """Parse size string like '1K–15K' or '5M–25M' to amount range."""
    size_str = size_str.strip().upper().replace(',', '')

    # Handle common formats with either dash type
    size_map = {
        "1K–15K": (1001, 15000),
        "1K-15K": (1001, 15000),
        "15K–50K": (15001, 50000),
        "15K-50K": (15001, 50000),
        "50K–100K": (50001, 100000),
        "50K-100K": (50001, 100000),
        "100K–250K": (100001, 250000),
        "100K-250K": (100001, 250000),
        "250K–500K": (250001, 500000),
        "250K-500K": (250001, 500000),
        "500K–1M": (500001, 1000000),
        "500K-1M": (500001, 1000000),
        "1M–5M": (1000001, 5000000),
        "1M-5M": (1000001, 5000000),
        "5M–25M": (5000001, 25000000),
        "5M-25M": (5000001, 25000000),
        "25M–50M": (25000001, 50000000),
        "25M-50M": (25000001, 50000000),
        "50M+": (50000001, 100000000),
    }

    return size_map.get(size_str, (1001, 15000))


def scrape_capitol_trades(limit: int = 50) -> list[ScrapedTrade]:
    """
    Scrape trades from Capitol Trades using Playwright.

    Args:
        limit: Maximum number of trades to return

    Returns:
        List of ScrapedTrade objects
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed - cannot scrape Capitol Trades")
        return []

    logger.info("Scraping Capitol Trades with Playwright...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to trades page
            page.goto('https://www.capitoltrades.com/trades', wait_until='networkidle', timeout=30000)

            # Wait for table to load
            page.wait_for_selector('table tbody tr', timeout=15000)

            # Extract trade data using JavaScript
            raw_trades = page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    const results = [];

                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 8) {
                            // Politician cell
                            const politicianCell = cells[0];
                            const politicianName = politicianCell.querySelector('h2')?.textContent?.trim() || '';
                            const partyInfo = politicianCell.textContent.replace(politicianName, '').trim();

                            // Issuer cell - has company name and ticker
                            const issuerCell = cells[1];
                            const issuerName = issuerCell.querySelector('h3')?.textContent?.trim() || '';
                            // Ticker is in format like "PUK:US" or "N/A"
                            const tickerText = issuerCell.textContent.replace(issuerName, '').trim();
                            const tickerMatch = tickerText.match(/^([A-Z]{1,5}):/);
                            const ticker = tickerMatch ? tickerMatch[1] : null;

                            // Date cells
                            const publishedDate = cells[2].textContent.trim();
                            const tradedDate = cells[3].textContent.trim();

                            // Transaction type
                            const txType = cells[6].textContent.trim().toLowerCase().replace('*', '');

                            // Size
                            const size = cells[7].textContent.trim();

                            results.push({
                                politician: politicianName,
                                partyInfo: partyInfo,
                                issuer: issuerName,
                                ticker: ticker,
                                publishedDate: publishedDate,
                                tradedDate: tradedDate,
                                type: txType,
                                size: size
                            });
                        }
                    });

                    return results;
                }
            """)

            browser.close()

            # Convert to ScrapedTrade objects
            trades = []
            for item in raw_trades[:limit]:
                party, chamber, state = _parse_party_info(item.get('partyInfo', ''))
                published_date = _parse_date(item.get('publishedDate', ''))
                traded_date = _parse_date(item.get('tradedDate', ''))
                size_str = item.get('size', '1K–15K')
                amount_range = _parse_amount_range(size_str)

                trade = ScrapedTrade(
                    politician=item.get('politician', 'Unknown'),
                    party=party,
                    chamber=chamber,
                    state=state,
                    issuer=item.get('issuer', ''),
                    ticker=item.get('ticker'),
                    transaction_type=item.get('type', 'buy'),
                    published_date=published_date,
                    traded_date=traded_date,
                    size=size_str,
                    amount_range=amount_range,
                )
                trades.append(trade)

            logger.info(f"Scraped {len(trades)} trades from Capitol Trades")
            return trades

    except Exception as e:
        logger.warning(f"Capitol Trades scraper failed: {e}")
        return []


def scraped_to_congress_format(trade: ScrapedTrade) -> dict:
    """Convert ScrapedTrade to format matching the Congress adapter's expected input."""
    return {
        "representative": trade.politician,
        "party": trade.party,
        "district": trade.state,
        "ticker": trade.ticker or "",
        "type": "purchase" if trade.transaction_type == "buy" else "sale",
        "amount": trade.size,
        "disclosure_date": trade.published_date.strftime("%m/%d/%Y") if trade.published_date else "",
        "transaction_date": trade.traded_date.strftime("%Y-%m-%d") if trade.traded_date else "",
        "asset_description": trade.issuer,
    }


if __name__ == "__main__":
    # Test the scraper
    logging.basicConfig(level=logging.DEBUG)
    trades = scrape_capitol_trades(limit=10)
    print(f"\nScraped {len(trades)} trades:\n")
    for t in trades:
        ticker_display = t.ticker or "(no ticker)"
        print(f"  {t.politician} ({t.party}-{t.state}): {t.transaction_type} {ticker_display} - {t.size}")
        print(f"    Issuer: {t.issuer}")
        print(f"    Dates: traded {t.traded_date}, published {t.published_date}")
        print()
