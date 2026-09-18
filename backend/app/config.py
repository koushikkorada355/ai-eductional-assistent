from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys
from loguru import logger


class Settings(BaseSettings):
    # PostgreSQL / Neon (single Railway container talks to hosted Neon).
    # Accepts Neon/Railway variants: postgres:// -> postgresql://,
    # keeps ?sslmode=require. Stripped so copy-paste stays safe.
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v):
        if isinstance(v, str):
            v = v.strip().strip('"').strip("'")
            if v.startswith("postgres://"):
                v = "postgresql://" + v[len("postgres://"):]
            return v
        return v

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

    # Redis (Celery broker + result backend). Strip stray whitespace/newlines
    # from copy-pasted Railway values — trailing spaces break connections.
    REDIS_URL: str | None = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def _strip_redis(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

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


def _env_presence_report() -> str:
    """Names + lengths only (never values) of env vars reaching this process.

    Proves whether Railway actually injected Variables into THIS service.
    Catches the classic traps: vars set on web but not worker, wrong
    environment, typos (DATABASEURL vs DATABASE_URL), or added-but-not-redeployed.
    """
    import difflib
    import os

    watched = ("DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY", "REDIS_URL",
               "GOOGLE_API_KEY", "INCEPTION_API_KEY", "UPLOAD_DIR", "FRONTEND_URL")
    parts = []
    for name in watched:
        val = os.getenv(name)
        if val is None:
            parts.append(f"{name}=<absent>")
        elif not val.strip():
            parts.append(f"{name}=<empty>")
        else:
            parts.append(f"{name}=set({len(val.strip())} chars)")
    # Spot typos: near-miss key names actually present in the environment.
    try:
        env_keys = list(os.environ.keys())
        for want in ("DATABASE_URL", "SECRET_KEY", "REDIS_URL"):
            if os.getenv(want) or (want == "SECRET_KEY" and os.getenv("JWT_SECRET_KEY")):
                continue
            close = difflib.get_close_matches(want, env_keys, n=2, cutoff=0.7)
            # Also catch case/underscore variants difflib misses (e.g. databaseurl).
            if not close:
                norm = want.lower().replace("_", "")
                close = [k for k in env_keys if k.lower().replace("_", "") == norm][:2]
            if close:
                parts.append(f"hint: found {close} — did you mean {want}? (names are exact, uppercase)")
    except Exception:
        pass
    return "; ".join(parts)


try:
    settings = Settings()
except Exception as e:
    # Actionable boot error: raw pydantic tracebacks hide which Railway
    # service env is incomplete. Worker and web need the SAME values —
    # docker-compose shares .env, Railway services do NOT.
    missing: list[str] = []
    try:
        from pydantic import ValidationError as _VE

        if isinstance(e, _VE):
            missing = sorted({str(err.get("loc", ("?",))[0]) for err in e.errors() if err.get("loc")})
    except Exception:
        pass
    logger.error(
        "FATAL: missing required environment: "
        f"{', '.join(missing) if missing else e}. "
        f"Process env seen: {_env_presence_report()}. "
        "Fix: Variables must be on THIS service (a split worker has its own Variables tab — "
        "web vars do NOT flow to it), same environment, then REDEPLOY (new vars need a new "
        "deployment to reach the process). Best: link one shared env group to web+worker. "
        "Local fix: ensure .env exists (see .env.example)."
    )
    sys.exit(1)


# Fail fast if required variables are missing
if not settings.SECRET_KEY or not settings.DATABASE_URL:
    logger.error(
        "FATAL: DATABASE_URL or SECRET_KEY is missing from environment! "
        "Fix: copy both into THIS service Variables (split worker needs its own copy) and redeploy."
    )
    sys.exit(1)