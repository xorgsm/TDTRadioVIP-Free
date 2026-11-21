"""Vista de parrilla de la Guía (ui.guide_view.GuideView).

Pintado propio sobre core.guide_grid.build_rows: regla de horas, línea de
«ahora» y celdas posicionadas. Se verifica de forma estructural (rectángulos
de celda, textos pintados, geometrías con la hoja de estilos real), porque
los tests no ven la pantalla.
"""
import time
from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from core.channels import Channel
from core.epg import Programme, _prepare_guide, channel_key
from ui import palette
from ui.guide_view import (
    GUIDE_FILTERS, MAX_PAINTED_ROWS, NO_PROGRAMMING, GuideView, now_cell_colors,
)

NOW = datetime(2026, 11, 20, 21, 10)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def app_font():
    """Figtree y Barlow registradas: sin ellas offscreen mide mal el texto."""
    from ui.application import _register_app_font

    QApplication.instance() or QApplication([])
    _register_app_font()


def _xt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _prog(title, start, stop, tvg="La1.es@SD", description=""):
    return Programme(channel_id=tvg, title=title, start=_xt(start), stop=_xt(stop),
                     description=description)


def _guide(programmes_by_tvg):
    return _prepare_guide({channel_key(tvg): list(progs) for tvg, progs in programmes_by_tvg.items()})


def _view(channels, guide, *, favorites=(), size=(900, 500)):
    view = GuideView(channels, guide, favorites=favorites, clock=lambda: NOW)
    view.resize(*size)
    view.show()
    QApplication.processEvents()
    return view


def _la1():
    return Channel(name="La 1", url="http://la1/stream.m3u8", group="General", tvg_id="La1.es@SD")


def _la1_guide():
    return _guide({"La1.es@SD": [
        _prog("Telediario 2", NOW.replace(minute=0), NOW.replace(minute=45),
              description="Edición de la noche."),
        _prog("Cine: El Ministerio", NOW.replace(minute=45), NOW.replace(hour=23, minute=0)),
    ]})


def test_guide_view_paints_its_styled_background(app):
    view = _view([_la1()], _la1_guide())
    try:
        assert view.testAttribute(Qt.WA_StyledBackground)
        assert view.grid.testAttribute(Qt.WA_StyledBackground)
    finally:
        view.close()


