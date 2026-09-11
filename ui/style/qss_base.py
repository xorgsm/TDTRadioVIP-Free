"""
Plantilla QSS base del tema oscuro.

Hoja de estilos estructural, sin los colores dependientes del acento:
`ui.style.builder.build_style` la toma como punto de partida y le añade
encima los bloques que varían con el acento y el tema.
"""

DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #0a0a0a;
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QWidget {
    background-color: transparent;
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QWidget#appSurface {
    background-color: #08131f;
}

/* La ventana raíz es transparente: el redondeado real lo dan la barra de
   menú (arriba) y la barra de estado (abajo), que sí pintan su propio fondo. */
QMainWindow#mainWindowRoot {
    background: transparent;
}

/* ---------- Barra de navegación superior (nav_top) ---------- */
QWidget#navTopBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0e1b2a, stop:0.48 #091522, stop:1 #06101a);
    border-bottom: 1px solid rgba(255, 255, 255, 12);
}
QToolButton#navButton {
    background: transparent;
    border: none;
    border-left: 1px solid transparent;
    border-radius: 10px;
    color: #a6b5c7;
    font-size: 10pt;
    font-weight: 650;
    padding: 9px 12px;
    margin: 2px 0;
    min-height: 24px;
    text-align: left;
}
QToolButton#navButton:hover {
    background: rgba(255, 255, 255, 9);
    color: #e6edf3;
    border-left: 1px solid rgba(255, 255, 255, 28);
}
QToolButton#navButton:checked {
    background-color: #283c5e;
    color: #f2efe6;
    border-left: 1px solid #c9a227;
}
QToolButton#navButton:focus {
    border: 1px solid #e8c360;
}

/* ---------- Barra superior ---------- */
QLabel#sectionTitle {
    color: #ffffff;
    font-size: 17pt;
    font-weight: 800;
}
QLabel#catalogCount {
    color: #8b949e;
    background-color: rgba(255, 255, 255, 8);
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 9px;
    padding: 4px 8px;
    font-size: 7.5pt;
    font-weight: 800;
    letter-spacing: 0.8px;
}
QLineEdit#searchBox {
    background-color: #0d1b2a;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    padding: 9px 14px;
    color: #e6edf3;
}
QLineEdit#searchBox:focus {
    border: 1px solid #c9a227;
    background-color: #12243a;
}
QComboBox#groupFilter:focus {
    border: 1px solid #c9a227;
    color: #f2efe6;
}
QComboBox#groupFilter {
    background-color: #142338;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    padding: 7px 12px;
    color: #b9c2ce;
}
QComboBox#groupFilter:hover {
    background-color: #1a2d45;
    border-color: #405675;
    color: #f2efe6;
}
QComboBox#groupFilter::drop-down {
    border: none;
    width: 22px;
}

/* ---------- Listas tipo tarjeta ---------- */
QListWidget#channelList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#channelList::item {
    border: none;
}
QListWidget#channelList::item:selected {
    background: transparent;
}

/* ---------- Panel de vídeo / ecualizador ---------- */
QFrame#playerFrame {
    background-color: #060606;
    border: 1px solid #2a3b55;
    border-radius: 16px;
}

/* ---------- Barra "Reproduciendo ahora" ---------- */
QFrame#nowPlayingBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e2c3e, stop:0.5 #111d2a, stop:1 #0a0a0a);
    border: 1px solid rgba(255, 255, 255, 18);
    border-top: 1px solid rgba(255, 255, 255, 26);
    border-radius: 18px;
}
QLabel#nowTitle {
    color: #ffffff;
    font-size: 14pt;
    font-weight: 750;
}
QLabel#nowSubtitle {
    color: #bcc9da;
    font-size: 8.5pt;
}
/* ---------- Botones de control ---------- */
QPushButton#playCircle {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 19px;
    font-size: 13pt;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
}
QPushButton#playCircle:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
    border: 1px solid rgba(255, 255, 255, 80);
}
QPushButton#ctrlButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#ctrlButton:hover {
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 30);
    color: #ffffff;
}
QPushButton#ctrlButton:checked {
    background-color: #c9a227;
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Enviar a Chromecast/TV: acento propio (teal) al estar activo, para no
   confundirlo visualmente con "favorito" (dorado) ni con "grabando" (rojo). */
