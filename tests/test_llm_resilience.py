import pytest
from unittest.mock import MagicMock, patch
from oracle.analysis import LLMClient
from oracle.schemas import AnalysisResponse
from oracle.config import settings

# Mock Data
valid_json_response = """
{
    "action": "BUY",
    "emoji": "🚀",
    "confidence": 0.9,
    "summary_he": "Good trigger",
    "key_points_he": ["Point 1", "Point 2"],
    "invalidation_he": "Below 100",
    "risk_note_he": "Low risk"
}
"""

invalid_json_response = """
{
    "action": "INVALID",
    "confidence": 2.0
}
"""

@patch("oracle.analysis.OpenAI")
def test_valid_response(MockOpenAI):
    mock_client = MockOpenAI.return_value
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=valid_json_response))
    ]

    llm = LLMClient()
    result = llm.analyze_ticker("AAPL", {"current_price": 100})

    assert result["action"] == "BUY"
    assert result["confidence"] == 0.9

@patch("oracle.analysis.OpenAI")
def test_fallback_on_invalid_schema(MockOpenAI):
    mock_client = MockOpenAI.return_value
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=invalid_json_response))
    ]

    llm = LLMClient()
    result = llm.analyze_ticker("AAPL", {"current_price": 100})

    assert result["action"] == "HOLD" # Fallback default
    assert "שגיאה בניתוח" in str(result["key_points_he"])

@patch("oracle.analysis.OpenAI")
def test_routing_basic(MockOpenAI):
    mock_client = MockOpenAI.return_value
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=valid_json_response))
    ]

    llm = LLMClient()
    # Plan basic -> Basic model
    llm.analyze_ticker("AAPL", {"price_change_pct": 5.0}, plan="basic")

    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == settings.MODEL_BASIC

@patch("oracle.analysis.OpenAI")
def test_routing_pro_major_event(MockOpenAI):
    mock_client = MockOpenAI.return_value
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=valid_json_response))
    ]

    llm = LLMClient()
    # Plan pro + Major Event (>3%) -> HQ model
    llm.analyze_ticker("AAPL", {"price_change_pct": 4.0}, plan="pro")

    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == settings.MODEL_HQ

@patch("oracle.analysis.OpenAI")
def test_routing_pro_minor_event(MockOpenAI):
    mock_client = MockOpenAI.return_value
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=valid_json_response))
    ]

    llm = LLMClient()
    # Plan pro + Minor Event (<3%) -> Basic model
    llm.analyze_ticker("AAPL", {"price_change_pct": 1.0}, plan="pro")

    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == settings.MODEL_BASIC
