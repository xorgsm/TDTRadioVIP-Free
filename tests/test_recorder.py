"""
Cobertura de core/recorder.py (grabación de streams con ffmpeg), sin
ffmpeg real: subprocess.Popen se dobla con un FakeProcess controlable, y
time.monotonic()/time.sleep() con un FakeClock que avanza en cada sleep()
en vez de esperar de verdad -- ver FakeClock más abajo. Mismo estilo que
tests/test_vpn_client.py (monkeypatch sobre nombres del propio módulo,
sin mocks pesados).
"""
import subprocess
from pathlib import Path

import pytest

from core import recorder as recorder_module
from core.recorder import Recorder, _escape_drawtext


class FakeStdin:
    def __init__(self, raise_on_write=False):
        self.written = b""
        self.flushed = False
        self._raise_on_write = raise_on_write

    def write(self, data):
        if self._raise_on_write:
            raise OSError("pipe cerrado")
        self.written += data

    def flush(self):
        self.flushed = True


class FakeProcess:
    """becomes_dead_on: "immediate" (muere sola a la segunda consulta),
    "terminate" (solo tras terminate()), "kill" (solo tras kill()), o
    None (nunca muere sola, para forzar la ruta de excepción)."""

    def __init__(self, becomes_dead_on="immediate", returncode=0, stdin=None):
        self.becomes_dead_on = becomes_dead_on
        self.returncode = returncode
        self.stdin = stdin if stdin is not None else FakeStdin()
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []
        self._natural_calls = 0

    def poll(self):
        if self.becomes_dead_on == "immediate":
            self._natural_calls += 1
            return self.returncode if self._natural_calls >= 2 else None
        if self.becomes_dead_on == "terminate":
            return self.returncode if self.terminated else None
        if self.becomes_dead_on == "kill":
            return self.returncode if self.killed else None
        return None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        rc = self.poll()
        if rc is None:
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout)
        return rc


