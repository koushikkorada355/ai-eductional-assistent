# Single-server production image (Render): FastAPI web + Celery worker in
# ONE container (see backend/start-single.sh).
#
# Why one container: Render disks are per-service (no shared volume between
# a separate web + worker), and uploads written by web must be visible to
# the worker. Same container = same filesystem = no shared-volume problem.
#
# This file lives at the repo root because Render looks for ./Dockerfile by
# default. Local docker-compose is untouched (it still builds ./backend and
# runs split backend/worker services with --reload).
FROM python:3.11-slim

WORKDIR /code

COPY backend/requirements.txt ./
# tesseract-ocr binary: required by pytesseract for the scanned-image OCR
# fallback in app/utils/pdf_parser.py. English only keeps the image small.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Celery refuses root with a noisy SecurityWarning (harmless in Docker but
# buries the real crash line in deploy logs). Containers run as root by
# default — silence it explicitly.
ENV C_FORCE_ROOT=true

# Render mounts a persistent disk at /data/uploads (see render.yaml) so
# uploaded PDFs survive restarts/redeploys.
ENV UPLOAD_DIR=/data/uploads

RUN chmod +x ./start-single.sh

EXPOSE 8000

# Honors $PORT (Render injects it). Starts worker + web together.
CMD ["sh", "./start-single.sh"]
