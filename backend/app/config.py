from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys
from loguru import logger


class Settings(BaseSettings):
    # PostgreSQL / Neon
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str = Field(
        validation_alias=AliasChoices(
            "SECRET_KEY",
            "JWT_SECRET_KEY"
        )
    )

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Groq
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str | None = None

    # Inception Labs / Mercury
    INCEPTION_API_KEY: str | None = None
    INCEPTION_MODEL: str | None = "mercury-2.5"
    INCEPTION_BASE_URL: str | None = "https://api.inceptionlabs.ai/v1"

    # LangSmith
    LANGCHAIN_TRACING_V2: bool | None = None
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str | None = None
    LANGCHAIN_ENDPOINT: str | None = None

    # Redis
    REDIS_URL: str | None = None

    # Google
    GOOGLE_API_KEY: str | None = None

    # ColiVara
    COLIVARA_API_KEY: str | None = None

    # OCR
    OCR_API_KEY: str | None = None

    # Default admin account
    ADMIN_EMAIL: str = "admin@gmail.com"
    ADMIN_PASSWORD: str = "12345"
    ADMIN_NAME: str = "admin"

    # CORS: public frontend URL on Railway/Vercel (comma-separated allowed).
    # Local dev keeps working without it (localhost + LAN regex in main.py).
    FRONTEND_URL: str | None = None

    # Upload storage: absolute dir shared by web + worker.
    # Local dev defaults to ./uploads. Production (Railway) must mount the
    # SAME volume into web and worker at /data/uploads and set
    # UPLOAD_DIR=/data/uploads on both services.
    UPLOAD_DIR: str | None = None
    # Reject oversized PDFs early so one huge upload can't OOM the worker.
    MAX_UPLOAD_MB: int = 25

    # Pydantic settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()


# Fail fast if required variables are missing
if not settings.SECRET_KEY or not settings.DATABASE_URL:
    logger.error(
        "FATAL: DATABASE_URL or SECRET_KEY is missing from environment!"
    )
    sys.exit(1)