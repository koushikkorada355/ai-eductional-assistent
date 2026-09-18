"""Celery app + worker logging.

Read this first when "works local, worker Crashed in prod":
  1. `... | worker | boot | ...`   — what THIS worker process actually saw
     (env lengths, redis/db host, upload dir, ping results). Missing env or
     bad REDIS_URL shows up here, before any job runs.
  2. `[JOB <task>|id=..|task=..] received/started` — broker delivered the job.
     If boot is fine but no JOB lines appear, web+worker are on different
     REDIS_URL (or worker scaled to 0). Check GET /health/queue.
  3. `[JOB ...] phase=...` — step-by-step progress inside the task.
  4. `[JOB ...] done|failed duration=..s` — terminal outcome + timing.
  5. `[WORKER] ...` — ready/shutdown/revoked/crash lines.

All lines go to stdout (Railway keeps only stdout/stderr), plain text in
prod (no ANSI colors), secrets never logged (hosts + lengths only).
"""
from urllib.parse import urlsplit
import time

from celery import Celery, Task
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_revoked,
    worker_ready,
    worker_shutdown,
)
from loguru import logger

from app.core.logging_config import log_boot_diagnostics, setup_logging

setup_logging("worker")

from app.config import settings  # noqa: E402  (logging first so FATAL is visible)


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


def _job_id_of(args, kwargs) -> str:
    """First positional arg is the entity id in every task here (doc/quiz/...)."""
    try:
        if args:
            return str(args[0])[:36]
        for key in ("document_id", "quiz_id", "assignment_id", "project_id", "chat_session_id", "quiz_question_id"):
            if isinstance(kwargs, dict) and kwargs.get(key):
                return str(kwargs[key])[:36]
    except Exception:
        pass
    return "n/a"


_raw_redis = get_live_redis_url()
if not _raw_redis:
    logger.warning(
        "[WORKER] boot | REDIS_URL is not set — Celery dispatch will fail with 'worker unreachable'. "
        "Local: redis://redis:6379/0 via docker-compose. "
        "Railway: copy the Redis service internal URL into BOTH web and worker env, then restart web. "
        "The worker stays alive and keeps retrying the broker (see boot banner below)."
    )
else:
    logger.info(f"[WORKER] boot | Celery Redis: {_redacted_redis_url(_raw_redis)}")

# Full boot banner (env presence, ping results). This is the line to paste
# when asking why prod crashed — it names the missing/bad layer directly.
try:
    log_boot_diagnostics("worker")
except Exception as _e:  # never let diagnostics crash the worker
    logger.warning(f"[WORKER] boot | diagnostics skipped: {_e}")


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
            logger.warning(f"[WORKER] broker | could not update Celery broker URL: {e}")
        # Drop cached connections holding the old host/auth.
        for attempt in (
            lambda: celery_app.pool and celery_app.pool.force_close_all(),
            lambda: celery_app.backend.client and celery_app.backend.client.connection_pool.disconnect(),
        ):
            try:
                attempt()
            except Exception:
                pass
        logger.info(f"[WORKER] broker | refreshed: {_redacted_redis_url(live)} (was {_redacted_redis_url(current)})")
    return live


