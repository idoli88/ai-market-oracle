import pytest
from datetime import datetime, timedelta
from oracle.analysis import AnalysisGate
from oracle.config import settings

# Mock Data
mock_snapshot_empty = None
mock_snapshot_old = {
    "last_price": 100,
    "last_rsi": 50,
    "last_ema_short": 100,
    "last_trigger_at": (datetime.now() - timedelta(hours=5)).isoformat() # Processed string
}

mock_snapshot_recent = {
    "last_price": 100,
    "last_rsi": 50,
    "last_trigger_at": (datetime.now() - timedelta(minutes=10)).isoformat()
}

def test_first_run():
    current = {
        "current_price": 100,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, None)
    assert should is True
    assert reason == "FIRST_RUN"

def test_cooldown_active():
    current = {
        "current_price": 200,
        "rsi": 90,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_recent)
    assert should is False
    assert reason is None

def test_cooldown_expired_but_no_change():
    current = {
        "current_price": 100, # No change
        "rsi": 50,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_old)
    assert should is False

def test_price_change_trigger():
    # 1.2% threshold default
    current = {
        "current_price": 102, # 2% change
        "rsi": 50,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_old)
    assert should is True
    assert "Price Change" in reason

def test_rsi_trigger():
    current = {
        "current_price": 100,
        "rsi": 80,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_old)
    assert should is True
    assert "RSI Overbought" in reason

def test_rsi_delta_trigger():
    # Last RSI 50. Delta Trigger 10.
    current = {
        "current_price": 100,
        "rsi": 65,
        "ema_short": 100,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_old)
    assert should is True
    assert "RSI Delta" in reason

def test_volume_spike_trigger():
    # Multiplier 2.0.
    current = {
        "current_price": 100,
        "rsi": 50,
        "current_volume": 500,
        "volume_sma": 200, # 500 > 400
        "ema_short": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, mock_snapshot_old)
    assert should is True
    assert "Volume Spike" in reason

def test_ema_cross_bullish():
    # Snapshot: Price 100, EMA 100. (Neutral)
    # Actually logic: Last Price < Last EMA AND Curr Price > Curr EMA.
    # mock_snapshot_old has Last Price 100, Last EMA 100. 100 < 100 is False.
    # Let's make snapshot bearish first.
    bear_snapshot = {
        "last_price": 90,
        "last_ema_short": 100, # Price below EMA
        "last_trigger_at": (datetime.now() - timedelta(hours=5)).isoformat()
    }

    current = {
        "current_price": 105,
        "ema_short": 100, # Crossed above
        "rsi": 50,
        "current_volume": 100,
        "volume_sma": 100
    }
    should, reason = AnalysisGate.should_trigger_llm("AAPL", current, bear_snapshot)
    assert should is True
    assert "Bullish EMA50 Cross" in reason
