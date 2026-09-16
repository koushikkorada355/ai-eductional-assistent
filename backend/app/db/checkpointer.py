from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

pool = AsyncConnectionPool(conninfo=settings.DATABASE_URL, kwargs={"autocommit": True})
checkpointer = AsyncPostgresSaver(pool)

async def setup_checkpointer():
    await pool.open()
    await checkpointer.setup()
