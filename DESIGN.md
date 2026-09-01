---
name: "TDT & Radio VIP"
description: "Biblioteca multimedia Windows de precisión nocturna, con navegación naval y acento luminoso configurable."
colors:
  signal-gold: "#c9a227"
  signal-gold-light: "#e8c360"
  signal-gold-lighter: "#f4d476"
  midnight-root: "#0d1b2a"
  midnight-panel: "#1b2a41"
  midnight-card: "#223350"
  midnight-raised: "#283c5e"
  midnight-hover: "#2f466d"
  boundary: "#2a3b55"
  boundary-strong: "#3d5578"
  text-primary: "#f2efe6"
  text-secondary: "#bcc9da"
  text-muted: "#a6b5c7"
  text-dim: "#8e9daf"
  status-danger: "#f26f6c"
  status-success: "#42c985"
  function-cast: "#31c7b2"
  function-sleep: "#9b7bea"
  function-info: "#55a7e8"
  function-media: "#f39a55"
typography:
  display:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "22pt"
    fontWeight: 800
    letterSpacing: "-0.3px"
  headline:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "17pt"
    fontWeight: 800
  title:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "14pt"
    fontWeight: 750
  body:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "10pt"
    fontWeight: 400
  label:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "8pt"
    fontWeight: 800
    letterSpacing: "1.4px"
rounded:
  control-sm: "7px"
  control: "10px"
  card: "14px"
  prominent: "18px"
  hero: "20px"
  pill: "22px"
spacing:
  micro: "2px"
  xs: "4px"
  sm: "8px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  xxl: "22px"
components:
  button-primary:
    backgroundColor: "{colors.signal-gold}"
    textColor: "{colors.midnight-root}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  button-quick-action:
    backgroundColor: "{colors.signal-gold}"
    textColor: "{colors.midnight-root}"
    typography: "{typography.body}"
    rounded: "{rounded.pill}"
    padding: "11px 22px"
  button-secondary:
    backgroundColor: "{colors.midnight-card}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  input:
    backgroundColor: "{colors.midnight-root}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  navigation-item:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  navigation-item-active:
    backgroundColor: "{colors.midnight-raised}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  card:
    backgroundColor: "{colors.midnight-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.card}"
    padding: "14px"
---

# Design System: TDT & Radio VIP

## Overview

**Creative North Star: "La Cabina Nocturna"**

TDT & Radio VIP se comporta como una cabina de emisión personal: oscura, estable y preparada para sesiones largas. La base azul marino reduce el ruido de catálogos densos; el dorado configurable aparece como señal de acción o foco, mientras que los colores funcionales distinguen TV, radio, emisión, temporizador y estados sin competir con la marca.

La interfaz es una herramienta nativa de Windows en modo Operate. Su personalidad vive en la precisión de las capas, los bordes finos, las esquinas suaves, los degradados contenidos y la iconografía vectorial pintada con QPainter. La información y el estado de reproducción mandan sobre el ornamento.

**Key Characteristics:**

- Jerarquía naval por superficies tonales, con contraste cálido en texto y acento.
- Densidad de escritorio legible, preparada para ratón y teclado.
- Estado activo neutral con una línea de acento contextual, nunca una masa de color gratuita.
- Inicio y Ahora suena se recomponen para conservar controles esenciales en ventanas estrechas.
- Iconos geométricos consistentes, sin depender de glifos tipográficos.

## Colors

La paleta combina profundidad naval con una señal cálida y escasa; los colores adicionales comunican función, no decoración.

### Primary

- **Oro de Señal:** acento predeterminado para acciones principales, foco, selección y progreso; puede ser sustituido por el color elegido en Apariencia y conserva derivados claro, oscuro, hover, pressed, soft y texto sobre acento.
- **Oro de Señal Claro:** borde de foco y énfasis seleccionado sobre superficies oscuras.
- **Oro de Señal Luminoso:** texto o detalle de selección que necesita sobresalir sin rellenar toda la superficie.

### Secondary

- **Turquesa de Emisión:** estado y acción de casting.
- **Violeta de Descanso:** temporizador de apagado.
- **Azul de Información:** TV, información y estados de carga.
- **Naranja de Medios:** radio, podcasts y categorías afines.

### Tertiary

- **Verde de Sistema:** confirmación y salud correcta.
- **Coral de Alerta:** error, peligro y grabación crítica.

