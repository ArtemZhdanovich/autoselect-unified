"""Системные эндпоинты: `/health` и `/health/detailed`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend_service.api.deps import ContainerDep, get_settings
from shared.settings import Settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    """Liveness: процесс жив и знает, в каком режиме работает."""
    return {"status": "ok", "service": settings.service, "mode": settings.mode}


@router.get("/health/detailed")
async def health_detailed(
    container: ContainerDep, settings: Settings = Depends(get_settings)
) -> JSONResponse:
    """Готовность зависимостей: отдаёт режим каждого порта и пробу каталога."""
    catalog_ok = True
    try:
        await container.catalog.get(1)
    except Exception:  # noqa: BLE001 — healthcheck не должен падать
        catalog_ok = False

    body = {
        "status": "ok" if catalog_ok else "degraded",
        "service": settings.service,
        "mode": settings.mode,
        "components": {
            "catalog": catalog_ok,
            **{
                name: settings.adapter_mode(name)
                for name in ("users", "dialog", "calc", "analysis", "billing", "notify")
            },
        },
    }
    return JSONResponse(status_code=200 if catalog_ok else 503, content=body)
