FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt ./
# tesseract-ocr binary: required by pytesseract for the scanned-image OCR
# fallback in app/utils/pdf_parser.py. English only keeps the image small.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Celery refuses root with a noisy SecurityWarning (harmless in Docker but
# buries the real crash line in Railway logs). Containers run as root by
# default — silence it explicitly.
ENV C_FORCE_ROOT=true

EXPOSE 8000

# Prod start: honor Railway's $PORT, no --reload (dev only).
# Local docker-compose still works ($PORT unset → 8000).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]