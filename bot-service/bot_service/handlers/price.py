"""Подбор по цене: `price:start` → min → max → результаты (UX из эталона)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_service.skin import deutsche as skin
from bot_service.states import PriceSelection
from bot_service.ui import keyboards, render
from bot_service.ui.panel import edit_or_answer, show_panel
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb
from shared.contracts.listing import ListingOut

router = Router(name="price")

PER_PAGE = 4


def parse_price(raw: str) -> float | None:
    """«40 000» → 40000; «abc» → None."""
    cleaned = (raw or "").strip().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def price_range_text(min_price: float, max_price: float) -> str:
    return f"{render.num(min_price)}–{render.num(max_price)} $"


async def show_results(
    message: Message,
    state: FSMContext,
    backend: BackendPort,
    page: int,
) -> None:
    """Выдача по диапазону: пагинация и «Изменить параметры»."""
    data = await state.get_data()
    min_price = data.get("price_min")
    max_price = data.get("price_max")
    if min_price is None or max_price is None:
        await message.answer(skin.PRICE_TITLE.format(question=skin.PRICE_ASK_MIN),
                             reply_markup=keyboards.price_cancel_kb())
        return

    found = await backend.search_listings_page(
        {"price_min": min_price, "price_max": max_price, "sort": "price_asc"},
        limit=PER_PAGE + 1,
        offset=page * PER_PAGE,
    )
    if found is None:
        await message.answer(skin.BACKEND_DOWN)
        return

    range_text = price_range_text(min_price, max_price)
    if not found.items:
        await message.answer(
            skin.PRICE_EMPTY.format(range=range_text), reply_markup=keyboards.price_cancel_kb()
        )
        return

    items = found.items[:PER_PAGE]
    has_next = found.total > (page + 1) * PER_PAGE
    await message.answer(
        skin.PRICE_RESULTS.format(range=range_text),
        reply_markup=keyboards.price_results_kb(items, page, has_next),
    )


@router.callback_query(F.data == "price:start")
async def start_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PriceSelection.min_price)
    await callback.answer()
    await edit_or_answer(
        callback,
        skin.PRICE_TITLE.format(question=skin.PRICE_ASK_MIN),
        keyboards.price_cancel_kb(),
    )


@router.message(PriceSelection.min_price, F.text)
async def process_min(message: Message, state: FSMContext) -> None:
    value = parse_price(message.text or "")
    if value is None:
        await message.answer(
            skin.PRICE_BAD_NUMBER.format(example="40000"),
            reply_markup=keyboards.price_cancel_kb(),
        )
        return
    if value < 0:
        await message.answer(skin.PRICE_NEGATIVE, reply_markup=keyboards.price_cancel_kb())
        return

    await state.update_data(price_min=value)
    await state.set_state(PriceSelection.max_price)
    await message.answer(
        skin.PRICE_TITLE.format(question=skin.PRICE_ASK_MAX),
        reply_markup=keyboards.price_cancel_kb(),
    )


@router.message(PriceSelection.max_price, F.text)
async def process_max(message: Message, state: FSMContext, backend: BackendPort) -> None:
    value = parse_price(message.text or "")
    if value is None:
        await message.answer(
            skin.PRICE_BAD_NUMBER.format(example="70000"),
            reply_markup=keyboards.price_cancel_kb(),
        )
        return
    if value < 0:
        await message.answer(skin.PRICE_NEGATIVE, reply_markup=keyboards.price_cancel_kb())
        return

    data = await state.get_data()
    min_price = float(data.get("price_min") or 0)
    if value < min_price:
        await message.answer(
            skin.PRICE_INVERTED.format(min_price=f"{render.num(min_price)} $"),
            reply_markup=keyboards.price_cancel_kb(),
        )
        return

    await state.update_data(price_max=value)
    await show_results(message, state, backend, page=0)


@router.callback_query(F.data.startswith("price_page:"))
async def next_page(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.PricePage)

    data = await state.get_data()
    if data.get("price_min") is None or data.get("price_max") is None:
        await callback.answer(skin.PRICE_EMPTY.format(range="—"), show_alert=True)
        return

    await callback.answer()
    message = callback.message
    assert message is not None
    await show_results(message, state, backend, page=parsed.page)


@router.callback_query(F.data.startswith("price_car:"))
async def show_price_car(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    """Карточка из выдачи по цене: назад — к результатам подбора."""
    from bot_service.handlers.catalog import show_card

    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.PriceCar)

    listing = await backend.get_listing(parsed.car_id)
    message = callback.message
    assert message is not None
    if listing is None:
        await callback.answer(skin.CAR_GONE, show_alert=True)
        return

    await callback.answer()
    await show_card(message, listing, parsed.page)


@router.callback_query(F.data == "price:cancel")
async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await edit_or_answer(callback, skin.PRICE_CANCELLED, keyboards.main_menu_kb())
