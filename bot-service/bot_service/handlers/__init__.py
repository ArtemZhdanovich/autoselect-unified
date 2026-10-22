"""Сборка роутеров бота.

Порядок включения — часть логики: сначала специфичные команды/колбэки и
state-хендлеры, в конце — `F.text` из диалога. Если переставить, свободный
текст начнёт перехватывать шаги подбора.
"""

from __future__ import annotations

from aiogram import Router

from bot_service.handlers import (
    calc,
    card,
    catalog,
    dialog,
    fallback,
    inline,
    menu,
    notify,
    price,
    subscribe,
)

#: Порядок важен: см. докстринг модуля.
_ROUTER_ORDER = (
    menu,
    notify,
    subscribe,
    calc,
    card,
    catalog,
    price,
    fallback,
    dialog,
    inline,
)


def build_router() -> Router:
    root = Router(name="root")
    for module in _ROUTER_ORDER:
        root.include_router(module.router)
    return root


__all__ = ["build_router"]
