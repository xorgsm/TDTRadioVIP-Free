"""La ventana sigue siendo usable en su tamaño mínimo (860 × 580) y el dock
conserva lo esencial por debajo de 700 px (DESIGN.md, «Essential Controls
Survive»).

A diferencia de los tests de carcasa de test_main_window_widget_contract.py,
aquí la ventana lleva la hoja de estilos de producción (build_style) y las
fuentes empaquetadas registradas: sin ellas, la plataforma offscreen mide
botones más bajos que los reales y un raíl que no cabe parece que sí cabe.
La fixture make_window vive en tests/conftest.py.
"""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def styled_window(make_window):
    """Ventana con la hoja de estilos y las fuentes de la app real."""
    from ui.application import _register_app_font
    from ui.style import build_style

    _register_app_font()

    def _make(width, height, **kwargs):
        win = make_window(width, height, **kwargs)
        win.setStyleSheet(build_style())
        QApplication.processEvents()
        win.resize(width, height)
        QApplication.processEvents()
        return win

    return _make


def _rect_in_window(widget):
    top_left = widget.mapTo(widget.window(), widget.rect().topLeft())
    return widget.rect().translated(top_left)


def _assert_inside_window(win, widget):
    assert widget.isVisible(), widget.objectName()
    rect = _rect_in_window(widget)
    assert win.rect().contains(rect), (widget.objectName(), rect, win.rect())


def _rail_entries(win):
    """Lo que el raíl muestra, de arriba abajo: secciones, Biblioteca, tarjeta
    de VPN (si está a la vista), Ajustes, Más y búsqueda."""
    entries = [btn for btn in win.nav_group.buttons() if btn.isVisible()]
    entries.append(win.library_toggle_btn)
    card = win.nav_rail.vpn_card
    if card is not None and card.isVisible():
        entries.append(card)
    entries += [win.settings_btn, win.more_menu_btn, win.global_search_btn]
    return entries


def _assert_rail_fits(win):
    """Cada entrada del raíl se ve entera dentro del raíl (sin desplazar) y
    ninguna se monta sobre la siguiente."""
    rail = win.nav_rail
    rail_rect = _rect_in_window(rail)
    rects = []
    for widget in _rail_entries(win):
        _assert_inside_window(win, widget)
        rect = _rect_in_window(widget)
        assert rail_rect.contains(rect), (widget.toolTip(), rect, rail_rect)
        # Lo que de verdad se ve: un botón dentro de un área desplazable
        # puede tener geometría «dentro» del raíl y estar recortado.
        assert widget.visibleRegion().boundingRect().size() == widget.size(), widget.toolTip()
        rects.append((rect, widget.toolTip()))
    rects.sort(key=lambda item: item[0].top())
    for (upper, upper_name), (lower, lower_name) in zip(rects, rects[1:]):
        assert upper.bottom() < lower.top(), f"{upper_name} pisa a {lower_name}"


def _assert_window_usable(win):
    assert (win.width(), win.height()) == (860, 580)
    # Raíl en iconos.
    assert win.nav_rail.width() == 64
    for widget in (win.play_btn, win.stop_btn, win.top_search_btn, win.nav_rail):
        _assert_inside_window(win, widget)
    _assert_rail_fits(win)


def test_window_is_usable_at_860x580(styled_window):
    win = styled_window(860, 580)
    _assert_window_usable(win)


def test_activated_window_is_usable_at_860x580_with_vpn_card(styled_window):
    """La edición activada es la más alta: siete secciones y la tarjeta de VPN."""
    pytest.importorskip("core.caster")
    win = styled_window(860, 580, es_version_free=False, activated=True)
    assert len([b for b in win.nav_group.buttons() if b.isVisible()]) == 7
    win.nav_rail.set_vpn_status(True, "Japón (VPNGate)")
    QApplication.processEvents()
    assert win.nav_rail.vpn_card.isVisible()
    _assert_window_usable(win)


def test_dock_keeps_essential_controls_below_700px(styled_window):
    from ui.now_playing_bar_builder import set_quality_badge

    win = styled_window(1320, 860)
    set_quality_badge(win, "Señal · estable", "stable")
    # El mínimo normal de la ventana es 860 px; en PiP baja a 320, así que
    # el dock sí puede quedarse por debajo de 700.
    win.setMinimumSize(320, 240)
    win.resize(690, 580)
    QApplication.processEvents()
    assert win.now_playing_bar.width() == 690
    dock = _rect_in_window(win.now_playing_bar)
    for widget in (win.play_btn, win.stop_btn, win.record_btn, win.volume_slider, win.more_btn):
        _assert_inside_window(win, widget)
        assert dock.contains(_rect_in_window(widget)), widget.objectName()
    for widget in (win.dock_quality_badge, win.pip_btn, win.sleep_btn):
        assert not widget.isVisible(), widget.objectName()
    # La etiqueta no reaparece por recibir texto mientras el dock es estrecho.
    set_quality_badge(win, "Sin señal", "down")
    assert not win.dock_quality_badge.isVisible()

    win.resize(1320, 860)
    QApplication.processEvents()
    for widget in (win.dock_quality_badge, win.pip_btn, win.sleep_btn):
        assert widget.isVisible(), widget.objectName()


@pytest.mark.parametrize("licensed", [False, True])
def test_default_size_keeps_the_normal_rail_density(styled_window, licensed):
    """A 1320 × 860 todo cabe con el relleno normal: la densidad compacta es
    solo para ventanas bajas."""
    kwargs = {}
    if licensed:
        pytest.importorskip("core.caster")
        kwargs = {"es_version_free": False, "activated": True}
    win = styled_window(1320, 860, **kwargs)
    win.nav_rail.set_vpn_status(True, "Japón (VPNGate)")
    QApplication.processEvents()
    assert win.nav_rail.width() == 208
    assert not win.nav_rail.is_dense()
    _assert_rail_fits(win)


def test_leaving_pip_restores_the_startup_minimums(make_window, monkeypatch):
    """Salir de la ventana flotante devuelve los mínimos del arranque
    (860 × 580 y 330 px de contenido), no unos más anchos."""
    win = make_window(1320, 860)
    startup_min = (win.minimumWidth(), win.minimumHeight())
    startup_content = win.content_widget.minimumWidth()
    assert startup_min == (860, 580)
    assert startup_content == 330
    monkeypatch.setattr(win, "move", lambda *_a: None)
    win.window_chrome.enter_pip_mode()
    win.window_chrome.exit_pip_mode()
    QApplication.processEvents()
    assert (win.minimumWidth(), win.minimumHeight()) == startup_min
    assert win.content_widget.minimumWidth() == startup_content
