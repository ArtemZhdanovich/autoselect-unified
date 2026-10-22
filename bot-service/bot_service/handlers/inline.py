"""Inline-режим «Поделиться»: `listing:<id>` → карточка лота в любой чат."""

from __future__ import annotations

import re

from aiogram import Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from bot_service.config import get_settings
from bot_service.skin import deutsche as skin
from bot_service.ui import render
from shared.contracts.backend_port import BackendPort

router = Router(name="inline")

#: Запрос из `WebApp.switchInlineQuery("listing:<id>")` и старые варианты.
_LISTING_QUERY = re.compile(r"^listing[_:\-\s]?(\d+)$", re.IGNORECASE)


def share_keyboard(listing_id: int, url: str, bot_username: str) -> InlineKeyboardMarkup:
    """Кнопки inline-карточки: deep link в Mini App + источник."""
    rows: list[list[InlineKeyboardButton]] = []
    username = (bot_username or "").strip().lstrip("@")
    if username:
        rows.append(
            [
                InlineKeyboardButton(
                    text=skin.BTN_SHARE_APP,
                    url=f"https://t.me/{username}?startapp=listing_{listing_id}",
                )
            ]
        )
    if url:
        rows.append([InlineKeyboardButton(text=skin.BTN_SHARE_SOURCE, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.inline_query()
async def inline_listing_share(query: InlineQuery, backend: BackendPort) -> None:
    """Отдаём 0 или 1 результат: пустой/чужой запрос — просто ничего."""
    results: list[InlineQueryResultArticle] = []
    match = _LISTING_QUERY.match((query.query or "").strip())
    if match:
        listing = await backend.get_listing(int(match.group(1)))
        if listing is not None:
            username = get_settings().bot_username or (
                query.bot.username if query.bot else ""
            )
            caption = render.caption(listing)
            kwargs = {
                "id": f"listing_{listing.id}",
                "title": render_title(listing.make, listing.model, listing.year),
                "description": caption[:256] or None,
                "input_message_content": InputTextMessageContent(
                    message_text=caption, parse_mode="HTML", disable_web_page_preview=False
                ),
                "reply_markup": share_keyboard(listing.id, str(listing.url or ""), username),
            }
            thumbnail = next(
                (
                    str(url)
                    for url in (listing.images or [])
                    if str(url).split("?")[0].lower().endswith((".jpg", ".jpeg"))
                ),
                None,
            )
            if thumbnail:  # Telegram принимает thumb только JPEG
                kwargs["thumbnail_url"] = thumbnail
            results.append(InlineQueryResultArticle(**kwargs))

    await query.answer(results, cache_time=15, is_personal=True)


def render_title(make: str | None, model: str | None, year: int | None) -> str:
    title = " ".join(part for part in (make, model) if part) or "Автомобиль"
    if year:
        title = f"{title}, {year}"
    return title[:256]
