"""Construcción de la portada (Inicio) de MainWindow. Extraído de
ui/main_window.py: el comportamiento de estos widgets ya vive en
ui.home_controller.HomeController (win.home); aquí solo se ensamblan.
"""
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui.carousel import Carousel
from ui.visual import set_variant


def build_home_page(win) -> QScrollArea:
    """
    Portada: hero con la reproducción actual (o la última emisión, o un
    genérico si no hay historial) + filas de carrusel con lo más
    relevante -- Continuar viendo/escuchando, Ahora en antena, Recomendado
    para ti y Favoritos -- sin duplicar las pestañas TV/Radio de la barra
    de navegación superior (ui.nav_top), que ya cubren "ver todos los
    canales/emisoras" (spec v8 §6.1). No usa win._make_list() en absoluto
    -- las 4 filas son ui.carousel.Carousel, la misma tarjeta
    reutilizable/testeada que ya usaban 3 de las 4 antes de esta fase.
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
    # Guardados para que HomeController.update_home_compact() pueda
    # encoger el hero (menos padding, tipografía más pequeña) al acercarse
    # al mínimo de la ventana, en vez de ocultarlo u obligar a un layout
    # vertical (spec v8 §5.4).
    win._home_hero_layout = hero_layout

    greeting = QLabel("Tu televisión y radio")
    greeting.setObjectName("homeGreeting")
    greeting.setWordWrap(True)
    greeting.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    win.home_greeting = greeting
    hero_layout.addWidget(greeting)

    subtitle = QLabel("Retoma lo que estabas escuchando o busca algo nuevo.")
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
    layout.addWidget(hero)

    # ---- Estado de las emisiones (se construye aquí, se añade al final,
    # debajo de las 4 filas de carrusel -- panel secundario, no una fila) ----
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
    health_btn.clicked.connect(win.dialogs.open_stream_diagnostics)
    health_layout.addWidget(health_btn)

    # ---- Continuar viendo/escuchando (antes "Recientes") ----
    panel_recientes = QFrame()
    panel_recientes.setObjectName("dialogPanel")
    panel_recientes.setProperty("uiSurface", "homeSectionCard")
    pr_layout = QVBoxLayout(panel_recientes)
    pr_layout.setContentsMargins(16, 14, 16, 14)
    pr_layout.setSpacing(8)
    lbl_recientes = QLabel("CONTINUAR VIENDO/ESCUCHANDO")
    lbl_recientes.setObjectName("dialogSectionLabel")
    pr_layout.addWidget(lbl_recientes)
    win.home_recent_carousel = Carousel(
        on_activate=win.home.activate_home_entry,
        logo_loader=win.logo_loader,
        empty_text="Todavía no has visto ni escuchado nada.",
    )
    pr_layout.addWidget(win.home_recent_carousel)
    layout.addWidget(panel_recientes)

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
    layout.addWidget(panel_antena)

    # ---- Recomendado para ti ----
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
    layout.addWidget(panel_recomendado)

    # ---- Favoritos (antes lista, ahora carrusel -- spec v8 §4.6/§6.1) ----
    panel_favs = QFrame()
    panel_favs.setObjectName("dialogPanel")
    panel_favs.setProperty("uiSurface", "homeSectionCard")
    pf_layout = QVBoxLayout(panel_favs)
    pf_layout.setContentsMargins(16, 14, 16, 14)
    pf_layout.setSpacing(8)
    lbl_favs = QLabel("TUS FAVORITOS")
    lbl_favs.setObjectName("dialogSectionLabel")
    pf_layout.addWidget(lbl_favs)
    win.home_fav_carousel = Carousel(
        on_activate=win.home.activate_home_entry,
        logo_loader=win.logo_loader,
        empty_text="Todavía no tienes ningún favorito marcado.",
    )
    pf_layout.addWidget(win.home_fav_carousel)
    layout.addWidget(panel_favs)

    layout.addWidget(health_panel)
    layout.addStretch(1)
    scroll.setWidget(content)
    win._home_viewport = scroll.viewport()
    return scroll
