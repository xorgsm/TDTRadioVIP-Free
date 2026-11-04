"""
Plantilla QSS de los controles y la estructura de la ventana.

Es una `string.Template`: cada color y fuente es un token `$nombre` que
`ui.style.builder.build_style` resuelve según el acento y el tema. Un token
sin definir falla al construir el estilo, no con un color suelto en pantalla.
"""

DARK_STYLE = """
QMainWindow, QDialog {
    background-color: $bg_root;
    color: $text;
    font-family: $body_font;
    font-size: 10pt;
}
QWidget {
    background-color: transparent;
    color: $text;
    font-family: $body_font;
    font-size: 10pt;
}
QWidget#appSurface {
    background-color: $bg_root;
}

/* La ventana raíz es transparente: el redondeado real lo dan la barra de
   título (arriba) y la barra de estado (abajo), que sí pintan su fondo. */
QMainWindow#mainWindowRoot {
    background: transparent;
}

/* ---------- Títulos: la voz de la cadena ---------- */
QLabel#sectionTitle,
QLabel#titleBrand,
QLabel#dialogTitle,
QDialog QLabel#dialogTitle,
QLabel#homeGreeting,
QDialog QLabel#titulo {
    font-family: $display_font;
    font-weight: 800;
}

/* ---------- Barra de título propia ---------- */
QWidget#titleBar {
    background-color: $bg_panel;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
QFrame#identStrip {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, $ident_stops);
    border: none;
}
QLabel#titleBrand {
    color: $text;
    font-size: 13pt;
}
QLabel#titleVersion {
    color: $muted;
    font-size: 8pt;
    font-weight: 700;
}
QLabel#editionBadge {
    background-color: transparent;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 7pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#editionBadge[uiVariant="free"] {
    color: $tv;
    border: 1px solid $tv;
}
QLabel#editionBadge[uiVariant="licensed"] {
    color: $success;
    border: 1px solid $success;
}
QLabel#editionBadge[uiVariant="unactivated"] {
    color: $danger;
    border: 1px solid $danger;
}
QToolButton#winCtrlButton, QToolButton#winCloseButton {
    background: transparent;
    border: none;
    color: $text2;
    font-size: 13pt;
    font-weight: 600;
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
}
QToolButton#winCtrlButton:hover {
    background-color: $wash_strong;
    color: $text;
}
QToolButton#winCloseButton:hover {
    background-color: #e81123;
    color: #ffffff;
}

/* ---------- Navegación superior ---------- */
QWidget#navTopBar {
    background-color: $bg_panel;
    border-bottom: 1px solid $border;
}
QToolButton#navButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    color: $text2;
    font-size: 10.5pt;
    font-weight: 700;
    padding: 9px 14px;
    margin: 2px 0;
    min-height: 24px;
    text-align: left;
}
QToolButton#navButton:hover {
    background-color: $bg_alt;
    color: $text;
}
QToolButton#navButton:checked {
    background-color: $bg_alt;
    color: $text;
}
QToolButton#navButton:focus {
    border: 1px solid $accent_light;
}
QToolButton#navButton::menu-indicator {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 2px;
}

/* ---------- Cabecera de sección y buscador ---------- */
QLabel#sectionTitle {
    color: $text;
    font-size: 20pt;
}
QLabel#catalogCount {
    color: $muted;
    background-color: $wash;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 4px 8px;
    font-size: 8pt;
    font-weight: 700;
}
QLineEdit#searchBox, QComboBox#groupFilter {
    background-color: $bg_panel;
    border: 1px solid $border;
    border-radius: 10px;
    color: $text;
}
QLineEdit#searchBox {
    padding: 10px 16px;
}
QLineEdit#searchBox:focus {
    border: 1px solid $accent;
    background-color: $bg_card;
}
QComboBox#groupFilter {
    padding: 9px 15px;
    color: $text2;
}
QComboBox#groupFilter:hover {
    background-color: $bg_hover;
    border-color: $border_strong;
    color: $text;
}
QComboBox#groupFilter:focus {
    border: 1px solid $accent;
    color: $text;
}
QComboBox#groupFilter::drop-down {
    border: none;
    width: 22px;
}
QToolButton#catalogViewToggle {
    background-color: $bg_panel;
    color: $dim;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 3px;
}
QToolButton#catalogViewToggle:hover {
    background-color: $bg_hover;
    border-color: $border_strong;
}
QToolButton#catalogViewToggle:checked {
    background-color: $accent;
    border-color: $accent_hover;
}

/* ---------- Listas de canales ---------- */
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

/* ---------- Botones genéricos ---------- */
QPushButton {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 9px 18px;
    min-height: 22px;
    font-size: 10.5pt;
    font-weight: 650;
}
QPushButton:hover {
    background-color: $bg_hover;
    border-color: $border_strong;
}
QPushButton:pressed {
    background-color: $bg_card;
}
QPushButton:focus {
    border: 1px solid $accent_light;
}
QPushButton:disabled {
    background-color: $bg_panel;
    color: $dim;
    border-color: $border;
}
QPushButton[uiVariant="primary"], QPushButton#primaryButton {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    font-weight: 700;
}
QPushButton[uiVariant="primary"]:hover, QPushButton#primaryButton:hover {
    background-color: $accent_hover;
    border-color: $accent_hover;
}
QPushButton[uiVariant="primary"]:pressed, QPushButton#primaryButton:pressed {
    background-color: $accent_pressed;
}
QPushButton[uiVariant="primary"]:focus, QPushButton#primaryButton:focus {
    border: 2px solid $text;
}
QPushButton[uiVariant="secondary"], QToolButton[uiVariant="secondary"] {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
}
QPushButton[uiVariant="secondary"]:hover, QToolButton[uiVariant="secondary"]:hover {
    background-color: $bg_hover;
    border-color: $border_strong;
}
QPushButton[uiVariant="danger"], QToolButton[uiVariant="danger"] {
    background-color: transparent;
    color: $danger;
    border: 1px solid $danger;
    border-radius: 10px;
}
QPushButton[uiVariant="danger"]:hover, QToolButton[uiVariant="danger"]:hover {
    background-color: $block_danger;
    color: $ink;
}
QPushButton[uiVariant="success"], QToolButton[uiVariant="success"] {
    background-color: transparent;
    color: $success;
    border: 1px solid $success;
    border-radius: 10px;
}
QPushButton[uiVariant="success"]:hover, QToolButton[uiVariant="success"]:hover {
    background-color: $block_success;
    color: $ink;
}
QPushButton[uiVariant="cast"] {
    background-color: $bg_alt;
    color: $cast;
    border: 1px solid $cast;
    border-radius: 10px;
}
QPushButton[uiVariant="cast"]:hover {
    background-color: $block_cast;
    color: $ink;
}
QPushButton#toastClose, QPushButton[uiVariant="ghost"] {
    background: transparent;
    color: $muted;
    border: none;
}
QPushButton#toastClose:hover, QPushButton[uiVariant="ghost"]:hover {
    color: $text;
}

/* ---------- Transporte del reproductor ---------- */
QPushButton#playCircle {
    background-color: $accent;
    color: $on_accent;
    border: none;
    border-radius: 23px;
    min-width: 46px;
    max-width: 46px;
    min-height: 46px;
    max-height: 46px;
    padding: 0;
}
QPushButton#playCircle:hover {
    background-color: $accent_hover;
}
QPushButton#playCircle:pressed {
    background-color: $accent_pressed;
}
QPushButton#playCircle:focus {
    border: 2px solid $text;
}
QPushButton#ctrlButton,
QPushButton#castButton,
QPushButton#sleepButton,
QPushButton#muteButton,
QPushButton#recordButton {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid transparent;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    border-radius: 17px;
    padding: 0;
    font-size: 9pt;
}
QPushButton#ctrlButton:hover {
    background-color: $bg_hover;
    border-color: $border_strong;
}
QPushButton#ctrlButton:focus,
QPushButton#castButton:focus,
QPushButton#sleepButton:focus,
QPushButton#muteButton:focus,
QPushButton#recordButton:focus {
    border: 1px solid $accent_light;
}
QPushButton#ctrlButton:disabled {
    background-color: transparent;
}
QPushButton#ctrlButton:checked {
    background-color: $accent;
    color: $on_accent;
}
QPushButton#castButton:hover { border-color: $cast; }
QPushButton#sleepButton:hover { border-color: $sleep; }
QPushButton#muteButton:hover { border-color: $tv; }
QPushButton#recordButton:hover { border-color: $danger; }
QPushButton#castButton:checked {
    background-color: $block_cast;
    color: $ink;
}
QPushButton#sleepButton:checked {
    background-color: $block_sleep;
    color: $ink;
}
QPushButton#muteButton:checked {
    background-color: $block_tv;
    color: $ink;
}
QPushButton#recordButton:checked {
    background-color: $block_danger;
    color: $ink;
}
QFrame#ctrlSeparator {
    background-color: $border;
}

/* ---------- Deslizadores ---------- */
QSlider::groove:horizontal {
    height: 4px;
    background: $bg_hover;
    border-radius: 2px;
}
/* El tramo recorrido lleva el acento para leer el nivel de un vistazo. */
QSlider::sub-page:horizontal {
    background: $accent;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: $bg_hover;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: $accent;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}
/* Verticales del ecualizador (ver ui/equalizer_dialog.py): sin esto, Qt
   los pinta con el estilo nativo del sistema. */
QSlider::groove:vertical {
    width: 4px;
    background: $bg_hover;
    border-radius: 2px;
}
QSlider::sub-page:vertical {
    background: $bg_hover;
    border-radius: 2px;
}
QSlider::add-page:vertical {
    background: $accent;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: $accent;
    height: 12px;
    margin: 0 -5px;
    border-radius: 6px;
}
QSlider#volumeSlider::groove:horizontal {
    background: $bg_root;
    height: 5px;
    border-radius: 2px;
}
QSlider#volumeSlider::handle:horizontal {
    background: $accent;
    border: 2px solid $bg_panel;
    width: 13px;
    margin: -5px 0;
    border-radius: 7px;
}

/* ---------- Barras de desplazamiento ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 3px 1px 3px 0;
}
QScrollBar::handle:vertical {
    background: $bg_hover;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: $border_strong;
}
QScrollBar::handle:vertical:pressed {
    background: $accent;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}
/* Sin esto, Qt rellena el carril con su patrón de rejilla por defecto. */
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 3px 1px 3px;
}
QScrollBar::handle:horizontal {
    background: $bg_hover;
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: $border_strong;
}
QScrollBar::handle:horizontal:pressed {
    background: $accent;
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

/* ---------- Estructura ---------- */
QSplitter#mainSplitter::handle {
    background-color: $border;
    width: 1px;
}
QSplitter#mainSplitter::handle:hover {
    background-color: $accent;
}
QStatusBar {
    background-color: $bg_panel;
    color: $muted;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}

/* ---------- Menús ---------- */
QMenu {
    background-color: $bg_card;
    color: $text;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 4px;
    font-weight: 500;
}
QMenu::item {
    padding: 9px 16px;
    border-radius: 7px;
    margin: 1px 3px;
}
QMenu::item:selected {
    background-color: $accent;
    color: $on_accent;
}

/* ---------- Campos ---------- */
QLineEdit, QComboBox {
    background-color: $bg_card;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 8px 12px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QComboBox::drop-down {
    border: none;
    background: transparent;
    width: 24px;
}
/* Lista desplegable de QComboBox: sin esto, Qt la pinta con la paleta
   nativa del sistema en vez de la del tema. */
QComboBox QAbstractItemView {
    background-color: $bg_card;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    min-height: 22px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: $bg_hover;
}

/* ---------- Pestañas ---------- */
QTabWidget::pane {
    border: 1px solid $border;
    border-radius: 12px;
    background-color: $bg_panel;
    top: -1px;
}
QTabBar::tab {
    background-color: $bg_card;
    color: $muted;
    padding: 10px 22px;
    border: 1px solid $border;
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    margin-right: 2px;
}
QTabBar::tab:hover {
    background-color: $bg_hover;
    color: $text;
}
QTabBar::tab:selected {
    background-color: $accent;
    border-color: $accent;
    color: $on_accent;
    font-weight: 700;
}
"""
