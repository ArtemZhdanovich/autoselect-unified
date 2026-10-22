"""Real-адаптеры: тонкие клиенты к реальным зависимостям.

Этап 2 (strangler): «реальный» источник правды — работающий `auto_bot` API.
Это даёт 100 % совместимость контракта по построению и позволяет переключать
бот на новый бэкенд, не переписывая домен целиком. Прямые адаптеры
(PostgreSQL, RabbitMQ, GLM, RAG, N3) встают на эти же порты на Этапе 4 —
менять придётся только `container.py`.

Любая ошибка сети → `None` (как `BackendClient` в `auto_bot`), кроме 403 на
разборе цены: это не сбой, а исчерпанная квота.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.contracts.analysis import AnalysisOut, AnalysisUnavailable, QuotaExceeded
from shared.contracts.delivery import CompareOut, DeliveryOut
from shared.contracts.dialog import (
    DialogFinalizeOut,
    DialogReplyResponse,
    DialogResetOut,
    DialogRestoreOut,
)
from shared.contracts.listing import ListingListOut, ListingOut
from shared.contracts.notifications import NotifySettingsOut
from shared.contracts.payments import (
    PaymentPrepareOut,
    PaymentSuccessOut,
    UserSubscriptionOut,
)
from shared.contracts.users import LoginLinkConfirmOut, UserOut


class LegacyClient:
    """HTTP-клиент к legacy `auto_bot` с internal-токеном."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("LEGACY_BACKEND_URL не задан — MODE=real требует адрес auto_bot")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"X-Internal-Token": token},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        return response.json()

    async def post(
        self, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any | None:
        try:
            response = await self._client.post(path, json=payload or {}, timeout=timeout)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        return response.json()

    async def post_raw(
        self, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None
    ) -> httpx.Response | None:
        """Как `post`, но отдаёт ответ целиком — нужен там, где важен статус (403)."""
        try:
            return await self._client.post(path, json=payload or {}, timeout=timeout)
        except httpx.HTTPError:
            return None


class LegacyUsers:
    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def upsert(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> UserOut:
        data = await self._c.post(
            "/api/users/upsert",
            {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
            },
        )
        if data is None:
            raise ConnectionError("legacy backend: /api/users/upsert недоступен")
        return UserOut.model_validate(data)

    async def confirm_login(self, code: str, telegram_id: int) -> LoginLinkConfirmOut:
        data = await self._c.post(
            "/api/auth/telegram/link/confirm", {"code": code, "telegram_id": telegram_id}
        )
        return LoginLinkConfirmOut.model_validate(data or {"status": "expired"})


class LegacyCatalog:
    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def page(
        self, params: dict[str, Any] | None = None, limit: int = 20, offset: int = 0
    ) -> ListingListOut:
        query = {"limit": limit, "offset": offset}
        query.update({k: v for k, v in (params or {}).items() if v is not None})
        data = await self._c.get("/api/listings", params=query)
        if data is None:
            raise ConnectionError("legacy backend: /api/listings недоступен")
        return ListingListOut.model_validate(data)

    async def get(self, listing_id: int) -> ListingOut | None:
        data = await self._c.get(f"/api/listings/{int(listing_id)}")
        return ListingOut.model_validate(data) if data else None

    async def by_url(self, url: str) -> ListingOut | None:
        data = await self._c.get("/api/listings/by-url", params={"url": url})
        return ListingOut.model_validate(data) if data else None


class LegacyDialog:
    DIALOG_TIMEOUT = 120.0

    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def message(self, user_id: int, text: str) -> DialogReplyResponse:
        data = await self._c.post(
            "/api/dialog/message",
            {"user_id": user_id, "text": text},
            timeout=self.DIALOG_TIMEOUT,
        )
        if data is None:
            raise ConnectionError("legacy backend: /api/dialog/message недоступен")
        return DialogReplyResponse.model_validate(data)

    async def reset(self, user_id: int) -> DialogResetOut:
        await self._c.post("/api/dialog/reset", {"user_id": user_id})
        return DialogResetOut()

    async def restore(self, user_id: int) -> DialogRestoreOut:
        data = await self._c.post("/api/dialog/restore", {"user_id": user_id})
        return DialogRestoreOut.model_validate(data or {})

    async def finalize(
        self, user_id: int, criteria: dict[str, Any] | None = None
    ) -> DialogFinalizeOut:
        data = await self._c.post(
            "/api/dialog/finalize", {"user_id": user_id, "criteria": criteria}
        )
        return DialogFinalizeOut.model_validate(data or {})


class LegacyCalc:
    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def delivery(
        self,
        price_usd: float,
        engine_cc: int,
        year: int,
        power_hp: int | None = None,
        region: str = "ru",
    ) -> DeliveryOut:
        payload: dict[str, Any] = {
            "price_usd": price_usd,
            "engine_cc": engine_cc,
            "year": year,
            "region": region,
        }
        if power_hp:
            payload["power_hp"] = power_hp
        data = await self._c.post("/api/calc/delivery", payload)
        if data is None:
            raise ConnectionError("legacy backend: /api/calc/delivery недоступен")
        return DeliveryOut.model_validate(data)

    async def compare(self, items: list[dict[str, Any]]) -> CompareOut:
        data = await self._c.post("/api/calc/compare", {"items": items})
        return CompareOut.model_validate(data or {"items": []})


class LegacyAnalysis:
    TIMEOUT = 120.0

    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def analyze(self, listing_id: int, user_id: int) -> AnalysisOut:
        response = await self._c.post_raw(
            f"/api/bot/listings/{int(listing_id)}/analysis",
            {"user_id": user_id},
            timeout=self.TIMEOUT,
        )
        if response is None:
            raise AnalysisUnavailable("legacy backend: analysis недоступен")
        if response.status_code == 403:
            raise QuotaExceeded("бесплатная квота разборов исчерпана")
        if response.status_code >= 400:
            raise AnalysisUnavailable(f"legacy analysis: HTTP {response.status_code}")
        return AnalysisOut.model_validate(response.json())


class LegacyBilling:
    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def status(self, user_id: int) -> UserSubscriptionOut:
        data = await self._c.get(f"/api/users/{int(user_id)}/subscription")
        if data is None:
            raise ConnectionError("legacy backend: subscription недоступен")
        return UserSubscriptionOut.model_validate(data)

    async def prepare(self, user_id: int, tier: str, period_days: int) -> PaymentPrepareOut:
        data = await self._c.post(
            "/api/payments/prepare",
            {"user_id": user_id, "tier": tier, "period_days": period_days},
        )
        if data is None:
            raise ConnectionError("legacy backend: /api/payments/prepare недоступен")
        return PaymentPrepareOut.model_validate(data)

    async def success(
        self, payment_id: int, user_id: int, provider_payment_id: str, amount: int
    ) -> PaymentSuccessOut:
        data = await self._c.post(
            "/api/payments/success",
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "provider_payment_id": provider_payment_id,
                "amount": amount,
            },
        )
        if data is None:
            raise ConnectionError("legacy backend: /api/payments/success недоступен")
        payload = {"activated": True, **data}
        return PaymentSuccessOut.model_validate(payload)


class LegacyNotify:
    def __init__(self, client: LegacyClient) -> None:
        self._c = client

    async def settings(
        self,
        user_id: int,
        notify_mode: str | None = None,
        quiet_hours: str | None = None,
        quiet_hours_clear: bool = False,
    ) -> NotifySettingsOut:
        payload: dict[str, Any] = {"user_id": user_id, "notify_mode": notify_mode}
        if quiet_hours_clear:
            payload["quiet_hours_clear"] = True
        elif quiet_hours is not None:
            payload["quiet_hours"] = quiet_hours
        data = await self._c.post("/api/notifications/settings", payload)
        if data is None:
            raise ConnectionError("legacy backend: /api/notifications/settings недоступен")
        return NotifySettingsOut.model_validate(data)
