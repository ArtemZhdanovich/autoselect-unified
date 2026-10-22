"""Подписки и Telegram Stars — контракт перенесён из `auto_bot/app/schemas/payment.py` 1:1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SubscriptionOut(BaseModel):
    """GET /api/subscription — статус и лимиты текущего тарифа."""

    tier: str
    paid_tier: str
    subscription_until: datetime | None
    max_filters: int | None
    ai_daily_limit: int | None
    instant: bool
    prices: dict[str, int]


class StarsInvoiceRequest(BaseModel):
    tier: Literal["pro", "business"]
    period: Literal["month", "year"] = "month"


class StarsInvoiceOut(BaseModel):
    payment_id: int
    invoice_url: str
    amount: int  # в Stars
    currency: str = "XTR"
    tier: str
    period_days: int


class PaymentPrepareIn(BaseModel):
    """POST /api/payments/prepare (internal, бот) — создать pending-платёж."""

    user_id: int
    tier: Literal["pro", "business"]
    period_days: int = Field(ge=1, le=400)


class PaymentPrepareOut(BaseModel):
    payment_id: int
    amount: int
    currency: str = "XTR"
    tier: str
    period_days: int
    title: str
    description: str


class PaymentSuccessIn(BaseModel):
    """POST /api/payments/success (internal, бот) — successful_payment."""

    payment_id: int
    user_id: int
    provider_payment_id: str
    amount: int


class PaymentSuccessOut(BaseModel):
    """Ответ активации подписки (auto_bot отдавал dict с теми же ключами)."""

    activated: bool = True
    tier: str
    subscription_until: datetime | None = None


class UserSubscriptionOut(BaseModel):
    """GET /api/users/{id}/subscription (internal, бот) — для /subscribe."""

    user_id: int
    tier: str
    subscription_until: datetime | None
