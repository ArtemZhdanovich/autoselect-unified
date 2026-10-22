"""HTTP- и HTTPS-приложения edge: ACME-челлендж, редирект и прокси к Mini App."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from edge_service.certs import describe
from edge_service.config import EdgeConfig

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}

ACME_PREFIX = "/.well-known/acme-challenge/"


async def _proxy(client: httpx.AsyncClient, request: Request, path: str) -> Response:
    """Прозрачный проброс в upstream: путь, query и тело уходят как есть."""
    headers: dict[str, str] = {}
    for name in ("content-type", "accept", "user-agent", "cookie"):
        value = request.headers.get(name)
        if value:
            headers[name] = value

    try:
        upstream = await client.request(
            request.method,
            f"/{path}",
            params=request.query_params.multi_items(),
            content=await request.body(),
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": "upstream недоступен", "error": str(exc)[:200]},
        )

    passthrough = {
        key: value for key, value in upstream.headers.items() if key.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=passthrough,
        media_type=upstream.headers.get("content-type"),
    )


def _client(config: EdgeConfig, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.upstream, timeout=15.0, follow_redirects=False, transport=transport
    )


def build_http_app(config: EdgeConfig) -> FastAPI:
    """Порт 80: ACME-челлендж и редирект на HTTPS."""

    app = FastAPI(title="edge http")

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "edge",
            "mode": config.tls_mode,
            "port": config.http_port,
        }

    @app.get(ACME_PREFIX + "{challenge}", tags=["acme"])
    async def acme_challenge(challenge: str) -> Response:
        """Отдать файл челленджа, который положил certbot."""
        if "/" in challenge or "\\" in challenge or challenge.startswith("."):
            return PlainTextResponse("bad name", status_code=400)
        target = Path(config.acme_webroot) / challenge
        if not target.is_file():
            return PlainTextResponse("not found", status_code=404)
        return PlainTextResponse(target.read_text(encoding="utf-8").strip())

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
    async def redirect(path: str, request: Request) -> Response:
        """Всё остальное — на HTTPS (308, чтобы метод не терялся)."""
        host = config.domain or (request.url.hostname or "localhost")
        suffix = "" if config.https_port == 443 else f":{config.https_port}"
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"https://{host}{suffix}/{path}{query}", status_code=308)

    return app


def build_https_app(
    config: EdgeConfig, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """Порт 443: прокси к Mini App и служебный `/status`."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = _client(config, transport)
        yield
        await app.state.client.aclose()

    app = FastAPI(title="edge https", lifespan=lifespan)

    @app.get("/status", tags=["system"])
    async def status() -> dict:
        cert_path, _ = (
            config.le_cert_paths() if config.tls_mode == "letsencrypt" else config.selfsigned_paths
        )
        payload: dict = {
            "service": "edge",
            "mode": config.tls_mode,
            "domain": config.domain or None,
            "upstream": config.upstream,
            "https_port": config.https_port,
        }
        if cert_path.exists():
            try:
                payload["certificate"] = describe(cert_path)
            except Exception:  # noqa: BLE001 — статус не должен падать из-за сертификата
                payload["certificate"] = {"error": "не читается"}
        return payload

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "edge",
            "mode": config.tls_mode,
            "port": config.https_port,
        }

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
    async def proxy(path: str, request: Request) -> Response:
        return await _proxy(app.state.client, request, path)

    return app
