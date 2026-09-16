from loguru import logger
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

pool = None
checkpointer = None

try:
    # Creating the pool requires a running event loop in some contexts
    # (e.g. Celery forked workers). Fall back to lazy init there; the
    # batch/eval helpers only need plain DB sessions, not the saver.
    pool = AsyncConnectionPool(conninfo=settings.DATABASE_URL, kwargs={"autocommit": True})
    checkpointer = AsyncPostgresSaver(pool)
except RuntimeError as e:
    logger.warning(f"Deferring checkpointer init (no event loop at import): {e}")


async def setup_checkpointer():
    global pool, checkpointer
    if pool is None:
        pool = AsyncConnectionPool(conninfo=settings.DATABASE_URL, kwargs={"autocommit": True})
        checkpointer = AsyncPostgresSaver(pool)
    await pool.open()
    await checkpointer.setup()
