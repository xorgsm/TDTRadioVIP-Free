"""Inicialización compartida de las ediciones VIP y Free de la aplicación."""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import APP_VERSION, get_font_paths, get_icon_path, load_settings
from core.single_instance import SingleInstanceGuard
from player.vlc_player import vlc_disponible_al_arrancar
from ui.main_window import MainWindow
from ui.style import DEFAULT_ACCENT, build_style

# Nombres fijos del cerrojo de instancia única (ver core/single_instance.py)
# -- mismo criterio que el AppUserModelID de core/bootstrap.py: cada edición
# usa el suyo, así que se pueden tener las dos abiertas a la vez; solo se
# bloquea abrir la MISMA edición dos veces.
_INSTANCE_KEY_VIP = "TDTRadioVIP-instancia-unica-Licenciada"
_INSTANCE_KEY_FREE = "TDTRadioVIP-instancia-unica-Free"


def _bring_existing_window_to_front(window) -> None:
    """Ver SingleInstanceGuard.activation_requested: una segunda instancia
    pidió que se traiga esta ventana al frente en vez de abrir otra."""
    window.showNormal()
    window.raise_()
    window.activateWindow()


def _register_app_font() -> None:
    """
    Registra las tipografías empaquetadas en resources/fonts/ (Manrope,
    Playfair Display e Inter, ver core.get_font_paths) para Qt. Es la fuente del mockup original del
    rediseño 7.5.8 (ver ui/palette.py); antes del empaquetado, ui/style.py
    solo podía usar 'Segoe UI' porque Inter no estaba instalada en el
    sistema. Si por lo que sea no está disponible (build sin recursos,
    instalación incompleta), simplemente no se registra nada y build_style()
    cae en su fallback declarado ('Segoe UI', sans-serif) sin romper nada.
    """
    for font_path in get_font_paths():
        QFontDatabase.addApplicationFont(font_path)


def _apply_font_rendering(app: QApplication) -> None:
    """Desactiva el hinting de la fuente de la app: con Manrope (variable)
    el hinting por defecto colapsa el ancho de los espacios en tamaños
    pequeños ("loqueestabas") y el texto se lee peor."""
    font = app.font()
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)


def _create_application(instance_key: str) -> tuple[QApplication, QIcon, SingleInstanceGuard] | None:
    """
    None si ya había otra instancia de esta edición corriendo: se le avisó
    para que traiga su ventana al frente y quien llama debe terminar sin
    construir MainWindow. Si no, la aplicación, su icono y el guard, que hay
    que conectar a la ventana ya creada.
    """
    app = QApplication(sys.argv)
    guard = SingleInstanceGuard(instance_key)
    if not guard.try_acquire():
        return None
    # Referencia fuerte en el propio QApplication: como variable local nada
    # la mantendría viva hasta conectar activation_requested a la ventana.
    app._single_instance_guard = guard
    app.aboutToQuit.connect(guard.release)
    app.setApplicationName("TDT & Radio VIP")
    app.setApplicationVersion(APP_VERSION)
    _register_app_font()
    _apply_font_rendering(app)
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

    Imports locales (no arriba del módulo): run_free() no llama a run_vip(),
    pero como ambas viven en el mismo archivo, un import a nivel de módulo
    de core.license/ui.splash se habría colado igual en el build free vía
    TDTRadioVIP_Free.spec -- ver el mismo comentario junto a
    self._cast_session en ui/main_window.py para el porqué de fondo.
    """
    from core.license import load_activation
    from ui.splash import SplashDialog

    created = _create_application(_INSTANCE_KEY_VIP)
    if created is None:
        return 0
    app, app_icon, guard = created
    activated = False
    tiene_licencia = bool(load_activation().get("activated"))
    if tiene_licencia or not load_settings().get("splash_free_seen"):
        splash = SplashDialog()
        splash.setWindowIcon(app_icon)
        splash.exec()
        activated = splash.activated
    window = MainWindow(activated=activated)
    window.setWindowIcon(app_icon)
    guard.bind_activation(lambda: _bring_existing_window_to_front(window))
    window.show()
    return app.exec()


def run_free() -> int:
    """Ejecuta la edición Free, sin pantalla de activación."""
    created = _create_application(_INSTANCE_KEY_FREE)
    if created is None:
        return 0
    app, app_icon, guard = created
    window = MainWindow(activated=True, es_version_free=True)
    window.setWindowIcon(app_icon)
    guard.bind_activation(lambda: _bring_existing_window_to_front(window))
    window.show()
    return app.exec()
