# Single-server production image (Railway + Neon): FastAPI web + Celery worker
# in ONE container (see backend/start-single.sh).
#
# Why one container: Railway volumes are per-service (no shared volume between
# a separate web + worker), and uploads written by web must be visible to
# the worker. Same container = same filesystem = no shared-volume problem.
# Postgres lives outside in Neon (DATABASE_URL) — this image is stateless
# except for /data/uploads (mount a Railway volume there).
#
# This file lives at the repo root because Railway (railway.json) and Render
# both look for ./Dockerfile by default. Local docker-compose builds ./backend
# but runs the same single-server supervisor (sh ./start-single.sh), so
# local == prod.
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

# Railway mounts a persistent volume at /data/uploads so
# uploaded PDFs survive restarts/redeploys (see Railway dashboard -> Volumes).
ENV UPLOAD_DIR=/data/uploads

RUN chmod +x ./start-single.sh

EXPOSE 8000

# Honors $PORT (Railway/Render inject it). Starts worker + web together.
CMD ["sh", "./start-single.sh"]
