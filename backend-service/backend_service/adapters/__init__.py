"""Адаптеры: `real` (legacy auto_bot / инфраструктура) и `mock` (фикстуры)."""

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

__all__ = [
    "LegacyAnalysis",
    "LegacyBilling",
    "LegacyCalc",
    "LegacyCatalog",
    "LegacyClient",
    "LegacyDialog",
    "LegacyNotify",
    "LegacyUsers",
]
