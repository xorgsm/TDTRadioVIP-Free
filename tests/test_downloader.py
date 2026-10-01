"""
Cobertura de core/downloader.py más allá de la validación de URL (ver
tests/test_downloader_url_validation.py). Los workers son QThread, pero se
prueban llamando a .run() directamente (nunca .start()): así las señales se
emiten de forma síncrona en el hilo del test, sin necesitar un QApplication
ni un bucle de eventos real.
"""
import hashlib
import pathlib
import time

import pytest

from core import downloader
from core.downloader import (
    DownloadWorker,
    SearchWorker,
    UpdateCheckWorker,
    _build_search_command,
    _fmt_eta,
    _fmt_velocidad,
    _num,
    _parse_search_line,
    ensure_yt_dlp,
    mark_update_checked,
    self_update_yt_dlp,
    should_check_update,
)


# --------------------------------------------------------------------------
# Utilidades puras
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor,esperado", [
    ("12.5", 12.5),
    ("0", 0.0),
    ("", None),
    (None, None),
    ("NA", None),
    ("None", None),
    ("no-es-un-numero", None),
])
def test_num_parses_or_returns_none(valor, esperado):
    assert _num(valor) == esperado


@pytest.mark.parametrize("bps,esperado", [
    (0, ""),
    (None, ""),
    (2048, "2 KB/s"),
    (1024 * 1024, "1.0 MB/s"),
    (5 * 1024 * 1024, "5.0 MB/s"),
])
def test_fmt_velocidad(bps, esperado):
    assert _fmt_velocidad(bps) == esperado


@pytest.mark.parametrize("segundos,esperado", [
    (None, ""),
    (45, "faltan 0:45"),
    (125, "faltan 2:05"),
    (3661, "faltan 1h 01m"),
])
def test_fmt_eta(segundos, esperado):
    assert _fmt_eta(segundos) == esperado


def test_url_valida_rejects_value_that_makes_urlsplit_raise_valueerror():
    """urlsplit() puede lanzar ValueError con una URL IPv6 mal formada --
    debe tratarse como URL inválida, no reventar la comprobación."""
    assert downloader.url_valida_para_descarga("http://[::1") is False


# --------------------------------------------------------------------------
# should_check_update / mark_update_checked
# --------------------------------------------------------------------------

def test_should_check_update_true_when_no_marker_file(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    assert should_check_update() is True


def test_should_check_update_false_when_checked_recently(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    mark_update_checked()
    assert should_check_update() is False


def test_should_check_update_true_after_interval_elapsed(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    marker = downloader._last_check_file()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(time.time() - downloader.UPDATE_CHECK_INTERVAL_SECONDS - 1))
    assert should_check_update() is True


def test_should_check_update_true_when_marker_content_is_corrupted(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    marker = downloader._last_check_file()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("no-es-un-timestamp")
    assert should_check_update() is True


def test_mark_update_checked_tolerates_write_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)

    def _raise(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(pathlib.Path, "write_text", _raise)
    mark_update_checked()  # no debe lanzar


# --------------------------------------------------------------------------
# ensure_yt_dlp
# --------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, chunks=(), headers=None):
        self._chunks = list(chunks)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, n=-1):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def _urlopen_sequence(*responses):
    it = iter(responses)

    def fake_urlopen(request, timeout=None):
        return next(it)

    return fake_urlopen


def test_ensure_yt_dlp_skips_download_when_local_copy_is_already_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    tools_dir = downloader._tools_dir()
    exe_path = tools_dir / "yt-dlp.exe"
    contenido = b"binario yt-dlp"
    exe_path.write_bytes(contenido)
    (tools_dir / "yt-dlp.exe.sha256").write_text(hashlib.sha256(contenido).hexdigest())

    def _no_debe_llamarse(*args, **kwargs):
        pytest.fail("con una copia local válida no debe consultar la red")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", _no_debe_llamarse)

    assert ensure_yt_dlp() == str(exe_path)


def test_ensure_yt_dlp_redownloads_when_local_hash_file_is_missing(tmp_path, monkeypatch):
    """El .exe existe pero el .sha256 no (instalación dañada a medias) --
    debe tratarse como copia local inválida y volver a descargar, no
    reventar con el OSError de read_text()."""
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    tools_dir = downloader._tools_dir()
    exe_path = tools_dir / "yt-dlp.exe"
    exe_path.write_bytes(b"binario sin hash acompanante")

    payload = b"binario nuevo"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[f"{digest} *yt-dlp.exe\n".encode("ascii")]),
        _FakeResponse(chunks=[payload], headers={"Content-Length": str(len(payload))}),
    ))

    assert ensure_yt_dlp() == str(exe_path)
    assert exe_path.read_bytes() == payload


