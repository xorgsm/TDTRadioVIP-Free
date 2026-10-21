"""Diálogo "Añadir lista pública de TV…": la lista de un país sin pegar URLs."""
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout

from ui.visual import set_surface

from ui.dialogs._common import _fill_country_combo, _header, _panel


class AddPublicTvListDialog(QDialog):
    """
    Añadir la lista pública de TV de un país sin tener que buscar ni pegar
    ninguna URL a mano -- a diferencia de ImportPlaylistDialog, aquí el
    origen no lo escribe el usuario: se construye con
    core.channels.playlist_url_for(código_país), la misma función que ya
    usa CatalogLoadController para la lista del país configurado en
    Preferencias. Pensado para el caso de "se me vaciaron los canales de
    un país con el tiempo" o "quiero añadir canales de otro país además
    del mío" sin salir de la app.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Añadir lista pública de TV")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Añadir lista pública de TV",
            "Elige un país y se añadirán a tu lista personalizada todos los "
            "canales de su lista pública (iptv-org), sin duplicar los que ya "
            "tengas. No hace falta buscar ni pegar ninguna URL.",
        ))

        panel, form = _panel("País")
        self.country_combo = QComboBox()
        _fill_country_combo(self.country_combo, "ES")
        form.addRow("Lista de:", self.country_combo)
        root.addWidget(panel)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Ok).setText("Añadir")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_country_code(self) -> str:
        return self.country_combo.currentData()

    def selected_country_name(self) -> str:
        return self.country_combo.currentText()
