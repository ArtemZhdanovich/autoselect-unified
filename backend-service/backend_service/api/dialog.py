"""Диалог: `/api/dialog/*` (internal) и алиасы `/api/ai/*` (совместимость)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend_service.api.deps import ContainerDep, require_internal
from shared.contracts.dialog import (
    DialogFinalizeIn,
    DialogFinalizeOut,
    DialogMessageIn,
    DialogReplyResponse,
    DialogResetOut,
    DialogRestoreOut,
    DialogUserIn,
)

router = APIRouter(prefix="/api/dialog", tags=["dialog"], dependencies=[Depends(require_internal)])
#: `auto_bot` исторически имел второй вход для того же домена — сохраняем.
ai_router = APIRouter(prefix="/api/ai", tags=["ai-search"], dependencies=[Depends(require_internal)])


@router.post("/message", response_model=DialogReplyResponse)
@ai_router.post("/message", response_model=DialogReplyResponse)
async def dialog_message(body: DialogMessageIn, container: ContainerDep) -> DialogReplyResponse:
    """Ход AI-диалога. Долгий вызов: таймаут на стороне бота — 120 секунд."""
    return await container.dialog.message(body.user_id, body.text)


@router.post("/reset", response_model=DialogResetOut)
@ai_router.post("/reset", response_model=DialogResetOut)
async def dialog_reset(body: DialogUserIn, container: ContainerDep) -> DialogResetOut:
    return await container.dialog.reset(body.user_id)


@router.post("/restore", response_model=DialogRestoreOut)
async def dialog_restore(body: DialogUserIn, container: ContainerDep) -> DialogRestoreOut:
    """Поднять последний диалог из архива (TTL — сутки с последнего сообщения)."""
    return await container.dialog.restore(body.user_id)


@router.post("/finalize", response_model=DialogFinalizeOut)
@ai_router.post("/finalize", response_model=DialogFinalizeOut)
async def dialog_finalize(
    body: DialogFinalizeIn, container: ContainerDep
) -> DialogFinalizeOut:
    """Запуск поиска: домен ставит задачи парсинга и возвращает активные источники."""
    return await container.dialog.finalize(body.user_id, body.criteria)
