"""AI-диалог: панель, опции с токеном хода, финализация и свободный текст."""

from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards, render
from bot_service.ui.panel import edit_or_answer, show_panel
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb
from shared.contracts.bot.limits import MAX_CARD_ITEMS, MAX_DIALOG_OPTIONS
from shared.contracts.listing import ListingOut

logger = logging.getLogger(__name__)

router = Router(name="dialog")

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

#: Поля критериев, которые уходят в `GET /api/listings` как query-параметры.
_QUERY_FIELDS = (
    "make",
    "model",
    "year_from",
    "year_to",
    "price_max",
    "mileage_max",
    "body_type",
    "fuel",
    "transmission",
    "drive",
)


def extract_url(text: str) -> str | None:
    """Первая ссылка из текста (без хвостовой пунктуации)."""
    match = _URL_RE.search(text or "")
    return match.group(0).rstrip(").,>;") if match else None


def query_from_criteria(criteria: dict) -> dict:
    return {field: criteria[field] for field in _QUERY_FIELDS if criteria.get(field)}


def _first_image(listing: ListingOut) -> str | None:
    for image in listing.images or []:
        candidate = str(image)
        if candidate.startswith("http"):
            return candidate
    return None


async def send_cards(message: Message, items: list[ListingOut]) -> None:
    """Фото-карточки найденного: не больше пяти, с фолбэком в текст."""
    sent = 0
    for listing in items[:MAX_CARD_ITEMS]:
        caption = render.caption(listing)
        reply_markup = keyboards.card_kb(listing)
        photo = _first_image(listing)
        if photo:
            try:
                await message.answer_photo(
                    photo=photo, caption=caption, reply_markup=reply_markup
                )
                sent += 1
                continue
            except Exception as exc:  # картинка недоступна → текстовая карточка
                logger.debug("photo_send_failed id=%s: %s", listing.id, exc)
        await message.answer(caption, reply_markup=reply_markup)
        sent += 1
    if not sent:
        await message.answer(skin.NO_RESULTS)


async def send_reply(
    message: Message, reply, state: FSMContext
) -> None:
    """Показать ответ агента; опции и токен хода сохраняем в FSM."""
    data = await state.get_data()
    turn = int(data.get("dlg_turn", 0)) + 1
    options = list(reply.options or [])[:MAX_DIALOG_OPTIONS]
    criteria = reply.criteria or {}
    await state.update_data(dlg_turn=turn, dlg_options=options, dlg_criteria=criteria)
    keyboard = keyboards.dialog_kb(reply, turn, criteria, render.search_ready(criteria))
    await show_panel(message, state, render.dialog_text(reply.text, criteria), keyboard)


async def agent_turn(
    message: Message,
    text: str,
    state: FSMContext,
    backend: BackendPort,
    *,
    user_id: int | None = None,
) -> None:
    """Один ход диалога; при недоступности LLM — кнопочный режим."""
    if user_id is None:
        user_id = message.from_user.id if message.from_user else 0
    reply = await backend.dialog_message(user_id, text)
    if reply is None:
        from bot_service.handlers.fallback import start_button_flow

        logger.warning("dialog_unavailable_falling_back: user_id=%s", user_id)
        await start_button_flow(message, state)
        return
    await send_reply(message, reply, state)


@router.callback_query(F.data == "dlg:reset")
async def dialog_reset(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    await callback.answer()
    await state.clear()
    await backend.dialog_reset(callback.from_user.id)
    await edit_or_answer(callback, skin.DIALOG_RESET, keyboards.main_menu_kb())


@router.callback_query(F.data == "dlg:restore")
async def dialog_restore(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    """Поднять прошлый диалог: история + сохранённые критерии."""
    await callback.answer()
    message = callback.message
    assert message is not None

    result = await backend.dialog_restore(callback.from_user.id)
    if result is None:
        await message.answer(skin.BACKEND_DOWN)
        return
    if not result.restored:
        await message.answer(skin.RESTORE_EMPTY)
        return

    criteria = result.criteria or {}
    await state.update_data(dlg_criteria=criteria, dlg_turn=0, dlg_options=[])
    text = skin.RESTORE_HEADER.format(history=render.history_text(result.messages))
    if criteria:
        text += f"\n\n{skin.CRITERIA_HEADER}\n{render.criteria_text(criteria)}"

    rows: list[list[InlineKeyboardButton]] = []
    if render.search_ready(criteria):
        rows.append(
            [InlineKeyboardButton(text=skin.BTN_SEARCH, callback_data=cb.cb_dialog("finalize"))]
        )
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_RESET, callback_data=cb.cb_dialog("reset"))]
    )
    await show_panel(message, state, text, InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "dlg:finalize")
async def dialog_finalize(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    """Запуск поиска: домен ставит задачи парсинга, бот показывает, что нашлось."""
    await callback.answer()
    message = callback.message
    assert message is not None
    user_id = callback.from_user.id

    result = await backend.dialog_finalize(user_id)
    if result is None:
        await message.answer(skin.BACKEND_DOWN)
        return

    sources = ", ".join(result.sources or []) or "нет активных источников"
    mini = keyboards.miniapp_button(skin.BTN_APP_PICK)
    rows: list[list[InlineKeyboardButton]] = []
    if mini:
        rows.append([mini])
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_NEW_SEARCH, callback_data=cb.cb_dialog("reset"))]
    )
    await edit_or_answer(
        callback,
        skin.SEARCH_STARTED.format(sources=sources),
        InlineKeyboardMarkup(inline_keyboard=rows),
    )

    data = await state.get_data()
    criteria = data.get("dlg_criteria") or {}
    found = await backend.search_listings_page(query_from_criteria(criteria), limit=6)
    if found is None:
        return
    total = found.total
    if total == 0:
        await message.answer(skin.SEARCH_EMPTY)
        return
    if total <= MAX_CARD_ITEMS:
        await message.answer(render.found_few(total))
        await send_cards(message, found.items)
        return

    feed_rows: list[list[InlineKeyboardButton]] = []
    feed_mini = keyboards.miniapp_button(skin.BTN_APP_FEED.format(total=total), "")
    if feed_mini:
        feed_rows.append([feed_mini])
    feed_rows.append(
        [InlineKeyboardButton(text=skin.BTN_NEW_SEARCH, callback_data=cb.cb_dialog("reset"))]
    )
    await message.answer(
        render.found_many(total), reply_markup=InlineKeyboardMarkup(inline_keyboard=feed_rows)
    )


@router.callback_query(F.data.startswith("dlg:opt:"))
async def dialog_option(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    """Клик по опции: валиден только для текущего токена хода."""
    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.DialogOption)

    data = await state.get_data()
    if parsed.turn != int(data.get("dlg_turn", -1)):
        await callback.answer(skin.STALE_BUTTON)
        return

    options = data.get("dlg_options") or []
    if parsed.index >= len(options):
        await callback.answer(skin.STALE_BUTTON_TEXT)
        return

    option = options[parsed.index]
    await callback.answer()
    message = callback.message
    assert message is not None
    await agent_turn(message, option, state, backend, user_id=callback.from_user.id)


@router.message(F.text)
async def free_text(message: Message, state: FSMContext, backend: BackendPort) -> None:
    """Свободный текст: ссылка на объявление → карточка, иначе ход AI-диалога."""
    text = message.text or ""
    url = extract_url(text)
    if url:
        listing = await backend.get_listing_by_url(url)
        if listing is not None:
            await send_cards(message, [listing])
            return
    await agent_turn(message, text, state, backend)
