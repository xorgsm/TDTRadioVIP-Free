# v8 — Fase 1: Barra de navegación superior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el raíl lateral fijo de navegación (`ui/nav_rail.py`, 180px, vertical) por una barra de navegación horizontal superior (`ui/nav_top.py`) con las mismas seis secciones y el mismo comportamiento de cambio de sección, como primer PR autocontenido del rediseño v8.

**Architecture:** `ui/nav_top.py` reemplaza a `ui/nav_rail.py` con la misma API pública (`build_nav_top(win)`, `toggle_library_sidebar`, `open_favorites_folder`, `on_groups_sidebar_changed`) pero con layout `QHBoxLayout` en vez de `QVBoxLayout`. `ui/main_window.py` mueve la barra de la columna izquierda del `QHBoxLayout` raíz (`cuerpo`) a una fila propia dentro del `QVBoxLayout` vertical (`raiz_v`), justo debajo de `title_bar` y encima de `cuerpo`. `ui/window_chrome.py` actualiza sus referencias a `win.nav_rail` → `win.nav_top` en los cuatro sitios que ocultan/muestran la navegación durante pantalla completa y PiP. El contrato estático de atributos (`tests/test_main_window_widget_contract.py`) se actualiza en el mismo commit.

**Tech Stack:** Python 3.12, PySide6 (Qt Widgets), pytest + pytest-cov (sin pytest-qt; los tests de UI instancian `QApplication` directamente, patrón ya usado en `tests/test_ui_performance.py`).

**Spec:** `docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md` §4.1 (navegación en barra superior) y §5.6 (sustitución directa dentro de `ui/`, sin flags ni árbol paralelo).

## Global Constraints

- Identidad de marca y sistema de tokens de `DESIGN.md` sin cambios (colores, tipografía Inter, iconografía QPainter existente en `ui/icons.py`) — este plan solo reestructura composición, no introduce color/tipografía nuevos.
- Tamaño mínimo operativo de ventana: 860×580px (`DESIGN.md` §Layout) — no debe romperse por este cambio; el umbral de colapso a solo-iconos de la barra superior es de una fase posterior (spec §5.4), no de esta.
- "Ahora suena" (`ui/now_playing_bar_builder.py`) no se toca en este plan — spec §4.2 y §5.4 la dejan sin cambios.
- `ui/app_menu.py` (QMenuBar) no se toca en este plan — su retirada es la Fase 3 (spec §5.2). En esta fase sigue viviendo dentro de `title_bar.py` tal cual, aunque su alineación con el contenido (que dependía de `NAV_RAIL_WIDTH`) deja de tener sentido una vez el contenido ya no arranca a 180px — se corrige en el mismo commit (Task 2) por ser un efecto directo de este cambio, no un rediseño aparte.
- Cualquier atributo de `MainWindow` añadido, renombrado o quitado debe reflejarse en `FROZEN_EXPECTED_ATTRS` de `tests/test_main_window_widget_contract.py` en el mismo commit — el propio test así lo exige.
- Comando de test del repo (documentado en `README.md`): `python -m pytest -q` desde la raíz del proyecto (no se ha encontrado `pytest.ini`/`pyproject.toml` con configuración adicional ni `conftest.py`; los fixtures de `QApplication` son locales a cada archivo de test, patrón que este plan reutiliza). Entradas de la app: `python main.py` (VIP) y `python main_free.py` (Free).

---

### Task 1: Crear `ui/nav_top.py` (barra horizontal) con test dedicado

**Files:**
- Create: `ui/nav_top.py`
- Create: `tests/test_nav_top.py`
- Modify: `ui/nav_sections.py` (sustituir `NAV_RAIL_WIDTH` por `NAV_TOP_HEIGHT`)

