import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from oracle.telegram_bot import broadcast_report
from oracle import database

# Mock data
reports = {
    "AAPL": {"html": "AAPL Report", "significant": False},
    "NVDA": {"html": "NVDA Report", "significant": True}
}

active_users = [
    {"chat_id": 100, "notification_pref": "standard"},
    {"chat_id": 200, "notification_pref": "alerts_only"},
    {"chat_id": 300, "notification_pref": "digest_only"},
    {"chat_id": 400, "notification_pref": "3x_full"}
]

@patch("oracle.telegram_bot.Bot")
@patch("oracle.database.get_user_tickers")
def test_broadcast_logic(mock_get_tickers, MockBot):
    # Setup
    mock_bot_instance = MockBot.return_value
    mock_bot_instance.send_message = AsyncMock()

    # Mock tickers for all users to be AAPL and NVDA
    mock_get_tickers.return_value = ["AAPL", "NVDA"]

    # --- Scenario 1: Normal Run ---
    asyncio.run(broadcast_report(active_users, reports, run_type="normal"))

    # 100 (Standard): Should get NVDA (Significant). Should NOT get AAPL (Quiet).
    # 200 (Alerts): Should get NVDA. Not AAPL.
    # 300 (Digest): Should get NOTHING.
    # 400 (3x): Should get AAPL AND NVDA.

    # Check calls
    # We can inspect send_message calls.
    # Args: chat_id, text, parse_mode

    calls = mock_bot_instance.send_message.call_args_list

    # Helper to find text sent to chat_id
    def get_msg_for(chat_id):
        msgs = []
        for call in calls:
            args, kwargs = call
            if kwargs.get('chat_id') == chat_id:
                msgs.append(kwargs.get('text'))
        return "\n".join(msgs)

    msg_100 = get_msg_for(100)
    assert "NVDA Report" in msg_100
    assert "AAPL Report" not in msg_100
    assert "עדכון שוק" in msg_100

    msg_200 = get_msg_for(200)
    assert "NVDA Report" in msg_200
    assert "AAPL Report" not in msg_200

    msg_300 = get_msg_for(300)
    assert msg_300 == "" # Nothing for digest_only in normal run

    msg_400 = get_msg_for(400)
    assert "NVDA Report" in msg_400
    assert "AAPL Report" in msg_400

@patch("oracle.telegram_bot.Bot")
@patch("oracle.database.get_user_tickers")
def test_broadcast_logic_digest(mock_get_tickers, MockBot):
    mock_bot_instance = MockBot.return_value
    mock_bot_instance.send_message = AsyncMock()
    mock_get_tickers.return_value = ["AAPL", "NVDA"]

    # --- Scenario 2: Digest Run ---
    asyncio.run(broadcast_report(active_users, reports, run_type="digest"))

    calls = mock_bot_instance.send_message.call_args_list
    def get_msg_for(chat_id):
        msgs = []
        for call in calls:
            args, kwargs = call
            if kwargs.get('chat_id') == chat_id:
                msgs.append(kwargs.get('text'))
        return "\n".join(msgs)

    # 100 (Standard): Should get ALL in digest.
    msg_100 = get_msg_for(100)
    assert "NVDA Report" in msg_100
    assert "AAPL Report" in msg_100
    assert "סיכום יומי" in msg_100

    # 200 (Alerts): Should get ONLY Significant?
    # Logic in code: elif pref == "alerts_only": if is_significant: should_send = True.
    # So even in digest run, Alerts Only users receive ONLY alerts?
    # Yes, that matches "Alerts Only" preference name.
    msg_200 = get_msg_for(200)
    assert "NVDA Report" in msg_200
    assert "AAPL Report" not in msg_200

    # 300 (Digest): Should get ALL.
    msg_300 = get_msg_for(300)
    assert "NVDA Report" in msg_300
    assert "AAPL Report" in msg_300

    # 400 (3x): Should get ALL.
    msg_400 = get_msg_for(400)
    assert "NVDA Report" in msg_400
    assert "AAPL Report" in msg_400
