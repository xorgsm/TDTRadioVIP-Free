"""Regresiones de fluidez: señales, trabajo diferido y vida útil de widgets."""
import json
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QListWidget, QWidget

from core import backup
from ui import widgets
from ui.app_lifecycle import AppLifecycle
from ui.carousel import Carousel, CarouselCard
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
from ui.download_panel import DownloadPanel
from ui.fetch_worker import ActiveWorkerRegistry, FetchWorker
from ui.home_controller import HomeController
from ui.style import build_style
from ui.widgets import ROLE_DATA, ROLE_FAV, ROLE_PLAYING


@pytest.fixture
def app(monkeypatch):
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(FetchWorker, "_active_registry", ActiveWorkerRegistry())
    yield application
    for worker in FetchWorker.active_workers():
        worker.cancel()
        worker.wait(5000)
    application.processEvents()


def wait_for(app, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert predicate()


def test_tuning_large_catalog_only_notifies_changed_rows(app):
    model = ChannelListModel()
    model.set_entries([
        {ROLE_DATA: {"type": "tv", "name": str(i)}, ROLE_PLAYING: i == 0, ROLE_FAV: False}
        for i in range(10_000)
    ])
    view = ChannelListView()
    view.setModel(model)
    empty = QListWidget()
    window = SimpleNamespace(
        tv_list=view, radio_list=empty, fav_list=empty, hist_list=empty,
        current_type="tv", current_name="1", _playback_failed=False, favorites=[],
    )
    changes = []
    model.dataChanged.connect(lambda first, last, roles: changes.append((first.row(), last.row())))
    controller = ChannelListsController(window)
    controller.mark_playing_everywhere()
    assert changes == [(0, 0), (1, 1)]
    changes.clear()
    controller.mark_playing_everywhere()
    controller.mark_favorites_everywhere()
    assert changes == []
    window.favorites = [{"type": "tv", "name": "50"}]
    controller.mark_favorites_everywhere()
    assert changes == [(50, 50)]
    changes.clear()
    model.set_filter(lambda item: item[ROLE_DATA]["name"] != "1")
    window.current_name = "2"
    controller.mark_playing_everywhere()
    assert not model.entries()[1][ROLE_PLAYING]
    assert changes == [(1, 1)]  # El canal 2 ocupa la fila visible 1.


def test_carousel_reuses_cards_and_refreshes_keyboard_target(app):
    activate = Mock()
    carousel = Carousel(activate)
    entries = [{"type": "tv", "url": str(i), "name": f"Canal {i}"} for i in range(3)]
    carousel.set_entries(entries)
    cards = list(carousel._cards)
    carousel.set_entries(entries)
    assert carousel._cards == cards
    revised = dict(entries[1], name="Nombre nuevo", subtitle="Programa nuevo")
    carousel.set_entries([revised, entries[0]])
    assert carousel._cards == [cards[1], cards[0]]
    assert cards[1].kind_label.text() == "Programa nuevo"
    assert cards[1].accessibleName() == "Reproducir Nombre nuevo"
    QTest.keyClick(cards[1], Qt.Key_Return)
    activate.assert_called_once_with(revised)
    assert not cards[2].isVisible()


def test_carousel_ignores_obsolete_logo_callbacks(app):
    loader = Mock()
    card = CarouselCard({"type": "tv", "url": "stream", "logo": "old"}, Mock(), loader)
    old_callback = loader.load.call_args.args[1]
    card.update_entry({"type": "tv", "url": "stream", "logo": "new"})
    new_callback = loader.load.call_args.args[1]
    red, blue = QPixmap(10, 10), QPixmap(10, 10)
    red.fill(QColor("red"))
    blue.fill(QColor("blue"))
    new_callback(blue)
    old_callback(red)
    assert card.logo_label.pixmap().toImage().pixelColor(0, 0) == QColor("blue")


def test_gradient_colors_for_name_are_deterministic_and_vary(app):
    from ui.carousel import _gradient_colors_for_name
    first = _gradient_colors_for_name("La 1")
    again = _gradient_colors_for_name("La 1")
    other = _gradient_colors_for_name("Antena 3")
    assert first == again
    assert first != other
    for color in first:
        assert color.startswith("#")


def test_carousel_card_applies_deterministic_gradient_stylesheet(app):
    card_a = CarouselCard({"type": "tv", "url": "u1", "name": "La 1"}, Mock())
    card_b = CarouselCard({"type": "tv", "url": "u2", "name": "La 1"}, Mock())
    card_c = CarouselCard({"type": "radio", "url": "u3", "name": "Antena 3"}, Mock())
    assert "qlineargradient" in card_a.styleSheet()
    assert card_a.styleSheet() == card_b.styleSheet()
    assert card_a.styleSheet() != card_c.styleSheet()


def test_carousel_card_updates_gradient_when_name_changes(app):
    card = CarouselCard({"type": "tv", "url": "u1", "name": "La 1"}, Mock())
    original = card.styleSheet()
    card.update_entry({"type": "tv", "url": "u1", "name": "La 2"})
    assert card.styleSheet() != original
    assert "qlineargradient" in card.styleSheet()


def test_carousel_card_stylesheet_includes_focus_ring(app):
    card = CarouselCard({"type": "tv", "url": "u1", "name": "La 1"}, Mock())
    assert ":focus" in card.styleSheet()


def test_download_tools_are_lazy_and_share_latest_destination(app, monkeypatch, tmp_path):
    built = []

    class Tool(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.initial_args = args
            self.set_dest_dir = Mock()
            self.shutdown = Mock()
            built.append(self)

    for module, name in (
        ("torrent_panel", "TorrentPanel"), ("podcast_panel", "PodcastPanel"),
        ("soulseek_panel", "SoulseekPanel"), ("audio_converter_panel", "AudioConverterPanel"),
        ("mp3_editor_panel", "Mp3EditorPanel"), ("mp3_tag_editor_panel", "Mp3TagEditorPanel"),
    ):
        monkeypatch.setitem(sys.modules, f"ui.{module}", SimpleNamespace(**{name: Tool}))
    panel = DownloadPanel(str(tmp_path))
    assert built == []
    panel.tabs.setCurrentIndex(1)
    assert len(built) == 1
    new_dir = str(tmp_path / "new")
    panel._on_torrent_dest_changed(new_dir)
    panel.tabs.setCurrentIndex(2)
    assert built[1].initial_args == (new_dir,)
    panel.tabs.setCurrentIndex(1)
    assert len(built) == 2
    panel.shutdown()
    assert len(built) == 2  # Cerrar no construye los otros cuatro paneles.
    assert all(tool.shutdown.call_count == 1 for tool in built)


def test_logo_io_runs_off_ui_and_reuses_disk_cache(app, monkeypatch, tmp_path):
    monkeypatch.setattr(widgets, "get_app_data_dir", lambda: tmp_path)
    image = QImage(512, 512, QImage.Format_ARGB32)
    image.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    payload = bytes(buffer.data())
    main_thread = threading.get_ident()
    downloads = []

    def download(url):
        downloads.append(threading.get_ident())
        return payload

    monkeypatch.setattr(widgets, "_download_logo_bytes", download)
    received = []
    loader = widgets.LogoLoader()
    loader.load("https://example.test/logo", lambda pix: received.append((pix, threading.get_ident())))
    wait_for(app, lambda: len(received) == 1)
    assert downloads[0] != main_thread
    assert received[0][1] == main_thread
    assert received[0][0].width() == 44
    loader2 = widgets.LogoLoader()
    loader2.load("https://example.test/logo", lambda pix: received.append((pix, threading.get_ident())))
    wait_for(app, lambda: len(received) == 2)
    assert len(downloads) == 1


def test_automatic_backup_does_not_block_ui_or_report_after_close(app, monkeypatch, tmp_path):
    from core import config

    started, release = threading.Event(), threading.Event()
    threads = []

    def slow_backup(*args, **kwargs):
        threads.append(threading.get_ident())
        started.set()
        assert release.wait(5)
        return True

    class Window:
        def statusBar(self):
            return self.status

    monkeypatch.setattr(backup, "run_automatic_backup", slow_backup)
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "get_profile_data_dir", lambda: tmp_path)
    window = Window()
    window._is_closing = False
    window.settings = {}
    window.status = Mock()
    lifecycle = AppLifecycle(window)
    try:
        lifecycle.run_automatic_backup()
        wait_for(app, started.is_set)
        assert threads[0] != threading.get_ident()
        first_worker = window._backup_worker
        lifecycle.run_automatic_backup()
        assert window._backup_worker is first_worker
        window._is_closing = True
    finally:
        release.set()
        window._backup_worker.wait(5000)
        app.processEvents()
    window.status.showMessage.assert_not_called()


def test_cleanup_old_updates_scans_the_updates_folder(monkeypatch, tmp_path):
    from core import config, updater

    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    window = SimpleNamespace(_is_closing=False)
    lifecycle = AppLifecycle(window)
    calls = []
    monkeypatch.setattr(
        updater, "cleanup_obsolete_updates", lambda destination_dir: calls.append(destination_dir)
    )
    lifecycle.cleanup_old_updates()
    assert calls == [tmp_path / "updates"]


def test_cleanup_old_updates_skips_after_window_starts_closing(monkeypatch):
    from core import updater

    window = SimpleNamespace(_is_closing=True)
    lifecycle = AppLifecycle(window)
    calls = []
    monkeypatch.setattr(
        updater, "cleanup_obsolete_updates", lambda destination_dir: calls.append(destination_dir)
    )
    lifecycle.cleanup_old_updates()
    assert calls == []


def test_disconnect_vpn_profiles_disconnects_only_connected_tunnels(monkeypatch):
    from core import vpn_client, vpn_profiles

    window = SimpleNamespace(_is_closing=False)
    lifecycle = AppLifecycle(window)
    monkeypatch.setattr(vpn_client, "is_openvpn_installed", lambda: True)
    monkeypatch.setattr(
        vpn_profiles, "list_profiles",
        lambda: [
            {"name": "Japón", "tunnel": "japon", "conf_path": "x"},
            {"name": "Croacia", "tunnel": "croacia", "conf_path": "y"},
        ],
    )
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: tunnel == "japon")
    disconnected = []
    monkeypatch.setattr(vpn_client, "disconnect", lambda tunnel: disconnected.append(tunnel))
    lifecycle.disconnect_vpn_profiles()
    assert disconnected == ["japon"]


