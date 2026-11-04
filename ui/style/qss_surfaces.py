"""
Plantilla QSS de las superficies de la aplicación: reproductor, rótulo de
"Ahora suena", Inicio, paneles de medios y diálogos. Mismos tokens `$nombre`
que `ui.style.qss_base`.
"""

SURFACES_STYLE = """
/* ---------- Estados y variantes de color ---------- */
QPushButton[uiVariant="cast"], QLabel[uiVariant="cast"] { color: $cast; }
QPushButton[uiVariant="sleep"], QLabel[uiVariant="sleep"] { color: $sleep; }
QPushButton[uiVariant="info"], QLabel[uiVariant="info"],
QPushButton[uiVariant="tv"], QLabel[uiVariant="tv"] { color: $tv; }
QPushButton[uiVariant="radio"], QLabel[uiVariant="radio"],
QPushButton[uiVariant="podcast"], QLabel[uiVariant="podcast"] { color: $radio; }
QLabel[uiVariant="success"] { color: $success; }
QLabel[uiVariant="secondary"] { color: $text2; }
QWidget[uiState="error"] { border: 1px solid $danger; }
QWidget[uiState="loading"] { color: $tv; }
QWidget[uiState="empty"] { color: $muted; }

/* ---------- Área de emisión ---------- */
QWidget#playerPanel {
    background-color: $bg_root;
}
QFrame#playerFrame {
    background-color: $video;
    border: 1px solid $border;
    border-radius: 14px;
}
QLabel#liveBadge {
    background-color: $block_danger;
    color: $ink;
    border: none;
    border-radius: 6px;
    padding: 4px 9px;
    font-size: 8.5pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#playerContextLabel {
    color: $muted;
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1px;
}

/* El lienzo del reproductor es negro también en tema claro. */
QWidget#playerIdleView QLabel#nowTitle { color: #faf7ff; }
QWidget#playerIdleView QLabel#nowSubtitle { color: #ddd7ea; }
QWidget#playerIdleView QLabel#dialogSectionLabel { color: #ddd7ea; }

/* ---------- Ahora suena: rótulo en antena ---------- */
QFrame#nowPlayingBar {
    background-color: $bg_panel;
    border: 1px solid $border;
    border-radius: 14px;
}
QFrame#nowRotulo {
    background-color: transparent;
    border: none;
    border-radius: 10px;
}
QFrame#nowRotulo[uiState="tv"] { background-color: $block_tv; }
QFrame#nowRotulo[uiState="radio"] { background-color: $block_radio; }
QFrame#nowRotulo[uiState="error"] { background-color: $block_danger; border: none; }
QLabel#nowTitle {
    color: $text;
    font-family: $display_font;
    font-size: 14pt;
    font-weight: 800;
}
QLabel#nowSubtitle {
    color: $text2;
    font-size: 9pt;
}
QFrame#nowRotulo[uiState="tv"] QLabel#nowTitle,
QFrame#nowRotulo[uiState="tv"] QLabel#nowSubtitle,
QFrame#nowRotulo[uiState="radio"] QLabel#nowTitle,
QFrame#nowRotulo[uiState="radio"] QLabel#nowSubtitle,
QFrame#nowRotulo[uiState="error"] QLabel#nowTitle,
QFrame#nowRotulo[uiState="error"] QLabel#nowSubtitle {
    color: $ink;
}
QLabel#nowLogo {
    background-color: $bg_alt;
    border-radius: 8px;
}
QFrame#nowRotulo[uiState="tv"] QLabel#nowLogo,
QFrame#nowRotulo[uiState="radio"] QLabel#nowLogo,
QFrame#nowRotulo[uiState="error"] QLabel#nowLogo {
    background-color: $video;
}

/* ---------- Inicio ---------- */
QScrollArea#homeScroll, QScrollArea#homeScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QFrame#homeHero {
    background-color: $home;
    border: none;
    border-radius: 14px;
}
QLabel#homeGreeting {
    color: $ink;
    font-size: 30pt;
}
QFrame#homeHero QLabel#dialogSubtitle {
    color: $ink;
    font-size: 11pt;
    font-weight: 500;
}
QFrame#homeHero QFrame#dialogPanel[uiSurface="homeSectionCard"] {
    background-color: $video;
    border-radius: 10px;
}
QFrame#homeHero QLabel#nowTitle { color: #faf7ff; }
QFrame#homeHero QLabel#nowSubtitle { color: #ddd7ea; }
QFrame#dialogPanel[uiSurface="homeSectionCard"] {
    background: transparent;
    border: none;
    border-radius: 0;
}
QFrame#dialogPanel[uiSurface="homeSectionCard"] QLabel#dialogSectionLabel {
    color: $text;
    font-family: $display_font;
    font-size: 14pt;
    font-weight: 800;
    letter-spacing: 0;
}
QLabel#homeHealthSummary {
    color: $muted;
    font-size: 9.5pt;
}
QLabel#homeHealthSummary[uiVariant="success"] { color: $success; }
QLabel#homeHealthSummary[uiVariant="danger"] { color: $danger; }
QPushButton#homeQuickButton, QPushButton#homeQuickButtonAlt {
    border-radius: 10px;
    font-weight: 700;
    padding: 11px 22px;
}
QPushButton#homeQuickButton {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
}
QPushButton#homeQuickButton:hover {
    background-color: $accent_hover;
}
QPushButton#homeQuickButton[uiVariant="tv"] {
    background-color: $block_tv;
    color: $ink;
    border: 1px solid $block_tv;
}
QPushButton#homeQuickButtonAlt {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid $border;
}
QPushButton#homeQuickButtonAlt:hover {
    background-color: $bg_hover;
}
QPushButton#homeQuickButtonAlt[uiVariant="radio"] {
    background-color: $block_radio;
    color: $ink;
    border: 1px solid $block_radio;
}

/* ---------- Carruseles ----------
   El fondo, borde y foco de cada tarjeta los pone
   ui.carousel._card_stylesheet() por instancia, derivados del nombre del
   canal. Aquí solo queda lo común: QLabel hijos transparentes. */
QFrame#carouselCard QLabel { background: transparent; }
QLabel#carouselLogo { background-color: $video; border-radius: 10px; }
QLabel#carouselName { color: $text; font-size: 9.5pt; font-weight: 700; }
QLabel#carouselMeta { color: $text2; font-size: 8pt; }
QLabel#carouselEmpty { color: $dim; font-size: 9pt; padding: 8px; }

/* ---------- Paneles laterales ---------- */
QWidget#librarySidebar[uiSurface="sidebar"], QWidget#groupsSidebar[uiSurface="sidebar"] {
    background-color: $bg_panel;
    border-right: 1px solid $border;
}
QWidget#librarySidebar QLabel#libraryHeading {
    color: $text;
    font-family: $display_font;
    font-size: 12pt;
    font-weight: 800;
}
QWidget#librarySidebar QLabel#libSectionTitle {
    color: $muted;
    font-size: 9pt;
    font-weight: 700;
}
QListWidget#libraryRecentList, QListWidget#libraryPlaylistsList, QListWidget#groupsSidebarList {
    background: transparent;
    border: none;
    color: $text;
    font-size: 10pt;
}
QListWidget#libraryRecentList::item, QListWidget#libraryPlaylistsList::item,
QListWidget#groupsSidebarList::item {
    padding: 8px 10px;
    border-radius: 9px;
    margin: 2px 0;
}
QListWidget#libraryRecentList::item:hover, QListWidget#libraryPlaylistsList::item:hover,
QListWidget#groupsSidebarList::item:hover {
    background-color: $bg_hover;
}
QListWidget#libraryRecentList::item:selected, QListWidget#libraryPlaylistsList::item:selected,
QListWidget#groupsSidebarList::item:selected {
    background-color: $accent;
    color: $on_accent;
}
QWidget#equalizerWidget {
    background-color: $bg_root;
    border-radius: 14px;
}

/* ---------- Paneles de medios (Descargas, Podcasts, Soulseek...) ---------- */
QWidget#downloadPanel, QWidget[uiSurface="mediaPanel"] { background: transparent; }
QTabWidget#mediaTabs::pane {
    background-color: $bg_panel;
    border: 1px solid $border;
    border-radius: 14px;
    top: -1px;
    padding: 8px;
}
QTabWidget#mediaTabs QTabBar::tab {
    background: transparent;
    color: $muted;
    border: none;
    border-radius: 8px;
    margin: 0 2px 6px 2px;
    padding: 9px 13px;
    font-weight: 650;
}
QTabWidget#mediaTabs QTabBar::tab:hover {
    background-color: $bg_hover;
    color: $text;
}
QTabWidget#mediaTabs QTabBar::tab:selected {
    background-color: $download;
    color: $ink;
    font-weight: 700;
}
QProgressBar#mediaProgress {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    font-size: 8pt;
    font-weight: 650;
}
QProgressBar#mediaProgress::chunk {
    background-color: $accent;
    border-radius: 7px;
}
QLabel#mediaStatus { color: $muted; font-size: 9pt; border: none; }
QLabel#mediaStatus[uiState="loading"] { color: $tv; }
QLabel#mediaStatus[uiState="empty"] { color: $dim; }
QLabel#mediaStatus[uiState="error"] { color: $danger; border: none; }
QFrame#mediaSeparator { color: $border; }
QToolButton#mediaToolbarButton { min-width: 34px; min-height: 34px; font-size: 13pt; }
QToolButton#mediaToolbarButton[uiVariant="primary"] {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
}
QToolButton#mediaToolbarButton[uiVariant="info"] {
    color: $tv;
    border-color: $tv;
}
QLabel#mediaMeta { color: $dim; font-size: 8.5pt; }
QLabel#mediaPath { color: $tv; font-size: 8.5pt; }
QLabel#mediaSection { color: $muted; font-weight: 700; font-size: 9pt; }
QLabel#mediaRowIcon { font-size: 15pt; }
QLabel#mediaRowTitle { color: $text; font-weight: 650; font-size: 9.5pt; }
QLabel#mediaRowMeta { color: $text2; font-size: 8pt; }
QLabel#mediaRowDetail { color: $dim; font-size: 8pt; }

/* ---------- Diálogos ---------- */
QDialog {
    background-color: $bg_root;
}
QDialog QLabel, QDialog QCheckBox, QDialog QRadioButton, QDialog QGroupBox,
QDialog QComboBox, QMessageBox QLabel {
    font-weight: 500;
}
QDialog[uiSurface="dialog"] {
    background-color: $bg_root;
    color: $text;
}
QFrame#dialogPanel {
    background-color: $bg_card;
    border: 1px solid $border;
    border-radius: 14px;
}
QLabel#dialogTitle, QDialog QLabel#dialogTitle {
    color: $text;
    font-size: 18pt;
    font-weight: 800;
}
QLabel#dialogSubtitle, QDialog QLabel#dialogSubtitle {
    color: $text2;
    font-size: 9.5pt;
}
QLabel#dialogSectionLabel {
    color: $accent_text;
    font-weight: 800;
    font-size: 8.5pt;
    letter-spacing: 1px;
}
QDialog QLineEdit, QDialog QPlainTextEdit, QDialog QTextEdit {
    background-color: $bg_panel;
    color: $text;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QDialog QLineEdit:focus, QDialog QPlainTextEdit:focus, QDialog QTextEdit:focus {
    border-color: $accent;
    background-color: $bg_card;
}
QDialog QComboBox, QDialog QSpinBox, QDialog QDateTimeEdit {
    background-color: $bg_panel;
    color: $text;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 7px 10px;
}
QDialog QListWidget, QDialog QTableWidget {
    background-color: $bg_panel;
    alternate-background-color: $bg_card;
    color: $text;
    border: 1px solid $border;
    border-radius: 12px;
    outline: none;
}
QDialog QListWidget::item, QDialog QTableWidget::item {
    padding: 7px;
    border-radius: 6px;
}
QDialog QListWidget::item:selected, QDialog QTableWidget::item:selected {
    background-color: $accent;
    color: $on_accent;
}
QDialog QCheckBox, QDialog QRadioButton {
    color: $text2;
    spacing: 8px;
}
QDialog QGroupBox {
    color: $accent_text;
    border: 1px solid $border;
    border-radius: 12px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 750;
}
QDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

/* ---------- Paleta de comandos y avisos ---------- */
QWidget[uiSurface="floating"] {
    background-color: $bg_panel;
    border: 1px solid $border_strong;
    border-radius: 14px;
}
QDialog#commandPalette[uiSurface="floating"] { padding: 2px; }
QLineEdit#commandSearch {
    background-color: $bg_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 9px 11px;
    font-size: 11pt;
}
QListWidget#commandResults { background: transparent; border: none; color: $text; }
QListWidget#commandResults::item { padding: 8px 9px; border-radius: 8px; }
QListWidget#commandResults::item:selected { background-color: $accent; color: $on_accent; }
QFrame#toastNotice QLabel#toastMessage { color: $text; background: transparent; }
QPushButton#toastAction { background: transparent; color: $accent_text; border: none; font-weight: 700; }

/* ---------- Activación ---------- */
QLabel#splashStatus { color: $muted; font-size: 8.5pt; border: none; }
QLabel#splashStatus[uiState="active"] { color: $success; }
QLabel#splashStatus[uiState="error"] { color: $danger; border: none; }
QDialog QLabel#titulo { color: $text; font-size: 20pt; }
QDialog QLabel#version { color: $dim; font-size: 8.5pt; }
QDialog QLabel#aviso, QDialog QLabel#hw_label { color: $text2; font-size: 10pt; }
QDialog QLabel#hw_id {
    color: $accent_text;
    font-family: 'Consolas';
    font-size: 13pt;
    font-weight: 650;
    letter-spacing: 2px;
}
QDialog QLabel#funciones_free { color: $muted; font-size: 8.5pt; }
QDialog QLineEdit#codigo_input {
    background-color: $bg_panel;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 8px 14px;
    color: $text;
    font-family: 'Consolas';
}
QDialog QPushButton#btn_activar {
    background-color: $accent;
    color: $on_accent;
    border-radius: 10px;
    font-weight: 700;
}
QDialog QPushButton#btn_continuar {
    background-color: $bg_alt;
    color: $text2;
    border: 1px solid $border;
    border-radius: 10px;
}
"""