**Interfaces:**
- Produces: `ui.nav_top.build_nav_top(win) -> QWidget` (widget con `layout()` de tipo `QHBoxLayout`, altura fija `NAV_TOP_HEIGHT`, `objectName() == "navTopBar"`); `ui.nav_top.toggle_library_sidebar(win, visible: bool) -> None`; `ui.nav_top.open_favorites_folder(win, folder) -> None`; `ui.nav_top.on_groups_sidebar_changed(win, groups) -> None`. Efectos secundarios sobre `win`: asigna `win.nav_group` (`QButtonGroup`, un botón checkable por `NAV_HOME/NAV_TV/NAV_RADIO/NAV_FAV/NAV_HIST` y, si `not win.es_version_free`, también `NAV_DOWNLOAD`) y `win.library_toggle_btn` (`QToolButton` checkable).
- Consumes (de código ya existente, sin cambios): `ui.nav_sections.NAV_HOME/NAV_TV/NAV_RADIO/NAV_FAV/NAV_HIST/NAV_DOWNLOAD/SECTION_COLORS/SECTION_VARIANTS`, `ui.icons` (`icon_home`, `icon_tv`, `icon_radio`, `icon_favorite`, `icon_history`, `icon_download`, `icon_library`), `ui.palette.TEXT_MUTED/ACCENT`, `ui.visual.set_variant`, `win.navigation.on_nav_changed` (callback ya existente, sin cambios de firma), `win.activated`, `win.es_version_free`.

- [ ] **Step 1: Sustituir `NAV_RAIL_WIDTH` por `NAV_TOP_HEIGHT` en `ui/nav_sections.py`**

En `ui/nav_sections.py`, reemplazar el bloque (líneas 10-15):

```python
# Ancho del riel lateral (ver _build_nav_rail). Se comparte con
# _build_title_bar para que el menu (Archivo/Configuracion/Ayuda) arranque
# alineado con el panel de contenido -- antes quedaba pegado al nombre de
# la app y no coincidia con el borde de "Inicio" ni con el resto de la
# ventana.
NAV_RAIL_WIDTH = 180
```

por:

```python
# Alto de la barra de navegación superior (ver ui.nav_top.build_nav_top).
# Mismo orden de magnitud que el icono de sección (24px) más el padding
# vertical del ritmo espacial documentado en DESIGN.md (8-18px).
NAV_TOP_HEIGHT = 56
```

También actualizar el docstring del módulo (líneas 1-4): cambiar
`"ui/nav_rail.py, ui/catalog_toolbar.py, controladores"` por
`"ui/nav_top.py, ui/catalog_toolbar.py, controladores"`.

- [ ] **Step 2: Escribir el test (falla porque `ui/nav_top.py` no existe)**

Crear `tests/test_nav_top.py`:

```python
"""Contrato de ui.nav_top.build_nav_top: mismo comportamiento de navegación
que el riel lateral que sustituye, pero como barra horizontal."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QHBoxLayout

from ui.nav_sections import NAV_DOWNLOAD, NAV_FAV, NAV_HOME, NAV_TOP_HEIGHT
from ui.nav_top import build_nav_top, toggle_library_sidebar


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win(*, es_version_free=False, activated=True):
    win = SimpleNamespace(
        es_version_free=es_version_free,
        activated=activated,
        navigation=SimpleNamespace(on_nav_changed=Mock()),
        settings={"accent_color": "#c9a227"},
    )
    return win


def test_nav_top_is_horizontal_with_fixed_height(app):
    win = _make_win()
    bar = build_nav_top(win)
    assert isinstance(bar.layout(), QHBoxLayout)
    assert bar.objectName() == "navTopBar"
    assert bar.height() == NAV_TOP_HEIGHT


def test_nav_top_builds_six_sections_for_activated_vip(app):
    win = _make_win(es_version_free=False, activated=True)
    build_nav_top(win)
    assert len(win.nav_group.buttons()) == 6
    assert win.nav_group.button(NAV_DOWNLOAD).isVisible()


def test_nav_top_hides_downloads_for_unactivated_vip(app):
    win = _make_win(es_version_free=False, activated=False)
    build_nav_top(win)
    assert not win.nav_group.button(NAV_DOWNLOAD).isVisible()


def test_nav_top_omits_downloads_entirely_for_free_edition(app):
    win = _make_win(es_version_free=True, activated=False)
    build_nav_top(win)
    assert win.nav_group.button(NAV_DOWNLOAD) is None
    assert len(win.nav_group.buttons()) == 5


def test_nav_top_home_button_starts_checked(app):
    win = _make_win()
    build_nav_top(win)
    assert win.nav_group.button(NAV_HOME).isChecked()


def test_nav_top_clicking_a_button_notifies_navigation_controller(app):
    win = _make_win()
    build_nav_top(win)
    win.nav_group.button(NAV_FAV).click()
    win.navigation.on_nav_changed.assert_called_once_with(NAV_FAV)


def test_toggle_library_sidebar_updates_visibility(app):
    win = _make_win()
    win.library_sidebar = Mock()
    build_nav_top(win)
    toggle_library_sidebar(win, True)
    win.library_sidebar.setVisible.assert_called_once_with(True)
```