def test_disconnect_vpn_profiles_is_a_no_op_without_openvpn_installed(monkeypatch):
    from core import vpn_client, vpn_profiles

    window = SimpleNamespace(_is_closing=False)
    lifecycle = AppLifecycle(window)
    monkeypatch.setattr(vpn_client, "is_openvpn_installed", lambda: False)
    calls = []
    monkeypatch.setattr(vpn_profiles, "list_profiles", lambda: calls.append("called") or [])
    lifecycle.disconnect_vpn_profiles()
    assert calls == []


def test_disconnect_vpn_profiles_ignores_disconnect_errors(monkeypatch):
    from core import vpn_client, vpn_profiles

    window = SimpleNamespace(_is_closing=False)
    lifecycle = AppLifecycle(window)
    monkeypatch.setattr(vpn_client, "is_openvpn_installed", lambda: True)
    monkeypatch.setattr(
        vpn_profiles, "list_profiles",
        lambda: [{"name": "Japón", "tunnel": "japon", "conf_path": "x"}],
    )
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: True)

    def _raise(tunnel):
        raise vpn_client.VpnClientError("no se pudo lanzar openvpn-gui.exe")

    monkeypatch.setattr(vpn_client, "disconnect", _raise)
    lifecycle.disconnect_vpn_profiles()  # no debe propagar el error


