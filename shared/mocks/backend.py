"""`MockBackend` — реализация `BackendPort` целиком в процессе.

Это то, что позволяет `make up-bot`: бот поднимается **без backend-service,
PostgreSQL, Redis и RabbitMQ** — все данные приходят из детерминированных
фикстур. Полезно и для UI-разработки, и для демо, и для e2e без инфры.
"""

from __future__ import annotations

from typing import Any

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
from shared.mocks.adapters import MockServices, build_mock_services


class MockBackend:
    """Собирает `BackendPort` из мок-адаптеров домена."""

    def __init__(self, services: MockServices | None = None) -> None:
        self.services = services or build_mock_services()

    async def aclose(self) -> None:  # ресурсов нет, но протокол требует
        return None

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
        return await self.services.users.upsert(
            telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

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
        return await self.services.users.confirm_login(code, telegram_id)

    # --- диалог -------------------------------------------------------------
    async def dialog_message(self, user_id: int, text: str) -> DialogReplyResponse | None:
        return await self.services.dialog.message(user_id, text)

    async def dialog_reset(self, user_id: int) -> DialogResetOut | None:
        return await self.services.dialog.reset(user_id)

    async def dialog_restore(self, user_id: int) -> DialogRestoreOut | None:
        return await self.services.dialog.restore(user_id)

    async def dialog_finalize(
        self, user_id: int, criteria: dict[str, Any] | None = None
    ) -> DialogFinalizeOut | None:
        return await self.services.dialog.finalize(user_id, criteria)

    # --- каталог ------------------------------------------------------------
    async def get_listing(self, listing_id: int) -> ListingOut | None:
        return await self.services.listings.get(listing_id)

    async def get_listing_by_url(self, url: str) -> ListingOut | None:
        return await self.services.listings.by_url(url)

    async def search_listings_page(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> ListingListOut | None:
        return await self.services.listings.page(params, limit=limit, offset=offset)

    async def search_listings(
        self, params: dict[str, Any] | None = None, limit: int = 5, offset: int = 0
    ) -> list[ListingOut] | None:
        page = await self.search_listings_page(params, limit=limit, offset=offset)
        return page.items if page else None

    async def analyze_price(self, listing_id: int, user_id: int) -> AnalysisOut | None:
        try:
            return await self.services.analysis.analyze(listing_id, user_id)
        except Exception:
            # `QuotaExceeded` пробрасывается наверх: бот показывает апселл.
            raise

    # --- расчёты ------------------------------------------------------------
    async def calc_delivery(
        self,
        price_usd: float,
        engine_cc: int,
        year: int,
        power_hp: int | None = None,
    ) -> DeliveryOut | None:
        return await self.services.calc.delivery(price_usd, engine_cc, year, power_hp)

    async def compare_delivery(self, items: list[dict[str, Any]]) -> CompareOut | None:
        return await self.services.calc.compare(items)

    # --- деньги и уведомления ----------------------------------------------
    async def subscription_status(self, user_id: int) -> UserSubscriptionOut | None:
        return await self.services.billing.status(user_id)

    async def prepare_payment(
        self, user_id: int, tier: str, period_days: int
    ) -> PaymentPrepareOut | None:
        try:
            return await self.services.billing.prepare(user_id, tier, period_days)
        except ValueError:
            return None

    async def payment_success(
        self,
        *,
        payment_id: int,
        user_id: int,
        provider_payment_id: str,
        amount: int,
    ) -> PaymentSuccessOut | None:
        try:
            return await self.services.billing.success(
                payment_id, user_id, provider_payment_id, amount
            )
        except KeyError:
            return None

    async def notification_settings(
        self, user_id: int, notify_mode: str
    ) -> NotifySettingsOut | None:
        return await self.services.notify.settings(user_id, notify_mode=notify_mode)

    async def quiet_hours(
        self, user_id: int, value: str | None = None, *, clear: bool = False
    ) -> NotifySettingsOut | None:
        return await self.services.notify.settings(
            user_id, quiet_hours=value, quiet_hours_clear=clear
        )
