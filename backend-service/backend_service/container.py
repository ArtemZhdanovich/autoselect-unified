"""Сборка контейнера портов по ENV.

Единственное место, где `MODE`/`ADAPTER_*` превращается в конкретные классы.
Домен и роутеры видят только протоколы — поэтому переключение mock ↔ real
не требует правок кода (требование ТЗ).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend_service.adapters.legacy import (
    LegacyAnalysis,
    LegacyBilling,
    LegacyCalc,
    LegacyCatalog,
    LegacyClient,
    LegacyDialog,
    LegacyNotify,
    LegacyUsers,
)
from backend_service.ports import (
    AnalysisPort,
    BillingPort,
    CalcPort,
    CatalogPort,
    DialogPort,
    NotifyPort,
    UsersPort,
)
from shared.mocks.adapters import build_mock_services
from shared.settings import Settings

#: Имена портов — они же имена ENV-переопределений (`ADAPTER_CATALOG=real`).
PORT_NAMES: tuple[str, ...] = (
    "users",
    "catalog",
    "dialog",
    "calc",
    "analysis",
    "billing",
    "notify",
)


@dataclass(frozen=True)
class Container:
    users: UsersPort
    catalog: CatalogPort
    dialog: DialogPort
    calc: CalcPort
    analysis: AnalysisPort
    billing: BillingPort
    notify: NotifyPort
    close: Callable[[], Awaitable[None]]


async def _noop_close() -> None:
    return None


def build_container(settings: Settings) -> Container:
    modes = {name: settings.adapter_mode(name) for name in PORT_NAMES}
    real_ports = [name for name, mode in modes.items() if mode == "real"]
    mock_ports = [name for name, mode in modes.items() if mode == "mock"]

    legacy: LegacyClient | None = None
    if real_ports:
        legacy = LegacyClient(
            base_url=settings.legacy_backend_url,
            token=settings.internal_token,
            timeout=settings.http_timeout_sec,
        )

    mocks = build_mock_services() if mock_ports else None

    def pick(name: str, real_factory: Callable[[LegacyClient], Any], mock_attr: str) -> Any:
        if modes[name] == "real":
            assert legacy is not None  # гарантировано ветвлением выше
            return real_factory(legacy)
        assert mocks is not None
        return getattr(mocks, mock_attr)

    container = Container(
        users=pick("users", LegacyUsers, "users"),
        catalog=pick("catalog", LegacyCatalog, "listings"),
        dialog=pick("dialog", LegacyDialog, "dialog"),
        calc=pick("calc", LegacyCalc, "calc"),
        analysis=pick("analysis", LegacyAnalysis, "analysis"),
        billing=pick("billing", LegacyBilling, "billing"),
        notify=pick("notify", LegacyNotify, "notify"),
        close=legacy.aclose if legacy is not None else _noop_close,
    )
    return container
