"""Запуск edge-service: `python scripts/run_edge.py`.

Режим задаётся окружением (`TLS_MODE`), порты можно переопределить флагами —
это нужно для локальной проверки, где 80/443 занят или недоступен.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bootstrap import prepare_path  # noqa: E402

prepare_path()

from edge_service.config import EdgeConfig, EdgeError  # noqa: E402
from edge_service.main import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="edge-service: TLS / ACME / туннель")
    parser.add_argument("--http-port", type=int, help="переопределить EDGE_HTTP_PORT")
    parser.add_argument("--https-port", type=int, help="переопределить EDGE_HTTPS_PORT")
    parser.add_argument("--mode", choices=["selfsigned", "letsencrypt", "tunnel"])
    args = parser.parse_args()

    if args.http_port:
        os.environ["EDGE_HTTP_PORT"] = str(args.http_port)
    if args.https_port:
        os.environ["EDGE_HTTPS_PORT"] = str(args.https_port)
    if args.mode:
        os.environ["TLS_MODE"] = args.mode

    try:
        config = EdgeConfig.from_env()
    except EdgeError as exc:
        print(f"[edge] ОШИБКА: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    import asyncio

    try:
        asyncio.run(run(config))
    except EdgeError as exc:
        print(f"[edge] ОШИБКА: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
