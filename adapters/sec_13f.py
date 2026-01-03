"""
SEC EDGAR 13F Adapter.

Fetches institutional holdings from SEC 13F filings.
13F filings are quarterly reports filed by institutional investment managers
with over $100M in AUM, disclosing their US equity holdings.

Source: https://www.sec.gov/cgi-bin/browse-edgar

Free API, no key required. User-Agent header required.
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

from domain import Observation, Category
from ports import FetchError, ParseError
from db import get_db, HedgeFund, HedgeFundHolding

from .base import BaseAdapter

logger = logging.getLogger(__name__)


# Top hedge funds to track (CIK, name, manager, style)
# CIKs without leading zeros - will be padded when needed
TOP_HEDGE_FUNDS = [
    ("1067983", "Berkshire Hathaway", "Warren Buffett", "value"),
    ("1336528", "Bridgewater Associates", "Ray Dalio", "macro"),
    ("1649339", "Pershing Square Capital", "Bill Ackman", "activist"),
    ("1029160", "Renaissance Technologies", "Jim Simons", "quant"),
    ("1056831", "Citadel Advisors", "Ken Griffin", "quant"),
    ("1037389", "Soros Fund Management", "George Soros", "macro"),
    ("1350694", "Appaloosa Management", "David Tepper", "value"),
    ("1061165", "Elliott Investment", "Paul Singer", "activist"),
    ("1167483", "Third Point", "Dan Loeb", "activist"),
    ("1591086", "Baupost Group", "Seth Klarman", "value"),
    ("1040273", "Viking Global Investors", "Andreas Halvorsen", "growth"),
    ("1061768", "Tiger Global Management", "Chase Coleman", "growth"),
    ("902664", "DE Shaw & Co", "David Shaw", "quant"),
    ("1484150", "Coatue Management", "Philippe Laffont", "tech"),
    ("1159159", "Lone Pine Capital", "Stephen Mandel", "growth"),
]

# CUSIP to ticker mapping cache (populated during parsing)
CUSIP_TICKER_MAP: dict[str, str] = {}

# Common CUSIP mappings for major stocks
CUSIP_TICKERS = {
    "037833100": "AAPL",  # Apple
    "594918104": "MSFT",  # Microsoft
    "88160R101": "TSLA",  # Tesla
    "023135106": "AMZN",  # Amazon
    "02079K107": "GOOG",  # Alphabet Class C
    "02079K305": "GOOGL", # Alphabet Class A
    "30303M102": "META",  # Meta Platforms
    "67066G104": "NVDA",  # NVIDIA
    "92826C839": "V",     # Visa
    "478160104": "JNJ",   # Johnson & Johnson
    "46625H100": "JPM",   # JPMorgan Chase
    "74762E102": "QCOM",  # Qualcomm
    "172967424": "C",     # Citigroup
    "060505104": "BAC",   # Bank of America
    "92343V104": "VZ",    # Verizon
    "031162100": "AMGN",  # Amgen
    "254687106": "DIS",   # Disney
    "20030N101": "CMCSA", # Comcast
    "88579Y101": "MMM",   # 3M
    "375558103": "GM",    # General Motors
    "191216100": "KO",    # Coca-Cola
    "713448108": "PEP",   # PepsiCo
    "742718109": "PG",    # Procter & Gamble
    "931142103": "WMT",   # Walmart
    "369604103": "GE",    # General Electric
    "084670702": "BRK.B", # Berkshire Hathaway B
    "02005N100": "ALLY",  # Ally Financial
    "03027X100": "AXP",   # American Express
    "17275R102": "C",     # Citigroup
    "126650100": "CVX",   # Chevron
    "166764100": "CVX",   # Chevron (alt)
    "20825C104": "COP",   # ConocoPhillips
}


@dataclass
class Filing13F:
    """Parsed 13F filing metadata."""
    accession_number: str
    filing_date: date
    report_date: date  # Quarter end date
    primary_doc: str
    infotable_file: str


@dataclass
class Holding13F:
    """Single holding from 13F filing."""
    cusip: str
    issuer_name: str
    shares: int
    value: int  # Value in dollars (as reported, often in thousands)
    ticker: str = ""


class SEC13FAdapter(BaseAdapter):
    """
    SEC EDGAR 13F filing adapter.

    Fetches institutional holdings from quarterly 13F filings.
    """

    BASE_URL = "https://data.sec.gov/submissions"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

    @property
    def source_name(self) -> str:
        return "sec_13f"

    @property
    def category(self) -> Category:
        return Category.SENTIMENT

    @property
    def reliability(self) -> float:
        return 0.95  # Official SEC filings, very high reliability

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """
        Fetch 13F holdings for tracked hedge funds.

        Args:
            limit: Maximum number of holdings to return (default 100)
            fund_cik: Optional specific fund CIK to fetch

        Returns:
            List of Observations containing hedge fund holdings
        """
        limit = kwargs.get("limit", 100)
        fund_cik = kwargs.get("fund_cik", None)

        logger.info(f"Fetching 13F holdings (limit={limit})")

        db = get_db()
        all_observations = []

        # Get funds to process
        if fund_cik:
            # Look up fund info from our list
            fund_info = next(
                ((c, n, m, s) for c, n, m, s in TOP_HEDGE_FUNDS if c == fund_cik),
                (fund_cik, f"Fund CIK {fund_cik}", "Unknown", "")
            )
            funds = [fund_info]
        else:
            funds = TOP_HEDGE_FUNDS

        for cik, name, manager, style in funds:
            try:
                # Ensure fund exists in database
                fund = self._ensure_fund_exists(cik, name, manager, style)
                if not fund:
                    continue

                # Get latest 13F filing
                filing = self._get_latest_13f_filing(cik)
                if not filing:
                    logger.warning(f"No 13F filing found for {name} (CIK: {cik})")
                    continue

                # Check if we already have this filing
                if fund.last_filing_date == filing.filing_date:
                    logger.debug(f"Already have latest filing for {name}")
                    # Load from database instead
                    holdings = db.get_holdings_for_fund(fund.id, limit=limit)
                    for h in holdings:
                        obs = self._holding_to_observation(fund, h)
                        all_observations.append(obs)
                    continue

                # Fetch and parse holdings
                holdings = self._fetch_holdings(cik, filing)
                if not holdings:
                    continue

                logger.info(f"Found {len(holdings)} holdings for {name}")

                # Store holdings in database
                stored = self._store_holdings(fund, filing, holdings)

                # Update fund's last filing date
                fund.last_filing_date = filing.filing_date
                db.upsert_hedge_fund(fund)

                # Convert to observations
                for db_holding in stored[:limit]:
                    obs = self._holding_to_observation(fund, db_holding)
                    all_observations.append(obs)

            except Exception as e:
                logger.warning(f"Failed to fetch 13F for {name}: {e}")
                continue

        return all_observations[:limit]

    def _ensure_fund_exists(
        self, cik: str, name: str, manager: str, style: str
    ) -> Optional[HedgeFund]:
        """Ensure fund exists in database, create if not."""
        db = get_db()

        # Try to get existing fund
        fund = db.get_hedge_fund_by_cik(cik)
        if fund:
            return fund

        # Create new fund record
        fund_id = hashlib.md5(f"fund:{cik}".encode()).hexdigest()[:12]
        fund = HedgeFund(
            id=fund_id,
            name=name,
            cik=cik.zfill(10),
            manager=manager,
            style=style,
            is_active=True,
        )
        db.upsert_hedge_fund(fund)
        logger.info(f"Created fund record for {name}")
        return fund

    def _get_latest_13f_filing(self, cik: str) -> Optional[Filing13F]:
        """Get the latest 13F-HR filing for a fund."""
        padded_cik = cik.zfill(10)
        url = f"{self.BASE_URL}/CIK{padded_cik}.json"

        try:
            data = self._http_get_json(url)
        except Exception as e:
            logger.warning(f"Failed to fetch company info for CIK {cik}: {e}")
            return None

        # Find 13F-HR filings
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        primary_docs = filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "13F-HR":  # Skip amendments (13F-HR/A)
                try:
                    filing_date = datetime.strptime(dates[i], "%Y-%m-%d").date()
                    accession = accessions[i]

                    # Calculate report date (quarter end, typically 45 days before filing)
                    # Q1 ends Mar 31, Q2 ends Jun 30, Q3 ends Sep 30, Q4 ends Dec 31
                    report_date = self._calculate_report_date(filing_date)

                    return Filing13F(
                        accession_number=accession,
                        filing_date=filing_date,
                        report_date=report_date,
                        primary_doc=primary_docs[i] if i < len(primary_docs) else "",
                        infotable_file="",  # Will find in filing index
                    )
                except (IndexError, ValueError) as e:
                    logger.debug(f"Error parsing filing: {e}")
                    continue

        return None

    def _calculate_report_date(self, filing_date: date) -> date:
        """Calculate the quarter end date for a 13F filing."""
        # 13F filings are due 45 days after quarter end
        # So filing in Feb = Q4 (Dec 31), May = Q1 (Mar 31), etc.
        month = filing_date.month

        if month in [1, 2]:  # Q4 report
            return date(filing_date.year - 1, 12, 31)
        elif month in [3, 4, 5]:  # Q1 report (filed in May)
            return date(filing_date.year, 3, 31)
        elif month in [6, 7, 8]:  # Q2 report (filed in Aug)
            return date(filing_date.year, 6, 30)
        elif month in [9, 10, 11]:  # Q3 report (filed in Nov)
            return date(filing_date.year, 9, 30)
        else:  # month == 12, Q3 or Q4
            return date(filing_date.year, 9, 30)

    def _fetch_holdings(self, cik: str, filing: Filing13F) -> list[Holding13F]:
        """Fetch and parse holdings from a 13F filing."""
        # First, get the filing index to find the infotable file
        accession_formatted = filing.accession_number.replace("-", "")
        index_url = f"{self.ARCHIVES_URL}/{cik}/{accession_formatted}"

        # Try common infotable file names
        infotable_names = [
            "infotable.xml",
            f"{accession_formatted[-6:]}.xml",  # Last 6 digits
        ]

        # Also check the filing index for XML files
        try:
            index_html = self._http_get_text(f"{index_url}/{filing.accession_number}-index.htm")
            # Find XML files that might be the infotable
            xml_matches = re.findall(r'href="([^"]+\.xml)"', index_html)
            for xml in xml_matches:
                if "primary" not in xml.lower():
                    infotable_names.insert(0, xml.split("/")[-1])
        except:
            pass

        # Try each possible infotable file
        xml_content = None
        for filename in infotable_names:
            try:
                url = f"{index_url}/{filename}"
                xml_content = self._http_get_text(url)
                if "<informationTable" in xml_content or "<infoTable" in xml_content:
                    break
            except:
                continue

        if not xml_content:
            logger.warning(f"Could not find infotable for filing {filing.accession_number}")
            return []

        # Parse the XML
        return self._parse_infotable(xml_content)

    def _parse_infotable(self, xml_content: str) -> list[Holding13F]:
        """Parse 13F infotable XML."""
        holdings = []

        try:
            # Remove namespace for easier parsing
            xml_content = re.sub(r' xmlns="[^"]+"', '', xml_content)
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse infotable XML: {e}")
            return []

        # Aggregate holdings by CUSIP (may have multiple entries)
        cusip_holdings: dict[str, Holding13F] = {}

        for info_table in root.findall(".//infoTable"):
            try:
                cusip = info_table.findtext("cusip", "").strip()
                if not cusip:
                    continue

                issuer = info_table.findtext("nameOfIssuer", "").strip()
                value = int(info_table.findtext("value", "0") or "0")
                shares_elem = info_table.find(".//sshPrnamt")
                shares = int(shares_elem.text or "0") if shares_elem is not None else 0

                # Look up ticker from CUSIP
                ticker = self._cusip_to_ticker(cusip, issuer)

                if cusip in cusip_holdings:
                    # Aggregate with existing holding
                    existing = cusip_holdings[cusip]
                    existing.shares += shares
                    existing.value += value
                else:
                    cusip_holdings[cusip] = Holding13F(
                        cusip=cusip,
                        issuer_name=issuer,
                        shares=shares,
                        value=value,  # Value is already in dollars
                        ticker=ticker,
                    )

            except Exception as e:
                logger.debug(f"Error parsing infoTable: {e}")
                continue

        return list(cusip_holdings.values())

    def _cusip_to_ticker(self, cusip: str, issuer_name: str) -> str:
        """Convert CUSIP to ticker symbol."""
        # Check static mapping first
        if cusip in CUSIP_TICKERS:
            return CUSIP_TICKERS[cusip]

        # Check cache
        if cusip in CUSIP_TICKER_MAP:
            return CUSIP_TICKER_MAP[cusip]

        # Try to derive ticker from issuer name
        ticker = self._derive_ticker_from_name(issuer_name)
        if ticker:
            CUSIP_TICKER_MAP[cusip] = ticker
            return ticker

        # Return empty string if we can't determine ticker
        return ""

    def _derive_ticker_from_name(self, name: str) -> str:
        """Try to derive ticker from company name."""
        name = name.upper().strip()

        # Common patterns
        patterns = [
            (r"APPLE\s*INC", "AAPL"),
            (r"MICROSOFT", "MSFT"),
            (r"AMAZON", "AMZN"),
            (r"ALPHABET", "GOOGL"),
            (r"GOOGLE", "GOOGL"),
            (r"META\s*PLATFORM", "META"),
            (r"FACEBOOK", "META"),
            (r"NVIDIA", "NVDA"),
            (r"TESLA", "TSLA"),
            (r"BERKSHIRE", "BRK.B"),
            (r"JPMORGAN|JP\s*MORGAN", "JPM"),
            (r"BANK\s*OF?\s*AMER", "BAC"),
            (r"WELLS\s*FARGO", "WFC"),
            (r"JOHNSON\s*&?\s*JOHNSON", "JNJ"),
            (r"PROCTER\s*&?\s*GAMBLE|P\s*&\s*G", "PG"),
            (r"COCA\s*COLA", "KO"),
            (r"PEPSICO", "PEP"),
            (r"WALMART", "WMT"),
            (r"EXXON", "XOM"),
            (r"CHEVRON", "CVX"),
            (r"VISA\s+INC", "V"),
            (r"MASTERCARD", "MA"),
            (r"AMERICAN\s*EXPRESS", "AXP"),
            (r"DISNEY", "DIS"),
            (r"VERIZON", "VZ"),
            (r"AT\s*&\s*T", "T"),
            (r"INTEL\s+CORP", "INTC"),
            (r"CISCO", "CSCO"),
            (r"ORACLE", "ORCL"),
            (r"SALESFORCE", "CRM"),
            (r"ADOBE", "ADBE"),
            (r"PAYPAL", "PYPL"),
            (r"NETFLIX", "NFLX"),
            (r"UBER", "UBER"),
            (r"AIRBNB", "ABNB"),
            (r"SPOTIFY", "SPOT"),
            (r"SNOWFLAKE", "SNOW"),
            (r"PALANTIR", "PLTR"),
            (r"COINBASE", "COIN"),
            (r"ROBINHOOD", "HOOD"),
            (r"ALLY\s*FINL?", "ALLY"),
        ]

        for pattern, ticker in patterns:
            if re.search(pattern, name):
                return ticker

        return ""

    def _store_holdings(
        self,
        fund: HedgeFund,
        filing: Filing13F,
        holdings: list[Holding13F]
    ) -> list[HedgeFundHolding]:
        """Store holdings in database and calculate changes from previous quarter."""
        db = get_db()
        stored = []

        # Calculate total portfolio value for percentage calculation
        total_value = sum(h.value for h in holdings)

        # Get previous quarter's holdings for comparison
        prev_holdings_map: dict[str, HedgeFundHolding] = {}
        prev_holdings = db.get_holdings_for_fund(
            fund.id,
            report_date=filing.report_date - timedelta(days=95),  # Previous quarter
            limit=1000
        )
        for h in prev_holdings:
            prev_holdings_map[h.cusip] = h

        # Track tickers in this filing to detect sold positions
        current_cusips = set()

        # Sort by value for ranking
        holdings.sort(key=lambda h: h.value, reverse=True)

        for rank, holding in enumerate(holdings, 1):
            current_cusips.add(holding.cusip)

            # Generate holding ID
            id_str = f"{fund.id}:{holding.cusip}:{filing.report_date.isoformat()}"
            holding_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

            # Calculate portfolio percentage
            portfolio_pct = (holding.value / total_value * 100) if total_value > 0 else 0

            # Determine action and calculate changes
            prev = prev_holdings_map.get(holding.cusip)
            if prev:
                shares_change = holding.shares - prev.shares
                shares_change_pct = (shares_change / prev.shares * 100) if prev.shares > 0 else 0

                if shares_change > 0:
                    action = "increased"
                elif shares_change < 0:
                    action = "decreased"
                else:
                    action = "hold"
            else:
                action = "new"
                shares_change = holding.shares
                shares_change_pct = None

            db_holding = HedgeFundHolding(
                id=holding_id,
                fund_id=fund.id,
                ticker=holding.ticker,
                cusip=holding.cusip,
                issuer_name=holding.issuer_name,
                shares=holding.shares,
                value=holding.value,
                filing_date=filing.filing_date,
                report_date=filing.report_date,
                prev_shares=prev.shares if prev else None,
                prev_value=prev.value if prev else None,
                shares_change=shares_change,
                shares_change_pct=shares_change_pct,
                action=action,
                portfolio_pct=round(portfolio_pct, 2),
                rank=rank,
            )

            db.upsert_hedge_fund_holding(db_holding)
            stored.append(db_holding)

        # Mark sold positions (in previous quarter but not in current)
        for cusip, prev in prev_holdings_map.items():
            if cusip not in current_cusips:
                # Position was sold
                id_str = f"{fund.id}:{cusip}:{filing.report_date.isoformat()}:sold"
                holding_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

                sold_holding = HedgeFundHolding(
                    id=holding_id,
                    fund_id=fund.id,
                    ticker=prev.ticker,
                    cusip=cusip,
                    issuer_name=prev.issuer_name,
                    shares=0,
                    value=0,
                    filing_date=filing.filing_date,
                    report_date=filing.report_date,
                    prev_shares=prev.shares,
                    prev_value=prev.value,
                    shares_change=-prev.shares,
                    shares_change_pct=-100.0,
                    action="sold",
                    portfolio_pct=0,
                    rank=None,
                )
                db.upsert_hedge_fund_holding(sold_holding)

        logger.info(f"Stored {len(stored)} holdings for {fund.name}")
        return stored

    def _holding_to_observation(
        self,
        fund: HedgeFund,
        holding: HedgeFundHolding
    ) -> Observation:
        """Convert database holding to observation."""
        # Determine direction based on action
        if holding.action in ["new", "increased"]:
            direction = "buy"
        elif holding.action in ["sold", "decreased"]:
            direction = "sell"
        else:
            direction = "hold"

        # Calculate strength based on portfolio percentage and action
        if holding.action == "new":
            strength = min(0.9, 0.5 + (holding.portfolio_pct or 0) / 10)
        elif holding.action == "increased":
            strength = min(0.8, 0.4 + abs(holding.shares_change_pct or 0) / 100)
        elif holding.action == "sold":
            strength = 0.85
        elif holding.action == "decreased":
            strength = min(0.7, 0.3 + abs(holding.shares_change_pct or 0) / 100)
        else:
            strength = 0.3

        # Generate summary
        if holding.action == "new":
            summary = f"{fund.manager} opened new position in {holding.ticker or holding.issuer_name}"
        elif holding.action == "increased":
            pct = f"+{holding.shares_change_pct:.1f}%" if holding.shares_change_pct else ""
            summary = f"{fund.manager} increased {holding.ticker or holding.issuer_name} {pct}"
        elif holding.action == "sold":
            summary = f"{fund.manager} sold entire position in {holding.ticker or holding.issuer_name}"
        elif holding.action == "decreased":
            pct = f"{holding.shares_change_pct:.1f}%" if holding.shares_change_pct else ""
            summary = f"{fund.manager} reduced {holding.ticker or holding.issuer_name} {pct}"
        else:
            summary = f"{fund.manager} holds {holding.ticker or holding.issuer_name}"

        return Observation(
            source=self.source_name,
            timestamp=datetime.combine(holding.filing_date, datetime.min.time()),
            category=Category.SENTIMENT,
            data={
                "id": holding.id,
                "signal_type": "13f",
                "ticker": holding.ticker,
                "direction": direction,
                "strength": round(strength, 2),
                "summary": summary,
                "details": {
                    "fund_name": fund.name,
                    "manager": fund.manager,
                    "style": fund.style,
                    "cusip": holding.cusip,
                    "issuer_name": holding.issuer_name,
                    "shares": holding.shares,
                    "value": holding.value,
                    "portfolio_pct": holding.portfolio_pct,
                    "rank": holding.rank,
                    "action": holding.action,
                    "shares_change": holding.shares_change,
                    "shares_change_pct": holding.shares_change_pct,
                    "filing_date": holding.filing_date.isoformat() if holding.filing_date else None,
                    "report_date": holding.report_date.isoformat() if holding.report_date else None,
                },
            },
            ticker=holding.ticker or None,
            reliability=self.reliability,
        )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_top_holdings(self, fund_cik: str = None, limit: int = 20) -> list[Observation]:
        """Get top holdings for a fund or all tracked funds."""
        return self.fetch(fund_cik=fund_cik, limit=limit)

    def get_new_positions(self, limit: int = 50) -> list[Observation]:
        """Get recently opened positions across all tracked funds."""
        db = get_db()
        holdings = db.get_recent_hedge_fund_activity(action="new", limit=limit)

        observations = []
        for h in holdings:
            fund = db.get_hedge_fund(h.fund_id)
            if fund:
                obs = self._holding_to_observation(fund, h)
                observations.append(obs)

        return observations

    def get_sold_positions(self, limit: int = 50) -> list[Observation]:
        """Get recently sold positions across all tracked funds."""
        db = get_db()
        holdings = db.get_recent_hedge_fund_activity(action="sold", limit=limit)

        observations = []
        for h in holdings:
            fund = db.get_hedge_fund(h.fund_id)
            if fund:
                obs = self._holding_to_observation(fund, h)
                observations.append(obs)

        return observations

    def get_holdings_for_ticker(self, ticker: str) -> list[Observation]:
        """Get all hedge fund holdings for a specific ticker."""
        db = get_db()
        holdings = db.get_holdings_for_ticker(ticker.upper())

        observations = []
        for h in holdings:
            fund = db.get_hedge_fund(h.fund_id)
            if fund:
                obs = self._holding_to_observation(fund, h)
                observations.append(obs)

        return observations

    def refresh_all_funds(self) -> dict:
        """Refresh 13F data for all tracked funds."""
        logger.info("Refreshing 13F data for all tracked funds...")

        results = {
            "funds_processed": 0,
            "holdings_updated": 0,
            "errors": [],
        }

        db = get_db()

        for cik, name, manager, style in TOP_HEDGE_FUNDS:
            try:
                fund = self._ensure_fund_exists(cik, name, manager, style)
                if not fund:
                    continue

                filing = self._get_latest_13f_filing(cik)
                if not filing:
                    results["errors"].append(f"No filing for {name}")
                    continue

                if fund.last_filing_date == filing.filing_date:
                    logger.debug(f"Already have latest filing for {name}")
                    results["funds_processed"] += 1
                    continue

                holdings = self._fetch_holdings(cik, filing)
                if holdings:
                    stored = self._store_holdings(fund, filing, holdings)
                    fund.last_filing_date = filing.filing_date
                    db.upsert_hedge_fund(fund)

                    results["funds_processed"] += 1
                    results["holdings_updated"] += len(stored)
                    logger.info(f"Updated {len(stored)} holdings for {name}")

            except Exception as e:
                results["errors"].append(f"{name}: {str(e)}")
                logger.warning(f"Error processing {name}: {e}")

        return results
