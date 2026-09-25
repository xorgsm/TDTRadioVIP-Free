"""
Cobertura de core/audio_converter.py: nombre de salida sin sobrescribir,
comando ffmpeg, y el ciclo de vida de AudioConvertWorker (éxito, fallo
por archivo, cancelación, sin ffmpeg, carpeta de destino no escribible),
con ffmpeg simulado (tests/ffmpeg_fakes.py).

AudioConvertWorker es un QThread, pero se prueba llamando a .run()
directamente (nunca .start()), igual que el resto del proyecto.
"""
import os
from unittest.mock import Mock

import pytest

from core import audio_converter
from core.audio_converter import AudioConvertWorker, build_output_path
from tests.ffmpeg_fakes import FakePopenFactory


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(audio_converter, "get_ffmpeg_exe", lambda: "ffmpeg.exe")

    def install(**process_kwargs):
        factory = FakePopenFactory(**process_kwargs)
        monkeypatch.setattr(audio_converter.subprocess, "Popen", factory)
        return factory
    return install


def _record_signals(worker):
    eventos = []
    worker.progress.connect(lambda i, t, n: eventos.append(("progress", i, t, n)))
    worker.file_done.connect(lambda i, o: eventos.append(("done", i, o)))
    worker.file_failed.connect(lambda i, m: eventos.append(("failed", i, m)))
    worker.finished_all.connect(lambda: eventos.append(("finished_all",)))
    worker.cancelled.connect(lambda: eventos.append(("cancelled",)))
    return eventos


def _leftover_temps(folder):
    return [n for n in os.listdir(folder) if n.startswith("tdtvip_conv_")]


# --------------------------------------------------------------------------
# build_output_path() / _build_command()
# --------------------------------------------------------------------------

def test_build_output_path_uses_input_name_with_mp3_extension(tmp_path):
    assert build_output_path("C:/musica/tema.flac", str(tmp_path)) == str(tmp_path / "tema.mp3")


def test_build_output_path_never_overwrites_existing_files(tmp_path):
    (tmp_path / "tema.mp3").write_bytes(b"")
    (tmp_path / "tema (2).mp3").write_bytes(b"")

    assert build_output_path("tema.wav", str(tmp_path)) == str(tmp_path / "tema (3).mp3")


def test_build_command_drops_video_and_encodes_320k_mp3():
    cmd = audio_converter._build_command("ffmpeg.exe", "in.webm", "out.mp3")

    assert cmd[0] == "ffmpeg.exe"
    assert cmd[cmd.index("-i") + 1] == "in.webm"
    assert "-vn" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "libmp3lame"
    assert cmd[cmd.index("-b:a") + 1] == "320k"
    assert cmd[-1] == "out.mp3"


# --------------------------------------------------------------------------
# AudioConvertWorker
# --------------------------------------------------------------------------

def test_worker_converts_every_file_and_finishes(fake_ffmpeg, tmp_path):
    factory = fake_ffmpeg()
    dest = tmp_path / "salida"
    worker = AudioConvertWorker(["a.wav", "b.flac"], str(dest))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [
        ("progress", 0, 2, "a.wav"),
        ("done", "a.wav", str(dest / "a.mp3")),
        ("progress", 1, 2, "b.flac"),
        ("done", "b.flac", str(dest / "b.mp3")),
        ("finished_all",),
    ]
    assert (dest / "a.mp3").read_bytes() == b"MP3DATA"
    assert len(factory.processes) == 2
    assert _leftover_temps(dest) == []


