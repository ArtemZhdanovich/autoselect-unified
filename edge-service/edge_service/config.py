"""Конфигурация edge-service: режим TLS, домен, порты, адреса.

Всё — из окружения. Сервис умеет три режима:

* `selfsigned`  — локальный TLS своим сертификатом (браузер ругнётся, Telegram не примет);
* `letsencrypt` — настоящий сертификат Let's Encrypt по HTTP-01, нужен домен и порт 80;
* `tunnel`      — публичный HTTPS через туннель, когда домена и внешнего IP нет.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TLS_MODES: tuple[str, ...] = ("selfsigned", "letsencrypt", "tunnel")

#: Провайдеры публичного туннеля (используются при `TLS_MODE=tunnel`).
TUNNEL_PROVIDERS: tuple[str, ...] = ("cloudflared", "tunnelmole")


class EdgeError(RuntimeError):
    """Ошибка запуска с человеческим объяснением, что именно не так."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True, slots=True)
class EdgeConfig:
    tls_mode: str = "selfsigned"
    domain: str = ""
    acme_email: str = ""

    upstream: str = "http://127.0.0.1:8080"
    bind: str = "0.0.0.0"
    http_port: int = 80
    https_port: int = 443

    certs_dir: Path = field(default_factory=lambda: Path("./.certs"))
    runtime_dir: Path = field(default_factory=lambda: Path("./runtime"))

    #: Имена, которые попадут в SAN самоподписанного сертификата.
    extra_hosts: tuple[str, ...] = ()

    certbot_bin: str = "certbot"
    cloudflared_bin: str = "cloudflared"
    tunnel_provider: str = "cloudflared"
    tunnelmole_bin: str = "npx"

    log_level: str = "info"

    @classmethod
    def from_env(cls) -> EdgeConfig:
        hosts = tuple(
            part.strip()
            for part in _env("EDGE_EXTRA_HOSTS").split(",")
            if part.strip()
        )
        config = cls(
            tls_mode=_env("TLS_MODE", "selfsigned").lower(),
            domain=_env("DOMAIN").lower().rstrip("."),
            acme_email=_env("ACME_EMAIL"),
            upstream=_env("UPSTREAM", "http://127.0.0.1:8080").rstrip("/"),
            bind=_env("EDGE_BIND", "0.0.0.0"),
            http_port=int(_env("EDGE_HTTP_PORT", "80") or 80),
            https_port=int(_env("EDGE_HTTPS_PORT", "443") or 443),
            certs_dir=Path(_env("CERTS_DIR", "./.certs")),
            runtime_dir=Path(_env("RUNTIME_DIR", "./runtime")),
            extra_hosts=hosts,
            certbot_bin=_env("CERTBOT_BIN", "certbot"),
            cloudflared_bin=_env("CLOUDFLARED_BIN", "cloudflared"),
            tunnel_provider=_env("TUNNEL_PROVIDER", "cloudflared").lower(),
            tunnelmole_bin=_env("TUNNELMOLE_BIN", "npx"),
            log_level=_env("LOG_LEVEL", "info").lower(),
        )
        return config.validate()

    def validate(self) -> EdgeConfig:
        if self.tls_mode not in TLS_MODES:
            raise EdgeError(
                f"TLS_MODE={self.tls_mode!r} не поддерживается; допустимо: {', '.join(TLS_MODES)}"
            )
        if self.tls_mode == "tunnel" and self.tunnel_provider not in TUNNEL_PROVIDERS:
            raise EdgeError(
                f"TUNNEL_PROVIDER={self.tunnel_provider!r} не поддерживается; "
                f"допустимо: {', '.join(TUNNEL_PROVIDERS)}"
            )
        if self.tls_mode == "letsencrypt":
            missing = [
                name
                for name, value in (("DOMAIN", self.domain), ("ACME_EMAIL", self.acme_email))
                if not value
            ]
            if missing:
                raise EdgeError(
                    "TLS_MODE=letsencrypt требует "
                    + " и ".join(missing)
                    + ". Домен должен указывать A-записью на этот хост, а порт 80 — "
                    "быть доступен из интернета (проброс на роутере)."
                )
        return self

    # ------------------------------------------------------------------ пути

    @property
    def acme_webroot(self) -> Path:
        """Каталог, который читает ACME-валидатор (`/.well-known/acme-challenge`)."""
        return self.certs_dir / "webroot"

    @property
    def le_root(self) -> Path:
        return self.certs_dir / "letsencrypt"

    def le_cert_paths(self) -> tuple[Path, Path]:
        base = self.le_root / "live" / self.domain
        return base / "fullchain.pem", base / "privkey.pem"

    @property
    def selfsigned_paths(self) -> tuple[Path, Path]:
        return self.certs_dir / "selfsigned.crt", self.certs_dir / "selfsigned.key"

    @property
    def public_url_file(self) -> Path:
        return self.runtime_dir / "public_url.txt"

    def hostnames(self) -> list[str]:
        """Что положить в SAN: домен (если есть), localhost и локальные адреса."""
        hosts = ["localhost", "127.0.0.1"]
        if self.domain:
            hosts.insert(0, self.domain)
        hosts.extend(self.extra_hosts)
        # уникализируем, сохраняя порядок
        return list(dict.fromkeys(hosts))
