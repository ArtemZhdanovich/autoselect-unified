"""Общая подготовка путей для launcher-скриптов.

Python в этом окружении стартует изолированно и может игнорировать `PYTHONPATH`,
поэтому сервисные скрипты добавляют корни пакетов в `sys.path` сами.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare_path() -> Path:
    """Корень репозитория + все сервисы — как `PYTHONPATH` в Dockerfile."""
    for path in (ROOT, ROOT / "bot-service", ROOT / "backend-service", ROOT / "miniapp-service", ROOT / "edge-service"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    # cwd — корень проекта: относительные данные (.env, фикстуры) ищутся от него.
    return ROOT
