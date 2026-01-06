"""
SEC EDGAR 8-K Filings Adapter.

Fetches material event disclosures (8-K filings) from SEC EDGAR.
8-K filings report unscheduled material events including:
- Earnings announcements
- Mergers and acquisitions
- Management changes
- Bankruptcy
- Asset acquisitions/dispositions
- Credit rating changes

Source: https://www.sec.gov/cgi-bin/browse-edgar
API: https://data.sec.gov/

Free API, no key required. User-Agent header with contact info required.
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

from domain import Observation, Category
from ports import FetchError, ParseError
from config import get_settings

from .base import BaseAdapter

logger = logging.getLogger(__name__)


# 8-K form item codes and descriptions
# https://www.sec.gov/files/form8-k.pdf
FORM_8K_ITEMS = {
    "1.01": "Entry into Material Definitive Agreement",
    "1.02": "Termination of Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety - Reporting of Shutdowns and Patterns of Violations",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy Listing Rule",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure/Election of Directors or Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws",
    "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
    "5.05": "Amendments to Registrant's Code of Ethics",
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}

# High-priority 8-K items (material events)
HIGH_PRIORITY_ITEMS = {
    "1.03",  # Bankruptcy
    "2.01",  # M&A
    "2.02",  # Earnings
    "5.01",  # Change of control
    "5.02",  # Management changes
}


@dataclass
class Filing8K:
    """Parsed 8-K filing data."""
    accession_number: str
    company_name: str
    cik: str
    ticker: str | None
    filing_date: datetime
    description: str
    items: list[str]  # Item codes like "2.02", "5.02"
    url: str


class SECAdapter(BaseAdapter):
    """
    SEC EDGAR 8-K filing adapter.

    Fetches recent 8-K filings (material event disclosures) from SEC EDGAR.
    """

    RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    COMPANY_URL = "https://data.sec.gov/submissions"

    @property
    def source_name(self) -> str:
        return "sec_8k"

    @property
    def category(self) -> Category:
        return Category.NEWS

    @property
    def reliability(self) -> float:
        return 0.98  # Official SEC filings, very high reliability

    def _get_sec_headers(self) -> dict[str, str]:
        """
        Get headers for SEC EDGAR API requests.

        SEC requires User-Agent header with contact info.
        """
        settings = get_settings()
        # SEC requires User-Agent with contact info
        user_agent = settings.user_agent
        if "fintel" not in user_agent.lower():
            # Ensure we have identifiable User-Agent for SEC
            user_agent = "Fintel/1.0 (Investment Analysis Tool; admin@fintel.app)"

        return {
            "User-Agent": user_agent,
            "Accept": "application/xml",
        }

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """
        Fetch recent 8-K filings.

        Args:
            limit: Maximum number of filings to return (default 50)
            ticker: Optional ticker to filter by
            start: Optional start index for pagination (default 0)

        Returns:
            List of Observations containing 8-K filing data
        """
        limit = kwargs.get("limit", 50)
        ticker = kwargs.get("ticker", None)
        start = kwargs.get("start", 0)

        if ticker:
            return self._fetch_by_ticker(ticker, limit)
        else:
            return self._fetch_recent(limit, start)

    def _fetch_recent(self, limit: int, start: int = 0) -> list[Observation]:
        """Fetch recent 8-K filings from RSS feed."""
        # SEC RSS feed for recent 8-K filings
        url = f"{self.RSS_URL}?action=getcurrent&type=8-K&output=atom&start={start}&count={limit}"

        try:
            xml_content = self._http_get_text(url, headers=self._get_sec_headers())
        except Exception as e:
            raise FetchError(
                source=self.source_name,
                reason=f"Failed to fetch SEC RSS feed: {e}",
                url=url,
            )

        # Parse Atom feed
        filings = self._parse_atom_feed(xml_content)

        if not filings:
            logger.warning("No 8-K filings found in RSS feed")
            return []

        # Convert to observations
        observations = []
        for filing in filings[:limit]:
            obs = self._filing_to_observation(filing)
            observations.append(obs)

        return observations

    def _fetch_by_ticker(self, ticker: str, limit: int) -> list[Observation]:
        """Fetch recent 8-K filings for a specific ticker."""
        ticker = self._validate_ticker(ticker)

        # First, we need to get the CIK for this ticker
        # SEC doesn't have a direct ticker->CIK API, so we use the company tickers JSON
        cik = self._ticker_to_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for ticker {ticker}")
            return []

        # Fetch company filings
        url = f"{self.COMPANY_URL}/CIK{cik.zfill(10)}.json"

        try:
            data = self._http_get_json(url, headers=self._get_sec_headers())
        except Exception as e:
            raise FetchError(
                source=self.source_name,
                reason=f"Failed to fetch filings for {ticker}: {e}",
                url=url,
            )

        # Extract 8-K filings from recent filings
        filings = self._parse_company_filings(data, ticker, limit)

        # Convert to observations
        observations = []
        for filing in filings:
            obs = self._filing_to_observation(filing)
            observations.append(obs)

        return observations

    def _ticker_to_cik(self, ticker: str) -> str | None:
        """
        Convert ticker symbol to CIK.

        Uses SEC's company tickers JSON endpoint.
        """
        # SEC provides a company tickers mapping
        url = "https://www.sec.gov/files/company_tickers.json"

        try:
            data = self._http_get_json(url, headers=self._get_sec_headers())
        except Exception as e:
            logger.warning(f"Failed to fetch company tickers: {e}")
            return None

        # Search for ticker in the data
        ticker = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker:
                cik = str(entry.get("cik_str", ""))
                return cik

        return None

    def _parse_atom_feed(self, xml_content: str) -> list[Filing8K]:
        """Parse SEC Atom feed XML."""
        filings = []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ParseError(
                source=self.source_name,
                format_type="xml",
                reason=f"Failed to parse Atom feed: {e}",
                raw_content=xml_content[:500],
            )

        # Atom namespace
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            try:
                title = entry.findtext("atom:title", "", ns).strip()
                link_elem = entry.find("atom:link", ns)
                link = link_elem.get("href", "") if link_elem is not None else ""
                updated = entry.findtext("atom:updated", "", ns)
                summary = entry.findtext("atom:summary", "", ns).strip()

                # Parse title: "8-K - COMPANY NAME (CIK: 0001234567)"
                company_match = re.search(r"^8-K - (.+?) \(", title)
                cik_match = re.search(r"CIK: (\d+)", title)

                company_name = company_match.group(1) if company_match else ""
                cik = cik_match.group(1).lstrip("0") if cik_match else ""

                # Parse filing date
                filing_date = parsedate_to_datetime(updated) if updated else datetime.now()

                # Extract accession number from link
                accession_match = re.search(r"/(\d{10}-\d{2}-\d{6})", link)
                accession = accession_match.group(1) if accession_match else ""

                # Extract item numbers from summary
                items = self._extract_items(summary)

                if company_name and accession:
                    filing = Filing8K(
                        accession_number=accession,
                        company_name=company_name,
                        cik=cik,
                        ticker=None,  # Not provided in RSS feed
                        filing_date=filing_date,
                        description=summary[:500] if summary else "",
                        items=items,
                        url=link,
                    )
                    filings.append(filing)

            except Exception as e:
                logger.debug(f"Error parsing feed entry: {e}")
                continue

        return filings

    def _parse_company_filings(
        self,
        data: dict,
        ticker: str,
        limit: int
    ) -> list[Filing8K]:
        """Parse company filings JSON data for 8-K forms."""
        filings = []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        descriptions = recent.get("primaryDocDescription", [])

        company_name = data.get("name", "")
        cik = str(data.get("cik", ""))

        for i, form in enumerate(forms):
            if len(filings) >= limit:
                break

            # Only process 8-K filings (not amendments)
            if form != "8-K":
                continue

            try:
                accession = accessions[i] if i < len(accessions) else ""
                filing_date_str = dates[i] if i < len(dates) else ""
                description = descriptions[i] if i < len(descriptions) else ""

                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                # Build filing URL
                accession_formatted = accession.replace("-", "")
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_formatted}/{accession}-index.htm"

                # Extract item codes from description
                items = self._extract_items(description)

                filing = Filing8K(
                    accession_number=accession,
                    company_name=company_name,
                    cik=cik,
                    ticker=ticker,
                    filing_date=filing_date,
                    description=description,
                    items=items,
                    url=url,
                )
                filings.append(filing)

            except Exception as e:
                logger.debug(f"Error parsing filing at index {i}: {e}")
                continue

        return filings

    def _extract_items(self, text: str) -> list[str]:
        """
        Extract 8-K item codes from description text.

        Example: "Item 2.02, Item 9.01" -> ["2.02", "9.01"]
        """
        items = []

        # Pattern: "Item X.YY" or "Items X.YY"
        pattern = r"Item[s]?\s+(\d+\.\d{2})"
        matches = re.findall(pattern, text, re.IGNORECASE)

        for match in matches:
            if match in FORM_8K_ITEMS:
                items.append(match)

        return items

    def _filing_to_observation(self, filing: Filing8K) -> Observation:
        """Convert 8-K filing to observation."""
        # Build title
        items_desc = ", ".join(
            FORM_8K_ITEMS.get(item, f"Item {item}")
            for item in filing.items
        ) if filing.items else "Material Event"

        title = f"{filing.company_name}: {items_desc}"

        # Determine if high priority
        is_high_priority = any(item in HIGH_PRIORITY_ITEMS for item in filing.items)

        # Build observation data
        data = {
            "title": title,
            "url": filing.url,
            "source": "SEC EDGAR",
            "description": filing.description,
            "accession_number": filing.accession_number,
            "company_name": filing.company_name,
            "cik": filing.cik,
            "form_type": "8-K",
            "items": filing.items,
            "item_descriptions": [
                FORM_8K_ITEMS.get(item, f"Item {item}")
                for item in filing.items
            ],
            "is_high_priority": is_high_priority,
        }

        return Observation(
            source=self.source_name,
            timestamp=filing.filing_date,
            category=Category.NEWS,
            data=data,
            ticker=filing.ticker,
            reliability=self.reliability,
        )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_recent_filings(self, limit: int = 50) -> list[Observation]:
        """Get recent 8-K filings across all companies."""
        return self.fetch(limit=limit)

    def get_filings_for_ticker(self, ticker: str, limit: int = 20) -> list[Observation]:
        """Get recent 8-K filings for a specific ticker."""
        return self.fetch(ticker=ticker, limit=limit)

    def get_earnings_announcements(self, limit: int = 50) -> list[Observation]:
        """
        Get recent earnings announcements.

        Filters for Item 2.02 (Results of Operations and Financial Condition).
        """
        all_filings = self.fetch(limit=limit * 2)  # Fetch extra to filter

        earnings = [
            obs for obs in all_filings
            if "2.02" in obs.data.get("items", [])
        ]

        return earnings[:limit]

    def get_management_changes(self, limit: int = 50) -> list[Observation]:
        """
        Get recent management changes.

        Filters for Item 5.02 (Departure/Election of Directors or Officers).
        """
        all_filings = self.fetch(limit=limit * 2)

        mgmt_changes = [
            obs for obs in all_filings
            if "5.02" in obs.data.get("items", [])
        ]

        return mgmt_changes[:limit]

    def get_mergers_acquisitions(self, limit: int = 50) -> list[Observation]:
        """
        Get recent M&A activity.

        Filters for Item 2.01 (Completion of Acquisition or Disposition of Assets).
        """
        all_filings = self.fetch(limit=limit * 2)

        ma_filings = [
            obs for obs in all_filings
            if "2.01" in obs.data.get("items", [])
        ]

        return ma_filings[:limit]