QPushButton#castButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    font-size: 9pt;
}
QPushButton#castButton:hover {
    background: rgba(47, 181, 154, 12);
    border: 1px solid rgba(58, 209, 181, 110);
}
QPushButton#castButton:checked {
    background-color: #2fb59a;
    color: #062b23;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Temporizador de apagado: acento violeta al estar activo. */
QPushButton#sleepButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    font-size: 9pt;
}
QPushButton#sleepButton:hover {
    background: rgba(167, 139, 250, 10);
    border: 1px solid rgba(167, 139, 250, 110);
}
QPushButton#sleepButton:checked {
    background-color: #8b7ae0;
    color: #171233;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Silencio: acento azulado discreto, sin usar el dorado de "favorito". */
QPushButton#muteButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#muteButton:hover {
    background: rgba(91, 155, 213, 10);
    border: 1px solid rgba(91, 155, 213, 110);
}
QPushButton#muteButton:checked {
    background-color: #4a7fb5;
    color: #0d1b2a;
    border: 1px solid rgba(255, 255, 255, 50);
}
QPushButton#recordButton {
    background-color: #242424;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 10);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#recordButton:hover {
    background: rgba(218, 54, 51, 14);
    border: 1px solid rgba(218, 54, 51, 80);
}
QPushButton#recordButton:checked {
    background-color: #da3633;
    color: white;
    border: 1px solid rgba(255, 255, 255, 40);
}

/* ---------- Genéricos ---------- */
QPushButton {
    background-color: #242424;
    color: #e6edf3;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #2a2a2a;
}
QPushButton:focus {
    border: 1px solid #e8c360;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    /* Tramo ya "recorrido" del volumen, coloreado con el acento -- antes
       el carril era gris plano de punta a punta y solo el mando marcaba
       el nivel; así se ve de un vistazo cuánto volumen hay sin fijarse en
       la posición exacta del mando. */
    background: #c9a227;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #c9a227;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}
/* Sliders verticales del ecualizador (ver ui/equalizer_dialog.py) -- sin
   esta sección, Qt los pinta con el estilo nativo del sistema en vez del
   tema oscuro, y desentonan de golpe con el resto del diálogo. */
QSlider::groove:vertical {
    width: 4px;
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::sub-page:vertical {
    background: #c9a227;
    border-radius: 2px;
}
QSlider::add-page:vertical {
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: #c9a227;
    height: 12px;
    margin: 0 -5px;
    border-radius: 6px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 3px 1px 3px 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 22);
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 38);
}
QScrollBar::handle:vertical:pressed {
    background: #c9a227;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    /* Sin esto, Qt rellena el carril (la zona por la que se desliza el
       mando) con su patrón de rejilla por defecto en vez de un color
       plano — es justo lo que se veía como "no sólido". */
    background: transparent;
    border: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 3px 1px 3px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 22);
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 38);
}
QScrollBar::handle:horizontal:pressed {
    background: #c9a227;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}
QSplitter#mainSplitter::handle {
    background-color: #2a3b55;
    width: 1px;
}
QSplitter#mainSplitter::handle:hover {
    background-color: #c9a227;
}
QFrame#ctrlSeparator {
    background-color: rgba(255, 255, 255, 26);
}
QStatusBar {
    background-color: #050d17;
    color: #6e7787;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}
QMenu {
    background-color: #181818;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 10px;
    padding: 4px;
}
QMenu::item {
    padding: 9px 14px;
    border-radius: 7px;
    margin: 1px 3px;
}
QMenu::item:selected {
    background-color: #c9a227;
    color: #0a0a0a;
    border-radius: 7px;
}

/* ---------- Barra de título propia ---------- */
QWidget#titleBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #11243a, stop:1 #08131f);
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 8);
}
QLabel#titleBrand {
    color: #c9a227;
    font-weight: 800;
    font-size: 12pt;
    letter-spacing: 0.3px;
    background: transparent;
}
QLabel#titleVersion {
    color: #8b949e;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.7px;
    background: transparent;
}
QLabel#editionBadge {
    background-color: transparent;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 6.5pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#editionBadge[uiVariant="free"] {
    color: #55a7e8;
    border: 1px solid #55a7e8;
}
QLabel#editionBadge[uiVariant="licensed"] {
    color: #42c985;
    border: 1px solid #42c985;
}
QLabel#editionBadge[uiVariant="unactivated"] {
    color: #f26f6c;
    border: 1px solid #f26f6c;
}
/* ---------- Controles de ventana (minimizar / maximizar / cerrar) ---------- */
QToolButton#winCtrlButton {
    background: transparent;
    border: none;
    color: #d8dee8;
    font-size: 13pt;
    font-weight: 600;
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
}
QToolButton#winCtrlButton:hover {
    background-color: rgba(255, 255, 255, 10);
    color: #ffffff;
}
QToolButton#winCloseButton {
    background: transparent;
    border: none;
    color: #d8dee8;
    font-size: 14pt;
    font-weight: 600;
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
}
QToolButton#winCloseButton:hover {
    background-color: #e81123;
    color: white;
}
QLineEdit, QComboBox {
    background-color: #181818;
    border: 1px solid #2a2a2a;
    border-radius: 9px;
    padding: 6px 10px;
    color: #e6edf3;
}
/* Lista desplegable de QComboBox: sin esto, Qt la pinta con la paleta
   nativa del sistema (fondo claro, texto oscuro/apenas visible) en vez del
   tema oscuro -- afectaba a TODOS los combos de la app (filtro de
   categoría, selectores de Configuración, el de "Gestionar canales
   personalizados"...), no solo a uno. */