def test_ensure_yt_dlp_redownloads_when_local_hash_does_not_match(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    tools_dir = downloader._tools_dir()
    exe_path = tools_dir / "yt-dlp.exe"
    exe_path.write_bytes(b"version vieja corrupta")
    (tools_dir / "yt-dlp.exe.sha256").write_text("0" * 64)

    payload = b"binario nuevo descargado"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[f"{digest} *yt-dlp.exe\n".encode("ascii")]),
        _FakeResponse(chunks=[payload], headers={"Content-Length": str(len(payload))}),
    ))

    resultado = ensure_yt_dlp()

    assert resultado == str(exe_path)
    assert exe_path.read_bytes() == payload


def test_ensure_yt_dlp_downloads_and_verifies_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    payload = b"contenido del ejecutable"
    digest = hashlib.sha256(payload).hexdigest()
    progresos = []
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[f"{digest} *yt-dlp.exe\n".encode("ascii")]),
        _FakeResponse(chunks=[payload[:5], payload[5:]], headers={"Content-Length": str(len(payload))}),
    ))

    resultado = ensure_yt_dlp(progress_cb=progresos.append)

    exe_path = downloader._tools_dir() / "yt-dlp.exe"
    assert resultado == str(exe_path)
    assert exe_path.read_bytes() == payload
    assert (downloader._tools_dir() / "yt-dlp.exe.sha256").read_text() == digest
    assert not exe_path.with_suffix(".part").exists()
    assert progresos  # se reportó progreso al menos una vez


def test_ensure_yt_dlp_raises_when_checksum_file_lacks_yt_dlp_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[b"deadbeef *otro-fichero.exe\n"]),
    ))

    with pytest.raises(RuntimeError, match="SHA-256 de yt-dlp.exe"):
        ensure_yt_dlp()


def test_ensure_yt_dlp_raises_when_declared_size_exceeds_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    digest = hashlib.sha256(b"x").hexdigest()
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[f"{digest} *yt-dlp.exe\n".encode("ascii")]),
        _FakeResponse(headers={"Content-Length": str(downloader.MAX_TOOL_DOWNLOAD_BYTES + 1)}),
    ))

    with pytest.raises(RuntimeError, match="tamaño máximo"):
        ensure_yt_dlp()
    assert not (downloader._tools_dir() / "yt-dlp.exe.part").exists()


def test_ensure_yt_dlp_raises_when_streamed_bytes_exceed_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    digest = hashlib.sha256(b"x").hexdigest()
    chunk_grande = b"a" * (downloader.MAX_TOOL_DOWNLOAD_BYTES + 1)
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[f"{digest} *yt-dlp.exe\n".encode("ascii")]),
        _FakeResponse(chunks=[chunk_grande], headers={"Content-Length": "0"}),
    ))

    with pytest.raises(RuntimeError, match="tamaño máximo"):
        ensure_yt_dlp()
    assert not (downloader._tools_dir() / "yt-dlp.exe.part").exists()


def test_ensure_yt_dlp_raises_when_digest_does_not_match_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "get_app_data_dir", lambda: tmp_path)
    payload = b"contenido descargado"
    monkeypatch.setattr(downloader.urllib.request, "urlopen", _urlopen_sequence(
        _FakeResponse(chunks=[("0" * 64 + " *yt-dlp.exe\n").encode("ascii")]),
        _FakeResponse(chunks=[payload], headers={"Content-Length": str(len(payload))}),
    ))

    with pytest.raises(RuntimeError, match="no coincide"):
        ensure_yt_dlp()
    assert not (downloader._tools_dir() / "yt-dlp.exe.part").exists()
    assert not (downloader._tools_dir() / "yt-dlp.exe").exists()


