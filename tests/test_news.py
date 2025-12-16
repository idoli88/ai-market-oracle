import pytest
from unittest.mock import MagicMock, patch
from oracle.news import YahooRSSProvider
from oracle.database import update_news_cache, get_cached_news, init_db
import sqlite3
import os
from datetime import datetime, timedelta
import time

# Mock RSS Data
MOCK_RSS_XML = """
<rss version="2.0">
<channel>
    <item>
        <title>Test News 1</title>
        <link>http://example.com/1</link>
        <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
    </item>
    <item>
        <title>Test News 2</title>
        <link>http://example.com/2</link>
        <pubDate>Mon, 01 Jan 2024 09:00:00 GMT</pubDate>
    </item>
</channel>
</rss>
"""

@patch("oracle.news.feedparser.parse")
def test_yahoo_rss_fetch(mock_parse):
    # Setup Mock
    mock_feed = MagicMock()
    mock_feed.bozo = 0
    mock_feed.entries = [
        {'title': 'Test News 1', 'link': 'http://example.com/1', 'published_parsed': time.gmtime()},
        {'title': 'Test News 2', 'link': 'http://example.com/2', 'published_parsed': time.gmtime()}
    ]
    mock_parse.return_value = mock_feed

    provider = YahooRSSProvider()
    news = provider.fetch("AAPL")

    assert len(news) == 2
    assert news[0]['title'] == "Test News 1"
    assert news[0]['source'] == "Yahoo Finance"

def test_db_caching():
    # Setup Temp DB (Absolute path for safety in Docker)
    test_db = os.path.abspath("/tmp/test_news.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    with patch("oracle.config.settings.DB_PATH", test_db):
        init_db()

        # 1. Update Cache
        news_items = [
            {"title": "Valid News", "url": "http://1", "source": "T", "published_at": datetime.now().isoformat()}
        ]
        update_news_cache("AAPL", news_items)

        # 2. Get Valid Cache
        cached = get_cached_news("AAPL", ttl_minutes=60)
        assert len(cached) == 1
        assert cached[0]['title'] == "Valid News"

        # 3. Test TTL Expiration
        # Manually backdate the fetched_at
        conn = sqlite3.connect(test_db)
        old_time = (datetime.now() - timedelta(minutes=61)).isoformat()
        conn.execute("UPDATE news_cache SET fetched_at = ?", (old_time,))
        conn.commit()
        conn.close()

        expired = get_cached_news("AAPL", ttl_minutes=60)
        assert len(expired) == 0

    if os.path.exists(test_db):
        os.remove(test_db)
