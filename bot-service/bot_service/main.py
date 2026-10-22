"""Точка входа bot-service: polling, FSM, регистрация команд.

`SERVICE=bot` — сервис самодостаточен: при `MODE=mock` бэкенд не нужен вовсе,
FSM уходит в память. При `MODE=real` работает обычный HTTP-клиент к
backend-service, а FSM (если задан `REDIS_URL`) — в Redis.
"""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    ErrorEvent,
    MenuButtonWebApp,
    WebAppInfo,
)

from bot_service.config import get_settings
from bot_service.handlers import build_router
from bot_service.middlewares import BackendMiddleware
from bot_service.port import build_backend
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot.commands import BOT_COMMANDS, MENU_BUTTON_TEXT
from shared.settings import Settings

logger = logging.getLogger(__name__)


def build_storage(settings: Settings) -> BaseStorage:
    """Redis, если он настроен и доступен пакет `redis`; иначе память.

    Ключи FSM остаются дефолтными для aiogram — как в `auto_bot`, где
    использовался `RedisStorage.from_url`. Формат ключей не меняется.
    """
    if settings.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage

            return RedisStorage.from_url(settings.redis_url)
        except Exception as exc:  # нет пакета/битый URL — не роняем бота
            logger.warning("fsm_redis_unavailable: %s — использую MemoryStorage", exc)
    return MemoryStorage()


def build_dispatcher(
    backend: BackendPort | None = None, settings: Settings | None = None
) -> Dispatcher:
    """Собрать Dispatcher: storage, middleware с портом, роутеры, обработчик ошибок."""
    resolved = settings or get_settings()
    dispatcher = Dispatcher(storage=build_storage(resolved))
    dispatcher.update.outer_middleware(BackendMiddleware(backend or build_backend(resolved)))
    dispatcher.include_router(build_router())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> bool:
        """Лог + вежливое сообщение вместо тишины (как в `auto_bot`)."""
        logger.exception("handler_error: %s", event.exception)
        message = event.update.message
        callback = event.update.callback_query
        try:
            if message is not None:
                await message.answer("😔 Что-то пошло не так — я уже разбираюсь. Попробуйте ещё раз.")
            elif callback is not None:
                await callback.answer("Что-то сломалось, попробуйте ещё раз", show_alert=True)
        except Exception:  # уведомление не должно маскировать исходную ошибку
            logger.debug("error_notify_failed", exc_info=True)
        return True

    return dispatcher


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.require_bot_token(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def register_commands(bot: Bot, settings: Settings) -> None:
    """Меню команд и кнопка Mini App — контракт `set_my_commands`."""
    await bot.set_my_commands(
        [BotCommand(command=name, description=description) for name, description in BOT_COMMANDS],
        scope=BotCommandScopeAllPrivateChats(),
    )
    if settings.miniapp_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=MENU_BUTTON_TEXT, web_app=WebAppInfo(url=settings.miniapp_url)
            )
        )
    elif settings.miniapp_url:
        logger.warning(
            "miniapp_url не HTTPS (%s) — кнопка-меню Mini App не установлена",
            settings.miniapp_url,
        )


async def main() -> None:  # pragma: no cover - требует реального BOT_TOKEN
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    if settings.service not in ("bot", "all"):
        raise RuntimeError(
            f"SERVICE={settings.service!r}: bot-service стартует только при SERVICE=bot|all"
        )

    backend = build_backend(settings)
    bot = build_bot(settings)
    dispatcher = build_dispatcher(backend=backend, settings=settings)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await register_commands(bot, settings)
        logger.info("bot_service_started mode=%s", settings.mode)
        await dispatcher.start_polling(bot)
    finally:
        await backend.aclose()
        await bot.session.close()


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(main())
