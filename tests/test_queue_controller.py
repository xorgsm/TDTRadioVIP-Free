"""
Cobertura de ui/queue_controller.py: la cola "Reproduciendo a continuación".

El estado (añadir, sacar, vaciar, tooltip del botón) se prueba con una
ventana falsa mínima; el panel emergente necesita widgets Qt de verdad
(QDialog parentado a la ventana, QListWidget con arrastre), así que la
ventana falsa es un QWidget real con el resto de colaboradores en Mock.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from ui.queue_controller import ROLE_QUEUE_DATA, QueueController

LA1 = {"type": "tv", "name": "La 1", "url": "https://stream.test/la1",
       "tvg_id": "la1", "logo": "https://logo/la1.png",
       "alternate_urls": ["https://respaldo/la1"]}
RNE = {"type": "radio", "name": "RNE", "url": "https://stream.test/rne"}
CUATRO = {"type": "tv", "name": "Cuatro", "url": "https://stream.test/c4"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._status = Mock()
        self.playback = Mock()
        self.queue_btn = QPushButton(self)
        self.more_btn = QPushButton(self)

    def statusBar(self):
        return self._status


@pytest.fixture
def win(qapp):
    w = FakeWindow()
    yield w
    w.deleteLater()


@pytest.fixture
def queue(win):
    return QueueController(win)


def _rows(queue):
    lst = queue._list_widget
    return [lst.item(r).text() for r in range(lst.count())]


# --------------------------------------------------------------------------
# Estado de la cola
# --------------------------------------------------------------------------

def test_starts_empty(queue, win):
    assert win._queue == []
    assert not queue.has_items()


def test_add_appends_a_copy_and_updates_tooltip(queue, win):
    data = dict(LA1)

    queue.add(data)
    data["name"] = "cambiado"

    assert queue.has_items()
    assert win._queue[0]["name"] == "La 1"
    assert win.queue_btn.toolTip() == "Cola de reproducción (1)"
    win.statusBar().showMessage.assert_called_once()


@pytest.mark.parametrize("data", [None, {}, {"name": "Sin enlace", "url": ""}])
def test_add_ignores_entries_without_url(queue, win, data):
    queue.add(data)

    assert win._queue == []
    win.statusBar().showMessage.assert_not_called()


def test_play_next_plays_first_item_with_its_backup_urls(queue, win):
    """Un canal en cola debe conservar sus fuentes de respaldo: sin ellas,
    si la URL principal fallaba nunca se probaban las alternativas."""
    queue.add(LA1)
    queue.add(RNE)

    assert queue.play_next() is True

    win.playback.play.assert_called_once_with(
        "tv", "La 1", "https://stream.test/la1", "la1",
        "https://logo/la1.png", ["https://respaldo/la1"],
    )
    assert [d["name"] for d in win._queue] == ["RNE"]


def test_play_next_without_optional_fields_uses_defaults(queue, win):
    queue.add(RNE)

    queue.play_next()

    win.playback.play.assert_called_once_with(
        "radio", "RNE", "https://stream.test/rne", "", "", [],
    )


def test_play_next_on_empty_queue_does_nothing(queue, win):
    assert queue.play_next() is False
    win.playback.play.assert_not_called()


def test_clear_empties_queue_and_tooltip(queue, win):
    queue.add(LA1)
    queue.add(RNE)

    queue.clear()

    assert not queue.has_items()
    assert win.queue_btn.toolTip() == "Cola de reproducción (vacía)"


def test_badge_refresh_tolerates_missing_button(queue, win):
    win.queue_btn = None

    queue.add(LA1)

    assert queue.has_items()


# --------------------------------------------------------------------------
# Panel emergente
# --------------------------------------------------------------------------

def test_panel_shows_empty_placeholder(queue):
    queue.toggle_panel()

    assert queue._dialog.isVisible()
    assert _rows(queue) == ["La cola está vacía."]
    assert queue._list_widget.item(0).data(ROLE_QUEUE_DATA) is None


def test_panel_lists_items_and_follows_changes(queue):
    queue.add(LA1)
    queue.toggle_panel()
    assert _rows(queue) == ["TV · La 1"]

    queue.add(RNE)
    assert _rows(queue) == ["TV · La 1", "FM · RNE"]

    queue.play_next()
    assert _rows(queue) == ["FM · RNE"]

    queue.clear()
    assert _rows(queue) == ["La cola está vacía."]


def test_toggle_closes_open_panel_and_reuses_it(queue):
    queue.toggle_panel()
    dialog = queue._dialog

    queue.toggle_panel()
    assert not dialog.isVisible()

    queue.add(LA1)
    queue.toggle_panel()
    assert queue._dialog is dialog
    assert dialog.isVisible()
    assert _rows(queue) == ["TV · La 1"]


def test_dragging_rows_reorders_the_queue(queue, win):
    for data in (LA1, RNE, CUATRO):
        queue.add(data)
    queue.toggle_panel()

    moved = queue._list_widget.model().moveRow(QModelIndex(), 2, QModelIndex(), 0)

    assert moved
    assert [d["name"] for d in win._queue] == ["Cuatro", "La 1", "RNE"]
    queue.play_next()
    assert win.playback.play.call_args.args[1] == "Cuatro"
