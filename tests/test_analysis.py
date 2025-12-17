import pytest
from datetime import datetime, timedelta
from oracle.analysis import AnalysisGate
from oracle.config import settings

@pytest.fixture
def mock_snapshot():
    return {
        "last_price": 100.0,
        "last_rsi": 50.0,
        "last_ema_short": 100.0,
        "last_ema_long": 90.0,
        "last_run_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        "last_trigger_at": (datetime.now() - timedelta(hours=24)).isoformat() # > cooldown
    }

def test_gate_first_run():
    # No snapshot -> Should trigger
    should_run, reason = AnalysisGate.should_trigger_llm("TEST", {}, None)
    assert should_run
    assert reason == "FIRST_RUN"

def test_gate_cooldown(mock_snapshot):
    # Update last_trigger_at to now -> Cooldown active
    mock_snapshot["last_trigger_at"] = datetime.now()
    should_run, reason = AnalysisGate.should_trigger_llm("TEST", {}, mock_snapshot)
    assert not should_run

def test_gate_price_change(mock_snapshot):
    # Price change > threshold
    current_data = {
        "current_price": 110.0, # 10% change
        "rsi": 50,
        "volume_sma": 1000,
        "current_volume": 1000,
        "ema_short": 105,
        "ema_long": 95
    }
    # Ensure cooldown passed
    mock_snapshot["last_trigger_at"] = (datetime.now() - timedelta(hours=24))

    should_run, reason = AnalysisGate.should_trigger_llm("TEST", current_data, mock_snapshot)
    assert should_run
    assert "Price Change" in reason

def test_gate_no_change(mock_snapshot):
    # No significant change
    current_data = {
        "current_price": 100.0,
        "rsi": 50,
        "volume_sma": 1000,
        "current_volume": 1000,
        "ema_short": 100,
        "ema_long": 90
    }
    mock_snapshot["last_trigger_at"] = (datetime.now() - timedelta(days=2))

    should_run, reason = AnalysisGate.should_trigger_llm("TEST", current_data, mock_snapshot)
    assert not should_run
