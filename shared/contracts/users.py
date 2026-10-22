"""Пользователи — контракт `/api/users/upsert` и `/api/me`, перенесён 1:1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserUpsert(BaseModel):
    """Данные для создания/обновления пользователя (используется ботом)."""

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    role: Literal["buyer", "dealer", "salon", "admin"]
    subscription_tier: Literal["free", "pro", "business"]
    subscription_until: datetime | None
    created_at: datetime
    is_active: bool
    onboarded_at: datetime | None = None


class LoginLinkConfirmIn(BaseModel):
    """POST /api/auth/telegram/link/confirm — вход на сайт через `/start login_<code>`."""

    code: str
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


class LoginLinkConfirmOut(BaseModel):
    status: str