- [ ] **Step 3: Ejecutar los tests y confirmar que fallan por import error**

Run: `pytest tests/test_nav_top.py -v`
Expected: `ModuleNotFoundError: No module named 'ui.nav_top'` (o `ImportError`) en la fase de colección — ningún test llega a ejecutarse todavía.

- [ ] **Step 4: Implementar `ui/nav_top.py`**

Crear `ui/nav_top.py` — puerto de `ui/nav_rail.py` a layout horizontal, sin la
etiqueta "EXPLORAR" (no encaja en una barra horizontal de pestañas estilo
Netflix/Plex, spec §4.1 no la contempla) y sin ancho fijo (`NAV_TOP_HEIGHT`
fija el alto, no el ancho):

```python
"""Barra de navegación superior (Inicio/TV/Radio/Favoritos/Historial/
Descargas + toggle de biblioteca). Sustituye a ui/nav_rail.py (raíl lateral
fijo de 180px) como parte del rediseño v8 -- ver
docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md §4.1.
"""
from functools import partial

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QToolButton, QWidget

from ui import icons as app_icons
from ui import palette
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_TOP_HEIGHT,
    NAV_TV, SECTION_COLORS, SECTION_VARIANTS,
)
from ui.visual import set_variant


def build_nav_top(win) -> QWidget:
    bar = QWidget()
    bar.setObjectName("navTopBar")
    bar.setFixedHeight(NAV_TOP_HEIGHT)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(18, 6, 12, 6)
    layout.setSpacing(6)

    win.nav_group = QButtonGroup(win)
    win.nav_group.setExclusive(True)

    # Cada icono conserva el color de su sección como señal secundaria;
    # el estado activo usa una superficie común para no convertir toda
    # la navegación en un bloque de color distinto en cada pantalla.
    nav_icon_builders = {
        NAV_HOME: (app_icons.icon_home, SECTION_COLORS[NAV_HOME]),
        NAV_TV: (app_icons.icon_tv, SECTION_COLORS[NAV_TV]),
        NAV_RADIO: (app_icons.icon_radio, SECTION_COLORS[NAV_RADIO]),
        NAV_FAV: (app_icons.icon_favorite, SECTION_COLORS[NAV_FAV]),
        NAV_HIST: (app_icons.icon_history, SECTION_COLORS[NAV_HIST]),
        NAV_DOWNLOAD: (app_icons.icon_download, SECTION_COLORS[NAV_DOWNLOAD]),
    }
    nav_defs = [
        (NAV_HOME, "Inicio"),
        (NAV_TV, "Televisión"),
        (NAV_RADIO, "Radio"),
        (NAV_FAV, "Favoritos"),
        (NAV_HIST, "Historial"),
    ]
    # Nunca se construye en la versión free -- no hay import de
    # ui.download_panel que lo respalde (ver comentario junto a
    # self.download_panel en main_window.py), así que ni siquiera puede
    # activarse en tiempo de ejecución como en la edición con licencia.
    if not win.es_version_free:
        nav_defs.append((NAV_DOWNLOAD, "Descargas"))
    for nav_id, tooltip in nav_defs:
        btn = QToolButton()
        btn.setObjectName("navButton")
        set_variant(btn, SECTION_VARIANTS[nav_id])
        btn.setToolTip(tooltip)
        btn.setText(tooltip)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        builder, inactive_color = nav_icon_builders[nav_id]
        btn.setIconSize(QSize(22, 22))
        btn.setIcon(builder(inactive_color, size=24))
        btn.toggled.connect(
            lambda _checked, b=btn, f=builder, c=inactive_color: b.setIcon(
                f(c, size=24)
            )
        )
        win.nav_group.addButton(btn, nav_id)
        layout.addWidget(btn)
        # El botón de descargas solo aparece con licencia activada de
        # verdad. En la versión free ni siquiera se construye (ver
        # nav_defs más arriba), así que este condicional solo puede
        # afectar a la edición con licencia sin activar todavía.
        if nav_id == NAV_DOWNLOAD and not win.activated:
            btn.setVisible(False)

    win.nav_group.button(NAV_HOME).setChecked(True)
    win.nav_group.idClicked.connect(win.navigation.on_nav_changed)

    layout.addStretch(1)

    win.library_toggle_btn = QToolButton()
    win.library_toggle_btn.setObjectName("navButton")
    win.library_toggle_btn.setToolTip("Mostrar/ocultar biblioteca")
    win.library_toggle_btn.setText("Biblioteca")
    win.library_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    win.library_toggle_btn.setCheckable(True)
    win.library_toggle_btn.setChecked(False)
    win.library_toggle_btn.setCursor(Qt.PointingHandCursor)
    win.library_toggle_btn.setIconSize(QSize(26, 26))
    win.library_toggle_btn.setIcon(app_icons.icon_library(palette.TEXT_MUTED))
    win.library_toggle_btn.toggled.connect(partial(toggle_library_sidebar, win))
    layout.addWidget(win.library_toggle_btn)

    return bar


def toggle_library_sidebar(win, visible: bool) -> None:
    win.library_sidebar.setVisible(visible)
    win.library_toggle_btn.setIcon(
        app_icons.icon_library(palette.ACCENT if visible else palette.TEXT_MUTED)
    )


def open_favorites_folder(win, folder) -> None:
    """
    Salta a la pestaña de Favoritos y, si se indica una carpeta, la deja
    seleccionada en el filtro -- llamado desde el panel de biblioteca al
    pinchar una "playlist". folder=None significa "todos los favoritos,
    sin filtrar por carpeta".
    """
    win.nav_group.button(NAV_FAV).click()
    if folder:
        idx = win.group_filter.findText(folder)
        if idx >= 0:
            win.group_filter.setCurrentIndex(idx)
    else:
        win.group_filter.setCurrentIndex(0)


def on_groups_sidebar_changed(win, groups) -> None:
    """
    Callback de GroupsSidebar cuando cambia la selección de grupos.
    `groups` es un set de nombres de grupo, o None si no hay filtro
    (se eligió "(Todos)" o se deseleccionó todo).
    """
    win._tv_sidebar_groups = groups
    win.lists.filter_current_list()
```

