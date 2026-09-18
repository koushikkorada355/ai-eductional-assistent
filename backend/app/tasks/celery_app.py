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


_raw_redis = (getattr(settings, "REDIS_URL", None) or "").strip() or None
if not _raw_redis:
    logger.warning(
        "REDIS_URL is not set — Celery dispatch will fail with 'worker unreachable'. "
        "Local: redis://redis:6379/0 via docker-compose. "
        "Railway: copy the Redis service internal URL into BOTH web and worker env, then restart web."
    )
else:
    logger.info(f"Celery Redis: {_redacted_redis_url(_raw_redis)}")


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
    # Fail fast with a clear log instead of hanging the request for minutes
    # when Redis is unreachable (wrong host/password, service down).
    broker_connection_timeout=5,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=3,
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
