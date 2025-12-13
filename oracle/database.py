import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from oracle.logger import setup_logger

logger = setup_logger(__name__)

DB_PATH = "subscribers.db"

def init_db():
    """Initialize the database with the subscribers table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            subscription_end_date TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def add_subscriber(phone_number: str, days: int) -> bool:
    """
    Add a new subscriber or update an existing one.
    Returns True if successful, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        end_date = datetime.now() + timedelta(days=days)
        
        # Check if exists
        cursor.execute("SELECT id FROM subscribers WHERE phone_number = ?", (phone_number,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE subscribers 
                SET is_active = 1, subscription_end_date = ? 
                WHERE phone_number = ?
            ''', (end_date, phone_number))
            logger.info(f"Updated subscription for {phone_number}. Ends: {end_date}")
        else:
            cursor.execute('''
                INSERT INTO subscribers (phone_number, is_active, subscription_end_date)
                VALUES (?, 1, ?)
            ''', (phone_number, end_date))
            logger.info(f"Added new subscriber {phone_number}. Ends: {end_date}")
            
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add subscriber: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_active_subscribers() -> List[str]:
    """Return a list of phone numbers for active subscribers."""
    active_users = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Deactivate expired first (lazy expiration)
        now = datetime.now()
        cursor.execute('''
            UPDATE subscribers 
            SET is_active = 0 
            WHERE subscription_end_date < ? AND is_active = 1
        ''', (now,))
        if cursor.rowcount > 0:
            logger.info(f"Deactivated {cursor.rowcount} expired subscriptions.")
            conn.commit()

        # Fetch active
        cursor.execute("SELECT phone_number FROM subscribers WHERE is_active = 1")
        rows = cursor.fetchall()
        active_users = [row[0] for row in rows]
        
    except Exception as e:
        logger.error(f"Failed to fetch subscribers: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
    return active_users

def remove_subscriber(phone_number: str) -> bool:
    """Manually remove/deactivate a subscriber."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE subscribers SET is_active = 0 WHERE phone_number = ?", (phone_number,))
        conn.commit()
        logger.info(f"Subscriber {phone_number} deactivated.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove subscriber: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()
