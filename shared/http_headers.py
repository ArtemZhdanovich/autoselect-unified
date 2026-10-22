"""Заголовок авторизации внутренних вызовов.

Вынесено в отдельный модуль, чтобы имя заголовка не дублировалось по адаптерам:
значение всегда приходит из окружения (`INTERNAL_TOKEN`/`APP_SECRET_KEY`),
в репозитории секретов нет.
"""

from __future__ import annotations

#: Имя заголовка, которым бот и воркеры доказывают право звать internal-эндпоинты.
AUTH_HEADER = "X-Internal-Token"


def auth_headers(secret: str) -> dict[str, str]:
    """Заголовки для internal-запроса. `secret` берётся из настроек, не из кода."""
    return {AUTH_HEADER: secret}
