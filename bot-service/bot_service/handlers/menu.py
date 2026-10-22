"""Главное меню и команды: `/start`, `/menu`, `/help`, `/reset`, `menu:*`."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot_service.handlers.deeplink import handle_deep_link
from bot_service.handlers.subscribe import show_subscription
from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards
from bot_service.ui.panel import edit_or_answer
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb

router = Router(name="menu")

#: Действия, которые обслуживает именно этот модуль (уведомления — в notify.py).
_MENU_ACTIONS = ("main", "more", "ai", "compare", "calc", "help", "reset", "subscribe")


@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject | None,
    state: FSMContext,
    backend: BackendPort,
) -> None:
    """Онбординг: регистрируем пользователя, обрабатываем deep link, показываем меню."""
    await state.clear()

    user = message.from_user
    if user is not None:
        await backend.upsert_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )

    args = command.args if command else None
    if args and await handle_deep_link(message, args, backend):
        return

    await message.answer(skin.WELCOME, reply_markup=keyboards.main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(skin.MENU_TITLE, reply_markup=keyboards.main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(skin.HELP, reply_markup=keyboards.main_menu_kb())


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, backend: BackendPort) -> None:
    """Сброс диалога: чистим FSM и архив сессии на бэкенде."""
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    await backend.dialog_reset(user_id)
    await message.answer(skin.DIALOG_RESET_CMD)


@router.callback_query(F.data.in_({f"menu:{action}" for action in _MENU_ACTIONS}))
async def menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    backend: BackendPort,
) -> None:
    """Диспетчер главного меню: единая точка для `menu:*`."""
    action = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id
    message = callback.message
    assert message is not None  # callback всегда приходит с сообщением

    if action == "main":
        await callback.answer()
        await state.clear()
        await edit_or_answer(callback, skin.WELCOME, keyboards.main_menu_kb())
        return

    if action == "more":
        await callback.answer()
        await edit_or_answer(callback, skin.MENU_MORE_TITLE, keyboards.more_menu_kb())
        return

    if action == "ai":
        await callback.answer()
        await state.clear()
        await edit_or_answer(
            callback,
            skin.MENU_AI_HINT,
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=skin.BTN_RESTORE,
                            callback_data=cb.cb_dialog("restore"),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=skin.BTN_BACK_MAIN,
                            callback_data=cb.cb_menu("main"),
                        )
                    ],
                ]
            ),
        )
        return

    if action == "compare":
        await callback.answer()
        await message.answer(
            skin.COMPARE_HINT, reply_markup=keyboards.compare_kb()
        )
        return

    if action == "calc":
        await callback.answer()
        await message.answer(skin.CALC_HINT, reply_markup=keyboards.calc_kb("/calc"))
        return

    if action == "notify":
        # Обрабатывается в notify.py; сюда не попадает (см. фильтр действий).
        await callback.answer()
        return

    if action == "subscribe":
        await callback.answer()
        await show_subscription(message, backend, user_id)
        return

    if action == "reset":
        await callback.answer()
        await state.clear()
        await backend.dialog_reset(user_id)
        await edit_or_answer(callback, skin.DIALOG_RESET, keyboards.main_menu_kb())
        return

    if action == "help":
        await callback.answer()
        await edit_or_answer(callback, skin.HELP, keyboards.main_menu_kb())
