from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    BOT_TOKEN: str
    DATABASE_URL: str
    OWNER_TELEGRAM_ID: int = 6142120016

    # Цех — Dania Beach, FL
    WORKSHOP_LAT: float = 25.9950
    WORKSHOP_LON: float = -80.1426
    WORKSHOP_NAME: str = "Цех — Dania Beach"
    WORKSHOP_ADDRESS: str = "1300 Stirling Rd 3a-3b, Dania Beach, FL 33004"

    GEO_RADIUS_METERS: int = 150
    APP_ENV: str = "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
