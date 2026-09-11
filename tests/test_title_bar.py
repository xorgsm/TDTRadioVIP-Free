"""Contrato de ui.title_bar.update_edition_badge: insignia FREE/LICENCIADA/
SIN ACTIVAR junto a la versión en la barra de título."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from ui.title_bar import update_edition_badge


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win(*, es_version_free, activated):
    return SimpleNamespace(
        es_version_free=es_version_free, activated=activated, edition_badge=QLabel(),
    )


def test_edition_badge_shows_free_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=True)
    update_edition_badge(win)
    assert win.edition_badge.text() == "FREE"
    assert win.edition_badge.property("uiVariant") == "free"


def test_edition_badge_shows_licenciada_when_activated(app):
    win = _make_win(es_version_free=False, activated=True)
    update_edition_badge(win)
    assert win.edition_badge.text() == "LICENCIADA"
    assert win.edition_badge.property("uiVariant") == "licensed"


def test_edition_badge_shows_sin_activar_when_licensed_but_not_activated(app):
    win = _make_win(es_version_free=False, activated=False)
    update_edition_badge(win)
    assert win.edition_badge.text() == "SIN ACTIVAR"
    assert win.edition_badge.property("uiVariant") == "unactivated"


def test_edition_badge_variants_are_recognized_by_set_variant(app):
    """VALID_VARIANTS degrada a "default" cualquier nombre desconocido --
    esto habría hecho que la insignia nunca cogiera color."""
    from ui.visual import VALID_VARIANTS
    assert {"free", "licensed", "unactivated"} <= VALID_VARIANTS
