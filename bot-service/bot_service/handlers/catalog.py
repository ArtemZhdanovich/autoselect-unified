"""Каталог и фото-карточка: `catalog:*`, `car:*`, `car_image:*` (UI из эталона)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards, render
from bot_service.ui.panel import edit_or_answer
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb
from shared.contracts.listing import ListingOut

logger = logging.getLogger(__name__)

router = Router(name="catalog")

#: Столько карточек на страницу — как в `deutsche_motors_bot` (`CARS_PER_PAGE = 4`).
PER_PAGE = 4


def photo_urls(listing: ListingOut) -> list[str]:
    """Только абсолютные http(s)-картинки: Telegram не принимает относительные."""
    return [str(image) for image in (listing.images or []) if str(image).startswith("http")]


async def show_card(message: Message, listing: ListingOut, page: int) -> None:
    """Карточка авто: фото с подписью и навигацией; без фото — текстом."""
    caption = render.caption(listing)
    images = photo_urls(listing)

    if not images:
        await message.answer(
            caption,
            reply_markup=keyboards.photo_card_kb(
                listing, page, 0, 0, cb.cb_catalog(page)
            ),
        )
        return

    keyboard = keyboards.photo_card_kb(listing, page, 0, len(images), cb.cb_catalog(page))
    try:
        await message.delete()
    except Exception:  # сообщение могло быть уже удалено — не критично
        pass
    await message.answer_photo(photo=images[0], caption=caption, reply_markup=keyboard)


@router.callback_query(F.data.startswith("catalog:"))
async def show_catalog(callback: CallbackQuery, backend: BackendPort) -> None:
    """Список авто: пагинация по 4, «Далее» только если есть что показать."""
    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.CatalogPage)
    page = parsed.page

    found = await backend.search_listings_page(
        {"sort": "new"}, limit=PER_PAGE + 1, offset=page * PER_PAGE
    )
    if found is None:
        await callback.answer(skin.BACKEND_DOWN, show_alert=True)
        return
    if not found.items:
        await callback.answer(skin.CATALOG_EMPTY, show_alert=True)
        return

    items = found.items[:PER_PAGE]
    has_next = found.total > (page + 1) * PER_PAGE
    await callback.answer()
    await edit_or_answer(
        callback, skin.CATALOG_TITLE, keyboards.catalog_kb(items, page, has_next)
    )


@router.callback_query(F.data.startswith("car:"))
async def show_car(callback: CallbackQuery, backend: BackendPort) -> None:
    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.CatalogCar)

    listing = await backend.get_listing(parsed.car_id)
    message = callback.message
    assert message is not None
    if listing is None:
        await callback.answer(skin.CAR_GONE, show_alert=True)
        return

    await callback.answer()
    await show_card(message, listing, parsed.page)


@router.callback_query(F.data == "car_image:noop")
async def image_noop(callback: CallbackQuery) -> None:
    """Счётчик `📷 1/4` — не действие, просто гасим «часики»."""
    await callback.answer()


@router.callback_query(F.data.startswith("car_image:"))
async def change_image(callback: CallbackQuery, backend: BackendPort) -> None:
    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.CatalogImage)

    listing = await backend.get_listing(parsed.car_id)
    message = callback.message
    assert message is not None
    if listing is None:
        await callback.answer(skin.CAR_GONE, show_alert=True)
        return

    images = photo_urls(listing)
    if not images or parsed.index >= len(images):
        await callback.answer(skin.IMAGE_GONE, show_alert=True)
        return

    keyboard = keyboards.photo_card_kb(
        listing, parsed.page, parsed.index, len(images), cb.cb_catalog(parsed.page)
    )
    try:
        await message.edit_media(
            media=InputMediaPhoto(media=images[parsed.index], caption=render.caption(listing)),
            reply_markup=keyboard,
        )
    except Exception:
        # Сообщение без фото (текстовая карточка) — пересоздаём.
        await message.answer_photo(
            photo=images[parsed.index],
            caption=render.caption(listing),
            reply_markup=keyboard,
        )
    await callback.answer()
