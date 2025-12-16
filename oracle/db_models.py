"""
Database schema definitions for SQLite.
Extended to support web users, payments, and sessions.
"""

# Original tables
CREATE_SUBSCRIBERS_TABLE = """
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1,
    subscription_end_date TIMESTAMP,
    plan TEXT DEFAULT 'basic',
    notification_pref TEXT DEFAULT 'standard',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_USER_PORTFOLIOS_TABLE = """
CREATE TABLE IF NOT EXISTS user_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_chat_id, ticker),
    FOREIGN KEY (telegram_chat_id) REFERENCES subscribers(telegram_chat_id)
)
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
    last_summary_json TEXT,
    last_trigger_type TEXT,
    last_trigger_at TIMESTAMP
)
"""

CREATE_FUNDAMENTALS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS fundamentals_cache (
    ticker TEXT PRIMARY KEY,
    source TEXT,
    last_updated TIMESTAMP,
    data_json TEXT,
    period TEXT DEFAULT 'latest'
)
"""

CREATE_NEWS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS news_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    title TEXT,
    url TEXT,
    source TEXT,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP
)
"""

CREATE_FILINGS_CHECKPOINT_TABLE = """
CREATE TABLE IF NOT EXISTS filings_checkpoint (
    ticker TEXT PRIMARY KEY,
    source TEXT DEFAULT 'SEC_EDGAR',
    last_checked TIMESTAMP,
    last_accession_or_id TEXT,
    last_filing_date TEXT,
    filings_json TEXT
)
"""

# NEW: Web users (for landing page authentication)
CREATE_WEB_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS web_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    telegram_chat_id INTEGER UNIQUE,
    is_active INTEGER DEFAULT 1,
    is_verified INTEGER DEFAULT 0,
    plan TEXT DEFAULT 'none',
    subscription_start_date TIMESTAMP,
    subscription_end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    FOREIGN KEY (telegram_chat_id) REFERENCES subscribers(chat_id)
)
"""

# NEW: Payment records
CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tranzila_transaction_id TEXT UNIQUE,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'ILS',
    status TEXT NOT NULL,
    payment_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY (user_id) REFERENCES web_users(id)
)
"""

# NEW: Active sessions (for JWT invalidation)
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES web_users(id)
)
"""

# NEW: API keys (for future API access feature)
CREATE_API_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key_hash TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES web_users(id)
)
"""

# NEW: Email verification tokens
CREATE_EMAIL_VERIFICATION_TABLE = """
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES web_users(id)
)
"""

# All tables list
ALL_TABLES = [
    CREATE_SUBSCRIBERS_TABLE,
    CREATE_USER_PORTFOLIOS_TABLE,
    CREATE_TICKER_SNAPSHOTS_TABLE,
    CREATE_FUNDAMENTALS_CACHE_TABLE,
    CREATE_NEWS_CACHE_TABLE,
    CREATE_FILINGS_CHECKPOINT_TABLE,
    CREATE_WEB_USERS_TABLE,
    CREATE_PAYMENTS_TABLE,
    CREATE_SESSIONS_TABLE,
    CREATE_API_KEYS_TABLE,
    CREATE_EMAIL_VERIFICATION_TABLE,
]
