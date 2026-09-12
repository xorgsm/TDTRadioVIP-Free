"""
Biblioteca local de grabaciones: lista los ficheros grabados y permite
reproducirlos, abrir su carpeta o borrarlos, sin tocar el catálogo de
canales.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.recording_library import list_recordings
from ui.visual import set_surface

from ui.dialogs._common import _header


class RecordingsLibraryDialog(QDialog):
    """Biblioteca local de grabaciones sin modificar el catálogo de canales."""

    def __init__(self, recordings_dir: str, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Biblioteca de grabaciones")
        self.setMinimumSize(720, 440)
        self._directory = Path(recordings_dir)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Biblioteca de grabaciones",
            "Tus grabaciones de TV y radio. Puedes abrirlas, mostrar su carpeta o eliminar las que ya no necesites.",
        ))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nombre", "Tipo", "Tamaño", "Fecha"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_selected)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 90)
        root.addWidget(self.table, stretch=1)

        actions = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self._reload)
        actions.addWidget(refresh)
        open_folder = QPushButton("Abrir carpeta")
        open_folder.clicked.connect(self._open_folder)
        actions.addWidget(open_folder)
        actions.addStretch(1)
        self.open_btn = QPushButton("Abrir")
        self.open_btn.clicked.connect(self._open_selected)
        actions.addWidget(self.open_btn)
        self.delete_btn = QPushButton("Eliminar seleccionadas")
        self.delete_btn.clicked.connect(self._delete_selected)
        actions.addWidget(self.delete_btn)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        root.addLayout(actions)
        self._reload()

    def _reload(self):
        self.table.setRowCount(0)
        for recording in list_recordings(self._directory):
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(recording.path.name)
            name.setData(Qt.UserRole, str(recording.path))
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem("Radio" if recording.path.suffix.casefold() == ".mka" else "TV"))
            self.table.setItem(row, 2, QTableWidgetItem(self._format_size(recording.size)))
            date = datetime.fromtimestamp(recording.modified).strftime("%d/%m/%Y %H:%M")
            self.table.setItem(row, 3, QTableWidgetItem(date))
        is_empty = self.table.rowCount() == 0
        self.open_btn.setEnabled(not is_empty)
        self.delete_btn.setEnabled(not is_empty)

    def _selected_paths(self) -> list[Path]:
        paths = []
        for index in self.table.selectionModel().selectedRows():
            value = self.table.item(index.row(), 0).data(Qt.UserRole)
            if value:
                paths.append(Path(value))
        return paths

    def _open_selected(self):
        paths = self._selected_paths()
        if paths:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths[0])))

    def _open_folder(self):
        self._directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._directory)))

    def _delete_selected(self):
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "Selecciona grabaciones", "Selecciona una o más grabaciones para eliminarlas.")
            return
        if QMessageBox.question(
            self, "Eliminar grabaciones",
            f"Vas a eliminar {len(paths)} grabación(es) de forma permanente.\n\n¿Continuar?",
        ) != QMessageBox.Yes:
            return
        errors = 0
        for path in paths:
            try:
                path.unlink()
                log = path.with_suffix(".log")
                if log.exists():
                    log.unlink()
            except OSError:
                errors += 1
        self._reload()
        if errors:
            QMessageBox.warning(self, "No se pudieron eliminar todas", f"No se pudieron eliminar {errors} grabación(es).")

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
