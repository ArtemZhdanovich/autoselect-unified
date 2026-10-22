"""Запуск backend-service: `python scripts/run_backend.py --port 8000`.

Эквивалент `make up-backend`: SERVICE=backend, MODE из окружения (по умолчанию mock).
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
    parser = argparse.ArgumentParser(description="backend-service (FastAPI)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info").lower())
    args = parser.parse_args()

    os.environ.setdefault("SERVICE", "backend")
    os.environ.setdefault("MODE", "mock")

    uvicorn.run(
        "backend_service.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    sys.exit(main())
