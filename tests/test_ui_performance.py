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
from PySide6.QtWidgets import QApplication, QListWidget, QWidget

from core import backup
from ui import widgets
from ui.carousel import Carousel, CarouselCard
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
from ui.download_panel import DownloadPanel
from ui.fetch_worker import ActiveWorkerRegistry, FetchWorker
from ui.home_controller import HomeController
from ui.main_window import MainWindow
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
        tv_list=view, radio_list=empty, fav_list=empty, hist_list=empty, home_fav_list=empty,
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

    class Window(QWidget):
        _run_automatic_backup = MainWindow._run_automatic_backup
        _on_automatic_backup_done = MainWindow._on_automatic_backup_done

        def statusBar(self):
            return self.status

    monkeypatch.setattr(backup, "run_automatic_backup", slow_backup)
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "get_profile_data_dir", lambda: tmp_path)
    window = Window()
    window._is_closing = False
    window.settings = {}
    window.status = Mock()
    try:
        window._run_automatic_backup()
        wait_for(app, started.is_set)
        assert threads[0] != threading.get_ident()
        first_worker = window._backup_worker
        window._run_automatic_backup()
        assert window._backup_worker is first_worker
        window._is_closing = True
    finally:
        release.set()
        window._backup_worker.wait(5000)
        app.processEvents()
    window.status.showMessage.assert_not_called()


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
    window.playback.play.assert_called_once_with("radio", "Radio", entry["url"], "", "")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_style_builds_with_carousel_focus(theme):
    assert 'QFrame#carouselCard:focus' in build_style(theme=theme)
