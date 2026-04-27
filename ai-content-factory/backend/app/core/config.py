"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "changeme-min-32-chars-secret-key-here"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production" and self.SECRET_KEY == _DEFAULT_SECRET_KEY:
            raise ValueError("SECRET_KEY must be changed from the default value in production")
        return self

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ai_content_factory"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/ai_content_factory"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Security
    SECRET_KEY: str = "changeme-min-32-chars-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/auth/callback"

    # YouTube
    YOUTUBE_API_KEY: str = ""

    # Groq (primary AI — free, fastest)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # OpenRouter (fallback 1 & 2)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_FALLBACK_MODEL: str = "openai/gpt-4o-mini"

    # Whisper
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # ACRCloud
    ACRCLOUD_HOST: str = ""
    ACRCLOUD_ACCESS_KEY: str = ""
    ACRCLOUD_ACCESS_SECRET: str = ""

    # Notifications
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@yourdomain.com"

    # Storage
    STORAGE_TYPE: Literal["local", "s3", "r2"] = "local"
    LOCAL_STORAGE_PATH: str = "./storage"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET: str = ""
    CLOUDFLARE_R2_ENDPOINT: str = ""

    # App
    APP_ENV: Literal["development", "production", "test"] = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_VIDEO_SIZE_GB: float = 10.0
    MAX_VIDEO_DURATION_HOURS: float = 3.0

    @property
    def max_video_size_bytes(self) -> int:
        return int(self.MAX_VIDEO_SIZE_GB * 1024 * 1024 * 1024)

    @property
    def max_video_duration_seconds(self) -> int:
        return int(self.MAX_VIDEO_DURATION_HOURS * 3600)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