# --------------------------------------------------------------------------
# self_update_yt_dlp
# --------------------------------------------------------------------------

class _FakeProcess:
    def __init__(self, returncode=0, poll_sequence=None):
        self.returncode = returncode
        self._poll_sequence = list(poll_sequence) if poll_sequence is not None else [returncode]
        self.killed = False
        self.waited = False

    def poll(self):
        if len(self._poll_sequence) > 1:
            return self._poll_sequence.pop(0)
        return self._poll_sequence[0]

    def kill(self):
        self.killed = True
        self._poll_sequence = [self.returncode]

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode


def test_self_update_returns_false_when_process_cannot_start(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("no se encontró el ejecutable")

    monkeypatch.setattr(downloader.subprocess, "Popen", _raise)
    assert self_update_yt_dlp("yt-dlp.exe") is False


def test_self_update_returns_true_on_success(monkeypatch):
    proceso = _FakeProcess(returncode=0)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)
    assert self_update_yt_dlp("yt-dlp.exe") is True


def test_self_update_refreshes_local_hash_so_ensure_does_not_redownload(tmp_path, monkeypatch):
    """yt-dlp -U sustituye el .exe; si el .sha256 guardado no se refresca,
    el siguiente ensure_yt_dlp() lo ve distinto, lo borra y lo vuelve a
    descargar, deshaciendo la autoactualizacion."""
    monkeypatch.setattr(downloader, "_tools_dir", lambda: tmp_path)
    exe_path = tmp_path / "yt-dlp.exe"
    exe_path.write_bytes(b"version vieja")
    hash_path = tmp_path / "yt-dlp.exe.sha256"
    hash_path.write_text(hashlib.sha256(b"version vieja").hexdigest())

    class _ProcesoQueActualiza(_FakeProcess):
        def poll(self):
            exe_path.write_bytes(b"version nueva")  # yt-dlp se sustituye a si mismo
            return self.returncode

    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: _ProcesoQueActualiza(0))

    assert self_update_yt_dlp(str(exe_path)) is True

    assert hash_path.read_text().strip() == hashlib.sha256(b"version nueva").hexdigest()
    assert ensure_yt_dlp() == str(exe_path)  # sin red: no intenta descargar


def test_self_update_failure_keeps_stored_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "_tools_dir", lambda: tmp_path)
    exe_path = tmp_path / "yt-dlp.exe"
    exe_path.write_bytes(b"version vieja")
    hash_path = tmp_path / "yt-dlp.exe.sha256"
    original = hashlib.sha256(b"version vieja").hexdigest()
    hash_path.write_text(original)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: _FakeProcess(returncode=1))

    assert self_update_yt_dlp(str(exe_path)) is False
    assert hash_path.read_text().strip() == original


def test_self_update_returns_false_on_nonzero_exit(monkeypatch):
    proceso = _FakeProcess(returncode=1)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)
    assert self_update_yt_dlp("yt-dlp.exe") is False


def test_self_update_kills_process_when_cancel_check_triggers(monkeypatch):
    proceso = _FakeProcess(poll_sequence=[None, None])
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    assert self_update_yt_dlp("yt-dlp.exe", timeout=25, cancel_check=lambda: True) is False
    assert proceso.killed is True


def test_self_update_swallows_timeout_expired_while_waiting_after_kill(monkeypatch):
    proceso = _FakeProcess(poll_sequence=[None, None])

    def _wait(timeout=None):
        raise downloader.subprocess.TimeoutExpired(cmd="yt-dlp.exe", timeout=timeout)

    proceso.wait = _wait
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    assert self_update_yt_dlp("yt-dlp.exe", cancel_check=lambda: True) is False
    assert proceso.killed is True


def test_self_update_kills_process_on_timeout(monkeypatch):
    proceso = _FakeProcess(poll_sequence=[None, None])
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)
    monkeypatch.setattr(downloader.time, "monotonic", iter([0, 100, 100]).__next__)
    monkeypatch.setattr(downloader.time, "sleep", lambda *_: None)

    assert self_update_yt_dlp("yt-dlp.exe", timeout=1) is False
    assert proceso.killed is True


