"""
Cobertura de core/caster.py: detección de disponibilidad de pychromecast,
adivinación de content-type, el servidor HTTP de un solo archivo con
soporte de rangos (LocalFileServer/_SingleFileHandler), y las clases que
envuelven pychromecast (CastDiscoveryWorker, CastSession).

pychromecast se importa de forma perezosa dentro de las funciones que lo
usan (ver el docstring del propio módulo) -- los tests que necesitan
simular su presencia/ausencia inyectan un módulo falso en sys.modules en
vez de requerir la dependencia real instalada.

CastDiscoveryWorker es un QThread, pero se prueba llamando a .run()
directamente (nunca .start()), igual que el resto del proyecto (ver
tests/test_downloader.py): así las señales se emiten de forma síncrona
sin necesitar un QApplication ni un bucle de eventos real.
"""
import sys
import types
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest

from core import caster
from core.caster import CastDiscoveryWorker, CastSession, LocalFileServer


# --------------------------------------------------------------------------
# pychromecast_available()
# --------------------------------------------------------------------------

def test_pychromecast_available_false_when_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "pychromecast", None)
    assert caster.pychromecast_available() is False


def test_pychromecast_available_true_when_import_succeeds(monkeypatch):
    fake_module = types.ModuleType("pychromecast")
    monkeypatch.setitem(sys.modules, "pychromecast", fake_module)
    assert caster.pychromecast_available() is True


# --------------------------------------------------------------------------
# guess_stream_content_type()
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url,kind,esperado", [
    ("https://ejemplo.com/canal.m3u8", "", "application/x-mpegURL"),
    ("https://ejemplo.com/canal.M3U8", "", "application/x-mpegURL"),
    ("https://ejemplo.com/hls/m3u8/index.txt", "", "application/x-mpegURL"),
    ("https://ejemplo.com/canal.mpd", "", "application/dash+xml"),
    ("https://ejemplo.com/radio.mp3", "", "audio/mp3"),
    ("https://ejemplo.com/radio.aac", "", "audio/aac"),
    ("https://ejemplo.com/radio.m4a", "", "audio/aac"),
    ("https://ejemplo.com/stream", "radio", "audio/mp3"),
    ("https://ejemplo.com/canal.ts", "", "video/mp4"),
    ("https://ejemplo.com/canal", "tv", "video/mp4"),
])
def test_guess_stream_content_type(url, kind, esperado):
    assert caster.guess_stream_content_type(url, kind) == esperado


def test_guess_stream_content_type_strips_query_string_before_matching():
    """La extensión real es .mp3, pero la query contiene "m3u8" -- debe
    ganar la extensión del path, no una coincidencia dentro de la query."""
    assert caster.guess_stream_content_type("https://ejemplo.com/radio.mp3?ref=m3u8") == "audio/mp3"


# --------------------------------------------------------------------------
# _local_lan_ip()
# --------------------------------------------------------------------------

def test_local_lan_ip_returns_the_sockets_local_address(monkeypatch):
    fake_socket = Mock()
    fake_socket.getsockname.return_value = ("192.168.1.50", 12345)
    monkeypatch.setattr(caster.socket, "socket", lambda *a, **k: fake_socket)

    assert caster._local_lan_ip() == "192.168.1.50"
    fake_socket.connect.assert_called_once_with(("8.8.8.8", 80))
    fake_socket.close.assert_called_once()


def test_local_lan_ip_falls_back_to_loopback_on_oserror(monkeypatch):
    fake_socket = Mock()
    fake_socket.connect.side_effect = OSError("sin red")
    monkeypatch.setattr(caster.socket, "socket", lambda *a, **k: fake_socket)

    assert caster._local_lan_ip() == "127.0.0.1"
    fake_socket.close.assert_called_once()


# --------------------------------------------------------------------------
# LocalFileServer / _SingleFileHandler (servidor HTTP real en localhost)
# --------------------------------------------------------------------------

