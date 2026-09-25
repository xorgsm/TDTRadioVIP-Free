"""
Cobertura de core/audio_editor.py: construcción del comando ffmpeg de
unión con crossfade, validación de marcas, estimación de duración,
lectura del progreso de ffmpeg y el ciclo de vida de AudioEditWorker, con
ffmpeg simulado (tests/ffmpeg_fakes.py).

AudioEditWorker es un QThread, pero se prueba llamando a .run()
directamente (nunca .start()), igual que el resto del proyecto.
"""
import os
from unittest.mock import Mock

import pytest

from core import audio_editor
from core.audio_editor import (
    AudioEditWorker, Segment, build_join_command, estimated_output_seconds,
    validate_segments,
)
from tests.ffmpeg_fakes import FakePopenFactory


# --------------------------------------------------------------------------
# build_join_command()
# --------------------------------------------------------------------------

def test_build_join_command_requires_segments():
    with pytest.raises(ValueError):
        build_join_command([], 2.0, "out.mp3", "ffmpeg.exe")


def test_build_join_command_single_segment_has_no_crossfade():
    cmd = build_join_command([Segment("a.mp3")], 2.0, "out.mp3", "ffmpeg.exe")

    filtro = cmd[cmd.index("-filter_complex") + 1]
    assert "acrossfade" not in filtro
    assert filtro.startswith("[0:a]loudnorm")
    assert cmd[cmd.index("-map") + 1] == "[n0]"
    assert "-ss" not in cmd and "-t" not in cmd
    assert cmd[-1] == "out.mp3"


def test_build_join_command_trims_inputs_with_seek_and_duration():
    cmd = build_join_command(
        [Segment("a.mp3", start_ms=1500, end_ms=4000), Segment("b.mp3", end_ms=3000)],
        2.0, "out.mp3", "ffmpeg.exe",
    )

    i_a = cmd.index("a.mp3")
    assert cmd[i_a - 5:i_a + 1] == ["-ss", "1.500", "-t", "2.500", "-i", "a.mp3"]
    i_b = cmd.index("b.mp3")
    assert cmd[i_b - 3:i_b + 1] == ["-t", "3.000", "-i", "b.mp3"]


def test_build_join_command_chains_crossfades_in_order():
    segmentos = [Segment("a.mp3"), Segment("b.mp3"), Segment("c.mp3")]

    cmd = build_join_command(segmentos, 3.0, "out.mp3", "ffmpeg.exe")

    filtro = cmd[cmd.index("-filter_complex") + 1]
    assert "[n0][n1]acrossfade=d=3.0:c1=tri:c2=tri[cf1]" in filtro
    assert "[cf1][n2]acrossfade=d=3.0:c1=tri:c2=tri[cf2]" in filtro
    assert cmd[cmd.index("-map") + 1] == "[cf2]"
    assert cmd[cmd.index("-progress") + 1] == "pipe:1"


# --------------------------------------------------------------------------
# validate_segments() / estimated_output_seconds() / _parse_out_time_ms()
# --------------------------------------------------------------------------

def test_validate_segments_rejects_end_before_or_equal_start():
    assert validate_segments([Segment("x/a.mp3", 1000, 5000)]) is None
    assert validate_segments([Segment("a.mp3", 5000, None)]) is None
    mensaje = validate_segments([Segment("x/tema.mp3", 5000, 5000)])
    assert mensaje is not None and "tema.mp3" in mensaje


def test_estimated_output_subtracts_one_fade_per_join():
    segmentos = [Segment("a", 0, 10_000), Segment("b", 2_000, 12_000), Segment("c")]

    assert estimated_output_seconds(segmentos, 2.0) == pytest.approx(16.0)
    assert estimated_output_seconds([Segment("a", 0, 1_000), Segment("b", 0, 1_000)], 5.0) == 0.0


@pytest.mark.parametrize("linea, esperado", [
    ("out_time_ms=12345000", 12345),
    ("out_time_us=2000000", 2000),
    ("out_time_ms=N/A", None),
    ("progress=continue", None),
])
def test_parse_out_time_ms(linea, esperado):
    assert audio_editor._parse_out_time_ms(linea) == esperado


# --------------------------------------------------------------------------
# AudioEditWorker
# --------------------------------------------------------------------------

@pytest.fixture
def fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(audio_editor, "get_ffmpeg_exe", lambda: "ffmpeg.exe")

    def install(**process_kwargs):
        factory = FakePopenFactory(**process_kwargs)
        monkeypatch.setattr(audio_editor.subprocess, "Popen", factory)
        return factory
    return install


