"""Contrato de ui.nav_top.build_nav_top: mismo comportamiento de navegación
que el riel lateral que sustituye, pero como barra horizontal."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QHBoxLayout

from ui.nav_sections import NAV_DOWNLOAD, NAV_FAV, NAV_HOME, NAV_TOP_HEIGHT
from ui.nav_top import build_nav_top, toggle_library_sidebar


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win(*, es_version_free=False, activated=True):
    win = SimpleNamespace(
        es_version_free=es_version_free,
        activated=activated,
        navigation=SimpleNamespace(on_nav_changed=Mock()),
        settings={"accent_color": "#c9a227"},
        # build_more_menu_button()/build_global_search_button() (ver
        # ui.more_menu) conectan sus acciones a estos controladores -- solo
        # hace falta que existan como Mock, ninguna de estas pruebas
        # ejerce el menú "Más ▾" en sí (eso lo cubre tests/test_more_menu.py).
        dialogs=Mock(), library=Mock(), catalog=Mock(), epg=Mock(), updates=Mock(),
    )
    return win


def test_nav_top_is_horizontal_with_fixed_height(app):
    win = _make_win()
    bar = build_nav_top(win)
    assert isinstance(bar.layout(), QHBoxLayout)
    assert bar.objectName() == "navTopBar"
    assert bar.height() == NAV_TOP_HEIGHT


def test_nav_top_builds_six_sections_for_activated_vip(app):
    win = _make_win(es_version_free=False, activated=True)
    bar = build_nav_top(win)  # noqa: F841 -- kept alive so Qt doesn't GC its child buttons
    assert len(win.nav_group.buttons()) == 6
    # isHidden() checks the widget's own explicit hidden flag; isVisible()
    # would require the whole ancestor chain (including `bar`) to be shown
    # on screen, which never happens in this headless unit test.
    assert not win.nav_group.button(NAV_DOWNLOAD).isHidden()


def test_nav_top_hides_downloads_for_unactivated_vip(app):
    win = _make_win(es_version_free=False, activated=False)
    bar = build_nav_top(win)  # noqa: F841
    assert win.nav_group.button(NAV_DOWNLOAD).isHidden()


def test_nav_top_omits_downloads_entirely_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    bar = build_nav_top(win)  # noqa: F841
    assert win.nav_group.button(NAV_DOWNLOAD) is None
    assert len(win.nav_group.buttons()) == 5


def test_nav_top_home_button_starts_checked(app):
    win = _make_win()
    bar = build_nav_top(win)  # noqa: F841
    assert win.nav_group.button(NAV_HOME).isChecked()


def test_nav_top_clicking_a_button_notifies_navigation_controller(app):
    win = _make_win()
    bar = build_nav_top(win)  # noqa: F841
    win.nav_group.button(NAV_FAV).click()
    win.navigation.on_nav_changed.assert_called_once_with(NAV_FAV)


def test_toggle_library_sidebar_updates_visibility(app):
    win = _make_win()
    win.library_sidebar = Mock()
    bar = build_nav_top(win)  # noqa: F841
    toggle_library_sidebar(win, True)
    win.library_sidebar.setVisible.assert_called_once_with(True)
