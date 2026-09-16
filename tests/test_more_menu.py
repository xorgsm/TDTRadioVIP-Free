"""Contrato de ui.more_menu: el botón "Más ▾" y el icono de búsqueda global
que sustituyen a la barra de menú clásica (ui/app_menu.py, retirada) --
ver docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md §5.1/§5.2."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from ui.more_menu import build_global_search_button, build_more_menu_button
from ui.nav_sections import NAV_DOWNLOAD


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win(*, es_version_free=False, activated=True):
    return SimpleNamespace(
        es_version_free=es_version_free,
        activated=activated,
        dialogs=Mock(), library=Mock(), catalog=Mock(), epg=Mock(), updates=Mock(),
        nav_group=Mock(), download_panel=Mock(),
    )


def _action_texts(menu: QMenu) -> list:
    return [a.text() for a in menu.actions()]


def _find_action(menu: QMenu, text: str):
    """Busca una acción por texto exacto en el menú y en sus submenús
    directos (un solo nivel de anidado, suficiente para esta estructura)."""
    for action in menu.actions():
        if action.text() == text:
            return action
        submenu = action.menu()
        if submenu is not None:
            for sub_action in submenu.actions():
                if sub_action.text() == text:
                    return sub_action
    raise AssertionError(f"No se encontró la acción {text!r} en el menú")


def test_more_menu_has_all_top_level_categories(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    assert _action_texts(btn.menu()) == [
        "Gestión de contenido", "Grabaciones", "Herramientas de audio",
        "Guía EPG", "VPN…", "Ajustes", "Ayuda y sistema",
    ]


def test_more_menu_omits_audio_tools_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    btn = build_more_menu_button(win)
    assert "Herramientas de audio" not in _action_texts(btn.menu())


def test_more_menu_vpn_opens_vpn_dialog(app):
    """VPN vivía escondida al final del scroll de Preferencias -- ahora es
    una entrada de primer nivel en "Más ▾" (ver ui.dialog_actions.open_vpn_dialog)."""
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "VPN…").trigger()
    win.dialogs.open_vpn_dialog.assert_called_once_with()


def test_more_menu_omits_vpn_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    btn = build_more_menu_button(win)
    assert "VPN…" not in _action_texts(btn.menu())


def test_more_menu_omits_vpn_when_unactivated(app):
    win = _make_win(es_version_free=False, activated=False)
    btn = build_more_menu_button(win)
    assert "VPN…" not in _action_texts(btn.menu())


def test_more_menu_shows_activate_vip_when_licensed_and_unactivated(app):
    win = _make_win(es_version_free=False, activated=False)
    btn = build_more_menu_button(win)
    accion = _find_action(btn.menu(), "Activar VIP…")
    assert win.activate_vip_action is accion


def test_more_menu_hides_activate_vip_once_activated(app):
    win = _make_win(es_version_free=False, activated=True)
    btn = build_more_menu_button(win)
    ajustes = next(a.menu() for a in btn.menu().actions() if a.text() == "Ajustes")
    assert "Activar VIP…" not in [a.text() for a in ajustes.actions()]
    assert not hasattr(win, "activate_vip_action")


def test_more_menu_hides_activate_vip_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    btn = build_more_menu_button(win)
    ajustes = next(a.menu() for a in btn.menu().actions() if a.text() == "Ajustes")
    assert "Activar VIP…" not in [a.text() for a in ajustes.actions()]


def test_more_menu_guia_epg_opens_epg_dialog(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "Guía EPG").trigger()
    win.epg.open_dialog.assert_called_once_with()


def test_more_menu_actualizar_canales_tv_forces_reload(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "Actualizar canales TV").trigger()
    win.catalog.load_tv_channels.assert_called_once_with(force=True)


def test_more_menu_diagnosticar_opens_stream_diagnostics(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "Diagnosticar canales y emisoras…").trigger()
    win.dialogs.open_stream_diagnostics.assert_called_once_with()


def test_more_menu_ecualizador_opens_equalizer_dialog(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "Ecualizador…").trigger()
    win.dialogs.open_equalizer_dialog.assert_called_once_with()


def test_more_menu_audio_tool_jumps_to_download_tab(app):
    win = _make_win()
    btn = build_more_menu_button(win)
    _find_action(btn.menu(), "Convertir").trigger()
    win.nav_group.button.assert_called_once_with(NAV_DOWNLOAD)
    win.nav_group.button.return_value.click.assert_called_once_with()
    win.download_panel.tabs.setCurrentIndex.assert_called_once_with(4)


def test_global_search_button_opens_command_palette(app):
    win = _make_win()
    btn = build_global_search_button(win)
    btn.click()
    win.dialogs.open_command_palette.assert_called_once_with()
