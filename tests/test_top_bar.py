"""Barra superior global (ui.top_bar): búsqueda siempre visible y Multivista."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from ui import palette
from ui.style.builder import build_style
from ui.top_bar import SEARCH_HINT, TOP_BAR_HEIGHT, build_app_top_bar


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win():
    return SimpleNamespace(dialogs=Mock())


def test_top_bar_is_56px_with_the_search_hint_and_shortcut(app):
    win = _make_win()
    bar = build_app_top_bar(win)
    assert bar.height() == TOP_BAR_HEIGHT == 56
    texts = [label.text() for label in win.top_search_btn.findChildren(QLabel)]
    assert SEARCH_HINT == "Buscar canales, emisoras, programas, podcasts…"
    assert SEARCH_HINT in texts and "Ctrl K" in texts


def test_search_trigger_opens_the_command_palette(app):
    win = _make_win()
    bar = build_app_top_bar(win)  # noqa: F841
    win.top_search_btn.click()
    win.dialogs.open_command_palette.assert_called_once_with()


def test_multivista_opens_the_mosaic(app):
    win = _make_win()
    bar = build_app_top_bar(win)
    chip = next(b for b in bar.findChildren(QPushButton) if b.text() == "Multivista")
    chip.click()
    win.dialogs.open_mosaic_view.assert_called_once_with()


def test_top_bar_paints_its_background_and_bottom_rule(app):
    win = _make_win()
    host = QWidget()
    host.setObjectName("topHost")
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(build_app_top_bar(win))
    layout.addStretch(1)
    app.setStyleSheet(build_style() + "\nQWidget#topHost { background-color: #ff0000; }")
    try:
        host.resize(900, 120)
        host.show()
        app.processEvents()
        img = host.grab().toImage()
        bar = win.top_search_btn.parentWidget()
        chip = next(b for b in bar.findChildren(QPushButton) if b.text() == "Multivista")
        # Buscador a su ancho máximo a la izquierda; Multivista pegado a la derecha.
        assert win.top_search_btn.width() == 560
        assert chip.geometry().right() == bar.width() - 20 - 1
        # Hueco entre el buscador y Multivista.
        assert img.pixelColor(700, TOP_BAR_HEIGHT // 2).name() == palette.BG_ROOT.lower()
        assert img.pixelColor(700, TOP_BAR_HEIGHT - 1).name() == palette.BORDER.lower()
    finally:
        app.setStyleSheet("")
        host.hide()
