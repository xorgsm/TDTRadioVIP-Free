"""
Helpers de composición compartidos por los diálogos.

`_panel` y `_header` construyen los bloques visuales repetidos en cada
sección de cada diálogo (panel con textura + etiqueta de sección, y
cabecera título/subtítulo).
"""

from PySide6.QtWidgets import (
    QComboBox, QFormLayout,
    QFrame, QLabel, QVBoxLayout,
)

from core import countries



def _panel(section_label: str) -> tuple[QFrame, QFormLayout]:
    """
    Panel con textura (mismo lenguaje visual que la barra de reproducción)
    y una etiqueta de sección en mayúsculas arriba, con un QFormLayout
    dentro listo para añadir filas. Evita repetir este bloque en cada
    sección de cada diálogo.
    """
    frame = QFrame()
    frame.setObjectName("dialogPanel")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(8)

    label = QLabel(section_label.upper())
    label.setObjectName("dialogSectionLabel")
    outer.addWidget(label)

    form = QFormLayout()
    form.setSpacing(10)
    form.setContentsMargins(0, 4, 0, 0)
    outer.addLayout(form)
    return frame, form


def _header(title: str, subtitle: str) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("dialogTitle")
    box.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("dialogSubtitle")
        subtitle_label.setWordWrap(True)
        box.addWidget(subtitle_label)
    return box


def _fill_country_combo(combo: QComboBox, selected_code: str):
    """
    Rellena `combo` con core.countries.COUNTRIES y deja seleccionado
    `selected_code` (o España si el código no está en la lista). Punto
    único de verdad: lo usan SettingsDialog (país de TV/radio por defecto)
    y AddPublicTvListDialog (añadir la lista de otro país).
    """
    for code, name in countries.COUNTRIES:
        combo.addItem(name, code)
    idx = combo.findData((selected_code or "ES").upper())
    combo.setCurrentIndex(idx if idx >= 0 else combo.findData("ES"))