# --------------------------------------------------------------------------
# Búsqueda multi-fuente: comando y parseo
# --------------------------------------------------------------------------

@pytest.mark.parametrize("source,esperado_prefijo,contiene_sufijo", [
    ("YouTube", "ytsearch", False),
    ("SoundCloud", "scsearch", False),
    ("FMA / Jamendo", "ytsearch", True),
    ("Todo", "ytsearch", False),
])
def test_build_search_command(source, esperado_prefijo, contiene_sufijo):
    cmd = _build_search_command("yt-dlp.exe", "una consulta", source, 8)
    assert cmd[0] == "yt-dlp.exe"
    assert cmd[1].startswith(f"{esperado_prefijo}8:una consulta")
    assert ("creative commons free music" in cmd[1]) is contiene_sufijo
    assert "--dump-json" in cmd


def test_parse_search_line_discards_invalid_json():
    assert _parse_search_line("esto no es json", "YouTube") is None


def test_parse_search_line_discards_entry_without_url():
    import json
    linea = json.dumps({"title": "sin url"})
    assert _parse_search_line(linea, "YouTube") is None


def test_parse_search_line_maps_soundcloud_extractor():
    import json
    linea = json.dumps({
        "webpage_url": "https://soundcloud.com/artista/tema",
        "extractor_key": "Soundcloud",
        "title": "Tema", "uploader": "Artista", "duration": 180, "id": "abc",
    })
    resultado = _parse_search_line(linea, "SoundCloud")
    assert resultado["source"] == "SoundCloud"
    assert resultado["duration"] == "3:00"


def test_parse_search_line_keeps_fma_jamendo_label_for_youtube_results():
    import json
    linea = json.dumps({
        "webpage_url": "https://youtube.com/watch?v=x",
        "extractor_key": "Youtube",
        "title": "Tema libre", "duration": 200, "id": "x",
    })
    resultado = _parse_search_line(linea, "FMA / Jamendo")
    assert resultado["source"] == "FMA / Jamendo"


def test_parse_search_line_uses_youtube_label_outside_fma_search():
    import json
    linea = json.dumps({
        "webpage_url": "https://youtube.com/watch?v=x",
        "extractor_key": "Youtube",
        "title": "Tema", "duration": 200, "id": "x",
    })
    resultado = _parse_search_line(linea, "YouTube")
    assert resultado["source"] == "YouTube"


def test_parse_search_line_falls_back_to_extractor_key_for_other_sources():
    import json
    linea = json.dumps({
        "webpage_url": "https://vimeo.com/1", "extractor_key": "Vimeo",
        "title": "Tema", "duration": 10, "id": "1",
    })
    resultado = _parse_search_line(linea, "Todo")
    assert resultado["source"] == "Vimeo"


def test_parse_search_line_discards_private_soundcloud_api_url():
    import json
    linea = json.dumps({
        "webpage_url": "https://api.soundcloud.com/tracks/12345",
        "extractor_key": "Soundcloud", "duration": 200, "id": "12345",
    })
    assert _parse_search_line(linea, "SoundCloud") is None


def test_parse_search_line_discards_short_soundcloud_preview():
    import json
    linea = json.dumps({
        "webpage_url": "https://soundcloud.com/artista/tema",
        "extractor_key": "Soundcloud", "duration": 20, "id": "1",
    })
    assert _parse_search_line(linea, "SoundCloud") is None


def test_parse_search_line_keeps_short_track_on_non_soundcloud_sources():
    import json
    linea = json.dumps({
        "webpage_url": "https://youtube.com/watch?v=x",
        "extractor_key": "Youtube", "duration": 20, "id": "x",
    })
    assert _parse_search_line(linea, "YouTube") is not None


# --------------------------------------------------------------------------
# UpdateCheckWorker
# --------------------------------------------------------------------------

def test_update_check_worker_emits_success(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "self_update_yt_dlp", lambda *a, **k: True)
    monkeypatch.setattr(downloader, "mark_update_checked", lambda: None)

    worker = UpdateCheckWorker()
    resultados = []
    worker.done.connect(lambda ok, msg: resultados.append((ok, msg)))
    worker.run()

    assert resultados == [(True, "yt-dlp está actualizado a la última versión.")]


