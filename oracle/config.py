from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    CALLMEBOT_API_KEY: Optional[str] = None

    # Application Settings
    LOG_LEVEL: str = "INFO"
    DRY_RUN: bool = False
    SCHEDULE_MINUTES: int = 240 # Default: Every 4 hours
    
    # Defaults
    DEFAULT_TICKERS: List[str] = ["QQQ", "NVDA", "TSLA", "LUMI.TA"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
