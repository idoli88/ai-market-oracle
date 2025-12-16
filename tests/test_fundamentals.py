import pytest
from unittest.mock import MagicMock, patch
from oracle.fundamentals import SecEdgarProvider
from oracle.database import (
    get_fundamentals,
    update_fundamentals,
    get_filing_checkpoint,
    update_filing_checkpoint,
    init_db
)
import sqlite3
import os
from datetime import datetime, timedelta

# Mock SEC API Responses
MOCK_COMPANY_TICKERS = {
    "0": {"ticker": "AAPL", "cik_str": 320193},
    "1": {"ticker": "MSFT", "cik_str": 789019}
}

MOCK_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-Q"],
            "accessionNumber": ["0000320193-24-000001", "0000320193-24-000002", "0000320193-24-000003"],
            "filingDate": ["2024-01-15", "2024-01-10", "2024-01-05"]
        }
    }
}

MOCK_COMPANY_FACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {"end": "2023-12-31", "val": 385000000000},
                        {"end": "2022-12-31", "val": 365000000000}
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {"end": "2023-12-31", "val": 97000000000}
                    ]
                }
            },
            "EarningsPerShareBasic": {
                "units": {
                    "shares": [
                        {"end": "2023-12-31", "val": 6.15}
                    ]
                }
            }
        }
    }
}

@patch("oracle.fundamentals.requests.get")
def test_get_cik(mock_get):
    """Test CIK lookup for ticker."""
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_COMPANY_TICKERS
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    provider = SecEdgarProvider()
    cik = provider.get_cik("AAPL")

    assert cik == "0000320193"

    # Test cache
    cik2 = provider.get_cik("AAPL")
    assert cik2 == "0000320193"
    assert mock_get.call_count == 1  # Should use cache

@patch("oracle.fundamentals.requests.get")
def test_get_latest_filing(mock_get):
    """Test retrieving latest 10-Q/10-K filing."""
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_SUBMISSIONS
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    provider = SecEdgarProvider()
    filing = provider.get_latest_filing("0000320193")

    assert filing is not None
    assert filing['form'] == "10-K"
    assert filing['accession_number'] == "0000320193-24-000001"

@patch("oracle.fundamentals.requests.get")
def test_extract_kpis(mock_get):
    """Test KPI extraction from companyfacts."""
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_COMPANY_FACTS
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    provider = SecEdgarProvider()
    kpis = provider.extract_kpis("0000320193")

    assert 'revenue' in kpis
    assert kpis['revenue'] == 385.0  # Billions
    assert 'net_income' in kpis
    assert kpis['net_income'] == 97000.0  # Millions
    assert 'eps' in kpis
    assert kpis['eps'] == 6.15

def test_fundamentals_caching():
    """Test fundamentals cache read/write with TTL."""
    test_db = os.path.abspath("/tmp/test_fundamentals.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    with patch("oracle.config.settings.DB_PATH", test_db):
        init_db()

        # 1. Update cache
        test_kpis = {
            "revenue": 385.0,
            "net_income": 97000.0,
            "eps": 6.15
        }
        update_fundamentals("AAPL", test_kpis)

        # 2. Read fresh cache
        cached = get_fundamentals("AAPL", ttl_days=7)
        assert cached is not None
        assert cached['kpis']['revenue'] == 385.0

        # 3. Test TTL expiration
        conn = sqlite3.connect(test_db)
        old_time = (datetime.now() - timedelta(days=8)).isoformat()
        conn.execute("UPDATE fundamentals_cache SET last_updated = ?", (old_time,))
        conn.commit()
        conn.close()

        expired = get_fundamentals("AAPL", ttl_days=7)
        assert expired is None

    if os.path.exists(test_db):
        os.remove(test_db)

def test_filing_checkpoint():
    """Test filing checkpoint tracking."""
    test_db = os.path.abspath("/tmp/test_filing_checkpoint.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    with patch("oracle.config.settings.DB_PATH", test_db):
        init_db()

        # 1. Create checkpoint
        update_filing_checkpoint("AAPL", "0000320193-24-000001", "2024-01-15")

        # 2. Read checkpoint
        checkpoint = get_filing_checkpoint("AAPL")
        assert checkpoint is not None
        assert checkpoint['last_accession_or_id'] == "0000320193-24-000001"
        assert checkpoint['last_filing_date'] == "2024-01-15"

        # 3. Update with new filing
        update_filing_checkpoint("AAPL", "0000320193-24-000002", "2024-02-15")

        checkpoint2 = get_filing_checkpoint("AAPL")
        assert checkpoint2['last_accession_or_id'] == "0000320193-24-000002"

    if os.path.exists(test_db):
        os.remove(test_db)
