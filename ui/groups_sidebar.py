"""
Panel lateral de grupos/categorías del catálogo de TV: lista cada
group-title de la lista M3U cargada (pública + personalizada) con el
número de canales que tiene -- al estilo del panel de grupos del editor
M3U de escritorio. Selección múltiple con Ctrl/Shift para filtrar el
catálogo de TV por uno o varios grupos a la vez.

Panel aditivo: se inserta en el root layout junto a LibrarySidebar (ver
ui/main_window._build_ui) y solo se muestra durante la sección de
Televisión (ver MainWindow._on_nav_changed) -- Radio y el resto de
secciones no tienen "grupo" como concepto en esta app.

Coder By X@R
"""
from typing import Callable, Dict, Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget,
)

ROLE_GROUP = Qt.UserRole + 71
ALL_LABEL = "(Todos)"


class GroupsSidebar(QWidget):
    """Panel de grupos de TV, con contador de canales por grupo."""

    def __init__(
        self,
        on_selection_changed: Callable[[Optional[Set[str]]], None],
        on_delete_groups: Optional[Callable[[Set[str]], None]] = None,
    ):
        super().__init__()
        self._on_selection_changed = on_selection_changed
        self._on_delete_groups = on_delete_groups
        self._updating = False
        self.setObjectName("groupsSidebar")
        self.setProperty("uiSurface", "sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 12, 14)
        layout.setSpacing(6)

        heading = QLabel("GRUPOS")
        heading.setObjectName("libraryHeading")
        layout.addWidget(heading)

        hint = QLabel("Ctrl/Shift + clic para elegir varios")
        hint.setObjectName("libSectionTitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(4)
        self.group_list = QListWidget()
        self.group_list.setObjectName("groupsSidebarList")
        self.group_list.setFrameShape(QListWidget.NoFrame)
        self.group_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.group_list.itemSelectionChanged.connect(self._emit_selection)
        if self._on_delete_groups is not None:
            self.group_list.setContextMenuPolicy(Qt.CustomContextMenu)
            self.group_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.group_list, stretch=1)

    # ---------- Menú contextual (eliminar grupo) ----------

    def _show_context_menu(self, pos):
        item = self.group_list.itemAt(pos)
        if item is None or item.data(ROLE_GROUP) is None:
            return  # fondo vacío o "(Todos)": nada que eliminar

        # Si el clic derecho cae sobre un grupo que ya formaba parte de una
        # selección múltiple (Ctrl/Shift), se actúa sobre toda esa
        # selección; si no, el clic derecho selecciona solo ese grupo,
        # igual que en el resto de listas de la app.
        if not item.isSelected():
            self.group_list.setCurrentItem(item)
        names = {
            it.data(ROLE_GROUP) for it in self.group_list.selectedItems()
            if it.data(ROLE_GROUP) is not None
        }
        if not names:
            return

        menu = QMenu(self)
        texto = "Eliminar grupo…" if len(names) == 1 else f"Eliminar {len(names)} grupos…"
        delete_action = menu.addAction(texto)
        if menu.exec(self.group_list.viewport().mapToGlobal(pos)) == delete_action:
            self._on_delete_groups(names)

    # ---------- Poblado ----------

    def set_groups(self, counts: Dict[str, int]):
        """
        Repuebla la lista a partir de {nombre_de_grupo: nº_canales}.
        Conserva la selección de grupos que sigan existiendo tras el
        refresco (p.ej. al añadir un canal nuevo no debe perderse el
        filtro que el usuario ya tenía puesto) -- solo cae a "(Todos)" si
        ninguno de los grupos seleccionados sigue existiendo.
        """
        previous = self._selected_names()
        self._updating = True
        try:
            self.group_list.clear()
            item_all = QListWidgetItem(f"{ALL_LABEL}  ({sum(counts.values())})")
            item_all.setData(ROLE_GROUP, None)
            self.group_list.addItem(item_all)
            rows_by_name = {}
            for name in sorted(counts, key=lambda g: -counts[g]):
                item = QListWidgetItem(f"{name}  ({counts[name]})")
                item.setData(ROLE_GROUP, name)
                self.group_list.addItem(item)
                rows_by_name[name] = self.group_list.count() - 1
            rows = [rows_by_name[n] for n in previous if n in rows_by_name] if previous else []
            self._select_rows_or_all(rows)
        finally:
            self._updating = False

    def select_groups(self, names: Optional[Set[str]]):
        """Selecciona por nombre desde fuera (p.ej. al restaurar un filtro guardado)."""
        rows = []
        if names:
            for i in range(self.group_list.count()):
                item = self.group_list.item(i)
                if item.data(ROLE_GROUP) in names:
                    rows.append(i)
        self._updating = True
        try:
            self._select_rows_or_all(rows)
        finally:
            self._updating = False

    def _select_rows_or_all(self, rows):
        self.group_list.clearSelection()
        if rows:
            for r in rows:
                self.group_list.item(r).setSelected(True)
            self.group_list.setCurrentRow(rows[0])
        elif self.group_list.count():
            self.group_list.setCurrentRow(0)

    # ---------- Selección ----------

    def current_selection(self) -> Optional[Set[str]]:
        """
        Grupos seleccionados ahora mismo (None = "(Todos)"). Público para
        que quien puebla la lista pueda releer el estado real tras un
        set_groups() que haya tenido que caer a "(Todos)" porque algún
        grupo antes seleccionado ya no existe (p.ej. se borró ese grupo).
        """
        return self._selected_names()

    def _selected_names(self) -> Optional[Set[str]]:
        selected = self.group_list.selectedItems()
        if not selected:
            return None
        names = {it.data(ROLE_GROUP) for it in selected}
        return None if None in names else names

    def _emit_selection(self):
        if self._updating:
            return
        self._on_selection_changed(self._selected_names())
