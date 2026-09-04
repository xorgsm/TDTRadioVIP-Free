"""Modelo ligero para los catálogos grandes de TV y radio."""

from collections.abc import Callable, Iterable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, Qt
from PySide6.QtWidgets import QListView

from ui.widgets import (
    ROLE_DATA,
)


class ChannelListModel(QAbstractListModel):
    """Almacena todas las entradas y expone solo las filas visibles.

    ``QListWidget`` crea un objeto Qt completo por canal. Con catálogos de
    miles de entradas esa estructura, más los repintados de cada inserción,
    pesa bastante. Este modelo conserva los diccionarios de datos y deja que
    ``QListView`` cree/delegue únicamente lo que entra en pantalla.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[dict] = []
        self._visible_rows: list[int] = []
        self._entry_rows: dict[int, int] = {}
        self._visible_positions: dict[int, int] = {}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._visible_rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._visible_rows):
            return None
        entry = self._entries[self._visible_rows[index.row()]]
        if role == Qt.DisplayRole:
            return (entry.get(ROLE_DATA) or {}).get("name", "")
        return entry.get(role)

    def set_entries(self, entries: Iterable[dict]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self._visible_rows = list(range(len(self._entries)))
        self._entry_rows = {id(entry): row for row, entry in enumerate(self._entries)}
        self._visible_positions = {row: row for row in self._visible_rows}
        self.endResetModel()

    def entries(self) -> tuple[dict, ...]:
        return tuple(self._entries)

    def entry_at(self, row: int) -> dict | None:
        if row < 0 or row >= len(self._visible_rows):
            return None
        return self._entries[self._visible_rows[row]]

    def row_for_entry(self, entry: dict) -> int:
        source_row = self._entry_rows.get(id(entry), -1)
        if source_row < 0:
            return -1
        return self._visible_positions.get(source_row, -1)

    def set_filter(self, predicate: Callable[[dict], bool] | None) -> None:
        visible_rows = [
            row for row, entry in enumerate(self._entries)
            if predicate is None or predicate(entry)
        ]
        if visible_rows == self._visible_rows:
            return
        self.beginResetModel()
        self._visible_rows = visible_rows
        self._visible_positions = {source_row: row for row, source_row in enumerate(visible_rows)}
        self.endResetModel()

    def sort_entries(self, key: Callable[[dict], object]) -> None:
        active_entries = {
            id(self._entries[row]): self._entries[row]
            for row in self._visible_rows
        }
        self.beginResetModel()
        self._entries.sort(key=key)
        self._entry_rows = {id(entry): row for row, entry in enumerate(self._entries)}
        self._visible_rows = [
            row for row, entry in enumerate(self._entries)
            if id(entry) in active_entries
        ]
        self._visible_positions = {source_row: row for row, source_row in enumerate(self._visible_rows)}
        self.endResetModel()

    def set_entry_data(self, entry: dict, role: int, value) -> bool:
        source_row = self._entry_rows.get(id(entry), -1)
        if source_row < 0:
            return False
        entry[role] = value
        visible_row = self._visible_positions.get(source_row, -1)
        if visible_row >= 0:
            model_index = self.index(visible_row, 0)
            self.dataChanged.emit(model_index, model_index, [role])
        return True

    def update_entries(self, updater: Callable[[dict], bool]) -> None:
        changed_rows = []
        for source_row, entry in enumerate(self._entries):
            if updater(entry):
                changed_rows.append(source_row)
        for source_row in changed_rows:
            visible_row = self._visible_positions.get(source_row, -1)
            if visible_row < 0:
                continue
            model_index = self.index(visible_row, 0)
            self.dataChanged.emit(model_index, model_index, [])


class ChannelListItem:
    """Adaptador pequeño para conservar la API usada por controles antiguos."""

    def __init__(self, model: ChannelListModel, entry: dict):
        self.model = model
        self.entry = entry

    def data(self, role):
        return self.entry.get(role)

    def setData(self, role, value):
        self.model.set_entry_data(self.entry, role, value)

    def isHidden(self):
        return self.model.row_for_entry(self.entry) < 0


class ChannelListView(QListView):
    """QListView con los métodos mínimos compatibles con QListWidget."""

    def count(self) -> int:
        return self.model().rowCount() if self.model() is not None else 0

    def item(self, row: int) -> ChannelListItem | None:
        model = self.model()
        entry = model.entry_at(row) if isinstance(model, ChannelListModel) else None
        return ChannelListItem(model, entry) if entry is not None else None

    def itemAt(self, pos):
        index = self.indexAt(pos)
        return self.item(index.row()) if index.isValid() else None

    def row(self, item: ChannelListItem) -> int:
        return self.model().row_for_entry(item.entry)

    def visualItemRect(self, item: ChannelListItem):
        row = self.row(item)
        return self.visualRect(self.model().index(row, 0)) if row >= 0 else QRect()

    def clear(self) -> None:
        self.model().set_entries([])