QComboBox QAbstractItemView {
    background-color: #181818;
    color: #e6edf3;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: #c9a227;
    selection-color: #0a0a0a;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    min-height: 22px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #2a2a2a;
}

/* Botón principal ("Guardar", "Importar", "Aceptar"...) en los diálogos de
   Configuración / Añadir canal / Importar lista: antes todos los botones
   del cuadro de diálogo eran iguales entre sí y no se distinguían de los
   controles de canal; con esto la acción principal queda al mismo nivel
   visual que "reproducir" o "favorito" en el resto de la app. */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 50);
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
}

/* Pestañas (panel de Descargas: "Vídeo (URL)" / "Torrents"). Sin esto,
   QTabWidget usa el estilo nativo de Windows para la barra de pestañas —
   fondo claro con texto claro encima, prácticamente en blanco sobre el
   resto de la interfaz oscura. */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 10px;
    background-color: #121212;
    top: -1px;
}
QTabBar::tab {
    background-color: #181818;
    color: #8b949e;
    padding: 9px 20px;
    border: 1px solid rgba(255, 255, 255, 10);
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    margin-right: 2px;
}
QTabBar::tab:hover {
    background-color: rgba(255, 255, 255, 7);
    color: #e6edf3;
}
QTabBar::tab:selected {
    background-color: #121212;
    color: #f4d476;
    font-weight: 700;
    border-top: 2px solid #c9a227;
}

/* ---------- Diálogos (Configuración / Añadir canal / Importar lista) ----------
   Antes eran un QFormLayout plano sin ninguna jerarquía visual — ahora los
   campos relacionados van agrupados en paneles con el mismo lenguaje visual
   (degradado sutil + borde translúcido) que ya usa la barra de reproducción,
   en vez de quedar todos al mismo nivel. */
