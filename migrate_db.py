"""
Database Migration Script
Adds missing columns to existing database.
Run this after updating db_models.py
"""
import sqlite3
import logging
from oracle.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_is_verified():
    """Add is_verified column to web_users table"""
    try:
        conn = sqlite3.connect(settings.DB_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(web_users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_verified' not in columns:
            logger.info("Adding is_verified column to web_users...")
            cursor.execute("""
                ALTER TABLE web_users 
                ADD COLUMN is_verified INTEGER DEFAULT 0
            """)
            conn.commit()
            logger.info("✅ is_verified column added successfully")
        else:
            logger.info("✓ is_verified column already exists")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def run_all_migrations():
    """Run all pending migrations"""
    logger.info("🔄 Running database migrations...")
    
    migrations = [
        migrate_add_is_verified,
    ]
    
    for migration in migrations:
        if not migration():
            logger.error(f"Migration {migration.__name__} failed!")
            return False
    
    logger.info("✅ All migrations completed successfully")
    return True


if __name__ == "__main__":
    run_all_migrations()
