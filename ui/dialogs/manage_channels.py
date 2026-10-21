"""
Gestión del catálogo: permite ocultar, mostrar y borrar en bloque
canales y emisoras, separando lo reversible de lo destructivo.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)

from ui import palette
from ui.visual import set_surface

from ui.dialogs._common import _header


class ManageChannelsDialog(QDialog):
    """
    Gestión de canales/emisoras en tres ámbitos, elegibles con un combo:

    - "Personalizados" -- los que el usuario añadió a mano o importó por
      M3U. Se pueden borrar de verdad (on_delete), igual que antes.
    - "Lista pública" -- los que vienen de iptv-org/Radio-Browser. No se
      pueden borrar (se descargan de nuevo en cada actualización), pero sí
      OCULTAR (on_hide) para que dejen de aparecer en las listas sin tocar
      la lista pública en sí -- pensado para los canales que vienen por
      defecto de otro país/región y no interesan.
    - "Ocultados" -- los que se ocultaron antes desde aquí. Se pueden
      RESTAURAR (on_unhide) en cualquier momento.

    El guardado real (disco + estado de la ventana) no vive aquí -- se pide
    al llamador vía on_delete(tipo, nombres) / on_hide(tipo, nombres) /
    on_unhide(tipo, nombres), igual que el resto de diálogos de este módulo
    dejan la persistencia a LibraryController. Los tres deben devolver
    cuántos se aplicaron de verdad, y este diálogo actualiza su propia
    lista visual con ese resultado sin tener que cerrarse.
    """

    _AMBITOS = [
        ("custom", "Personalizados (eliminar)"),
        ("public", "Lista pública (ocultar)"),
        ("hidden", "Ocultados (restaurar)"),
    ]

    def __init__(self, tv_datos: dict, radio_datos: dict, on_delete, on_hide, on_unhide,
                 entry_type: str = "tv", parent=None):
        """
        tv_datos / radio_datos: {"custom": [Channel/Station...],
        "public": [Channel/Station...], "hidden_names": set(str)|list(str)}.
        "public" debe venir ya SIN los ocultos (el llamador lo arma así),
        para no listar el mismo nombre a la vez en "Lista pública" y en
        "Ocultados".
        """
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Gestionar canales personalizados")
        self.setMinimumSize(560, 520)
        self._datos = {"tv": dict(tv_datos), "radio": dict(radio_datos)}
        for tipo in self._datos:
            self._datos[tipo]["hidden_names"] = set(self._datos[tipo].get("hidden_names") or ())
        self._on_delete = on_delete
        self._on_hide = on_hide
        self._on_unhide = on_unhide

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Gestionar canales personalizados",
            "Elige el tipo y el ámbito: borra tus canales personalizados, oculta "
            "canales de la lista pública que no quieras ver, o restaura los que "
            "ocultaste antes.",
        ))

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.type_combo = QComboBox()
        self.type_combo.addItem("Canales de TV", "tv")
        self.type_combo.addItem("Emisoras de radio", "radio")
        idx = self.type_combo.findData(entry_type)
        self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.type_combo.currentIndexChanged.connect(self._reload_list)
        top_row.addWidget(self.type_combo)

        self.scope_combo = QComboBox()
        for valor, etiqueta in self._AMBITOS:
            self.scope_combo.addItem(etiqueta, valor)
        self.scope_combo.currentIndexChanged.connect(self._reload_list)
        top_row.addWidget(self.scope_combo)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar por nombre…")
        self.filter_input.textChanged.connect(self._reload_list)
        top_row.addWidget(self.filter_input, stretch=1)
        root.addLayout(top_row)

        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._update_count)
        root.addWidget(self.list_widget, stretch=1)

        sel_row = QHBoxLayout()
        select_all_btn = QPushButton("Seleccionar todo")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        sel_row.addWidget(select_all_btn)
        select_none_btn = QPushButton("Ninguno")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        sel_row.addWidget(select_none_btn)
        sel_row.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("dialogSubtitle")
        sel_row.addWidget(self.count_label)
        root.addLayout(sel_row)

        buttons = QDialogButtonBox()
        # self.action_btn tiene que existir ANTES de la primera llamada a
        # _reload_list() de más abajo -- _reload_list() dispara
        # _update_count(), que lo habilita/deshabilita según haya algo
        # marcado. Con el orden invertido, esa primera llamada revienta con
        # AttributeError dentro de __init__ y todo el diálogo se queda sin
        # construir -- "le pincho pero no hace nada", sin ningún error
        # visible porque PySide se traga la excepción de un slot de menú y
        # sigue funcionando como si nada (ver bug ya resuelto con delete_btn).
        self.action_btn = buttons.addButton("Eliminar seleccionados", QDialogButtonBox.AcceptRole)
        self.action_btn.clicked.connect(self._on_action_clicked)
        close_btn = buttons.addButton("Cerrar", QDialogButtonBox.RejectRole)
        close_btn.clicked.connect(self.accept)  # cerrar no deshace lo ya aplicado

        self._reload_list()

        root.addWidget(buttons)

    # ---------- listado ----------

    def _current_names(self):
        tipo = self.type_combo.currentData()
        ambito = self.scope_combo.currentData()
        datos_tipo = self._datos[tipo]
        if ambito == "custom":
            nombres = [c.name for c in datos_tipo["custom"]]
        elif ambito == "public":
            nombres = [c.name for c in datos_tipo["public"]]
        else:
            nombres = sorted(datos_tipo["hidden_names"])
        return tipo, ambito, nombres

    def _reload_list(self):
        _tipo, _ambito, nombres = self._current_names()
        filtro = self.filter_input.text().strip().casefold()

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for nombre in nombres:
            if filtro and filtro not in nombre.casefold():
                continue
            item = QListWidgetItem(nombre)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, nombre)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._update_action_button()
        self._update_count()

    def _set_all_checked(self, checked: bool):
        estado = Qt.Checked if checked else Qt.Unchecked
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(estado)
        self.list_widget.blockSignals(False)
        self._update_count()

    def _update_action_button(self):
        _tipo, ambito, _nombres = self._current_names()
        if ambito == "custom":
            texto, color = "Eliminar seleccionados", palette.DANGER
        elif ambito == "public":
            texto, color = "Ocultar seleccionados", palette.ACCENT_CATEGORY_ORANGE
        else:
            texto, color = "Restaurar seleccionados", palette.SUCCESS
        self.action_btn.setText(texto)
        self.action_btn.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: white; font-weight: 700; }}"
        )

    def _update_count(self, *_ignorar):
        total = self.list_widget.count()
        marcados = sum(
            1 for i in range(total)
            if self.list_widget.item(i).checkState() == Qt.Checked
        )
        if total == 0:
            _tipo, ambito, _nombres = self._current_names()
            mensajes = {
                "custom": "No hay entradas personalizadas de este tipo.",
                "public": "No hay canales públicos que mostrar (o están todos ocultos).",
                "hidden": "No has ocultado ninguno todavía.",
            }
            self.count_label.setText(mensajes.get(ambito, ""))
        else:
            self.count_label.setText(f"{marcados} de {total} seleccionados")
        self.action_btn.setEnabled(marcados > 0)

    # ---------- acción: borrar / ocultar / restaurar ----------

    def _on_action_clicked(self):
        tipo, ambito, _nombres = self._current_names()
        seleccionados = [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.Checked
        ]
        if not seleccionados:
            return

        etiqueta = "canales" if tipo == "tv" else "emisoras"
        datos_tipo = self._datos[tipo]
        borrados = set(seleccionados)

        if ambito == "custom":
            if QMessageBox.question(
                self, "Eliminar seleccionados",
                f"Vas a eliminar {len(seleccionados)} {etiqueta} de tu lista personalizada. "
                "Esto no se puede deshacer desde aquí.\n\n¿Continuar?",
            ) != QMessageBox.Yes:
                return
            self._on_delete(tipo, seleccionados)
            datos_tipo["custom"] = [c for c in datos_tipo["custom"] if c.name not in borrados]

        elif ambito == "public":
            if QMessageBox.question(
                self, "Ocultar seleccionados",
                f"Vas a ocultar {len(seleccionados)} {etiqueta} de la lista pública. "
                "Podrás volver a mostrarlos desde \"Ocultados\" cuando quieras.\n\n¿Continuar?",
            ) != QMessageBox.Yes:
                return
            self._on_hide(tipo, seleccionados)
            datos_tipo["public"] = [c for c in datos_tipo["public"] if c.name not in borrados]
            datos_tipo["hidden_names"] |= borrados

        else:  # "hidden" -- restaurar es reversible e inofensivo, sin confirmación
            self._on_unhide(tipo, seleccionados)
            datos_tipo["hidden_names"] -= borrados

        self._reload_list()
