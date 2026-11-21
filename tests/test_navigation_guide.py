"""Sección «Guía» del raíl (NAV_GUIDE): une GuideView y GuideDetailPanel en la
ventana principal. La ventana lleva la hoja de estilos y las fuentes reales
(ver test_main_window_min_size.py); por defecto es la edición Free."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from ui.nav_sections import (
    NAV_FAV, NAV_GUIDE, NAV_RADIO, NAV_TV, SECTION_COLORS, SECTION_TITLES,
    SECTION_VARIANTS,
)


@pytest.fixture
def styled_window(make_window):
    from ui.application import _register_app_font
    from ui.style import build_style

    _register_app_font()

    def _make(width=1320, height=860, **kwargs):
        win = make_window(width, height, **kwargs)
        win.setStyleSheet(build_style())
        QApplication.processEvents()
        win.resize(width, height)
        QApplication.processEvents()
        return win

    return _make


def _rect(widget):
    return widget.rect().translated(widget.mapTo(widget.window(), widget.rect().topLeft()))


def test_guide_section_constants():
    assert NAV_GUIDE == 6
    assert SECTION_TITLES[NAV_GUIDE] == "Guía"
    assert SECTION_VARIANTS[NAV_GUIDE] == "guide"
    from ui import palette

    assert SECTION_COLORS[NAV_GUIDE] == palette.ACCENT_GUIDE


def test_guide_section_switches_stack_page(make_window):
    win = make_window()
    win.nav_group.button(NAV_GUIDE).click()
    QApplication.processEvents()
    assert win.stack.currentIndex() == NAV_GUIDE
    assert win.stack.currentWidget() is win.guide_page
    assert win.guide_view.parent() is win.guide_page
    assert win.guide_detail.parent() is win.guide_page
    assert win.guide_detail.width() == 300
    assert win.section_title.text() == "Guía"


def test_guide_button_sits_between_radio_and_favorites(make_window):
    win = make_window()
    rail = win.nav_rail.sections.layout()
    order = [
        win.nav_group.id(rail.itemAt(i).widget())
        for i in range(rail.count())
        if rail.itemAt(i).widget() in win.nav_group.buttons()
    ]
    assert order.index(NAV_RADIO) + 1 == order.index(NAV_GUIDE)
    assert order.index(NAV_GUIDE) + 1 == order.index(NAV_FAV)


def test_open_dialog_navigates_to_guide(make_window, monkeypatch):
    win = make_window()
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: pytest.fail("sin diálogo"))
    win.epg.open_dialog()
    assert win.nav_group.button(NAV_GUIDE).isChecked()
    assert win.stack.currentIndex() == NAV_GUIDE


def test_guide_hidden_catalog_toolbar_controls(make_window):
    win = make_window()
    win.nav_group.button(NAV_TV).click()
    QApplication.processEvents()
    assert win.tv_view_toggle.isVisible() and win.catalog_sort.isVisible()
    win.nav_group.button(NAV_GUIDE).click()
    QApplication.processEvents()
    for widget in (win.group_filter, win.catalog_sort, win.health_filter, win.tv_view_toggle,
                   win.epg_btn, win.search_box):
        assert not widget.isVisible(), widget.objectName()


def test_tune_from_guide_selects_tv_section(make_window, monkeypatch):
    win = make_window()
    win.tv_channels_data = [SimpleNamespace(tvg_id="la1.es", name="La 1", url="http://x/1", logo="")]
    played = []
    monkeypatch.setattr(win.playback, "play", lambda *a: played.append(a))
    win.nav_group.button(NAV_GUIDE).click()
    win.guide_detail.tune_requested.emit("la1.es")
    QApplication.processEvents()
    assert played and played[0][1] == "La 1"
    assert win.stack.currentIndex() == NAV_TV
    assert win.nav_group.button(NAV_TV).isChecked()


def test_programme_selection_reaches_the_detail_panel(make_window):
    win = make_window()
    info = {
        "tvg_id": "la1.es", "channel_name": "La 1", "channel_url": "http://x/1",
        "title": "Telediario", "start": "20300101210000 +0000", "stop": "20300101220000 +0000",
        "description": "Noticias",
    }
    win.guide_view.programme_selected.emit(info)
    assert win.guide_detail.title_text() == "Telediario"


def test_recording_is_off_in_free_edition(make_window):
    win = make_window()
    assert win.guide_detail.record_btn.isHidden() and win.guide_detail.series_btn.isHidden()


def test_epg_load_feeds_the_guide(make_window):
    win = make_window()
    win.tv_channels_data = [SimpleNamespace(tvg_id="la1.es", name="La 1", url="u", logo="")]
    from core.epg import channel_key

    win.epg._on_loaded({channel_key("la1.es"): []})
    assert channel_key("la1.es") in win.guide_view._guide


def test_entering_the_guide_refreshes_channels_and_favorites(make_window):
    win = make_window()
    channel = SimpleNamespace(tvg_id="la1.es", name="La 1", url="u", logo="", group="General")
    win.tv_channels_data = [channel]
    win.favorites = [{"type": "tv", "name": "La 1", "url": "u"}]
    win.nav_group.button(NAV_GUIDE).click()
    assert win.guide_view._all_channels == [channel]
    assert win.guide_view._favorites == {"La 1"}


def _assert_guide_clear_of_rail(win):
    rail = _rect(win.nav_rail)
    view, detail = _rect(win.guide_view), _rect(win.guide_detail)
    grid = _rect(win.guide_view.grid)
    assert win.guide_view.isVisible() and win.guide_detail.isVisible()
    assert rail.right() < view.left()
    assert view.right() < detail.left()
    assert grid.right() < detail.left()
    assert win.rect().contains(view) and win.rect().contains(detail)
    # La parrilla conserva un ancho útil, no una rendija.
    assert grid.width() >= 200, grid
    assert detail.width() == 300
    # Los botones del panel quedan dentro de él.
    for button in (win.guide_detail.view_btn, win.guide_detail.remind_btn):
        assert detail.contains(_rect(button)), button.text()


@pytest.mark.parametrize("licensed", [False, True])
def test_guide_and_rail_do_not_overlap_at_860x580(styled_window, licensed):
    kwargs = {}
    if licensed:
        pytest.importorskip("core.caster")
        kwargs = {"es_version_free": False, "activated": True}
    win = styled_window(860, 580, **kwargs)
    win.nav_group.button(NAV_GUIDE).click()
    for _ in range(3):
        QApplication.processEvents()
    assert win.nav_rail.width() == 64
    _assert_guide_clear_of_rail(win)
    entries = [b for b in win.nav_group.buttons() if b.isVisible()]
    entries += [win.library_toggle_btn, win.settings_btn, win.more_menu_btn, win.global_search_btn]
    rects = sorted(((_rect(w), w.toolTip()) for w in entries), key=lambda item: item[0].top())
    rail = _rect(win.nav_rail)
    for (upper, un), (lower, ln) in zip(rects, rects[1:]):
        assert upper.bottom() < lower.top(), f"{un} pisa a {ln}"
    for rect, name in rects:
        assert rail.contains(rect), name
    for widget in entries:
        assert widget.visibleRegion().boundingRect().size() == widget.size(), widget.toolTip()
    assert licensed is False or len([b for b in win.nav_group.buttons() if b.isVisible()]) == 7
