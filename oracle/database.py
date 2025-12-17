import sqlite3
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Any, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

from oracle.logger import setup_logger
from oracle.config import settings
from oracle.db_models import (
    ALL_TABLES,
    ALL_TABLE_NAMES,
    CREATE_SUBSCRIBERS_TABLE,
    CREATE_USER_PORTFOLIOS_TABLE,
    CREATE_TICKER_SNAPSHOTS_TABLE,
    CREATE_FUNDAMENTALS_CACHE_TABLE,
    CREATE_NEWS_CACHE_TABLE
)

logger = setup_logger(__name__)

def _prepare_sql(query: str) -> str:
    """
    Convert SQLite-style placeholders to PostgreSQL placeholders when needed.
    """
    if settings.use_postgres:
        return query.replace("?", "%s")
    return query


def _translate_schema(sql: str) -> str:
    """
    Translate SQLite DDL to be PostgreSQL-compatible.
    Minimal conversion for current schemas.
    """
    if not settings.use_postgres:
        return sql
    translated = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    translated = translated.replace("AUTOINCREMENT", "")
    return translated


class PostgresCursor:
    """Minimal cursor wrapper to mimic sqlite3 interface."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query: str, params: Optional[tuple] = None):
        self._cursor.execute(_prepare_sql(query), params or [])

    def executemany(self, query: str, seq_of_params):
        self._cursor.executemany(_prepare_sql(query), seq_of_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()


class PostgresConnection:
    """Connection wrapper providing sqlite-like API for postgres backends."""

    def __init__(self, conn):
        self._conn = conn
        self._row_factory = None  # for compatibility

    # Compatibility with sqlite interface
    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        # Ignored for postgres; RealDictCursor already provides dict-like rows
        self._row_factory = value

    def cursor(self):
        return PostgresCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def execute(self, query: str, params: Optional[tuple] = None):
        with self.cursor() as cursor:
            cursor.execute(query, params)
            try:
                rows = cursor.fetchall()
            except psycopg2.ProgrammingError:
                rows = None
            self._conn.commit()
            return rows

    def executemany(self, query: str, seq_of_params):
        with self.cursor() as cursor:
            cursor.executemany(query, seq_of_params)
            self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    if settings.use_postgres:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for PostgreSQL connections. Install requirements.txt.")
        conn = psycopg2.connect(settings.DATABASE_URL)
        wrapped = PostgresConnection(conn)
        try:
            yield wrapped
        finally:
            wrapped.close()
    else:
        conn = sqlite3.connect(settings.DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable access by column name
        try:
            yield conn
        finally:
            conn.close()

# --- Subscriber Management ---

def migrate_db():
    """Check for missing columns and add them (SQLite migration)."""
    if settings.use_postgres:
        logger.info("Skipping SQLite migrations (use Alembic or SQL migrations for Postgres).")
        return
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check subscribers table
            # Create Tables (if they don't exist)
            conn.execute(CREATE_SUBSCRIBERS_TABLE)
            conn.execute(CREATE_USER_PORTFOLIOS_TABLE)
            conn.execute(CREATE_TICKER_SNAPSHOTS_TABLE)
            conn.execute(CREATE_FUNDAMENTALS_CACHE_TABLE)
            conn.execute(CREATE_NEWS_CACHE_TABLE)

            # Migrations
            # 1. Add notification_pref if missing
            try:
                 conn.execute("ALTER TABLE subscribers ADD COLUMN notification_pref TEXT DEFAULT 'standard'")
                 logger.info("Migrating DB: Added notification_pref to subscribers.")
            except sqlite3.OperationalError:
                 pass

            # 2. Add last_trigger details if missing
            try:
                 conn.execute("ALTER TABLE ticker_snapshots ADD COLUMN last_trigger_type TEXT")
                 conn.execute("ALTER TABLE ticker_snapshots ADD COLUMN last_trigger_at TIMESTAMP")
                 logger.info("Migrating DB: Added trigger columns to ticker_snapshots.")
            except sqlite3.OperationalError:
                 pass

            conn.commit()
    except Exception as e:
        logger.error(f"Migration failed: {e}")

def init_db():
    """Initialize the database with all defined tables."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for table_schema in ALL_TABLES:
                cursor.execute(_translate_schema(table_schema))
            conn.commit()

        # Run migrations
        migrate_db()

        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

# --- Sessions (JWT revocation) ---

