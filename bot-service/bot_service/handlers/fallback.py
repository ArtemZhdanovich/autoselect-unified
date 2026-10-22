"""Кнопочный fallback-сбор: работает, когда AI-диалог недоступен (ТЗ п. 7.9).

Шаги и `callback_data` — прежние (`btn:{field}:{index}`, `ButtonForm`), а подача
взята из `deutsche_motors_bot`: «Шаг N/4», «Сбросить», одна живая панель.
"""

from __future__ import annotations

import html
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot_service.skin import deutsche as skin
from bot_service.states import ButtonForm
from bot_service.ui import keyboards, render
from bot_service.ui.panel import show_panel
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb
from shared.contracts.bot.limits import BUTTON_FLOW_STEPS

router = Router(name="fallback")

POPULAR_MAKES: tuple[str, ...] = (
    "Hyundai",
    "Kia",
    "Genesis",
    "BMW",
    "Mercedes-Benz",
    "Toyota",
    "Lexus",
)
YEAR_OPTIONS: tuple[str, ...] = ("2020–2022", "2022–2024", "2023–2025", "Не важно")
BUDGET_OPTIONS: tuple[str, ...] = (
    "до 30 000 $",
    "30 000–45 000 $",
    "45 000–60 000 $",
    "60 000+ $",
)

_CATALOG = {"make": POPULAR_MAKES, "year": YEAR_OPTIONS, "budget": BUDGET_OPTIONS}


def _reset_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Сбросить", callback_data=cb.cb_flow_reset())]
        ]
    )


def _step(step: int, question: str) -> str:
    return skin.FLOW_STEP.format(step=step, total=BUTTON_FLOW_STEPS, question=question)


def parse_years(text: str) -> dict:
    nums = [int(n) for n in re.findall(r"\d{4}", text)]
    if not nums:
        return {}
    return {"year_from": nums[0], "year_to": nums[-1]}


def parse_budget(text: str) -> dict:
    nums = [int(n.replace(" ", "")) for n in re.findall(r"\d[\d\s]*", text)]
    nums = [n for n in nums if not 1900 <= n <= 2100]  # годы — не деньги
    if "+" in text and nums:
        return {"price_min": nums[0]}
    if len(nums) >= 2:
        return {"price_min": nums[0], "price_max": nums[1]}
    if nums:
        return {"price_max": nums[0]}
    return {}


async def start_button_flow(message: Message, state: FSMContext) -> None:
    """Вход в кнопочный режим: первый шаг — марка."""
    await state.set_state(ButtonForm.make)
    await show_panel(
        message,
        state,
        f"{skin.FLOW_UNAVAILABLE}\n\n{_step(1, skin.FLOW_MAKE)}",
        keyboards.flow_kb("make", list(POPULAR_MAKES)),
    )


async def _finalize(
    message: Message, state: FSMContext, data: dict, backend: BackendPort
) -> None:
    """Запуск поиска по собранным кнопками критериям."""
    user_id = message.from_user.id if message.from_user else 0
    result = await backend.dialog_finalize(user_id, criteria=data)
    await state.clear()
    if result is None:
        await show_panel(message, state, skin.FLOW_FAILED, _reset_kb())
        return

    sources = ", ".join(result.sources or []) or "нет активных источников"
    criteria = result.criteria or data
    mini = keyboards.miniapp_button(skin.BTN_APP_PICK)
    rows: list[list[InlineKeyboardButton]] = []
    if mini:
        rows.append([mini])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    await show_panel(
        message,
        state,
        skin.FLOW_DONE.format(criteria=render.criteria_text(criteria), sources=sources),
        keyboard,
    )


@router.callback_query(F.data.startswith("btn:"))
async def btn_click(
    callback: CallbackQuery, state: FSMContext, backend: BackendPort
) -> None:
    """Кнопки шагов: марка / годы / бюджет / сброс."""
    message = callback.message
    assert message is not None

    parsed = cb.parse(callback.data)
    if isinstance(parsed, cb.FlowReset):
        await callback.answer()
        await state.clear()
        await message.edit_text(skin.DIALOG_RESET, reply_markup=None)
        return

    assert isinstance(parsed, cb.FlowOption)
    catalog = _CATALOG.get(parsed.field)
    if catalog is None or parsed.index >= len(catalog):
        await callback.answer(skin.FLOW_BAD_BUTTON)
        return

    choice = catalog[parsed.index]
    await callback.answer()

    if parsed.field == "make":
        await state.update_data(make=choice)
        await state.set_state(ButtonForm.model)
        await show_panel(
            message,
            state,
            f"✅ Марка: <b>{html.escape(choice)}</b>\n\n{_step(2, skin.FLOW_MODEL)}",
            _reset_kb(),
        )
        return

    if parsed.field == "year":
        await state.update_data(**parse_years(choice))
        await state.set_state(ButtonForm.budget)
        await show_panel(
            message,
            state,
            f"✅ Годы: <b>{html.escape(choice)}</b>\n\n{_step(4, skin.FLOW_BUDGET)}",
            keyboards.flow_kb("budget", list(BUDGET_OPTIONS)),
        )
        return

    if parsed.field == "budget":
        await state.update_data(**parse_budget(choice))
        data = await state.get_data()
        data["country"] = "KR"  # MVP: работаем только с Кореей
        data["created_from_dialog"] = True
        await _finalize(message, state, data, backend)


@router.message(ButtonForm.make, F.text)
async def fsm_make(message: Message, state: FSMContext) -> None:
    await state.update_data(make=message.text)
    await state.set_state(ButtonForm.model)
    await show_panel(
        message,
        state,
        f"✅ Марка: <b>{html.escape(message.text or '')}</b>\n\n{_step(2, skin.FLOW_MODEL)}",
        _reset_kb(),
    )


@router.message(ButtonForm.model, F.text)
async def fsm_model(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    model = None if raw.lower() == skin.FLOW_SKIP.lower() else raw
    await state.update_data(model=model)
    await state.set_state(ButtonForm.year)
    await show_panel(
        message,
        state,
        f"✅ Модель: <b>{html.escape(model or '—')}</b>\n\n{_step(3, skin.FLOW_YEAR)}",
        keyboards.flow_kb("year", list(YEAR_OPTIONS)),
    )


@router.message(ButtonForm.year, F.text)
async def fsm_year(message: Message, state: FSMContext) -> None:
    await state.update_data(**parse_years(message.text or ""))
    await state.set_state(ButtonForm.budget)
    await show_panel(
        message,
        state,
        f"✅ Годы: <b>{html.escape(message.text or '—')}</b>\n\n{_step(4, skin.FLOW_BUDGET)}",
        keyboards.flow_kb("budget", list(BUDGET_OPTIONS)),
    )


@router.message(ButtonForm.budget, F.text)
async def fsm_budget(message: Message, state: FSMContext, backend: BackendPort) -> None:
    await state.update_data(**parse_budget(message.text or ""))
    data = await state.get_data()
    data["country"] = "KR"
    data["created_from_dialog"] = True
    await _finalize(message, state, data, backend)
