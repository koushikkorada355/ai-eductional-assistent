"""Central logging for web + Celery worker.

Railway only keeps stdout/stderr, so every background job must log there
with a plain (no-color) line that tells you:
  WHAT job, WHICH id, HOW LONG, and WHY it failed.

Usage:
    from app.core.logging_config import setup_logging
    setup_logging("worker")   # or "web"

Worker boot diagnostics:
    from app.core.logging_config import log_boot_diagnostics
    log_boot_diagnostics("worker")
"""
from __future__ import annotations

import logging
import os
import sys

from loguru import logger


_CONFIGURED: dict[str, bool] = {}


def _log_level() -> str:
    return (os.getenv("LOG_LEVEL") or "INFO").upper()


def _redact_url(url: str | None) -> str:
    """Host-only form for logs — never leak passwords/tokens."""
    if not url:
        return "<unset>"
    try:
        from urllib.parse import urlsplit

        parts = urlsplit(url.strip())
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        scheme = parts.scheme or "?"
        return f"{scheme}://{host}{port}"
    except Exception:
        return "<unparseable>"


def _env_presence(names: tuple[str, ...]) -> str:
    """set(N chars) / <absent> / <empty> per var — never values."""
    parts = []
    for name in names:
        val = os.getenv(name)
        if val is None:
            parts.append(f"{name}=<absent>")
        elif not val.strip():
            parts.append(f"{name}=<empty>")
        else:
            parts.append(f"{name}=set({len(val.strip())} chars)")
    return "; ".join(parts)


class _LoguruHandler(logging.Handler):
    """Route stdlib logs (celery, uvicorn, sqlalchemy) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = record.levelname
        except Exception:
            level = "INFO"
        try:
            logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())
        except Exception:
            pass


def setup_logging(service: str = "app") -> None:
    """Configure loguru once per process. Safe to call repeatedly."""
    if _CONFIGURED.get(service):
        return
    _CONFIGURED[service] = True

    try:
        logger.remove()
    except Exception:
        pass

    # Railway log viewer has no ANSI support — only colorize on a real TTY
    # (local docker-compose) so prod lines stay readable/greppable.
    colorize = sys.stdout.isatty()

    logger.add(
        sys.stdout,
        level=_log_level(),
        colorize=colorize,
        backtrace=False,
        diagnose=False,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            f"{service} | {{name}}:{{function}}:{{line}} - {{message}}"
        ),
    )

    # Bridge stdlib (celery/kombu/uvicorn) into the same stdout stream so
    # "worker crashed" always leaves a line, even outside our own tasks.
    try:
        handler = _LoguruHandler()
        for name in ("celery", "celery.worker", "celery.task", "kombu", "uvicorn", "uvicorn.error"):
            std = logging.getLogger(name)
            std.handlers[:] = [handler]
            std.setLevel(getattr(logging, _log_level(), logging.INFO))
            std.propagate = False
        root = logging.getLogger()
        if not any(isinstance(h, _LoguruHandler) for h in root.handlers):
            root.addHandler(handler)
    except Exception:
        pass

    # Uncaught exceptions in the worker child previously vanished (exit code
    # only). Force them onto stdout with service context.
    try:
        import threading

        def _thread_hook(args: threading.ExceptHookArgs) -> None:
            logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).error(
                f"[{service}] uncaught thread exception in {args.thread.name}"
            )

        threading.excepthook = _thread_hook
    except Exception:
        pass


def log_boot_diagnostics(service: str = "worker") -> dict:
    """Log one greppable boot banner. Returns the facts for tests/health.

    This is the first thing to read when "works local, crashed in prod":
    it proves which env values THIS process actually saw (lengths only),
    plus Redis/DB/UPLOAD reachability — without leaking secrets.
    Never raises.
    """
    import platform

    facts: dict = {}
    try:
        import celery as _celery

        celery_ver = getattr(_celery, "__version__", "?")
    except Exception:
        celery_ver = "?"

    watched = (
        "DATABASE_URL",
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "REDIS_URL",
        "GOOGLE_API_KEY",
        "INCEPTION_API_KEY",
        "GROQ_API_KEY",
        "UPLOAD_DIR",
        "FRONTEND_URL",
    )
    env_report = _env_presence(watched)
    facts["env"] = env_report

    redis_url = (os.getenv("REDIS_URL") or "").strip()
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    upload_dir = (os.getenv("UPLOAD_DIR") or "uploads").strip() or "uploads"
    facts["redis"] = _redact_url(redis_url) if redis_url else "<unset>"
    facts["db"] = _redact_url(db_url) if db_url else "<unset>"
    facts["upload_dir"] = os.path.abspath(upload_dir)

    logger.info(
        f"[{service}] boot | python={platform.python_version()} celery={celery_ver} "
        f"pid={os.getpid()} log_level={_log_level()}"
    )
    logger.info(f"[{service}] boot | env: {env_report}")
    logger.info(f"[{service}] boot | redis={facts['redis']} db={facts['db']} upload_dir={facts['upload_dir']}")

    if not redis_url:
        logger.error(
            f"[{service}] boot | FATAL? REDIS_URL is <unset> on THIS service — "
            "Celery has no broker and the worker will crash-loop. "
            "Fix: copy the Redis internal URL into this service's Variables and redeploy."
        )
    if not db_url:
        logger.error(
            f"[{service}] boot | FATAL? DATABASE_URL is <unset> on THIS service — "
            "tasks cannot reach Postgres. Fix: copy it into this service's Variables and redeploy."
        )

    # Reachability probes: warning-only, but they name the exact layer
    # (DNS vs auth vs refused) so prod crashes stop being a guessing game.
    if redis_url:
        try:
            import redis as _redis_lib

            _redis_lib.from_url(redis_url, socket_timeout=3, socket_connect_timeout=3).ping()
            logger.info(f"[{service}] boot | redis PING ok ({facts['redis']})")
            facts["redis_ping"] = "ok"
        except Exception as e:
            logger.error(
                f"[{service}] boot | redis PING FAILED ({facts['redis']}): "
                f"{type(e).__name__}: {e} — worker will retry broker forever; "
                "check Redis Running + same REDIS_URL on web+worker."
            )
            facts["redis_ping"] = f"{type(e).__name__}: {e}"

    try:
        os.makedirs(facts["upload_dir"], exist_ok=True)
        writable = os.access(facts["upload_dir"], os.W_OK)
        logger.info(
            f"[{service}] boot | upload_dir ready: {facts['upload_dir']} (writable={writable})"
        )
        facts["upload_writable"] = writable
    except Exception as e:
        logger.error(
            f"[{service}] boot | upload_dir NOT writable ({facts['upload_dir']}): "
            f"{type(e).__name__}: {e}"
        )
        facts["upload_writable"] = False

    return facts


def job_logger(task_name: str, job_id: str, task_id: str | None = None):
    """Bound logger adding [JOB name|id=..|task=..] prefix to every line."""
    short = (job_id or "?")[:8]
    prefix = f"[JOB {task_name}|id={short}|task={str(task_id or 'n/a')[:8]}]"
    return logger.bind(task_name=task_name, job_id=job_id, task_id=task_id), prefix
