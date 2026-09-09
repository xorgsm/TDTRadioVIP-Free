# Rediseño radical de interfaz — TDT & Radio VIP v8

**Estado:** Diseño en progreso, PAUSADO a petición del usuario para retomar en otra sesión.
**Fecha de inicio:** 2026-09-09
**Ruta de trabajo dedicada:** `v8/` (ver `v8/README.md`)
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
Podcasts, Descargas**, más "Más ▾" para el resto de herramientas (pendiente de
cerrar en §5.1).

## 5. Abierto / pendiente para la próxima sesión

Estos puntos se identificaron durante la exploración pero **no se han resuelto
todavía** — son el punto de partida al retomar el diseño:

1. **Contenido completo de "Más ▾"**: candidatos restantes por ubicar
   (Torrents/Soulseek ya viven dentro de Descargas, no aquí): Grabaciones
   recurrentes, herramientas de audio —Convertir, Editor MP3, Editar info—,
   Guía EPG, Configuración, Ecualizador. Favoritos e Historial ya se
   resolvieron como filas de Inicio (§4.6) y Descargas ya se resolvió como
   top-level (§4.7) — faltan solo estos últimos por agrupar.
2. **Barra de menú clásica de Windows** (Archivo/Configuración/Ayuda,
   `ui/app_menu.py` — incluye acciones como "Grabaciones recurrentes…"): no se
   ha decidido si se mantiene tal cual (convención de escritorio actual), se
   fusiona dentro de "Más ▾", o desaparece a favor de un patrón más "app
   moderna" sin barra de menú tradicional.
3. **Estilo visual de diálogos** (Ajustes, Ecualizador, Editor M3U, Programar
   grabación, etc.): no se ha decidido si se mantienen como diálogos modales
   (patrón actual) o se rediseñan como paneles a pantalla completa al estilo
   Netflix/Plex.
4. **Comportamiento responsive**: `DESIGN.md` documenta umbrales concretos
   (520px para Inicio, 390px para Ahora suena) sobre el layout actual de raíl
   lateral. Con barra superior + hero, estos umbrales y el comportamiento en
   la resolución mínima soportada (860×580) hay que redefinirlos desde cero.
5. **Reflejo del split VIP/Free en la nueva navegación superior**: se sabe que
   ambas ediciones comparten el mismo shell (decisión ya tomada en la revisión
   de arquitectura previa), pero no se ha revisado cómo se oculta/adapta la
   barra superior y "Más ▾" para la edición Free (hoy son 21 sitios
   condicionales dispersos en `main_window.py` basados en `activated` /
   `es_version_free`).
6. **Enfoque técnico de migración**: `main_window.py` ya fue dividido
   recientemente en módulos (`nav_rail.py`, `catalog_toolbar.py`,
   `home_page_builder.py`, etc. — ver commits de refactor `cfa3a5e`..`22e57aa`
   en el historial de `origin/master`). El rediseño de v8 probablemente
   necesita módulos nuevos equivalentes (`nav_top.py`, `home_hero.py`,
   `poster_card.py`...) en vez de reutilizar los actuales — falta decidir si
   se reescriben desde cero en `v8/` o se adaptan/migran los módulos
   existentes.

## 6. Próximos pasos al retomar

1. Resolver los puntos pendientes de §5 (preguntas una a una, con companion
   visual para las que sean de layout/composición).
2. Completar el diseño por secciones (arquitectura de módulos, migración de
   datos si aplica, testing) siguiendo el resto del proceso de
   `superpowers:brainstorming` (path arquitectónico).
3. Reescribir esta spec como versión final (sustituir "PAUSADO" por
   "aprobado") y pedir revisión explícita del usuario.
4. Invocar `superpowers:writing-plans` para generar el plan de implementación
   dentro de `v8/`.

## Referencias

- `DESIGN.md` — sistema de diseño vigente (tokens, reglas, componentes).
- `PRODUCT.md` — compromisos de marca y contexto de producto.
- Mockups del companion visual: `.superpowers/brainstorm/127-1788960745/content/`
  (`home-layout.html`, `card-style.html`).
