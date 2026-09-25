"""
Cobertura de player/vlc_player.py con un módulo `vlc` simulado -- ningún
test necesita VLC instalado ni abre vídeo real. Se prueba: arranque con y
sin libVLC, play() (recreación del media_player en cada zapeo, liberación
del Media anterior, conservación de volumen/silencio), señales desde los
callbacks de libVLC, recorrido y liberación de la lista enlazada C de
pistas, seek, info técnica y cierre ordenado.

VLCPlayer es un QFrame: hace falta una QApplication (igual que en
tests/test_channel_model.py). Las señales internas se reenvían en cola, así
que se procesan los eventos pendientes antes de comprobarlas.
"""
import pytest
from PySide6.QtWidgets import QApplication

from player import vlc_player
from player.vlc_player import VLCPlayer
from tests.vlc_fakes import FakeInstance, FakeMediaPlayer, fake_vlc_module


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_vlc(monkeypatch):
    modulo = fake_vlc_module()
    monkeypatch.setattr(vlc_player, "vlc", modulo)
    monkeypatch.setattr(vlc_player, "VLC_IMPORT_ERROR", None)
    return modulo


@pytest.fixture
def player(qapp, fake_vlc):
    widget = VLCPlayer()
    yield widget
    widget.release()
    widget.deleteLater()


def _signals(widget):
    eventos = []
    widget.error_occurred.connect(lambda m: eventos.append(("error", m)))
    widget.end_reached.connect(lambda: eventos.append(("end",)))
    widget.meta_changed.connect(lambda t: eventos.append(("meta", t)))
    return eventos


# --------------------------------------------------------------------------
# Arranque
# --------------------------------------------------------------------------

def test_without_libvlc_player_is_unavailable_and_play_reports_error(qapp, monkeypatch):
    monkeypatch.setattr(vlc_player, "vlc", None)
    monkeypatch.setattr(vlc_player, "VLC_IMPORT_ERROR", "libvlc.dll no encontrada")
    widget = VLCPlayer()
    eventos = _signals(widget)

    widget.play("https://stream.test/la1.m3u8")

    assert not widget.disponible
    assert "libvlc.dll no encontrada" in vlc_player.vlc_disponible_al_arrancar()
    assert eventos and eventos[0][0] == "error" and "libvlc.dll no encontrada" in eventos[0][1]
    assert widget.is_playing() is False
    assert widget.audio_tracks() == []
    assert widget.technical_info() == {}
    widget.release()


def test_startup_configures_instance_and_attaches_player_events(player, fake_vlc):
    assert vlc_player.vlc_disponible_al_arrancar() is None
    assert player.disponible
    instancia = fake_vlc.instances[0]
    assert "--network-caching=3000" in instancia.args
    assert "--http-reconnect" in instancia.args
    assert set(instancia.players[0].events.attached) == {"error", "end", "vout"}


def test_startup_failure_releases_partial_objects(qapp, fake_vlc, monkeypatch):
    def attach_roto(self):
        raise OSError("libvlc rota")
    monkeypatch.setattr(VLCPlayer, "_attach_events", attach_roto)

    widget = VLCPlayer()

    instancia = fake_vlc.instances[0]
    assert not widget.disponible
    assert instancia.players[0].released and instancia.released
    assert widget.motivo_no_disponible() == "No se pudo inicializar el motor de vídeo de VLC."


# --------------------------------------------------------------------------
# play() y zapeo
# --------------------------------------------------------------------------

def test_play_creates_fresh_player_keeping_volume_and_mute(player, fake_vlc):
    instancia = fake_vlc.instances[0]
    player.set_volume(150)  # se recorta a 100
    player.set_volume(40)
    player.set_muted(True)

    player.play("https://stream.test/la1.m3u8")

    viejo, nuevo = instancia.players
    assert viejo.released and viejo.events.detached == ["error", "end", "vout"]
    assert nuevo.media.url == "https://stream.test/la1.m3u8"
    assert nuevo.playing
    assert (nuevo.volume, nuevo.muted) == (40, 1)
    assert "meta" in nuevo.media.events.attached


def test_zapping_releases_previous_media(player, fake_vlc):
    player.play("https://stream.test/la1.m3u8")
    player.play("https://stream.test/la2.m3u8")

    primero, segundo = fake_vlc.instances[0].medias
    assert primero.released
    assert not segundo.released


def test_play_failure_releases_new_media_and_reports_error(player, fake_vlc, monkeypatch):
    eventos = _signals(player)

    def set_media_roto(self, media):
        raise OSError("ctypes")
    monkeypatch.setattr(FakeMediaPlayer, "set_media", set_media_roto)

    player.play("https://stream.test/roto.m3u8")

    assert fake_vlc.instances[0].medias[0].released
    assert eventos[-1][0] == "error"


def test_play_reports_error_when_player_cannot_be_recreated(player, fake_vlc, monkeypatch):
    eventos = _signals(player)
    monkeypatch.setattr(FakeInstance, "media_player_new", lambda self: (_ for _ in ()).throw(OSError("x")))

    player.play("https://stream.test/la1.m3u8")

    assert not player.disponible
    assert eventos[-1][0] == "error"


