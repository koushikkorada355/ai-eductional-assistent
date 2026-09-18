"""Placeholder analytics jobs + worker self-test.

`worker.ping` is the cheapest prod check: dispatch it (or call it from
GET /health/queue in the future) and look for its DONE line in the worker
logs. If the line never appears, the worker is not consuming from the same
Redis as web — no need to upload a real PDF to learn that.
"""
import time

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="worker.ping", bind=True)
def worker_ping_task(self, note: str = "") -> str:
    t0 = time.monotonic()
    tid = str(getattr(getattr(self, "request", None), "id", "n/a"))[:8]
    logger.info(f"[JOB worker.ping|task={tid}] received note={note[:80]!r}")
    try:
        from app.core.logging_config import log_boot_diagnostics

        facts = log_boot_diagnostics("worker-ping")
        logger.success(
            f"[JOB worker.ping|task={tid}] DONE in {time.monotonic() - t0:.1f}s "
            f"redis={facts.get('redis')} db={facts.get('db')}"
        )
        return f"pong:{note[:50]}"
    except Exception as e:
        logger.opt(exception=True).error(f"[JOB worker.ping|task={tid}] FAILED: {e}")
        return f"failed:{e}"
