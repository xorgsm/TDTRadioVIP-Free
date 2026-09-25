"""
Editor de listas M3U: carga una lista, permite renombrar, reordenar,
eliminar y comprobar la validez de las entradas, y guarda el resultado.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QMenu, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core import channels as tv_channels
from core.playlist_export import export_m3u
from ui.fetch_worker import FetchWorker
from ui.visual import set_surface

from ui.dialogs._common import _header


class M3UEditorDialog(QDialog):
    """Editor visual para revisar una lista M3U antes de exportarla."""

    def __init__(self, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Editor M3U")
        self.resize(1120, 720)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "EDITOR M3U",
            "Carga una lista HTTP(S) o un archivo, filtra grupos y edita su contenido antes de exportarlo.",
        ))

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Origen (URL o archivo):"))
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("http(s)://…/lista.m3u o archivo .m3u/.m3u8")
        source_row.addWidget(self.source_input, 1)
        browse_btn = QPushButton("Examinar…")
        browse_btn.clicked.connect(self._browse_file)
        source_row.addWidget(browse_btn)
        load_btn = QPushButton("Cargar")
        load_btn.setObjectName("primaryButton")
        load_btn.clicked.connect(self._load_source)
        source_row.addWidget(load_btn)
        self._load_btn = load_btn
        self._load_worker = None
        root.addLayout(source_row)

        content = QHBoxLayout()
        groups_box = QVBoxLayout()
        groups_box.addWidget(QLabel("GRUPOS"))
        groups_hint = QLabel("Ctrl/Shift + clic para seleccionar varios")
        groups_hint.setObjectName("dialogSubtitle")
        groups_box.addWidget(groups_hint)
        self.groups_list = QListWidget()
        self.groups_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.groups_list.itemSelectionChanged.connect(self._apply_filters)
        self.groups_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.groups_list.customContextMenuRequested.connect(self._show_groups_menu)
        groups_box.addWidget(self.groups_list, 1)
        content.addLayout(groups_box, 1)

        table_box = QVBoxLayout()
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Buscar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nombre, grupo o URL")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filters)
        self.search_input.textChanged.connect(lambda _text: self._filter_timer.start())
        search_row.addWidget(self.search_input, 1)
        clear_btn = QPushButton("Quitar filtro")
        clear_btn.clicked.connect(self._clear_filters)
        search_row.addWidget(clear_btn)
        table_box.addLayout(search_row)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Incluir", "Grupo", "Nombre del canal", "URL", "Estado"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 68)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 250)
        self.table.setColumnWidth(4, 130)
        table_box.addWidget(self.table, 1)
        content.addLayout(table_box, 4)
        root.addLayout(content, 1)

        actions = QHBoxLayout()
        include_btn = QPushButton("Marcar visibles")
        include_btn.clicked.connect(lambda: self._set_visible_checked(Qt.Checked))
        actions.addWidget(include_btn)
        exclude_btn = QPushButton("Desmarcar visibles")
        exclude_btn.clicked.connect(lambda: self._set_visible_checked(Qt.Unchecked))
        actions.addWidget(exclude_btn)
        remove_rows_btn = QPushButton("Eliminar seleccionados")
        remove_rows_btn.clicked.connect(self._remove_selected_rows)
        actions.addWidget(remove_rows_btn)
        remove_groups_btn = QPushButton("Eliminar grupo(s) seleccionado(s)")
        remove_groups_btn.clicked.connect(self._remove_selected_groups)
        actions.addWidget(remove_groups_btn)
        self.analyze_btn = QPushButton("Analizar lista")
        self.analyze_btn.clicked.connect(self._start_analysis)
        actions.addWidget(self.analyze_btn)
        actions.addStretch(1)
        export_btn = QPushButton("Exportar lista…")
        export_btn.setObjectName("primaryButton")
        export_btn.clicked.connect(self._export)
        actions.addWidget(export_btn)
        root.addLayout(actions)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona lista M3U", "", "Listas M3U (*.m3u *.m3u8);;Todos los archivos (*)"
        )
        if path:
            self.source_input.setText(path)

    def _load_source(self):
        source = self.source_input.text().strip()
        if not source or self._load_worker is not None:
            return

        self._load_btn.setEnabled(False)
        self._load_btn.setText("Cargando…")
        worker = FetchWorker(self._fetch_and_parse_source, source)
        worker.done.connect(self._on_source_loaded)
        worker.finished.connect(self._on_source_worker_finished)
        self._load_worker = worker
        worker.start()

    @staticmethod
    def _fetch_and_parse_source(source: str):
        """Lee y parsea una lista fuera del hilo de interfaz."""
        try:
            text = tv_channels.read_playlist_source(source)
        except (OSError, requests.RequestException, ValueError):
            return None
        return tv_channels.parse_m3u(text, deduplicate=False)

    def _on_source_loaded(self, channels):
        if self._load_worker is None:
            return
        if channels is None:
            QMessageBox.warning(
                self, "No se pudo cargar",
                "No se pudo leer la lista. Revisa la URL o la ruta del archivo e inténtalo de nuevo.",
            )
            return
        if not channels:
            QMessageBox.information(self, "Lista vacía", "No se encontraron canales M3U válidos.")
            return
        self._populate(channels)

    def _on_source_worker_finished(self):
        self._load_worker = None
        self._load_btn.setEnabled(True)
        self._load_btn.setText("Cargar")

    def _populate(self, channels):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(channels))
            for row, channel in enumerate(channels):
                include = QTableWidgetItem()
                include.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                include.setCheckState(Qt.Checked)
                self.table.setItem(row, 0, include)
                self.table.setItem(row, 1, QTableWidgetItem(channel.group))
                self.table.setItem(row, 2, QTableWidgetItem(channel.name))
                self.table.setItem(row, 3, QTableWidgetItem(channel.url))
                status = QTableWidgetItem("Pendiente")
                status.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 4, status)
        finally:
            self.table.setUpdatesEnabled(True)
        self._mark_duplicates()
        self._refresh_groups()

    def _mark_duplicates(self):
        names: dict[str, int] = {}
        urls: dict[str, int] = {}
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 2).text().strip().casefold()
            url = self.table.item(row, 3).text().strip().casefold()
            names[name] = names.get(name, 0) + 1
            urls[url] = urls.get(url, 0) + 1
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 2).text().strip().casefold()
            url = self.table.item(row, 3).text().strip().casefold()
            duplicate = names.get(name, 0) > 1 or urls.get(url, 0) > 1
            self.table.item(row, 4).setText("Duplicado" if duplicate else "Pendiente")

    def _refresh_groups(self):
        selected = {item.text() for item in self.groups_list.selectedItems()}
        groups = sorted({self.table.item(row, 1).text().strip() or "Sin grupo" for row in range(self.table.rowCount())})
        self.groups_list.clear()
        for group in groups:
            item = QListWidgetItem(group)
            self.groups_list.addItem(item)
            item.setSelected(group in selected)
        self._apply_filters()

    def _clear_filters(self):
        self.search_input.clear()
        self.groups_list.clearSelection()

    def _show_groups_menu(self, position):
        item = self.groups_list.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.groups_list.clearSelection()
            item.setSelected(True)
        selected_count = len(self.groups_list.selectedItems())
        menu = QMenu(self)
        label = "Eliminar grupo…" if selected_count == 1 else f"Eliminar {selected_count} grupos…"
        menu.addAction(label, self._remove_selected_groups)
        menu.exec(self.groups_list.mapToGlobal(position))

    def _apply_filters(self):
        groups = {item.text() for item in self.groups_list.selectedItems()}
        query = self.search_input.text().strip().casefold()
        self.table.setUpdatesEnabled(False)
        try:
            for row in range(self.table.rowCount()):
                values = [self.table.item(row, column).text() for column in range(1, 5)]
                group = values[0].strip() or "Sin grupo"
                visible = (not groups or group in groups) and (
                    not query or query in " ".join(values).casefold()
                )
                self.table.setRowHidden(row, not visible)
        finally:
            self.table.setUpdatesEnabled(True)

    def _set_visible_checked(self, state):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(state)

    def _remove_selected_rows(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        self._mark_duplicates()
        self._refresh_groups()

    def _remove_selected_groups(self):
        groups = {item.text() for item in self.groups_list.selectedItems()}
        if not groups:
            return
        rows = [
            row for row in range(self.table.rowCount())
            if (self.table.item(row, 1).text().strip() or "Sin grupo") in groups
        ]
        if not rows:
            return
        answer = QMessageBox.question(
            self, "Eliminar grupos", f"Se eliminarán {len(rows)} canales de {len(groups)} grupo(s). ¿Continuar?"
        )
        if answer != QMessageBox.Yes:
            return
        for row in reversed(rows):
            self.table.removeRow(row)
        self._mark_duplicates()
        self._refresh_groups()

    @staticmethod
    def _check_streams(urls: list[str]) -> dict[str, str]:
        def check(url: str) -> tuple[str, str]:
            if not url.lower().startswith(("http://", "https://")):
                return url, "No verificable"
            try:
                response = requests.get(url, stream=True, timeout=(4, 8), headers={"User-Agent": "TDTRadioVIP"})
                response.close()
                return url, "OK" if response.status_code < 400 else f"Error HTTP {response.status_code}"
            except requests.RequestException:
                return url, "Sin respuesta"

        results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(check, url) for url in set(urls)]
            for future in as_completed(futures):
                url, status = future.result()
                results[url] = status
        return results

    def _start_analysis(self):
        if not self.table.rowCount() or getattr(self, "_analysis_worker", None):
            return
        urls = [self.table.item(row, 3).text().strip() for row in range(self.table.rowCount())]
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analizando…")
        worker = FetchWorker(self._check_streams, urls)
        worker.done.connect(self._finish_analysis)
        worker.finished.connect(lambda: setattr(self, "_analysis_worker", None))
        self._analysis_worker = worker
        worker.start()

    def _finish_analysis(self, results):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analizar lista")
        if not isinstance(results, dict):
            QMessageBox.warning(self, "Análisis interrumpido", "No se pudo comprobar la lista.")
            return
        for row in range(self.table.rowCount()):
            url = self.table.item(row, 3).text().strip()
            status_item = self.table.item(row, 4)
            prefix = "Duplicado · " if status_item.text() == "Duplicado" else ""
            status_item.setText(prefix + results.get(url, "Sin respuesta"))

    def _export(self):
        entries = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() != Qt.Checked:
                continue
            name = self.table.item(row, 2).text().strip()
            url = self.table.item(row, 3).text().strip()
            if name and url:
                entries.append({"name": name, "url": url, "group": self.table.item(row, 1).text().strip()})
        if not entries:
            QMessageBox.information(self, "Lista vacía", "No hay canales marcados para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar lista M3U", "lista_editada.m3u", "Listas M3U (*.m3u)")
        if not path:
            return
        try:
            export_m3u(entries, path)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo exportar", str(exc))
            return
        QMessageBox.information(self, "Lista exportada", f"Se exportaron {len(entries)} canales.")
