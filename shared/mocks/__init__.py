"""Моки платформы: фикстуры каталога, адаптеры домена и `MockBackend` для бота."""

from shared.mocks.adapters import (
    MemoryState,
    MockAnalysis,
    MockBilling,
    MockCalc,
    MockDialog,
    MockListings,
    MockNotify,
    MockServices,
    MockUsers,
    build_mock_services,
)
from shared.mocks.backend import MockBackend

__all__ = [
    "MemoryState",
    "MockAnalysis",
    "MockBackend",
    "MockBilling",
    "MockCalc",
    "MockDialog",
    "MockListings",
    "MockNotify",
    "MockServices",
    "MockUsers",
    "build_mock_services",
]
