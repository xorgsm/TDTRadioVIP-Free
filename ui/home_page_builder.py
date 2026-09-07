"""Construcción de la portada (Inicio) de MainWindow. Extraído de
ui/main_window.py: el comportamiento de estos widgets ya vive en
ui.home_controller.HomeController (win.home); aquí solo se ensamblan.
"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui import icons as app_icons
from ui import palette
from ui.carousel import Carousel
from ui.nav_sections import NAV_RADIO, NAV_TV
from ui.visual import set_variant
from ui.widgets import ChannelDelegate


def build_home_page(win) -> QScrollArea:
    """
    Portada de bienvenida: accesos rápidos a TV/Radio, y un vistazo a lo
    último visto y a los favoritos, sin tener que entrar en cada sección.
    Reutiliza win._make_list() (misma tarjeta, mismo clic-para-reproducir,
    mismo menú contextual que el resto de la app) en vez de inventar un
    sistema de tarjetas nuevo sin poder probarlo antes de dártelo.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setObjectName("homeScroll")

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(2, 4, 20, 18)
    layout.setSpacing(18)
    win._home_layout = layout

    hero = QFrame()
    hero.setObjectName("homeHero")
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(22, 18, 22, 18)
    hero_layout.setSpacing(10)

    greeting = QLabel("Tu televisión y radio")
    greeting.setObjectName("homeGreeting")
    greeting.setWordWrap(True)
    greeting.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    hero_layout.addWidget(greeting)

    subtitle = QLabel("Elige TV, radio o retoma lo que estabas escuchando.")
    subtitle.setObjectName("dialogSubtitle")
    subtitle.setWordWrap(True)
    subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    hero_layout.addWidget(subtitle)

    win.home_now_card = QFrame()
    win.home_now_card.setObjectName("dialogPanel")
    win.home_now_card.setProperty("uiSurface", "homeSectionCard")
    now_layout = QBoxLayout(QBoxLayout.LeftToRight, win.home_now_card)
    now_layout.setContentsMargins(14, 10, 14, 10)
    now_layout.setSpacing(10)
    win._home_now_layout = now_layout
    now_text = QVBoxLayout()
    win.home_now_title = QLabel("Nada en reproducción")
    win.home_now_title.setObjectName("nowTitle")
    win.home_now_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    win.home_now_subtitle = QLabel("Busca cualquier canal o emisora con Ctrl+K")
    win.home_now_subtitle.setObjectName("nowSubtitle")
    win.home_now_subtitle.setWordWrap(True)
    win.home_now_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    now_text.addWidget(win.home_now_title)
    now_text.addWidget(win.home_now_subtitle)
    now_layout.addLayout(now_text, 1)
    win.home_resume_btn = QPushButton("Buscar")
    set_variant(win.home_resume_btn, "primary")
    win.home_resume_btn.clicked.connect(win.home.home_resume_or_search)
    now_layout.addWidget(win.home_resume_btn)
    win.home_float_btn = QPushButton("Ventana flotante")
    win.home_float_btn.clicked.connect(win.window_chrome.toggle_pip_mode)
    win.home_float_btn.setVisible(False)
    now_layout.addWidget(win.home_float_btn)
    hero_layout.addWidget(win.home_now_card)

    quick_row = QBoxLayout(QBoxLayout.LeftToRight)
    quick_row.setSpacing(10)
    win._home_quick_layout = quick_row

    tv_btn = QPushButton(" Ver TV en directo")
    tv_btn.setObjectName("homeQuickButton")
    set_variant(tv_btn, "tv")
    # Icono oscuro a juego con el "color" que ya usa
    # QPushButton#homeQuickButton[uiVariant="tv"] en ui/style.py para el
    # texto sobre el fondo palette.ACCENT_INFO -- un literal aparte aquí
    # se habría podido desincronizar si ese tono cambia más adelante.
    tv_btn.setIcon(app_icons.icon_tv(palette.BG_ROOT))
    tv_btn.setIconSize(QSize(20, 20))
    tv_btn.setCursor(Qt.PointingHandCursor)
    tv_btn.clicked.connect(lambda: win.nav_group.button(NAV_TV).click())
    quick_row.addWidget(tv_btn)

    radio_btn = QPushButton(" Escuchar Radio")
    radio_btn.setObjectName("homeQuickButtonAlt")
    set_variant(radio_btn, "radio")
    radio_btn.setIcon(app_icons.icon_radio(palette.TEXT_PRIMARY))
    radio_btn.setIconSize(QSize(20, 20))
    radio_btn.setCursor(Qt.PointingHandCursor)
    radio_btn.clicked.connect(lambda: win.nav_group.button(NAV_RADIO).click())
    quick_row.addWidget(radio_btn)
    quick_row.addStretch(1)
    hero_layout.addLayout(quick_row)
    layout.addWidget(hero)

    health_panel = QFrame()
    health_panel.setObjectName("dialogPanel")
    health_panel.setProperty("uiSurface", "homeSectionCard")
    health_layout = QBoxLayout(QBoxLayout.LeftToRight, health_panel)
    health_layout.setContentsMargins(16, 13, 16, 13)
    health_layout.setSpacing(12)
    win._home_health_layout = health_layout
    health_text = QVBoxLayout()
    health_text.setSpacing(3)
    health_heading = QLabel("ESTADO DE LAS EMISIONES")
    health_heading.setObjectName("dialogSectionLabel")
    health_text.addWidget(health_heading)
    win.home_health_summary = QLabel()
    win.home_health_summary.setObjectName("homeHealthSummary")
    win.home_health_summary.setWordWrap(True)
    win.home_health_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    health_text.addWidget(win.home_health_summary)
    health_layout.addLayout(health_text, 1)
    health_btn = QPushButton("Ver diagnóstico")
    set_variant(health_btn, "secondary")
    health_btn.clicked.connect(win._open_stream_diagnostics)
    health_layout.addWidget(health_btn)

    # ---- Ahora en antena (qué está echando cada canal, vía EPG) ----
    panel_antena = QFrame()
    panel_antena.setObjectName("dialogPanel")
    panel_antena.setProperty("uiSurface", "homeSectionCard")
    pa_layout = QVBoxLayout(panel_antena)
    pa_layout.setContentsMargins(16, 14, 16, 14)
    pa_layout.setSpacing(8)
    lbl_antena = QLabel("AHORA EN ANTENA")
    lbl_antena.setObjectName("dialogSectionLabel")
    pa_layout.addWidget(lbl_antena)
    win.home_on_air_carousel = Carousel(
        on_activate=win.home.activate_home_entry,
        logo_loader=win.logo_loader,
        empty_text="Configura una guía de programación (EPG) en Configuración para ver esto.",
    )
    pa_layout.addWidget(win.home_on_air_carousel)
    win.panel_antena = panel_antena

    # ---- Recientes (carrusel horizontal, estilo Spotify) ----
    panel_recientes = QFrame()
    panel_recientes.setObjectName("dialogPanel")
    panel_recientes.setProperty("uiSurface", "homeSectionCard")
    pr_layout = QVBoxLayout(panel_recientes)
    pr_layout.setContentsMargins(16, 14, 16, 14)
    pr_layout.setSpacing(8)
    lbl_recientes = QLabel("RECIENTES")
    lbl_recientes.setObjectName("dialogSectionLabel")
    pr_layout.addWidget(lbl_recientes)
    win.home_recent_carousel = Carousel(
        on_activate=win.home.activate_home_entry,
        logo_loader=win.logo_loader,
        empty_text="Todavía no has visto ni escuchado nada.",
    )
    pr_layout.addWidget(win.home_recent_carousel)
    layout.addWidget(panel_recientes)

    # ---- Recomendado para ti (carrusel horizontal) ----
    panel_recomendado = QFrame()
    panel_recomendado.setObjectName("dialogPanel")
    panel_recomendado.setProperty("uiSurface", "homeSectionCard")
    pv_layout = QVBoxLayout(panel_recomendado)
    pv_layout.setContentsMargins(16, 14, 16, 14)
    pv_layout.setSpacing(8)
    lbl_recomendado = QLabel("RECOMENDADO PARA TI")
    lbl_recomendado.setObjectName("dialogSectionLabel")
    pv_layout.addWidget(lbl_recomendado)
    win.home_recommended_carousel = Carousel(
        on_activate=win.home.activate_home_entry,
        logo_loader=win.logo_loader,
        empty_text="Actualiza los canales de TV para ver sugerencias aquí.",
    )
    pv_layout.addWidget(win.home_recommended_carousel)

    # ---- Favoritos ----
    panel_favs = QFrame()
    panel_favs.setObjectName("dialogPanel")
    panel_favs.setProperty("uiSurface", "homeSectionCard")
    pf_layout = QVBoxLayout(panel_favs)
    pf_layout.setContentsMargins(16, 14, 16, 14)
    pf_layout.setSpacing(8)
    lbl_favs = QLabel("TUS FAVORITOS")
    lbl_favs.setObjectName("dialogSectionLabel")
    pf_layout.addWidget(lbl_favs)
    win.home_fav_list = win._make_list()
    win.home_fav_list.setFixedHeight(5 * ChannelDelegate.ROW_HEIGHT + 12)
    win.home_fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    pf_layout.addWidget(win.home_fav_list)
    win.home_fav_empty = QLabel("Todavía no tienes ningún favorito marcado.")
    win.home_fav_empty.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 8pt;")
    pf_layout.addWidget(win.home_fav_empty)

    # "Recomendado para ti" y "Tus favoritos" van uno junto al otro
    # (2:1, como en la referencia de Stitch) en vez de apilados a lo
    # largo de toda la portada -- ambos son paneles cortos y quedaba
    # mucho hueco vacío a los lados si ocupaban el ancho completo.
    secondary_row = QBoxLayout(QBoxLayout.LeftToRight)
    secondary_row.setSpacing(16)
    win._home_secondary_layout = secondary_row
    secondary_row.addWidget(panel_recomendado, 2)
    secondary_row.addWidget(panel_favs, 1)
    layout.addLayout(secondary_row)

    layout.addWidget(panel_antena)
    layout.addWidget(health_panel)
    layout.addStretch(1)
    scroll.setWidget(content)
    win._home_viewport = scroll.viewport()
    return scroll
