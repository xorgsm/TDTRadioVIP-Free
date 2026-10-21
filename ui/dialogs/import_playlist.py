"""
Diálogo de importación de listas M3U completas, por URL remota o desde
un archivo local.
"""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout,
)

from ui.visual import set_surface

from ui.dialogs._common import _header, _panel


class ImportPlaylistDialog(QDialog):
    """Importar una lista M3U/M3U8 completa desde una URL o un archivo local."""

    def __init__(self, parent=None, entry_type: str | None = None):
        super().__init__(parent)
        self._entry_type = entry_type if entry_type in ("tv", "radio") else None
        set_surface(self, "dialog")
        title = "Importar lista de TV" if self._entry_type == "tv" else (
            "Importar lista de radio" if self._entry_type == "radio" else "Importar lista M3U"
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Importar lista M3U",
            "Pega la URL de una lista M3U/M3U8 pública, o elige un archivo guardado "
            "en tu PC. Se añadirán todos los canales que contenga a tu lista "
            "personalizada, sin duplicar los que ya tienes.",
        ))

        panel, form = _panel("Origen")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Canales de TV", "tv")
        self.type_combo.addItem("Emisoras de radio", "radio")
        if self._entry_type:
            self.type_combo.setCurrentIndex(self.type_combo.findData(self._entry_type))
            self.type_combo.setEnabled(False)
        form.addRow("Añadir como:", self.type_combo)

        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("URL http(s):// o ruta de un archivo .m3u/.m3u8")
        browse_btn = QPushButton("Examinar…")
        browse_btn.clicked.connect(self._browse_file)
        source_row.addWidget(self.source_input)
        source_row.addWidget(browse_btn)
        form.addRow("Origen:", source_row)

        root.addWidget(panel)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Ok).setText("Importar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona lista M3U", "", "Listas M3U (*.m3u *.m3u8);;Todos los archivos (*)"
        )
        if path:
            self.source_input.setText(path)

    def get_values(self):
        return self.type_combo.currentData(), self.source_input.text().strip()
