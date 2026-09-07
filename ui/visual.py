"""Helpers visuales compartidos, sin lógica de negocio."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QWidget


VALID_VARIANTS = frozenset({
    "default",
    "primary",
    "secondary",
    "ghost",
    "danger",
    "info",
    "success",
    "cast",
    "sleep",
    "tv",
    "radio",
    "podcast",
    "download",
})

VALID_STATES = frozenset({"default", "active", "loading", "empty", "error"})
VALID_SURFACES = frozenset({"default", "dialog", "floating", "sidebar", "mediaPanel", "homeSectionCard"})


def _set_dynamic(widget: QWidget, name: str, value: str) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def set_variant(widget: QWidget, variant: str) -> str:
    """Aplica una variante conocida y degrada las desconocidas a default."""
    safe = variant if variant in VALID_VARIANTS else "default"
    _set_dynamic(widget, "uiVariant", safe)
    return safe


def set_visual_state(widget: QWidget, state: str) -> str:
    """Aplica un estado visual conocido sin alterar el estado funcional."""
    safe = state if state in VALID_STATES else "default"
    _set_dynamic(widget, "uiState", safe)
    return safe


def set_surface(widget: QWidget, surface: str) -> str:
    """Asigna una superficie reutilizable y segura al widget."""
    safe = surface if surface in VALID_SURFACES else "default"
    _set_dynamic(widget, "uiSurface", safe)
    return safe


def make_separator() -> QFrame:
    """
    Línea vertical fina entre grupos de botones de control. Antes todos
    los botones iban en una sola fila sin ninguna separación visual más
    que el spacing del layout — con el halo del play y poco espacio
    entre botones, la fila entera se veía como un bloque pegado en vez
    de controles agrupados por función (favorito/cast, reproducción,
    grabar/volumen, vista).
    """
    sep = QFrame()
    sep.setObjectName("ctrlSeparator")
    sep.setFixedWidth(1)
    sep.setFixedHeight(22)
    return sep


def make_glow(color: QColor, blur: float = 22, alpha: int = 160, y_offset: float = 0) -> QGraphicsDropShadowEffect:
    """
    Halo de color alrededor de un botón, vía QGraphicsDropShadowEffect
    (esto sí aplica a QWidgets normales, a diferencia de los delegados
    de lista, que no soportan QGraphicsEffect y necesitan pintarlo a mano).
    """
    effect = QGraphicsDropShadowEffect()
    glow_color = QColor(color)
    glow_color.setAlpha(alpha)
    effect.setColor(glow_color)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    return effect
