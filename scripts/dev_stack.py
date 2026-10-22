"""Поднять backend-service + miniapp-service одним процессом (для разработки).

Зачем: два `uvicorn` руками — это два окна, два лога и забытый процесс.
Здесь оба сервера живут в одном asyncio-цикле и падают вместе.

    python scripts/dev_stack.py            # backend :8010, miniapp :8080

Mini App откроется на http://127.0.0.1:8080 — она же проксирует `/api/*` в backend.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bootstrap import prepare_path  # noqa: E402

prepare_path()

import uvicorn  # noqa: E402


async def serve(host: str, backend_port: int, miniapp_port: int) -> None:
    os.environ.setdefault("SERVICE", "backend")
    os.environ.setdefault("MODE", "mock")
    os.environ.setdefault("BACKEND_URL", f"http://{host}:{backend_port}")

    backend = uvicorn.Server(
        uvicorn.Config(
            "backend_service.main:app",
            host=host,
            port=backend_port,
            log_level=os.getenv("LOG_LEVEL", "warning").lower(),
        )
    )
    miniapp = uvicorn.Server(
        uvicorn.Config(
            "miniapp_service.main:app",
            host=host,
            port=miniapp_port,
            log_level=os.getenv("LOG_LEVEL", "warning").lower(),
        )
    )
    print(f"backend  → http://{host}:{backend_port}/health")
    print(f"miniapp  → http://{host}:{miniapp_port}/")
    await asyncio.gather(backend.serve(), miniapp.serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="backend + miniapp в одном процессе")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8010)
    parser.add_argument("--miniapp-port", type=int, default=8080)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.host, args.backend_port, args.miniapp_port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
