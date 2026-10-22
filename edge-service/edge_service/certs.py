"""Сертификаты: самоподписанный, Let's Encrypt (HTTP-01 через certbot), инспекция.

Let's Encrypt не «просто работает»: нужен домен, указывающий на этот хост, и
доступный из интернета порт 80. Если условия не выполнены, сервис не делает вид,
что выпустил сертификат, а говорит, чего не хватает.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import shutil
import socket
import subprocess
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from edge_service.config import EdgeConfig, EdgeError

SELF_SIGNED_DAYS = 365


def _write_private_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _split_hosts(hosts: list[str]) -> tuple[list[str], list[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    dns: list[str] = []
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for host in hosts:
        try:
            ips.append(ipaddress.ip_address(host))
        except ValueError:
            dns.append(host)
    return dns, ips


def ensure_selfsigned(config: EdgeConfig) -> tuple[Path, Path]:
    """Создать (или переиспользовать) самоподписанный сертификат для локального TLS."""
    cert_path, key_path = config.selfsigned_paths
    if cert_path.exists() and key_path.exists() and not is_expired(cert_path):
        return cert_path, key_path

    hosts = config.hostnames()
    dns_names, ip_names = _split_hosts(hosts)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])])
    now = dt.datetime.now(dt.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=SELF_SIGNED_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    )
    alt: list[x509.GeneralName] = [x509.DNSName(name) for name in dns_names]
    alt.extend(x509.IPAddress(ip) for ip in ip_names)
    builder = builder.add_extension(x509.SubjectAlternativeName(alt), critical=False)

    certificate = builder.sign(key, hashes.SHA256())
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    _write_private_key(key_path, key)
    return cert_path, key_path


def is_expired(cert_path: Path) -> bool:
    try:
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except Exception:  # битый файл — считаем, что сертификата нет
        return True
    return certificate.not_valid_after_utc <= dt.datetime.now(dt.timezone.utc)


def describe(cert_path: Path) -> dict:
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "not_after": certificate.not_valid_after_utc.isoformat(),
        "days_left": (certificate.not_valid_after_utc - dt.datetime.now(dt.timezone.utc)).days,
        "self_signed": certificate.subject == certificate.issuer,
    }


# ----------------------------------------------------------------- Let's Encrypt


def _certbot(config: EdgeConfig) -> str:
    binary = shutil.which(config.certbot_bin)
    if binary:
        return binary
    candidate = Path(config.certbot_bin)
    if candidate.exists():
        return str(candidate)
    raise EdgeError(
        "certbot не найден. Варианты: `apt install certbot` на хосте, "
        "образ `certbot/certbot` рядом, либо `pip install certbot` для локального запуска. "
        "Либо переключитесь на TLS_MODE=tunnel — он даёт HTTPS без домена."
    )


def _certbot_dirs(config: EdgeConfig) -> list[str]:
    return [
        "--config-dir",
        str(config.le_root),
        "--work-dir",
        str(config.certs_dir / "work"),
        "--logs-dir",
        str(config.certs_dir / "logs"),
    ]


def domain_resolves_here(domain: str) -> tuple[bool, str]:
    """Проверка, что домен вообще указывает на этот хост (A-запись)."""
    try:
        resolved = socket.gethostbyname(domain)
    except OSError as exc:
        return False, f"DNS не разрешается: {exc}"
    try:
        local = socket.gethostbyname(socket.gethostname())
    except OSError:
        local = ""
    if local and resolved == local:
        return True, resolved
    return True, f"{domain} → {resolved} (локальный адрес: {local or 'неизвестен'})"


def issue_letsencrypt(config: EdgeConfig) -> tuple[Path, Path]:
    """Выпустить сертификат по HTTP-01. Порт 80 должен уже отдавать challenge."""
    cert_path, key_path = config.le_cert_paths()
    if cert_path.exists() and key_path.exists() and not is_expired(cert_path):
        return cert_path, key_path

    config.acme_webroot.mkdir(parents=True, exist_ok=True)
    binary = _certbot(config)
    command = [
        binary,
        "certonly",
        "--webroot",
        "--webroot-path",
        str(config.acme_webroot),
        "--domain",
        config.domain,
        "--email",
        config.acme_email,
        "--agree-tos",
        "--non-interactive",
        "--keep-until-expiring",
        *_certbot_dirs(config),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-600:]
        raise EdgeError(
            "certbot не смог выпустить сертификат. Частые причины: домен не указывает на "
            "этот хост, порт 80 закрыт извне, лимит Let's Encrypt.\n" + tail
        )
    if not cert_path.exists():
        raise EdgeError(f"certbot завершился без ошибки, но файла {cert_path} нет")
    return cert_path, key_path


def renew_letsencrypt(config: EdgeConfig) -> bool:
    """Продлить сертификат. True — файл сертификата изменился (нужен рестарт)."""
    cert_path, _ = config.le_cert_paths()
    before = cert_path.stat().st_mtime if cert_path.exists() else 0
    binary = _certbot(config)
    subprocess.run(
        [binary, "renew", "--quiet", *_certbot_dirs(config)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    after = cert_path.stat().st_mtime if cert_path.exists() else 0
    return after != before
