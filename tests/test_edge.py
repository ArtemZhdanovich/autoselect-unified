"""edge-service: режимы, сертификаты, ACME-челлендж, редирект и прокси."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from edge_service.apps import build_http_app, build_https_app
from edge_service.certs import describe, ensure_selfsigned
from edge_service.config import EdgeConfig, EdgeError
from edge_service.tunnel import (
    CLOUDFLARED_URL_RE,
    TUNNELMOLE_URL_RE,
    CloudflaredTunnel,
    TunnelmoleTunnel,
    build_tunnel,
)


def test_default_mode_is_selfsigned() -> None:
    assert EdgeConfig().tls_mode == "selfsigned"


@pytest.mark.parametrize("bad", ["nginx", ""])
def test_unknown_mode_is_rejected(bad: str) -> None:
    with pytest.raises(EdgeError):
        EdgeConfig(tls_mode=bad).validate()


def test_letsencrypt_requires_domain_and_email() -> None:
    with pytest.raises(EdgeError) as exc:
        EdgeConfig(tls_mode="letsencrypt").validate()
    message = str(exc.value)
    assert "DOMAIN" in message and "ACME_EMAIL" in message
    assert "80" in message  # подсказка про проброс порта


def test_letsencrypt_accepts_complete_config() -> None:
    EdgeConfig(tls_mode="letsencrypt", domain="cars.example", acme_email="me@example.com").validate()


def test_hostnames_cover_domain_and_localhost() -> None:
    config = EdgeConfig(domain="cars.example", extra_hosts=("192.168.1.81",))
    hosts = config.hostnames()
    assert hosts[0] == "cars.example"
    assert "localhost" in hosts and "127.0.0.1" in hosts
    assert "192.168.1.81" in hosts


def test_selfsigned_is_created_and_reused(tmp_path) -> None:
    config = EdgeConfig(certs_dir=tmp_path, extra_hosts=("192.168.1.81",))
    cert_path, key_path = ensure_selfsigned(config)
    assert cert_path.exists() and key_path.exists()

    info = describe(cert_path)
    assert info["self_signed"] is True
    assert info["days_left"] > 300

    fingerprint = cert_path.stat().st_mtime
    again, _ = ensure_selfsigned(config)
    assert again.stat().st_mtime == fingerprint  # не перегенерируем зря


def test_acme_challenge_is_served_from_webroot(tmp_path) -> None:
    config = EdgeConfig(certs_dir=tmp_path, domain="cars.example")
    webroot = tmp_path / "webroot"
    webroot.mkdir(parents=True)
    (webroot / "abc123").write_text("challenge-value", encoding="utf-8")

    response = TestClient(build_http_app(config)).get("/.well-known/acme-challenge/abc123")
    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_acme_missing_challenge_is_404(tmp_path) -> None:
    config = EdgeConfig(certs_dir=tmp_path)
    response = TestClient(build_http_app(config)).get("/.well-known/acme-challenge/none")
    assert response.status_code == 404


def test_http_redirects_everything_else_to_https(tmp_path) -> None:
    config = EdgeConfig(certs_dir=tmp_path, domain="cars.example", https_port=443)
    response = TestClient(build_http_app(config)).get("/app.js?x=1", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "https://cars.example/app.js?x=1"


def test_https_proxy_forwards_path_and_query(tmp_path) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json={"ok": True})

    config = EdgeConfig(certs_dir=tmp_path, upstream="http://upstream.test")
    app = build_https_app(config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.get("/api/listings?limit=2")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "/api/listings" in seen["url"]
    assert "limit=2" in seen["url"]


def test_https_proxy_reports_upstream_failure(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream is down")

    config = EdgeConfig(certs_dir=tmp_path, upstream="http://upstream.test")
    app = build_https_app(config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.get("/api/listings")

    assert response.status_code == 503
    assert "upstream" in response.json()["detail"]


def test_status_reports_certificate(tmp_path) -> None:
    config = EdgeConfig(certs_dir=tmp_path, tls_mode="selfsigned")
    ensure_selfsigned(config)

    with TestClient(build_https_app(config)) as client:
        body = client.get("/status").json()

    assert body["mode"] == "selfsigned"
    assert body["certificate"]["self_signed"] is True


def test_tunnel_url_is_extracted_from_line() -> None:
    line = "2026-10-22T05:00:00Z INF |  https://random-words-1234.trycloudflare.com  |"
    match = CLOUDFLARED_URL_RE.search(line)
    assert match is not None
    assert match.group(0) == "https://random-words-1234.trycloudflare.com"
    assert CLOUDFLARED_URL_RE.search("https://example.com") is None


def test_tunnel_url_ignores_service_endpoints() -> None:
    """В баннере cloudflared есть `api.trycloudflare.com` — его брать нельзя."""
    banner = "INF Requesting new quick Tunnel on trycloudflare.com..."
    assert CLOUDFLARED_URL_RE.search(banner) is None
    assert CLOUDFLARED_URL_RE.search("https://api.trycloudflare.com") is None
    assert CLOUDFLARED_URL_RE.search("https://www.trycloudflare.com") is None


def test_tunnelmole_url_pattern() -> None:
    line = "https://rawa4r-ip-82-209-250-140.tunnelmole.net вџ¶   http://localhost:8080"
    match = TUNNELMOLE_URL_RE.search(line)
    assert match is not None
    assert match.group(0) == "https://rawa4r-ip-82-209-250-140.tunnelmole.net"


def test_cloudflared_binary_is_required(tmp_path) -> None:
    config = EdgeConfig(tls_mode="tunnel", cloudflared_bin=str(tmp_path / "missing-binary"))
    with pytest.raises(EdgeError) as exc:
        CloudflaredTunnel(config).argv()
    assert "cloudflared" in str(exc.value)


def test_tunnelmole_binary_is_required(tmp_path) -> None:
    config = EdgeConfig(tls_mode="tunnel", tunnelmole_bin=str(tmp_path / "missing-npx"))
    with pytest.raises(EdgeError) as exc:
        TunnelmoleTunnel(config).argv()
    assert "npx" in str(exc.value)


def test_tunnel_provider_is_selected_by_env_field() -> None:
    config = EdgeConfig(tls_mode="tunnel", tunnel_provider="tunnelmole")
    assert isinstance(build_tunnel(config), TunnelmoleTunnel)
    assert isinstance(build_tunnel(EdgeConfig(tls_mode="tunnel")), CloudflaredTunnel)


def test_unknown_tunnel_provider_is_rejected() -> None:
    with pytest.raises(EdgeError):
        EdgeConfig(tls_mode="tunnel", tunnel_provider="ngrok").validate()
