import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from oracle.data import MarketDataFetcher

@patch('yfinance.download')
def test_fetch_history_success(mock_download):
    # Setup mock return value
    mock_df = pd.DataFrame({'Close': [100, 101, 102]})
    mock_download.return_value = mock_df

    fetcher = MarketDataFetcher(['AAPL'])
    data = fetcher.fetch_history()

    assert 'AAPL' in data
    assert not data['AAPL'].empty
    mock_download.assert_called_once()

@patch('yfinance.download')
def test_fetch_history_empty(mock_download):
    # Setup mock to return empty DF
    mock_download.return_value = pd.DataFrame()

    fetcher = MarketDataFetcher(['INVALID'])
    data = fetcher.fetch_history()

    assert 'INVALID' not in data

@patch('yfinance.download')
def test_fetch_history_exception(mock_download):
    # Setup mock to raise exception
    mock_download.side_effect = Exception("Network Error")

    fetcher = MarketDataFetcher(['FAIL'])
    data = fetcher.fetch_history()

    assert 'FAIL' not in data
    # Should handle exception gracefully without crashing