def test_update_check_worker_emits_failure_when_ensure_yt_dlp_raises(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: (_ for _ in ()).throw(RuntimeError("sin red")))

    worker = UpdateCheckWorker()
    resultados = []
    worker.done.connect(lambda ok, msg: resultados.append((ok, msg)))
    worker.run()

    assert resultados[0][0] is False
    assert "sin red" in resultados[0][1]


def test_update_check_worker_emits_failure_when_self_update_fails(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "self_update_yt_dlp", lambda *a, **k: False)
    monkeypatch.setattr(downloader, "mark_update_checked", lambda: None)

    worker = UpdateCheckWorker()
    resultados = []
    worker.done.connect(lambda ok, msg: resultados.append((ok, msg)))
    worker.run()

    assert resultados[0][0] is False


def test_update_check_worker_does_not_emit_when_cancelled_before_ensure(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: (_ for _ in ()).throw(RuntimeError("no debería importar")))

    worker = UpdateCheckWorker()
    worker.cancel()
    resultados = []
    worker.done.connect(lambda *a: resultados.append(a))
    worker.run()

    assert resultados == []


def test_update_check_worker_does_not_emit_when_cancelled_right_after_ensure(monkeypatch):
    worker = UpdateCheckWorker()

    def _ensure():
        worker._cancelado = True
        return "yt-dlp.exe"

    monkeypatch.setattr(downloader, "ensure_yt_dlp", _ensure)

    def _no_debe_llamarse(*args, **kwargs):
        pytest.fail("no debe autoactualizar tras cancelar")

    monkeypatch.setattr(downloader, "self_update_yt_dlp", _no_debe_llamarse)
    resultados = []
    worker.done.connect(lambda *a: resultados.append(a))
    worker.run()

    assert resultados == []


def test_update_check_worker_does_not_emit_when_cancelled_after_self_update(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")

    worker = UpdateCheckWorker()

    def _self_update(*args, **kwargs):
        worker._cancelado = True
        return True

    monkeypatch.setattr(downloader, "self_update_yt_dlp", _self_update)
    monkeypatch.setattr(downloader, "mark_update_checked", lambda: None)
    resultados = []
    worker.done.connect(lambda *a: resultados.append(a))
    worker.run()

    assert resultados == []


# --------------------------------------------------------------------------
# DownloadWorker
# --------------------------------------------------------------------------

def test_download_worker_run_fails_fast_on_invalid_url():
    worker = DownloadWorker("no-es-una-url", ".", as_mp3=False)
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "no es válida" in fallos[0]


def test_download_worker_run_fails_when_dest_dir_cannot_be_created(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path / "destino"), as_mp3=False)
    monkeypatch.setattr(downloader.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("sin permiso")))
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "no se pudo crear la carpeta" in fallos[0].lower()


def test_download_worker_run_fails_when_ensure_yt_dlp_raises(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda **k: (_ for _ in ()).throw(RuntimeError("sin internet")))
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "sin internet" in fallos[0]


def test_download_worker_run_reports_cancelled_right_after_preparing_tool(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)

    def _ensure(**kwargs):
        worker._cancelado = True
        return "yt-dlp.exe"

    monkeypatch.setattr(downloader, "ensure_yt_dlp", _ensure)
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert fallos == ["__cancelled__"]


def test_download_worker_run_checks_for_updates_when_due(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda **k: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "should_check_update", lambda: True)
    llamadas = []
    monkeypatch.setattr(downloader, "self_update_yt_dlp", lambda *a, **k: llamadas.append(a) or True)
    monkeypatch.setattr(downloader, "mark_update_checked", lambda: llamadas.append("marked"))
    monkeypatch.setattr(worker, "_run_download", lambda exe: str(tmp_path / "resultado.mp4"))

    finalizados = []
    worker.finished_ok.connect(finalizados.append)
    worker.run()

    assert llamadas[0] == ("yt-dlp.exe",)
    assert "marked" in llamadas
    assert finalizados == [str(tmp_path / "resultado.mp4")]


