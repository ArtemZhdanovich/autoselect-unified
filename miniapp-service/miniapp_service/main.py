"""miniapp-service: статика Mini App + прокси `/api/*` в backend-service.

Зачем сервис вообще: Mini App открывается по HTTPS-адресу, и ходить в API с
другого origin — это CORS, cookie-политики и лишние грабли. Здесь статика и API
живут на одном origin, поэтому браузер не знает, что за ним два процесса.

Прокси — «тупой»: ничего не добавляет и не подменяет. Mini App пользуется только
публичными ручками (`/api/listings*`, `/api/calc/*`), внутренний токен сюда не
попадает и в браузер не уезжает.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

#: Заголовки, которые нельзя пробрасывать как есть.
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}


@dataclass(frozen=True, slots=True)
class MiniAppConfig:
    """У edge-сервиса два параметра и нет домена — `Settings` ему не нужен."""

    backend_url: str = "http://localhost:8000"
    timeout_sec: float = 10.0

    @classmethod
    def from_env(cls) -> MiniAppConfig:
        return cls(
            backend_url=(os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/"),
            timeout_sec=float(os.getenv("HTTP_TIMEOUT_SEC") or 10),
        )


def create_app(
    config: MiniAppConfig | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    resolved = config or MiniAppConfig.from_env()

    app = FastAPI(
        title="autoselect miniapp-service",
        version="0.3.0",
        description="Telegram Mini App: каталог, карточка, подбор по цене, калькулятор.",
    )
    app.state.config = resolved

    client = httpx.AsyncClient(
        base_url=resolved.backend_url,
        timeout=resolved.timeout_sec,
        transport=transport,
    )
    app.state.upstream = client

    @app.on_event("shutdown")
    async def _close_upstream() -> None:
        await client.aclose()

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok", "service": "miniapp", "upstream": resolved.backend_url}

    @app.get("/config", tags=["system"])
    async def config() -> dict:
        """Публичная конфигурация для клиента: бот для deep-link и режим для бейджа."""
        return {
            "bot_username": (os.getenv("BOT_USERNAME") or "").lstrip("@"),
            "mode": (os.getenv("MODE") or "mock").lower(),
            "backend": resolved.backend_url,
        }

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        tags=["proxy"],
    )
    async def proxy(path: str, request: Request) -> Response:
        """Прозрачный проброс в backend-service: тот же путь, те же параметры."""
        headers: dict[str, str] = {}
        if request.headers.get("content-type"):
            headers["content-type"] = request.headers["content-type"]
        if request.headers.get("accept"):
            headers["accept"] = request.headers["accept"]

        try:
            upstream = await client.request(
                request.method,
                f"/api/{path}",
                params=request.query_params.multi_items(),
                content=await request.body(),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.warning("miniapp_proxy_failed: %s %s", path, exc)
            return JSONResponse(
                status_code=503,
                content={"detail": "backend недоступен", "upstream": str(exc)[:200]},
            )

        passthrough = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in _HOP_BY_HOP
        }
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=passthrough,
            media_type=upstream.headers.get("content-type"),
        )

    # Статика монтируется последней: иначе `/` перехватил бы `/api/*`.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