class FakeClock:
    """time.monotonic()/time.sleep() dobles: sleep() avanza el reloj en
    vez de bloquear de verdad, así _wait_until() puede "esperar" varios
    segundos simulados en microsegundos reales."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(recorder_module.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(recorder_module.time, "sleep", clock.sleep)
    return clock


# --------------------------------------------------------------------------
# _escape_drawtext (pura)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("Canal normal", "Canal normal"),
    ("Canal: Live", "Canal\\: Live"),
    ("It's Live", "It\\'s Live"),
    ("C:\\ruta", "C\\:\\\\ruta"),
])
def test_escape_drawtext_escapes_colon_quote_and_backslash(texto, esperado):
    assert _escape_drawtext(texto) == esperado


# --------------------------------------------------------------------------
# __init__
# --------------------------------------------------------------------------

def test_init_creates_the_requested_output_dir(tmp_path):
    destino = tmp_path / "grabaciones"
    rec = Recorder(str(destino))
    assert rec.output_dir == destino
    assert destino.is_dir()


def test_init_falls_back_to_app_data_dir_when_output_dir_is_invalid(monkeypatch, tmp_path):
    real_mkdir = Path.mkdir
    calls = {"n": 0}

    def _flaky_mkdir(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("ruta no válida en este equipo")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _flaky_mkdir)
    fallback_dir = tmp_path / "fallback"
    # __init__ hace `from core.config import get_app_data_dir` DENTRO del
    # except (import perezoso), así que hay que doblar el atributo en
    # core.config, no en core.recorder.
    import core.config as config_module
    monkeypatch.setattr(config_module, "get_app_data_dir", lambda: fallback_dir)

    rec = Recorder(str(tmp_path / "unidad_desconectada"))

    assert rec.output_dir == fallback_dir / "recordings"


# --------------------------------------------------------------------------
# ffmpeg_available()
# --------------------------------------------------------------------------

def test_ffmpeg_available_true_when_get_ffmpeg_exe_returns_a_path(monkeypatch):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "C:/ffmpeg/ffmpeg.exe")
    assert Recorder.ffmpeg_available() is True


def test_ffmpeg_available_false_when_get_ffmpeg_exe_returns_none(monkeypatch):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: None)
    assert Recorder.ffmpeg_available() is False


# --------------------------------------------------------------------------
# start()
# --------------------------------------------------------------------------

def _fake_popen(cmd_holder, process=None, kwargs_holder=None):
    def _popen(cmd, **kwargs):
        cmd_holder.append(cmd)
        if kwargs_holder is not None:
            kwargs_holder.append(kwargs)
        return process or FakeProcess()
    return _popen


def test_start_raises_if_a_recording_is_already_in_progress(tmp_path):
    rec = Recorder(str(tmp_path))
    rec.process = FakeProcess(becomes_dead_on=None)
    with pytest.raises(RuntimeError, match="Ya hay una grabación en curso"):
        rec.start("http://example.com/stream", "Canal")


@pytest.mark.parametrize("url", [
    "concat:file1.mp4|file2.mp4",
    "pipe:0",
    "subfile:start=0:1000:filename.mp4",
    "ftp://example.com/stream",
    "",
])
def test_start_rejects_non_http_urls(tmp_path, url):
    rec = Recorder(str(tmp_path))
    with pytest.raises(RuntimeError, match="http"):
        rec.start(url, "Canal")
    assert rec.process is None


def test_start_raises_when_ffmpeg_is_not_available(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: None)
    rec = Recorder(str(tmp_path))
    with pytest.raises(RuntimeError, match="ffmpeg"):
        rec.start("http://example.com/stream", "Canal")


def test_start_builds_a_radio_command_without_watermark_or_video(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    cmds = []
    monkeypatch.setattr(recorder_module.subprocess, "Popen", _fake_popen(cmds))

    rec = Recorder(str(tmp_path))
    resultado = rec.start("http://example.com/radio", "Radio Ejemplo", kind="radio")

    assert resultado.suffix == ".mka"
    cmd = cmds[0]
    assert "-vn" in cmd
    assert "-vf" not in cmd
    assert cmd[-1] == str(resultado)


def test_start_builds_a_tv_command_with_watermark_when_font_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    monkeypatch.setattr(recorder_module.os.path, "exists", lambda path: True)
    cmds, popen_kwargs = [], []
    monkeypatch.setattr(recorder_module.subprocess, "Popen", _fake_popen(cmds, kwargs_holder=popen_kwargs))

    rec = Recorder(str(tmp_path))
    resultado = rec.start("http://example.com/tv", "Canal: Live", kind="tv")

    assert resultado.suffix == ".mp4"
    cmd = cmds[0]
    assert "-vf" in cmd
    drawtext = cmd[cmd.index("-vf") + 1]
    assert "Canal\\: Live" in drawtext
    assert "libx264" in cmd
    assert popen_kwargs[0]["cwd"] == recorder_module._WATERMARK_FONT_DIR


def test_start_builds_a_tv_command_without_watermark_when_font_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    monkeypatch.setattr(recorder_module.os.path, "exists", lambda path: False)
    cmds, popen_kwargs = [], []
    monkeypatch.setattr(recorder_module.subprocess, "Popen", _fake_popen(cmds, kwargs_holder=popen_kwargs))

    rec = Recorder(str(tmp_path))
    rec.start("http://example.com/tv", "Canal", kind="tv")

    cmd = cmds[0]
    assert "-vf" not in cmd
    assert "copy" in cmd
    assert popen_kwargs[0]["cwd"] is None


def test_start_sanitizes_the_channel_name_for_the_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    cmds = []
    monkeypatch.setattr(recorder_module.subprocess, "Popen", _fake_popen(cmds))

    rec = Recorder(str(tmp_path))
    resultado = rec.start("http://example.com/radio", "Canal/Raro:Test\\..", kind="radio")

    assert "/" not in resultado.name
    assert "\\" not in resultado.name
    assert ":" not in resultado.name
    assert resultado.parent == tmp_path


def test_start_raises_and_cleans_up_when_popen_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(recorder_module, "get_ffmpeg_exe", lambda: "ffmpeg.exe")

    def _raise(cmd, **kwargs):
        raise OSError("no se pudo lanzar ffmpeg")

    monkeypatch.setattr(recorder_module.subprocess, "Popen", _raise)

    rec = Recorder(str(tmp_path))
    with pytest.raises(RuntimeError, match="No se pudo iniciar la grabación"):
        rec.start("http://example.com/radio", "Canal", kind="radio")

    assert rec.current_file is None
    assert rec._log_fh is None


# --------------------------------------------------------------------------
# check_early_failure()
# --------------------------------------------------------------------------

def test_check_early_failure_returns_none_when_no_process():
    rec = Recorder.__new__(Recorder)
    rec.process = None
    assert rec.check_early_failure() is None


def test_check_early_failure_returns_none_while_process_is_alive(tmp_path):
    rec = Recorder(str(tmp_path))
    rec.process = FakeProcess(becomes_dead_on=None)
    assert rec.check_early_failure() is None
    assert rec.process is not None


def test_check_early_failure_resets_state_and_reports_log_tail_when_process_died(tmp_path):
    rec = Recorder(str(tmp_path))
    rec.process = FakeProcess(becomes_dead_on="terminate")
    rec.process.terminated = True  # ya muerto desde el primer poll()
    rec.current_log = tmp_path / "salida.log"
    rec.current_log.write_text("Error: servidor rechazó la conexión", encoding="utf-8")

    mensaje = rec.check_early_failure()

    assert "ffmpeg se cerró" in mensaje
    assert "servidor rechazó la conexión" in mensaje
    assert rec.process is None
    assert rec.is_recording is False


# --------------------------------------------------------------------------
# stop()
# --------------------------------------------------------------------------

def test_stop_returns_none_and_false_when_nothing_is_recording():
    rec = Recorder.__new__(Recorder)
    rec.process = None
    rec.current_file = None
    assert rec.stop() == (None, False)


def test_stop_writes_q_waits_gracefully_and_reports_ok_for_a_valid_file(tmp_path):
    fake = FakeProcess(becomes_dead_on="immediate")
    rec = Recorder.__new__(Recorder)
    rec.process = fake
    rec.current_file = tmp_path / "grabacion.mp4"
    rec.current_file.write_bytes(b"0" * 5000)
    rec.current_log = None
    rec._log_fh = None

    archivo, ok = rec.stop()

    assert archivo == tmp_path / "grabacion.mp4"
    assert ok is True
    assert fake.stdin.written == b"q"
    assert fake.terminated is False
    assert fake.killed is False
    assert rec.is_recording is False


def test_stop_reports_not_ok_when_the_file_is_too_small(tmp_path):
    rec = Recorder.__new__(Recorder)
    rec.process = FakeProcess(becomes_dead_on="immediate")
    rec.current_file = tmp_path / "vacio.mp4"
    rec.current_file.write_bytes(b"0" * 10)  # por debajo de _MIN_VALID_SIZE_BYTES
    rec.current_log = None
    rec._log_fh = None

    _archivo, ok = rec.stop()

    assert ok is False


def test_stop_reports_not_ok_when_the_file_was_never_written(tmp_path):
    rec = Recorder.__new__(Recorder)
    rec.process = FakeProcess(becomes_dead_on="immediate")
    rec.current_file = tmp_path / "nunca_escrito.mp4"
    rec.current_log = None
    rec._log_fh = None

    _archivo, ok = rec.stop()

    assert ok is False


def test_stop_escalates_to_terminate_when_graceful_stop_does_not_respond(tmp_path):
    fake = FakeProcess(becomes_dead_on="terminate")
    rec = Recorder.__new__(Recorder)
    rec.process = fake
    rec.current_file = tmp_path / "grabacion.mp4"
    rec.current_file.write_bytes(b"0" * 5000)
    rec.current_log = None
    rec._log_fh = None

    rec.stop()

    assert fake.terminated is True
    assert fake.killed is False
    assert rec.process is None


def test_stop_escalates_to_kill_when_terminate_does_not_respond(tmp_path):
    fake = FakeProcess(becomes_dead_on="kill")
    rec = Recorder.__new__(Recorder)
    rec.process = fake
    rec.current_file = tmp_path / "grabacion.mp4"
    rec.current_file.write_bytes(b"0" * 5000)
    rec.current_log = None
    rec._log_fh = None

    rec.stop()

    assert fake.terminated is True
    assert fake.killed is True


def test_stop_tolerates_stdin_write_failure(tmp_path):
    rec = Recorder.__new__(Recorder)
    rec.process = FakeProcess(becomes_dead_on="immediate", stdin=FakeStdin(raise_on_write=True))
    esperado = tmp_path / "grabacion.mp4"
    rec.current_file = esperado
    esperado.write_bytes(b"0" * 5000)
    rec.current_log = None
    rec._log_fh = None

    archivo, ok = rec.stop()

    assert ok is True
    assert archivo == esperado


def test_stop_falls_back_to_kill_when_wait_until_raises_unexpectedly(tmp_path, monkeypatch):
    fake = FakeProcess(becomes_dead_on="kill")
    rec = Recorder.__new__(Recorder)
    rec.process = fake
    rec.current_file = tmp_path / "grabacion.mp4"
    rec.current_file.write_bytes(b"0" * 5000)
    rec.current_log = None
    rec._log_fh = None

    def _boom(*_a, **_k):
        raise RuntimeError("fallo inesperado esperando al proceso")

    monkeypatch.setattr(rec, "_wait_until", _boom)

    archivo, ok = rec.stop()

    assert fake.killed is True
    assert rec.process is None
    assert archivo == tmp_path / "grabacion.mp4"
    assert ok is True


# --------------------------------------------------------------------------
# is_recording
# --------------------------------------------------------------------------

def test_is_recording_reflects_process_state(tmp_path):
    rec = Recorder(str(tmp_path))
    assert rec.is_recording is False
    rec.process = FakeProcess()
    assert rec.is_recording is True
