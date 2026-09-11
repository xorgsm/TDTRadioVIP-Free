# Rediseño radical de interfaz — TDT & Radio VIP v8

**Estado:** Rediseño v8 **completo y fusionado a `master`** (2026-09-11).
Fase 1 (§4.1-4.2, nav_top) implementada y fusionada a `master` (2026-09-10).
Fase 2 (§6, Inicio hero+filas+tarjetas) implementada (2026-09-10, rama
`feature/v8-home-hero`). Fases 3-5 (§5.1-5.2, §5.4, §5.5) implementadas
(2026-09-11, misma rama) -- ver §8 para el cierre de cada una. La fusión de
`feature/v8-home-hero` a `master` se resolvió por fast-forward: `master`,
`feature/v8-home-hero` y `origin/master` apuntan los tres a `36eb956`
(`chore: bump APP_VERSION/MyAppVersion a 8.0.2`), por lo que no existe commit
de merge separado. Versión publicada: **8.0.2**.
**Fecha de inicio:** 2026-09-09 · **Fecha de aprobación (diseño inicial):** 2026-09-10
**Ruta de trabajo dedicada:** `TDTRadioVIP_v8.0/TDTRadioVIP/` — git worktree real
del repo (mismo historial/remotos), donde se ejecuta y prueba cada fase.
**Clasificación:** Arquitectónico (proceso completo de brainstorming: preguntas → enfoques → diseño por secciones → spec → plan de implementación).

## 1. Motivación

La interfaz actual (7.6.x) es funcionalmente sólida — la revisión de arquitectura y
de código reciente no encontró bugs críticos y el sistema de diseño documentado en
`DESIGN.md` ("La Cabina Nocturna") es coherente. El motivo del rediseño **no es
corregir un problema funcional**, sino que la interfaz se percibe anticuada frente
a aplicaciones modernas de streaming (Spotify, Netflix, Plex).

## 2. Alcance decidido

**Se conserva la identidad de marca** (decisión explícita del usuario, ver
`PRODUCT.md` § Brand Commitments):

- Nombre "TDT & Radio VIP", firma "Coder By X@R", icono de la app.
- Paleta marino + dorado configurable, tipografía Inter, iconografía QPainter
  (sin emojis ni fuentes de iconos).
- El documento `DESIGN.md` (colores, tipografía, spacing, shapes) sigue siendo la
  base de tokens; lo que cambia es la **composición y estructura** de las
  pantallas, no el lenguaje visual de bajo nivel.

**Se rehace radicalmente:**

- Modelo de navegación (de raíl lateral fijo a barra superior).
- Layout de la pantalla de Inicio (de lista/carrusel simple a hero + filas estilo
  Netflix/Plex).
- Forma y composición de las tarjetas de contenido en los carruseles.
- Organización de las secciones (qué es contenido de primer nivel vs. herramienta
  secundaria).

## 3. Referencia visual

**Netflix / Plex**: filas horizontales de carruseles grandes, hero destacado
arriba, navegación superior en vez de lateral. (Se descartaron como referencia
principal: Spotify puro y Apple TV/Music — el usuario prefirió explícitamente el
modelo Netflix/Plex).

## 4. Decisiones de diseño confirmadas

### 4.1 Navegación

Barra superior con las secciones principales de contenido como pestañas visibles,
y un menú **"Más ▾"** para el resto de herramientas. Sustituye al raíl lateral
fijo de 180px (`ui/nav_rail.py`, `NAV_RAIL_WIDTH`) del sistema actual.

### 4.2 Barra "Ahora suena"

Se mantiene como **barra inferior persistente**, siempre visible, estilo
Spotify — sin modo mini/expandido de dos estados. Esto conserva la regla actual
"The Essential Controls Survive Rule" de `DESIGN.md`: controles de reproducción,
parada, reintento, grabación y silencio nunca desaparecen.

### 4.3 Layout de Inicio — Opción A: "Hero + filas"

Confirmado por el usuario sobre 3 mockups comparados en el companion visual
(`.superpowers/brainstorm/127-1788960745/content/home-layout.html`, evento
`choice: hero-rows`):

- Banner grande arriba mostrando el canal/emisora destacada o en curso de
  reproducción (con degradado de superficie, sin foto de fondo real —
  ver §4.4 sobre datos disponibles).
