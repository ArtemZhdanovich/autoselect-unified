"""Порты домена — единственные точки, через которые домен видит внешний мир.

Правило: обработчик API не знает, откуда данные. Он получает порт, а `MODE`
решает, какой адаптер подставлен: `mock` (фикстуры) или `real` (legacy auto_bot /
PostgreSQL / LLM — Этап 4). Никаких прямых `httpx`/`sqlalchemy` из роутеров.
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
class UsersPort(Protocol):
    async def upsert(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> UserOut: ...

    async def confirm_login(self, code: str, telegram_id: int) -> LoginLinkConfirmOut: ...


@runtime_checkable
class CatalogPort(Protocol):
    async def page(
        self, params: dict[str, Any] | None = None, limit: int = 20, offset: int = 0
    ) -> ListingListOut: ...

    async def get(self, listing_id: int) -> ListingOut | None: ...

    async def by_url(self, url: str) -> ListingOut | None: ...


@runtime_checkable
class DialogPort(Protocol):
    async def message(self, user_id: int, text: str) -> DialogReplyResponse: ...

    async def reset(self, user_id: int) -> DialogResetOut: ...

    async def restore(self, user_id: int) -> DialogRestoreOut: ...

    async def finalize(
        self, user_id: int, criteria: dict[str, Any] | None = None
    ) -> DialogFinalizeOut: ...


@runtime_checkable
class CalcPort(Protocol):
    async def delivery(
        self,
        price_usd: float,
        engine_cc: int,
        year: int,
        power_hp: int | None = None,
        region: str = "ru",
    ) -> DeliveryOut: ...

    async def compare(self, items: list[dict[str, Any]]) -> CompareOut: ...


@runtime_checkable
class AnalysisPort(Protocol):
    async def analyze(self, listing_id: int, user_id: int) -> AnalysisOut:
        """Бросает `QuotaExceeded` / `AnalysisUnavailable`."""
        ...


@runtime_checkable
class BillingPort(Protocol):
    async def status(self, user_id: int) -> UserSubscriptionOut: ...

    async def prepare(self, user_id: int, tier: str, period_days: int) -> PaymentPrepareOut: ...

    async def success(
        self, payment_id: int, user_id: int, provider_payment_id: str, amount: int
    ) -> PaymentSuccessOut: ...


@runtime_checkable
class NotifyPort(Protocol):
    async def settings(
        self,
        user_id: int,
        notify_mode: str | None = None,
        quiet_hours: str | None = None,
        quiet_hours_clear: bool = False,
    ) -> NotifySettingsOut: ...
