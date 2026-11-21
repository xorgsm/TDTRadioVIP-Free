"""Guarda el contrato implícito de atributos de MainWindow mientras se
divide ui/main_window.py (ver el plan de refactor: main_window.py concentra
hoy toda la construcción de widgets, y 10+ controladores en ui/ los leen
como ``win.<atributo>`` sin que ningún test instancie MainWindow para
comprobarlo). Un builder que olvide asignar un atributo pasaría los 137
tests existentes y solo fallaría en runtime al abrir la app.

Los dos primeros tests son estáticos (usan ast, no instancian Qt): recorren
ui/*.py buscando accesos ``win.<attr>`` / ``window.<attr>`` / ``self.win.<attr>``
en lectura, y comprueban que cada nombre se asigna (``self.<attr> = ...`` o
``self.win.<attr> = ...``) o se define como método en algún módulo de ui/ --
main_window.py hoy, los módulos builder/controller que salgan de él mañana.
El resto construye la MainWindow real (offscreen) para vigilar la carcasa
del rediseño v10: raíl, barra superior y contenido.
"""
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

# Miembros heredados de QWidget/QMainWindow: nunca se asignan en Python (los
# provee Qt), así que quedan fuera del contrato que este test vigila.
QT_INHERITED_ALLOWLIST = {
    "activateWindow", "close", "frameGeometry", "geometry", "move", "raise_",
    "resize", "screen", "setGeometry", "setMinimumSize", "setWindowFlag",
    "showMinimized",
    "setWindowIcon", "show", "showFullScreen", "showNormal", "statusBar",
    "width", "windowHandle", "windowIcon", "y",
}

# Instantánea congelada del contrato en el momento de escribir este test
# (previa a cualquier fase del refactor). Cambiar esta lista debe ser una
# decisión consciente en el mismo commit que añade/renombra/quita un
# atributo de MainWindow -- no un efecto secundario silencioso de mover código.
FROZEN_EXPECTED_ATTRS = {
    "_active_item", "_active_list", "_active_row",
    "_apply_saved_equalizer", "_audio_only_tv",
    "_auto_skip_count", "_background_diagnostics_started",
    "_background_health_results",
    "_cast_session", "_current_alternate_urls", "_current_nav_id",
    "_dlna_session", "_ensure_download_panel", "_fs_last_cursor_pos", "_fs_mouse_poll_timer",
    "_fs_overlay_hide_timer", "_geometria_antes_pip", "_geometria_normal",
    "_home_health_layout", "_home_hero_layout", "_home_layout", "_home_now_layout",
    "_is_closing",
    "_maximize_btn", "_media_keys", "_nav_rail", "_nav_rail_brand", "_nav_rail_caption",
    "_nav_rail_text_buttons",
    "_now_bar_layout",
    "_pending_reminder_tune", "_pip_compact_visibility", "_pip_mode",
    "_playback_failed", "_playback_token", "_player_fullscreen",
    "_pseudo_maximizado", "_queue", "_reminder_timer",
    "_scheduled_recording_active", "_search_debounce",
    "_sleep_countdown", "_sleep_minutes_left",
    "_sleep_timer", "_taskbar", "_tray_icon", "_tv_sidebar_groups", "_was_maximized_before_fs",
    "_was_maximized_before_pip", "activate_vip_action", "activated",
    "cast_btn", "catalog", "catalog_count_label", "catalog_sort", "casting",
    "content_widget", "current_logo", "current_name", "current_tvg_id",
    "current_type", "current_url", "delegate", "dialogs", "dock_progress",
    "dock_quality_badge", "download_panel",
    "downloads_dir",
    "edition_badge",
    "epg", "epg_btn",
    "epg_guide", "equalizer", "es_version_free",
    "fav_btn", "fav_list", "favorites", "fullscreen_btn",
    "global_search_btn", "grid_delegate",
    "group_filter", "guide_view",
    "groups_sidebar", "health_filter", "hist_list", "history", "home",
    "home_fav_carousel", "home_float_btn", "home_greeting",
    "home_health_summary", "home_now_card", "home_now_subtitle",
    "home_now_title", "home_on_air_carousel", "home_recent_carousel",
    "home_recommended_carousel", "home_resume_btn", "library",
    "library_sidebar", "library_toggle_btn", "lists", "live_badge", "logo_loader",
    "more_btn", "more_menu_btn", "mute_btn", "nav_group", "nav_rail", "navigation", "now_controls_separator",
    "now_logo", "now_rotulo",
    "now_playing_bar", "now_subtitle", "now_title", "pip_btn", "play_btn",
    "playback", "player", "player_context_label", "player_frame", "player_header_bar",
    "player_idle_view",
    "player_stack", "queue", "queue_btn", "radio_list", "radio_stations_data",
    "record_btn", "recorder", "recordings_dir", "retry_btn", "search_box",
    "section_title", "seek_back_btn", "seek_fwd_btn",
    "set_live_badge_visible", "set_player_panel_collapsed", "settings", "settings_btn",
    "sleep_btn", "stack", "stop_btn", "title_bar", "top_bar", "top_search_btn",
    "tracks_btn", "tray",
    "tv_channels_data", "tv_list",
    "tv_view_toggle", "updates", "volume_slider", "vpn_status", "window_chrome",
}


