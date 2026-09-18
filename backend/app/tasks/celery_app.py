from urllib.parse import urlsplit
from celery import Celery, Task
from loguru import logger
from app.config import settings


def _redacted_redis_url(url: str | None) -> str:
    """Host-only form for logs (never leak password)."""
    if not url:
        return "<unset>"
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        scheme = parts.scheme or "?"
        return f"{scheme}://{host}{port}/{parts.path.lstrip('/') or ''}".rstrip("/")
    except Exception:
        return "<unparseable>"


def get_live_redis_url() -> str | None:
    """Live REDIS_URL (env wins so a changed value works even if settings was imported earlier)."""
    import os

    for candidate in (os.getenv("REDIS_URL"), getattr(settings, "REDIS_URL", None)):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _ssl_opts_for(url: str | None) -> dict:
    # Railway often issues rediss:// (TLS). Without these Celery/redis fail handshake.
    try:
        if (url or "").lower().startswith("rediss://"):
            return {"ssl_cert_reqs": "required"}
    except Exception:
        pass
    return {}


_raw_redis = get_live_redis_url()
if not _raw_redis:
    logger.warning(
        "REDIS_URL is not set — Celery dispatch will fail with 'worker unreachable'. "
        "Local: redis://redis:6379/0 via docker-compose. "
        "Railway: copy the Redis service internal URL into BOTH web and worker env, then restart web."
    )
else:
    logger.info(f"Celery Redis: {_redacted_redis_url(_raw_redis)}")


def refresh_broker_from_env() -> str | None:
    """Point Celery at the current REDIS_URL and drop stale pooled connections.

    Call before every dispatch/ping so a changed URL takes effect without
    requiring a full process restart to clear Kombu's cached 'must be
    restarted' connection. Returns the live URL (or None if unset).
    """
    live = get_live_redis_url()
    try:
        current = celery_app.conf.broker_url
    except Exception:
        current = None
    if live != current:
        try:
            celery_app.conf.broker_url = live
            celery_app.conf.result_backend = live
            ssl_opts = _ssl_opts_for(live)
            celery_app.conf.broker_use_ssl = ssl_opts or None
            celery_app.conf.redis_backend_use_ssl = ssl_opts or None
        except Exception as e:
            logger.warning(f"Could not update Celery broker URL: {e}")
        # Drop cached connections holding the old host/auth.
        for attempt in (
            lambda: celery_app.pool and celery_app.pool.force_close_all(),
            lambda: celery_app.backend.client and celery_app.backend.client.connection_pool.disconnect(),
        ):
            try:
                attempt()
            except Exception:
                pass
        logger.info(f"Celery broker refreshed: {_redacted_redis_url(live)} (was {_redacted_redis_url(current)})")
    return live


class BaseTask(Task):
    # We track progress in Postgres (Document.status/error), never via
    # AsyncResult — so tasks must not require the result backend at
    # dispatch time. A dead result store must never block uploads.
    ignore_result = True

    def __call__(self, *args, **kwargs):
        logger.info(f"Task starting: {self.name}")
        return super().__call__(*args, **kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        logger.success(f"Task succeeded: {self.name} [{task_id}]")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task failed: {self.name} [{task_id}] - {exc}")


celery_app = Celery(
    "ai_study_companion",
    broker=_raw_redis,
    backend=_raw_redis,
    task_cls=BaseTask,
    include=["app.tasks.document_tasks", "app.tasks.concept_tasks", "app.tasks.quiz_tasks", "app.tasks.assignment_tasks", "app.tasks.analytics_tasks", "app.tasks.learning_tasks"],
)
# TLS for rediss:// URLs (Railway public endpoint). Private redis:// needs none.
try:
    _ssl = _ssl_opts_for(_raw_redis)
    if _ssl:
        celery_app.conf.broker_use_ssl = _ssl
        celery_app.conf.redis_backend_use_ssl = _ssl
except Exception:
    pass

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    # Requeue in-flight tasks if the worker restarts, so uploads can never
    # get stranded in 'queued' during deploys.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Status lives in Postgres — never block dispatch on the result store.
    task_ignore_result=True,
    result_extended=False,
    result_expires=3600,
    # Web publish path fails fast on its own: materials.py pings Redis (3s)
    # before apply_async, and .delay()/apply_async default to retry=False
    # (single attempt, raises immediately). So the WORKER may retry the
    # broker forever here without making web requests hang: a boot race
    # (Redis not up yet) or a redeploy must never exit the worker as
    # "Crashed" — previously max_retries=3 killed it after ~seconds.
    broker_connection_timeout=5,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    redis_socket_timeout=5,
    redis_socket_connect_timeout=5,
    redis_retry_on_timeout=True,
    broker_transport_options={
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
        "max_connections": 10,
    },
    result_backend_transport_options={
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
        "max_connections": 10,
    },
)
