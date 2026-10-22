"""Запуск miniapp-service: `python scripts/run_miniapp.py --port 8080`.

Сервис раздаёт статику Mini App и проксирует `/api/*` в `BACKEND_URL`
(по умолчанию `http://localhost:8000`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Изолированный Python не кладёт папку скрипта в sys.path — делаем это сами.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bootstrap import prepare_path  # noqa: E402

prepare_path()

import uvicorn  # noqa: E402  (после prepare_path — иначе пакет не найдётся)


def main() -> None:
    parser = argparse.ArgumentParser(description="miniapp-service (статика + прокси)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info").lower())
    args = parser.parse_args()

    uvicorn.run(
        "miniapp_service.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
