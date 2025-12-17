from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str

    # Application Settings
    LOG_LEVEL: str = "INFO"
    DRY_RUN: bool = False
    
    # Database Configuration
    DATABASE_URL: Optional[str] = None  # PostgreSQL: postgresql://user:pass@host:5432/dbname
    DB_PATH: str = "subscribers.db"  # SQLite fallback for development
    
    @property
    def use_postgres(self) -> bool:
        """Check if PostgreSQL should be used instead of SQLite"""
        return self.DATABASE_URL is not None and self.DATABASE_URL.startswith("postgresql://")

    # LLM Models
    MODEL_BASIC: str = "gpt-4o-mini"
    MODEL_HQ: str = "gpt-4o"
    MAJOR_EVENT_THRESHOLD_PCT: float = 3.0

    # SEC & Data Source
    SEC_USER_AGENT: str = "AI Market Oracle (admin@example.com)"

    # Logic & Gating
    RUN_TIMES: List[str] = ["09:00", "14:00", "21:00"]
    MAX_LLM_TICKERS_PER_RUN: int = 10

    # Gate Thresholds
    PRICE_CHANGE_TRIGGER_PCT: float = 1.2
    RSI_OVERBOUGHT: int = 75
    RSI_OVERSOLD: int = 30
    RSI_DELTA_TRIGGER: int = 10

    ATR_WINDOW: int = 14
    VOLUME_WINDOW: int = 20
    VOL_SPIKE_MULTIPLIER: float = 2.0
    NEWS_TTL_MINUTES: int = 60

    # SEC EDGAR API
    FUNDAMENTALS_TTL_DAYS: int = 7

    COOLDOWN_HOURS: int = 4

    EMA_SHORT: int = 50
    EMA_LONG: int = 200
    NEWS_CACHE_MINUTES: int = 60

    # Data retention (cleanup)
    NEWS_RETENTION_DAYS: int = 30
    FUNDAMENTALS_RETENTION_DAYS: int = 30
    SESSION_RETENTION_DAYS: int = 30

    # Defaults
    DEFAULT_PLAN: str = "basic"

    # API & Web
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Tranzila Payment
    TRANZILA_TERMINAL: str = ""
    TRANZILA_API_KEY: str = ""
    TRANZILA_WEBHOOK_SECRET: str = ""
    PAYMENT_CURRENCY: str = "ILS"
    SUBSCRIPTION_PRICE: int = 29

    # AWS SES Email
    AWS_SES_REGION: str = "us-east-1"
    AWS_SES_FROM_EMAIL: str = "noreply@example.com"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""
    ADMIN_JWT_EXPIRY_MINUTES: int = 30

    # Security
    RATE_LIMIT_PER_MINUTE: int = 60
    PASSWORD_HASH_ROUNDS: int = 12
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

settings = Settings()
