"""Контракт диалога: запросы/ответы `/api/dialog/*` и `/api/ai/*`.

`DialogReplyResponse` перенесён из `auto_bot/app/api/dialog.py` 1:1.
`DialogFinalizeOut` / `DialogRestoreOut` описывают уже существующий JSON-ответ
(auto_bot отдавал `dict` с теми же ключами) — форма не меняется, меняется только
способ типизации.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from shared.contracts.criteria import SearchCriteria


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=_utcnow)
    tool_name: str | None = None


class DialogState(BaseModel):
    """Состояние AI-диалога (хранится в Redis за `DialogStore`)."""

    session_id: str
    user_id: int

    criteria: SearchCriteria = Field(default_factory=SearchCriteria)

    asked_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    freeform_notes: list[str] = Field(default_factory=list)
    answered_questions: list[str] = Field(default_factory=list)

    messages: list[Message] = Field(default_factory=list)

    status: Literal["collecting", "ready", "searching", "done"] = "collecting"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    turn_count: int = 0


class DialogMessageIn(BaseModel):
    user_id: int
    text: str


class DialogUserIn(BaseModel):
    user_id: int


class DialogFinalizeIn(BaseModel):
    user_id: int
    criteria: dict[str, Any] | None = None


class DialogReplyResponse(BaseModel):
    """Ответ одного хода диалога — ровно то, что рендерит панель бота."""

    session_id: str
    text: str
    options: list[str]
    status: str
    finalize_ready: bool
    turn_count: int
    criteria: dict[str, Any]


class DialogFinalizeOut(BaseModel):
    sources: list[str] = Field(default_factory=list)
    criteria: dict[str, Any] = Field(default_factory=dict)


class DialogRestoreOut(BaseModel):
    restored: bool = False
    messages: list[dict[str, Any]] = Field(default_factory=list)
    criteria: dict[str, Any] = Field(default_factory=dict)


class DialogResetOut(BaseModel):
    reset: bool = True
