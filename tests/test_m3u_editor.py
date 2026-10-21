import ipaddress

import pytest

from core import net_safety
from core.channels import parse_m3u


_DUPLICATED_PLAYLIST = """#EXTM3U
#EXTINF:-1 group-title="Noticias",Canal Uno
https://example.test/uno
#EXTINF:-1 group-title="Noticias",Canal Uno
https://example.test/uno-alternativo
"""


def test_editor_can_keep_duplicates_for_review():
    channels = parse_m3u(_DUPLICATED_PLAYLIST, deduplicate=False)

    assert [channel.name for channel in channels] == ["Canal Uno", "Canal Uno"]


def test_regular_import_keeps_its_existing_deduplication():
    channels = parse_m3u(_DUPLICATED_PLAYLIST)

    assert len(channels) == 1
    assert channels[0].alternate_urls == ["https://example.test/uno-alternativo"]


def test_editor_loads_ansi_playlist_without_losing_accents(tmp_path):
    from ui.dialogs.m3u_editor import M3UEditorDialog

    ruta = tmp_path / "lista.m3u"
    ruta.write_bytes('#EXTINF:-1,Canción España\nhttps://es\n'.encode("cp1252"))

    canales = M3UEditorDialog._fetch_and_parse_source(str(ruta))

    assert [c.name for c in canales] == ["Canción España"]


# --------------------------------------------------------------------------
# "Analizar lista": una lista ajena no puede usar la app para pedir URLs
# internas (loopback, metadatos de nube) ni seguir redirecciones hacia ellas.
# --------------------------------------------------------------------------

class _Response:
    def __init__(self, status_code=200, location=None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}

    def close(self):
        pass


@pytest.fixture
def public_dns(monkeypatch):
    def _resolve(host):
        try:
            return [ipaddress.ip_address(host)]
        except ValueError:
            return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr(net_safety, "_resolve", _resolve)


def _check(urls):
    from ui.dialogs.m3u_editor import M3UEditorDialog

    return M3UEditorDialog._check_streams(urls)


def test_analysis_reports_ok_and_http_errors(monkeypatch, public_dns):
    respuestas = {"https://ok.example/a": 200, "https://roto.example/b": 404}
    monkeypatch.setattr(
        "core.http_limits.requests.get",
        lambda url, **kwargs: _Response(respuestas[url]),
    )

    assert _check(list(respuestas)) == {
        "https://ok.example/a": "OK",
        "https://roto.example/b": "Error HTTP 404",
    }


def test_analysis_keeps_marking_non_http_entries_as_not_verifiable(public_dns):
    assert _check(["rtsp://cam.example/live"]) == {"rtsp://cam.example/live": "No verificable"}


def test_analysis_refuses_internal_destinations_without_requesting_them(monkeypatch, public_dns):
    def _boom(*args, **kwargs):
        raise AssertionError("no debía hacerse ninguna petición")

    monkeypatch.setattr("core.http_limits.requests.get", _boom)
    urls = ["http://127.0.0.1:8080/reiniciar", "http://169.254.169.254/latest/meta-data"]

    assert _check(urls) == {url: "Destino no permitido" for url in urls}


def test_analysis_refuses_a_redirect_to_an_internal_destination(monkeypatch, public_dns):
    pedidas = []

    def _get(url, **kwargs):
        pedidas.append(url)
        return _Response(302, location="http://127.0.0.1:9000/interno")

    monkeypatch.setattr("core.http_limits.requests.get", _get)

    resultado = _check(["https://cdn.example/lista"])

    assert resultado == {"https://cdn.example/lista": "Destino no permitido"}
    assert pedidas == ["https://cdn.example/lista"]