def test_download_worker_run_emits_finished_ok_using_dest_dir_when_path_unknown(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda **k: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "should_check_update", lambda: False)
    monkeypatch.setattr(worker, "_run_download", lambda exe: None)

    finalizados = []
    worker.finished_ok.connect(finalizados.append)
    worker.run()

    assert finalizados == [str(tmp_path)]


def test_download_worker_run_does_not_emit_finished_when_run_download_already_failed(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda **k: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "should_check_update", lambda: False)

    def _run_download(exe):
        worker._fallo_grave = True
        return None

    monkeypatch.setattr(worker, "_run_download", _run_download)
    finalizados, fallos = [], []
    worker.finished_ok.connect(finalizados.append)
    worker.failed.connect(fallos.append)
    worker.run()

    assert finalizados == []
    assert fallos == []  # el fallo concreto ya se emitió dentro de _run_download


def test_download_worker_run_reports_cancelled_after_run_download(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda **k: "yt-dlp.exe")
    monkeypatch.setattr(downloader, "should_check_update", lambda: False)

    def _run_download(exe):
        worker._cancelado = True
        return None

    monkeypatch.setattr(worker, "_run_download", _run_download)
    finalizados, fallos = [], []
    worker.finished_ok.connect(finalizados.append)
    worker.failed.connect(fallos.append)
    worker.run()

    assert finalizados == []
    assert fallos == ["__cancelled__"]


def test_run_download_uses_a_temp_file_and_cleans_it_up(tmp_path, monkeypatch):
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    rutas_vistas = []

    def _fake_ejecutar(exe_path, ruta_salida_tmp):
        rutas_vistas.append(ruta_salida_tmp)
        assert downloader.os.path.exists(ruta_salida_tmp)
        return "resultado.mp4"

    monkeypatch.setattr(worker, "_ejecutar", _fake_ejecutar)

    resultado = worker._run_download("yt-dlp.exe")

    assert resultado == "resultado.mp4"
    assert rutas_vistas and not downloader.os.path.exists(rutas_vistas[0])


def test_run_download_tolerates_temp_file_already_removed(tmp_path, monkeypatch):
    """Si _ejecutar() ya limpió el temporal (o algo más lo borró), el
    os.unlink() final no debe reventar el resultado de la descarga."""
    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)

    def _fake_ejecutar(exe_path, ruta_salida_tmp):
        downloader.os.unlink(ruta_salida_tmp)
        return "resultado.mp4"

    monkeypatch.setattr(worker, "_ejecutar", _fake_ejecutar)

    assert worker._run_download("yt-dlp.exe") == "resultado.mp4"


def test_download_worker_cancel_terminates_running_process():
    worker = DownloadWorker("https://example.com/v", ".", as_mp3=False)
    proceso = _FakeProcess()
    worker._process = proceso
    worker.cancel()
    assert worker._cancelado is True


def test_download_worker_cancel_is_a_noop_without_a_running_process():
    worker = DownloadWorker("https://example.com/v", ".", as_mp3=False)
    worker.cancel()  # no debe lanzar aunque nunca haya arrancado


@pytest.mark.parametrize("as_mp3,esperado", [
    (True, "--extract-audio"),
    (False, "--merge-output-format"),
])
def test_construir_comando_branches_by_format(as_mp3, esperado):
    worker = DownloadWorker("https://example.com/v", "salida", as_mp3=as_mp3)
    cmd = worker._construir_comando("yt-dlp.exe", "tmp.txt")
    assert esperado in cmd


def test_construir_comando_includes_ffmpeg_location_when_configured(monkeypatch):
    monkeypatch.setattr(downloader, "get_ffmpeg_dir", lambda: r"C:\ffmpeg\bin")
    worker = DownloadWorker("https://example.com/v", "salida", as_mp3=False)
    cmd = worker._construir_comando("yt-dlp.exe", "tmp.txt")
    assert "--ffmpeg-location" in cmd
    assert r"C:\ffmpeg\bin" in cmd


