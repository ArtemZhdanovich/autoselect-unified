"""Уведомления: `menu:notify`, `menu:quiet`, `/stop`, `/resume`."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards
from bot_service.ui.panel import edit_or_answer
from shared.contracts.backend_port import BackendPort

router = Router(name="notify")

_MODE_MESSAGES = {
    "instant": skin.NOTIFY_ON_INSTANT,
    "digest": skin.NOTIFY_ON_DIGEST,
    "off": skin.NOTIFY_ON_OFF,
}


@router.callback_query(F.data == "menu:notify")
async def show_notify(callback: CallbackQuery) -> None:
    await callback.answer()
    await edit_or_answer(callback, skin.NOTIFY_TITLE, keyboards.notify_kb())


@router.callback_query(F.data.startswith("menu:notify_set:"))
async def set_notify_mode(callback: CallbackQuery, backend: BackendPort) -> None:
    """Режим применяется ко всем фильтрам пользователя — одним запросом."""
    mode = (callback.data or "").split(":", 2)[2]
    await callback.answer()
    user_id = callback.from_user.id
    result = await backend.notification_settings(user_id, mode)
    message = callback.message
    assert message is not None
    if result is None:
        await message.answer(skin.BACKEND_DOWN)
        return
    await message.answer(_MODE_MESSAGES.get(mode, skin.NOTIFY_ON_OFF))


@router.callback_query(F.data == "menu:quiet")
async def show_quiet(callback: CallbackQuery) -> None:
    await callback.answer()
    await edit_or_answer(callback, skin.QUIET_TITLE, keyboards.quiet_kb())


@router.callback_query(F.data.startswith("menu:quiet_set:"))
async def set_quiet_hours(callback: CallbackQuery, backend: BackendPort) -> None:
    """Значение содержит `:` внутри («23:00-08:00») — режем только по первым двум."""
    value = (callback.data or "").split(":", 2)[2]
    await callback.answer()
    user_id = callback.from_user.id
    message = callback.message
    assert message is not None

    if value == "off":
        result = await backend.quiet_hours(user_id, clear=True)
        text = skin.QUIET_CLEARED
    else:
        result = await backend.quiet_hours(user_id, value)
        start, end = value.split("-", 1)
        text = skin.QUIET_SET.format(start=start, end=end)

    if result is None:
        await message.answer(skin.BACKEND_DOWN)
        return
    await message.answer(text)


@router.message(Command("stop"))
async def cmd_stop(message: Message, backend: BackendPort) -> None:
    user_id = message.from_user.id if message.from_user else 0
    result = await backend.notification_settings(user_id, "off")
    if result is None:
        await message.answer(skin.BACKEND_DOWN)
        return
    await message.answer(skin.STOPPED)


@router.message(Command("resume"))
async def cmd_resume(message: Message, backend: BackendPort) -> None:
    """Включение уведомлений; если поисков нет — подсказываем, что делать."""
    user_id = message.from_user.id if message.from_user else 0
    result = await backend.notification_settings(user_id, "digest")
    if result is None:
        await message.answer(skin.BACKEND_DOWN)
    elif result.updated == 0:
        await message.answer(skin.NOTIFY_NO_FILTERS)
    else:
        await message.answer(skin.RESUMED)
