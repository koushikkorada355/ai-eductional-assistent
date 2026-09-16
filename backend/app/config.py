from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys
from loguru import logger

class Settings(BaseSettings):
    # Pydantic will automatically read these from the environment variables
    DATABASE_URL: str
    SECRET_KEY: str = Field(validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"))
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str | None = None
    LANGCHAIN_TRACING_V2: bool | None = None
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str | None = None
    LANGCHAIN_ENDPOINT: str | None = None
    REDIS_URL: str | None = None
    GOOGLE_API_KEY: str | None = None

    # We tell Pydantic to look for a .env file, but Docker will inject the env vars directly
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra='ignore')

settings = Settings()

# Fail fast if variables are missing
if not settings.SECRET_KEY or not settings.DATABASE_URL:
    logger.error("FATAL: DATABASE_URL or SECRET_KEY is missing from environment!")
    sys.exit(1)