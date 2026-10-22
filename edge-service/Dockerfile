# edge-service: TLS-терминация, ACME (Let's Encrypt) и публичный туннель
FROM python:3.12-slim

ENV PYTHONPATH=/app:/app/edge-service \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY edge-service ./edge-service

# certbot нужен для режима TLS_MODE=letsencrypt (HTTP-01, webroot).
RUN pip install --no-cache-dir \
        "fastapi>=0.110,<1" \
        "uvicorn>=0.27,<1" \
        "httpx>=0.27,<1" \
        "cryptography>=42" \
        "certbot>=2.6"

ENV TLS_MODE=selfsigned \
    EDGE_HTTP_PORT=80 \
    EDGE_HTTPS_PORT=443 \
    CERTS_DIR=/app/.certs \
    RUNTIME_DIR=/app/runtime

EXPOSE 80 443

CMD ["python", "-m", "edge_service.main"]