def test_disconnect_vpn_profiles_swallows_any_exception_not_just_vpn_client_error(monkeypatch):
    """Reproduce el fallo real reportado: subprocess.TimeoutExpired no es
    un VpnClientError, y sin capturarlo aparte cortaba el resto del
    cierre de la app en silencio (ver core.vpn_client._run)."""
    from core import vpn_client, vpn_profiles

    window = SimpleNamespace(_is_closing=False)
    lifecycle = AppLifecycle(window)
    monkeypatch.setattr(vpn_client, "is_openvpn_installed", lambda: True)
    monkeypatch.setattr(
        vpn_profiles, "list_profiles",
        lambda: [
            {"name": "Japón", "tunnel": "japon", "conf_path": "x"},
            {"name": "Croacia", "tunnel": "croacia", "conf_path": "y"},
        ],
    )
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: True)
    disconnected = []

    def _flaky_disconnect(tunnel):
        if tunnel == "japon":
            raise RuntimeError("openvpn-gui.exe no respondió a tiempo")
        disconnected.append(tunnel)

    monkeypatch.setattr(vpn_client, "disconnect", _flaky_disconnect)
    lifecycle.disconnect_vpn_profiles()  # no debe propagar el error
    assert disconnected == ["croacia"]  # sigue con el resto de perfiles


