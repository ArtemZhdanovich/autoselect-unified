"""FSM-группы бота.

`ButtonForm` сохраняет прежнее имя и набор состояний: незавершённые сценарии
в Redis переживают деплой. `PriceSelection` — новая группа под экран
«подбор по цене» из `deutsche_motors_bot`.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ButtonForm(StatesGroup):
    """Кнопочный fallback-сбор, когда AI-диалог недоступен."""

    make = State()
    model = State()
    year = State()
    budget = State()


class PriceSelection(StatesGroup):
    """Подбор по цене: минимальная → максимальная → результаты."""

    min_price = State()
    max_price = State()
