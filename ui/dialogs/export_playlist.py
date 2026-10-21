"""
Diálogo de exportación del catálogo actual (o una selección) a un
archivo M3U.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ui.visual import set_surface

from ui.dialogs._common import _header


class ExportPlaylistDialog(QDialog):
    """Vista previa editable antes de exportar TV y radio como M3U."""

    def __init__(self, entries: list[dict], parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Preparar lista M3U")
        self.resize(860, 560)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Preparar exportación M3U",
            "Desmarca lo que no quieras incluir o edita nombre, URL y categoría. "
            "Los cambios solo afectan al archivo exportado, no a tu catálogo.",
        ))

        self.table = QTableWidget(len(entries), 5)
        self.table.setHorizontalHeaderLabels(["Incluir", "Tipo", "Nombre", "URL", "Categoría"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 68)
        self.table.setColumnWidth(1, 62)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 300)
        for row, entry in enumerate(entries):
            include = QTableWidgetItem()
            include.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            include.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, include)
            kind = QTableWidgetItem("TV" if entry.get("type") == "tv" else "Radio")
            kind.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 1, kind)
            name = QTableWidgetItem(str(entry.get("name", "")))
            name.setData(Qt.UserRole, dict(entry))
            self.table.setItem(row, 2, name)
            self.table.setItem(row, 3, QTableWidgetItem(str(entry.get("url", ""))))
            self.table.setItem(
                row, 4, QTableWidgetItem(str(entry.get("group") or entry.get("tags") or ""))
            )
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        all_btn = QPushButton("Incluir todo")
        all_btn.clicked.connect(lambda: self._set_all_checked(Qt.Checked))
        actions.addWidget(all_btn)
        none_btn = QPushButton("No incluir nada")
        none_btn.clicked.connect(lambda: self._set_all_checked(Qt.Unchecked))
        actions.addWidget(none_btn)
        remove_btn = QPushButton("Quitar seleccionados")
        remove_btn.clicked.connect(self._remove_selected_rows)
        actions.addWidget(remove_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Elegir destino…")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def entries_for_export(self) -> list[dict]:
        entries = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() != Qt.Checked:
                continue
            base = dict(self.table.item(row, 2).data(Qt.UserRole) or {})
            base["name"] = self.table.item(row, 2).text().strip()
            base["url"] = self.table.item(row, 3).text().strip()
            group = self.table.item(row, 4).text().strip()
            if base.get("type") == "radio":
                base["tags"] = group
            else:
                base["group"] = group
            entries.append(base)
        return entries

    def _set_all_checked(self, state):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def _remove_selected_rows(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
