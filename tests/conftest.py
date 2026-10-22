"""Общая настройка тестов: пути пакетов.

Пакеты лежат в `shared/`, `bot-service/` и `backend-service/`, поэтому корни
добавляются в `sys.path` — так же, как `PYTHONPATH` в Makefile/Dockerfile.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "bot-service", ROOT / "backend-service"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
