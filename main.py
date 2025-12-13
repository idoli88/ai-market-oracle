import argparse
import sys
import time
import schedule
from oracle.bot import MarketOracleBot
from oracle.config import settings
from oracle.logger import setup_logger

# Initialize logger for main script
logger = setup_logger('main')

def main():
    parser = argparse.ArgumentParser(description="The AI Market Oracle - Swing Trading Assistant")
    parser.add_argument('--dry-run', action='store_true', help="Run analysis but do not send WhatsApp message")
    parser.add_argument('--tickers', type=str, nargs='+', help="Override watchlist (e.g. --tickers AAPL MSFT)")
    parser.add_argument('--daemon', action='store_true', help="Run in daemon mode (continuous loop)")
    
    args = parser.parse_args()
    
    logger.info("Initializing application")
    
    try:
        # Tickers from args (if present) force override, otherwise None (uses settings)
        bot = MarketOracleBot(tickers=args.tickers)
        
        # Dry run from args overrides settings if True
        is_dry_run = args.dry_run or settings.DRY_RUN
        
        if args.daemon:
            logger.info(f"Starting in DAEMON mode. Schedule: Every {settings.SCHEDULE_MINUTES} minutes.")
            
            # Define the job
            def job():
                logger.info("Executing scheduled job...")
                try:
                    bot.run(dry_run=is_dry_run)
                except Exception as e:
                    logger.error(f"Error in scheduled job: {e}", exc_info=True)
            
            # Run once immediately
            job()
            
            # Schedule
            schedule.every(settings.SCHEDULE_MINUTES).minutes.do(job)
            
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            bot.run(dry_run=is_dry_run)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Critical Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
