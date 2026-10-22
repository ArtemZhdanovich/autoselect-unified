"""Границы слоёв: UI не лезет в БД, контракты не тянут фреймворки.

Это тест архитектуры, а не поведения: он первым поймает «по-быстрому дернул
sqlalchemy из хендлера» — то, что запрещено ТЗ.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)", re.MULTILINE)


def imports_of(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.split(".")[0] for match in _IMPORT_RE.findall(text)}


def modules(*parts: str):
    return list((ROOT.joinpath(*parts)).rglob("*.py"))


def test_bot_service_has_no_domain_or_db_imports() -> None:
    forbidden = {"sqlalchemy", "asyncpg", "aio_pika", "boto3", "psycopg", "psycopg2"}
    violations = {
        str(path.relative_to(ROOT)): sorted(imports_of(path) & forbidden)
        for path in modules("bot-service", "bot_service")
        if imports_of(path) & forbidden
    }
    assert violations == {}


def test_shared_contracts_have_no_framework_imports() -> None:
    forbidden = {"aiogram", "fastapi", "sqlalchemy", "httpx", "uvicorn"}
    violations = {
        str(path.relative_to(ROOT)): sorted(imports_of(path) & forbidden)
        for path in modules("shared")
        if imports_of(path) & forbidden
    }
    assert violations == {}


def test_backend_api_has_no_direct_infrastructure() -> None:
    """Роутеры работают только через порты — не через httpx/SQL/aiogram."""
    forbidden = {"httpx", "sqlalchemy", "asyncpg", "aio_pika", "aiogram"}
    violations = {
        str(path.relative_to(ROOT)): sorted(imports_of(path) & forbidden)
        for path in modules("backend-service", "backend_service", "api")
        if imports_of(path) & forbidden
    }
    assert violations == {}


def test_bot_handlers_use_only_contract_ports() -> None:
    """Хендлеры не должны знать про httpx: единственный канал — `BackendPort`."""
    violations = {}
    for path in modules("bot-service", "bot_service", "handlers"):
        found = imports_of(path) & {"httpx", "sqlalchemy", "aio_pika"}
        if found:
            violations[str(path.relative_to(ROOT))] = sorted(found)
    assert violations == {}
