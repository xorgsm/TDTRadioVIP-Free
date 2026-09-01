"""Inicialización de la edición Free de la aplicación."""
from __future__ import annotations

import sys

from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import APP_VERSION, get_font_path, get_icon_path, load_settings
from player.vlc_player import vlc_disponible_al_arrancar
from ui.main_window import MainWindow
from ui.style import DEFAULT_ACCENT, build_style


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


def _create_application() -> tuple[QApplication, QIcon]:
    app = QApplication(sys.argv)
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
    return app, app_icon


def run_free() -> int:
    """Ejecuta la edición Free, sin pantalla de activación."""
    app, app_icon = _create_application()
    window = MainWindow(activated=True, es_version_free=True)
    window.setWindowIcon(app_icon)
    window.show()
    return app.exec()
