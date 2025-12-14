from datetime import datetime
import time
from typing import List, Optional

from oracle.data import MarketDataFetcher
from oracle.analysis import TechnicalAnalyst
from oracle.brain import OracleBrain
from oracle.notifier import WhatsAppNotifier
from oracle import database
from oracle.config import settings
from oracle.logger import setup_logger

logger = setup_logger(__name__)

class MarketOracleBot:
    def __init__(self, tickers: Optional[List[str]] = None):
        if tickers is None:
            # Default watchlist based on requirements or settings
            tickers = settings.DEFAULT_TICKERS
            
        # Initialize DB
        database.init_db()
        
        self.fetcher = MarketDataFetcher(tickers)
        self.analyst = TechnicalAnalyst()
        self.brain = OracleBrain()
        self.notifier = WhatsAppNotifier()
        logger.debug("MarketOracleBot components initialized")

    def run(self, dry_run: bool = False):
        """
        Execute the daily workflow using Batch Processing & Personalization.
        """
        start_time = datetime.now()
        logger.info(f"Starting The Market Oracle (Batch Mode)... (dry_run={dry_run})")
        
        # 1. Get Unique Tickers from ALL users
        unique_tickers = list(database.get_all_unique_tickers())
        if not unique_tickers:
            # Fallback for empty DB or first run
            unique_tickers = settings.DEFAULT_TICKERS
            logger.info(f"No tickers in DB. Using default watchlist: {unique_tickers}")

        logger.info(f"Fetching market data for {len(unique_tickers)} unique tickers...")
        
        # 2. Fetch Data (One Batch Request)
        self.fetcher = MarketDataFetcher(unique_tickers)
        data = self.fetcher.fetch_history()
        
        if not data:
            logger.warning("No data fetched. Exiting.")
            return

        # 3. Process Technicals
        logger.info("Calculating technical indicators...")
        processed_data = self.analyst.process(data)
        
        # 4. Batch Analysis (LLM)
        logger.info("Performing Batch AI Analysis...")
        analysis_map = self._analyze_batch(processed_data)
        
        # 5. Distribute Personalized Messages
        logger.info("Distributing personalized reports...")
        self._distribute_reports(analysis_map, dry_run)

        duration = datetime.now() - start_time
        logger.info(f"Mission Complete. Duration: {duration}")

    def _analyze_batch(self, processed_data: dict) -> dict:
        """
        Analyze stocks in chunks and parse output into a dictionary.
        Returns: {'NVDA': 'Analysis...', 'TSLA': 'Analysis...'}
        """
        analysis_map = {}
        
        # Convert processed data to summary string first
        chunk_size = 20
        tickers = list(processed_data.keys())
        
        for i in range(0, len(tickers), chunk_size):
            chunk_tickers = tickers[i:i + chunk_size]
            logger.info(f"Analyzing batch {i//chunk_size + 1}: {chunk_tickers}")
            
            # Prepare summary for this chunk
            chunk_data = {t: processed_data[t] for t in chunk_tickers}
            summary_text = self.analyst.summarize_last_state(chunk_data)
            
            # Ask LLM
            response_text = self.brain.analyze(summary_text)
            
            # Parse Response
            for line in response_text.split('\n'):
                if "|||" in line:
                    try:
                        parts = line.split("|||")
                        if len(parts) >= 3:
                            t_symbol = parts[0].strip().upper()
                            t_action = parts[1].strip()
                            t_reason = parts[2].strip()
                            analysis_map[t_symbol] = f"{t_action}\n{t_reason}"
                    except Exception as e:
                        logger.error(f"Failed to parse line: {line} -> {e}")
                        
        return analysis_map

    def _distribute_reports(self, analysis_map: dict, dry_run: bool):
        """Send personalized messages to each subscriber."""
        subscribers = database.get_active_subscribers()
        
        if not subscribers:
            logger.warning("No active subscribers.")
            return

        for phone in subscribers:
            user_tickers = database.get_user_tickers(phone)
            if not user_tickers:
                logger.info(f"User {phone} has no tickers defined. Skipping.")
                continue
                
            # Build Personal Report
            report_lines = [f"🔮 דו\"ח האורקל שלך ({datetime.now().strftime('%d/%m')})"]
            
            for ticker in user_tickers:
                # Find analysis (handle case mismatch)
                ticker_upper = ticker.upper()
                if ticker_upper in analysis_map:
                    report_lines.append(f"\n🔹 *{ticker_upper}*: {analysis_map[ticker_upper]}")
                else:
                    report_lines.append(f"\n🔹 *{ticker_upper}*: אין נתונים/ניתוח.")
            
            final_msg = "\n".join(report_lines)
            
            if dry_run or settings.DRY_RUN:
                logger.info(f"[Dry Run] To {phone}:\n{final_msg}")
            else:
                try:
                    self.notifier.send_message(final_msg, phone)
                    time.sleep(2)  # Rate limit
                except Exception as e:
                    logger.error(f"Failed to send to {phone}: {e}")
