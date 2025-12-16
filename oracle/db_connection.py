"""
Database connection manager supporting both SQLite (dev) and PostgreSQL (production).
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator, Any
from oracle.config import settings

logger = logging.getLogger(__name__)

# Check if psycopg2 is available
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not installed. PostgreSQL support disabled.")


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """
    Context manager for database connections.
    Automatically uses PostgreSQL if DATABASE_URL is set, otherwise SQLite.
    """
    if settings.use_postgres:
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("PostgreSQL configured but psycopg2 not installed!")
        
        # PostgreSQL connection
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.set_session(autocommit=False)
        # Use RealDictCursor for dict-like row access
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL transaction failed: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        # SQLite connection (development)
        conn = sqlite3.connect(settings.DB_PATH)
        conn.row_factory = sqlite3.Row
        
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite transaction failed: {e}")
            raise
        finally:
            conn.close()


def get_placeholder() -> str:
    """
    Get the correct SQL placeholder for the current database.
    PostgreSQL uses %s, SQLite uses ?
    """
    return "%s" if settings.use_postgres else "?"


def convert_query(query: str) -> str:
    """
    Convert SQLite query to PostgreSQL compatible query.
    Replaces ? placeholders with %s for PostgreSQL.
    """
    if settings.use_postgres:
        return query.replace("?", "%s")
    return query
