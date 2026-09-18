#!/bin/sh
# Single-server production start: FastAPI web + Celery worker in ONE container.
#
# Why: Railway volumes are per-service (and Render has no shared disk between
# services), so a split web/worker setup with a shared /data/uploads volume
# cannot work there. One container = web and worker share the same filesystem,
# so uploads written by web are always visible to the worker. Postgres lives
# in Neon (DATABASE_URL); Redis is the Railway Redis plugin (REDIS_URL).
#
# - Honors $PORT (Railway/Render inject it; defaults to 8000 for local runs).
# - Worker runs with --concurrency=1 (small instances; each prefork child
#   duplicates interpreter memory from langchain/torch imports).
# - All logs go to stdout (Railway/Render keep only stdout/stderr).
# - If EITHER process dies, the other is stopped and the container exits
#   non-zero so Railway/Render restarts it. In-flight jobs requeue via acks_late.
set -eu

export C_FORCE_ROOT="${C_FORCE_ROOT:-true}"
PORT="${PORT:-8000}"
UPLOAD_DIR="${UPLOAD_DIR:-/data/uploads}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-info}"

mkdir -p "$UPLOAD_DIR"

echo "[single] starting celery worker (concurrency=${CELERY_CONCURRENCY}, upload_dir=${UPLOAD_DIR})..."
celery -A app.tasks.celery_app.celery_app worker --loglevel="${CELERY_LOGLEVEL}" --concurrency="${CELERY_CONCURRENCY}" &
WORKER_PID=$!

echo "[single] starting web on port ${PORT}..."
# Foreground child: Railway/Render track the container, not a specific port process.
uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
WEB_PID=$!

# Shutdown helper: stop both children, then exit.
_shutdown() {
  echo "[single] stopping (worker=${WORKER_PID} web=${WEB_PID})..."
  kill -TERM "$WORKER_PID" 2>/dev/null || true
  kill -TERM "$WEB_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
  wait "$WEB_PID" 2>/dev/null || true
}
trap _shutdown TERM INT

# Supervisor loop: if either child exits, stop the other and exit non-zero
# so Railway/Render restart the container (jobs requeue via acks_late).
while kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 5
done

echo "[single] a child exited (worker alive: $(kill -0 "$WORKER_PID" 2>/dev/null && echo yes || echo no), web alive: $(kill -0 "$WEB_PID" 2>/dev/null && echo yes || echo no)) — shutting down so Railway/Render restart us"
_shutdown
exit 1
