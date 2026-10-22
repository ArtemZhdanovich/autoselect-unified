"""Единая конфигурация платформы.

Правило проекта: переключение mock ↔ real и выбор сервиса — **только через ENV**,
без правки кода. Здесь нет чтения файлов: конфиг полностью задаётся окружением,
что делает возможным `docker compose` с профилями и локальный запуск без инфры.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

SERVICES: tuple[str, ...] = ("bot", "backend", "all")
MODES: tuple[str, ...] = ("mock", "real")


class ConfigError(RuntimeError):
    """Некорректная конфигурация — падаем сразу, а не на первом запросе."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True, slots=True)
class Settings:
    """Снимок окружения. Иммутабельный: сервис получает один объект на процесс."""

    service: str = "all"
    mode: str = "mock"

    bot_token: str = ""
    bot_username: str = ""

    #: Секрет внутренних эндпоинтов (`X-Internal-Token`).
    internal_token: str = "dev-internal-token"
    app_secret_key: str = "dev-secret-change-me"

    #: Куда bot-service ходит за данными (`MODE=real`).
    backend_url: str = "http://localhost:8000"

    #: Legacy auto_bot API — источник правды на время миграции (strangler).
    legacy_backend_url: str = ""

    miniapp_url: str = ""
    redis_url: str = ""

    log_level: str = "INFO"
    http_timeout_sec: float = 10.0
    dialog_timeout_sec: float = 120.0

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            service=_env("SERVICE", "all").lower(),
            mode=_env("MODE", "mock").lower(),
            bot_token=_env("BOT_TOKEN"),
            bot_username=_env("BOT_USERNAME").lstrip("@"),
            internal_token=_env("INTERNAL_TOKEN") or _env("APP_SECRET_KEY", "dev-internal-token"),
            app_secret_key=_env("APP_SECRET_KEY", "dev-secret-change-me"),
            backend_url=_env("BACKEND_URL", "http://localhost:8000").rstrip("/"),
            legacy_backend_url=_env("LEGACY_BACKEND_URL").rstrip("/"),
            miniapp_url=_env("MINIAPP_URL").rstrip("/"),
            redis_url=_env("REDIS_URL"),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            http_timeout_sec=float(_env("HTTP_TIMEOUT_SEC", "10") or 10),
            dialog_timeout_sec=float(_env("DIALOG_TIMEOUT_SEC", "120") or 120),
        )
        return settings.validate()

    def validate(self) -> Settings:
        if self.service not in SERVICES:
            raise ConfigError(
                f"SERVICE={self.service!r} не поддерживается; допустимо: {', '.join(SERVICES)}"
            )
        if self.mode not in MODES:
            raise ConfigError(
                f"MODE={self.mode!r} не поддерживается; допустимо: {', '.join(MODES)}"
            )
        return self

    # ------------------------------------------------------------------ режимы

    def adapter_mode(self, name: str) -> str:
        """Режим конкретного порта: `ADAPTER_<NAME>` перекрывает общий `MODE`.

        Пример: `MODE=mock ADAPTER_LLM=real` — всё мокнуто, кроме LLM.
        """
        value = _env(f"ADAPTER_{name.upper()}").lower()
        if not value:
            return self.mode
        if value not in MODES:
            raise ConfigError(
                f"ADAPTER_{name.upper()}={value!r} не поддерживается; допустимо: {', '.join(MODES)}"
            )
        return value

    # ------------------------------------------------------------------ утилиты

    def for_service(self, service: str) -> Settings:
        """Копия с подменённым SERVICE — для запуска нескольких сервисов в тестах."""
        if service not in SERVICES:
            raise ConfigError(f"неизвестный сервис: {service!r}")
        return replace(self, service=service)

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def require_bot_token(self) -> str:
        if not self.bot_token:
            raise ConfigError("BOT_TOKEN не задан — заполните .env или окружение")
        return self.bot_token