def create_session(user_id: int, token_hash: str, expires_at: datetime) -> bool:
    """Persist a session record for token revocation."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, token_hash, expires_at))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to create session for user {user_id}: {e}")
        return False


def deactivate_session_by_hash(token_hash: str) -> bool:
    """Deactivate a session using its token hash."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE sessions
                SET is_active = 0
                WHERE token_hash = ?
            """, (token_hash,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to deactivate session: {e}")
        return False


def is_session_active(token_hash: str) -> bool:
    """Check if a session is active and not expired; auto-deactivate expired ones."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_active, expires_at FROM sessions
                WHERE token_hash = ?
            """, (token_hash,))
            row = cursor.fetchone()
            if not row:
                return False
            is_active = row["is_active"] if isinstance(row, dict) else row[0]
            expires_at = row["expires_at"] if isinstance(row, dict) else row[1]
            if not is_active:
                return False
            if expires_at and datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
                conn.execute("""
                    UPDATE sessions SET is_active = 0 WHERE token_hash = ?
                """, (token_hash,))
                conn.commit()
                return False
            return True
    except Exception as e:
        logger.error(f"Failed to check session: {e}")
        return False


def purge_expired_sessions(retention_days: int = settings.SESSION_RETENTION_DAYS) -> int:
    """Delete expired or inactive sessions older than retention window."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM sessions
                WHERE (expires_at < ? OR is_active = 0) AND created_at < ?
            """, (datetime.utcnow(), cutoff))
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                logger.info(f"Purged {deleted} old sessions")
            return deleted
    except Exception as e:
        logger.error(f"Failed to purge sessions: {e}")
        return 0


def prune_news_cache(retention_days: int = settings.NEWS_RETENTION_DAYS) -> int:
    """Remove news_cache rows older than retention_days."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news_cache WHERE fetched_at < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                logger.info(f"Pruned {deleted} news_cache rows")
            return deleted
    except Exception as e:
        logger.error(f"Failed to prune news cache: {e}")
        return 0


def prune_fundamentals_cache(retention_days: int = settings.FUNDAMENTALS_RETENTION_DAYS) -> int:
    """Remove fundamentals cache rows older than retention_days."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fundamentals_cache WHERE last_updated < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                logger.info(f"Pruned {deleted} fundamentals_cache rows")
            return deleted
    except Exception as e:
        logger.error(f"Failed to prune fundamentals cache: {e}")
        return 0


def run_maintenance():
    """Run lightweight DB maintenance for caches and sessions."""
    prune_news_cache()
    prune_fundamentals_cache()
    purge_expired_sessions()

def reset_database():
    """
    Reset database state (used in tests).
    Removes the SQLite file and recreates schema, or truncates Postgres tables.
    """
    try:
        if settings.use_postgres:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for table in ALL_TABLE_NAMES:
                    cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                conn.commit()
        else:
            if os.path.exists(settings.DB_PATH):
                os.remove(settings.DB_PATH)
            init_db()
        logger.info("Database reset successfully.")
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
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

def get_cached_news(ticker: str, ttl_minutes: int = 60) -> List[Dict]:
    """
    Get valid cached news (younger than TTL).
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check fetch time
            cursor.execute("""
                SELECT * FROM news_cache
                WHERE ticker = ?
                ORDER BY published_at DESC
                LIMIT 5
            """, (ticker,))
            rows = cursor.fetchall()

            if not rows:
                return []

            # Check TTL of the batch (using first item's fetch time)
            last_fetch = datetime.fromisoformat(rows[0]['fetched_at'])
            age_minutes = (datetime.now() - last_fetch).total_seconds() / 60

            if age_minutes > ttl_minutes:
                return []

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error reading news cache for {ticker}: {e}")
        return []

def update_news_cache(ticker: str, news_items: List[Dict]):
    """
    Replace cache for ticker with new items.
    """
    if not news_items:
        return

    try:
        with get_db_connection() as conn:
            # Clear old
            conn.execute("DELETE FROM news_cache WHERE ticker = ?", (ticker,))

            fetched_at = datetime.now()
            data = []
            for item in news_items:
                data.append((
                    ticker,
                    item.get('title'),
                    item.get('url'),
                    item.get('source'),
                    item.get('published_at', datetime.now()),
                    fetched_at
                ))

            conn.executemany("""
                INSERT INTO news_cache (ticker, title, url, source, published_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating news cache for {ticker}: {e}")

def get_fundamentals(ticker: str, ttl_days: int = 7) -> Optional[Dict]:
    """
    Get cached fundamentals if fresh (within TTL).
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM fundamentals_cache
                WHERE ticker = ?
            """, (ticker,))
            row = cursor.fetchone()

            if not row:
                return None

            # Check TTL
            last_updated = datetime.fromisoformat(row['last_updated'])
            age_days = (datetime.now() - last_updated).days

            if age_days > ttl_days:
                return None

            # Parse JSON data
            return {
                'ticker': ticker,
                'kpis': json.loads(row['data_json']),
                'source': row['source'],
                'last_updated': row['last_updated'],
                'period': row['period']
            }
    except Exception as e:
        logger.error(f"Error reading fundamentals for {ticker}: {e}")
        return None

def update_fundamentals(ticker: str, kpis: Dict, source: str = "SEC_EDGAR", period: str = "latest"):
    """
    Update fundamentals cache for ticker.
    """
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fundamentals_cache
                (ticker, source, last_updated, data_json, period)
                VALUES (?, ?, ?, ?, ?)
            """, (
                ticker,
                source,
                datetime.now().isoformat(),
                json.dumps(kpis),
                period
            ))
            conn.commit()
            logger.info(f"Updated fundamentals for {ticker}")
    except Exception as e:
        logger.error(f"Error updating fundamentals for {ticker}: {e}")