class _FakeDownloadProcess:
    def __init__(self, lineas, returncode=0):
        self.stdout = iter(lineas)
        self._returncode = returncode
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self._returncode

    def poll(self):
        return self._returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def test_ejecutar_returns_final_path_on_success(tmp_path, monkeypatch):
    salida = tmp_path / "video.mp4"
    salida.write_bytes(b"x")
    ruta_tmp = tmp_path / "ruta.txt"
    ruta_tmp.write_text(str(salida))

    progreso = "download:@@PROG@@1024|2048|NA|500000|10"
    proceso = _FakeDownloadProcess([f"{progreso}\n", "[ffmpeg] procesando\n"], returncode=0)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    eventos = []
    worker.progress.connect(lambda frac, texto: eventos.append((frac, texto)))

    resultado = worker._ejecutar("yt-dlp.exe", str(ruta_tmp))

    assert resultado == str(salida)
    assert any(texto == "Procesando con ffmpeg…" for _, texto in eventos)


def test_ejecutar_collects_error_lines_and_fails_on_nonzero_exit(tmp_path, monkeypatch):
    proceso = _FakeDownloadProcess(["ERROR: no se pudo\n"], returncode=1)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    fallos = []
    worker.failed.connect(fallos.append)

    resultado = worker._ejecutar("yt-dlp.exe", str(tmp_path / "ruta.txt"))

    assert resultado is None
    assert worker._fallo_grave is True
    assert "ERROR: no se pudo" in fallos[0]


def test_ejecutar_returns_none_and_marks_cancelled_process(tmp_path, monkeypatch):
    proceso = _FakeDownloadProcess([], returncode=0)
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    worker._cancelado = True

    resultado = worker._ejecutar("yt-dlp.exe", str(tmp_path / "ruta.txt"))

    assert resultado is None


def test_ejecutar_fails_when_process_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(
        downloader.subprocess, "Popen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no encontrado")),
    )

    worker = DownloadWorker("https://example.com/v", str(tmp_path), as_mp3=False)
    fallos = []
    worker.failed.connect(fallos.append)

    resultado = worker._ejecutar("yt-dlp.exe", str(tmp_path / "ruta.txt"))

    assert resultado is None
    assert worker._fallo_grave is True
    assert "no encontrado" in fallos[0]


def test_emitir_progreso_ignores_incomplete_payload():
    worker = DownloadWorker("https://example.com/v", ".", as_mp3=False)
    eventos = []
    worker.progress.connect(lambda *a: eventos.append(a))
    worker._emitir_progreso("solo|dos")
    assert eventos == []


def test_emitir_progreso_computes_fraction_and_details():
    worker = DownloadWorker("https://example.com/v", ".", as_mp3=False)
    eventos = []
    worker.progress.connect(lambda frac, texto: eventos.append((frac, texto)))
    worker._emitir_progreso("512|1024|NA|204800|30")
    frac, texto = eventos[0]
    assert frac == 0.5
    assert "200 KB/s" in texto
    assert "faltan 0:30" in texto


def test_emitir_progreso_defaults_to_zero_fraction_without_totals():
    worker = DownloadWorker("https://example.com/v", ".", as_mp3=False)
    eventos = []
    worker.progress.connect(lambda frac, texto: eventos.append((frac, texto)))
    worker._emitir_progreso("NA|NA|NA|NA|NA")
    assert eventos[0][0] == 0.0


def test_leer_ruta_final_returns_last_existing_path(tmp_path):
    existente = tmp_path / "video.mp4"
    existente.write_bytes(b"x")
    ruta_tmp = tmp_path / "salida.txt"
    ruta_tmp.write_text(f"{tmp_path / 'no-existe.mp4'}\n{existente}\n")

    assert DownloadWorker._leer_ruta_final(str(ruta_tmp)) == str(existente)


def test_leer_ruta_final_returns_none_when_no_path_exists(tmp_path):
    ruta_tmp = tmp_path / "salida.txt"
    ruta_tmp.write_text(str(tmp_path / "fantasma.mp4"))
    assert DownloadWorker._leer_ruta_final(str(ruta_tmp)) is None


def test_leer_ruta_final_returns_none_when_file_missing(tmp_path):
    assert DownloadWorker._leer_ruta_final(str(tmp_path / "no-existe.txt")) is None


# --------------------------------------------------------------------------
# SearchWorker
# --------------------------------------------------------------------------

