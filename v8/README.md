# TDT & Radio VIP — v8 (rediseño de interfaz)

Carpeta de trabajo dedicada al rediseño radical de interfaz planteado para la
versión 8. Todavía **no contiene código** — el proyecto está en fase de diseño
y la sesión de brainstorming se pausó a petición del usuario.

## Estado actual

**Diseño en progreso, pausado.** Ver el spec completo con todo lo decidido y lo
pendiente:

- [`docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md`](../docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md)

## Resumen de una línea

Rediseño radical de la estructura, navegación y layout de la app (estilo
Netflix/Plex: barra superior, hero + filas de carruseles, tarjetas tipo
póster), conservando la identidad de marca actual (nombre, icono, firma
"Coder By X@R", paleta marino + dorado, tipografía Inter — ver `../DESIGN.md`
y `../PRODUCT.md`).

## Cómo retomar

1. Abrir el spec enlazado arriba y leer la sección "Abierto / pendiente para
   la próxima sesión".
2. Invocar de nuevo `superpowers:brainstorming` (o simplemente pedir
   "seguimos con el diseño de v8") para continuar resolviendo esos puntos.
3. Cuando el diseño esté aprobado, se generará un plan de implementación
   (`superpowers:writing-plans`) y el código de v8 empezará a vivir dentro de
   esta misma carpeta.

## Estructura prevista (aún no creada)

```
v8/
├── README.md          (este archivo)
├── docs/              (documentación específica de v8 según avance el diseño)
└── ...                (código de la nueva interfaz, cuando empiece la implementación)
```
