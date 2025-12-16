#!/usr/bin/env python3
"""
Migration script: SQLite → PostgreSQL
Migrates all data from SQLite database to PostgreSQL.

Usage:
    python3 migrate_to_postgres.py
"""
import sqlite3
import psycopg2
import psycopg2.extras
import os
from oracle.config import settings
from oracle.db_models import ALL_TABLES

def migrate_sqlite_to_postgres():
    """
    Migrate all data from SQLite to PostgreSQL.
    """
    if not settings.DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in .env")
        print("Set it to: postgresql://oracle:password@localhost:5432/oracle")
        return False
    
    sqlite_path = settings.DB_PATH
    if not os.path.exists(sqlite_path):
        print(f"❌ ERROR: SQLite database not found: {sqlite_path}")
        return False
    
    print("🔄 Starting migration from SQLite to PostgreSQL...")
    print(f"   Source: {sqlite_path}")
    print(f"   Target: {settings.DATABASE_URL}")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    pg_conn = psycopg2.connect(settings.DATABASE_URL)
    pg_cursor = pg_conn.cursor()
    
    try:
        # 1. Create tables in PostgreSQL
        print("\n📦 Creating tables in PostgreSQL...")
        for table_sql in ALL_TABLES:
            # Convert SQLite SQL to PostgreSQL
            pg_sql = table_sql.replace("AUTOINCREMENT", "SERIAL")
            pg_sql = pg_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            
            try:
                pg_cursor.execute(pg_sql)
                print(f"   ✓ Created table")
            except Exception as e:
                print(f"   ⚠ Table may already exist: {e}")
        
        pg_conn.commit()
        
        # 2. Get list of tables
        tables_to_migrate = [
            'subscribers',
            'user_portfolios',
            'ticker_snapshots',
            'fundamentals_cache',
            'news_cache',
            'filings_checkpoint',
            'web_users',
            'payments',
            'sessions',
            'api_keys'
        ]
        
        # 3. Migrate data table by table
        print("\n📊 Migrating data...")
        total_rows = 0
        
        for table_name in tables_to_migrate:
            # Check if table exists in SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            
            if not sqlite_cursor.fetchone():
                print(f"   ⏭ Skipping {table_name} (doesn't exist in SQLite)")
                continue
            
            # Get all rows from SQLite
            sqlite_cursor.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"   ⏭ {table_name}: 0 rows")
                continue
            
            # Get column names
            columns = [description[0] for description in sqlite_cursor.description]
            
            # Insert into PostgreSQL
            placeholders = ', '.join(['%s'] * len(columns))
            insert_sql = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            for row in rows:
                pg_cursor.execute(insert_sql, tuple(row))
            
            pg_conn.commit()
            total_rows += len(rows)
            print(f"   ✓ {table_name}: {len(rows)} rows")
        
        print(f"\n✅ Migration completed successfully!")
        print(f"   Total rows migrated: {total_rows}")
        
        # 4. Verify migration
        print("\n🔍 Verifying migration...")
        for table_name in tables_to_migrate:
            try:
                pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = pg_cursor.fetchone()[0]
                if count > 0:
                    print(f"   ✓ {table_name}: {count} rows")
            except:
                pass
        
        print("\n✅ All done! PostgreSQL is ready to use.")
        print("\n⚠️  IMPORTANT: Update your .env file:")
        print(f"   DATABASE_URL={settings.DATABASE_URL}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        pg_conn.rollback()
        return False
        
    finally:
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate_sqlite_to_postgres()
