"""HTTP-контракт backend-service: те же роуты и те же коды, что у `auto_bot`.

Сценарий «клиент старого бота не замечает разницы» проверяется здесь на уровне
запросов: бот ходит именно этими вызовами (см. `bot_service/port.py`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend_service.main import create_app
from shared.http_headers import auth_headers
from shared.settings import Settings

#: Настройки тестового приложения. Заголовок строится из них же — чтобы тест
#: не разъехался с приложением, если дефолт поменяется.
SETTINGS = Settings(service="backend", mode="mock")
INTERNAL = auth_headers(SETTINGS.internal_token)


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app(SETTINGS)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "backend"
    assert body["mode"] == "mock"


def test_health_detailed(client: TestClient) -> None:
    response = client.get("/health/detailed")
    assert response.status_code == 200
    assert response.json()["components"]["catalog"] is True


def test_users_upsert_is_public(client: TestClient) -> None:
    response = client.post(
        "/api/users/upsert",
        json={"telegram_id": 1001, "username": "tester", "first_name": "Иван"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["telegram_id"] == 1001
    assert body["subscription_tier"] == "free"


def test_listings_feed(client: TestClient) -> None:
    response = client.get("/api/listings", params={"limit": 4})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 12
    assert len(body["items"]) == 4


def normalized_usd(item: dict) -> float:
    """Цена в USD: в каталоге есть лоты в KRW (как и в бою)."""
    price = float(item.get("price") or 0)
    return price / 1350 if (item.get("currency") or "").upper() == "KRW" else price


def test_listings_filters(client: TestClient) -> None:
    body = client.get("/api/listings", params={"price_max": 30000, "limit": 50}).json()
    assert body["total"] == 3
    assert all(item["price"] <= 30000 for item in body["items"])


def test_listings_sort_by_normalized_price(client: TestClient) -> None:
    body = client.get("/api/listings", params={"sort": "price_asc", "limit": 50}).json()
    prices = [normalized_usd(item) for item in body["items"]]
    assert prices == sorted(prices)


def test_listings_pagination_offset(client: TestClient) -> None:
    first = client.get("/api/listings", params={"limit": 4, "offset": 0}).json()
    second = client.get("/api/listings", params={"limit": 4, "offset": 4}).json()
    assert {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]} == set()


def test_listing_by_id_and_404(client: TestClient) -> None:
    ok = client.get("/api/listings/1")
    assert ok.status_code == 200
    assert ok.json()["id"] == 1
    assert client.get("/api/listings/9999").status_code == 404


def test_listing_by_url(client: TestClient) -> None:
    listing = client.get("/api/listings/1").json()
    found = client.get("/api/listings/by-url", params={"url": listing["url"]})
    assert found.status_code == 200
    assert found.json()["id"] == 1


def test_facets(client: TestClient) -> None:
    body = client.get("/api/listings/facets").json()
    assert body["total"] == 12
    assert body["makes"]["Kia"] >= 1


def test_analysis_requires_internal_token(client: TestClient) -> None:
    response = client.post("/api/bot/listings/1/analysis", json={"user_id": 2001})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal token"


def test_analysis_quota_maps_to_403(client: TestClient) -> None:
    first = client.post(
        "/api/bot/listings/1/analysis", json={"user_id": 2002}, headers=INTERNAL
    )
    assert first.status_code == 200
    assert first.json()["verdict"] in {"deal", "fair", "overpriced"}

    second = client.post(
        "/api/bot/listings/1/analysis", json={"user_id": 2002}, headers=INTERNAL
    )
    assert second.status_code == 403


def test_calc_delivery(client: TestClient) -> None:
    response = client.post(
        "/api/calc/delivery", json={"price_usd": 18000, "engine_cc": 2000, "year": 2022}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_usd"] > 18000
    assert body["components"]


def test_calc_compare(client: TestClient) -> None:
    response = client.post(
        "/api/calc/compare",
        json={
            "items": [
                {"price_usd": 18000, "engine_cc": 2000, "year": 2022},
                {"price_usd": 15000, "engine_cc": 3500, "year": 2019},
            ]
        },
    )
    assert response.status_code == 200
    totals = [row["total_usd"] for row in response.json()["items"]]
    assert totals == sorted(totals)


def test_dialog_flow_with_internal_token(client: TestClient) -> None:
    message = client.post(
        "/api/dialog/message",
        json={"user_id": 3001, "text": "Hyundai Palisade"},
        headers=INTERNAL,
    )
    assert message.status_code == 200
    body = message.json()
    assert body["criteria"]["make"] == "Hyundai"
    assert body["finalize_ready"] is False
    assert set(body) == {
        "session_id",
        "text",
        "options",
        "status",
        "finalize_ready",
        "turn_count",
        "criteria",
    }

    finalize = client.post("/api/dialog/finalize", json={"user_id": 3001}, headers=INTERNAL)
    assert finalize.status_code == 200
    assert finalize.json()["sources"] == ["encar", "kcar"]

    reset = client.post("/api/dialog/reset", json={"user_id": 3001}, headers=INTERNAL)
    assert reset.status_code == 200


def test_dialog_without_token_is_401(client: TestClient) -> None:
    response = client.post("/api/dialog/message", json={"user_id": 1, "text": "Kia"})
    assert response.status_code == 401


def test_notification_settings(client: TestClient) -> None:
    response = client.post(
        "/api/notifications/settings",
        json={"user_id": 4001, "notify_mode": "digest"},
        headers=INTERNAL,
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == 4001


def test_payments_prepare_and_success(client: TestClient) -> None:
    prepared = client.post(
        "/api/payments/prepare",
        json={"user_id": 5001, "tier": "pro", "period_days": 30},
        headers=INTERNAL,
    )
    assert prepared.status_code == 200
    payment = prepared.json()
    assert payment["amount"] == 500
    assert payment["currency"] == "XTR"

    success = client.post(
        "/api/payments/success",
        json={
            "payment_id": payment["payment_id"],
            "user_id": 5001,
            "provider_payment_id": "charge-1",
            "amount": 500,
        },
        headers=INTERNAL,
    )
    assert success.status_code == 200
    assert success.json()["tier"] == "pro"

    status = client.get("/api/users/5001/subscription", headers=INTERNAL)
    assert status.status_code == 200
    assert status.json()["tier"] == "pro"


def test_subscription_is_open_for_new_user(client: TestClient) -> None:
    response = client.get("/api/users/6001/subscription", headers=INTERNAL)
    assert response.status_code == 200
    assert response.json()["tier"] == "free"


def test_ai_alias_router(client: TestClient) -> None:
    """`/api/ai/*` — исторический дубль `/api/dialog/*`; должен отвечать так же."""
    response = client.post(
        "/api/ai/message", json={"user_id": 7001, "text": "Kia"}, headers=INTERNAL
    )
    assert response.status_code == 200
    assert response.json()["criteria"]["make"] == "Kia"


def test_openapi_contains_legacy_paths(client: TestClient) -> None:
    """Набор путей фиксирован контрактом — сверяем ключевые."""
    paths = set(client.get("/openapi.json").json()["paths"])
    for path in (
        "/api/users/upsert",
        "/api/listings",
        "/api/listings/{listing_id}",
        "/api/listings/by-url",
        "/api/bot/listings/{listing_id}/analysis",
        "/api/calc/delivery",
        "/api/calc/compare",
        "/api/dialog/message",
        "/api/dialog/reset",
        "/api/dialog/restore",
        "/api/dialog/finalize",
        "/api/notifications/settings",
        "/api/payments/prepare",
        "/api/payments/success",
        "/api/users/{user_id}/subscription",
    ):
        assert path in paths, path
