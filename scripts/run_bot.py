"""Запуск bot-service: `python scripts/run_bot.py`.

Эквивалент `make up-bot`: SERVICE=bot, MODE из окружения (по умолчанию mock).
При MODE=mock бот полностью работает без бэкенда и без инфраструктуры.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Изолированный Python не кладёт папку скрипта в sys.path — делаем это сами.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bootstrap import prepare_path  # noqa: E402

prepare_path()

from bot_service.main import main  # noqa: E402  (после prepare_path)


if __name__ == "__main__":
    os.environ.setdefault("SERVICE", "bot")
    os.environ.setdefault("MODE", "mock")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # Ctrl+C — штатная остановка
        sys.exit(0)
