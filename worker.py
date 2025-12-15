
import logging
import time
import schedule
import asyncio
import argparse
import sys
from oracle.config import settings
from oracle.logger import setup_logger
from oracle import database
from oracle.pipeline import run_pipeline

# Setup logging globally
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("worker_service")

def job_runner(dry_run: bool, run_type: str = "normal"):
    """Wrapper to run async pipeline from sync scheduler"""
    try:
        asyncio.run(run_pipeline(dry_run=dry_run, run_type=run_type))
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Oracle Worker Service")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline immediately without sending messages, then exit (for testing/maintenance).")
    args = parser.parse_args()

    logger.info("Initializing Oracle Worker Service...")
    database.init_db()

    if args.dry_run:
        logger.info("Dry Run Mode Enabled. Running pipeline once...")
        job_runner(dry_run=True, run_type="normal") # Default to normal for dry run, or maybe digest to see all? Normal is strictly safer.
        logger.info("Dry run complete. Exiting.")
        sys.exit(0)

    # Schedule Jobs
    logger.info(f"Scheduling jobs at: {settings.RUN_TIMES}")
    for t in settings.RUN_TIMES:
        # Determine Run Type
        r_type = "digest" if t == "21:00" else "normal"
        
        schedule.every().day.at(t).do(job_runner, dry_run=False, run_type=r_type)
        logger.info(f"Scheduled job at {t} (Type: {r_type})")

    # Keep alive loop
    logger.info("Worker started. Waiting for jobs...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Worker stopped by user.")
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
