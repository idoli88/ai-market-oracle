
import yfinance as yf
import ta
import pandas as pd
import requests
import logging
from typing import Dict, Any, Optional, List
from oracle.config import settings

logger = logging.getLogger(__name__)

class MarketData:
    @staticmethod
    def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
        """Fetch history from yfinance."""
        try:
            # yfinance handles caching internally if configured, but we do simple fetch
            df = yf.Ticker(ticker).history(period=period)
            if df.empty:
                logger.warning(f"No data found for {ticker}")
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    @staticmethod
    def calculate_technicals(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate RSI, EMA50, EMA200 from DataFrame."""
        if df.empty or len(df) < 200:
            return {}
        
        try:
            close = df['Close']
            
            # RSI
            rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
            current_rsi = rsi_series.iloc[-1]
            
            # EMA
            ema_short = ta.trend.EMAIndicator(close, window=settings.EMA_SHORT).ema_indicator().iloc[-1]
            ema_long = ta.trend.EMAIndicator(close, window=settings.EMA_LONG).ema_indicator().iloc[-1]
            
            # ATR (Volatility)
            atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], close, window=settings.ATR_WINDOW).average_true_range().iloc[-1]
            
            # Volume
            current_volume = df['Volume'].iloc[-1]
            volume_sma = df['Volume'].rolling(window=settings.VOLUME_WINDOW).mean().iloc[-1]
            
            current_price = close.iloc[-1]
            prev_price = close.iloc[-2]
            price_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            return {
                "current_price": round(current_price, 2),
                "price_change_pct": round(price_change_pct, 2),
                "rsi": round(current_rsi, 2),
                "ema_short": round(ema_short, 2),
                "ema_long": round(ema_long, 2),
                "atr": round(atr, 2),
                "current_volume": int(current_volume),
                "volume_sma": int(volume_sma) if pd.notna(volume_sma) else 0
            }
        except Exception as e:
            logger.error(f"Error calculating technicals: {e}")
            return {}

class SECData:
    BASE_URL = "https://data.sec.gov"
    
    @staticmethod
    def get_headers():
        return {"User-Agent": settings.SEC_USER_AGENT}

    @staticmethod
    def fetch_fundamentals(ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch basic fundamentals from SEC companyfacts (Stub/MVP).
        Real implementation requires mapping Ticker -> CIK.
        For MVP, we might skip full XBRL parsing or use a simplified approach 
        if we can't reliably map CIK without a huge mapping file.
        
        Returns a simplified dict of KPI if successful.
        """
        # TODO: Implement CIK mapping and accurate parsing.
        # For MVP, we return None so the system relies on price/technicals.
        logger.info(f"SEC fetch for {ticker} not fully implemented in MVP.")
        return None

    @staticmethod
    def check_new_filings(ticker: str, last_checked_date: str) -> List[str]:
        """
        Check for new filings since date.
        Returns list of headlines/form types.
        """
        return []

class TASEData:
    """Connector for Tel Aviv Stock Exchange (MAYA)."""
    @staticmethod
    def check_disclosures(ticker: str) -> List[str]:
        # Stub
        return []
