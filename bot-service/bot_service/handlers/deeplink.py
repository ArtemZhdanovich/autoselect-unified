"""Deep links: `listing_`, `filter_`, `login_`, `ref_`.

Формат параметров — часть контракта (`auto_bot/handlers.py:handle_deep_link`).
Функция не регистрирует роутер: её вызывает `cmd_start` после `upsert_user`.
"""

from __future__ import annotations

import html
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards, render
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb

logger = logging.getLogger(__name__)


async def handle_deep_link(message: Message, args: str, backend: BackendPort) -> bool:
    """True — deep link обработан, обычный онбординг не нужен."""
    if args.startswith("listing_"):
        try:
            listing_id = int(args.removeprefix("listing_"))
        except ValueError:
            return False

        listing = await backend.get_listing(listing_id)
        if listing is None:
            await message.answer(skin.DEEPLINK_LISTING_MISS)
            return True

        caption = render.caption(listing)
        reply_markup = keyboards.card_kb(listing)
        images = listing.images or []
        if images:
            await message.answer_photo(
                photo=str(images[0]), caption=caption, reply_markup=reply_markup
            )
        else:
            await message.answer(caption, reply_markup=reply_markup)
        return True

    if args.startswith("filter_"):
        mini = keyboards.miniapp_button(skin.BTN_APP_FILTER)
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[[mini]]) if mini else None
        await message.answer(skin.DEEPLINK_FILTER, reply_markup=reply_markup)
        return True

    if args.startswith("login_"):
        code = args.removeprefix("login_")
        user = message.from_user
        result = await backend.confirm_login_link(
            code=code,
            telegram_id=user.id if user else 0,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            language_code=user.language_code if user else None,
        )
        status = result.status if result else "expired"
        await message.answer(skin.LOGIN_OK if status == "ok" else skin.LOGIN_EXPIRED)
        return True

    if args.startswith("ref_"):
        # Рефералка вне рамок Этапа 2: фиксируем переход в лог, онбординг продолжаем.
        logger.info(
            "referral_start: referrer=%s user=%s",
            html.escape(args.removeprefix("ref_")),
            message.from_user.id if message.from_user else None,
        )
        return False

    return False
