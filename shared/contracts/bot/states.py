"""FSM-контракт: имена групп/состояний и ключи данных в Redis.

Имена групп и состояний — часть контракта: они попадают в Redis (`fsm:{...}`),
в логи и в тесты `auto_bot`. Группа `ButtonForm` существует с прежним именем,
поэтому незавершённые диалоги переживают деплой без миграции хранилища.

`PriceSelection` — новое пространство (экран «подбор по цене» из
`deutsche_motors_bot`), оно не пересекается с прежними именами.
"""

from __future__ import annotations

from typing import Final

#: Группа кнопочного fallback (существовала в auto_bot).
BUTTON_FORM_GROUP: Final[str] = "ButtonForm"
BUTTON_FORM_STATES: Final[tuple[str, ...]] = ("make", "model", "year", "budget")

#: Группа подбора по цене (новый UX из deutsche_motors_bot).
PRICE_SELECTION_GROUP: Final[str] = "PriceSelection"
PRICE_SELECTION_STATES: Final[tuple[str, ...]] = ("min_price", "max_price")

#: Ключи, которыми бот пользуется в FSM-хранилище.
FSM_DATA_KEYS: Final[tuple[str, ...]] = (
    "panel_msg_id",   # id «живой» панели: edit_message_text вместо новых сообщений
    "dlg_turn",       # токен хода — защита от кликов по устаревшим кнопкам
    "dlg_options",
    "dlg_criteria",
    "make",
    "model",
    "year_from",
    "year_to",
    "price_min",
    "price_max",
    "country",
    "created_from_dialog",
)


def state_name(group: str, state: str) -> str:
    """Полное имя состояния в том виде, в каком его хранит aiogram."""
    return f"{group}:{state}"
