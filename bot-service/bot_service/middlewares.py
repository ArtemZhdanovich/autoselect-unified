"""Middleware: прокидывает `BackendPort` в хендлеры.

Почему не глобал: зависимость должна приходить аргументом, чтобы её можно было
подменить в тестах и чтобы ни один хендлер не мог создать клиент сам.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from shared.contracts.backend_port import BackendPort


class BackendMiddleware(BaseMiddleware):
    """Кладёт реализацию порта в `data["backend"]`."""

    def __init__(self, backend: BackendPort) -> None:
        self.backend = backend

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["backend"] = self.backend
        return await handler(event, data)