def test_backup_uses_captured_profile_directory(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "favorites.json").write_text('[{"name": "first"}]', encoding="utf-8")
    (second / "favorites.json").write_text('[{"name": "second"}]', encoding="utf-8")
    monkeypatch.setattr(backup, "get_profile_data_dir", lambda: second)
    target = backup.create_automatic_backup(
        tmp_path / "backups", app_data_dir=tmp_path, profile_data_dir=first,
    )
    assert json.loads(target.read_text(encoding="utf-8"))["favorites"] == [{"name": "first"}]


def test_home_can_return_to_last_station(app):
    entry = {"type": "radio", "name": "Radio", "url": "https://example.test/live"}
    window = SimpleNamespace(current_url=None, history=[entry], playback=Mock())
    HomeController(window).home_resume_or_search()
    window.playback.play.assert_called_once_with("radio", "Radio", entry["url"], "", "", [])


def test_refresh_home_page_populates_all_four_carousels(app):
    from ui.home_controller import HomeController
    win = SimpleNamespace(
        history=[{"type": "tv", "name": "Canal 1", "url": "u1", "logo": ""}],
        favorites=[{"type": "radio", "name": "Radio 1", "url": "u2", "logo": ""}],
        tv_channels_data=[],
        epg=SimpleNamespace(now_on_air_entries=Mock(return_value=[{"type": "tv", "name": "En antena", "url": "u3"}])),
        home_recent_carousel=Mock(),
        home_on_air_carousel=Mock(),
        home_recommended_carousel=Mock(),
        home_fav_carousel=Mock(),
    )
    HomeController(win).refresh_home_page()
    win.home_recent_carousel.set_entries.assert_called_once_with(win.history[:12])
    win.home_on_air_carousel.set_entries.assert_called_once_with([{"type": "tv", "name": "En antena", "url": "u3"}])
    win.home_recommended_carousel.set_entries.assert_called_once_with([])
    win.home_fav_carousel.set_entries.assert_called_once_with(win.favorites[:5])


def _make_home_compact_win():
    return SimpleNamespace(
        _home_now_layout=Mock(), _home_health_layout=Mock(), _home_layout=Mock(),
        _home_hero_layout=Mock(), home_greeting=Mock(),
    )


def test_update_home_compact_switches_hero_and_health_direction(app):
    from ui.home_controller import HomeController
    win = _make_home_compact_win()
    HomeController(win).update_home_compact(400)
    win._home_now_layout.setDirection.assert_called_once_with(QBoxLayout.TopToBottom)
    win._home_health_layout.setDirection.assert_called_once_with(QBoxLayout.TopToBottom)
    win._home_layout.setContentsMargins.assert_called_once_with(2, 4, 2, 18)
    # 400px es "compacto" (< 520) pero no "muy compacto" (< 360, ver
    # test_update_home_compact_shrinks_hero_below_360 más abajo) -- el
    # hero todavía usa su padding/tipografía normales a este ancho.
    win._home_hero_layout.setContentsMargins.assert_called_once_with(22, 18, 22, 18)
    win.home_greeting.setStyleSheet.assert_called_once_with("")


def test_update_home_compact_shrinks_hero_below_360(app):
    """Spec v8 §5.4: el hero se encoge en altura (menos padding,
    tipografía más pequeña) al acercarse al mínimo de la ventana, en vez
    de ocultarse u obligar a un layout vertical."""
    from ui.home_controller import HomeController
    win = _make_home_compact_win()
    HomeController(win).update_home_compact(300)
    win._home_hero_layout.setContentsMargins.assert_called_once_with(14, 10, 14, 10)
    win._home_hero_layout.setSpacing.assert_called_once_with(6)
    win.home_greeting.setStyleSheet.assert_called_once_with("font-size: 15pt;")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_style_builds_with_carousel_label_transparency(theme):
    assert 'QFrame#carouselCard QLabel' in build_style(theme=theme)
