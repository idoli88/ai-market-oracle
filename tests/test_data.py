import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from oracle.data_source import MarketData

@patch('yfinance.Ticker')
def test_fetch_history_success(mock_ticker):
    # Setup mock return value
    mock_instance = MagicMock()
    mock_df = pd.DataFrame({'Close': [100, 101, 102]})
    mock_instance.history.return_value = mock_df
    mock_ticker.return_value = mock_instance

    df = MarketData.fetch_price_history('AAPL')

    assert not df.empty
    assert 'Close' in df.columns
    mock_instance.history.assert_called_once()

@patch('yfinance.Ticker')
def test_fetch_history_empty(mock_ticker):
    # Setup mock to return empty DF
    mock_instance = MagicMock()
    mock_instance.history.return_value = pd.DataFrame()
    mock_ticker.return_value = mock_instance

    df = MarketData.fetch_price_history('INVALID')

    assert df.empty

def test_calculate_technicals():
    # Create a dummy DataFrame with enough data
    dates = pd.date_range(start="2023-01-01", periods=250)
    data = {
        'Close': [100 + i for i in range(250)],
        'High': [105 + i for i in range(250)],
        'Low': [95 + i for i in range(250)],
        'Open': [100 + i for i in range(250)],
        'Volume': [1000 for _ in range(250)]
    }
    df = pd.DataFrame(data, index=dates)

    technicals = MarketData.calculate_technicals(df)

    assert technicals
    assert 'rsi' in technicals
    assert 'ema_short' in technicals
    assert 'ema_long' in technicals
    assert technicals['rsi'] is not None

def test_calculate_technicals_insufficient_data():
    dates = pd.date_range(start="2024-01-01", periods=10)
    df = pd.DataFrame({'Close': range(10)}, index=dates)

    technicals = MarketData.calculate_technicals(df)

    assert technicals == {}
