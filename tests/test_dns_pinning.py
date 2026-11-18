"""DNS rebinding: la validación del destino y la conexión usan la MISMA resolución.

Antes, `validate_url` resolvía el nombre, lo aceptaba, y luego `requests`
volvía a resolverlo: un DNS hostil podía contestar primero una IP pública y
después 127.0.0.1. Aquí un servidor real escucha en loopback y `getaddrinfo`
simula ese DNS; nada sale a internet.
"""
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from core import http_limits, net_safety

PUBLIC_IP = "93.184.216.34"


class _Server:
    def __init__(self):
        self.hits = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits.append(self.headers.get("Host"))
                body = b"secreto-local"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(autouse=True)
def _no_env_proxies(monkeypatch):
    """Estos tests conectan en directo: un proxy del entorno los desviaría."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setenv("NO_PROXY", "*")


@pytest.fixture
def server():
    srv = _Server()
    yield srv
    srv.close()


def _rebinding_dns(monkeypatch):
    """Primera resolución de `rebind.test`: pública. Las siguientes: loopback.
    Se simula en `net_safety._resolve` (lo que usa la validación; conftest ya lo
    sustituye) y en `socket.getaddrinfo` (lo que usaría `requests`), con un
    contador común: da igual quién resuelva, el DNS hostil cambia de respuesta."""
    import ipaddress

    real = socket.getaddrinfo
    calls = []

    def answer():
        calls.append("rebind.test")
        return PUBLIC_IP if len(calls) == 1 else "127.0.0.1"

    def fake_getaddrinfo(host, port=None, *args, **kwargs):
        if host != "rebind.test":
            return real(host, port, *args, **kwargs)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (answer(), int(port or 0)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        net_safety, "_resolve", lambda host: [ipaddress.ip_address(answer())]
    )
    return calls


def test_a_host_that_rebinds_to_loopback_after_validation_is_not_contacted(monkeypatch, server):
    calls = _rebinding_dns(monkeypatch)
    url = f"http://rebind.test:{server.port}/"

    with pytest.raises(requests.RequestException):
        http_limits.get_following_safe_redirects(
            url, validate_url=net_safety.is_safe_download_url, timeout=3, stream=True
        )

    assert server.hits == []
    assert len(calls) >= 2  # validó con una IP pública y la conexión se encontró otra


def test_the_connection_goes_to_the_validated_address_without_resolving_again(monkeypatch, server):
    """Con un resolutor propio la conexión usa SU dirección y nunca el DNS."""
    real = socket.getaddrinfo

    def only_numeric(host, *args, **kwargs):
        if host != "127.0.0.1":  # una IP literal no es una consulta DNS
            raise AssertionError(f"la conexión no debe resolver el nombre {host!r}")
        return real(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", only_numeric)

    def validate(url):
        return True

    validate.resolve = lambda host: ["127.0.0.1"]
    response = http_limits.get_following_safe_redirects(
        f"http://pinned.test:{server.port}/", validate_url=validate, timeout=3
    )

    assert response.content == b"secreto-local"
    assert server.hits == [f"pinned.test:{server.port}"]  # el Host sigue siendo el nombre


def test_a_resolver_that_refuses_the_host_blocks_the_connection(monkeypatch, server):
    def validate(url):
        return True

    validate.resolve = lambda host: []
    with pytest.raises(requests.RequestException):
        http_limits.get_following_safe_redirects(
            f"http://127.0.0.1:{server.port}/", validate_url=validate, timeout=3
        )
    assert server.hits == []


def test_the_download_validators_expose_a_resolver_with_their_own_policy(monkeypatch):
    monkeypatch.undo()  # conftest fija todo host a una IP pública: aquí hace falta la real
    assert net_safety.is_safe_download_url.resolve("127.0.0.1") == []
    assert net_safety.is_safe_https_url.resolve("127.0.0.1") == []


def test_the_user_url_host_may_resolve_to_loopback_but_a_redirect_target_may_not(monkeypatch):
    monkeypatch.undo()
    validator = net_safety.redirect_validator_for("http://127.0.0.1:8080/lista.m3u")
    assert validator.resolve("127.0.0.1") == ["127.0.0.1"]
    assert validator.resolve("localhost") == []


def test_a_redirect_to_the_user_url_host_loses_the_loopback_exemption(monkeypatch):
    monkeypatch.undo()
    user_url = "http://127.0.0.1:8080/lista.m3u"
    validator = net_safety.redirect_validator_for(user_url)
    assert validator(user_url)
    assert validator.resolve("127.0.0.1") == ["127.0.0.1"]
    # Redirección al mismo nombre en otro puerto: ya no es la URL del usuario.
    assert not validator("http://127.0.0.1:9090/admin")
    assert validator.resolve("127.0.0.1") == []


def test_a_redirect_back_to_the_user_url_does_not_regain_the_loopback_exemption(monkeypatch):
    monkeypatch.undo()
    user_url = "http://127.0.0.1:8080/lista.m3u"
    validator = net_safety.redirect_validator_for(user_url)
    assert validator(user_url)
    assert validator.resolve("127.0.0.1") == ["127.0.0.1"]
    # Un Location idéntico a la URL del usuario, o una cadena que vuelve a ella.
    assert validator(user_url)
    assert validator.resolve("127.0.0.1") == []
    assert not validator("http://127.0.0.1:9090/otra")
    assert validator(user_url)
    assert validator.resolve("127.0.0.1") == []


@pytest.mark.parametrize("configured, seen_by_transport", [
    ("http://127.0.0.1.:8080/lista.m3u", "127.0.0.1"),
    ("http://localhost.:8080/lista.m3u", "localhost"),
    ("http://LOCALHOST:8080/lista.m3u", "localhost"),
    ("http://bücher.test:8080/lista.m3u", "xn--bcher-kva.test"),
])
def test_the_exemption_survives_the_hostname_normalisation_of_the_transport(
    monkeypatch, configured, seen_by_transport
):
    monkeypatch.undo()
    monkeypatch.setattr(net_safety, "_resolve", lambda host: [__import__("ipaddress").ip_address("127.0.0.1")])
    validator = net_safety.redirect_validator_for(configured)
    assert validator(configured)
    assert validator.resolve(seen_by_transport) == ["127.0.0.1"]
