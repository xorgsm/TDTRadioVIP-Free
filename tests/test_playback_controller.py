"""
Cobertura de la lógica de ui/playback_controller.py: grabación frente a
zapeo, reintentos y fuentes de respaldo, auto-salto de canal, aviso de
auto-ocultar, fin de emisión con cola, y ajustes de volumen/silencio.

La ventana es un MagicMock (cualquier widget que toque el controlador
existe y acepta llamadas) con el estado relevante fijado a mano. Los
efectos visuales (fundido del título, logo, EPG) y QTimer se sustituyen:
lo que se prueba es la decisión de qué hacer, no el dibujo.
"""
from unittest.mock import MagicMock, Mock

import pytest

from ui import playback_controller as pc_module
from ui.playback_controller import PlaybackController


@pytest.fixture
def timers(monkeypatch):
    """Recoge las funciones programadas con QTimer.singleShot sin ejecutarlas."""
    pendientes = []
    timer = Mock()
    timer.singleShot.side_effect = lambda ms, fn: pendientes.append(fn)
    monkeypatch.setattr(pc_module, "QTimer", timer)
    return pendientes


@pytest.fixture
def stores(monkeypatch):
    tv = Mock(record_channel_failure=Mock(return_value=1))
    radio = Mock(record_channel_failure=Mock(return_value=1))
    monkeypatch.setattr(pc_module, "tv_channels", tv)
    monkeypatch.setattr(pc_module, "radio_stations", radio)
    monkeypatch.setattr(pc_module, "hist_store", Mock(add_entry=Mock(return_value=[])))
    monkeypatch.setattr(pc_module, "fav_store", Mock(is_favorite=Mock(return_value=False)))
    monkeypatch.setattr(pc_module, "recording_schedule", Mock())
    monkeypatch.setattr(pc_module, "make_glow", Mock(), raising=False)
    monkeypatch.setattr(pc_module, "QMessageBox", Mock())
    monkeypatch.setattr(pc_module, "show_toast", Mock())
    monkeypatch.setattr(pc_module.cfg, "save_settings", Mock(return_value=True))
    return SimpleStores(tv, radio)


class SimpleStores:
    def __init__(self, tv, radio):
        self.tv = tv
        self.radio = radio


@pytest.fixture
def win():
    w = MagicMock()
    w.recorder.is_recording = False
    w.recorder.stop.return_value = ("C:/grab/x.mp4", True)
    w._scheduled_recording_active = None
    w._playback_token = 0
    w._playback_failed = False
    w._auto_skip_count = 0
    w._active_list = None
    w._audio_only_tv = False
    w._current_alternate_urls = []
    w.current_url = None
    w.current_type = None
    w.current_name = None
    w.volume_slider.value.return_value = 70
    w.mute_btn.isChecked.return_value = False
    w.queue.has_items.return_value = False
    w.settings = {}
    w.radio_stations_data = []
    return w


@pytest.fixture
def ctrl(win, timers, stores, monkeypatch):
    controller = PlaybackController(win)
    for nombre in ("_pulse_now_playing", "update_now_logo", "update_epg_display",
                   "_set_play_button_state", "_update_favorite_button_icon"):
        monkeypatch.setattr(controller, nombre, Mock())
    return controller


def _playing(win, url="https://stream.test/la1", name="La 1", kind="tv"):
    win.current_url, win.current_name, win.current_type = url, name, kind


# --------------------------------------------------------------------------
# Grabación frente a zapeo / parar
# --------------------------------------------------------------------------

def test_zapping_stops_a_manual_recording(ctrl, win):
    win.recorder.is_recording = True

    ctrl.play("tv", "Antena 3", "https://stream.test/a3")

    win.recorder.stop.assert_called_once()


