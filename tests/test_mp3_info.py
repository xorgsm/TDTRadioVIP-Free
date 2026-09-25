"""
Cobertura de core/mp3_info.py: lectura de duración/tags parseando la
salida de 'ffmpeg -i', el comando de escritura de tags, y el ciclo de
vida de Mp3TagWriteWorker, con ffmpeg simulado (tests/ffmpeg_fakes.py).

Mp3TagWriteWorker es un QThread, pero se prueba llamando a .run()
directamente (nunca .start()), igual que el resto del proyecto.
"""
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import mp3_info
from core.mp3_info import Mp3TagWriteWorker, build_write_tags_command
from tests.ffmpeg_fakes import FakePopenFactory

PROBE_OUTPUT = """\
Input #0, mp3, from 'tema.mp3':
  Metadata:
    title           : Canción: versión larga
    artist          : Alguien
    TRACK           : 3/12
  Duration: 01:02:03.50, start: 0.025057, bitrate: 320 kb/s
  Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp, 320 kb/s
    Metadata:
      encoder         : LAME3.100
At least one output file must be specified
"""


# --------------------------------------------------------------------------
# _parse_probe_output() / probe()
# --------------------------------------------------------------------------

def test_parse_probe_output_reads_duration_and_format_tags_only():
    info = mp3_info._parse_probe_output(PROBE_OUTPUT)

    assert info["duration_ms"] == (3600 + 2 * 60 + 3.5) * 1000
    assert info["tags"] == {
        "title": "Canción: versión larga",
        "artist": "Alguien",
        "track": "3/12",
    }


def test_parse_probe_output_without_info_returns_empty():
    assert mp3_info._parse_probe_output("tema.mp3: No such file or directory") == {
        "duration_ms": None, "tags": {},
    }


def test_probe_runs_ffmpeg_and_parses_stderr(monkeypatch):
    monkeypatch.setattr(mp3_info, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    run = Mock(return_value=SimpleNamespace(stderr=PROBE_OUTPUT))
    monkeypatch.setattr(mp3_info.subprocess, "run", run)

    info = mp3_info.probe("tema.mp3")

    assert info["tags"]["artist"] == "Alguien"
    assert run.call_args.args[0] == ["ffmpeg.exe", "-hide_banner", "-i", "tema.mp3"]
    assert run.call_args.kwargs["timeout"] == mp3_info._PROBE_TIMEOUT_SECONDS


@pytest.mark.parametrize("error", [OSError("no arranca"), subprocess.TimeoutExpired("ffmpeg", 15)])
def test_probe_returns_empty_on_ffmpeg_error(monkeypatch, error):
    monkeypatch.setattr(mp3_info, "get_ffmpeg_exe", lambda: "ffmpeg.exe")
    monkeypatch.setattr(mp3_info.subprocess, "run", Mock(side_effect=error))

    assert mp3_info.probe("tema.mp3") == {"duration_ms": None, "tags": {}}


def test_probe_without_ffmpeg_returns_empty(monkeypatch):
    monkeypatch.setattr(mp3_info, "get_ffmpeg_exe", lambda: None)

    assert mp3_info.probe("tema.mp3") == {"duration_ms": None, "tags": {}}


# --------------------------------------------------------------------------
# build_write_tags_command()
# --------------------------------------------------------------------------

def test_build_write_tags_command_copies_streams_and_sets_every_tag():
    cmd = build_write_tags_command("ffmpeg.exe", "in.mp3", "tmp.mp3", {"title": "Hola", "genre": "Rock"})

    assert cmd[cmd.index("-c") + 1] == "copy"
    metadatos = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-metadata"]
    assert metadatos == ["title=Hola", "artist=", "album=", "date=", "genre=Rock", "track="]
    assert cmd[-1] == "tmp.mp3"


# --------------------------------------------------------------------------
# Mp3TagWriteWorker
# --------------------------------------------------------------------------

@pytest.fixture
def fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(mp3_info, "get_ffmpeg_exe", lambda: "ffmpeg.exe")

    def install(**process_kwargs):
        factory = FakePopenFactory(**process_kwargs)
        monkeypatch.setattr(mp3_info.subprocess, "Popen", factory)
        return factory
    return install


@pytest.fixture
def mp3_file(tmp_path):
    ruta = tmp_path / "tema.mp3"
    ruta.write_bytes(b"ORIGINAL")
    return ruta


def _record_signals(worker):
    eventos = []
    worker.finished_ok.connect(lambda p: eventos.append(("ok", p)))
    worker.failed.connect(lambda m: eventos.append(("failed", m)))
    return eventos


def test_worker_replaces_original_with_retagged_file(fake_ffmpeg, mp3_file):
    factory = fake_ffmpeg(output_bytes=b"RETAGGED")
    worker = Mp3TagWriteWorker(str(mp3_file), {"title": "Nuevo"})
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("ok", str(mp3_file))]
    assert mp3_file.read_bytes() == b"RETAGGED"
    assert factory.processes[0].cmd[-1].endswith(".mp3")
    assert os.listdir(mp3_file.parent) == ["tema.mp3"]


