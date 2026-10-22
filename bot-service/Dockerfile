# bot-service: только UI-слой, без домена и без БД
FROM python:3.12-slim

ENV PYTHONPATH=/app:/app/bot-service:/app/backend-service \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY shared ./shared
COPY bot-service ./bot-service

RUN pip install --no-cache-dir \
        "aiogram>=3.13,<4" \
        "pydantic>=2.7,<3" \
        "httpx>=0.27,<1"

# SERVICE=bot + MODE=mock поднимает бота вообще без инфраструктуры.
ENV SERVICE=bot \
    MODE=mock

CMD ["python", "-m", "bot_service.main"]