def test_zapping_does_not_stop_a_scheduled_recording(ctrl, win):
    """Una grabación programada arrancó sola, con su propio canal y hora de
    fin: cambiar lo que se está viendo no puede cortarla."""
    win.recorder.is_recording = True
    win._scheduled_recording_active = Mock(tvg_id="la1", title="Noticias", start="x")

    ctrl.play("tv", "Antena 3", "https://stream.test/a3")

    win.recorder.stop.assert_not_called()
    pc_module.recording_schedule.mark_done.assert_not_called()
    assert win._scheduled_recording_active is not None


def test_stop_button_does_not_stop_a_scheduled_recording(ctrl, win):
    win.recorder.is_recording = True
    win._scheduled_recording_active = Mock()
    _playing(win)

    ctrl.stop_playback()

    win.recorder.stop.assert_not_called()
    win.player.stop.assert_called()
    assert win.current_url is None


def test_stop_button_stops_a_manual_recording(ctrl, win):
    win.recorder.is_recording = True
    _playing(win)

    ctrl.stop_playback()

    win.recorder.stop.assert_called_once()


def test_record_button_stops_scheduled_recording_and_clears_schedule(ctrl, win):
    """El botón de grabar sí es una acción explícita sobre la grabación."""
    win.recorder.is_recording = True
    activa = Mock(tvg_id="la1", title="Noticias", start="20260925210000")
    win._scheduled_recording_active = activa

    ctrl.toggle_recording()

    win.recorder.stop.assert_called_once()
    pc_module.recording_schedule.mark_done.assert_called_once_with("la1", "Noticias", "20260925210000")
    assert win._scheduled_recording_active is None


# --------------------------------------------------------------------------
# play()
# --------------------------------------------------------------------------

def test_play_tv_updates_state_and_schedules_confirmation(ctrl, win, timers):
    ctrl.play("tv", "La 1", "https://stream.test/la1", "La1.es", "logo.png", ["https://b"])

    win.player.play.assert_called_once_with("https://stream.test/la1")
    win.player.set_volume.assert_called_with(70)
    assert (win.current_type, win.current_name, win.current_url) == ("tv", "La 1", "https://stream.test/la1")
    assert win._current_alternate_urls == ["https://b"]
    assert win._playback_token == 1
    assert len(timers) == 1


def test_play_radio_starts_equalizer(ctrl, win):
    ctrl.play("radio", "Cadena SER", "https://stream.test/ser")

    win.player_stack.setCurrentWidget.assert_called_with(win.equalizer)
    win.equalizer.start.assert_called_once()


def test_confirmation_resets_failure_counter_only_for_current_playback(ctrl, win, timers, stores):
    ctrl.play("tv", "La 1", "https://stream.test/la1")
    confirmar = timers[-1]

    confirmar()
    stores.tv.reset_channel_failures.assert_called_once_with("La 1")

    stores.tv.reset_channel_failures.reset_mock()
    ctrl.play("tv", "Antena 3", "https://stream.test/a3")  # ya se cambió de canal
    confirmar()
    stores.tv.reset_channel_failures.assert_not_called()


# --------------------------------------------------------------------------
# Errores: reintentos, fuentes de respaldo, auto-salto, auto-ocultar
# --------------------------------------------------------------------------

def test_error_retries_same_url_then_alternate_then_gives_up(ctrl, win, timers, stores):
    _playing(win)
    win._current_alternate_urls = ["https://respaldo/la1"]

    ctrl.on_player_error("caída")          # 1er fallo -> reintento programado
    timers.pop()()                          # reintento 1: misma URL
    assert win.player.play.call_args.args[0] == "https://stream.test/la1"

    ctrl.on_player_error("caída")          # 2º fallo -> reintento programado
    timers.pop()()                          # reintento 2: primera URL de respaldo
    assert win.player.play.call_args.args[0] == "https://respaldo/la1"

    ctrl.on_player_error("caída")          # 3er fallo -> ya no reintenta
    stores.tv.record_channel_failure.assert_called_once_with("La 1")


def test_stale_retry_after_channel_change_does_nothing(ctrl, win, timers):
    _playing(win)
    ctrl.on_player_error("caída")
    reintento = timers.pop()
    win._playback_token += 5  # el usuario cambió de canal
    win.player.play.reset_mock()

    reintento()

    win.player.play.assert_not_called()


