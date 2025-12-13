import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
from oracle.logger import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = setup_logger(__name__)

class MarketDataFetcher:
    def __init__(self, tickers: List[str]):
        """
        Initialize the fetcher with a list of tickers.
        """
        self.tickers = tickers
        logger.debug(f"Initialized MarketDataFetcher with tickers: {tickers}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _fetch_ticker_data(self, ticker: str, period: str) -> Optional[pd.DataFrame]:
        logger.debug(f"Downloading data for {ticker}")
        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            logger.warning(f"No data found for {ticker}")
            return None
        return df

    def fetch_history(self, period: str = "1y") -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for all tickers.
        
        Args:
            period (str): The period to download (default: "1y").
            
        Returns:
            Dict[str, pd.DataFrame]: A dictionary mapping ticker to its DataFrame.
        """
        data = {}
        logger.info(f"Fetching historical data for period: {period}")
        
        for ticker in self.tickers:
            try:
                # Download data for specific ticker
                df = self._fetch_ticker_data(ticker, period)
                
                if df is not None:
                    data[ticker] = df
                    logger.info(f"Successfully fetched data for {ticker} ({len(df)} rows)")
            except Exception as e:
                logger.error(f"Error fetching data for {ticker} after retries: {e}")
        
        return data
