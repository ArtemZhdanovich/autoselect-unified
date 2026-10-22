"""Команды бота — контракт `set_my_commands`.

Порядок и текст описаний тоже видны клиенту в меню Telegram, поэтому список
зафиксирован: тест `test_contract_commands` сверяет его с эталоном `auto_bot`.
"""

from __future__ import annotations

from typing import Final

#: (command, description) — ровно как в `app/bot/__main__.py` (`set_my_commands`).
BOT_COMMANDS: Final[tuple[tuple[str, str], ...]] = (
    ("start", "Запуск / главное меню"),
    ("calc", "Калькулятор: цена $ объём год"),
    ("menu", "Меню"),
    ("reset", "Сбросить диалог подбора"),
    ("help", "Помощь"),
    ("stop", "Отписаться от уведомлений"),
)

#: Команды, которые обрабатываются, но не показываются в меню Telegram.
HIDDEN_COMMANDS: Final[tuple[str, ...]] = ("resume", "subscribe")

#: Команда, которой управляет кнопка-меню Mini App (не команда, но часть контракта UX).
MENU_BUTTON_TEXT: Final[str] = "🚗 Поиск авто"

#: Префиксы deep-link-параметров `?start=…`.
DEEP_LINK_PREFIXES: Final[tuple[str, ...]] = ("listing_", "filter_", "login_", "ref_", "app")


def is_known_command(name: str) -> bool:
    return name in {c for c, _ in BOT_COMMANDS} or name in HIDDEN_COMMANDS