def _names_bound_to_window(tree: ast.AST) -> set[str]:
    """Nombres locales que son el parámetro `window`/`win` del constructor
    o una variable a la que se le asignó `self.win` (patrón `win = self.win`
    usado por todos los controladores existentes)."""
    names = {"win", "window"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Attribute)
                and value.attr == "win"
                and isinstance(value.value, ast.Name)
                and value.value.id == "self"
            ):
                names.add(target.id)
    return names


def _collect_reads(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound = _names_bound_to_window(tree)
    reads = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)):
            continue
        base = node.value
        if isinstance(base, ast.Name) and base.id in bound:
            reads.add(node.attr)
        elif (
            isinstance(base, ast.Attribute)
            and base.attr == "win"
            and isinstance(base.value, ast.Name)
            and base.value.id == "self"
        ):
            reads.add(node.attr)
    return reads - QT_INHERITED_ALLOWLIST


def _collect_assigns_and_defs(path: Path) -> set[str]:
    """Nombres asignados vía `self.x = ...` / `win.x = ...` / `self.win.x = ...`
    (incluye AugAssign/AnnAssign y tuplas), más nombres de métodos/funciones
    definidos en el archivo -- un atributo leído como `win.foo` puede ser un
    dato o un método (`win.foo()`), ambos cuentan como "provisto"."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound = _names_bound_to_window(tree)
    names = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            candidates = target.elts if isinstance(target, ast.Tuple) else [target]
            for cand in candidates:
                if not isinstance(cand, ast.Attribute):
                    continue
                base = cand.value
                if isinstance(base, ast.Name) and (base.id == "self" or base.id in bound):
                    names.add(cand.attr)
                elif (
                    isinstance(base, ast.Attribute)
                    and base.attr == "win"
                    and isinstance(base.value, ast.Name)
                    and base.value.id == "self"
                ):
                    names.add(cand.attr)
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
    return names


def _all_ui_files() -> list[Path]:
    return sorted(p for p in UI_DIR.glob("*.py") if p.name != "__init__.py")


def test_every_attribute_read_from_win_is_assigned_somewhere_in_ui() -> None:
    """Ningún módulo de ui/ lee win.<attr> sin que exista una asignación
    (o un método con ese nombre) en algún otro módulo de ui/. Falla si un
    builder extraído de MainWindow olvida asignar un widget que otro
    controlador necesita."""
    all_reads = set()
    for path in _all_ui_files():
        if path.name == "main_window.py":
            continue
        all_reads |= _collect_reads(path)

    assigned = set()
    for path in _all_ui_files():
        assigned |= _collect_assigns_and_defs(path)

    missing = sorted(all_reads - assigned)
    assert missing == [], (
        "Estos atributos se leen como win.<attr> en algún módulo de ui/ "
        f"pero no se asignan/definen en ningún otro módulo de ui/: {missing}"
    )


def test_win_attribute_contract_matches_frozen_snapshot() -> None:
    """Si este test falla, el contrato de atributos de MainWindow cambió
    (se añadió, renombró o quitó algo que algún controlador lee). Revisa el
    diff y actualiza FROZEN_EXPECTED_ATTRS a propósito en el mismo commit --
    no es un fallo a silenciar sin mirar qué cambió."""
    all_reads = set()
    for path in _all_ui_files():
        if path.name == "main_window.py":
            continue
        all_reads |= _collect_reads(path)

    added = sorted(all_reads - FROZEN_EXPECTED_ATTRS)
    removed = sorted(FROZEN_EXPECTED_ATTRS - all_reads)
    assert not added and not removed, (
        f"Contrato de atributos cambiado. Nuevos: {added}. Ya no se leen: {removed}."
    )


# ---------------------------------------------------------------------------
# Carcasa real de la ventana (rediseño v10): raíl | barra superior + contenido.
# Estos sí construyen MainWindow de verdad (offscreen), sin red, bandeja,
# teclas multimedia ni ajustes del usuario (fixture make_window, en
# tests/conftest.py).
# ---------------------------------------------------------------------------


def test_window_uses_nav_rail_not_nav_top(make_window):
    win = make_window()
    assert hasattr(win, "nav_rail")
    assert not hasattr(win, "nav_top")
    assert win.nav_rail.objectName() == "navRail"


def test_global_search_is_always_visible_in_top_bar(make_window):
    for width, height in ((1320, 860), (860, 580)):
        win = make_window(width, height)
        assert win.top_bar.isVisible()
        assert win.top_search_btn.isVisible()
        assert win.top_bar.isAncestorOf(win.top_search_btn)
        text = " ".join(label.text() for label in win.top_search_btn.findChildren(QLabel))
        assert "Buscar canales, emisoras, programas, podcasts…" in text
        assert "Ctrl K" in text
        win.dialogs.open_command_palette = Mock()
        win.top_search_btn.click()
        win.dialogs.open_command_palette.assert_called_once_with()


def test_top_bar_has_multivista_button(make_window):
    win = make_window()
    buttons = {b.text(): b for b in win.top_bar.findChildren(QPushButton)}
    assert "Multivista" in buttons
    win.dialogs.open_mosaic_view = Mock()
    buttons["Multivista"].click()
    win.dialogs.open_mosaic_view.assert_called_once_with()


def _global_rect(widget):
    top_left = widget.mapTo(widget.window(), widget.rect().topLeft())
    return widget.rect().translated(top_left)


def test_shell_layout_is_rail_then_top_bar_over_content(make_window):
    win = make_window(1320, 860)
    rail = _global_rect(win.nav_rail)
    top = _global_rect(win.top_bar)
    content = _global_rect(win.main_splitter)
    title = _global_rect(win.title_bar)
    # La barra de título sigue arriba, a todo el ancho, por encima del raíl.
    assert title.bottom() < rail.top()
    assert title.width() >= win.centralWidget().width() - 1
    # Raíl a la izquierda; barra superior y contenido a su derecha.
    assert rail.right() < top.left()
    assert rail.right() < content.left()
    assert top.bottom() < content.top()
    assert top.height() == 56
    assert rail.top() == top.top()
    assert rail.bottom() >= content.bottom()


@pytest.mark.parametrize(("size", "rail_width"), [((860, 580), 64), ((1320, 860), 208)])
def test_rail_width_follows_window_width(make_window, size, rail_width):
    win = make_window(*size)
    assert win.width() == size[0]
    assert win.nav_rail.width() == rail_width


def test_rail_compacts_when_window_is_resized(make_window):
    from PySide6.QtWidgets import QApplication

    win = make_window(1320, 860)
    assert win.nav_rail.width() == 208
    win.resize(900, 700)
    QApplication.processEvents()
    assert win.nav_rail.width() == 64
    win.resize(1200, 700)
    QApplication.processEvents()
    assert win.nav_rail.width() == 208


def test_free_window_has_no_vpn_card_nor_vpn_polling(make_window):
    win = make_window(es_version_free=True)
    assert win.nav_rail.vpn_card is None
    assert win.vpn_status is None


def test_vpn_card_and_polling_only_in_the_activated_licensed_window(make_window):
    pytest.importorskip("core.caster")
    unactivated = make_window(es_version_free=False, activated=False)
    assert unactivated.nav_rail.vpn_card is None
    assert unactivated.vpn_status is None
    win = make_window(es_version_free=False, activated=True)
    assert win.nav_rail.vpn_card is not None and win.nav_rail.vpn_card.isHidden()
    assert win.vpn_status is not None
    # El arranque del sondeo va en AppLifecycle.schedule_startup_tasks
    # (parcheado en este fixture): construir la ventana no lanza nada.
    assert not win.vpn_status.is_active()


def test_fullscreen_hides_rail_and_top_bar(make_window, monkeypatch):
    win = make_window()
    monkeypatch.setattr(win, "showFullScreen", lambda: None)
    monkeypatch.setattr(win, "showNormal", lambda: None)
    win.window_chrome.enter_player_fullscreen()
    assert win.nav_rail.isHidden() and win.top_bar.isHidden()
    win.window_chrome.exit_player_fullscreen()
    assert not win.nav_rail.isHidden() and not win.top_bar.isHidden()


def test_dock_spans_full_width_below_content(make_window):
    win = make_window(1320, 860)
    dock = _global_rect(win.now_playing_bar)
    content = _global_rect(win.main_splitter)
    rail = _global_rect(win.nav_rail)
    surface = win.centralWidget()
    # Fuera del panel derecho: a todo el ancho, bajo el raíl y el contenido.
    assert not win.player_frame.parentWidget().isAncestorOf(win.now_playing_bar)
    assert dock.height() == 76
    assert dock.left() == 0
    assert dock.width() == surface.width()
    assert dock.top() > content.bottom()
    assert dock.top() > rail.bottom()
    assert dock.bottom() <= surface.height()


def test_dock_shows_every_control_on_a_wide_window(make_window):
    from ui.now_playing_bar_builder import set_quality_badge

    win = make_window(1320, 860)
    set_quality_badge(win, "Señal · estable", "stable")
    for widget in (win.play_btn, win.stop_btn, win.record_btn, win.volume_slider,
                   win.mute_btn, win.more_btn, win.fav_btn, win.pip_btn, win.sleep_btn,
                   win.dock_quality_badge, win.now_logo):
        assert widget.isVisible(), widget.objectName()


def test_dock_badge_hidden_without_health_data(make_window):
    from ui.now_playing_bar_builder import set_quality_badge

    win = make_window(1320, 860)
    assert not win.dock_quality_badge.isVisible()
    set_quality_badge(win, "", "")
    assert not win.dock_quality_badge.isVisible()


def test_channel_name_uses_the_display_font_in_caps(make_window):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from ui.style import build_style

    win = make_window(1320, 860)
    # La aplicación real aplica la hoja de estilos al QApplication (ver
    # ui.application); aquí basta con la ventana para no afectar a otros tests.
    win.setStyleSheet(build_style())
    QApplication.processEvents()
    font = win.now_title.font()
    assert "Barlow Condensed" in font.families()
    # La hoja de estilos fija familia, tamaño y peso, no la capitalización.
    assert font.capitalization() == QFont.AllUppercase


def test_epg_display_feeds_the_dock_progress(make_window):
    from datetime import datetime, timedelta

    from core.epg import Programme, channel_key

    win = make_window(1320, 860)
    assert not win.dock_progress.isVisible()
    now = datetime.now()
    start, stop = now - timedelta(minutes=30), now + timedelta(minutes=30)
    fmt = "%Y%m%d%H%M%S"
    win.epg_guide = {channel_key("la1"): [
        Programme("la1", "Telediario 2", start.strftime(fmt), stop.strftime(fmt)),
    ]}
    win.current_type, win.current_tvg_id = "tv", "la1"
    win.playback.update_epg_display()
    assert win.dock_progress.isVisible()
    assert 0.4 < win.dock_progress.fraction() < 0.6
    assert win.dock_progress.times() == (start.strftime("%H:%M"), stop.strftime("%H:%M"))
    assert win.now_subtitle.text() == "Ahora: Telediario 2"

    # La radio no tiene guía: la fila de progreso desaparece.
    win.current_type, win.current_tvg_id = "radio", ""
    win.playback.update_epg_display()
    assert not win.dock_progress.isVisible()


def _layout_widgets(layout):
    """Widgets de un layout y sus sublayouts, con repeticiones."""
    found = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is not None:
            found.append(item.widget())
        elif item.layout() is not None:
            found.extend(_layout_widgets(item.layout()))
    return found


def test_dock_layouts_hold_each_widget_once(make_window):
    win = make_window()
    widgets = []
    for layout in [win.now_playing_bar.layout()] + [
        child.layout() for child in win.now_playing_bar.findChildren(QWidget, "dockColumn")
    ]:
        widgets.extend(_layout_widgets(layout))
    repeated = {w.objectName() for w in widgets if widgets.count(w) > 1}
    assert repeated == set()
    assert widgets.count(win.fav_btn) == 1


def test_transport_is_centred_in_the_window(make_window):
    from PySide6.QtWidgets import QApplication

    from ui.style import build_style

    win = make_window(1320, 860)
    win.setStyleSheet(build_style())
    QApplication.processEvents()
    left = _global_rect(win.stop_btn).left()
    right = _global_rect(win.record_btn).right()
    assert abs((left + right) / 2 - win.width() / 2) <= 24


def test_pip_keeps_the_dock_height_and_essential_controls(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from ui.style import build_style

    win = make_window()
    win.setStyleSheet(build_style())
    monkeypatch.setattr(win, "move", lambda *_a: None)
    win.window_chrome.enter_pip_mode()
    try:
        QApplication.processEvents()
        assert win.width() == 460
        assert win.now_playing_bar.maximumHeight() == 76
        # Cabe sin recortes: el mínimo del dock no pasa del ancho de PiP.
        assert win.now_playing_bar.minimumSizeHint().width() <= win.width()
        dock = _global_rect(win.now_playing_bar)
        for widget in (win.play_btn, win.stop_btn, win.record_btn, win.volume_slider,
                       win.more_btn, win.pip_btn):
            assert widget.isVisible(), widget.objectName()
            assert dock.contains(_global_rect(widget)), widget.objectName()
        assert not win.fav_btn.isVisible()
        # El botón de PiP es la salida visible y lo dice.
        assert win.pip_btn.accessibleName() == "Salir de ventana flotante"
        assert win.pip_btn.toolTip() == "Salir de ventana flotante"
    finally:
        win.window_chrome.exit_pip_mode()
    QApplication.processEvents()
    assert win.now_playing_bar.maximumHeight() == 76
    assert win.pip_btn.accessibleName() == "Abrir ventana flotante"
    assert win.fav_btn.isVisible()


def test_idle_player_panel_is_collapsed_and_expands_on_play(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from core import history as hist_store
    from player import vlc_player
    from tests.vlc_fakes import fake_vlc_module

    # Doble de libVLC (tests/vlc_fakes.py): play() no abre red ni vídeo, y
    # el historial no se escribe en disco.
    monkeypatch.setattr(vlc_player, "vlc", fake_vlc_module())
    monkeypatch.setattr(vlc_player, "VLC_IMPORT_ERROR", None)
    monkeypatch.setattr(hist_store, "add_entry", lambda *a, **k: [])

    win = make_window(1320, 860)
    splitter = win.main_splitter
    panel = win.player_frame.parentWidget()

    def content_takes_all():
        return win.content_widget.width() >= splitter.width() - splitter.handleWidth()

    # En reposo el panel de vídeo está plegado y el catálogo ocupa todo,
    # también después de redimensionar la ventana.
    assert splitter.sizes()[1] <= 0
    assert content_takes_all()
    win.resize(1100, 760)
    QApplication.processEvents()
    assert splitter.sizes()[1] <= 0
    assert content_takes_all()

    win.playback.play("tv", "La 1", "http://example.invalid/la1.m3u8")
    QApplication.processEvents()
    assert panel.isVisible()
    assert splitter.sizes()[1] >= 300
    assert panel.width() >= 300

    # El tamaño que deja el usuario se recuerda entre reproducciones.
    total = sum(splitter.sizes())
    splitter.setSizes([total - 420, 420])
    QApplication.processEvents()
    remembered = splitter.sizes()[1]
    win.playback.stop_playback()
    QApplication.processEvents()
    assert splitter.sizes()[1] <= 0
    assert content_takes_all()
    win.playback.play("radio", "Radio 3", "http://example.invalid/r3.mp3")
    QApplication.processEvents()
    assert splitter.sizes()[1] == remembered


def test_fullscreen_and_pip_show_the_collapsed_player_panel(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    win = make_window()
    splitter = win.main_splitter
    assert splitter.sizes()[1] <= 0
    monkeypatch.setattr(win, "showFullScreen", lambda: None)
    monkeypatch.setattr(win, "showNormal", lambda: None)
    monkeypatch.setattr(win, "move", lambda *_a: None)
    win.window_chrome.enter_player_fullscreen()
    QApplication.processEvents()
    assert splitter.sizes()[1] > 0
    win.window_chrome.exit_player_fullscreen()
    QApplication.processEvents()
    assert splitter.sizes()[1] <= 0
    win.window_chrome.enter_pip_mode()
    QApplication.processEvents()
    assert splitter.sizes()[1] > 0
    win.window_chrome.exit_pip_mode()
    QApplication.processEvents()
    assert splitter.sizes()[1] <= 0


def _fake_playback(monkeypatch):
    from core import history as hist_store
    from player import vlc_player
    from tests.vlc_fakes import fake_vlc_module

    monkeypatch.setattr(vlc_player, "vlc", fake_vlc_module())
    monkeypatch.setattr(vlc_player, "VLC_IMPORT_ERROR", None)
    monkeypatch.setattr(hist_store, "add_entry", lambda *a, **k: [])


def test_panel_opened_by_dragging_the_handle_keeps_the_user_width(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    _fake_playback(monkeypatch)
    win = make_window(1320, 860)
    splitter = win.main_splitter
    assert splitter.sizes()[1] <= 0

    # El usuario abre el panel arrastrando el divisor (splitterMoved solo
    # se emite con arrastres reales, no con setSizes).
    total = sum(splitter.sizes())
    splitter.setSizes([total - 410, 410])
    splitter.splitterMoved.emit(total - 410, 1)
    QApplication.processEvents()

    win.playback.play("tv", "La 1", "http://example.invalid/la1.m3u8")
    QApplication.processEvents()
    assert splitter.sizes()[1] == 410


def test_width_is_remembered_when_playback_starts_inside_fullscreen(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    _fake_playback(monkeypatch)
    win = make_window(1320, 860)
    splitter = win.main_splitter
    monkeypatch.setattr(win, "showFullScreen", lambda: None)
    monkeypatch.setattr(win, "showNormal", lambda: None)
    monkeypatch.setattr(win, "move", lambda *_a: None)

    # Reposo -> pantalla completa -> reproducir -> salir -> ajustar -> parar.
    win.window_chrome.enter_player_fullscreen()
    win.playback.play("tv", "La 1", "http://example.invalid/la1.m3u8")
    win.window_chrome.exit_player_fullscreen()
    QApplication.processEvents()
    total = sum(splitter.sizes())
    splitter.setSizes([total - 450, 450])
    QApplication.processEvents()
    win.playback.stop_playback()
    QApplication.processEvents()
    assert splitter.sizes()[1] <= 0
    win.playback.play("radio", "Radio 3", "http://example.invalid/r3.mp3")
    QApplication.processEvents()
    assert splitter.sizes()[1] == 450


def test_pip_hides_rail_and_top_bar(make_window, monkeypatch):
    win = make_window()
    monkeypatch.setattr(win, "move", lambda *_a: None)
    win.window_chrome.enter_pip_mode()
    try:
        assert win.nav_rail.isHidden() and win.top_bar.isHidden()
    finally:
        win.window_chrome.exit_pip_mode()
    assert not win.nav_rail.isHidden() and not win.top_bar.isHidden()
