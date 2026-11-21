"""Contrato de ui.nav_rail.build_nav_rail: raíl lateral de navegación (208 px,
64 px en modo compacto) que deja sus botones como atributos de `win`
(nav_group, library_toggle_btn, settings_btn, more_menu_btn...) y lleva la
tarjeta «VPN activa» en la edición con licencia."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QVBoxLayout, QWidget

from ui import palette
from ui.nav_rail import (
    RAIL_COMPACT_BELOW, RAIL_COMPACT_WIDTH, RAIL_WIDTH, build_nav_rail,
    toggle_library_sidebar, update_nav_rail_compact,
)
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HOME, NAV_TV, SECTION_COLORS, SECTION_VARIANTS,
)
from ui.style.builder import build_style


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def app_font():
    """Figtree registrada una vez: sin ella, la plataforma offscreen mide
    cada glifo como una caja de 14 px y el texto parece el doble de ancho."""
    from ui.application import _register_app_font

    QApplication.instance() or QApplication([])
    _register_app_font()


def test_rail_paints_its_panel_background(app):
    """NavRail es una subclase de QWidget: sin WA_StyledBackground, Qt no
    pinta el fondo/borde de la hoja de estilos y se ve el fondo de debajo."""
    win = _make_win()
    host = QWidget()
    host.setObjectName("railHost")
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    rail = build_nav_rail(win)
    host_layout.addWidget(rail)
    app.setStyleSheet(build_style() + "\nQWidget#railHost { background-color: #ff0000; }")
    try:
        host.resize(RAIL_WIDTH, 600)
        host.show()
        app.processEvents()
        img = host.grab().toImage()
        # Margen derecho del raíl, a media altura: ni botones ni borde.
        assert img.pixelColor(RAIL_WIDTH - 5, 300).name() == palette.BG_PANEL.lower()
        # El borde derecho también se pinta.
        assert img.pixelColor(RAIL_WIDTH - 1, 300).name() == palette.BORDER.lower()
        # El área desplazable de las secciones tampoco tapa el panel: hueco
        # libre bajo «Biblioteca», dentro del área.
        below_library = win.library_toggle_btn.mapTo(
            host, win.library_toggle_btn.rect().bottomLeft()
        )
        scroll_bottom = rail.sections_scroll.mapTo(host, rail.sections_scroll.rect().bottomLeft())
        assert below_library.y() + 6 < scroll_bottom.y()
        assert img.pixelColor(RAIL_WIDTH // 2, below_library.y() + 6).name() == palette.BG_PANEL.lower()
    finally:
        app.setStyleSheet("")
        host.hide()


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


def test_nav_rail_is_vertical_with_fixed_width(app):
    win = _make_win()
    bar = build_nav_rail(win)
    assert isinstance(bar.layout(), QVBoxLayout)
    assert bar.objectName() == "navRail"
    assert bar.width() == 208
    assert (RAIL_WIDTH, RAIL_COMPACT_WIDTH, RAIL_COMPACT_BELOW) == (208, 64, 1000)


def test_nav_rail_builds_six_sections_for_activated_vip(app):
    win = _make_win(es_version_free=False, activated=True)
    bar = build_nav_rail(win)  # noqa: F841 -- kept alive so Qt doesn't GC its child buttons
    assert len(win.nav_group.buttons()) == 7
    # isHidden() checks the widget's own explicit hidden flag; isVisible()
    # would require the whole ancestor chain (including `bar`) to be shown
    # on screen, which never happens in this headless unit test.
    assert not win.nav_group.button(NAV_DOWNLOAD).isHidden()


def test_nav_rail_hides_downloads_for_unactivated_vip(app):
    win = _make_win(es_version_free=False, activated=False)
    bar = build_nav_rail(win)  # noqa: F841
    assert win.nav_group.button(NAV_DOWNLOAD).isHidden()


def test_nav_rail_omits_downloads_entirely_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    bar = build_nav_rail(win)  # noqa: F841
    assert win.nav_group.button(NAV_DOWNLOAD) is None
    assert len(win.nav_group.buttons()) == 6


def test_nav_rail_home_button_starts_checked(app):
    win = _make_win()
    bar = build_nav_rail(win)  # noqa: F841
    assert win.nav_group.button(NAV_HOME).isChecked()


def test_nav_rail_clicking_a_button_notifies_navigation_controller(app):
    win = _make_win()
    bar = build_nav_rail(win)  # noqa: F841
    win.nav_group.button(NAV_FAV).click()
    win.navigation.on_nav_changed.assert_called_once_with(NAV_FAV)


def test_toggle_library_sidebar_updates_visibility(app):
    win = _make_win()
    win.library_sidebar = Mock()
    bar = build_nav_rail(win)  # noqa: F841
    toggle_library_sidebar(win, True)
    win.library_sidebar.setVisible.assert_called_once_with(True)


def test_rail_is_208px_and_collapses_to_icons_below_1000px(app):
    win = _make_win()
    bar = build_nav_rail(win)
    update_nav_rail_compact(win, 999)
    assert bar.width() == 64
    for btn in win._nav_rail_text_buttons:
        assert btn.toolButtonStyle() == Qt.ToolButtonIconOnly
    update_nav_rail_compact(win, 1000)
    assert bar.width() == 208
    for btn in win._nav_rail_text_buttons:
        assert btn.toolButtonStyle() == Qt.ToolButtonTextBesideIcon


def test_update_nav_rail_compact_never_hides_buttons(app):
    """Colapsa a solo iconos, nunca a menú hamburguesa (spec v8 §5.4)."""
    win = _make_win()
    bar = build_nav_rail(win)  # noqa: F841
    update_nav_rail_compact(win, 600)
    for btn in win._nav_rail_text_buttons:
        assert not btn.isHidden()
        assert btn.toolButtonStyle() == Qt.ToolButtonIconOnly


def test_free_edition_has_no_download_button(app):
    win = _make_win(es_version_free=True, activated=True)
    bar = build_nav_rail(win)
    assert win.nav_group.button(NAV_DOWNLOAD) is None
    texts = [b.text() for b in bar.findChildren(QToolButton)]
    assert "Descargas" not in texts


def test_rail_exposes_same_widgets_as_the_top_bar(app):
    win = _make_win()
    bar = build_nav_rail(win)  # noqa: F841
    assert win.global_search_btn is not None
    assert win.more_menu_btn is not None
    assert win.library_toggle_btn.isCheckable()


def test_active_section_button_is_filled_with_its_ident(app):
    win = _make_win()
    bar = build_nav_rail(win)
    style = build_style()
    for nav_id, variant in ((NAV_HOME, "home"), (NAV_TV, "tv")):
        assert win.nav_group.button(nav_id).property("uiVariant") == SECTION_VARIANTS[nav_id] == variant
    tv_rule = style.split('QToolButton#navButton[uiVariant="tv"]:checked {')[1].split("}")[0]
    assert f"background-color: {SECTION_COLORS[NAV_TV]}" in tv_rule
    assert f"color: {palette.INK}" in tv_rule
    # El icono activo también va en tinta.
    app.setStyleSheet(style)
    try:
        bar.show()
        btn = win.nav_group.button(NAV_TV)
        btn.setChecked(True)
        img = btn.grab().toImage()
        assert img.pixelColor(4, img.height() // 2).name() == SECTION_COLORS[NAV_TV].lower()
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_compact_rail_footer_fits_within_64px(app):
    win = _make_win()
    bar = build_nav_rail(win)
    app.setStyleSheet(build_style())
    try:
        update_nav_rail_compact(win, 999)
        bar.setFixedHeight(600)
        bar.show()
        assert bar.layout().minimumSize().width() <= RAIL_COMPACT_WIDTH
        for btn in (win.settings_btn, win.more_menu_btn, win.global_search_btn):
            geo = btn.geometry()
            assert geo.width() >= btn.sizeHint().width()
            assert geo.left() >= 0 and geo.right() < RAIL_COMPACT_WIDTH
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_vpn_card_is_absent_in_free_edition(app):
    win = _make_win(es_version_free=True, activated=True)
    bar = build_nav_rail(win)
    assert bar.vpn_card is None
    assert bar.findChild(QWidget, "navVpnCard") is None
    bar.set_vpn_status(True, "Japón (VPNGate)")  # no-op, no rompe


def test_vpn_card_is_absent_when_not_activated(app):
    win = _make_win(es_version_free=False, activated=False)
    bar = build_nav_rail(win)
    assert bar.vpn_card is None


def test_vpn_card_is_hidden_while_disconnected(app):
    win = _make_win()
    bar = build_nav_rail(win)
    assert bar.vpn_card is not None
    assert bar.vpn_card.isHidden()
    bar.set_vpn_status(False, "Japón (VPNGate)")
    assert bar.vpn_card.isHidden()


def test_vpn_card_shows_the_server_when_connected(app):
    win = _make_win()
    bar = build_nav_rail(win)
    bar.set_vpn_status(True, "Japón (VPNGate)")
    assert not bar.vpn_card.isHidden()
    texts = [label.text() for label in bar.vpn_card.findChildren(QLabel)]
    assert "VPN activa" in texts
    assert "Japón (VPNGate)" in texts
    bar.set_vpn_status(False, "Japón (VPNGate)")
    assert bar.vpn_card.isHidden()


def test_vpn_card_sits_above_settings_and_fits_the_compact_rail(app):
    win = _make_win()
    bar = build_nav_rail(win)
    layout = bar.layout()
    assert layout.indexOf(bar.vpn_card) == layout.indexOf(win.settings_btn) - 1
    app.setStyleSheet(build_style())
    try:
        bar.set_vpn_status(True, "Japón (VPNGate)")
        update_nav_rail_compact(win, 999)
        bar.setFixedHeight(700)
        bar.show()
        assert bar.layout().minimumSize().width() <= RAIL_COMPACT_WIDTH
        geo = bar.vpn_card.geometry()
        assert geo.left() >= 0 and geo.right() < RAIL_COMPACT_WIDTH
        assert "Japón (VPNGate)" in bar.vpn_card.toolTip()
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_full_width_rail_labels_do_not_clip(app, app_font):
    """A 208 px, «Biblioteca» y el resto de etiquetas caben enteras, y cada
    entrada ocupa todo el ancho útil del raíl (bloque de sección parejo).
    Con la fuente real registrada (ver app_font)."""
    win = _make_win()
    bar = build_nav_rail(win)
    app.setStyleSheet(build_style())
    try:
        update_nav_rail_compact(win, 1320)
        bar.setFixedHeight(700)
        bar.show()
        usable = RAIL_WIDTH - 24
        for btn in win._nav_rail_text_buttons:
            assert btn.sizeHint().width() <= usable, btn.text()
            assert btn.width() == usable, btn.text()
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_settings_button_opens_settings(app):
    win = _make_win()
    bar = build_nav_rail(win)  # noqa: F841
    win.settings_btn.click()
    win.dialogs.open_settings.assert_called_once_with()
    assert win.settings_btn in win._nav_rail_text_buttons


def _footer(win, bar):
    widgets = [bar.vpn_card] if bar.vpn_card is not None and not bar.vpn_card.isHidden() else []
    return widgets + [win.settings_btn, win.more_menu_btn, win.global_search_btn]


def _show_rail_at_height(app, win, bar, height, *, width=999):
    bar.set_vpn_status(True, "Japón (VPNGate)")
    update_nav_rail_compact(win, width)
    bar.setFixedHeight(height)
    bar.show()
    for _ in range(3):
        app.processEvents()


def _assert_no_overlap(widgets):
    rects = sorted(
        (w.mapTo(w.window(), w.rect().topLeft()).y(), w.height(), w.toolTip()) for w in widgets
    )
    for (top, height, name), (next_top, _h, next_name) in zip(rects, rects[1:]):
        assert top + height <= next_top, f"{name} pisa a {next_name}"


def test_short_rail_switches_to_dense_and_fits_without_scrolling(app, app_font):
    """A 860 × 580 el raíl tiene ~421 px: con la edición activada (siete
    secciones y la tarjeta de VPN) solo cabe en densidad compacta."""
    win = _make_win()
    bar = build_nav_rail(win)
    app.setStyleSheet(build_style())
    try:
        _show_rail_at_height(app, win, bar, 421)
        assert bar.is_dense()
        assert bar.sections_scroll.verticalScrollBar().maximum() == 0
        entries = win.nav_group.buttons() + [win.library_toggle_btn] + _footer(win, bar)
        _assert_no_overlap(entries)
        for btn in win._nav_rail_text_buttons:
            # Densidad compacta, pero nunca por debajo de un objetivo cómodo.
            assert btn.height() >= 32, btn.toolTip()
        # Al volver a tener alto, recupera la densidad normal.
        bar.setFixedHeight(760)
        for _ in range(3):
            app.processEvents()
        assert not bar.is_dense()
        assert win.nav_group.button(NAV_HOME).height() >= 44
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_tall_rail_keeps_the_normal_density(app, app_font):
    win = _make_win()
    bar = build_nav_rail(win)
    app.setStyleSheet(build_style())
    try:
        _show_rail_at_height(app, win, bar, 760, width=1320)
        assert not bar.is_dense()
        assert bar.sections_scroll.verticalScrollBar().maximum() == 0
    finally:
        app.setStyleSheet("")
        bar.hide()


def test_very_short_rail_scrolls_the_sections_and_keeps_the_footer(app, app_font):
    """Si ni la densidad compacta basta, las secciones se desplazan y el pie
    (VPN, Ajustes, Más, búsqueda) sigue entero a la vista."""
    win = _make_win()
    bar = build_nav_rail(win)
    app.setStyleSheet(build_style())
    try:
        _show_rail_at_height(app, win, bar, 300)
        assert bar.is_dense()
        assert bar.sections_scroll.verticalScrollBar().maximum() > 0
        footer = _footer(win, bar)
        _assert_no_overlap([bar.sections_scroll] + footer)
        for widget in footer:
            assert widget.isVisible()
            assert widget.visibleRegion().boundingRect().size() == widget.size(), widget.toolTip()
            geo = widget.geometry()
            assert geo.top() >= 0 and geo.bottom() < bar.height()
        # Las secciones siguen alcanzables: el área las lleva a la vista.
        last = win.library_toggle_btn
        bar.sections_scroll.ensureWidgetVisible(last)
        app.processEvents()
        assert last.visibleRegion().boundingRect().size() == last.size()
    finally:
        app.setStyleSheet("")
        bar.hide()