@pytest.fixture
def served_file(monkeypatch, tmp_path):
    """Arranca un LocalFileServer sirviendo un archivo de prueba y
    devuelve (url_localhost, token, contenido, server) ya limpiado al
    terminar el test. La URL que devuelve serve() usa _local_lan_ip()
    (irrelevante para pruebas locales); se reescribe a 127.0.0.1 para
    conectar de verdad sin depender de la red real de la máquina."""
    monkeypatch.setattr(caster, "_local_lan_ip", lambda: "127.0.0.1")
    contenido = b"contenido de prueba" * 100
    archivo = tmp_path / "video.mp4"
    archivo.write_bytes(contenido)

    server = LocalFileServer()
    url, content_type = server.serve(str(archivo))
    try:
        yield url, content_type, contenido, server
    finally:
        server.stop()


def test_local_file_server_serves_full_content_with_valid_token(served_file):
    url, content_type, contenido, _server = served_file
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        assert resp.headers.get("Content-Type") == content_type
        assert resp.headers.get("Accept-Ranges") == "bytes"
        assert resp.read() == contenido


def test_local_file_server_rejects_request_without_valid_token(served_file):
    url, *_ = served_file
    url_sin_token = url.split("?")[0] + "?t=token-invalido"
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(url_sin_token, timeout=5)
    assert excinfo.value.code == 403


