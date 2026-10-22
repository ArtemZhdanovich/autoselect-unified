"""HTTP-реализация `BackendPort` для `MODE=real`.

Поведение скопировано с `auto_bot/app/bot/client.py`: любая сетевая проблема →
`None`, бот показывает человеческое сообщение вместо падения. Исключение одно —
403 на разборе цены: это не сбой, а исчерпанная квота (`QuotaExceeded`).
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
from shared.http_headers import auth_headers
from shared.mocks.backend import MockBackend
from shared.settings import Settings


class HttpBackend:
    """Клиент backend-service (или legacy `auto_bot`) по контракту `/api/*`."""

    def __init__(
        self,
        base_url: str,
        internal_key: str,
        *,
        timeout: float = 10.0,
        dialog_timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers=auth_headers(internal_key),
            transport=transport,
        )
        self._dialog_timeout = dialog_timeout

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ HTTP

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        return response.json()

    async def _post(
        self, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any | None:
        try:
            response = await self._client.post(path, json=payload or {}, timeout=timeout)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        return response.json()

    # --- пользователь -------------------------------------------------------

    async def upsert_user(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> UserOut | None:
        data = await self._post(
            "/api/users/upsert",
            {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
            },
        )
        return UserOut.model_validate(data) if data else None

    async def confirm_login_link(
        self,
        *,
        code: str,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> LoginLinkConfirmOut | None:
        data = await self._post(
            "/api/auth/telegram/link/confirm",
            {
                "code": code,
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
            },
        )
        return LoginLinkConfirmOut.model_validate(data) if data else None

    # --- диалог -------------------------------------------------------------

    async def dialog_message(self, user_id: int, text: str) -> DialogReplyResponse | None:
        data = await self._post(
            "/api/dialog/message",
            {"user_id": user_id, "text": text},
            timeout=self._dialog_timeout,
        )
        return DialogReplyResponse.model_validate(data) if data else None

    async def dialog_reset(self, user_id: int) -> DialogResetOut | None:
        data = await self._post("/api/dialog/reset", {"user_id": user_id})
        return DialogResetOut.model_validate(data) if data else None

    async def dialog_restore(self, user_id: int) -> DialogRestoreOut | None:
        data = await self._post("/api/dialog/restore", {"user_id": user_id})
        return DialogRestoreOut.model_validate(data) if data else None

    async def dialog_finalize(
        self, user_id: int, criteria: dict[str, Any] | None = None
    ) -> DialogFinalizeOut | None:
        data = await self._post(
            "/api/dialog/finalize", {"user_id": user_id, "criteria": criteria}
        )
        return DialogFinalizeOut.model_validate(data) if data else None

    # --- каталог ------------------------------------------------------------

    async def get_listing(self, listing_id: int) -> ListingOut | None:
        data = await self._get(f"/api/listings/{int(listing_id)}")
        return ListingOut.model_validate(data) if data else None

    async def get_listing_by_url(self, url: str) -> ListingOut | None:
        data = await self._get("/api/listings/by-url", params={"url": url})
        return ListingOut.model_validate(data) if data else None

    async def search_listings_page(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> ListingListOut | None:
        query: dict[str, Any] = {"limit": limit, "offset": offset}
        query.update({k: v for k, v in (params or {}).items() if v is not None})
        data = await self._get("/api/listings", params=query)
        return ListingListOut.model_validate(data) if data else None

    async def search_listings(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> list[ListingOut] | None:
        page = await self.search_listings_page(params, limit=limit, offset=offset)
        return page.items if page else None

    async def analyze_price(self, listing_id: int, user_id: int) -> AnalysisOut | None:
        try:
            response = await self._client.post(
                f"/api/bot/listings/{int(listing_id)}/analysis",
                json={"user_id": user_id},
                timeout=self._dialog_timeout,
            )
        except httpx.HTTPError as exc:  # сеть — это «недоступно», а не «нет квоты»
            raise AnalysisUnavailable(str(exc)) from exc
        if response.status_code == 403:
            raise QuotaExceeded("квота бесплатных разборов исчерпана")
        if response.status_code >= 400:
            raise AnalysisUnavailable(f"HTTP {response.status_code}")
        return AnalysisOut.model_validate(response.json())

    # --- расчёты ------------------------------------------------------------

    async def calc_delivery(
        self,
        price_usd: float,
        engine_cc: int,
        year: int,
        power_hp: int | None = None,
    ) -> DeliveryOut | None:
        payload: dict[str, Any] = {
            "price_usd": price_usd,
            "engine_cc": engine_cc,
            "year": year,
        }
        if power_hp:
            payload["power_hp"] = power_hp
        data = await self._post("/api/calc/delivery", payload)
        return DeliveryOut.model_validate(data) if data else None

    async def compare_delivery(self, items: list[dict[str, Any]]) -> CompareOut | None:
        data = await self._post("/api/calc/compare", {"items": items})
        return CompareOut.model_validate(data) if data else None

    # --- деньги и уведомления ----------------------------------------------

    async def subscription_status(self, user_id: int) -> UserSubscriptionOut | None:
        data = await self._get(f"/api/users/{int(user_id)}/subscription")
        return UserSubscriptionOut.model_validate(data) if data else None

    async def prepare_payment(
        self, user_id: int, tier: str, period_days: int
    ) -> PaymentPrepareOut | None:
        data = await self._post(
            "/api/payments/prepare",
            {"user_id": user_id, "tier": tier, "period_days": period_days},
        )
        return PaymentPrepareOut.model_validate(data) if data else None

    async def payment_success(
        self,
        *,
        payment_id: int,
        user_id: int,
        provider_payment_id: str,
        amount: int,
    ) -> PaymentSuccessOut | None:
        data = await self._post(
            "/api/payments/success",
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "provider_payment_id": provider_payment_id,
                "amount": amount,
            },
        )
        return PaymentSuccessOut.model_validate(data) if data else None

    async def notification_settings(
        self, user_id: int, notify_mode: str
    ) -> NotifySettingsOut | None:
        data = await self._post(
            "/api/notifications/settings", {"user_id": user_id, "notify_mode": notify_mode}
        )
        return NotifySettingsOut.model_validate(data) if data else None

    async def quiet_hours(
        self, user_id: int, value: str | None = None, *, clear: bool = False
    ) -> NotifySettingsOut | None:
        payload: dict[str, Any] = {"user_id": user_id, "notify_mode": None}
        if clear:
            payload["quiet_hours_clear"] = True
        elif value:
            payload["quiet_hours"] = value
        data = await self._post("/api/notifications/settings", payload)
        return NotifySettingsOut.model_validate(data) if data else None


def build_backend(settings: Settings):
    """Выбрать реализацию порта по ENV: `MODE`/`ADAPTER_BACKEND`."""
    if settings.adapter_mode("backend") == "real":
        return HttpBackend(
            settings.backend_url,
            settings.internal_token,
            timeout=settings.http_timeout_sec,
            dialog_timeout=settings.dialog_timeout_sec,
        )
    return MockBackend()
