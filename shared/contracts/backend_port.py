"""`BackendPort` — единственный канал, которым UI-слой разговаривает с доменом.

Контракт зафиксирован: bot-service вызывает **только** эти методы, backend-service
реализует их поверх своих портов. `None` = зависимость недоступна (бот показывает
человеческое сообщение, а не падает) — поведение унаследовано от `BackendClient`
`auto_bot`, где `None` означал «backend недоступен».
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shared.contracts.analysis import AnalysisOut
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


@runtime_checkable
class BackendPort(Protocol):
    """Порт бэкенда. Реализации: `HttpBackend` (real) и `MockBackend` (mock)."""

    # --- пользователь -------------------------------------------------------
    async def upsert_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
    ) -> UserOut | None: ...

    async def confirm_login_link(
        self,
        *,
        code: str,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> LoginLinkConfirmOut | None: ...

    # --- диалог -------------------------------------------------------------
    async def dialog_message(self, user_id: int, text: str) -> DialogReplyResponse | None: ...

    async def dialog_reset(self, user_id: int) -> DialogResetOut | None: ...

    async def dialog_restore(self, user_id: int) -> DialogRestoreOut | None: ...

    async def dialog_finalize(
        self, user_id: int, criteria: dict[str, Any] | None = None
    ) -> DialogFinalizeOut | None: ...

    # --- каталог ------------------------------------------------------------
    async def get_listing(self, listing_id: int) -> ListingOut | None: ...

    async def get_listing_by_url(self, url: str) -> ListingOut | None: ...

    async def search_listings_page(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> ListingListOut | None: ...

    async def search_listings(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> list[ListingOut] | None: ...

    async def analyze_price(self, listing_id: int, user_id: int) -> AnalysisOut | None:
        """`QuotaExceeded` — бесплатная квота исчерпана (бот показывает апселл)."""
        ...

    # --- расчёты ------------------------------------------------------------
    async def calc_delivery(
        self,
        price_usd: float,
        engine_cc: int,
        year: int,
        power_hp: int | None = None,
    ) -> DeliveryOut | None: ...

    async def compare_delivery(self, items: list[dict[str, Any]]) -> CompareOut | None: ...

    # --- деньги и уведомления ----------------------------------------------
    async def subscription_status(self, user_id: int) -> UserSubscriptionOut | None: ...

    async def prepare_payment(
        self, user_id: int, tier: str, period_days: int
    ) -> PaymentPrepareOut | None: ...

    async def payment_success(
        self,
        *,
        payment_id: int,
        user_id: int,
        provider_payment_id: str,
        amount: int,
    ) -> PaymentSuccessOut | None: ...

    async def notification_settings(
        self, user_id: int, notify_mode: str
    ) -> NotifySettingsOut | None: ...

    async def quiet_hours(
        self, user_id: int, value: str | None = None, *, clear: bool = False
    ) -> NotifySettingsOut | None: ...

    # --- жизненный цикл -----------------------------------------------------
    async def aclose(self) -> None: ...
