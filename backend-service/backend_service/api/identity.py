"""Пользователи и уведомления: `/api/users/upsert`, `/api/notifications/settings`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend_service.api.deps import ContainerDep, require_internal
from shared.contracts.notifications import NotifySettingsIn, NotifySettingsOut
from shared.contracts.users import LoginLinkConfirmIn, LoginLinkConfirmOut, UserOut, UserUpsert

router = APIRouter(prefix="/api/users", tags=["users"])
notifications = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_internal)],
)
auth = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/upsert", response_model=UserOut)
async def users_upsert(body: UserUpsert, container: ContainerDep) -> UserOut:
    """Создать/обновить пользователя по telegram_id (бот вызывает на /start)."""
    return await container.users.upsert(
        body.telegram_id,
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        language_code=body.language_code,
    )


@auth.post("/telegram/link/confirm", response_model=LoginLinkConfirmOut)
async def confirm_login_link(
    body: LoginLinkConfirmIn, container: ContainerDep
) -> LoginLinkConfirmOut:
    """Подтверждение веб-входа по одноразовому коду из deep link `login_<code>`."""
    return await container.users.confirm_login(body.code, body.telegram_id)


@notifications.post("/settings", response_model=NotifySettingsOut)
async def update_settings(
    payload: NotifySettingsIn, container: ContainerDep
) -> NotifySettingsOut:
    """Режим уведомлений и тихие часы применяются ко всем фильтрам пользователя."""
    return await container.notify.settings(
        payload.user_id,
        notify_mode=payload.notify_mode,
        quiet_hours=payload.quiet_hours,
        quiet_hours_clear=payload.quiet_hours_clear,
    )