- Filas de carruseles debajo, agrupadas por categoría (p. ej. "Continuar
  viendo", "Tus canales de TV", "Radio").
- Barra superior de navegación y barra de reproducción inferior persistente
  conviven con este layout (no compiten por espacio vertical porque el hero
  vive dentro del área de contenido scrolleable).

### 4.4 Estilo de tarjeta — Opción B: "Póster/miniatura" + resolución de datos

Confirmado sobre 3 mockups comparados
(`.superpowers/brainstorm/127-1788960745/content/card-style.html`, evento
`choice: poster-card`).

**Restricción de datos descubierta durante el diseño:** el modelo de canal
(`core/channels.py`) solo expone `logo` (el atributo `tvg-logo` del M3U). No
existe backdrop, captura de programa ni miniatura real en ningún punto del
código (TV, radio, podcasts ni EPG). Una tarjeta tipo póster con fotografía
real de fondo no es viable sin construir un pipeline nuevo de obtención de
imágenes, que además no tendría garantía de existir para canales M3U de
terceros o listas personalizadas del usuario.

**Resolución acordada:** cada tarjeta usa un **fondo degradado generado**
(derivado del color de acento o de un hash determinista del nombre del canal)
con el logo centrado encima, en vez de fotografía real. Esto conserva el
aspecto "cinematográfico" tipo póster sin depender de una fuente de imágenes
que no existe hoy y que no se puede garantizar para contenido de terceros.
Queda **fuera de alcance** de v8 cualquier pipeline de descarga/generación de
miniaturas reales — es una posible mejora futura, no parte de este rediseño.

### 4.5 Organización de secciones — Podcasts

Podcasts pasa a ser **sección de contenido de primer nivel** en la barra
superior, junto a TV y Radio. Hoy vive escondido como una pestaña dentro del
panel de Descargas (`ui/download_panel.py`, lista de pestañas que incluye
"Torrents", "Podcasts", "Soulseek", "Convertir", "Editor MP3", "Editar info").
Esto es consistente con que Podcasts es contenido reproducible, no una
herramienta de gestión de archivos.

### 4.6 Favoritos e Historial

Dejan de ser secciones propias en la barra superior. Pasan a mostrarse como
**filas de carrusel dentro de la pantalla de Inicio** (p. ej. "Favoritos",
"Continuar viendo/escuchando"), consistente con el modelo Netflix, que no
tiene una pestaña de "Historial" separada.

### 4.7 Descargas

**Se mantiene visible en la barra superior** (con Torrents y Soulseek como
pestañas internas, igual que hoy), aunque ya no incluya Podcasts. Se considera
una herramienta de uso frecuente que merece acceso directo, no solo un ítem
dentro de "Más ▾".

Barra superior de contenido de primer nivel resultante: **Inicio, TV, Radio,
Podcasts, Descargas**, más "Más ▾" para el resto de herramientas (contenido
cerrado en §5.1).

## 5. Decisiones adicionales (cerradas 2026-09-10)

Estos puntos quedaron abiertos tras la sesión inicial (2026-09-09) y se
resolvieron al retomar el diseño:

### 5.1 Contenido de "Más ▾"

Dropdown con categorías (no lista plana, no página dedicada a pantalla
completa). Agrupación final:

- **Gestión de contenido** — Añadir canal/emisora, Importar lista M3U
  (general/TV/radio), Exportar lista M3U (general/TV/radio), Editor M3U,
  Gestionar canales personalizados, Diagnosticar canales y emisoras,
  Actualizar canales TV, Actualizar emisoras de radio.
- **Grabaciones** — Biblioteca de grabaciones, Grabaciones recurrentes,
  Centro de grabaciones programadas, Multivista (mosaico).
- **Herramientas de audio** — Convertir, Editor MP3, Editar info (tags).
- **Guía EPG** — Guía EPG (entrada única, sin subgrupo).
- **Ajustes** — Preferencias, Ecualizador, Activar VIP… (solo si
  `not win.activated and not win.es_version_free`, igual que hoy).
- **Ayuda y sistema** — Acerca de, Estadísticas de uso, Buscar
  actualizaciones, Abrir carpeta de logs, Exportar copia de seguridad,
  Importar copia de seguridad.

"Búsqueda global…" (Ctrl+K) sale de "Más ▾" y pasa a ser un icono de búsqueda
directo en la barra superior, dado su uso frecuente. "Salir" no necesita
entrada de menú — el cierre de ventana ya lo cubre.

### 5.2 Barra de menú clásica de Windows

**Desaparece por completo.** Se elimina `QMenuBar` (`ui/app_menu.py` y su
invocación en `main_window.py`); todo su contenido se redistribuye entre la
barra superior, "Más ▾" (§5.1) y el icono de búsqueda global. Consistente con
el patrón de app moderna sin menú tradicional (Netflix/Plex/Spotify).

### 5.3 Estilo visual de diálogos

**Se mantiene el patrón modal flotante actual** (ventana centrada sobre fondo
oscurecido) para Ajustes, Ecualizador, Editor M3U, Programar grabación y el
resto de diálogos existentes. No se migra a paneles a pantalla completa —
evita reescribir cada diálogo y mantiene claro que son acciones puntuales,
cerrables con Esc/click fuera. Decisión validada con mockup comparativo en el
companion visual (`.superpowers/brainstorm/1366-1789036607/content/dialog-style.html`).

### 5.4 Comportamiento responsive

Sustituye los umbrales actuales de `DESIGN.md` (520px Inicio / raíl lateral)
por:

- **Barra superior**: a 860px (mínimo soportado) las 5 pestañas + "Más ▾" se
  muestran con texto completo. Por debajo de un umbral a definir en fase de
  implementación (según ancho real medido de las pestañas con texto), la
  barra colapsa a **solo iconos** — nunca a menú hamburguesa.
- **Hero de Inicio**: se encoge en altura (menos padding, tipografía más
  pequeña) al acercarse al mínimo de 860×580, en vez de ocultarse u
  obligar a un layout vertical. Las filas de carruseles ya se desplazan
  horizontalmente a cualquier ancho, así que no necesitan modo vertical.
- **"Ahora suena"**: **sin cambios** respecto a `DESIGN.md` — conserva el
  umbral de 390px y el modo compacto documentado (oculta carátula y saltos
  secundarios, reduce el deslizador de volumen de 108px a 56px, mantiene
  reproducción/parada/reintento/grabación/silencio/menú de opciones). No
  depende del modelo de navegación, así que el comportamiento actual sigue
  siendo válido tal cual.

### 5.5 Reflejo del split VIP/Free en la navegación superior

**Mismo patrón que hoy**, solo reubicado:

- La pestaña **Descargas** no se construye en la edición Free (igual que
  `nav_rail.py` hoy: no hay import de `ui/download_panel.py` que la respalde)
  y se oculta en VIP hasta que `win.activated` es `True`.
- El botón de **Cast/DLNA** en "Ahora suena" se omite en Free
  (`now_playing_bar_builder.py` ya condiciona esto; se traslada tal cual).
- **"Activar VIP…"** vive dentro de "Más ▾" → Ajustes, solo cuando
  `not win.activated and not win.es_version_free` (ver §5.1).

Sin cambios de comportamiento respecto al shell compartido VIP/Free ya
decidido en la revisión de arquitectura previa — solo cambia dónde vive cada
condicional en el árbol de módulos nuevo.

### 5.6 Enfoque técnico de migración

**Sustitución directa dentro de `ui/`**, sin coexistencia con flags ni árbol
paralelo en `v8/`. Los módulos nuevos (`nav_top.py`, y equivalentes para
"Más ▾", diálogos reubicados, etc. en fases futuras) reemplazan
directamente a los actuales (`nav_rail.py`, `app_menu.py`, etc.) en una
serie de PRs enfocados sobre el mismo árbol de `ui/`, siguiendo el patrón
ya establecido por el refactor reciente de `main_window.py` (commits
`cfa3a5e`..`22e57aa`). **Actualizado 2026-09-10:** `TDTRadioVIP_v8.0/` pasó
de ser un workspace de solo documentación a contener un git worktree real
del repo (`TDTRadioVIP_v8.0/TDTRadioVIP/`, mismo `.git`/historial/remotos
que este checkout) — es donde vive y se ejecuta el código de cada fase de
v8 a medida que se completa, no un árbol paralelo/duplicado.

## 6. Fase 2 — Inicio: hero + filas + tarjetas póster (decisiones cerradas 2026-09-10)

Diseño de la Fase 2, continuación directa de §4.3/§4.4/§4.6 (que ya
fijaban el enfoque de alto nivel). Estas son las decisiones de detalle que
faltaban, resueltas retomando el diseño:

### 6.1 Filas de Inicio: reorganizar lo existente, no inventar

`ui/home_page_builder.py` ya construye tres carruseles reales
(`ui.carousel.Carousel`/`CarouselCard`, con reutilización de tarjetas,
carga de logo diferida y accesibilidad ya implementadas y testeadas) más
una lista de favoritos. La Fase 2 reorganiza eso en vez de crear
categorías nuevas:

- **Ahora en antena** (`win.home_on_air_carousel`) — sin cambios de datos,
  solo el nuevo estilo de tarjeta.
- **Continuar viendo/escuchando** (antes "Recientes",
  `win.home_recent_carousel`) — mismo dato (`win.history`), solo renombrado
  para encajar con el lenguaje "hero + filas" de la spec.
- **Recomendado para ti** (`win.home_recommended_carousel`) — sin cambios.
- **Favoritos** — se convierte de lista (`win.home_fav_list`, un
  `_make_list()`) a carrusel (`Carousel`), consistente con §4.6.

Explícitamente **fuera de alcance**: filas de "todos tus canales de TV" o
"toda la radio" — esas ya tienen pestaña dedicada en la barra superior
(`ui.nav_top`); repetirlas en Inicio sería redundante, no lo que pedía la
spec (los ejemplos de §4.3 eran ilustrativos, no una lista cerrada).

### 6.2 Hero: restyling de la tarjeta "reproduciendo ahora" existente

`win.home_now_card` (`ui/home_page_builder.py`) y su lógica en
`ui.home_controller.HomeController._refresh_home_now_playing` ya
implementan exactamente el comportamiento que pide §4.3 ("destacada o en
curso de reproducción"):

1. Si hay algo sonando (`win.current_url`): muestra nombre, tipo (TV en
   directo / Radio online), botón Pausar/Continuar, botón de ventana
   flotante.
2. Si no hay nada sonando pero hay historial: muestra la última emisión
   ("Vuelve a tu última emisión en directo", botón "Volver a escuchar").
3. Si no hay historial: genérico ("¿Qué te apetece escuchar?", botón
   "Buscar" que abre la paleta de comandos Ctrl+K).

La Fase 2 **no toca esta lógica** — solo la composición visual, agrandando
la tarjeta a banner de hero con degradado de superficie (sin foto de fondo
real, igual que las tarjetas — ver §4.4 sobre por qué no hay backdrop
disponible) y quitando los "quick buttons" de TV/Radio de la portada (ya
redundantes con las pestañas de la barra superior).

### 6.3 Tarjeta póster: opción A "Compacta"

Confirmado sobre mockup comparativo en el companion visual
(`.superpowers/brainstorm/1755-1789041565/content/poster-card.html`,
comparando A "Compacta" 128×190px, B "Tile cuadrado" 170×170px y C
"Póster vertical" 140×210px):

- **Mismas dimensiones que `CarouselCard` hoy** (`CARD_WIDTH = 128`,
  `CARD_LOGO_SIZE = 96` en `ui/carousel.py`) — la tarjeta póster es un
  restyling del ancho/alto ya validado, no un tamaño nuevo.
- **Fondo degradado determinista**: hash del nombre del canal/emisora →
  selecciona un color base de `ui.style.ACCENT_PRESETS` (6 tonos ya
  existentes: Dorado, Azul, Violeta, Verde, Coral, Naranja) → tonos
  derivados (claro/oscuro) vía `ui.style.accent_shades()`, ya existente y
  usado hoy para la tarjeta "reproduciendo ahora" y el icono de PiP
  activo. No se introduce ningún sistema de color/hash nuevo.
- Logo centrado sobre el degradado, igual que hoy (`CARD_LOGO_SIZE`, con
  el mismo fallback a icono TV/Radio cuando no hay `logo`).

### 6.4 Enfoque técnico: restyling de `ui/carousel.py`, no un módulo nuevo

A diferencia de lo apuntado en §5.6 (que mencionaba `poster_card.py` como
módulo nuevo hipotético), la Fase 2 **reutiliza `CarouselCard` tal cual**
en vez de sustituirla: ya gestiona reutilización de tarjetas al actualizar
`set_entries()`, carga de logo diferida y navegación por teclado
(`tests/test_ui_performance.py` ya cubre esto). Solo cambia cómo se pinta
el fondo (degradado en vez de superficie plana). `ui/home_page_builder.py`
se reestructura para el layout hero+filas (banner grande arriba, filas de
carrusel debajo), siguiendo el mismo patrón de sustitución directa in-place
que la Fase 1 (§5.6) — sin flags, sin árbol paralelo.

## 7. Próximos pasos (histórico -- todas las fases quedaron cerradas, ver §8)

1. ~~Invocar `superpowers:writing-plans` para generar el plan de
   implementación detallado de la Fase 2, basado en §6~~ -- hecho, ver
   `docs/superpowers/plans/2026-09-10-v8-home-hero.md`.
2. ~~Ejecutar el plan siguiendo el flujo de desarrollo habitual (TDD,
   revisión de código)~~ -- hecho.
3. ~~Fases siguientes (§5.1-§5.2 "Más ▾" y retirada del menú clásico,
   responsive, pulido VIP/Free)~~ -- implementadas directamente sobre la
   spec ya cerrada de §5, sin plan formal aparte (alcance acotado y de
   bajo riesgo arquitectónico); ver §8 para el cierre de cada una.
4. ~~Pendiente real: fusionar `feature/v8-home-hero` a `master`~~ -- hecho
   (2026-09-11, fast-forward; ver cabecera **Estado**).

## 8. Fases 3-5 — cierre de implementación (2026-09-11)

Las tres fases quedaban con diseño cerrado desde §5 (2026-09-10); esta
sección documenta cómo aterrizó cada una en código, incluidas las
decisiones de detalle que §5 dejaba abiertas a "la fase de
implementación".

### 8.1 Fase 3 — "Más ▾" y retirada de la barra de menú clásica

`ui/app_menu.py` (QMenuBar) se retira por completo; `ui/more_menu.py`
(nuevo) construye el botón "Más ▾" de la barra superior con las mismas
seis categorías de §5.1, cada entrada delegando en el mismo
controlador/método que ya usaba la barra de menú clásica -- solo cambia
el punto de entrada. "Herramientas de audio" (Convertir/Editor MP3/
Editar info) no son diálogos propios: son pestañas de
`ui.download_panel.DownloadPanel`, así que esas tres entradas saltan a
Descargas y seleccionan la pestaña pedida en vez de abrir algo nuevo; se
omiten por completo en la edición Free (Descargas no existe ahí). El
icono de búsqueda global vive como botón propio en `ui.nav_top`, y el
atajo Ctrl+K se registra a nivel de ventana en
`MainWindow._registrar_atajos` (antes vivía en la `QAction` de la barra
de menú retirada).

### 8.2 Fase 4 — Responsive

**Barra superior**: el umbral de colapso a solo-iconos no es un píxel
fijo elegido a ojo -- `ui.nav_top.build_nav_top` mide el ancho real
(`sizeHint()`) que necesitan todos sus botones con el texto completo en
el momento de construir la barra, y `update_nav_top_compact()` compara
el ancho disponible contra ese valor medido en cada resize. Se adapta
solo a la fuente/DPI real de cada máquina, igual que ya hace
`download_panel.py` con `QFontMetrics` para sus propios botones de ancho
variable. Nunca oculta ni quita botones -- coherente con "nunca a menú
hamburguesa" (§5.4).

**Hero de Inicio**: `HomeController.update_home_compact()` gana un
segundo umbral, más estrecho que el ya existente de 520px (que apila la
fila de "reproduciendo ahora"/salud en vertical): por debajo de 360px de
`_home_viewport` (el área scrolleable de Inicio, no la ventana entera --
vive dentro del splitter junto al panel del reproductor y puede ser
bastante más estrecha que los 860px mínimos de la ventana), el hero
reduce su padding (22px → 14px) y el tamaño del título (22pt → 15pt) en
vez de ocultarse o cambiar de layout.

**"Ahora suena"**: sin cambios, tal como fijaba §5.4 -- conserva su
propio umbral de 390px.

### 8.3 Fase 5 — Pulido VIP/Free

Auditoría de los 3 puntos de §5.5 contra el código ya existente: **los
tres se cumplían ya sin necesidad de ningún cambio.** Descargas sigue sin
construirse en Free (`ui.nav_top`) y oculta en VIP hasta activar; el
botón de Cast/DLNA sigue condicionado a `win.activated`/`es_version_free`
en `ui.now_playing_bar_builder`; y "Activar VIP…" quedó ya reubicado
dentro de "Más ▾" → Ajustes como parte de la Fase 3 (§8.1), con la misma
condición (`not win.activated and not win.es_version_free`) que tenía en
la barra de menú clásica retirada. Fase cerrada sin diff de código propio.

## Referencias

- `DESIGN.md` — sistema de diseño vigente (tokens, reglas, componentes).
- `PRODUCT.md` — compromisos de marca y contexto de producto.
- Mockups del companion visual: `.superpowers/brainstorm/127-1788960745/content/`
  (`home-layout.html`, `card-style.html`),
  `.superpowers/brainstorm/1366-1789036607/content/` (`dialog-style.html`) y
  `.superpowers/brainstorm/1755-1789041565/content/` (`poster-card.html`).
