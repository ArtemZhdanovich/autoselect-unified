"""Зависимости FastAPI: настройки, контейнер портов, проверка internal-заголовка."""

from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from backend_service.container import Container
from shared.http_headers import AUTH_HEADER
from shared.settings import Settings


@lru_cache(maxsize=1)
def env_settings() -> Settings:
    """Снимок окружения — дефолт для сервиса, собранного без явных настроек."""
    return Settings.from_env()


def get_settings(request: Request) -> Settings:
    """Настройки конкретного приложения (позволяет поднимать несколько в тестах)."""
    settings = getattr(request.app.state, "settings", None)
    return settings if settings is not None else env_settings()


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - защита от неверной сборки app
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="container is not initialised",
        )
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_internal(
    supplied: str | None = Header(default=None, alias=AUTH_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Проверка внутреннего заголовка в постоянном времени.

    401 (а не 403) — намеренно: ровно так отвечает `auto_bot`
    (`check_internal_token`), и бот на это рассчитывает.
    """
    expected = settings.internal_token
    if supplied is None or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token"
        )


InternalDep = Annotated[None, Depends(require_internal)]
