"""Inicialización de la edición Free de la aplicación."""
from __future__ import annotations

import sys

from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import APP_VERSION, get_font_path, get_icon_path, load_settings
from core.single_instance import SingleInstanceGuard
from player.vlc_player import vlc_disponible_al_arrancar
from ui.main_window import MainWindow
from ui.style import DEFAULT_ACCENT, build_style

# Nombre fijo para el cerrojo de instancia única (ver core/single_instance.py)
# -- mismo criterio que el AppUserModelID de core/bootstrap.py: la edición
# con licencia usa un nombre distinto, así que tener ambas ediciones abiertas
# a la vez sigue funcionando (cada una es "su propia" instancia única), solo
# se bloquea abrir la MISMA edición dos veces.
_INSTANCE_KEY_FREE = "TDTRadioVIP-instancia-unica-Free"


def _bring_existing_window_to_front(window) -> None:
    """Ver SingleInstanceGuard.activation_requested: una segunda instancia
    pidió que se traiga esta ventana al frente en vez de abrir otra."""
    window.showNormal()
    window.raise_()
    window.activateWindow()


def _register_app_font() -> None:
    """
    Registra Inter (empaquetada en resources/fonts/, ver core.get_font_path)
    como tipografía disponible para Qt. Es la fuente del mockup original del
    rediseño 7.5.8 (ver ui/palette.py); antes del empaquetado, ui/style.py
    solo podía usar 'Segoe UI' porque Inter no estaba instalada en el
    sistema. Si por lo que sea no está disponible (build sin recursos,
    instalación incompleta), simplemente no se registra nada y build_style()
    cae en su fallback declarado ('Segoe UI', sans-serif) sin romper nada.
    """
    font_path = get_font_path()
    if font_path:
        QFontDatabase.addApplicationFont(font_path)


def _create_application() -> tuple[QApplication, QIcon, SingleInstanceGuard] | None:
    """
    None si ya había otra instancia de esta edición corriendo (se le avisó
    para que traiga su ventana al frente -- ver
    _bring_existing_window_to_front -- y run_free() debe terminar sin más,
    sin llegar a construir MainWindow). Si no, la aplicación y su guard, que
    hay que mantener con vida y conectar a la ventana ya creada -- ver
    run_free() más abajo.
    """
    app = QApplication(sys.argv)
    guard = SingleInstanceGuard(_INSTANCE_KEY_FREE)
    if not guard.try_acquire():
        return None
    # Referencia fuerte en el propio QApplication: si viviera solo como
    # variable local de run_free(), nada la mantendría con vida hasta que
    # activation_requested se conecta más abajo, y el GC podría llevársela
    # por delante antes de que llegue el aviso de una segunda instancia.
    app._single_instance_guard = guard
    app.setApplicationName("TDT & Radio VIP")
    app.setApplicationVersion(APP_VERSION)
    _register_app_font()
    settings = load_settings()
    app.setStyleSheet(build_style(
        settings.get("accent_color", DEFAULT_ACCENT),
        settings.get("theme_mode", "dark"),
    ))

    icon_path = get_icon_path()
    app_icon = QIcon(icon_path) if icon_path else QIcon()
    app.setWindowIcon(app_icon)

    vlc_warning = vlc_disponible_al_arrancar()
    if vlc_warning:
        QMessageBox.warning(None, "VLC no encontrado", vlc_warning)
    return app, app_icon, guard


def run_free() -> int:
    """Ejecuta la edición Free, sin pantalla de activación."""
    created = _create_application()
    if created is None:
        return 0
    app, app_icon, guard = created
    window = MainWindow(activated=True, es_version_free=True)
    window.setWindowIcon(app_icon)
    guard.activation_requested.connect(lambda: _bring_existing_window_to_front(window))
    window.show()
    return app.exec()
