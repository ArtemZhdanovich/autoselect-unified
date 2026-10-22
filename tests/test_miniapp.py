"""miniapp-service: раздача статики, прокси `/api/*`, отсутствие утечки токена."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from miniapp_service.main import MiniAppConfig, create_app

STATIC = Path(__file__).resolve().parents[1] / "miniapp-service" / "static"


def make_client(handler=None) -> TestClient:
    transport = httpx.MockTransport(handler) if handler is not None else None
    app = create_app(MiniAppConfig(backend_url="http://upstream.test"), transport=transport)
    return TestClient(app)


def test_index_is_served() -> None:
    response = make_client().get("/")
    assert response.status_code == 200
    assert 'id="view"' in response.text
    assert "/app.js" in response.text and "/app.css" in response.text


def test_assets_are_served() -> None:
    client = make_client()
    for path in ("/app.js", "/app.css", "/assets/car-suv.svg", "/assets/favicon.svg"):
        assert client.get(path).status_code == 200, path


def test_config_returns_bot_and_mode(monkeypatch) -> None:
    monkeypatch.setenv("BOT_USERNAME", "@demo_bot")
    monkeypatch.setenv("MODE", "mock")
    body = make_client().get("/config").json()
    assert body["bot_username"] == "demo_bot"
    assert body["mode"] == "mock"


def test_proxy_forwards_path_and_query() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"total": 1, "items": []})

    response = make_client(handler).get("/api/listings?limit=2&sort=new")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert "/api/listings" in seen["url"]
    assert "limit=2" in seen["url"] and "sort=new" in seen["url"]


def test_proxy_forwards_post_body() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        seen["method"] = request.method
        return httpx.Response(200, json={"total_usd": 42})

    response = make_client(handler).post(
        "/api/calc/delivery", json={"price_usd": 18000, "engine_cc": 2000, "year": 2022}
    )
    assert response.status_code == 200
    assert seen["method"] == "POST"
    assert b'"price_usd":18000' in seen["body"]


def test_proxy_does_not_inject_internal_header() -> None:
    """Mini App ходит только в публичные ручки: токен в браузер не попадает."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = {key.lower(): value for key, value in request.headers.items()}
        return httpx.Response(200, json={})

    make_client(handler).get("/api/listings")
    assert "x-internal-token" not in seen["headers"]


def test_proxy_reports_upstream_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream is down")

    response = make_client(handler).get("/api/listings")
    assert response.status_code == 503
    assert "backend" in response.json()["detail"]


def test_health_reports_upstream() -> None:
    body = make_client().get("/health").json()
    assert body["service"] == "miniapp"
    assert body["upstream"] == "http://upstream.test"


def test_client_code_has_no_internal_secret() -> None:
    """Статика не должна знать про внутренний заголовок — это гарантия изоляции."""
    for name in ("app.js", "index.html"):
        text = (STATIC / name).read_text(encoding="utf-8").lower()
        assert "x-internal-token" not in text
        assert "internal_token" not in text


def test_client_uses_public_endpoints_only() -> None:
    """Никаких `/api/bot/*`, `/api/dialog/*` и прочих internal-ручек из браузера."""
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "/api/listings" in script
    assert "/api/calc/delivery" in script
    for forbidden in ("/api/bot/", "/api/dialog/", "/api/payments/", "/api/admin/"):
        assert forbidden not in script, forbidden
