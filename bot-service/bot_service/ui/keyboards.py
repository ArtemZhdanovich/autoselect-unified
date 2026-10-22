"""Клавиатуры. Каждая кнопка собирается через реестр `callback_data`."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot_service.config import get_settings
from bot_service.skin import deutsche as skin
from shared.contracts.bot import callbacks as cb
from shared.contracts.bot.limits import MAX_DIALOG_OPTIONS
from shared.contracts.listing import ListingOut


def miniapp_button(text: str, path: str = "") -> InlineKeyboardButton | None:
    """Кнопка Mini App: `web_app` только для https, иначе обычный `url`.

    Требование Telegram: WebApp принимает исключительно HTTPS. Для локальной
    демки на http кнопка открывает приложение в браузере — как в `auto_bot`.
    """
    url = get_settings().miniapp_url
    if not url:
        return None
    if path:
        url = url.rstrip("/") + (path if path.startswith("/") else "/" + path)
    if url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=text, url=url)


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главный экран — ровно две крупные кнопки (решение D2)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=skin.BTN_AI, callback_data=cb.cb_menu("ai"))],
            [InlineKeyboardButton(text=skin.BTN_MORE, callback_data=cb.cb_menu("more"))],
        ]
    )


def more_menu_kb() -> InlineKeyboardMarkup:
    """Второй уровень: все прежние действия остаются достижимыми (≤2 клика)."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="🚗 Каталог", callback_data=cb.cb_catalog(0)),
            InlineKeyboardButton(text="💰 Подобрать по цене", callback_data=cb.cb_price_start()),
        ],
        [
            InlineKeyboardButton(text="🧮 Расчёт доставки", callback_data=cb.cb_menu("calc")),
            InlineKeyboardButton(text="⚖️ Сравнить", callback_data=cb.cb_menu("compare")),
        ],
        [
            InlineKeyboardButton(text="🔔 Уведомления", callback_data=cb.cb_menu("notify")),
            InlineKeyboardButton(text="⭐ Подписка", callback_data=cb.cb_menu("subscribe")),
        ],
    ]
    mini = miniapp_button(skin.BTN_APP)
    if mini:
        rows.append([mini])
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Сбросить диалог", callback_data=cb.cb_menu("reset")),
            InlineKeyboardButton(text="❓ Помощь", callback_data=cb.cb_menu("help")),
        ]
    )
    rows.append([InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dialog_kb(reply, turn: int, criteria: dict, search_ready: bool) -> InlineKeyboardMarkup:
    """Панель диалога: опции агента → «Искать» → приложение → сброс."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=option, callback_data=cb.cb_dialog_option(turn, index))]
        for index, option in enumerate((reply.options or [])[:MAX_DIALOG_OPTIONS])
    ]
    if reply.finalize_ready or search_ready:
        rows.append(
            [InlineKeyboardButton(text=skin.BTN_SEARCH, callback_data=cb.cb_dialog("finalize"))]
        )
    mini = miniapp_button(skin.BTN_APP_PICK)
    if mini:
        rows.append([mini])
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_RESET, callback_data=cb.cb_dialog("reset"))]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_kb(listing: ListingOut) -> InlineKeyboardMarkup:
    """Кнопки фото-карточки: источник, AI-разбор, доставка, приложение, меню."""
    rows: list[list[InlineKeyboardButton]] = []
    if listing.url:
        rows.append([InlineKeyboardButton(text=skin.BTN_OPEN_LISTING, url=str(listing.url))])
    rows.append(
        [
            InlineKeyboardButton(text=skin.BTN_ANALYZE, callback_data=cb.cb_analyze(listing.id)),
            InlineKeyboardButton(text=skin.BTN_DELIVERY, callback_data=cb.cb_calc(listing.id)),
        ]
    )
    mini = miniapp_button(skin.BTN_APP_CARD)
    if mini:
        rows.append([mini])
    rows.append([InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calc_kb(path: str = "") -> InlineKeyboardMarkup | None:
    mini = miniapp_button(skin.BTN_APP_CARD, path)
    if mini is None:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[mini]])


def compare_kb() -> InlineKeyboardMarkup | None:
    mini = miniapp_button(skin.BTN_APP_COMPARE, "/compare")
    if mini is None:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[mini]])


def notify_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=skin.BTN_NOTIFY_INSTANT, callback_data=cb.cb_menu_notify_set("instant"))],
            [InlineKeyboardButton(text=skin.BTN_NOTIFY_DIGEST, callback_data=cb.cb_menu_notify_set("digest"))],
            [InlineKeyboardButton(text=skin.BTN_NOTIFY_OFF, callback_data=cb.cb_menu_notify_set("off"))],
            [InlineKeyboardButton(text=skin.BTN_QUIET, callback_data=cb.cb_menu("quiet"))],
            [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))],
        ]
    )


def quiet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=skin.BTN_QUIET_23, callback_data=cb.cb_menu_quiet_set("23:00-08:00"))],
            [InlineKeyboardButton(text=skin.BTN_QUIET_22, callback_data=cb.cb_menu_quiet_set("22:00-10:00"))],
            [InlineKeyboardButton(text=skin.BTN_QUIET_OFF, callback_data=cb.cb_menu_quiet_set("off"))],
            [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))],
        ]
    )


def _tier_label(tier: str, days: int, amount: int) -> str:
    period = "год" if days >= 365 else "мес"
    name = "Pro" if tier == "pro" else "Business"
    return f"⭐ {name} — {amount}★/{period}"


def subscribe_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_tier_label("pro", 30, 500), callback_data=cb.cb_sub_buy("pro", 30))],
            [InlineKeyboardButton(text=_tier_label("pro", 365, 4800) + " (−20%)", callback_data=cb.cb_sub_buy("pro", 365))],
            [InlineKeyboardButton(text=_tier_label("business", 30, 2500), callback_data=cb.cb_sub_buy("business", 30))],
            [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))],
        ]
    )


def flow_kb(field: str, options: list[str]) -> InlineKeyboardMarkup:
    """Кнопки шага fallback-сбора: по одной на вариант + «Сбросить»."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=option, callback_data=cb.cb_flow(field, index))]
        for index, option in enumerate(options)
    ]
    rows.append([InlineKeyboardButton(text="🔄 Сбросить", callback_data=cb.cb_flow_reset())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_kb(items: list[ListingOut], page: int, has_next: bool) -> InlineKeyboardMarkup:
    """Список авто: по кнопке на карточку, «Далее», выход в меню."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{item.make} {item.model}", callback_data=cb.cb_car(item.id, page)
            )
        ]
        for item in items
    ]
    if has_next:
        rows.append(
            [InlineKeyboardButton(text=skin.BTN_NEXT, callback_data=cb.cb_catalog(page + 1))]
        )
    rows.append([InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))]
        ]
    )


def price_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=skin.BTN_CANCEL, callback_data=cb.cb_price_cancel())],
            [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))],
        ]
    )


def price_results_kb(
    items: list[ListingOut], page: int, has_next: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{item.make} {item.model}", callback_data=cb.cb_price_car(item.id, page)
            )
        ]
        for item in items
    ]
    if has_next:
        rows.append(
            [InlineKeyboardButton(text=skin.BTN_NEXT, callback_data=cb.cb_price_page(page + 1))]
        )
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_PRICE_CHANGE, callback_data=cb.cb_price_start())]
    )
    rows.append([InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def image_counter_button(index: int, count: int) -> InlineKeyboardButton:
    """Счётчик фото `📷 1/4` — «мёртвая» кнопка, чтобы пальцем не промахивались."""
    return InlineKeyboardButton(
        text=skin.IMAGE_COUNTER.format(index=index, count=count),
        callback_data=cb.cb_car_image_noop(),
    )


def arrow_left(listing_id: int, index: int, page: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="⬅️", callback_data=cb.cb_car_image(listing_id, index - 1, page)
    )


def arrow_right(listing_id: int, index: int, page: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="➡️", callback_data=cb.cb_car_image(listing_id, index + 1, page)
    )


def photo_card_kb(
    listing: ListingOut,
    page: int,
    index: int,
    count: int,
    back_callback: str,
) -> InlineKeyboardMarkup:
    """Фото-карточка: навигация `⬅️ 📷 N/M ➡️`, разбор, доставка, возврат.

    Паттерн из `deutsche_motors_bot`: счётчик — «мёртвая» кнопка (`car_image:noop`),
    стрелки появляются только когда есть куда листать.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if count > 1:
        navigation: list[InlineKeyboardButton] = []
        if index > 0:
            navigation.append(arrow_left(listing.id, index, page))
        navigation.append(image_counter_button(index + 1, count))
        if index < count - 1:
            navigation.append(arrow_right(listing.id, index, page))
        rows.append(navigation)

    rows.append(
        [
            InlineKeyboardButton(text=skin.BTN_ANALYZE, callback_data=cb.cb_analyze(listing.id)),
            InlineKeyboardButton(text=skin.BTN_DELIVERY, callback_data=cb.cb_calc(listing.id)),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_BACK_RESULTS, callback_data=back_callback)]
    )
    rows.append(
        [InlineKeyboardButton(text=skin.BTN_BACK_MAIN, callback_data=cb.cb_menu("main"))]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
