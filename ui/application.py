"""Inicialización compartida de las ediciones VIP y Free de la aplicación."""
from __future__ import annotations

import sys

from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import APP_VERSION, get_font_path, get_icon_path, load_settings
from core.license import load_activation
from player.vlc_player import vlc_disponible_al_arrancar
from ui.main_window import MainWindow
from ui.splash import SplashDialog
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


def run_vip() -> int:
    """Muestra la activación de la edición VIP y ejecuta su ventana.

    El splash solo aparece cuando aporta algo: en el primer arranque (para
    activar o elegir modo gratuito) y cuando hay una licencia guardada (se
    valida contra el hardware en segundo plano y el diálogo se cierra solo).
    Quien ya eligió modo gratuito entra directo — puede volver a este diálogo
    desde Configuración > Activar VIP….

    load_activation() solo lee license.json (barato); is_activated() no se
    llama aquí porque necesita el hardware ID y eso son varios segundos de
    subprocesos WMIC/PowerShell bloqueando el arranque — esa validación la
    hace el propio splash en su hilo de fondo, como siempre.
    """
    app, app_icon = _create_application()
    activated = False
    tiene_licencia = bool(load_activation().get("activated"))
    if tiene_licencia or not load_settings().get("splash_free_seen"):
        splash = SplashDialog()
        splash.setWindowIcon(app_icon)
        splash.exec()
        activated = splash.activated
    window = MainWindow(activated=activated)
    window.setWindowIcon(app_icon)
    window.show()
    return app.exec()


def run_free() -> int:
    """Ejecuta la edición Free, sin pantalla de activación."""
    app, app_icon = _create_application()
    window = MainWindow(activated=True, es_version_free=True)
    window.setWindowIcon(app_icon)
    window.show()
    return app.exec()