def _record_signals(worker):
    eventos = []
    worker.progress.connect(lambda f: eventos.append(("progress", f)))
    worker.finished_ok.connect(lambda p: eventos.append(("ok", p)))
    worker.failed.connect(lambda m: eventos.append(("failed", m)))
    return eventos


def test_worker_joins_reports_progress_and_saves_output(fake_ffmpeg, tmp_path):
    fake_ffmpeg(stdout_lines=["out_time_ms=5000000\n", "progress=continue\n", "out_time_ms=20000000\n"])
    salida = tmp_path / "mix.mp3"
    worker = AudioEditWorker([Segment("a.mp3"), Segment("b.mp3")], 2.0, str(salida),
                             expected_total_ms=10_000)
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("progress", 0.5), ("progress", 1.0), ("progress", 1.0), ("ok", str(salida))]
    assert salida.read_bytes() == b"MP3DATA"
    assert os.listdir(tmp_path) == ["mix.mp3"]


def test_worker_without_expected_total_never_emits_partial_progress(fake_ffmpeg, tmp_path):
    fake_ffmpeg(stdout_lines=["out_time_ms=5000000\n"])
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("progress", 1.0), ("ok", str(tmp_path / "mix.mp3"))]


def test_worker_failure_reports_last_stderr_lines_and_cleans_up(fake_ffmpeg, tmp_path, monkeypatch):
    factory = fake_ffmpeg(returncode=1)

    def escribe_log(proceso):
        # El worker pasa un archivo abierto como stderr; lo simulamos
        # escribiendo en el .log que corresponde al temporal de salida.
        with open(proceso.cmd[-1] + ".log", "w", encoding="utf-8") as fh:
            fh.write("linea 1\nlinea 2\n\nlinea 3\nError: acrossfade falló\n")
    factory.on_create = escribe_log
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("failed", "linea 2\nlinea 3\nError: acrossfade falló")]
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize("segmentos, esperado", [
    ([], "al menos un archivo"),
    ([Segment("a.mp3", 5000, 1000)], "anterior"),
])
def test_worker_rejects_invalid_input_without_running_ffmpeg(fake_ffmpeg, tmp_path, segmentos, esperado):
    factory = fake_ffmpeg()
    worker = AudioEditWorker(segmentos, 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert len(eventos) == 1 and eventos[0][0] == "failed" and esperado in eventos[0][1]
    assert factory.processes == []


def test_worker_without_ffmpeg_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(audio_editor, "get_ffmpeg_exe", lambda: None)
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[0][0] == "failed" and "ffmpeg" in eventos[0][1]


def test_worker_reports_unwritable_dest_dir_instead_of_dying(fake_ffmpeg, monkeypatch, tmp_path):
    factory = fake_ffmpeg()
    monkeypatch.setattr(
        audio_editor.tempfile, "mkstemp", Mock(side_effect=PermissionError("solo lectura"))
    )
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert len(eventos) == 1 and eventos[0][0] == "failed" and "solo lectura" in eventos[0][1]
    assert factory.processes == []


def test_worker_reports_popen_error_and_cleans_up(fake_ffmpeg, monkeypatch, tmp_path):
    fake_ffmpeg()
    monkeypatch.setattr(audio_editor.subprocess, "Popen", Mock(side_effect=OSError("no arranca")))
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos == [("failed", "no arranca")]
    assert os.listdir(tmp_path) == []


def test_worker_reports_rename_failure(fake_ffmpeg, monkeypatch, tmp_path):
    fake_ffmpeg()
    monkeypatch.setattr(audio_editor.os, "replace", Mock(side_effect=OSError("en uso")))
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"))
    eventos = _record_signals(worker)

    worker.run()

    assert eventos[-1][0] == "failed" and "en uso" in eventos[-1][1]
    assert os.listdir(tmp_path) == []


def test_cancel_terminates_ffmpeg_and_reports_cancelled(fake_ffmpeg, tmp_path):
    factory = fake_ffmpeg(stdout_lines=["out_time_ms=5000000\n"])
    worker = AudioEditWorker([Segment("a.mp3")], 2.0, str(tmp_path / "mix.mp3"),
                             expected_total_ms=10_000)
    eventos = _record_signals(worker)
    factory.on_create = lambda proceso: worker.cancel()

    worker.run()

    assert factory.processes[0].terminated
    assert eventos == [("failed", "__cancelled__")]
    assert os.listdir(tmp_path) == []
