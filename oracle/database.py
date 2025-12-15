
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Any, Tuple
from contextlib import contextmanager

from oracle.logger import setup_logger
from oracle.config import settings
from oracle.db_models import ALL_TABLES, CREATE_SUBSCRIBERS_TABLE

logger = setup_logger(__name__)

DB_PATH = settings.DB_PATH

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Enable access by column name
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database with all defined tables."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for table_schema in ALL_TABLES:
                cursor.execute(table_schema)
            conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

# --- Subscriber Management ---

def add_subscriber(chat_id: int, days: int = 30, plan: str = "basic") -> bool:
    """Add or update a subscriber by Telegram chat_id."""
    try:
        end_date = datetime.now() + timedelta(days=days)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM subscribers WHERE telegram_chat_id = ?", (chat_id,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute("""
                    UPDATE subscribers 
                    SET is_active = 1, subscription_end_date = ?, plan = ?
                    WHERE telegram_chat_id = ?
                """, (end_date, plan, chat_id))
                logger.info(f"Updated subscription for {chat_id}. Ends: {end_date}")
            else:
                cursor.execute("""
                    INSERT INTO subscribers (telegram_chat_id, is_active, subscription_end_date, plan)
                    VALUES (?, 1, ?, ?)
                """, (chat_id, end_date, plan))
                logger.info(f"Added new subscriber {chat_id}. Ends: {end_date}")
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add subscriber {chat_id}: {e}")
        return False

def remove_subscriber(chat_id: int) -> bool:
    """Deactivate a subscriber."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscribers SET is_active = 0 WHERE telegram_chat_id = ?", (chat_id,))
            conn.commit()
        logger.info(f"Subscriber {chat_id} deactivated.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove subscriber {chat_id}: {e}")
        return False

def get_active_subscribers() -> List[Dict[str, Any]]:
    """Return a list of dicts for active subscribers (chat_id, plan)."""
    active_users = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Deactivate expired
            now = datetime.now()
            cursor.execute("""
                UPDATE subscribers 
                SET is_active = 0 
                WHERE subscription_end_date < ? AND is_active = 1
            """, (now,))
            if cursor.rowcount > 0:
                logger.info(f"Deactivated {cursor.rowcount} expired subscriptions.")
                conn.commit()

            cursor.execute("SELECT telegram_chat_id, plan FROM subscribers WHERE is_active = 1")
            rows = cursor.fetchall()
            active_users = [{"chat_id": row["telegram_chat_id"], "plan": row["plan"]} for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch subscribers: {e}")
    return active_users

def get_subscriber_status(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get status for a specific user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscribers WHERE telegram_chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Failed to fetch status for {chat_id}: {e}")
    return None

# --- Portfolio Management ---

def add_ticker_to_user(chat_id: int, ticker: str) -> Tuple[bool, str]:
    """Add a ticker to a user's portfolio. Returns (success, message)."""
    try:
        ticker = ticker.upper().strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check limit (6)
            cursor.execute("SELECT COUNT(*) FROM user_portfolios WHERE telegram_chat_id = ?", (chat_id,))
            count = cursor.fetchone()[0]
            if count >= 6:
                return False, "Limit reached (max 6 tickers)."
                
            cursor.execute("""
                INSERT OR IGNORE INTO user_portfolios (telegram_chat_id, ticker) 
                VALUES (?, ?)
            """, (chat_id, ticker))
            conn.commit()
            
        logger.info(f"Added {ticker} to {chat_id}")
        return True, f"Added {ticker}."
    except Exception as e:
        logger.error(f"Failed to add portfolio item: {e}")
        return False, "Internal error."

def remove_ticker_from_user(chat_id: int, ticker: str) -> bool:
    try:
        ticker = ticker.upper().strip()
        with get_db_connection() as conn:
            conn.execute("DELETE FROM user_portfolios WHERE telegram_chat_id = ? AND ticker = ?", (chat_id, ticker))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to remove ticker: {e}")
        return False

def get_user_tickers(chat_id: int) -> List[str]:
    tickers = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM user_portfolios WHERE telegram_chat_id = ?", (chat_id,))
            rows = cursor.fetchall()
            tickers = [row["ticker"] for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch tickers for {chat_id}: {e}")
    return tickers

def get_all_unique_tickers() -> Set[str]:
    unique_tickers = set()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM user_portfolios")
            rows = cursor.fetchall()
            unique_tickers = {row["ticker"] for row in rows}
    except Exception as e:
        logger.error(f"Failed to fetch unique tickers: {e}")
    return unique_tickers

# --- Caching & Snapshots ---

def get_snapshot(ticker: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ticker_snapshots WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None

def update_snapshot(ticker: str, price: float, rsi: float, ema_s: float, ema_l: float, action: str, summary: Dict):
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ticker_snapshots 
                (ticker, last_price, last_rsi, last_ema_short, last_ema_long, last_run_at, last_action, last_summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticker, price, rsi, ema_s, ema_l, datetime.now(), action, json.dumps(summary)))
            conn.commit()
    except Exception as e:
        logger.error(f"Snapshot update failed for {ticker}: {e}")

def get_fundamentals_cache(ticker: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json, last_updated FROM fundamentals_cache WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            if row:
                # Check expiration (e.g. 7 days) - logic can be here or in caller
                return json.loads(row["data_json"])
    except Exception:
        pass
    return None

def update_fundamentals_cache(ticker: str, data: Dict, source: str = "SEC"):
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fundamentals_cache (ticker, source, last_updated, data_json)
                VALUES (?, ?, ?, ?)
            """, (ticker, source, datetime.now(), json.dumps(data)))
            conn.commit()
    except Exception as e:
        logger.error(f"Fundamentals cache update failed for {ticker}: {e}")
