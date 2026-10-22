"""Публичный HTTPS без домена: провайдеры туннелей.

Зачем: Let's Encrypt требует домен и внешний порт 80. Когда их нет, а прототип в
Telegram нужен сейчас, туннель даёт настоящий HTTPS с валидным сертификатом.

Поддерживаются два провайдера (`TUNNEL_PROVIDER`):

* `cloudflared` — quick tunnel Cloudflare (`*.trycloudflare.com`);
* `tunnelmole`  — `npx tunnelmole` (`*.tunnelmole.net`), удобно там, где сеть
  режет Cloudflare.

Оба запускаются как дочерние процессы; адрес вытаскивается из их вывода.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from edge_service.config import TUNNEL_PROVIDERS, EdgeConfig, EdgeError

#: Адрес quick tunnel'а: поддомен из случайных слов. Служебные `api.`/`www.`
#: (они мелькают в баннере cloudflared) отсекаем — иначе поймаем не тот URL.
CLOUDFLARED_URL_RE = re.compile(
    r"https://(?!api\.|www\.)[a-z0-9][a-z0-9-]{4,}\.trycloudflare\.com"
)
#: Tunnelmole печатает вид `https://random-name.tunnelmole.net`.
TUNNELMOLE_URL_RE = re.compile(r"https://[a-z0-9][a-z0-9-]{2,}\.tunnelmole\.net")


def _resolve_binary(name_or_path: str) -> str:
    candidate = Path(name_or_path)
    if candidate.exists():
        return str(candidate)
    found = shutil.which(name_or_path)
    if found:
        return found
    return ""


class BaseTunnel:
    """Общая механика: запустить процесс, вычитать адрес, аккуратно погасить."""

    provider = "base"
    url_pattern = re.compile(r"https://[a-z0-9.-]+")

    def __init__(self, config: EdgeConfig) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._tail: list[str] = []

    def argv(self) -> list[str]:  # pragma: no cover - переопределяется
        raise NotImplementedError

    async def start(self, timeout: float = 90.0) -> str:
        argv = self.argv()
        self._process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert self._process.stdout is not None

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(self._process.stdout.readline(), timeout=2.0)
            except asyncio.TimeoutError:
                if self._process.returncode is not None:
                    break
                continue
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self._tail.append(line)
                del self._tail[:-20]
            match = self.url_pattern.search(line)
            if match:
                return match.group(0)

        await self.stop()
        tail = "\n".join(self._tail[-8:])
        raise EdgeError(
            f"{self.provider} не выдал публичный адрес за {timeout:.0f} с. "
            "Частые причины: провайдер недоступен из этой сети, закончился лимит.\n" + tail
        )

    async def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.returncode is not None:
            return
        if os.name == "nt":
            # npx порождает дочерний node: убиваем дерево, иначе туннель живёт.
            await asyncio.to_thread(
                subprocess.run,
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
            )
        else:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()


class CloudflaredTunnel(BaseTunnel):
    provider = "cloudflared"
    url_pattern = CLOUDFLARED_URL_RE

    def argv(self) -> list[str]:
        binary = _resolve_binary(self.config.cloudflared_bin)
        if not binary:
            raise EdgeError(
                "cloudflared не найден. Установите: `winget install Cloudflare.cloudflared`, "
                "`brew install cloudflared`, либо укажите путь в CLOUDFLARED_BIN. "
                "Альтернатива без установки — TUNNEL_PROVIDER=tunnelmole."
            )
        return [binary, "tunnel", "--url", self.config.upstream, "--no-autoupdate", "--loglevel", "info"]


class TunnelmoleTunnel(BaseTunnel):
    provider = "tunnelmole"
    url_pattern = TUNNELMOLE_URL_RE

    def argv(self) -> list[str]:
        binary = _resolve_binary(self.config.tunnelmole_bin)
        if not binary:
            raise EdgeError(
                "npx не найден: tunnelmole запускается через `npx -y tunnelmole <port>`. "
                "Поставьте Node.js или переключитесь на TUNNEL_PROVIDER=cloudflared."
            )
        parsed = urlparse(self.config.upstream)
        port = parsed.port or 80
        return [binary, "-y", "tunnelmole", str(port)]


_TUNNELS = {"cloudflared": CloudflaredTunnel, "tunnelmole": TunnelmoleTunnel}


def build_tunnel(config: EdgeConfig) -> BaseTunnel:
    """Выбрать провайдера по `TUNNEL_PROVIDER`."""
    try:
        factory = _TUNNELS[config.tunnel_provider]
    except KeyError as exc:
        raise EdgeError(
            f"TUNNEL_PROVIDER={config.tunnel_provider!r} не поддерживается; "
            f"допустимо: {', '.join(TUNNEL_PROVIDERS)}"
        ) from exc
    return factory(config)