def test_worker_reports_ffmpeg_failure_and_cleans_temp(fake_ffmpeg, tmp_path):
    fake_ffmpeg(returncode=1)
    worker = AudioConvertWorker(["roto.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.run()

    assert ("failed", "roto.wav", "ffmpeg no pudo convertir el archivo.") in eventos
    assert eventos[-1] == ("finished_all",)
    assert os.listdir(tmp_path) == []


def test_worker_reports_popen_error_and_continues_with_next_file(fake_ffmpeg, tmp_path, monkeypatch):
    factory = fake_ffmpeg()
    llamadas = []

    def popen(cmd, **kwargs):
        llamadas.append(cmd)
        if len(llamadas) == 1:
            raise OSError("acceso denegado")
        return factory(cmd, **kwargs)
    monkeypatch.setattr(audio_converter.subprocess, "Popen", popen)
    worker = AudioConvertWorker(["a.wav", "b.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.run()

    assert ("failed", "a.wav", "acceso denegado") in eventos
    assert ("done", "b.wav", str(tmp_path / "b.mp3")) in eventos
    assert eventos[-1] == ("finished_all",)
    assert _leftover_temps(tmp_path) == []


def test_worker_without_ffmpeg_fails_every_file(monkeypatch, tmp_path):
    monkeypatch.setattr(audio_converter, "get_ffmpeg_exe", lambda: None)
    worker = AudioConvertWorker(["a.wav", "b.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.run()

    assert [e[0] for e in eventos] == ["failed", "failed", "finished_all"]


def test_worker_fails_every_file_when_dest_dir_cannot_be_created(fake_ffmpeg, monkeypatch, tmp_path):
    fake_ffmpeg()
    monkeypatch.setattr(audio_converter.os, "makedirs", Mock(side_effect=OSError("sin permiso")))
    worker = AudioConvertWorker(["a.wav"], str(tmp_path / "x"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[0][0] == "failed" and "sin permiso" in eventos[0][2]
    assert eventos[-1] == ("finished_all",)


def test_worker_reports_unwritable_dest_dir_instead_of_dying(fake_ffmpeg, monkeypatch, tmp_path):
    """La carpeta existe (makedirs no falla) pero no admite crear archivos:
    el lote tiene que terminar con file_failed + finished_all, no con una
    excepción que mate el hilo sin avisar a la UI."""
    factory = fake_ffmpeg()
    monkeypatch.setattr(
        audio_converter.tempfile, "mkstemp", Mock(side_effect=PermissionError("solo lectura"))
    )
    worker = AudioConvertWorker(["a.wav", "b.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.run()

    fallos = [e for e in eventos if e[0] == "failed"]
    assert [f[1] for f in fallos] == ["a.wav", "b.wav"]
    assert "solo lectura" in fallos[0][2]
    assert eventos[-1] == ("finished_all",)
    assert factory.processes == []


def test_worker_reports_rename_failure_and_cleans_temp(fake_ffmpeg, monkeypatch, tmp_path):
    fake_ffmpeg()
    monkeypatch.setattr(audio_converter.os, "replace", Mock(side_effect=OSError("en uso")))
    worker = AudioConvertWorker(["a.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[1][0] == "failed" and "en uso" in eventos[1][2]
    assert _leftover_temps(tmp_path) == []


def test_cancel_during_conversion_terminates_ffmpeg_and_stops_batch(fake_ffmpeg, tmp_path):
    factory = fake_ffmpeg()
    worker = AudioConvertWorker(["a.wav", "b.wav"], str(tmp_path))
    eventos = _record_signals(worker)
    factory.on_create = lambda proceso: worker.cancel()

    worker.run()

    assert len(factory.processes) == 1
    assert factory.processes[0].terminated
    assert eventos[-1] == ("cancelled",)
    assert not any(e[0] in ("done", "finished_all") for e in eventos)
    assert os.listdir(tmp_path) == []


def test_cancel_before_start_emits_cancelled_without_running_ffmpeg(fake_ffmpeg, tmp_path):
    factory = fake_ffmpeg()
    worker = AudioConvertWorker(["a.wav"], str(tmp_path))
    eventos = _record_signals(worker)

    worker.cancel()
    worker.run()

    assert eventos == [("cancelled",)]
    assert factory.processes == []