def test_clicking_a_cell_emits_programme_selected_with_channel_data(app):
    view = _view([_la1()], _la1_guide())
    try:
        received = []
        view.programme_selected.connect(received.append)
        rect = view.grid.cell_rect(0, 0)
        assert rect.width() > 10 and view.grid.viewport().rect().contains(rect.center())
        QTest.mouseClick(view.grid.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
        assert received == [{
            "tvg_id": "La1.es@SD",
            "channel_name": "La 1",
            "channel_url": "http://la1/stream.m3u8",
            "title": "Telediario 2",
            "start": _xt(NOW.replace(minute=0)),
            "stop": _xt(NOW.replace(minute=45)),
            "description": "Edición de la noche.",
        }]
        # Fuera de toda celda (columna de canales) no se emite nada.
        QTest.mouseClick(view.grid.viewport(), Qt.LeftButton, Qt.NoModifier,
                         QPoint(10, rect.center().y()))
        assert len(received) == 1
    finally:
        view.close()


def test_opens_scrolled_to_now_with_the_running_cell_in_view(app):
    view = _view([_la1()], _la1_guide())
    try:
        viewport = view.grid.viewport().rect()
        x = view.grid.now_x()
        assert x is not None and view.grid.lane_left() <= x <= viewport.width()
        assert view.grid.cell_rect(0, 0).intersects(viewport)
    finally:
        view.close()


def test_favorites_filter_limits_rows(app):
    channels = [_la1(), Channel(name="La 2", url="http://la2", tvg_id="La2.es@SD"),
                Channel(name="Antena 3", url="http://a3", tvg_id="Antena3.es@SD")]
    view = _view(channels, _la1_guide(), favorites={"La 2"})
    try:
        assert view.row_count() == 3
        view.set_filter("favorites")
        assert view.row_count() == 1
        assert view.row(0).channel_name == "La 2"
        assert view.filter_chip("favorites").isChecked()
        view.set_favorites({"La 1", "Antena 3"})
        assert [view.row(i).channel_name for i in range(view.row_count())] == ["La 1", "Antena 3"]
        view.set_filter("all")
        assert view.row_count() == 3
    finally:
        view.close()


def test_cinema_and_sports_filters_use_the_channel_category(app):
    channels = [
        Channel(name="Cine A", url="u1", group="Movies", tvg_id="CineA.es"),
        Channel(name="Cine B", url="u2", group="Cine;General", tvg_id="CineB.es"),
        Channel(name="Gol", url="u3", group="sports", tvg_id="Gol.es"),
        Channel(name="Noticias", url="u4", group="News", tvg_id="N24.es"),
    ]
    view = _view(channels, {})
    try:
        view.set_filter("cinema")
        assert [view.row(i).channel_name for i in range(view.row_count())] == ["Cine A", "Cine B"]
        view.set_filter("sports")
        assert [view.row(i).channel_name for i in range(view.row_count())] == ["Gol"]
    finally:
        view.close()


def test_unknown_filter_is_rejected(app):
    view = GuideView([], {}, clock=lambda: NOW)
    assert set(GUIDE_FILTERS) == {"all", "favorites", "cinema", "sports"}
    with pytest.raises(ValueError):
        view.set_filter("news")


def test_chips_drive_day_and_filter(app):
    view = _view([_la1()], _la1_guide())
    try:
        view.filter_chip("cinema").click()
        assert view.current_filter() == "cinema"
        view.day_chip(1).click()
        assert view.current_day() == NOW.date() + timedelta(days=1)
        assert view.day_chip(1).isChecked() and not view.day_chip(0).isChecked()
        view.set_day(NOW.date() - timedelta(days=1))
        assert view.day_chip(-1).isChecked()
        assert view.title_text().startswith("AYER")
    finally:
        view.close()


def test_set_day_shows_that_days_programmes(app):
    tomorrow = NOW + timedelta(days=1)
    guide = _guide({"La1.es@SD": [
        _prog("Hoy", NOW.replace(minute=0), NOW.replace(minute=45)),
        _prog("Mañana", tomorrow.replace(minute=0), tomorrow.replace(minute=45)),
    ]})
    view = _view([_la1()], guide)
    try:
        assert [c.title for c in view.row(0).cells] == ["Hoy"]
        assert view.row(0).cells[0].is_now
        view.set_day(tomorrow.date())
        assert [c.title for c in view.row(0).cells] == ["Mañana"]
        assert not view.row(0).cells[0].is_now
        # Otro día que no es hoy no tiene línea de «ahora».
        assert view.grid.now_x() is None
        # Y abre en la franja de noche, no en la medianoche.
        assert view.grid.horizontalScrollBar().value() > 0
    finally:
        view.close()


def test_row_without_guide_shows_no_programming_text(app):
    channels = [_la1(), Channel(name="Sin Id", url="http://x"),
                Channel(name="La 2", url="http://la2", tvg_id="La2.es@SD")]
    view = _view(channels, _la1_guide())
    try:
        # El canal sin tvg_id también tiene fila (Review Focus del plan).
        assert [view.row(i).channel_name for i in range(view.row_count())] == ["La 1", "Sin Id", "La 2"]
        view.grid.grab()
        labels = view.grid.painted_labels()
        assert labels.count(NO_PROGRAMMING) == 2
        assert "Telediario 2" in labels
        assert "LA 2" in labels
    finally:
        view.close()


def test_paints_at_most_sixty_rows(app):
    channels = [Channel(name=f"C{i}", url=f"u{i}", tvg_id=f"C{i}.es") for i in range(200)]
    view = _view(channels, {}, size=(900, 6000))
    try:
        view.grid.grab()
        assert view.grid.painted_row_count() == MAX_PAINTED_ROWS
    finally:
        view.close()


def test_view_with_3000_channels_builds_under_one_second(app):
    channels = [Channel(name=f"Canal {i}", url=f"http://c/{i}", group="General", tvg_id=f"C{i}.es")
                for i in range(3000)]
    base = datetime.combine(NOW.date(), datetime.min.time())
    guide = _guide({
        f"C{i}.es": [_prog(f"P{i}-{h}", base + timedelta(hours=h), base + timedelta(hours=h + 1),
                           tvg=f"C{i}.es") for h in range(24)]
        for i in range(0, 3000, 2)
    })
    view = _view(channels, guide)
    try:
        started = time.perf_counter()
        view.refresh()
        view.grid.grab()
        elapsed = time.perf_counter() - started
        assert view.row_count() == 3000
        assert elapsed < 1.0, elapsed
    finally:
        view.close()


def test_programmes_lookup_does_not_break_on_unknown_guide_entries(app):
    """Canal con tvg_id pero sin programas: fila vacía, sin excepción al pulsar."""
    view = _view([Channel(name="La 2", url="u", tvg_id="La2.es@SD")], _la1_guide())
    try:
        assert view.row(0).cells == []
        QTest.mouseClick(view.grid.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(300, 60))
    finally:
        view.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_running_cell_uses_the_guide_ident_and_stays_readable(theme):
    from ui.style.colors import _contrast_ratio

    try:
        palette.apply_theme(theme)
        background, border, text = now_cell_colors()
        assert border == palette.ACCENT_GUIDE
        assert _contrast_ratio(text, background) >= 4.5
        assert background not in (palette.BG_CARD, palette.BG_PANEL)
    finally:
        palette.apply_theme("dark")


def _rect_in(widget, ancestor):
    return widget.rect().translated(widget.mapTo(ancestor, widget.rect().topLeft()))


# Página de la Guía a 860 × 580 medida con la ventana real (753 × 319) menos
# el panel de detalle de la tarea 11 (300 px): queda ~450 × 319. Se prueba
# también la página a 1320 × 860 (1069 × 599) sin panel.
@pytest.mark.parametrize("size", [(450, 319), (1069, 599)])
def test_header_and_grid_fit_without_overlap(app, app_font, size):
    from ui.style import build_style

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    view = GuideView([_la1()], _la1_guide(), clock=lambda: NOW)
    layout.addWidget(view)
    app.setStyleSheet(build_style())
    try:
        host.resize(*size)
        host.show()
        QApplication.processEvents()
        assert host.size().width() == size[0] and host.size().height() == size[1]
        view_rect = _rect_in(view, host)
        chips = view.findChildren(QPushButton)
        assert len(chips) == 7
        rects = []
        for chip in chips:
            assert chip.isVisible(), chip.text()
            rect = _rect_in(chip, host)
            assert view_rect.contains(rect), (chip.text(), rect, view_rect)
            assert chip.width() >= chip.sizeHint().width(), chip.text()
            rects.append((rect, chip.text()))
        for i, (a, name_a) in enumerate(rects):
            for b, name_b in rects[i + 1:]:
                assert not a.intersects(b), f"{name_a} pisa a {name_b}"
        title = _rect_in(view.title_label, host)
        grid = _rect_in(view.grid, host)
        assert view_rect.contains(grid)
        for rect, name in rects:
            assert not title.intersects(rect), name
            assert rect.bottom() < grid.top(), name
        # Regla de horas y al menos dos filas completas a la vista.
        assert view.grid.viewport().height() >= view.grid.ruler_height() + 2 * view.grid.row_height()
        assert view.grid.viewport().width() > view.grid.lane_left() + 200
    finally:
        app.setStyleSheet("")
        host.close()


def test_reopening_a_hidden_guide_refreshes_the_running_cell(app):
    """Con la vista oculta el temporizador no actualiza nada: al volver a
    mostrarla, «en emisión» y «ahora» deben ir con la hora de entonces, no
    con la de la última vez que estuvo visible."""
    clock = {"now": NOW}
    view = GuideView([_la1()], _la1_guide(), clock=lambda: clock["now"])
    view.resize(900, 500)
    view.show()
    QApplication.processEvents()
    try:
        assert [c.is_now for c in view.row(0).cells] == [True, False]  # Telediario 2
        view.hide()
        clock["now"] = NOW.replace(minute=50)  # cruza al «Cine» sin ticks (oculta)
        view.show()
        QApplication.processEvents()
        assert [c.is_now for c in view.row(0).cells] == [False, True]
    finally:
        view.close()


def test_set_guide_and_channels_refresh_rows(app):
    view = _view([], {})
    try:
        assert view.row_count() == 0
        view.set_channels([_la1()])
        assert view.row(0).cells == []
        view.set_guide(_la1_guide())
        assert [c.title for c in view.row(0).cells] == ["Telediario 2", "Cine: El Ministerio"]
        assert view.current_day() == date(2026, 11, 20)
    finally:
        view.close()