def test_local_file_server_supports_range_requests(served_file):
    url, _content_type, contenido, _server = served_file
    req = urllib.request.Request(url, headers={"Range": "bytes=5-14"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 206
        assert resp.headers.get("Content-Range") == f"bytes 5-14/{len(contenido)}"
        assert resp.read() == contenido[5:15]


def test_local_file_server_supports_suffix_range_requests(served_file):
    url, _content_type, contenido, _server = served_file
    req = urllib.request.Request(url, headers={"Range": "bytes=-10"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 206
        assert resp.read() == contenido[-10:]


def test_local_file_server_rejects_range_outside_file_size(served_file):
    url, _content_type, contenido, _server = served_file
    req = urllib.request.Request(url, headers={"Range": f"bytes={len(contenido) + 100}-"})
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req, timeout=5)
    assert excinfo.value.code == 416


@pytest.mark.parametrize("range_header", [
    "bytes=abc-def",  # no matchea el patrón bytes=\d*-\d*
    "bytes=-",         # matchea pero ambos grupos vacíos
    "bytes=-0",        # forma sufijo con N <= 0
])
def test_local_file_server_rejects_unparseable_range_headers(served_file, range_header):
    url, *_ = served_file
    req = urllib.request.Request(url, headers={"Range": range_header})
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req, timeout=5)
    assert excinfo.value.code == 416


def test_local_file_server_returns_404_when_file_disappears_after_serving(served_file, tmp_path):
    url, *_ = served_file
    # El archivo servido vive dentro de tmp_path (ver el fixture served_file);
    # borrarlo simula que desaparece entre el arranque del servidor y la petición.
    for archivo in tmp_path.glob("*.mp4"):
        archivo.unlink()

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(url, timeout=5)
    assert excinfo.value.code == 404


def test_local_file_server_head_request_returns_headers_without_body(served_file):
    url, _content_type, contenido, _server = served_file
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert resp.headers.get("Content-Length") == str(len(contenido))
        assert resp.read() == b""


def test_local_file_server_serve_stops_previous_server_on_new_call(monkeypatch, tmp_path):
    monkeypatch.setattr(caster, "_local_lan_ip", lambda: "127.0.0.1")
    archivo_a = tmp_path / "a.mp4"
    archivo_a.write_bytes(b"a" * 10)
    archivo_b = tmp_path / "b.mp4"
    archivo_b.write_bytes(b"b" * 10)

    server = LocalFileServer()
    url_a, _ = server.serve(str(archivo_a))
    puerto_a = server.port
    url_b, _ = server.serve(str(archivo_b))

    try:
        assert server.port != puerto_a
        with pytest.raises(urllib.error.URLError):
            urllib.request.urlopen(url_a, timeout=2)
        with urllib.request.urlopen(url_b, timeout=5) as resp:
            assert resp.read() == b"b" * 10
    finally:
        server.stop()


def test_local_file_server_stop_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(caster, "_local_lan_ip", lambda: "127.0.0.1")
    archivo = tmp_path / "a.mp4"
    archivo.write_bytes(b"a")

    server = LocalFileServer()
    server.serve(str(archivo))
    server.stop()
    server.stop()  # no debe lanzar la segunda vez


def test_local_file_server_stop_swallows_oserror_from_shutdown(monkeypatch, tmp_path):
    monkeypatch.setattr(caster, "_local_lan_ip", lambda: "127.0.0.1")
    archivo = tmp_path / "a.mp4"
    archivo.write_bytes(b"a")

    server = LocalFileServer()
    server.serve(str(archivo))
    server._httpd.shutdown = Mock(side_effect=OSError("ya cerrado"))

    server.stop()  # no debe propagar la excepción

    assert server._httpd is None


# --------------------------------------------------------------------------
# CastDiscoveryWorker
# --------------------------------------------------------------------------

def test_cast_discovery_worker_emits_empty_list_when_pychromecast_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "pychromecast", None)
    worker = CastDiscoveryWorker()
    resultados = []
    worker.found.connect(resultados.append)

    worker.run()

    assert resultados == [[]]
    assert worker.devices == []


def test_cast_discovery_worker_emits_empty_list_when_get_chromecasts_raises(monkeypatch):
    fake_module = types.ModuleType("pychromecast")
    fake_module.get_chromecasts = Mock(side_effect=RuntimeError("sin red"))
    monkeypatch.setitem(sys.modules, "pychromecast", fake_module)

    worker = CastDiscoveryWorker()
    resultados = []
    worker.found.connect(resultados.append)

    worker.run()

    assert resultados == [[]]


def test_cast_discovery_worker_emits_device_names_on_success(monkeypatch):
    dispositivo_a = Mock(name="salon")
    dispositivo_a.name = "Salón"
    dispositivo_b = Mock(name="cuarto")
    dispositivo_b.name = "Cuarto"
    fake_browser = Mock()
    fake_module = types.ModuleType("pychromecast")
    fake_module.get_chromecasts = Mock(return_value=([dispositivo_a, dispositivo_b], fake_browser))
    monkeypatch.setitem(sys.modules, "pychromecast", fake_module)

    worker = CastDiscoveryWorker()
    resultados = []
    worker.found.connect(resultados.append)

    worker.run()

    assert resultados == [["Salón", "Cuarto"]]
    assert worker.devices == [dispositivo_a, dispositivo_b]
    assert worker._browser is fake_browser


def test_cast_discovery_worker_device_by_name_finds_existing_device():
    worker = CastDiscoveryWorker()
    dispositivo = Mock()
    dispositivo.name = "Salón"
    worker.devices = [dispositivo]

    assert worker.device_by_name("Salón") is dispositivo


def test_cast_discovery_worker_device_by_name_returns_none_when_not_found():
    worker = CastDiscoveryWorker()
    worker.devices = []
    assert worker.device_by_name("Inexistente") is None


def test_cast_discovery_worker_stop_discovery_is_a_noop_without_browser():
    worker = CastDiscoveryWorker()
    worker.stop_discovery()  # no debe lanzar
    assert worker._browser is None


def test_cast_discovery_worker_stop_discovery_calls_pychromecast_and_clears_browser(monkeypatch):
    fake_browser = Mock()
    fake_discovery = types.SimpleNamespace(stop_discovery=Mock())
    fake_module = types.ModuleType("pychromecast")
    fake_module.discovery = fake_discovery
    monkeypatch.setitem(sys.modules, "pychromecast", fake_module)

    worker = CastDiscoveryWorker()
    worker._browser = fake_browser

    worker.stop_discovery()

    fake_discovery.stop_discovery.assert_called_once_with(fake_browser)
    assert worker._browser is None


def test_cast_discovery_worker_stop_discovery_swallows_errors(monkeypatch):
    fake_discovery = types.SimpleNamespace(
        stop_discovery=Mock(side_effect=RuntimeError("boom"))
    )
    fake_module = types.ModuleType("pychromecast")
    fake_module.discovery = fake_discovery
    monkeypatch.setitem(sys.modules, "pychromecast", fake_module)

    worker = CastDiscoveryWorker()
    worker._browser = Mock()

    worker.stop_discovery()  # no debe propagar la excepción
    assert worker._browser is None


# --------------------------------------------------------------------------
# CastSession
# --------------------------------------------------------------------------

def test_cast_session_connect_waits_for_device_and_stores_it():
    session = CastSession()
    dispositivo = Mock()
    dispositivo.name = "Salón"

    session.connect(dispositivo)

    dispositivo.wait.assert_called_once_with(timeout=10)
    assert session.device is dispositivo
    assert session.device_name == "Salón"


def test_cast_session_cast_url_raises_without_a_connected_device():
    session = CastSession()
    with pytest.raises(RuntimeError):
        session.cast_url("http://ejemplo.com/x.mp4", "video/mp4")


def test_cast_session_cast_url_plays_media_on_the_connected_device():
    session = CastSession()
    dispositivo = Mock()
    session.device = dispositivo

    session.cast_url("http://ejemplo.com/x.mp4", "video/mp4", title="Mi vídeo")

    dispositivo.media_controller.play_media.assert_called_once_with(
        "http://ejemplo.com/x.mp4", "video/mp4", title="Mi vídeo"
    )
    dispositivo.media_controller.block_until_active.assert_called_once_with(timeout=10)


def test_cast_session_cast_url_passes_none_title_when_empty():
    session = CastSession()
    dispositivo = Mock()
    session.device = dispositivo

    session.cast_url("http://ejemplo.com/x.mp4", "video/mp4")

    dispositivo.media_controller.play_media.assert_called_once_with(
        "http://ejemplo.com/x.mp4", "video/mp4", title=None
    )


def test_cast_session_cast_local_file_serves_and_casts_the_url(monkeypatch):
    session = CastSession()
    dispositivo = Mock()
    session.device = dispositivo
    session.file_server = Mock()
    session.file_server.serve.return_value = ("http://127.0.0.1:1234/f.mp4?t=x", "video/mp4")

    session.cast_local_file("C:/videos/f.mp4", title="Peli")

    session.file_server.serve.assert_called_once_with("C:/videos/f.mp4")
    dispositivo.media_controller.play_media.assert_called_once_with(
        "http://127.0.0.1:1234/f.mp4?t=x", "video/mp4", title="Peli"
    )


def test_cast_session_stop_stops_device_and_file_server():
    session = CastSession()
    dispositivo = Mock()
    session.device = dispositivo
    session.file_server = Mock()

    session.stop()

    dispositivo.media_controller.stop.assert_called_once()
    dispositivo.quit_app.assert_called_once()
    session.file_server.stop.assert_called_once()


def test_cast_session_stop_swallows_device_errors_but_still_stops_file_server():
    session = CastSession()
    dispositivo = Mock()
    dispositivo.media_controller.stop.side_effect = RuntimeError("desconectado")
    session.device = dispositivo
    session.file_server = Mock()

    session.stop()  # no debe propagar la excepción

    session.file_server.stop.assert_called_once()


def test_cast_session_stop_without_a_device_only_stops_file_server():
    session = CastSession()
    session.file_server = Mock()

    session.stop()

    session.file_server.stop.assert_called_once()


def test_cast_session_disconnect_stops_and_clears_device():
    session = CastSession()
    dispositivo = Mock()
    dispositivo.name = "Salón"
    session.device = dispositivo
    session.device_name = "Salón"
    session.file_server = Mock()

    session.disconnect()

    assert session.device is None
    assert session.device_name is None
    session.file_server.stop.assert_called_once()