def test_search_worker_emits_empty_results_for_blank_query():
    worker = SearchWorker("   ", "YouTube")
    resultados = []
    worker.results.connect(resultados.append)
    worker.run()
    assert resultados == [[]]


def test_search_worker_fails_when_ensure_yt_dlp_raises(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: (_ for _ in ()).throw(RuntimeError("sin red")))
    worker = SearchWorker("consulta", "YouTube")
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "sin red" in fallos[0]


def test_search_worker_reports_cancelled_before_starting_process(monkeypatch):
    worker = SearchWorker("consulta", "YouTube")

    def _ensure():
        worker._cancelado = True
        return "yt-dlp.exe"

    monkeypatch.setattr(downloader, "ensure_yt_dlp", _ensure)
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert fallos == ["__cancelled__"]


def test_search_worker_fails_when_process_cannot_start(monkeypatch):
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(
        downloader.subprocess, "Popen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no encontrado")),
    )
    worker = SearchWorker("consulta", "YouTube")
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "no encontrado" in fallos[0]


def test_search_worker_emits_parsed_results(monkeypatch):
    import json
    linea = json.dumps({
        "webpage_url": "https://youtube.com/watch?v=x",
        "extractor_key": "Youtube", "title": "Tema", "duration": 120, "id": "x",
    })
    proceso = _FakeDownloadProcess([f"{linea}\n"], returncode=0)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = SearchWorker("consulta", "YouTube")
    resultados = []
    worker.results.connect(resultados.append)
    worker.run()

    assert len(resultados[0]) == 1
    assert resultados[0][0]["title"] == "Tema"


def test_search_worker_reports_cancelled_after_process_started(monkeypatch):
    """Cancelar a mitad de la lectura de stdout (no antes de arrancar el
    proceso, ver test_search_worker_reports_cancelled_before_starting_process)
    debe cortar el bucle y avisar igual con "__cancelled__"."""
    worker = SearchWorker("consulta", "YouTube")

    def _lineas_con_cancelacion():
        yield "algo\n"
        worker._cancelado = True
        yield "esto no debe procesarse\n"

    proceso = _FakeDownloadProcess([], returncode=0)
    proceso.stdout = _lineas_con_cancelacion()
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    fallos, resultados = [], []
    worker.failed.connect(fallos.append)
    worker.results.connect(resultados.append)
    worker.run()

    assert fallos == ["__cancelled__"]
    assert resultados == []


def test_search_worker_run_skips_blank_lines_from_stdout(monkeypatch):
    import json
    linea = json.dumps({
        "webpage_url": "https://youtube.com/watch?v=x",
        "extractor_key": "Youtube", "title": "Tema", "duration": 10, "id": "x",
    })
    proceso = _FakeDownloadProcess(["\n", "   \n", f"{linea}\n"], returncode=0)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = SearchWorker("consulta", "YouTube")
    resultados = []
    worker.results.connect(resultados.append)
    worker.run()

    assert len(resultados[0]) == 1


def test_search_worker_reports_timeout_message_when_stalled(monkeypatch):
    proceso = _FakeDownloadProcess(["algo\n"], returncode=0)
    monkeypatch.setattr(downloader, "ensure_yt_dlp", lambda: "yt-dlp.exe")
    monkeypatch.setattr(downloader.subprocess, "Popen", lambda *a, **k: proceso)

    worker = SearchWorker("consulta", "YouTube")
    worker._timeout_saltado = True
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "tardó más de" in fallos[0]


def test_search_worker_cancel_kills_running_process():
    worker = SearchWorker("consulta", "YouTube")
    proceso = _FakeProcess()
    worker._process = proceso
    worker.cancel()
    assert worker._cancelado is True
    assert proceso.killed is True


def test_search_worker_cancel_is_a_noop_without_a_running_process():
    worker = SearchWorker("consulta", "YouTube")
    worker.cancel()  # no debe lanzar aunque nunca haya arrancado


def test_search_worker_cancel_swallows_kill_failure():
    worker = SearchWorker("consulta", "YouTube")
    proceso = _FakeProcess()
    proceso.kill = lambda: (_ for _ in ()).throw(OSError("proceso ya terminado"))
    worker._process = proceso
    worker.cancel()  # no debe lanzar aunque kill() falle
