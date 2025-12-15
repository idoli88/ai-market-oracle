
import logging
import asyncio
from oracle.config import settings
from oracle.logger import setup_logger
from oracle import database
from oracle.telegram_bot import OracleBot

# Setup logging globally
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bot_service")

def main():
    logger.info("Initializing Telegram Bot Service...")
    
    # Initialize Database
    database.init_db()
    
    # Start Bot
    bot = OracleBot()
    logger.info("Starting polling...")
    
    try:
        # run_polling() is blocking and manages its own loop
        bot.app.run_polling()
    except Exception as e:
        logger.error(f"Bot Crashed: {e}")
        raise

if __name__ == "__main__":
    main()
