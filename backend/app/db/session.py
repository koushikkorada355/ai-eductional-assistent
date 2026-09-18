from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Neon/Railway-proof DSN: postgres:// -> postgresql://, strip quotes/space.

    Keeps ?sslmode=require intact. Defense-in-depth alongside the
    config.py validator so engine creation never sees a driver-less scheme.
    """
    u = (url or "").strip().strip('"').strip("'")
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    return u


engine = create_engine(
    _normalize_db_url(settings.DATABASE_URL),
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()