### Neutral

- **Medianoche Raíz:** lienzo más profundo y campos de entrada.
- **Medianoche Panel:** navegación y contenedores estructurales.
- **Medianoche Tarjeta:** tarjetas y grupos de contenido.
- **Medianoche Elevada:** selección neutral y superficies elevadas.
- **Medianoche Hover:** respuesta de puntero y máxima capa tonal ordinaria.
- **Límite Naval / Límite Firme:** separadores y contornos según jerarquía.
- **Marfil Primario:** títulos y contenido esencial.
- **Niebla Secundaria, Niebla Atenuada y Niebla Lejana:** escala de apoyo, metadatos y estados de menor prioridad; los niveles usados como texto mantienen contraste AA sobre sus superficies previstas.

**The Signal, Not Wallpaper Rule.** El acento identifica acción, selección, progreso o foco; no sustituye las superficies navales.

**The Functional Color Rule.** Turquesa, violeta, azul, naranja, verde y coral conservan su significado funcional y no se intercambian por variedad visual.

## Typography

**Display Font:** Inter (con Segoe UI y sans-serif como fallback)

**Body Font:** Inter (con Segoe UI y sans-serif como fallback)

**Label Font:** Inter (con Segoe UI y sans-serif como fallback)

**Character:** Inter aporta una voz técnica, clara y compacta que funciona bien en controles densos de escritorio. Peso, tamaño y tracking establecen jerarquía sin introducir una segunda familia ornamental.

### Hierarchy

- **Display** (800, 22pt, tracking -0.3px): saludo de Inicio y momentos de orientación principal.
- **Headline** (800, 17pt): título de sección o diálogo.
- **Title** (750, 14pt): contenido en reproducción y encabezados de alta relevancia.
- **Body** (400, 10pt): controles, menús y contenido operativo habitual.
- **Label** (800, 7.5–8.5pt, tracking 0.8–1.6px): captions, contadores, badges y contexto compacto; suele aparecer en mayúsculas cuando nombra una categoría de interfaz.

**The One Family Rule.** Toda la interfaz usa Inter; Segoe UI existe únicamente como fallback técnico.

**The Weight Before Color Rule.** La jerarquía principal se establece con peso y tamaño antes de añadir un color funcional.

## Layout

La ventana principal usa barra de título propia, raíl de navegación fijo de 180px, superficie de contenido flexible y barra persistente de reproducción. El tamaño mínimo operativo es 860 × 580px. Los paneles internos permiten encogerse en vez de forzar overflow horizontal.

Inicio cambia de composición horizontal a vertical cuando su ancho disponible baja de 520px. Ahora suena entra en modo compacto por debajo de 390px: oculta la carátula y los saltos secundarios, reduce el deslizador de volumen de 108px a 56px y mantiene visibles reproducción, parada, reintento, grabación, silencio y el menú de opciones. Las acciones secundarias viven en “Más opciones” para no comprimir objetivos esenciales.

El ritmo espacial se concentra entre 8 y 18px; 2–4px se reservan para microseparación, estados y ajustes ópticos. Las filas de catálogos son densas, pero las acciones críticas de la barra de reproducción conservan objetivos generosos y tooltips.

**The Essential Controls Survive Rule.** Reducir la ventana puede reordenar contenido u ocultar ayudas secundarias, pero nunca elimina la ruta para reproducir, detener, recuperar o abrir más opciones.

## Elevation & Depth

El sistema usa un híbrido de capas tonales, contornos finos y degradados navales. Las superficies permanecen mayormente planas; la profundidad de paneles destacados procede de un borde superior ligeramente más luminoso y de cambios de tono, no de sombras flotantes pesadas. Inicio, el reproductor, Ahora suena y los diálogos admiten degradados suaves porque representan zonas estructurales, no tarjetas decorativas independientes.

**The Tonal Depth Rule.** La jerarquía de profundidad se construye primero con Medianoche Raíz → Panel → Tarjeta → Elevada → Hover; un borde refuerza la separación solo cuando dos capas adyacentes lo necesitan.

**The No Floating Slabs Rule.** No se añaden sombras grandes a listas, formularios o tarjetas ordinarias.

## Shapes

