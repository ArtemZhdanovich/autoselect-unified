"""Числовые лимиты Telegram-сообщений — часть контракта, а не «настройка вкуса».

Значения взяты из фактического кода `auto_bot` / ограничений Bot API.
Менять их можно только вместе с golden-тестами Этапа 3.
"""

from __future__ import annotations

#: Telegram: максимум символов в caption к фото.
MAX_CAPTION = 1024
#: Telegram: максимум символов в тексте сообщения.
MAX_MESSAGE_TEXT = 4096
#: `auto_bot/handlers.py`: options[:8] — больше кнопок панель не показывает.
MAX_DIALOG_OPTIONS = 8
#: `auto_bot/handlers.py`: items[:5] — фото-карточек в чат не больше пяти.
MAX_CARD_ITEMS = 5
#: `auto_bot/handlers.py`: _format_history(limit=6, max_len=160).
HISTORY_MESSAGES = 6
HISTORY_TRUNCATE = 160
#: `CompareIn.items` — не более 10 вариантов (схема API).
MAX_COMPARE_ITEMS = 10
#: Число шагов кнопочного fallback-сбора (`_STEP_TOTAL = 4`).
BUTTON_FLOW_STEPS = 4
