from datetime import datetime
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
        Execute the daily workflow.
        
        Args:
            dry_run (bool): If True, does not send WhatsApp message.
        """
        start_time = datetime.now()
        logger.info(f"Starting The Market Oracle... (dry_run={dry_run})")
        
        # 1. Fetch Data
        logger.info("Fetching market data...")
        data = self.fetcher.fetch_history()
        if not data:
            logger.warning("No data fetched. Exiting.")
            return

        # 2. Analyze Technicals
        logger.info("Analyzing technical indicators...")
        processed_data = self.analyst.process(data)
        if not processed_data:
            logger.warning("No valid technical data to process.")
            return
            
        summary = self.analyst.summarize_last_state(processed_data)
        
        # Generete HTML Report
        try:
            report_path = self.analyst.generate_html_report(processed_data)
            logger.info(f"Report available at: {report_path}")
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")

        logger.info("--- Technical Summary ---")
        # Log line by line for clarity
        for line in summary.split('\n'):
            logger.info(line)
        logger.info("-------------------------")

        # 3. Consult The Oracle (LLM)
        logger.info("Consulting The Oracle...")
        advice = self.brain.analyze(summary)
        
        logger.info("--- Oracle Advice ---")
        for line in advice.split('\n'):
            logger.info(line)
        logger.info("---------------------")

        # 4. Notify
        if dry_run or settings.DRY_RUN:
            logger.info("[Dry Run] Skipping WhatsApp notification.")
        else:
            logger.info("Broadcasting notification via WhatsApp...")
            
            # Optional warning for long messages
            if len(advice) > 1000:
                logger.warning("Message is very long, might get truncated.")
            
            # Construct final message
            final_msg = f"*The Oracle Report ({datetime.now().strftime('%Y-%m-%d')})*\n\n{advice}"
            
            # Fetch subscribers
            subscribers = database.get_active_subscribers()
            if not subscribers:
                logger.warning("No active subscribers found.")
            else:
                logger.info(f"Found {len(subscribers)} active subscribers.")
                for phone in subscribers:
                    try:
                        self.notifier.send_message(final_msg, phone)
                        # Avoid rate limits
                        time.sleep(2) 
                    except Exception as e:
                        logger.error(f"Failed to send to {phone}: {e}")

        duration = datetime.now() - start_time
        logger.info(f"Mission Complete. Duration: {duration}")