Los controles pequeños usan curvas de 7–10px; las tarjetas y grupos usan 14px; Ahora suena usa 18px y los héroes estructurales 20px. Las acciones rápidas principales son píldoras de 22px. Bordes de un píxel y líneas contextuales de uno a tres píxeles mantienen las siluetas precisas. Carátulas y contenido multimedia quedan recortados dentro de su contenedor; la iconografía se dibuja con QPainter mediante trazos y rellenos vectoriales consistentes.

**The Radius Follows Scale Rule.** El radio aumenta con el tamaño y protagonismo del contenedor; una fila compacta no adopta la silueta de un héroe.

**The Painted Icon Rule.** Los controles usan iconos QPainter del sistema existente; no se introducen emojis, caracteres Unicode ni fuentes de iconos como sustitutos.

## Components

### Buttons

- **Shape:** controles ordinarios suavemente curvos (10px); acciones rápidas en píldora (22px).
- **Primary:** degradado derivado del acento, texto calculado para máximo contraste y borde luminoso fino; padding ordinario de 8px × 14px o 11px × 22px en acciones rápidas.
- **Hover / Focus:** hover aclara el acento; pressed lo oscurece; el foco visible usa el derivado claro sin depender solo de un cambio de relleno.
- **Secondary:** superficie naval o transparente con texto secundario; hover sube una capa tonal y fortalece el borde.
- **Semantic:** danger, cast, sleep e info conservan su color de función, incluidos estados checked.

### Chips

- **Style:** badges transparentes o tonales, borde fino, radio de 7–14px, tipografía compacta y tracking positivo.
- **State:** selección usa acento o color funcional con texto contrastado; los contadores permanecen neutrales.

### Cards / Containers

- **Corner Style:** 14px para tarjetas, 18–20px para superficies protagonistas.
- **Background:** capas navales; los carouseles de TV y radio reciben un tono soft derivado y una línea inferior del color funcional.
- **Shadow Strategy:** sin sombra ordinaria; profundidad tonal y borde.
- **Border:** un píxel en Límite Naval, reforzado al pasar el puntero.
- **Internal Padding:** habitualmente 8–14px, con mayor aire en héroes.

### Inputs / Fields

- **Style:** fondo Medianoche Raíz, borde naval, radio de 9–10px y padding de 8–14px.
- **Focus:** borde de acento visible y fondo ligeramente elevado.
- **Error / Disabled:** error mediante Coral de Alerta; los estados no disponibles reducen prioridad sin perder legibilidad.

### Navigation

El raíl de 180px alinea icono y etiqueta a la izquierda. En reposo es transparente con texto atenuado; hover usa una superficie neutral. La ruta activa usa Medianoche Elevada y una línea izquierda del acento contextual. El foco dibuja un contorno claro completo. La barra superior y los controles de ventana mantienen convenciones de escritorio Windows.

### Now Playing

Ahora suena es la firma operativa del sistema: una superficie naval persistente, título dominante, estado legible, carátula contenida y controles circulares dibujados. La información cambia con una breve transición de opacidad OutCubic; en ancho compacto se simplifica sin perder el control de la sesión.

### Carousel Card

Tarjeta compacta de 128px con logo de 96px, nombre, metadato y clasificación funcional TV/radio. Hover eleva el tono y el borde; la línea inferior conserva la categoría incluso en una fila visualmente densa.

## Do's and Don'ts

### Do:

- **Do** construir nuevas superficies con la escala naval compartida y reservar el acento para interacción y estado.
- **Do** conservar Inter, la marca TDT & Radio VIP, la firma Coder By X@R y el icono empaquetado.
- **Do** ofrecer foco visible, tooltip y nombre accesible en controles solo-icono.
- **Do** verificar Inicio y Ahora suena a 860 × 580px y en sus umbrales internos de 520px y 390px.
- **Do** usar los iconos QPainter existentes o ampliar ese mismo vocabulario geométrico.

### Don't:

- **Don't** usar el dorado configurable como fondo dominante de navegación activa; la selección se apoya en una superficie neutral y un acento contextual.
- **Don't** introducir glifos, emojis o fuentes de iconos en controles de producto.
- **Don't** ocultar controles esenciales ni provocar overflow para conservar una composición amplia.
- **Don't** añadir sombras pesadas, glassmorphism o tarjetas flotantes ajenas a la profundidad tonal existente.
- **Don't** asignar un color funcional por gusto: cada tono semántico conserva su significado.
