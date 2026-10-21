"""
Los logos (`tvg-logo`) vienen de listas M3U que pueden ser ajenas y se
descargan solos al pintar el catálogo: no pueden servir para pedir URLs
internas (loopback, metadatos de nube) ni seguir redirecciones hacia ellas.
"""
import ipaddress

import pytest

from core import net_safety
from core.http_limits import UnsafeRedirect
from ui import widgets


class _Response:
    def __init__(self, status_code=200, body=b"", location=None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}
        self._body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        yield self._body

    def close(self):
        pass


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    def _resolve(host):
        try:
            return [ipaddress.ip_address(host)]
        except ValueError:
            return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr(net_safety, "_resolve", _resolve)


def test_logo_from_a_public_host_is_downloaded(monkeypatch):
    monkeypatch.setattr(
        "core.http_limits.requests.get", lambda url, **kwargs: _Response(body=b"PNGDATA")
    )

    assert widgets._download_logo_bytes("https://cdn.example/logo.png") == b"PNGDATA"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080/accion",
    "http://169.254.169.254/latest/meta-data",
    "file:///C:/Windows/win.ini",
])
def test_logo_from_an_internal_destination_is_never_requested(monkeypatch, url):
    def _boom(*args, **kwargs):
        raise AssertionError("no debía hacerse ninguna petición")

    monkeypatch.setattr("core.http_limits.requests.get", _boom)

    with pytest.raises(UnsafeRedirect):
        widgets._download_logo_bytes(url)


def test_logo_redirect_to_an_internal_destination_is_refused(monkeypatch):
    pedidas = []

    def _get(url, **kwargs):
        pedidas.append(url)
        return _Response(302, location="http://127.0.0.1:9000/interno")

    monkeypatch.setattr("core.http_limits.requests.get", _get)

    with pytest.raises(UnsafeRedirect):
        widgets._download_logo_bytes("https://cdn.example/logo.png")

    assert pedidas == ["https://cdn.example/logo.png"]


def test_logo_download_uses_short_timeouts_a_total_deadline_and_few_redirects(monkeypatch):
    captured = {}

    def _get(url, **kwargs):
        captured.update(kwargs)
        return _Response(body=b"PNGDATA")

    monkeypatch.setattr("core.http_limits.requests.get", _get)

    widgets._download_logo_bytes("https://cdn.example/logo.png")

    connect, read = captured["timeout"]
    assert connect <= 4 and read <= 8
    assert widgets.LOGO_DEADLINE_SECONDS <= 30


def test_logo_download_gives_up_after_three_redirects(monkeypatch):
    pedidas = []

    def _get(url, **kwargs):
        pedidas.append(url)
        return _Response(302, location="https://cdn.example/otra")

    monkeypatch.setattr("core.http_limits.requests.get", _get)

    with pytest.raises(UnsafeRedirect):
        widgets._download_logo_bytes("https://cdn.example/logo.png")

    assert len(pedidas) == 4
