from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str

    # Application Settings
    LOG_LEVEL: str = "INFO"
    DRY_RUN: bool = False
    DB_PATH: str = "subscribers.db"
    
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
    
    COOLDOWN_HOURS: int = 4
    
    EMA_SHORT: int = 50
    EMA_LONG: int = 200
    NEWS_CACHE_MINUTES: int = 60
    
    # Defaults
    DEFAULT_PLAN: str = "basic"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
