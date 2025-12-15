
import sqlite3
import datetime
from typing import List, Optional, Any, Dict
import json
from contextlib import contextmanager

# Schema Definitions

CREATE_SUBSCRIBERS_TABLE = """
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    plan TEXT DEFAULT 'free',
    subscription_end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_USER_PORTFOLIOS_TABLE = """
CREATE TABLE IF NOT EXISTS user_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT DEFAULT 'US',
    UNIQUE(telegram_chat_id, ticker),
    FOREIGN KEY(telegram_chat_id) REFERENCES subscribers(telegram_chat_id)
);
"""

CREATE_TICKER_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS ticker_snapshots (
    ticker TEXT PRIMARY KEY,
    last_price REAL,
    last_rsi REAL,
    last_ema_short REAL,
    last_ema_long REAL,
    last_run_at TIMESTAMP,
    last_action TEXT,
    last_summary_json TEXT
);
"""

CREATE_FUNDAMENTALS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS fundamentals_cache (
    ticker TEXT PRIMARY KEY,
    source TEXT,
    last_updated TIMESTAMP,
    data_json TEXT,
    period TEXT
);
"""

CREATE_FILINGS_CHECKPOINT_TABLE = """
CREATE TABLE IF NOT EXISTS filings_checkpoint (
    ticker TEXT PRIMARY KEY,
    source TEXT,
    last_checked TIMESTAMP,
    last_accession_or_id TEXT,
    last_filing_date TEXT,
    filings_json TEXT
);
"""

CREATE_NEWS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS news_cache (
    ticker TEXT PRIMARY KEY,
    source TEXT,
    last_checked TIMESTAMP,
    items_json TEXT
);
"""

ALL_TABLES = [
    CREATE_SUBSCRIBERS_TABLE,
    CREATE_USER_PORTFOLIOS_TABLE,
    CREATE_TICKER_SNAPSHOTS_TABLE,
    CREATE_FUNDAMENTALS_CACHE_TABLE,
    CREATE_FILINGS_CHECKPOINT_TABLE,
    CREATE_NEWS_CACHE_TABLE
]
