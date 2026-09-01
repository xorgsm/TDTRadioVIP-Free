"""Centro de próximas grabaciones EPG y recurrentes materializadas."""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from core import recording_schedule
from ui.visual import set_surface


def _format_xmltv(value: str) -> str:
    try:
        return datetime.strptime(value[:14], "%Y%m%d%H%M%S").strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return value or "Hora desconocida"


class ScheduledRecordingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Centro de grabaciones programadas")
        self.setMinimumSize(620, 420)

        root = QVBoxLayout(self)
        title = QLabel("Próximas grabaciones")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "Reservas creadas desde la guía y reglas recurrentes ya preparadas para grabar."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget, 1)

        actions = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self._reload)
        actions.addWidget(refresh)
        self.cancel_btn = QPushButton("Cancelar seleccionada")
        self.cancel_btn.clicked.connect(self._cancel_selected)
        actions.addWidget(self.cancel_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        root.addWidget(buttons)
        self._reload()

    def _reload(self):
        self.list_widget.clear()
        status_labels = {"pending": "Pendiente", "recording": "Grabando", "error": "Fallida"}
        records = sorted(recording_schedule.load_scheduled(), key=lambda rec: rec.start)
        for rec in records:
            text = (
                f"{_format_xmltv(rec.start)} · {rec.channel_name}\n"
                f"{rec.title} · {status_labels.get(rec.status, rec.status)}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, (rec.tvg_id, rec.title, rec.start))
            self.list_widget.addItem(item)
        if not records:
            empty = QListWidgetItem("No hay grabaciones programadas.")
            empty.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(empty)
        self.cancel_btn.setEnabled(bool(records))

    def _cancel_selected(self):
        item = self.list_widget.currentItem()
        identity = item.data(Qt.UserRole) if item else None
        if not identity:
            return
        recording_schedule.remove_scheduled(*identity)
        self._reload()
