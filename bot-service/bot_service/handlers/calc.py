"""Калькулятор «под ключ»: `/calc` и `calc:{listing_id}` с карточки."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards, render
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb
from shared.contracts.bot.limits import MAX_COMPARE_ITEMS
from shared.contracts.listing import ListingOut

router = Router(name="calc")


def price_usd(listing: ListingOut) -> float | None:
    """Цена в USD: KRW/EUR конвертируем по фиксированному курсу MVP."""
    if not listing.price:
        return None
    currency = (listing.currency or "USD").upper()
    try:
        value = float(listing.price)
    except (TypeError, ValueError):
        return None
    if currency == "KRW":
        return round(value / 1350.0)
    if currency == "EUR":
        return round(value * 1.08)
    return round(value)


def parse_variants(text: str) -> list[tuple[float, int, int]]:
    """Варианты сравнения: «18000 2000 2022 vs 15000 1600 2021»."""
    chunks = re.split(r"(?:\bvs\b|;|\||\n)+", text, flags=re.IGNORECASE)
    result: list[tuple[float, int, int]] = []
    for chunk in chunks:
        raw = re.findall(r"\d+", chunk)
        # склейка тысяч: «18 000» → 18000
        merged: list[str] = []
        index = 0
        while index < len(raw):
            if index + 1 < len(raw) and len(raw[index]) <= 2 and len(raw[index + 1]) == 3:
                merged.append(raw[index] + raw[index + 1])
                index += 2
            else:
                merged.append(raw[index])
                index += 1
        if len(merged) < 2:
            continue
        price = float(merged[0])
        engine_cc = int(merged[1]) if len(merged) >= 3 else 2000
        year = int(merged[-1])
        if price > 0 and 1900 <= year <= 2100 and 50 <= engine_cc <= 10_000:
            result.append((price, engine_cc, year))
    return result


@router.callback_query(F.data.startswith("calc:"))
async def calc_from_card(callback: CallbackQuery, backend: BackendPort) -> None:
    """Смета прямо с карточки объявления (цена и год берутся из лота)."""
    await callback.answer("Считаю…")
    message = callback.message
    assert message is not None

    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.CardCalc)

    listing = await backend.get_listing(parsed.listing_id)
    if listing is None:
        await message.answer(skin.CAR_GONE)
        return

    usd = price_usd(listing)
    if not usd or not listing.year:
        await message.answer(skin.CALC_HINT)
        return

    out = await backend.calc_delivery(
        usd,
        int(listing.engine_volume * 1000) if listing.engine_volume else 2000,
        int(listing.year),
    )
    if out is None:
        await message.answer(skin.BACKEND_DOWN)
        return

    await message.answer(
        render.calc_text(out),
        reply_markup=keyboards.calc_kb(
            f"/calc?price={out.price_usd:.0f}&cc={out.engine_cc}&year={out.year}"
        ),
    )


@router.message(Command("calc"))
async def cmd_calc(
    message: Message, command: CommandObject | None, backend: BackendPort
) -> None:
    """/calc 18000 2000 2022 — смета; «A vs B» — сравнение вариантов."""
    variants = parse_variants(command.args if command else "")

    if len(variants) >= 2:
        payload = [
            {
                "price_usd": price,
                "engine_cc": engine_cc,
                "year": year,
                "title": f"{render.num(price)} $ · {engine_cc} см³ · {year}",
            }
            for price, engine_cc, year in variants[:MAX_COMPARE_ITEMS]
        ]
        compared = await backend.compare_delivery(payload)
        if compared and compared.items:
            await message.answer(
                render.compare_text(compared.items), reply_markup=keyboards.compare_kb()
            )
            return

    if len(variants) == 1:
        price, engine_cc, year = variants[0]
        out = await backend.calc_delivery(price, engine_cc, year)
        if out is not None:
            await message.answer(
                render.calc_text(out),
                reply_markup=keyboards.calc_kb(
                    f"/calc?price={price:.0f}&cc={engine_cc}&year={year}"
                ),
            )
            return

    await message.answer(skin.CALC_HINT, reply_markup=keyboards.calc_kb("/calc"))
