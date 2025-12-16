import pandas as pd
import pytest
from oracle.analysis import TechnicalAnalyst

@pytest.fixture
def sample_data():
    # Create a dummy DataFrame suitable for technical analysis
    dates = pd.date_range(start="2024-01-01", periods=100)
    data = {
        'Close': [100 + i for i in range(100)],
        'High': [105 + i for i in range(100)],
        'Low': [95 + i for i in range(100)],
        'Open': [100 + i for i in range(100)],
        'Volume': [1000 for _ in range(100)]
    }
    df = pd.DataFrame(data, index=dates)
    return {'TEST_TICKER': df}

def test_process_adds_indicators(sample_data):
    analyst = TechnicalAnalyst()
    processed = analyst.process(sample_data)

    assert 'TEST_TICKER' in processed
    df = processed['TEST_TICKER']

    assert 'RSI' in df.columns
    assert 'EMA_50' in df.columns
    assert 'EMA_200' in df.columns

def test_process_skips_insufficient_data():
    analyst = TechnicalAnalyst()
    # Create small dataframe
    df = pd.DataFrame({'Close': range(10)})
    data = {'SMALL': df}

    processed = analyst.process(data)
    assert 'SMALL' not in processed

def test_process_handles_case_insensitive_columns():
    analyst = TechnicalAnalyst()
    dates = pd.date_range(start="2024-01-01", periods=100)
    df = pd.DataFrame({'close': range(100)}, index=dates)
    data = {'LOWERCASE': df}

    processed = analyst.process(data)
    assert 'LOWERCASE' in processed
    assert 'RSI' in processed['LOWERCASE'].columns # Should still add RSI

def test_summarize_last_state(sample_data):
    analyst = TechnicalAnalyst()
    processed = analyst.process(sample_data)
    summary = analyst.summarize_last_state(processed)

    assert "--- TEST_TICKER ---" in summary
    assert "Price:" in summary
    assert "RSI (14):" in summary
    assert "Trend (vs EMA200):" in summary