def get_filing_checkpoint(ticker: str) -> Optional[Dict]:
    """
    Get last processed filing checkpoint for ticker.
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM filings_checkpoint
                WHERE ticker = ?
            """, (ticker,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'ticker': ticker,
                'source': row['source'],
                'last_checked': row['last_checked'],
                'last_accession_or_id': row['last_accession_or_id'],
                'last_filing_date': row['last_filing_date'],
                'filings_json': json.loads(row['filings_json']) if row['filings_json'] else None
            }
    except Exception as e:
        logger.error(f"Error reading filing checkpoint for {ticker}: {e}")
        return None

def update_filing_checkpoint(ticker: str, accession: str, filing_date: str, source: str = "SEC_EDGAR"):
    """
    Update filing checkpoint for ticker.
    """
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO filings_checkpoint
                (ticker, source, last_checked, last_accession_or_id, last_filing_date, filings_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                source,
                datetime.now().isoformat(),
                accession,
                filing_date,
                None  # Can store detailed filing info if needed
            ))
            conn.commit()
            logger.info(f"Updated filing checkpoint for {ticker}: {accession}")
    except Exception as e:
        logger.error(f"Error updating filing checkpoint for {ticker}: {e}")

# --- Web User Management ---

def create_web_user(email: str, password_hash: str, telegram_chat_id: Optional[int] = None) -> Optional[int]:
    """
    Create a new web user account.
    
    Args:
        email: User's email address
        password_hash: Bcrypt hashed password
        telegram_chat_id: Optional Telegram chat ID to link
    
    Returns:
        User ID if successful, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO web_users (email, password_hash, telegram_chat_id)
                VALUES (?, ?, ?)
            """, (email, password_hash, telegram_chat_id))
            conn.commit()
            user_id = cursor.lastrowid
            logger.info(f"Created web user: {email} (ID: {user_id})")
            return user_id
    except sqlite3.IntegrityError:
        logger.warning(f"User already exists: {email}")
        return None
    except Exception as e:
        logger.error(f"Failed to create web user {email}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user by email address.
    
    Args:
        email: User's email address
    
    Returns:
        User dict if found, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM web_users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Failed to fetch user {email}: {e}")
    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve user by ID.
    
    Args:
        user_id: User's ID
    
    Returns:
        User dict if found, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM web_users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Failed to fetch user ID {user_id}: {e}")
    return None


def link_telegram_to_web_user(email: str, telegram_chat_id: int) -> bool:
    """
    Link a Telegram account to an existing web user.
    
    Args:
        email: User's email
        telegram_chat_id: Telegram chat ID
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE web_users
                SET telegram_chat_id = ?
                WHERE email = ?
            """, (telegram_chat_id, email))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Linked Telegram {telegram_chat_id} to {email}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to link Telegram account: {e}")
        return False


def update_last_login(user_id: int) -> bool:
    """
    Update user's last login timestamp.
    
    Args:
        user_id: User's ID
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE web_users
                SET last_login = ?
                WHERE id = ?
            """, (datetime.now(), user_id))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update last login for user {user_id}: {e}")
        return False


# --- Payment Management ---

def log_payment(
    user_id: int,
    tranzila_transaction_id: str,
    amount: float,
    status: str,
    payment_method: str = "credit_card",
    metadata: Optional[Dict] = None
) -> Optional[int]:
    """
    Log a payment transaction.
    
    Args:
        user_id: User's ID
        tranzila_transaction_id: Tranzila transaction ID
        amount: Payment amount
        status: Payment status (pending, confirmed, failed, refunded)
        payment_method: Payment method used
        metadata: Additional payment metadata
    
    Returns:
        Payment ID if successful, None otherwise
    """
    try:
        metadata_json = json.dumps(metadata) if metadata else None
        confirmed_at = datetime.now() if status == "confirmed" else None
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments 
                (user_id, tranzila_transaction_id, amount, currency, status, payment_method, confirmed_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, tranzila_transaction_id, amount, "ILS", status, payment_method, confirmed_at, metadata_json))
            conn.commit()
            payment_id = cursor.lastrowid
            logger.info(f"Logged payment {tranzila_transaction_id} for user {user_id}: {status}")
            return payment_id
    except Exception as e:
        logger.error(f"Failed to log payment: {e}")
        return None


