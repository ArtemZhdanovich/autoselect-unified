"""Точка входа backend-service.

Запуск: `uvicorn backend_service.main:app --port 8000` при `SERVICE=backend|all`.
Контракт `/api/*` совпадает с `auto_bot` — см. `shared/contracts` и
`docs/STAGE1_ANALYSIS.md` §2.5.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend_service.api import billing, calc, catalog, dialog, health, identity
from backend_service.api.deps import env_settings
from backend_service.container import build_container
from shared.contracts.analysis import AnalysisUnavailable, QuotaExceeded
from shared.settings import ConfigError, Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or env_settings()
    if resolved.service not in ("backend", "all"):
        raise ConfigError(
            f"SERVICE={resolved.service!r}: backend-service стартует только при SERVICE=backend|all"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=resolved.log_level)
        logger.info("backend_service_started service=%s mode=%s", resolved.service, resolved.mode)
        yield
        await app.state.container.close()
        logger.info("backend_service_stopped")

    app = FastAPI(
        title="autoselect backend-service",
        version="0.2.0",
        description="Домен и BL объединённого бота. Контракт /api/* унаследован от auto_bot.",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.container = build_container(resolved)

    # --- ошибки портов → HTTP-коды, которых ждёт бот ------------------------
    @app.exception_handler(QuotaExceeded)
    async def _quota(_: Request, exc: QuotaExceeded) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(AnalysisUnavailable)
    async def _analysis_unavailable(_: Request, exc: AnalysisUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ConnectionError)
    async def _dependency_down(_: Request, exc: ConnectionError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc) or "dependency unavailable"})

    @app.exception_handler(KeyError)
    async def _not_found(_: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _bad_request(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(health.router)
    app.include_router(identity.router)
    app.include_router(identity.auth)
    app.include_router(identity.notifications)
    app.include_router(catalog.router)
    app.include_router(catalog.bot_router)
    app.include_router(dialog.router)
    app.include_router(dialog.ai_router)
    app.include_router(calc.router)
    app.include_router(billing.router)
    return app


app = create_app()


def main() -> None:  # pragma: no cover - используется в Docker CMD
    import uvicorn

    uvicorn.run("backend_service.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
