"""Подписка и Telegram Stars: internal-эндпоинты, которыми пользуется бот."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend_service.api.deps import ContainerDep, require_internal
from shared.contracts.payments import (
    PaymentPrepareIn,
    PaymentPrepareOut,
    PaymentSuccessIn,
    PaymentSuccessOut,
    UserSubscriptionOut,
)

router = APIRouter(prefix="/api", tags=["billing"])


@router.get(
    "/users/{user_id}/subscription",
    response_model=UserSubscriptionOut,
    dependencies=[Depends(require_internal)],
)
async def get_user_subscription(user_id: int, container: ContainerDep) -> UserSubscriptionOut:
    """Статус тарифа для `/subscribe`."""
    return await container.billing.status(user_id)


@router.post(
    "/payments/prepare",
    response_model=PaymentPrepareOut,
    dependencies=[Depends(require_internal)],
)
async def prepare_payment(
    body: PaymentPrepareIn, container: ContainerDep
) -> PaymentPrepareOut:
    """Создать pending-платёж; инвойс бот отправит сам через `sendInvoice` (XTR)."""
    return await container.billing.prepare(body.user_id, body.tier, body.period_days)


@router.post(
    "/payments/success",
    response_model=PaymentSuccessOut,
    dependencies=[Depends(require_internal)],
)
async def payment_success(
    body: PaymentSuccessIn, container: ContainerDep
) -> PaymentSuccessOut:
    """`successful_payment` от бота: платёж → paid, подписка активирована.

    Идемпотентность: повторный вызов с тем же `payment_id` не продлевает подписку
    второй раз (Telegram умеет ретраить апдейты).
    """
    return await container.billing.success(
        body.payment_id, body.user_id, body.provider_payment_id, body.amount
    )
