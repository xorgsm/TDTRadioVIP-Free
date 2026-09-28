"""
Reproducir desde lo guardado en el historial: el carrusel "Recientes" de
Inicio (HomeController.activate_home_entry), "reanudar al abrir"
(MainWindow._resume_last_stream) y "Recientes" de la barra lateral
(LibrarySidebar._activate_recent).

Los tres deben pasar a play() todo lo que la entrada guarda -- logo,
tvg_id y fuentes de respaldo --. Sin ellos la barra de reproducción salía
sin logo, la TV sin "Ahora: ..." de la guía EPG, y un corte no probaba las
URLs de respaldo.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from ui.home_controller import HomeController
from ui.library_sidebar import ROLE_ACTION, LibrarySidebar
from ui.main_window import MainWindow

ENTRY = {
    "type": "tv", "name": "La 1", "url": "https://stream.test/la1",
    "logo": "https://logo/la1", "tvg_id": "la1",
    "alternate_urls": ["https://respaldo/la1"], "timestamp": "28/09/2026 10:00",
}
EXPECTED = ("tv", "La 1", "https://stream.test/la1", "la1", "https://logo/la1",
            ["https://respaldo/la1"])
OLD_ENTRY = {"type": "radio", "name": "RNE", "url": "https://stream.test/rne"}
OLD_EXPECTED = ("radio", "RNE", "https://stream.test/rne", "", "", [])


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(entry):
    return SimpleNamespace(
        _is_closing=False, current_url=None, history=[entry], favorites=[],
        playback=Mock(),
    )


@pytest.mark.parametrize(("entry", "expected"), [(ENTRY, EXPECTED), (OLD_ENTRY, OLD_EXPECTED)])
def test_home_recent_card_plays_with_everything_saved(entry, expected):
    win = _window(entry)

    HomeController(win).activate_home_entry(entry)

    win.playback.play.assert_called_once_with(*expected)


@pytest.mark.parametrize(("entry", "expected"), [(ENTRY, EXPECTED), (OLD_ENTRY, OLD_EXPECTED)])
def test_resume_last_stream_plays_with_everything_saved(entry, expected):
    win = _window(entry)

    MainWindow._resume_last_stream(win)

    win.playback.play.assert_called_once_with(*expected)


@pytest.mark.parametrize(("entry", "expected"), [(ENTRY, EXPECTED), (OLD_ENTRY, OLD_EXPECTED)])
def test_sidebar_recent_plays_with_everything_saved(qapp, entry, expected):
    win = _window(entry)
    sidebar = LibrarySidebar(win, on_open_folder=Mock())
    item = sidebar.recent_list.item(0)
    assert item.data(ROLE_ACTION)["name"] == entry["name"]

    sidebar._activate_recent(item)

    win.playback.play.assert_called_once_with(*expected)
    sidebar.deleteLater()