def test_exhausted_retries_auto_skip_to_next_visible_item(ctrl, win, timers):
    _playing(win)
    ctrl._recovery_attempts = ctrl.MAX_STREAM_RETRIES
    lista = MagicMock()
    lista.count.return_value = 3
    oculto, siguiente = MagicMock(), MagicMock()
    oculto.isHidden.return_value = True
    siguiente.isHidden.return_value = False
    siguiente.data.return_value = {"type": "tv", "name": "Cuatro", "url": "https://stream.test/c4"}
    lista.item.side_effect = lambda row: {1: oculto, 2: siguiente}[row]
    lista.row.return_value = 2
    win._active_list = lista
    win._active_row = 0

    ctrl.on_player_error("caída")
    assert win._auto_skip_count == 1
    timers.pop()()

    assert win.current_name == "Cuatro"
    assert win._active_row == 2


def test_auto_skip_stops_after_max_attempts(ctrl, win, timers):
    _playing(win)
    ctrl._recovery_attempts = ctrl.MAX_STREAM_RETRIES
    win._active_list = MagicMock()
    win._auto_skip_count = ctrl.MAX_AUTO_SKIP

    ctrl.on_player_error("caída")

    assert timers == []
    assert win._auto_skip_count == 0


def test_autohide_is_offered_only_when_crossing_threshold(ctrl, win, stores):
    _playing(win)
    ctrl._recovery_attempts = ctrl.MAX_STREAM_RETRIES
    for fallos, avisos in ((2, 0), (3, 1), (4, 1)):
        stores.tv.record_channel_failure.return_value = fallos
        ctrl.on_player_error("caída")
        assert pc_module.show_toast.call_count == avisos


# --------------------------------------------------------------------------
# Fin de emisión, volumen, silencio, solo audio
# --------------------------------------------------------------------------

def test_end_reached_plays_next_in_queue(ctrl, win):
    win.queue.has_items.return_value = True

    ctrl.on_player_end_reached()

    win.queue.play_next.assert_called_once()
    win.equalizer.stop.assert_not_called()


def test_end_reached_after_failure_is_ignored(ctrl, win):
    win._playback_failed = True
    win.queue.has_items.return_value = True

    ctrl.on_player_end_reached()

    win.queue.play_next.assert_not_called()


def test_volume_change_is_saved_and_applied_to_radio_visualizer(ctrl, win):
    win.current_type = "radio"

    ctrl.on_volume_changed(40)

    win.player.set_volume.assert_called_with(40)
    assert win.settings["volume"] == 40
    win.equalizer.set_intensity.assert_called_with(0.4)


def test_audio_only_toggle_is_persisted_and_applied_to_tv(ctrl, win):
    win.current_type = "tv"

    ctrl.toggle_audio_only_tv()

    assert win.settings["audio_only_tv"] is True
    win.player.set_video_enabled.assert_called_with(False)
    ctrl.toggle_audio_only_tv()
    win.player.set_video_enabled.assert_called_with(True)


def test_toggle_play_without_selection_only_informs(ctrl, win):
    ctrl.toggle_play()

    win.player.pause_toggle.assert_not_called()
    pc_module.QMessageBox.information.assert_called_once()


def test_manual_recording_without_playback_is_refused(ctrl, win):
    ctrl.toggle_recording()

    win.recorder.start.assert_not_called()
    win.record_btn.setChecked.assert_called_with(False)


def test_manual_recording_starts_and_schedules_alive_check(ctrl, win, timers, monkeypatch):
    monkeypatch.setattr(pc_module.rec_module.Recorder, "ffmpeg_available", staticmethod(lambda: True))
    _playing(win, kind="radio")
    win.recorder.start.return_value = "C:/grab/la1.mka"

    ctrl.toggle_recording()

    win.recorder.start.assert_called_once_with("https://stream.test/la1", "La 1", kind="radio")
    win.record_btn.setChecked.assert_called_with(True)
    assert len(timers) == 1