class BaseTask(Task):
    # We track progress in Postgres (Document.status/error), never via
    # AsyncResult — so tasks must not require the result backend at
    # dispatch time. A dead result store must never block uploads.
    ignore_result = True

    def __call__(self, *args, **kwargs):
        jid = _job_id_of(args, kwargs)
        task_id = getattr(self.request, "id", "n/a") or "n/a"
        logger.info(
            f"[JOB {self.name}|id={jid[:8]}|task={str(task_id)[:8]}] started "
            f"args={str(args)[:160]} kwargs={str(kwargs)[:160]}"
        )
        self._job_start = time.monotonic()
        try:
            return super().__call__(*args, **kwargs)
        except Exception as e:
            dt = time.monotonic() - getattr(self, "_job_start", time.monotonic())
            logger.opt(exception=True).error(
                f"[JOB {self.name}|id={jid[:8]}|task={str(task_id)[:8]}] raised "
                f"after {dt:.1f}s: {type(e).__name__}: {e}"
            )
            raise

    def on_success(self, retval, task_id, args, kwargs):
        jid = _job_id_of(args, kwargs)
        dt = time.monotonic() - getattr(self, "_job_start", time.monotonic())
        logger.success(
            f"[JOB {self.name}|id={jid[:8]}|task={str(task_id)[:8]}] done "
            f"in {dt:.1f}s -> {str(retval)[:200]}"
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        jid = _job_id_of(args, kwargs)
        dt = time.monotonic() - getattr(self, "_job_start", time.monotonic())
        logger.opt(exception=einfo).error(
            f"[JOB {self.name}|id={jid[:8]}|task={str(task_id)[:8]}] FAILED "
            f"after {dt:.1f}s: {type(exc).__name__}: {exc} | "
            f"args={str(args)[:160]} — Doc stays visible via status=failed/error in DB; "
            "if the WORKER process itself vanished (Crashed/OOMKilled/exit 137) instead, "
            "this line never prints — look for [WORKER] shutdown / memory lines above."
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        jid = _job_id_of(args, kwargs)
        logger.warning(
            f"[JOB {self.name}|id={jid[:8]}|task={str(task_id)[:8]}] retrying: "
            f"{type(exc).__name__}: {exc}"
        )


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
    # Crash rails for small Railway instances: a hung OCR/embedding run is
    # killed and marked failed (soft limit raises inside the task, which
    # _fail() catches) instead of wedging the 1-concurrency worker forever;
    # a child that grows past ~350MB is recycled before the node OOMs
    # (task requeues via acks_late, then hits the page/chunk caps honestly).
    task_soft_time_limit=540,
    task_time_limit=600,
    worker_max_memory_per_child=350_000,
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


# ---------------------------------------------------------------------------
# Worker / task lifecycle signals — the lines that explain a prod "Crashed".
# ---------------------------------------------------------------------------

@worker_ready.connect
def _log_worker_ready(sender=None, **kwargs):
    try:
        names = sorted(celery_app.tasks.keys())
    except Exception:
        names = []
    ours = [n for n in names if not n.startswith("celery.")]
    logger.success(
        f"[WORKER] ready | hostname={getattr(sender, 'hostname', '?')} "
        f"concurrency={getattr(getattr(sender, 'pool', None), 'num_processes', '?')} "
        f"broker={_redacted_redis_url(get_live_redis_url())} "
        f"tasks({len(ours)}): {', '.join(ours) or '<none registered!>'}"
    )
    if not ours:
        logger.error(
            "[WORKER] ready | NO app tasks registered — check Celery `include` list; "
            "jobs will sit in Redis with no consumer and docs stay 'queued'."
        )


@worker_shutdown.connect
def _log_worker_shutdown(sender=None, **kwargs):
    logger.warning(f"[WORKER] shutdown | hostname={getattr(sender, 'hostname', '?')} — jobs requeue via acks_late")


@task_prerun.connect
def _log_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **rest):
    name = getattr(sender, "name", getattr(task, "name", "?"))
    logger.info(
        f"[JOB {name}|id={_job_id_of(args or (), kwargs or {})[:8]}|task={str(task_id)[:8]}] "
        f"received — worker picked it up from broker {_redacted_redis_url(get_live_redis_url())}"
    )


@task_postrun.connect
def _log_task_postrun(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **rest):
    name = getattr(sender, "name", getattr(task, "name", "?"))
    logger.info(
        f"[JOB {name}|id={_job_id_of(args or (), kwargs or {})[:8]}|task={str(task_id)[:8]}] "
        f"postrun state={state} -> {str(retval)[:160]}"
    )


@task_failure.connect
def _log_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **rest):
    name = getattr(sender, "name", "?")
    logger.opt(exception=(type(exception), exception, traceback) if exception else einfo).error(
        f"[JOB {name}|id={_job_id_of(args or (), kwargs or {})[:8]}|task={str(task_id)[:8]}] "
        f"signal failure: {type(exception).__name__ if exception else '?'}: {exception}"
    )


@task_retry.connect
def _log_task_retry(sender=None, task_id=None, reason=None, request=None, einfo=None, **rest):
    name = getattr(sender, "name", "?")
    logger.warning(
        f"[JOB {name}|task={str(task_id)[:8]}] signal retry: {reason} "
        f"retries={getattr(request, 'retries', '?')}"
    )


@task_revoked.connect
def _log_task_revoked(sender=None, request=None, terminated=None, signum=None, expired=None, **rest):
    name = getattr(getattr(request, "task", None), "name", "?") if request else "?"
    logger.warning(
        f"[JOB {name}] revoked terminated={terminated} signum={signum} expired={expired} — "
        "job requeues via acks_late if it was running"
    )
