
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


# --- Subscriber Management ---

def migrate_db():
    """Check for missing columns and add them (SQLite migration)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check subscribers table
            cursor.execute("PRAGMA table_info(subscribers)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "notification_pref" not in columns:
                logger.info("Migrating DB: Adding notification_pref to subscribers.")
                cursor.execute("ALTER TABLE subscribers ADD COLUMN notification_pref TEXT DEFAULT 'standard'")
                conn.commit()
            
            # Check ticker_snapshots table
            cursor.execute("PRAGMA table_info(ticker_snapshots)")
            columns_snap = [info[1] for info in cursor.fetchall()]
            
            if "last_trigger_type" not in columns_snap:
                logger.info("Migrating DB: Adding trigger columns to ticker_snapshots.")
                cursor.execute("ALTER TABLE ticker_snapshots ADD COLUMN last_trigger_type TEXT")
                cursor.execute("ALTER TABLE ticker_snapshots ADD COLUMN last_trigger_at TIMESTAMP")
                conn.commit()
    except Exception as e:
        logger.error(f"Migration failed: {e}")

def init_db():
    """Initialize the database with all defined tables."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for table_schema in ALL_TABLES:
                cursor.execute(table_schema)
            conn.commit()
        
        # Run migrations
        migrate_db()
        
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def add_subscriber(chat_id: int, days: int = 30, plan: str = "basic", notification_pref: str = "standard") -> bool:
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
                    SET is_active = 1, subscription_end_date = ?, plan = ?, notification_pref = ?
                    WHERE telegram_chat_id = ?
                """, (end_date, plan, notification_pref, chat_id))
                logger.info(f"Updated subscription for {chat_id}. Ends: {end_date}")
            else:
                cursor.execute("""
                    INSERT INTO subscribers (telegram_chat_id, is_active, subscription_end_date, plan, notification_pref)
                    VALUES (?, 1, ?, ?, ?)
                """, (chat_id, end_date, plan, notification_pref))
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

            cursor.execute("SELECT telegram_chat_id, plan, notification_pref FROM subscribers WHERE is_active = 1")
            rows = cursor.fetchall()
            active_users = [{
                "chat_id": row["telegram_chat_id"], 
                "plan": row["plan"],
                "notification_pref": row["notification_pref"]
            } for row in rows]
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
    """Get the last technical snapshot for a ticker."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ticker_snapshots WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            if row:
                return {
                    "ticker": row["ticker"],
                    "last_price": row["last_price"],
                    "last_rsi": row["last_rsi"],
                    "last_ema_short": row["last_ema_short"],
                    "last_ema_long": row["last_ema_long"],
                    "last_run_at": row["last_run_at"],
                    "last_action": row["last_action"],
                    "last_summary_json": row["last_summary_json"],
                    "last_trigger_type": row["last_trigger_type"],
                    "last_trigger_at": row["last_trigger_at"]
                }
    except Exception as e:
        logger.error(f"Failed to get snapshot for {ticker}: {e}")
    return None

def update_snapshot(ticker: str, price: float, rsi: float, ema_s: float, ema_l: float, action: str, summary_json: Dict, trigger_type: str = None, trigger_at: datetime = None):
    """Update or insert technical snapshot."""
    try:
        current_time = datetime.now()
        summary_str = json.dumps(summary_json, ensure_ascii=False)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # If trigger provided, update it. If not, preserve old trigger info??
            # Actually if we run and NO trigger, maybe we shouldn't wipe the old timestamp 
            # if we want to check cooldown from LAST trigger? 
            # But the 'last_run_at' updates every time. 
            # If we don't trigger now, we shouldn't change last_trigger_at.
            
            # Logic: If trigger_type is NOT None, update trigger columns. Else keep existing?
            # Simpler for now: Check if exists first.
            
            cursor.execute("SELECT last_trigger_type, last_trigger_at FROM ticker_snapshots WHERE ticker = ?", (ticker,))
            existing = cursor.fetchone()
            
            new_trigger_type = trigger_type
            new_trigger_at = trigger_at
            
            if not new_trigger_type and existing:
                new_trigger_type = existing['last_trigger_type']
                new_trigger_at = existing['last_trigger_at']
            
            cursor.execute("""
                INSERT INTO ticker_snapshots (ticker, last_price, last_rsi, last_ema_short, last_ema_long, last_run_at, last_action, last_summary_json, last_trigger_type, last_trigger_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    last_price = excluded.last_price,
                    last_rsi = excluded.last_rsi,
                    last_ema_short = excluded.last_ema_short,
                    last_ema_long = excluded.last_ema_long,
                    last_run_at = excluded.last_run_at,
                    last_action = excluded.last_action,
                    last_summary_json = excluded.last_summary_json,
                    last_trigger_type = excluded.last_trigger_type,
                    last_trigger_at = excluded.last_trigger_at
            """, (ticker, price, rsi, ema_s, ema_l, current_time, action, summary_str, new_trigger_type, new_trigger_at))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update snapshot for {ticker}: {e}")

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

def get_max_plan_for_ticker(ticker: str) -> str:
    """
    Check all subscribers watching this ticker.
    If ANY user has 'pro' or 'premium', return 'pro'.
    Else 'basic'.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT s.plan 
                FROM subscribers s
                JOIN user_portfolios p ON s.telegram_chat_id = p.telegram_chat_id
                WHERE p.ticker = ? AND s.is_active = 1
            """
            cursor.execute(query, (ticker,))
            rows = cursor.fetchall()
            
            for row in rows:
                plan = row["plan"].lower() if row["plan"] else "basic"
                if plan in ["pro", "premium", "vip"]:
                    return "pro"
            
            return "basic"
    except Exception as e:
        logger.error(f"Error checking plan for {ticker}: {e}")
        return "basic"
