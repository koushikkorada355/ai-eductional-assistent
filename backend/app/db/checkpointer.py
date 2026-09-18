from loguru import logger

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings


def get_psycopg_conninfo(url: str) -> str:
    """Strip SQLAlchemy driver prefix for raw psycopg usage.

    SQLAlchemy uses ``postgresql+psycopg://...`` but psycopg_pool /
    libpq only understand ``postgresql://...``. Passing the former
    causes: invalid connection option "postgresql+psycopg://...".
    """
    if "://" in url and "+" in url.split("://")[0]:
        scheme, rest = url.split("://", 1)
        dialect = scheme.split("+")[0]
        return f"{dialect}://{rest}"
    return url


pool = None
checkpointer = None


try:
    # Creating the pool requires a running event loop in some contexts
    # (e.g. Celery forked workers).
    # Fall back to lazy initialization there.
    pool = AsyncConnectionPool(
        conninfo=get_psycopg_conninfo(settings.DATABASE_URL),
        kwargs={"autocommit": True}
    )

    checkpointer = AsyncPostgresSaver(pool)

except RuntimeError as e:
    logger.warning(
        f"Deferring checkpointer init (no event loop at import): {e}"
    )


async def setup_checkpointer():
    global pool, checkpointer

    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=get_psycopg_conninfo(settings.DATABASE_URL),
            kwargs={"autocommit": True}
        )

        checkpointer = AsyncPostgresSaver(pool)

    await pool.open()

    await checkpointer.setup()