- [ ] **Step 5: Ejecutar los tests y confirmar que pasan**

Run: `pytest tests/test_nav_top.py -v`
Expected: 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/nav_top.py tests/test_nav_top.py ui/nav_sections.py
git commit -m "feat: añadir ui/nav_top.py, barra de navegación horizontal para v8"
```

---

### Task 2: Sustituir el raíl por la barra superior en `MainWindow` y retirar `ui/nav_rail.py`

**Files:**
- Modify: `ui/main_window.py:29-36` (imports), `ui/main_window.py:71-73` (comentario de mapa de responsabilidades), `ui/main_window.py:299-315` (`_build_ui`)
- Modify: `ui/window_chrome.py:172,203,280,336` (`win.nav_rail` → `win.nav_top`)
- Modify: `ui/title_bar.py` (quitar la dependencia de `NAV_RAIL_WIDTH` para el ancho de `marca_col`)
- Modify: `ui/library_sidebar.py:11` (comentario)
- Modify: `tests/test_main_window_widget_contract.py:65` (`"nav_rail"` → `"nav_top"` en `FROZEN_EXPECTED_ATTRS`)
- Delete: `ui/nav_rail.py`

**Interfaces:**
- Consumes: `ui.nav_top.build_nav_top`, `ui.nav_top.on_groups_sidebar_changed`, `ui.nav_top.open_favorites_folder` (Task 1).
- Produces: `win.nav_top` (sustituye a `win.nav_rail` en el contrato de atributos de `MainWindow`).

- [ ] **Step 1: Actualizar imports en `ui/main_window.py`**

Reemplazar (línea 31):

```python
from ui.nav_rail import build_nav_rail, on_groups_sidebar_changed, open_favorites_folder
```

por:

```python
from ui.nav_top import build_nav_top, on_groups_sidebar_changed, open_favorites_folder
```

- [ ] **Step 2: Actualizar el comentario de mapa de responsabilidades**

Reemplazar (líneas 71-73):

```python
# ui.nav_rail (funciones de módulo):
#     _build_nav_rail, _toggle_library_sidebar, _open_favorites_folder,
#     _on_groups_sidebar_changed
```

por:

```python
# ui.nav_top (funciones de módulo):
#     _build_nav_rail (ahora _build_nav_top), _toggle_library_sidebar,
#     _open_favorites_folder, _on_groups_sidebar_changed
```

- [ ] **Step 3: Mover la barra de navegación de `cuerpo` (horizontal) a `raiz_v` (vertical)**

En `_build_ui` (`ui/main_window.py`), reemplazar:

```python
        self.title_bar = build_title_bar(self)
        raiz_v.addWidget(self.title_bar)

        cuerpo = QWidget()
        root = QHBoxLayout(cuerpo)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_rail = build_nav_rail(self)
        root.addWidget(self.nav_rail)