def test_worker_failure_keeps_original_and_reports_stderr_tail(fake_ffmpeg, mp3_file):
    fake_ffmpeg(returncode=1, stderr_text="a\nb\nc\nInvalid data found\n")
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("failed", "b\nc\nInvalid data found")]
    assert mp3_file.read_bytes() == b"ORIGINAL"
    assert os.listdir(mp3_file.parent) == ["tema.mp3"]


def test_worker_without_ffmpeg_fails(monkeypatch, mp3_file):
    monkeypatch.setattr(mp3_info, "get_ffmpeg_exe", lambda: None)
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[0][0] == "failed"


def test_worker_reports_unwritable_folder_instead_of_dying(fake_ffmpeg, monkeypatch, mp3_file):
    """MP3 en una carpeta sin permiso de escritura (USB protegido, carpeta
    de sistema...): mkstemp falla, y el worker tiene que emitir failed --
    si no, el panel de tags se queda con "Guardar" desactivado para siempre."""
    factory = fake_ffmpeg()
    monkeypatch.setattr(
        mp3_info.tempfile, "mkstemp", Mock(side_effect=PermissionError("solo lectura"))
    )
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)

    worker.run()

    assert len(eventos) == 1 and eventos[0][0] == "failed" and "solo lectura" in eventos[0][1]
    assert factory.processes == []
    assert mp3_file.read_bytes() == b"ORIGINAL"


def test_worker_reports_popen_error_and_cleans_up(fake_ffmpeg, monkeypatch, mp3_file):
    fake_ffmpeg()
    monkeypatch.setattr(mp3_info.subprocess, "Popen", Mock(side_effect=OSError("no arranca")))
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("failed", "no arranca")]
    assert os.listdir(mp3_file.parent) == ["tema.mp3"]


def test_worker_reports_rename_failure_and_keeps_original(fake_ffmpeg, monkeypatch, mp3_file):
    fake_ffmpeg()
    monkeypatch.setattr(mp3_info.os, "replace", Mock(side_effect=OSError("en uso")))
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[0][0] == "failed" and "en uso" in eventos[0][1]
    assert mp3_file.read_bytes() == b"ORIGINAL"
    assert os.listdir(mp3_file.parent) == ["tema.mp3"]


def test_cancel_terminates_ffmpeg_and_keeps_original(fake_ffmpeg, mp3_file):
    factory = fake_ffmpeg()
    worker = Mp3TagWriteWorker(str(mp3_file), {})
    eventos = _record_signals(worker)
    factory.on_create = lambda proceso: worker.cancel()

    worker.run()

    assert factory.processes[0].terminated
    assert eventos == [("failed", "__cancelled__")]
    assert mp3_file.read_bytes() == b"ORIGINAL"
    assert os.listdir(mp3_file.parent) == ["tema.mp3"]
