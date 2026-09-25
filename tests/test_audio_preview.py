"""
Cobertura de player/audio_preview.py (vista previa de audio del editor de
MP3) con el módulo `vlc` simulado de tests/vlc_fakes.py -- no hace falta
VLC instalado.

AudioPreviewPlayer es un QObject que reenvía en cola las señales de los
callbacks de libVLC: se procesan los eventos pendientes de la
QApplication antes de comprobarlas.
"""
import pytest
from PySide6.QtWidgets import QApplication

from player import audio_preview
from player.audio_preview import AudioPreviewPlayer
from tests.vlc_fakes import FakeInstance, FakeMediaPlayer, fake_vlc_module


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_vlc(monkeypatch):
    modulo = fake_vlc_module()
    monkeypatch.setattr(audio_preview, "vlc", modulo)
    return modulo


@pytest.fixture
def preview(qapp, fake_vlc):
    reproductor = AudioPreviewPlayer()
    yield reproductor
    reproductor.release()


def _signals(reproductor):
    eventos = []
    reproductor.error_occurred.connect(lambda m: eventos.append(("error", m)))
    reproductor.end_reached.connect(lambda: eventos.append(("end",)))
    return eventos


def _player(fake_vlc) -> FakeMediaPlayer:
    return fake_vlc.instances[0].players[0]


# --------------------------------------------------------------------------
# Arranque
# --------------------------------------------------------------------------

def test_without_libvlc_is_unavailable_and_load_reports_error(qapp, monkeypatch):
    monkeypatch.setattr(audio_preview, "vlc", None)
    reproductor = AudioPreviewPlayer()
    eventos = _signals(reproductor)

    assert reproductor.load("tema.mp3") is False

    assert not reproductor.disponible
    assert eventos[0][0] == "error"
    # Sin reproductor, todo lo demás no hace nada y devuelve valores neutros.
    reproductor.play()
    reproductor.pause()
    reproductor.stop()
    reproductor.set_time_ms(1000)
    assert (reproductor.is_playing(), reproductor.get_time_ms(), reproductor.get_length_ms()) == (False, 0, 0)
    reproductor.release()


def test_startup_attaches_error_and_end_events(preview, fake_vlc):
    assert preview.disponible
    assert set(_player(fake_vlc).events.attached) == {"error", "end"}


def test_startup_failure_releases_partial_objects(qapp, fake_vlc, monkeypatch):
    def event_manager_roto(self):
        raise OSError("libvlc rota")
    monkeypatch.setattr(FakeMediaPlayer, "event_manager", event_manager_roto)

    reproductor = AudioPreviewPlayer()

    instancia = fake_vlc.instances[0]
    assert not reproductor.disponible
    assert instancia.players[0].released and instancia.released


# --------------------------------------------------------------------------
# load()
# --------------------------------------------------------------------------

def test_load_sets_media_and_releases_previous_one(preview, fake_vlc):
    assert preview.load("uno.mp3") is True
    assert preview.load("dos.mp3") is True

    primero, segundo = fake_vlc.instances[0].medias
    assert primero.released and not segundo.released
    assert _player(fake_vlc).media is segundo


def test_load_failure_in_media_new_reports_error(preview, fake_vlc, monkeypatch):
    eventos = _signals(preview)
    monkeypatch.setattr(FakeInstance, "media_new", lambda self, path: (_ for _ in ()).throw(OSError("ruta")))

    assert preview.load("roto.mp3") is False
    assert eventos == [("error", "No se pudo cargar el archivo para la vista previa.")]


def test_load_failure_in_set_media_releases_new_media(preview, fake_vlc, monkeypatch):
    """Si libVLC rechaza el medio ya creado, ese Media no puede quedarse sin
    liberar: cada intento fallido sería una fuga en libVLC."""
    preview.load("bueno.mp3")
    eventos = _signals(preview)

    def set_media_roto(self, media):
        raise OSError("ctypes")
    monkeypatch.setattr(FakeMediaPlayer, "set_media", set_media_roto)

    assert preview.load("roto.mp3") is False

    bueno, roto = fake_vlc.instances[0].medias
    assert roto.released
    assert not bueno.released  # el que sigue cargado no se toca
    assert eventos[-1][0] == "error"


# --------------------------------------------------------------------------
# Control y posición
# --------------------------------------------------------------------------

def test_play_pause_stop(preview, fake_vlc):
    preview.load("tema.mp3")

    preview.play()
    assert preview.is_playing()
    preview.pause()
    assert not preview.is_playing()
    preview.play()
    preview.stop()
    assert not preview.is_playing()


def test_time_and_length_are_never_negative(preview, fake_vlc):
    mp = _player(fake_vlc)
    mp.time, mp.length = -1, -1
    assert (preview.get_time_ms(), preview.get_length_ms()) == (0, 0)

    preview.set_time_ms(-500)
    assert mp.time == 0
    preview.set_time_ms(1234.9)
    assert mp.time == 1234


# --------------------------------------------------------------------------
# Callbacks de libVLC -> señales públicas (en cola)
# --------------------------------------------------------------------------

def test_libvlc_callbacks_are_forwarded_as_queued_signals(preview, fake_vlc, qapp):
    eventos = _signals(preview)
    mp = _player(fake_vlc)

    mp.events.attached["error"](None)
    mp.events.attached["end"](None)
    assert eventos == []
    qapp.processEvents()

    assert eventos == [("error", "Error al reproducir el archivo de vista previa."), ("end",)]


# --------------------------------------------------------------------------
# Cierre
# --------------------------------------------------------------------------

def test_release_frees_everything(qapp, fake_vlc):
    reproductor = AudioPreviewPlayer()
    reproductor.load("tema.mp3")
    instancia = fake_vlc.instances[0]

    reproductor.release()

    assert instancia.medias[0].released
    assert instancia.players[0].released
    assert instancia.released
    assert not reproductor.disponible


def test_release_detaches_events_before_freeing_player(qapp, fake_vlc):
    """El panel del editor destruye este QObject al cerrarse: un callback
    tardío de libVLC no puede llegar ya a un objeto Qt destruido."""
    reproductor = AudioPreviewPlayer()
    mp = fake_vlc.instances[0].players[0]

    reproductor.release()

    assert set(mp.events.detached) == {"error", "end"}


def test_release_still_frees_player_when_stop_fails(qapp, fake_vlc):
    reproductor = AudioPreviewPlayer()
    instancia = fake_vlc.instances[0]
    instancia.players[0].stop_error = OSError("libvlc ocupada")

    reproductor.release()

    assert instancia.players[0].released
    assert instancia.released