QFrame#dialogPanel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c2c40, stop:1 #121e2e);
    border: 1px solid rgba(255, 255, 255, 16);
    border-top: 1px solid rgba(255, 255, 255, 24);
    border-radius: 14px;
}
QLabel#dialogTitle {
    color: #ffffff;
    font-size: 16pt;
    font-weight: 800;
}
QLabel#dialogSubtitle {
    color: #bcc9da;
    font-size: 8.5pt;
}
QLabel#dialogSectionLabel {
    color: #c9a227;
    font-weight: 700;
    font-size: 8pt;
    letter-spacing: 1.5px;
}

/* ---------- Portada de Inicio ---------- */
QScrollArea#homeScroll, QScrollArea#homeScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QLabel#homeGreeting {
    color: #ffffff;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: -0.3px;
}
QLabel#homeHealthSummary {
    color: #a6b5c7;
    font-size: 9pt;
}
QLabel#homeHealthSummary[uiVariant="success"] { color: #42c985; }
QLabel#homeHealthSummary[uiVariant="danger"] { color: #f26f6c; }
QPushButton#homeQuickButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 22px;
    font-weight: 700;
    padding: 11px 22px;
}
QPushButton#homeQuickButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
    border: 1px solid rgba(255, 255, 255, 80);
}
QPushButton#homeQuickButtonAlt {
    background-color: rgba(255, 255, 255, 6);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 16);
    border-radius: 22px;
    font-weight: 700;
    padding: 11px 22px;
}
QPushButton#homeQuickButtonAlt:hover {
    background-color: rgba(255, 255, 255, 12);
    border: 1px solid rgba(255, 255, 255, 32);
}

/* ---------- Lenguaje compartido: vistas secundarias y diálogos ---------- */
QWidget#downloadPanel {
    background: transparent;
}
QTabWidget#mediaTabs::pane {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #13243a, stop:1 #0c1827);
    border: 1px solid #2a3b55;
    border-radius: 14px;
    top: -1px;
    padding: 8px;
}
QTabWidget#mediaTabs QTabBar::tab {
    background: transparent;
    color: #8fa1b8;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 7px;
    margin: 0 2px;
    padding: 9px 13px;
    font-weight: 650;
}
QTabWidget#mediaTabs QTabBar::tab:hover {
    background: rgba(255, 255, 255, 8);
    color: #f2efe6;
}
QTabWidget#mediaTabs QTabBar::tab:selected {
    background: rgba(201, 162, 39, 20);
    color: #f4d476;
    border-bottom-color: #c9a227;
}
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #12243a, stop:1 #091522);
}
QDialog QLabel#dialogTitle {
    color: #f2efe6;
    font-size: 17pt;
    font-weight: 800;
}
QDialog QLabel#dialogSubtitle {
    color: #8fa1b8;
    font-size: 9pt;
}
QDialog QLineEdit, QDialog QPlainTextEdit, QDialog QTextEdit {
    background-color: #0d1b2a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: #c9a227;
    selection-color: #0d1b2a;
}
QDialog QLineEdit:focus, QDialog QPlainTextEdit:focus, QDialog QTextEdit:focus {
    border-color: #c9a227;
    background-color: #12243a;
}
QDialog QComboBox, QDialog QSpinBox, QDialog QDateTimeEdit {
    background-color: #0d1b2a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 9px;
    padding: 7px 10px;
}
QDialog QListWidget, QDialog QTableWidget {
    background-color: #0d1b2a;
    alternate-background-color: #12243a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    outline: none;
}
QDialog QListWidget::item, QDialog QTableWidget::item {
    padding: 7px;
    border-radius: 6px;
}
QDialog QListWidget::item:selected, QDialog QTableWidget::item:selected {
    background-color: rgba(201, 162, 39, 48);
    color: #f4d476;
}
QDialog QCheckBox, QDialog QRadioButton {
    color: #dbe5f1;
    spacing: 8px;
}
QDialog QGroupBox {
    color: #c9a227;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 750;
}
QDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""
