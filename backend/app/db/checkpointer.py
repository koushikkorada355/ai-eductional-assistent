import asyncio

from loguru import logger
import psycopg

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings


# Neon (serverless Postgres) closes idle SSL connections. A pool that holds
# connections open indefinitely will hand the checkpointer a dead connection,
# surfacing as: psycopg.OperationalError: SSL connection has been closed
# unexpectedly. Mitigate on two layers:
#  1. TCP keepalives + idle/lifetime recycling so connections rarely go stale.
#  2. reset-and-retry around graph invocations (robust_ainvoke) for stragglers.


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


def _pool_kwargs() -> dict:
    return {
        "autocommit": True,
        # TCP keepalives: detect server-side idle kills (Neon) early.
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        # Generous: a suspended Neon compute needs seconds to resume on connect.
        "connect_timeout": 30,
    }


def _open_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=get_psycopg_conninfo(settings.DATABASE_URL),
        kwargs=_pool_kwargs(),
        min_size=1,
        # Recycle idle connections well before Neon kills them, and rotate
        # long-lived ones. Checkout waits at most `timeout` for a slot.
        max_idle=120,
        max_lifetime=30 * 60,
        timeout=30,
    )


pool = None
checkpointer = None
# Serializes pool resets so concurrent failing requests reset only once.
# Created lazily (asyncio.Lock needs a running loop).
_reset_lock = None


def _get_reset_lock() -> asyncio.Lock:
    global _reset_lock
    if _reset_lock is None:
        _reset_lock = asyncio.Lock()
    return _reset_lock


try:
    # Creating the pool requires a running event loop in some contexts
    # (e.g. Celery forked workers).
    # Fall back to lazy initialization there.
    pool = _open_pool()

    checkpointer = AsyncPostgresSaver(pool)

except RuntimeError as e:
    logger.warning(
        f"Deferring checkpointer init (no event loop at import): {e}"
    )


async def setup_checkpointer():
    global pool, checkpointer

    if pool is None:
        pool = _open_pool()

        checkpointer = AsyncPostgresSaver(pool)

    try:
        await pool.open()
    except Exception as e:
        # Pool may already be open (auto-opened at import inside a running
        # loop) — setup() below will prove whether it is usable.
        logger.info(f"[checkpointer] pool open skipped ({e})")

    await checkpointer.setup()


def _swap_saver_pool(saver, old_pool, new_pool) -> bool:
    """Re-point an existing saver at a new pool (identity-based, version-tolerant).

    Compiled LangGraph apps hold a reference to the saver created at import, so
    replacing the saver object is not enough — the saver itself must use the new
    pool. Matches whichever attribute currently holds the old pool."""
    swapped = False
    for attr in ("conn", "pool", "_pool", "_conn", "connection"):
        try:
            if getattr(saver, attr, None) is old_pool:
                setattr(saver, attr, new_pool)
                swapped = True
        except Exception:
            continue
    return swapped


async def reset_checkpointer_pool() -> None:
    """Replace a stale pool with a fresh one.

    NOTE: psycopg_pool pools cannot be closed-then-reopened (PoolClosed), so a
    brand-new pool object is created and the existing saver is re-pointed at it.
    Already-compiled graphs keep working because they hold the saver, not the pool.
    Safe under concurrency: only the first resetter rebuilds; others reuse it.
    """
    global pool
    old_pool = pool
    if old_pool is None:
        return
    async with _get_reset_lock():
        if pool is not old_pool:
            return  # another request already reset
        new_pool = _open_pool()
        try:
            await new_pool.open()
        except Exception as e:
            logger.error(f"[checkpointer] fresh pool failed to open: {e}")
            try:
                await new_pool.close()
            except Exception:
                pass
            raise
        if checkpointer is not None:
            if not _swap_saver_pool(checkpointer, old_pool, new_pool):
                logger.error("[checkpointer] saver pool swap found no matching attribute")
            try:
                await checkpointer.setup()
            except Exception as e:
                logger.warning(f"[checkpointer] setup on fresh pool skipped: {e}")
        pool = new_pool
        try:
            await old_pool.close()
        except Exception as e:
            logger.warning(f"[checkpointer] old pool close during reset: {e}")
    logger.success("[checkpointer] pool replaced after stale connection")


async def robust_ainvoke(app, *args, **kwargs):
    """Invoke a Postgres-checkpointed graph, surviving stale pooled connections.

    On psycopg.OperationalError (e.g. Neon's idle SSL kill), the pool is reset
    and the invocation is retried exactly once before re-raising."""
    try:
        return await app.ainvoke(*args, **kwargs)
    except psycopg.OperationalError as e:
        logger.warning(f"[checkpointer] stale connection ({e}); resetting pool and retrying once")
        await reset_checkpointer_pool()
        return await app.ainvoke(*args, **kwargs)