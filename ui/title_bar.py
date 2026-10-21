"""Construcción de la barra de título propia de MainWindow (marca, menú y
controles de ventana). Extraído de ui/main_window.py.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from core import config as cfg
from ui.visual import set_variant


def build_title_bar(win) -> QWidget:
    """
    Barra de título propia. Antes esto se montaba con los 'corner widgets'
    de QMenuBar, un mecanismo cuyo dibujado depende del estilo nativo y
    que en algunos equipos no llegaba a mostrarse. Aquí la disposición es
    explícita, así que se ve igual en cualquier máquina.

    Ya no aloja la barra de menú clásica (Archivo/Configuración/Ayuda,
    ui/app_menu.py) -- retirada por completo en el rediseño v8 (spec §5.2),
    redistribuida entre ui.nav_top (búsqueda global + "Más ▾", ver
    ui.more_menu) y el resto de la interfaz.
    """
    barra = QWidget()
    barra.setObjectName("titleBar")
    barra.setFixedHeight(58)

    fila = QHBoxLayout(barra)
    fila.setContentsMargins(18, 0, 8, 0)
    fila.setSpacing(12)

    # Marca + versión, apiladas: antes la versión no vivía aquí (esta
    # barra se veía apretada contra "Archivo" en ventanas no muy
    # anchas con la marca en una sola línea) y en su lugar se repetía
    # en el riel de navegación (brandLabel/versionLabel, ya retirado -- ver
    # ui.nav_top). Con la barra ya más alta para dos líneas, la marca+versión
    # viven una sola vez, más grandes, y la barra de navegación no las repite.
    marca = QLabel("TDT & Radio VIP")
    marca.setObjectName("titleBrand")
    marca.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    version_label = QLabel(f"Versión {cfg.APP_VERSION}")
    version_label.setObjectName("titleVersion")
    version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # Insignia FREE / LICENCIADA / SIN ACTIVAR junto a la versión, para
    # distinguir de un vistazo con qué edición se está probando algo --
    # mismo criterio de 3 estados que ya usaba
    # DialogActionsController.show_about ("Acerca de"), solo que visible
    # siempre, no solo al abrir ese diálogo.
    win.edition_badge = QLabel()
    win.edition_badge.setObjectName("editionBadge")
    update_edition_badge(win)

    version_row = QHBoxLayout()
    version_row.setContentsMargins(0, 0, 0, 0)
    version_row.setSpacing(6)
    version_row.addWidget(version_label)
    version_row.addWidget(win.edition_badge)
    version_row.addStretch(1)

    # Columna de ancho natural (antes se fijaba a NAV_RAIL_WIDTH para
    # alinear el menú con el contenido bajo el raíl lateral; ese raíl ya
    # no existe -- ver ui.nav_top -- así que la marca simplemente ocupa
    # el espacio que necesita su texto).
    marca_col = QWidget()
    marca_col_layout = QVBoxLayout(marca_col)
    marca_col_layout.setContentsMargins(0, 0, 0, 0)
    marca_col_layout.setSpacing(0)
    marca_col_layout.addStretch(1)
    marca_col_layout.addWidget(marca)
    marca_col_layout.addLayout(version_row)
    marca_col_layout.addStretch(1)
    fila.addWidget(marca_col)

    # Zona vacía: es la que permite arrastrar la ventana.
    fila.addStretch(1)

    min_btn = QToolButton()
    min_btn.setObjectName("winCtrlButton")
    min_btn.setText("–")
    min_btn.setCursor(Qt.PointingHandCursor)
    min_btn.setToolTip("Minimizar")
    min_btn.clicked.connect(win.showMinimized)
    fila.addWidget(min_btn)

    win._maximize_btn = QToolButton()
    win._maximize_btn.setObjectName("winCtrlButton")
    win._maximize_btn.setText("□")
    win._maximize_btn.setCursor(Qt.PointingHandCursor)
    win._maximize_btn.setToolTip("Maximizar")
    win._maximize_btn.clicked.connect(win.window_chrome.toggle_maximize)
    fila.addWidget(win._maximize_btn)

    close_btn = QToolButton()
    close_btn.setObjectName("winCloseButton")
    close_btn.setText("×")
    close_btn.setCursor(Qt.PointingHandCursor)
    close_btn.setToolTip("Cerrar")
    close_btn.clicked.connect(win.close)
    fila.addWidget(close_btn)

    barra.installEventFilter(win)
    return barra


def update_edition_badge(win) -> None:
    """Texto/color de win.edition_badge según edición y activación --
    reutilizable (no solo se llama al construir la barra de título): la
    llama también DialogActionsController.open_activation_dialog tras
    activar VIP con éxito, para que la insignia pase de "SIN ACTIVAR" a
    "LICENCIADA" sin tener que reiniciar la app."""
    if win.es_version_free:
        texto, variante = "FREE", "free"
    elif win.activated:
        texto, variante = "LICENCIADA", "licensed"
    else:
        texto, variante = "SIN ACTIVAR", "unactivated"
    win.edition_badge.setText(texto)
    set_variant(win.edition_badge, variante)
