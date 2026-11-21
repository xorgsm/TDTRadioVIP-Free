"""Barra superior global (rediseño v10): una fila de 56 px a la derecha del
raíl, encima del contenido, con la búsqueda siempre a la vista (abre la
paleta de comandos, Ctrl+K) y el acceso a Multivista.

No confundir con ui.catalog_toolbar.build_top_bar, que es la cabecera de
cada sección (título, filtros y buscador del catálogo).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from ui import icons as app_icons
from ui import palette

TOP_BAR_HEIGHT = 56
SEARCH_HINT = "Buscar canales, emisoras, programas, podcasts…"
SEARCH_SHORTCUT = "Ctrl K"
SEARCH_MAX_WIDTH = 560


def _build_search_trigger(win) -> QPushButton:
    """Botón con aspecto de campo: no se escribe en él, abre la paleta de
    comandos igual que ui.more_menu.build_global_search_button."""
    btn = QPushButton()
    btn.setObjectName("topSearchField")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("Búsqueda global (Ctrl+K)")
    btn.setAccessibleName("Búsqueda global")
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn.setMaximumWidth(SEARCH_MAX_WIDTH)
    btn.setMinimumWidth(160)
    row = QHBoxLayout(btn)
    row.setContentsMargins(12, 0, 8, 0)
    row.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(app_icons.icon_search(palette.TEXT_MUTED).pixmap(16, 16))
    hint = QLabel(SEARCH_HINT)
    hint.setObjectName("topSearchHint")
    # El texto se recorta en ventanas estrechas en vez de empujar la fila.
    hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    kbd = QLabel(SEARCH_SHORTCUT)
    kbd.setObjectName("topSearchKbd")
    for label in (icon, hint, kbd):
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    row.addWidget(icon, 0, Qt.AlignVCenter)
    row.addWidget(hint, 1)
    row.addWidget(kbd, 0, Qt.AlignVCenter)
    btn.clicked.connect(lambda: win.dialogs.open_command_palette())
    return btn


def build_app_top_bar(win) -> QWidget:
    bar = QWidget()
    bar.setObjectName("appTopBar")
    bar.setFixedHeight(TOP_BAR_HEIGHT)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(20, 0, 20, 0)
    layout.setSpacing(12)

    win.top_search_btn = _build_search_trigger(win)
    layout.addWidget(win.top_search_btn, 1)

    # Mismo destino que la entrada «Multivista (mosaico)…» del menú «Más».
    mosaic_btn = QPushButton("Multivista")
    mosaic_btn.setObjectName("topChip")
    mosaic_btn.setCursor(Qt.PointingHandCursor)
    mosaic_btn.setToolTip("Ver varios canales a la vez")
    mosaic_btn.clicked.connect(lambda: win.dialogs.open_mosaic_view())
    layout.addWidget(mosaic_btn)
    return bar