```

por:

```python
        self.title_bar = build_title_bar(self)
        raiz_v.addWidget(self.title_bar)

        # La barra de navegación vive como fila propia del layout vertical
        # (no como columna del QHBoxLayout de más abajo): en el modelo v8
        # las secciones son pestañas horizontales, no un raíl lateral que
        # comparte fila con el contenido. Ver spec v8 §4.1.
        self.nav_top = build_nav_top(self)
        raiz_v.addWidget(self.nav_top)

        cuerpo = QWidget()
        root = QHBoxLayout(cuerpo)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
```

(el resto de `_build_ui`, desde `self.library_sidebar = LibrarySidebar(...)` en adelante, no cambia — `root.addWidget(self.library_sidebar)` sigue siendo la primera línea que añade algo a `root`)

Más abajo en el mismo método (línea 395 antes de este cambio), la línea

```python
        raiz_v.addWidget(cuerpo, stretch=1)
```

no cambia — solo se ha insertado `self.nav_top` entre `self.title_bar` y
`cuerpo` más arriba en el método; el resto de `_build_ui` (incluida esta
línea) queda igual.

- [ ] **Step 4: Actualizar `ui/window_chrome.py` (4 sitios)**

Reemplazar cada aparición de `win.nav_rail.setVisible(...)` por
`win.nav_top.setVisible(...)`, manteniendo el valor booleano de cada línea
sin cambios:

- Línea 172: `win.nav_rail.setVisible(False)` → `win.nav_top.setVisible(False)` (dentro de `enter_player_fullscreen`)
- Línea 203: `win.nav_rail.setVisible(True)` → `win.nav_top.setVisible(True)` (dentro de `exit_player_fullscreen`)
- Línea 280: `win.nav_rail.setVisible(False)` → `win.nav_top.setVisible(False)` (dentro de `enter_pip_mode`)
- Línea 336: `win.nav_rail.setVisible(True)` → `win.nav_top.setVisible(True)` (dentro de `exit_pip_mode`)

`win.menu_bar.setVisible(...)` (líneas 298 y 341) no se toca — `ui/app_menu.py` sigue vivo hasta la Fase 3.

- [ ] **Step 5: Quitar la dependencia de `NAV_RAIL_WIDTH` en `ui/title_bar.py`**

La justificación original de `marca_col.setFixedWidth(NAV_RAIL_WIDTH - ...)`
era alinear el menú con el borde izquierdo del contenido, que antes
arrancaba tras el raíl de 180px. Con la navegación ahora en una fila propia
a ancho completo, esa alineación ya no aplica. Reemplazar:

```python
from ui.nav_sections import NAV_RAIL_WIDTH
```

por: (eliminar la línea — ya no se usa nada de `ui.nav_sections` en este archivo)

Y reemplazar:

```python
    # La marca vive en una columna de ancho fijo, igual que el riel
    # lateral de debajo (NAV_RAIL_WIDTH): asi el menu que viene a
    # continuacion arranca siempre en el mismo punto que el panel de
    # contenido (donde esta "Inicio"), sin depender de cuanto mida el
    # texto de la marca.
    marca_col = QWidget()
    marca_col.setFixedWidth(NAV_RAIL_WIDTH - fila.contentsMargins().left())
```

por:

```python
    # Columna de ancho natural (antes se fijaba a NAV_RAIL_WIDTH para
    # alinear el menú con el contenido bajo el raíl lateral; ese raíl ya
    # no existe -- ver ui.nav_top -- así que la marca simplemente ocupa
    # el espacio que necesita su texto).
    marca_col = QWidget()
