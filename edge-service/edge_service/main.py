"""Оркестратор edge-service: выбрать режим, подготовить сертификат, поднять порты."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

import uvicorn

from edge_service.apps import build_http_app, build_https_app
from edge_service.certs import (
    domain_resolves_here,
    ensure_selfsigned,
    issue_letsencrypt,
    renew_letsencrypt,
)
from edge_service.config import EdgeConfig, EdgeError
from edge_service.tunnel import build_tunnel

logger = logging.getLogger("edge")


async def _wait_started(server: uvicorn.Server, label: str, timeout: float = 20.0) -> None:
    """Дождаться, пока uvicorn реально займёт порт, и внятно упасть, если не смог."""
    for _ in range(int(timeout * 10)):
        if server.started:
            return
        if getattr(server, "should_exit", False):
            raise EdgeError(
                f"{label}: не удалось занять порт. Занят другим процессом или нет прав."
            )
        await asyncio.sleep(0.1)
    raise EdgeError(f"{label}: сервер не поднялся за {timeout:.0f} с")


def _prepare_certificates(config: EdgeConfig) -> tuple:
    if config.tls_mode == "letsencrypt":
        ok, info = domain_resolves_here(config.domain)
        logger.info("DNS %s: %s", config.domain, info)
        return issue_letsencrypt(config)
    return ensure_selfsigned(config)


async def _renew_forever(config: EdgeConfig) -> None:
    """Раз в 12 часов пробуем продлить сертификат Let's Encrypt."""
    while True:
        await asyncio.sleep(12 * 3600)
        try:
            changed = await asyncio.to_thread(renew_letsencrypt, config)
            if changed:
                logger.warning(
                    "сертификат обновлён; uvicorn читает файл только на старте — "
                    "перезапустите edge-service (docker restart / make up-edge)"
                )
        except Exception as exc:  # noqa: BLE001 — фоновое продление не должно ронять сервис
            logger.warning("продление не удалось: %s", exc)


async def run_tunnel(config: EdgeConfig) -> None:
    """Публичный HTTPS без домена: quick tunnel Cloudflare."""
    logger.info("режим tunnel (%s): → %s", config.tunnel_provider, config.upstream)
    tunnel = build_tunnel(config)
    url = await tunnel.start()

    config.runtime_dir.mkdir(parents=True, exist_ok=True)
    config.public_url_file.write_text(url + "\n", encoding="utf-8")

    print("")
    print(f"[edge] ПУБЛИЧНЫЙ HTTPS: {url}")
    print(f"[edge] в бота: MINIAPP_URL={url}")
    print("")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await tunnel.stop()


async def run_tls(config: EdgeConfig) -> None:
    http_app = build_http_app(config)
    http_server = uvicorn.Server(
        uvicorn.Config(http_app, host=config.bind, port=config.http_port, log_level=config.log_level)
    )
    http_task = asyncio.create_task(http_server.serve(), name="edge-http")
    await _wait_started(http_server, f"HTTP :{config.http_port}")
    logger.info("HTTP :%s слушает (ACME + редирект)", config.http_port)

    try:
        cert_path, key_path = await asyncio.to_thread(_prepare_certificates, config)
    except EdgeError:
        # Гасим уже поднятый :80 без трейсбека — ошибка уже сформулирована словами.
        http_server.should_exit = True
        with contextlib.suppress(Exception):
            await asyncio.wait_for(http_task, timeout=10)
        raise
    logger.info("%s сертификат: %s", config.tls_mode, cert_path)

    https_app = build_https_app(config)
    https_server = uvicorn.Server(
        uvicorn.Config(
            https_app,
            host=config.bind,
            port=config.https_port,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            log_level=config.log_level,
        )
    )
    renewer = asyncio.create_task(_renew_forever(config)) if config.tls_mode == "letsencrypt" else None
    try:
        await asyncio.gather(http_task, https_server.serve())
    finally:
        if renewer is not None:
            renewer.cancel()
        http_server.should_exit = True


async def run(config: EdgeConfig) -> None:
    if config.tls_mode == "tunnel":
        await run_tunnel(config)
    else:
        await run_tls(config)


def main() -> None:
    config = EdgeConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    try:
        asyncio.run(run(config))
    except EdgeError as exc:
        print(f"[edge] ОШИБКА: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
