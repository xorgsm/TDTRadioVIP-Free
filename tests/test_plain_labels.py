"""Los nombres de canal, torrent, archivo de Soulseek o episodio vienen de listas,
feeds y pares ajenos: una QLabel con formato automático los interpretaría como
HTML si llevan una etiqueta (imágenes remotas, enlaces, texto que suplanta otro).
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.visual import ElidedLabel, plain_label

HOSTIL = 'Canal <img src="//10.0.0.1/s/a.png"> <b>oficial</b>'


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_plain_label_keeps_markup_as_literal_text(qapp):
    label = plain_label(HOSTIL)

    assert label.textFormat() == Qt.PlainText
    assert label.text() == HOSTIL


def test_plain_label_without_text_is_plain_too(qapp):
    label = plain_label()
    label.setText(HOSTIL)

    assert label.textFormat() == Qt.PlainText
    assert label.text() == HOSTIL


def test_elided_label_never_interprets_markup(qapp):
    label = ElidedLabel(HOSTIL)
    label.setText(HOSTIL)

    assert label.textFormat() == Qt.PlainText
    assert label.text() == HOSTIL
