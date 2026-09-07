"""Guarda el contrato implícito de atributos de MainWindow mientras se
divide ui/main_window.py (ver el plan de refactor: main_window.py concentra
hoy toda la construcción de widgets, y 10+ controladores en ui/ los leen
como ``win.<atributo>`` sin que ningún test instancie MainWindow para
comprobarlo). Un builder que olvide asignar un atributo pasaría los 137
tests existentes y solo fallaría en runtime al abrir la app.

Este test es estático (usa ast, no importa ni instancia Qt): recorre
ui/*.py buscando accesos ``win.<attr>`` / ``window.<attr>`` / ``self.win.<attr>``
en lectura, y comprueba que cada nombre se asigna (``self.<attr> = ...`` o
``self.win.<attr> = ...``) o se define como método en algún módulo de ui/ --
main_window.py hoy, los módulos builder/controller que salgan de él mañana.
"""
import ast
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

# Miembros heredados de QWidget/QMainWindow: nunca se asignan en Python (los
# provee Qt), así que quedan fuera del contrato que este test vigila.
QT_INHERITED_ALLOWLIST = {
    "activateWindow", "frameGeometry", "geometry", "move", "raise_",
    "resize", "screen", "setGeometry", "setMinimumSize", "setWindowFlag",
    "setWindowIcon", "show", "showFullScreen", "showNormal", "statusBar",
    "width", "windowHandle", "windowIcon", "y",
}

# Instantánea congelada del contrato en el momento de escribir este test
# (previa a cualquier fase del refactor). Cambiar esta lista debe ser una
# decisión consciente en el mismo commit que añade/renombra/quita un
# atributo de MainWindow -- no un efecto secundario silencioso de mover código.
FROZEN_EXPECTED_ATTRS = {
    "_active_list", "_active_row", "_audio_only_tv", "_auto_skip_count",
    "_background_diagnostics_started", "_background_health_results",
    "_cast_session", "_current_alternate_urls", "_current_nav_id",
    "_dlna_session", "_fs_last_cursor_pos", "_fs_mouse_poll_timer",
    "_fs_overlay_hide_timer", "_geometria_antes_pip", "_geometria_normal",
    "_home_health_layout", "_home_layout", "_home_now_layout",
    "_home_quick_layout", "_home_secondary_layout", "_is_closing",
    "_make_glow", "_maximize_btn", "_on_nav_changed", "_open_command_palette",
    "_pending_reminder_tune", "_pip_compact_visibility", "_pip_mode",
    "_playback_failed", "_playback_token", "_player_fullscreen",
    "_pseudo_maximizado", "_queue", "_reminder_timer",
    "_scheduled_recording_active", "_sleep_countdown", "_sleep_minutes_left",
    "_sleep_timer", "_taskbar", "_tray_icon", "_was_maximized_before_fs",
    "_was_maximized_before_pip", "cast_btn", "catalog", "catalog_count_label",
    "content_widget", "current_logo", "current_name", "current_tvg_id",
    "current_type", "current_url", "epg", "epg_guide", "equalizer",
    "fav_btn", "fav_list", "favorites", "fullscreen_btn", "group_filter",
    "groups_sidebar", "health_filter", "hist_list", "history", "home",
    "home_fav_empty", "home_fav_list", "home_float_btn",
    "home_health_summary", "home_now_subtitle", "home_now_title",
    "home_on_air_carousel", "home_recent_carousel",
    "home_recommended_carousel", "home_resume_btn", "library",
    "library_sidebar", "library_toggle_btn", "lists", "logo_loader",
    "menu_bar", "more_btn", "mute_btn", "nav_group", "nav_rail", "now_logo",
    "now_playing_bar", "now_subtitle", "now_title", "pip_btn", "play_btn",
    "playback", "player", "player_frame", "player_header_bar",
    "player_stack", "queue", "radio_list", "radio_stations_data",
    "record_btn", "recorder", "recordings_dir", "retry_btn", "search_box",
    "seek_back_btn", "seek_fwd_btn", "set_live_badge_visible", "settings",
    "sleep_btn", "stack", "title_bar", "tv_channels_data", "tv_list",
    "volume_slider",
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