def update_payment_status(tranzila_transaction_id: str, status: str) -> bool:
    """
    Update payment status.
    
    Args:
        tranzila_transaction_id: Tranzila transaction ID
        status: New status
    
    Returns:
        True if successful, False otherwise
    """
    try:
        confirmed_at = datetime.now() if status == "confirmed" else None
        
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE payments
                SET status = ?, confirmed_at = ?
                WHERE tranzila_transaction_id = ?
            """, (status, confirmed_at, tranzila_transaction_id))
            conn.commit()
        
        logger.info(f"Updated payment {tranzila_transaction_id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to update payment status: {e}")
        return False


def get_payment_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get user's payment history.
    
    Args:
        user_id: User's ID
        limit: Maximum number of records to return
    
    Returns:
        List of payment records
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM payments
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch payment history for user {user_id}: {e}")
        return []


# --- Admin Functions ---

def get_all_web_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get all web users (for admin dashboard).
    
    Args:
        limit: Maximum number of users to return
        offset: Pagination offset
    
    Returns:
        List of user records
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.id, u.email, u.telegram_chat_id, u.created_at, u.last_login,
                    s.is_active, s.subscription_end_date, s.plan
                FROM web_users u
                LEFT JOIN subscribers s ON u.telegram_chat_id = s.telegram_chat_id
                ORDER BY u.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch all users: {e}")
        return []


def get_user_count() -> int:
    """
    Get total number of web users.
    
    Returns:
        Total user count
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM web_users")
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to get user count: {e}")
        return 0


# --- Email Verification ---

def create_verification_token(user_id: int) -> Optional[str]:
    """
    Create an email verification token for a user.
    
    Args:
        user_id: User's ID
    
    Returns:
        Verification token if successful, None otherwise
    """
    import secrets
    
    try:
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)  # 24 hour expiry
        
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO email_verification_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, token, expires_at))
            conn.commit()
        
        logger.info(f"Created verification token for user {user_id}")
        return token
    
    except Exception as e:
        logger.error(f"Failed to create verification token: {e}")
        return None


def verify_email_token(token: str) -> Optional[int]:
    """
    Verify an email token and mark user as verified.
    
    Args:
        token: Verification token
    
    Returns:
        User ID if successful, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if token exists and is valid
            cursor.execute("""
                SELECT user_id, expires_at, used_at
                FROM email_verification_tokens
                WHERE token = ?
            """, (token,))
            
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Invalid verification token: {token}")
                return None
            
            user_id = row["user_id"]
            expires_at = datetime.fromisoformat(row["expires_at"]) if isinstance(row["expires_at"], str) else row["expires_at"]
            used_at = row["used_at"]
            
            # Check if already used
            if used_at:
                logger.warning(f"Token already used: {token}")
                return None
            
            # Check if expired
            if datetime.now() > expires_at:
                logger.warning(f"Token expired: {token}")
                return None
            
            # Mark token as used
            cursor.execute("""
                UPDATE email_verification_tokens
                SET used_at = ?
                WHERE token = ?
            """, (datetime.now(), token))
            
            # Mark user as verified
            cursor.execute("""
                UPDATE web_users
                SET is_verified = 1
                WHERE id = ?
            """, (user_id,))
            
            conn.commit()
            
            logger.info(f"Email verified for user {user_id}")
            return user_id
    
    except Exception as e:
        logger.error(f"Failed to verify email token: {e}")
        return None


def resend_verification_email(user_id: int) -> Optional[str]:
    """
    Create a new verification token for resending email.
    Invalidates any previous unused tokens.
    
    Args:
        user_id: User's ID
    
    Returns:
        New verification token if successful, None otherwise
    """
    try:
        with get_db_connection() as conn:
            # Invalidate old tokens (mark as used)
            conn.execute("""
                UPDATE email_verification_tokens
                SET used_at = ?
                WHERE user_id = ? AND used_at IS NULL
            """, (datetime.now(), user_id))
            conn.commit()
        
        # Create new token
        return create_verification_token(user_id)
    
    except Exception as e:
        logger.error(f"Failed to resend verification email: {e}")
        return None