```

- [ ] **Step 6: Actualizar el comentario de `ui/library_sidebar.py:11`**

Reemplazar:

```
Panel aditivo: se inserta entre el riel de navegación (nav_rail) y el
```

por:

```
Panel aditivo: se inserta entre la barra de navegación superior (nav_top) y el
```

- [ ] **Step 7: Actualizar el contrato congelado de atributos**

En `tests/test_main_window_widget_contract.py`, línea 65, dentro de
`FROZEN_EXPECTED_ATTRS`, reemplazar `"nav_rail"` por `"nav_top"` (mantener
el resto del set y el orden alfabético del bloque):

```python
    "menu_bar", "more_btn", "mute_btn", "nav_group", "nav_top", "navigation", "now_controls_separator",
```

- [ ] **Step 8: Borrar `ui/nav_rail.py`**

```bash
git rm "ui/nav_rail.py"
```

- [ ] **Step 9: Ejecutar toda la suite de tests**

Run: `python -m pytest -q`
Expected: todos los tests PASS, incluidos
`test_every_attribute_read_from_win_is_assigned_somewhere_in_ui` y
`test_win_attribute_contract_matches_frozen_snapshot` (confirman que ningún
módulo de `ui/` quedó leyendo `win.nav_rail` y que el snapshot coincide con
la lectura real tras el rename) y los 7 tests nuevos de
`tests/test_nav_top.py` del Task 1.

- [ ] **Step 10: Arrancar la app y verificar visualmente**

Run: `python main.py`
Expected: la barra de navegación aparece como fila horizontal bajo la barra
de título (no como columna lateral), con las mismas seis pestañas de antes,
el botón de Inicio activo al arrancar, cambio de sección funcional al
pinchar cada pestaña, y el botón de biblioteca al extremo derecho
alternando el panel lateral igual que antes. Probar también F11 (pantalla
completa) y el botón de PiP para confirmar que `nav_top` se oculta/muestra
igual que antes lo hacía `nav_rail`.

Run: `python main_free.py`
Expected: la pestaña Descargas no existe en absoluto en la barra (edición
Free — 5 pestañas, sin "Descargas"), igual que se comprobaba antes con
`nav_rail`.

- [ ] **Step 11: Commit**

```bash
git add ui/main_window.py ui/window_chrome.py ui/title_bar.py ui/library_sidebar.py tests/test_main_window_widget_contract.py
git commit -m "refactor: sustituir el riel lateral (nav_rail) por la barra de navegación superior (nav_top)"
```

---

## Fases siguientes (planes futuros, no cubiertos aquí)

Este plan cierra solo la Fase 1 (modelo de navegación). Las fases
siguientes de la spec de v8 necesitan su propio plan de implementación
(`superpowers:writing-plans`) cuando llegue el momento, porque cada una
toca subsistemas independientes con su propio ciclo de test:

- **Fase 2 — Home hero + filas + tarjetas póster** (spec §4.3, §4.4):
  `ui/home_hero.py` y `ui/poster_card.py` nuevos, sustituyen a
  `ui/home_page_builder.py`; incluye mover Favoritos/Historial a filas de
  carrusel (§4.6) y el fondo degradado determinista de las tarjetas.
- **Fase 3 — "Más ▾" y retirada de la barra de menú clásica** (spec §5.1,
  §5.2): nuevo módulo para el dropdown por categorías, migración de las
  ~20 acciones de `ui/app_menu.py` (que se borra), Podcasts pasa a pestaña
  de primer nivel (§4.5) saliendo de `ui/download_panel.py`.
- **Fase 4 — Responsive** (spec §5.4): umbral de colapso a solo-iconos de
  `nav_top` (medido empíricamente sobre el `nav_top.py` de este plan) y
  encogido en altura del hero de la Fase 2.
- **Fase 5 — Pulido VIP/Free** (spec §5.5): revisión final de que
  `nav_top`/"Más ▾" reflejan los mismos condicionales de
  `activated`/`es_version_free` ya verificados aquí para `NAV_DOWNLOAD`
  (este plan ya cubre la pestaña Descargas; falta Cast/DLNA y
  "Activar VIP…" cuando "Más ▾" exista en la Fase 3).
