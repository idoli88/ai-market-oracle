import feedparser
import logging
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class NewsProvider(ABC):
    @abstractmethod
    def fetch(self, ticker: str) -> List[Dict]:
        pass

class YahooRSSProvider(NewsProvider):
    BASE_URL = "https://finance.yahoo.com/rss/headline?s={ticker}"

    def fetch(self, ticker: str) -> List[Dict]:
        """
        Fetch news from Yahoo RSS.
        """
        url = self.BASE_URL.format(ticker=ticker)
        logger.info(f"Fetching RSS for {ticker}")

        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.warning(f"RSS Parse Error for {ticker}: {feed.bozo_exception}")
                return []

            items = []
            for entry in feed.entries[:3]: # Top 3 only
                # Yahoo RSS published format is RFC822
                pub_date = entry.get('published_parsed')
                if pub_date:
                    dt = datetime.fromtimestamp(time.mktime(pub_date))
                else:
                    dt = datetime.now()

                items.append({
                    "title": entry.get('title'),
                    "url": entry.get('link'),
                    "source": "Yahoo Finance",
                    "published_at": dt.isoformat()
                })
            return items

        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []

class StubProvider(NewsProvider):
    def fetch(self, ticker: str) -> List[Dict]:
        return []

def get_provider_for_ticker(ticker: str) -> NewsProvider:
    # MVP: Use Yahoo for everyone.
    # Future: Use Maya/Bizportal for TA/TLV tickers.
    return YahooRSSProvider()