# --------------------------------------------------------------------------
# Callbacks de libVLC -> señales públicas (en cola)
# --------------------------------------------------------------------------

def test_libvlc_callbacks_are_forwarded_as_queued_signals(player, fake_vlc, qapp):
    player.play("https://stream.test/radio.mp3")
    qapp.processEvents()  # el meta_changed("") en cola que emite play()
    eventos = _signals(player)
    mp = fake_vlc.instances[0].players[-1]
    media = fake_vlc.instances[0].medias[-1]
    media.now_playing = "  Canción actual  "

    mp.events.attached["error"](None)
    mp.events.attached["end"](None)
    media.events.attached["meta"](None)
    mp.events.attached["vout"](None)
    assert eventos == []  # nada se ejecuta dentro del "hilo" de libVLC
    qapp.processEvents()

    assert eventos == [
        ("error", "No se pudo conectar con el servidor del stream."),
        ("end",),
        ("meta", "Canción actual"),
    ]
    assert mp.scale == 0


# --------------------------------------------------------------------------
# Pistas
# --------------------------------------------------------------------------

def test_track_lists_are_walked_and_released(player, fake_vlc):
    mp = fake_vlc.instances[0].players[0]

    assert player.audio_tracks() == [(-1, "Desactivar"), (1, "Español"), (2, "2")]
    assert player.subtitle_tracks() == []
    assert len(fake_vlc.released_lists) == 1  # la lista vacía no se libera
    assert fake_vlc.released_lists[0] is mp.audio_descriptions


def test_audio_only_mode_disables_and_restores_first_real_video_track(player, fake_vlc):
    mp = fake_vlc.instances[0].players[0]

    player.set_video_enabled(False)
    assert mp.video_track == -1
    player.set_video_enabled(True)
    assert mp.video_track == 5


def test_track_selection(player, fake_vlc):
    player.set_audio_track(2)
    player.set_subtitle_track(3)

    assert player.current_audio_track() == 2
    assert player.current_subtitle_track() == 3


# --------------------------------------------------------------------------
# Control, seek e info técnica
# --------------------------------------------------------------------------

def test_pause_toggle_and_stop(player, fake_vlc):
    mp = fake_vlc.instances[0].players[0]

    player.pause_toggle()
    assert player.is_playing()
    player.pause_toggle()
    assert not player.is_playing()
    player.pause_toggle()
    player.stop()
    assert not mp.playing
    assert player.get_state() == "State.Playing"


@pytest.mark.parametrize("offset, esperado", [
    (5_000, 15_000),
    (-60_000, 0),
    (100_000, 59_500),  # nunca hasta el final exacto
])
def test_seek_relative_clamps_to_media_bounds(player, fake_vlc, offset, esperado):
    player.seek_relative(offset)

    assert player.get_time() == esperado
    assert player.get_length() == 60_000


def test_seek_relative_does_nothing_on_live_streams(player, fake_vlc):
    mp = fake_vlc.instances[0].players[0]
    mp.seekable = False

    player.seek_relative(5_000)

    assert mp.time == 10_000
    assert not player.is_seekable()


def test_technical_info(player, fake_vlc):
    player.play("https://stream.test/la1.m3u8")

    info = player.technical_info()

    assert info == {
        "resolution": "1920 × 1080", "volume": 100, "audio_tracks": 3,
        "subtitle_tracks": 0, "state": "Playing",
        "input_bitrate": 0.5, "demux_bitrate": 0.0,
    }


# --------------------------------------------------------------------------
# Cierre ordenado
# --------------------------------------------------------------------------

def test_release_frees_media_player_and_instance(qapp, fake_vlc):
    widget = VLCPlayer()
    widget.play("https://stream.test/la1.m3u8")
    instancia = fake_vlc.instances[0]
    mp = instancia.players[-1]

    widget.release()

    assert mp.released and instancia.released
    assert instancia.medias[0].released
    assert not widget.disponible


def test_release_detaches_events_before_freeing_player(qapp, fake_vlc):
    """Igual que al zapear: un evento tardío de libVLC durante el cierre no
    puede llegar a un reproductor ya liberado."""
    widget = VLCPlayer()
    mp = fake_vlc.instances[0].players[0]

    widget.release()

    assert mp.events.detached == ["error", "end", "vout"]


def test_release_still_frees_instance_when_stop_fails(qapp, fake_vlc):
    """Un fallo al parar el reproductor no puede dejar la Instance de libVLC
    sin liberar: sus hilos internos podrían colgar el cierre de la app."""
    widget = VLCPlayer()
    instancia = fake_vlc.instances[0]
    mp = instancia.players[0]
    mp.stop_error = OSError("libvlc ocupada")

    widget.release()

    assert mp.released
    assert instancia.released
    assert widget.media_player is None and widget.instance is None
