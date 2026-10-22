"""Настройки bot-service (кэшированный снимок окружения)."""

from __future__ import annotations

from functools import lru_cache

from shared.settings import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
