# backend-service: домен и BL, без Telegram
FROM python:3.12-slim

ENV PYTHONPATH=/app:/app/bot-service:/app/backend-service \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY shared ./shared
COPY backend-service ./backend-service

RUN pip install --no-cache-dir \
        "fastapi>=0.110,<1" \
        "uvicorn>=0.27,<1" \
        "pydantic>=2.7,<3" \
        "httpx>=0.27,<1"

ENV SERVICE=backend \
    MODE=mock

EXPOSE 8000

CMD ["uvicorn", "backend_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
