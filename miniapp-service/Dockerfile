# miniapp-service: статика Mini App + прокси /api/* в backend-service
FROM python:3.12-slim

ENV PYTHONPATH=/app:/app/miniapp-service \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY miniapp-service ./miniapp-service

RUN pip install --no-cache-dir \
        "fastapi>=0.110,<1" \
        "uvicorn>=0.27,<1" \
        "httpx>=0.27,<1"

ENV BACKEND_URL=http://backend:8000

EXPOSE 8080

CMD ["uvicorn", "miniapp_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
