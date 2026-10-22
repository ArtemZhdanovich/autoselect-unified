"""«Живая» панель: один редактируемый месседж вместо потока новых.

Паттерн взят из `auto_bot` (`_show_panel`) и подтверждён в `deutsche_motors_bot`:
id панели лежит в FSM (`panel_msg_id`), поэтому после рестарта бота старые
панели просто перестают редактироваться — новых сообщений это не плодит.
"""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def show_panel(
    message: Message,
    state: FSMContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Отредактировать панель на месте; новое сообщение — только если её нет."""
    data = await state.get_data()
    panel_id = data.get("panel_msg_id")
    if panel_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=panel_id,
                text=text,
                reply_markup=keyboard,
            )
            return
        except Exception:  # панель могла быть фото/удалена — тогда шлём новую
            pass
    sent = await message.answer(text, reply_markup=keyboard)
    await state.update_data(panel_msg_id=sent.message_id)


async def edit_or_answer(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Ответ на callback: правим сообщение, а если нельзя (фото) — шлём новое."""
    message = callback.message
    if message is None:
        return
    try:
        await message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await message.answer(text, reply_markup=keyboard)


async def drop_panel(message: Message, state: FSMContext) -> None:
    """Удалить панель (например, перед отправкой фото-карточки)."""
    data = await state.get_data()
    panel_id = data.get("panel_msg_id")
    if not panel_id:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=panel_id)
    except Exception:
        pass
    await state.update_data(panel_msg_id=None)
