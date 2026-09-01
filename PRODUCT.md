# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Users

Personas que consumen televisión, radio, podcasts y archivos multimedia desde
un PC Windows y necesitan manejar catálogos grandes con rapidez. Esta
descripción se infiere de las funciones y textos existentes del producto.

## Product Purpose

Centralizar reproducción, descubrimiento, organización, grabación y descarga
de contenido audiovisual en una aplicación de escritorio. El éxito significa
encontrar y reproducir contenido con pocos pasos, incluso con miles de canales.

## Positioning

Una biblioteca multimedia personal que reúne TV, radio, EPG, podcasts,
grabaciones, descargas, torrents y Soulseek sin obligar al usuario a cambiar de
aplicación. Posicionamiento inferido del alcance funcional del repositorio.

## Operating Context

Uso frecuente con ratón y teclado en ventanas de tamaño variable, reproducción
prolongada, catálogos remotos y personalizados, perfiles compartidos en un PC y
conectividad que puede ser lenta o intermitente.

## Capabilities and Constraints

- Aplicación Python con PySide6 y reproductor VLC, distribuida para Windows.
- Ediciones VIP y Free con una misma interfaz y diferentes rutas de entrada.
- Debe conservar compatibilidad con los datos de la rama 7.6.x.
- Las operaciones de red y los catálogos grandes no deben bloquear la interfaz.
- La interfaz debe seguir siendo utilizable desde 860 × 580 píxeles.

## Brand Commitments

Se conservan el nombre TDT & Radio VIP, la firma Coder By X@R, el icono
existente, la tipografía Inter incluida y la identidad oscura azul marino con
acento dorado configurable. Compromisos inferidos de los recursos y tokens.

## Evidence on Hand

- Implementación visual: `ui/style.py`, `ui/palette.py` y `ui/main_window.py`.
- Mockup de referencia: `resources/design/panel-principal-mockup.png`.
- Tipografía e icono empaquetados bajo `resources/`.
- No hay testimonios, métricas comerciales ni material que deba inventarse.

## Product Principles

- Reproducción y estado actual siempre comprensibles.
- Navegación rápida aun con catálogos extensos.
- Controles densos, pero jerarquizados y accesibles.
- Fallos de red recuperables sin perder el contexto del usuario.
- Personalización sin sacrificar consistencia visual.

## Accessibility & Inclusion

Conservar contraste legible, foco visible, navegación por teclado, nombres
accesibles y controles operables en el tamaño mínimo soportado. Requisitos
inferidos de las decisiones de contraste y accesibilidad ya documentadas.
