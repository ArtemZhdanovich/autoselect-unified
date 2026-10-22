"""Уведомления — контракт `/api/notifications/settings` (internal), перенесён 1:1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class NotifySettingsIn(BaseModel):
    user_id: int
    # None = не менять режим (только тихие часы)
    notify_mode: Literal["instant", "digest", "off"] | None = None
    quiet_hours: str | None = None  # "23:00-08:00" или None
    # Явно сбросить тихие часы (отличить от «не передано»)
    quiet_hours_clear: bool = False


class NotifySettingsOut(BaseModel):
    user_id: int
    updated: int
