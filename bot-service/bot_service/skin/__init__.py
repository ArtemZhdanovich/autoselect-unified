"""Скины бота. Сейчас один — `deutsche`; второй (`legacy`) появится при откате UI.

Скин — это только слова. Структура сообщений и `callback_data` лежат в
`shared/contracts`, поэтому смена скина не может сломать контракт.
"""

from bot_service.skin import deutsche

__all__ = ["deutsche"]
