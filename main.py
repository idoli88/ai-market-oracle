
import logging
import time
import schedule
import asyncio
import signal
import sys
from threading import Thread

from oracle.config import settings
from oracle.logger import setup_logger
from oracle import database
from oracle.data_source import MarketData, SECData
from oracle.analysis import AnalysisGate, LLMClient
from oracle.telegram_bot import broadcast_report, OracleBot

logger = setup_logger(__name__)

async def run_pipeline():
    logger.info("🚀 Starting pipeline run...")
    
    # 1. Get all unique tickers from all active users
    active_users = database.get_active_subscribers()
    if not active_users:
        logger.info("No active subscribers. Skipping run.")
        return
        
    unique_tickers = database.get_all_unique_tickers()
    logger.info(f"Checking {len(unique_tickers)} unique tickers for {len(active_users)} users.")
    
    reports = {} # ticker -> formatted report
    llm_client = LLMClient()
    
    for ticker in unique_tickers:
        try:
            logger.info(f"Processing {ticker}...")
            
            # Fetch Data
            df = MarketData.fetch_price_history(ticker)
            if df.empty:
                continue
                
            technicals = MarketData.calculate_technicals(df)
            if not technicals:
                continue
                
            snapshot = database.get_snapshot(ticker)
            
            # Check for generic news triggers (Stub)
            
            # The Gate
            should_run_llm = AnalysisGate.should_trigger_llm(ticker, technicals, snapshot)
            
            analysis_result = None
            if should_run_llm:
                logger.info(f"invoking LLM for {ticker}")
                # Build context
                context = f"Previous action: {snapshot.get('last_action') if snapshot else 'None'}"
                analysis_result = llm_client.analyze_ticker(ticker, technicals, context)
            else:
                # Reuse old snapshot summary or create simple technical update
                logger.info(f"Skipping LLM for {ticker}, using fallback/cache")
                analysis_result = {
                    "ticker": ticker,
                    "action": "HOLD", # Default if no change
                    "confidence": 1.0, 
                    "summary_he": "אין שינוי מהותי במדדים הטכניים.",
                    "key_points_he": [f"RSI: {technicals.get('rsi')}", f"Price: {technicals.get('current_price')}"],
                    "invalidation_he": "-",
                    "risk_note_he": "-"
                }

            # Save Snapshot
            database.update_snapshot(
                ticker, 
                technicals.get('current_price'),
                technicals.get('rsi'),
                technicals.get('ema_short'), 
                technicals.get('ema_long'),
                analysis_result.get('action'),
                analysis_result
            )
            
            # Format Report for Telegram
            reports[ticker] = f"""
*{ticker}*: {analysis_result.get('action')} {analysis_result.get('emoji', '')}
מחיר: {technicals.get('current_price')} ({technicals.get('price_change_pct')}%)
RSI: {technicals.get('rsi')}
---
{analysis_result.get('summary_he')}
⚠️ {analysis_result.get('risk_note_he')}
            """.strip()

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
    
    # Broadcast
    if reports:
        logger.info("Broadcasting updates...")
        await broadcast_report(active_users, reports)
        logger.info("Broadcast complete.")
    else:
        logger.info("No reports generated.")

def job_runner():
    asyncio.run(run_pipeline())

def main():
    logger.info("Initializing System...")
    database.init_db()
    
    # Start Telegram Bot in background thread (for MVP)
    # Ideally, we'd use an async loop for everything, 
    # but python-telegram-bot's polling + schedule is tricky in one thread.
    # We will run the bot here and the scheduler in a separate thread for simplicity or vice versa.
    # Approach: Main thread runs Bot (blocking), Thread runs valid scheduler.
    
    def run_schedule():
        logger.info("Scheduler started.")
        # Schedule jobs
        for t in settings.RUN_TIMES:
            schedule.every().day.at(t).do(job_runner)
            logger.info(f"Scheduled job at {t}")
            
        while True:
            schedule.run_pending()
            time.sleep(60)

    scheduler_thread = Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()
    
    # Run Bot (Blocking)
    bot = OracleBot()
    # Create an event loop for the bot if needed, depending on implementation
    # Application.run_polling() manages its own loop.
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()
