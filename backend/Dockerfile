FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Prod start: honor Railway's $PORT, no --reload (dev only).
# Local docker-compose still works ($PORT unset → 8000).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]