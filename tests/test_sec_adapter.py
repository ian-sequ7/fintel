"""
Tests for SEC EDGAR 8-K adapter.

Basic tests for adapter structure, validation, and parsing.
"""

import pytest
from datetime import datetime
from adapters.sec import SECAdapter, Filing8K, FORM_8K_ITEMS, HIGH_PRIORITY_ITEMS
from domain import Category


class TestSECAdapter:
    """Test cases for SEC 8-K adapter."""

    def test_adapter_properties(self):
        """Test basic adapter properties."""
        adapter = SECAdapter()

        assert adapter.source_name == "sec_8k"
        assert adapter.category == Category.NEWS
        assert adapter.reliability == 0.98

    def test_sec_headers(self):
        """Test SEC-required headers are present."""
        adapter = SECAdapter()
        headers = adapter._get_sec_headers()

        assert "User-Agent" in headers
        assert "Accept" in headers
        assert len(headers["User-Agent"]) > 0

    def test_extract_items(self):
        """Test extraction of 8-K item codes from text."""
        adapter = SECAdapter()

        # Test single item
        text = "Item 2.02 - Results of Operations"
        items = adapter._extract_items(text)
        assert "2.02" in items

        # Test multiple items
        text = "Item 2.02, Item 9.01"
        items = adapter._extract_items(text)
        assert "2.02" in items
        assert "9.01" in items

        # Test case insensitivity
        text = "item 5.02 - Management Changes"
        items = adapter._extract_items(text)
        assert "5.02" in items

        # Test invalid items are ignored
        text = "Item 99.99 - Invalid"
        items = adapter._extract_items(text)
        assert len(items) == 0

    def test_filing_to_observation(self):
        """Test conversion of Filing8K to Observation."""
        adapter = SECAdapter()

        filing = Filing8K(
            accession_number="0001234567-23-000001",
            company_name="Test Company Inc",
            cik="1234567",
            ticker="TEST",
            filing_date=datetime(2024, 1, 15, 10, 30),
            description="Test filing description",
            items=["2.02", "9.01"],
            url="https://www.sec.gov/test",
        )

        obs = adapter._filing_to_observation(filing)

        assert obs.source == "sec_8k"
        assert obs.category == Category.NEWS
        assert obs.ticker == "TEST"
        assert obs.reliability == 0.98
        assert obs.data["company_name"] == "Test Company Inc"
        assert obs.data["form_type"] == "8-K"
        assert "2.02" in obs.data["items"]
        assert "9.01" in obs.data["items"]
        assert len(obs.data["item_descriptions"]) == 2

    def test_high_priority_detection(self):
        """Test high-priority filing detection."""
        adapter = SECAdapter()

        # High priority: Earnings
        filing = Filing8K(
            accession_number="0001234567-23-000001",
            company_name="Test Company",
            cik="1234567",
            ticker="TEST",
            filing_date=datetime.now(),
            description="Earnings announcement",
            items=["2.02"],  # Earnings
            url="https://www.sec.gov/test",
        )

        obs = adapter._filing_to_observation(filing)
        assert obs.data["is_high_priority"] is True

        # Normal priority
        filing_normal = Filing8K(
            accession_number="0001234567-23-000002",
            company_name="Test Company",
            cik="1234567",
            ticker="TEST",
            filing_date=datetime.now(),
            description="General disclosure",
            items=["8.01"],  # Other events
            url="https://www.sec.gov/test",
        )

        obs_normal = adapter._filing_to_observation(filing_normal)
        assert obs_normal.data["is_high_priority"] is False

    def test_ticker_validation(self):
        """Test ticker symbol validation."""
        adapter = SECAdapter()

        # Valid tickers
        assert adapter._validate_ticker("AAPL") == "AAPL"
        assert adapter._validate_ticker("msft") == "MSFT"
        assert adapter._validate_ticker("BRK-B") == "BRK-B"

        # Invalid tickers
        with pytest.raises(Exception):
            adapter._validate_ticker("")

        with pytest.raises(Exception):
            adapter._validate_ticker("TOOLONGTICKER")


class TestFormItems:
    """Test 8-K form item constants."""

    def test_form_items_complete(self):
        """Test that all major 8-K items are defined."""
        # Check key items are present
        assert "2.02" in FORM_8K_ITEMS  # Earnings
        assert "5.02" in FORM_8K_ITEMS  # Management changes
        assert "2.01" in FORM_8K_ITEMS  # M&A
        assert "1.03" in FORM_8K_ITEMS  # Bankruptcy
        assert "9.01" in FORM_8K_ITEMS  # Exhibits

    def test_high_priority_items(self):
        """Test that high-priority items are correctly flagged."""
        assert "2.02" in HIGH_PRIORITY_ITEMS  # Earnings
        assert "5.02" in HIGH_PRIORITY_ITEMS  # Management
        assert "2.01" in HIGH_PRIORITY_ITEMS  # M&A
        assert "1.03" in HIGH_PRIORITY_ITEMS  # Bankruptcy
        assert "8.01" not in HIGH_PRIORITY_ITEMS  # Other events - not high priority


# Integration tests would go here but require live API access
# These would be marked with @pytest.mark.integration and run separately
