"""Подписка и Telegram Stars: `/subscribe`, `sub:buy:*`, инвойс, платёж."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb

logger = logging.getLogger(__name__)

router = Router(name="subscribe")


def subscription_text(tier: str, until) -> str:
    until_suffix = skin.SUB_UNTIL.format(date=str(until)[:10]) if until else ""
    return skin.SUB_TITLE.format(tier=tier, until=until_suffix, prices=skin.SUB_PRICES)


async def show_subscription(message: Message, backend: BackendPort, user_id: int) -> None:
    """Статус тарифа + варианты оплаты. Общая точка для `/subscribe` и `menu:subscribe`."""
    status = await backend.subscription_status(user_id)
    if status is None:
        await message.answer(skin.BACKEND_DOWN)
        return
    await message.answer(
        subscription_text(status.tier, status.subscription_until),
        reply_markup=keyboards.subscribe_kb(),
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, backend: BackendPort) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await show_subscription(message, backend, user_id)


@router.callback_query(F.data.startswith("sub:buy:"))
async def sub_buy(callback: CallbackQuery, backend: BackendPort) -> None:
    """Выбор тарифа → pending-платёж в домене → `sendInvoice` (XTR)."""
    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    _, _, tier, days_raw = parts
    days = int(days_raw)
    message = callback.message
    assert message is not None

    prep = await backend.prepare_payment(callback.from_user.id, tier, days)
    if prep is None:
        await message.answer(skin.BACKEND_DOWN)
        return

    await message.answer_invoice(
        title=prep.title,
        description=prep.description,
        payload=f"sub:{prep.payment_id}",
        provider_token="",  # Telegram Stars: провайдер не требуется
        currency="XTR",
        prices=[LabeledPrice(label=prep.title, amount=prep.amount)],
    )


@router.pre_checkout_query()
async def pre_checkout_query(query: PreCheckoutQuery) -> None:
    """Telegram ждёт подтверждение перед списанием Stars."""
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, backend: BackendPort) -> None:
    """Оплата прошла: активируем подписку через домен (идемпотентно)."""
    payment = message.successful_payment
    if payment is None:
        return
    user_id = message.from_user.id if message.from_user else 0
    try:
        payment_id = int(payment.invoice_payload.split(":", 1)[1])
    except (IndexError, ValueError):
        logger.error("successful_payment_bad_payload: %s", payment.invoice_payload)
        return

    result = await backend.payment_success(
        payment_id=payment_id,
        user_id=user_id,
        provider_payment_id=payment.telegram_payment_charge_id,
        amount=payment.total_amount,
    )
    if result is None:
        await message.answer(skin.SUB_FAILED)
        return

    until = skin.SUB_UNTIL.format(date=str(result.subscription_until)[:10]) if result.subscription_until else ""
    await message.answer(
        skin.SUB_ACTIVATED.format(amount=payment.total_amount, tier=result.tier, until=until)
    )
