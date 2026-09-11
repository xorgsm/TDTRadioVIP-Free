"""
Diálogo para añadir manualmente un canal de TV o una emisora de radio
indicando nombre, URL y categoría.
"""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLineEdit, QMessageBox, QVBoxLayout,
)

from ui.visual import set_surface

from ui.dialogs._common import _header, _panel


class AddEntryDialog(QDialog):
    """Añadir (o editar) un único canal de TV o emisora de radio a mano."""

    def __init__(self, parent=None, initial: dict | None = None):
        super().__init__(parent)
        set_surface(self, "dialog")
        editing = initial is not None
        self.editing = editing
        self.original_name = initial.get("name") if editing else None
        self.setWindowTitle("Editar canal o emisora" if editing else "Añadir canal o emisora")
        self.setMinimumWidth(460)
        self.result_data = None

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Editar canal o emisora" if editing else "Añadir canal o emisora",
            "Se guarda en tu lista personalizada, junto a los canales que ya tienes.",
        ))

        panel, form = _panel("Datos")

        self.type_combo = QComboBox()
        self.type_combo.addItem("Canal de TV", "tv")
        self.type_combo.addItem("Emisora de radio", "radio")
        if editing:
            idx = self.type_combo.findData(initial.get("type", "tv"))
            self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.type_combo.setEnabled(False)
        form.addRow("Tipo:", self.type_combo)

        self.name_input = QLineEdit(initial.get("name", "") if editing else "")
        self.name_input.setPlaceholderText("Nombre a mostrar")
        form.addRow("Nombre:", self.name_input)

        self.url_input = QLineEdit(initial.get("url", "") if editing else "")
        self.url_input.setPlaceholderText("https://.../stream.m3u8")
        form.addRow("URL del stream:", self.url_input)

        self.logo_input = QLineEdit(initial.get("logo", "") if editing else "")
        self.logo_input.setPlaceholderText("(opcional) URL de la imagen del logo")
        form.addRow("Logo:", self.logo_input)

        self.group_input = QLineEdit(initial.get("group", "") if editing else "")
        self.group_input.setPlaceholderText("(opcional) ej. Generalista, Deportes…")
        form.addRow("Categoría:", self.group_input)

        root.addWidget(panel)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Ok).setText("Guardar cambios" if editing else "Añadir")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_accept(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Faltan datos", "El nombre y la URL del stream son obligatorios.")
            return
        self.result_data = {
            "type": self.type_combo.currentData(),
            "name": name,
            "url": url,
            "logo": self.logo_input.text().strip(),
            "group": self.group_input.text().strip(),
        }
        self.accept()
