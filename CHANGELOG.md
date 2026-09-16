# Changelog — TDT & Radio VIP (Coder By X@R)

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [8.6.1] — 2026-09-16

### Fixed
- **Descargas de YouTube: "ERROR: Postprocessing: ffprobe and ffmpeg not
  found"** (`resources/ffmpeg/ffmpeg.exe`): el `ffmpeg.exe` empaquetado
  con la 8.6.0 no era el binario real (~97 MB) sino un puntero de Git
  LFS sin resolver (134 bytes de texto) -- esta copia local del proyecto
  no es un clon git de verdad, así que `git lfs pull` nunca se ejecutó
  sobre ella. `core/config.get_ffmpeg_dir()` solo comprueba que el
  archivo exista, no que sea un ejecutable válido, así que la app creía
  tener ffmpeg empaquetado y se lo pasaba a yt-dlp con
  `--ffmpeg-location`; yt-dlp no encontraba ahí ni ffmpeg ni ffprobe
  funcionando y fallaba toda descarga que necesitara postproceso
  (extraer audio, fusionar vídeo+audio). Restaurado el binario real
  (verificado por SHA-256 contra el puntero LFS:
  `1326dde4c84ff1f96fe6b8916c5bed29e163e9b5dccf995f6f3db069d143ec5e`).
  No se toca `ffprobe.exe` -- sigue deliberadamente sin empaquetar (ver
  `core/mp3_info.py`), y con ffmpeg funcionando de nuevo yt-dlp deja de
  necesitarlo para el postproceso.

## [8.6.0] — 2026-09-16

### Added
- **Cliente VPN (edición VIP): reactivado "Importar perfil (.ovpn)…"**
  (`ui/dialogs/vpn_dialog.py`, `core/vpn_profiles.py`): el modelo
  bring-your-own se había retirado en 8.5.0 para que VPNGate fuera la
  única fuente (100% gratis, sin depender de terceros). En la práctica,
  VPNGate depende de qué voluntarios estén conectados en cada momento y
  suele estar dominado por servidores de Japón/Corea -- confirmado con
  un usuario real: de 99 servidores disponibles, los mejor puntuados
  eran todos de Japón. Se reactiva el botón de importar un `.ovpn`
  propio **junto a** VPNGate (no en su lugar), para quien encuentre un
  perfil gratuito de otro proveedor (p.ej. ProtonVPN free, Windscribe
  free) y quiera más variedad de país. `core/vpn_profiles.import_profile()`
  nunca se había quitado del todo (solo el botón en Ajustes), así que
  no hizo falta tocar su lógica.

### Changed
- **Cliente VPN (edición VIP): sección propia en vez de escondida al
  final de Preferencias** (`ui/dialogs/vpn_dialog.py`, `ui/more_menu.py`,
  `ui/dialog_actions.py`): la sección VPN vivía como la quinta de seis
  secciones dentro de un único diálogo con scroll (Ajustes), lo que la
  dejaba prácticamente invisible para quien no supiera de antemano que
  estaba ahí -- reportado por un usuario real que no encontraba cómo
  tener más países. Se extrae a su propio diálogo (`VpnDialog`) con una
  entrada de primer nivel «VPN…» en el menú «Más ▾», junto a «Guía EPG»
  -- un clic en vez de abrir Preferencias y bajar hasta el final. Sigue
  disponible solo en la edición VIP con licencia activada (mismo
  criterio que «Herramientas de audio»/«Activar VIP…»).

## [8.5.4] — 2026-09-15

### Fixed
- **Cliente VPN (edición VIP): la desconexión automática al cerrar la
  app (añadida en 8.5.3) podía no llegar a ejecutarse, sin ningún
  aviso** (`core/vpn_client.py`): `_run()` solo capturaba `OSError`
  alrededor de `subprocess.run()`, pero si `openvpn-gui.exe` no
  respondía a tiempo (10s), `subprocess.run()` lanza
  `subprocess.TimeoutExpired`, que **no** hereda de `OSError` -- se
  escapaba sin convertir a `VpnClientError`. Como esta app no tiene
  manejador global de excepciones (ni consola, al ser un `.exe` sin
  ventana), esa excepción desaparecía en silencio y cortaba el resto
  del cierre de la app a medias, sin dejar el túnel VPN desconectado ni
  ningún rastro en el log. Confirmado con un usuario real: la VPN se
  quedaba conectada al cerrar pese al arreglo de 8.5.3.
  `AppLifecycle.disconnect_vpn_profiles()` (`ui/app_lifecycle.py`)
  ahora además captura cualquier excepción por perfil (no solo
  `VpnClientError`) y la deja registrada en el log en vez de dejar que
  aborte el resto del cierre -- best-effort por diseño, nunca debe
  bloquear cerrar la app.

## [8.5.3] — 2026-09-15

### Fixed
- **Cliente VPN (edición VIP): el estado siempre salía "Desconectado"
  aunque el túnel estuviera realmente activo, y se acumulaban túneles
  duplicados** (`core/vpn_client.py`): `find_log_dir()` asumía que el
  log de cada perfil vivía junto a la carpeta de configs
  (`...\OpenVPN\log`, hermana de `...\OpenVPN\config`) -- confirmado en
  una instalación real (OpenVPN GUI 11.66.0.0 / OpenVPN 2.7.7) que esa
  carpeta ni existe: el log lo escribe siempre openvpn-gui.exe en la
  carpeta de logs *por usuario* (`%USERPROFILE%\OpenVPN\log`, o lo que
  diga `HKCU\SOFTWARE\OpenVPN-GUI\log_dir` si existe), sin relación con
  dónde viva el `.ovpn`. Como la app nunca encontraba el log real,
  `status()` devolvía siempre "desconectado" -- el botón de Ajustes
  nunca pasaba a "Desconectar", así que cada vez que el usuario pulsaba
  "Conectar" creyendo que no había túnel activo, se abría uno nuevo
  encima del anterior sin cerrar el que ya estaba (varios `openvpn.exe`
  y varios adaptadores TAP-Windows6 acumulados en Windows). Con el log
  encontrado en el sitio correcto, `status()` refleja la conexión real
  y el botón/etiqueta de Ajustes (ver 8.5.2) se comporta como toca.

### Added
- **La VPN se desconecta sola al cerrar la app**
  (`ui/app_lifecycle.py`): hasta ahora, cerrar TDT Radio VIP no tocaba
  el túnel VPN -- openvpn-gui.exe seguía gestionándolo aparte, así que
  se quedaba conectado hasta desconectarlo a mano. `AppLifecycle.shutdown()`
  ahora llama a `disconnect_vpn_profiles()`, que corta cualquier perfil
  VPN que siga conectado antes de cerrar.

## [8.5.2] — 2026-09-15

### Changed
- **Cliente VPN (edición VIP): estado de conexión visible y en verde
  dentro de la propia app** (`core/vpn_client.py`,
  `ui/dialogs/settings.py`, `ui/style/builder.py`): hasta ahora, para
  saber si la VPN estaba realmente conectada (o para desconectarla) casi
  siempre hacía falta mirar la ventana propia de `openvpn-gui.exe` (la
  que muestra el log de conexión y sus propios botones
  Desconectar/Reconectar), porque `connect()` la abre automáticamente y
  el estado en Ajustes solo se releía al abrir el diálogo o pulsar el
  botón. Ahora: (1) `connect()` activa "silent_connection" en
  openvpn-gui.exe antes de conectar, así que esa ventana ya no aparece
  sola; (2) el botón de conectar/desconectar y la etiqueta de estado en
  Ajustes → VPN se releen solos cada 2 segundos mientras el diálogo está
  abierto y se pintan en verde ("success", mismo verde que el resto de
  la app) al conectar. Todo el control queda dentro de la app, sin
  depender del icono ni de la ventana de OpenVPN.

## [8.5.1] — 2026-09-15

### Fixed
- **Cliente VPN (edición VIP): "No se pudo registrar el perfil en
  OpenVPN" aunque el usuario ya pertenece al grupo "OpenVPN
  Administrators"** (`core/vpn_client.py`, `core/vpn_profiles.py`): en
  instalaciones de OpenVPN donde el instalador no dejó permiso de
  escritura para ese grupo en `...\OpenVPN\config\` (pasa aunque el
  usuario sí sea miembro del grupo -- confirmado en una máquina real con
  OpenVPN 2.7.7), importar un servidor de VPNGate fallaba siempre con
  `PermissionError`. Ahora, si la copia del `.ovpn` falla por permisos,
  la app pide una única elevación (UAC) para conceder ese acceso con
  `icacls` y reintenta -- sin pasos manuales ni conocimientos de grupos
  de Windows por parte del usuario. Si cancela el UAC o el problema
  persiste, se mantiene el mensaje de error anterior como red de
  seguridad.

## [8.5.0] — 2026-09-14

### Removed
- **Cliente VPN (edición VIP): retirado el modelo "trae tu propia VPN"**
  (`ui/dialogs/settings.py`, `core/vpn_profiles.py`, `core/vpngate.py`):
  desaparece el botón "Importar perfil (.ovpn)…" que dejaba usar una
  suscripción VPN de pago propia. VPNGate (servidores públicos gratis,
  sin cuenta) pasa a ser la única fuente de perfiles VPN de la app --
  con esto el apartado de VPN queda 100% gratis y sin ninguna
  suscripción de terceros de por medio, en línea con el objetivo
  original de `docs/superpowers/specs/2026-09-14-vpngate-free-servers-design.md`.
  **Cambio incompatible:** quien ya tuviera un perfil VPN importado a
  mano (no VPNGate) sigue pudiendo conectarlo/desconectarlo/borrarlo si
  ya estaba guardado, pero no hay forma de importar uno nuevo así --
  solo mediante "Servidor gratuito (VPNGate)…".

## [8.4.0] — 2026-09-14

### Added
- **Servidores VPN gratuitos vía VPNGate** (`core/vpngate.py`,
  `ui/dialogs/vpngate_picker.py`): nuevo botón "Servidor gratuito
  (VPNGate)…" en Ajustes → VPN, junto al de importar un `.ovpn` propio.
  Descarga la lista pública de servidores del proyecto VPNGate
  (Universidad de Tsukuba) -- voluntarios, sin cuenta ni suscripción -- y
  deja elegir uno por país; a partir de ahí es un perfil VPN más, igual
  que uno importado a mano. Complementa el modelo bring-your-own de
  8.3.0, no lo sustituye. Diseño completo en
  `docs/superpowers/specs/2026-09-14-vpngate-free-servers-design.md`.

## [8.3.0] — 2026-09-14

### Changed
- **Cliente VPN (edición VIP): WireGuard → OpenVPN**
  (`core/vpn_client.py`, `core/vpn_profiles.py`, sección «VPN» en
  Ajustes): el usuario sigue aportando su propia suscripción VPN (modelo
  bring-your-own, sin servidores propios), pero ahora importa un `.ovpn`
  en vez de un `.conf` de WireGuard. Conectar y desconectar ya **no**
  piden permiso de administrador de Windows en cada operación -- OpenVPN
  ≥ 2.4 instala su servicio interactivo una sola vez (durante la
  instalación de OpenVPN, no la hace esta app) y a partir de ahí
  cualquier usuario del grupo local "OpenVPN Administrators" puede
  conectar/desconectar sin UAC. Detecta si falta el cliente oficial de
  OpenVPN y enlaza a la descarga en vez de fallar en silencio. Diseño
  completo en `docs/superpowers/specs/2026-09-11-vpn-client-design.md`.
- **Cambio incompatible:** los perfiles VPN de WireGuard guardados en
  8.1.0/8.2.0 no son compatibles con este formato. Quien actualice tiene
  que volver a importar sus perfiles como `.ovpn`; no hay migración
  automática.

## [8.2.0] — 2026-09-12

### Added
- **Comprobación automática de actualizaciones al iniciar**
  (`core/updater.check_for_update_if_due`, `ui/app_lifecycle.py`): además
  de la comprobación manual (Ayuda → Buscar actualizaciones), la app mira
  en segundo plano si hay una versión nueva al arrancar, como mucho una
  vez al día. Si la hay, avisa con un aviso flotante no bloqueante con un
  botón «Ver» -- pulsarlo abre el mismo diálogo de siempre (descarga
  verificada por SHA-256 y confirmación antes de ejecutar el instalador).
  La app nunca descarga ni instala nada sin que el usuario lo pida
  explícitamente. Puede desactivarse en Ajustes → Mantenimiento
  automático → «Buscar actualizaciones automáticamente al iniciar».

## [8.1.0] — 2026-09-11

### Added
- **Cliente VPN (WireGuard) en la edición VIP con licencia activada**
  (`core/vpn_client.py`, `core/vpn_profiles.py`, sección «VPN» en
  Ajustes): permite conectar con la suscripción VPN propia del usuario
  para acceder a listas públicas de TV/radio con restricción geográfica
  fuera de España. La app no opera servidores VPN propios -- el usuario
  importa el `.conf` de WireGuard que le da su proveedor, puede guardar
  varios perfiles (uno por país/servidor) y conectar/desconectar con un
  botón. Requiere tener instalado el cliente oficial de WireGuard para
  Windows; la app detecta si falta y enlaza a la descarga en vez de
  fallar en silencio. Conectar y desconectar piden permiso de
  administrador de Windows -- lo pide el propio wireguard.exe al
  instalar/quitar el túnel como servicio, no es una elevación añadida
  por esta app. Diseño completo en
  `docs/superpowers/specs/2026-09-11-vpn-client-design.md`.
- **Atajos de teclado de reproducción y navegación** (`ui/keyboard_shortcuts.py`):
  Espacio (reproducir/pausar), S (detener), ←/→ (±30 s), N/P
  (siguiente/anterior), ↑/↓ (volumen), M (silenciar), F (favorito) y
  Ctrl+1…6 (saltar a cada sección de la barra superior). `PRODUCT.md` ya
  comprometía navegación por teclado, pero la ventana solo registraba F11,
  Esc y Ctrl+K.
  Las teclas sueltas se gestionan con un filtro de eventos, no con
  `QShortcut`, porque un `QShortcut` consume la pulsación antes de que
  llegue al widget con el foco: la primera implementación hacía que la
  flecha Abajo sobre la lista de canales bajase el volumen en vez de
  cambiar de canal, que Espacio sobre un botón pausara en vez de pulsarlo y
  que las flechas no movieran el slider de volumen. El filtro cede la tecla
  cuando el widget enfocado la usa de forma nativa (campos de texto,
  listas, sliders, botones, desplegables editables) y solo actúa cuando
  nadie más la reclama.
- Entrada **«Atajos de teclado…»** en Más ▾ → Ayuda y sistema, generada
  desde la misma tabla que registra los atajos para que no pueda quedarse
  desfasada.
- **Verificación continua en GitHub Actions** (`.github/workflows/ci.yml`):
  ruff, pytest y compileall en cada push y pull request, sobre
  windows-latest y Python 3.12. No instala `python-vlc`, `libtorrent` ni
  `pychromecast`: se comprobó en un entorno limpio que la suite pasa sin
  ellos, y son dependencias binarias que harían el CI lento y frágil sin
  cubrir un solo test más.

### Changed
- `ui/dialogs.py` (1300 líneas) pasa a ser el paquete `ui/dialogs/`, un
  módulo por diálogo (el mayor, `settings.py`, en 357 líneas), y
  `ui/style.py` (1293 líneas) pasa a `ui/style/` repartido en `colors`,
  `qss_base` y `builder`. Ambos superaban con mucho el límite de 800 líneas
  por archivo. La API pública no cambia: los `from ui.dialogs import X` y
  `from ui.style import X` existentes siguen funcionando. Equivalencia del
  tema verificada por hash: `build_style()` produce un QSS idéntico byte a
  byte antes y después, en los 6 acentos × 2 temas.

### Fixed
- El README anunciaba la versión 7.6.5.2 con `APP_VERSION` ya en 8.0.2.
- `ruff check .` fallaba con 6 errores procedentes de utillaje de agentes de
  IA (`.agents/`), ajeno al código del producto.

### Tests
- 179 → 302 pruebas: contrato de los dos paquetes nuevos (46),
  `core/json_store.py`, que no tenía ninguna y es donde un fallo se traduce
  en pérdida de datos del usuario (26), los atajos de teclado (30), y el
  cliente VPN — `core/vpn_profiles.py` y `core/vpn_client.py` con
  `subprocess`/UAC sustituidos por dobles de prueba (21).

## [8.0] — 2026-09-11

Rediseño radical de interfaz (v8) — ver
`docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md` para el
diseño completo y las decisiones cerradas de cada fase. Sustitución
directa dentro de `ui/`, sin flags ni árbol paralelo: no hay forma de
volver a la interfaz de 7.6.x salvo instalando una versión anterior.

### Changed
- **Navegación**: el raíl lateral fijo (`ui/nav_rail.py`) se sustituye por
  una barra superior horizontal (`ui/nav_top.py`) con las secciones de
  contenido como pestañas (Inicio, TV, Radio, Favoritos, Historial,
  Descargas). Por debajo del ancho real que necesitan esas pestañas con
  su texto completo, la barra colapsa a solo iconos — nunca a menú
  hamburguesa.
- **Inicio**: pasa de una portada con botones rápidos TV/Radio y una lista
  de favoritos a un layout "hero + filas" estilo Netflix/Plex — banner
  grande con la reproducción actual (o la última emisión, o un genérico
  si no hay historial) arriba, y 4 filas de carrusel a ancho completo
  debajo (Continuar viendo/escuchando, Ahora en antena, Recomendado para
  ti, Favoritos). El hero se encoge en altura (menos padding, título más
  pequeño) al acercarse al mínimo de la ventana, en vez de ocultarse.
- **Tarjetas de carrusel**: fondo degradado determinista (mismo nombre de
  canal/emisora, mismo color siempre) en vez de superficie plana por
  variante TV/Radio, con logo centrado encima — aspecto "cinematográfico"
  de póster sin depender de fotografía real (el modelo de canal no expone
  backdrop ni miniatura).
- **Barra de menú clásica de Windows** (Archivo/Configuración/Ayuda,
  `QMenuBar`) desaparece por completo. Su contenido se redistribuye entre
  un botón **"Más ▾"** en la barra superior (categorizado: Gestión de
  contenido, Grabaciones, Herramientas de audio, Guía EPG, Ajustes, Ayuda
  y sistema) y un icono de búsqueda global directo (Ctrl+K).

### Fixed
- Nada — este rediseño es puro cambio de composición/estructura visual;
  la identidad de marca, la paleta, la tipografía y toda la lógica de
  reproducción, favoritos, historial, grabaciones y descargas quedan sin
  tocar (ver `PRODUCT.md` § Brand Commitments).

### Tests
- 168 pruebas pasando (`python -m pytest -q`), con cobertura nueva para
  el degradado de tarjetas, la reestructuración de Inicio, el menú
  "Más ▾" y el colapso responsive de la barra superior/el hero.

## [7.6.6.0] — 2026-09-07

### Changed
- Refactor interno puro, sin cambios de comportamiento observable:
  `ui/main_window.py` pasaba de 2309 líneas concentrando construcción de
  UI, navegación, diálogos y ciclo de vida de la app en una única clase.
  Se divide en 13 fases verificadas en 11 módulos nuevos (constantes de
  navegación, portada, barra de título, menú, riel de navegación, barra
  de catálogo, menús del reproductor, barra "Ahora suena", panel del
  reproductor, diálogos secundarios, cambio de sección y arranque/cierre),
  siguiendo el patrón de controladores que ya usaba el resto del código.
  `ui/main_window.py` queda en 605 líneas.

## [7.6.5.2] — 2026-09-07

### Fixed
- El recorte de la guía EPG a los canales del usuario (7.6.5.1) rompía si
  algún canal no tenía `tvg_id`; ahora es tolerante a canales sin ese dato.

### Performance
- El diagnóstico automático de salud de streams al arrancar pasa de 12 a 3
  comprobaciones simultáneas y espera 8 segundos tras cargar el catálogo,
  para no competir por CPU con la carga inicial y la descarga de la guía
  EPG. El diagnóstico manual ("Comprobar catálogo ahora") sigue igual de
  rápido.

## [7.6.5.1] — 2026-09-07

### Performance
- La guía EPG descargada (miles de canales de la fuente pública, aunque el
  usuario solo tenga unos pocos) se recorta en memoria a los canales que
  existen en la lista del usuario, en vez de mantener la guía nacional
  completa residente mientras la app está abierta.

## [7.6.5.0] — 2026-09-05

### Performance
- Las copias automáticas se ejecutan en segundo plano y capturan el perfil
  activo al empezar, manteniendo la ventana disponible durante la escritura.
- Los cambios de reproducción y favoritos solo notifican las filas cuyo estado
  ha cambiado, incluso con catálogos grandes.
- Las herramientas de Descargas se construyen al abrir cada pestaña, no todas
  durante el arranque.
- Los logos se leen y decodifican fuera del hilo de interfaz y las tarjetas de
  Inicio se reciclan al actualizar sus datos.

### Changed
- Inicio prioriza volver a escuchar la última emisión y ordena el estado de
  emisiones antes del diagnóstico técnico.
- Las tarjetas de Inicio tienen foco visible, nombre accesible y activación con
  Enter o Espacio.
- Los botones de cancelar usan iconografía vectorial consistente en lugar de
  glifos dependientes de la fuente.

### Tests
- Se añaden pruebas de regresión para catálogos de 10.000 entradas, caché de
  logos, carga diferida, cierre cooperativo y navegación por teclado.

## [7.6.4.1] — 2026-09-05

### Added
- Mensaje de cariño a Hugo Moreno en el diálogo "Acerca de".

### Changed
- Bump de versión a 7.6.4.1 para que el comprobador de actualizaciones
  detecte esta versión como más nueva que la 7.6.4.0 ya publicada.

## [7.6.4.0] — 2026-09-05

### Changed
- Bump de versión a 7.6.4.0 para alinear el repositorio de fuentes completo
  (VIP + Free) con la versión ya publicada en el repositorio de la edición
  Free.

## [7.6.3.1] — 2026-09-04

### Changed
- Los catálogos grandes de TV y radio usan `QAbstractListModel` con
  `QListView`: se conservan todas las entradas en memoria, pero Qt solo crea
  y pinta las filas visibles.
- El filtrado y el orden se aplican en el modelo, sin ocultar ni reconstruir
  miles de widgets individuales.
- Se mantienen los comportamientos existentes de reproducción, menú
  contextual, favoritos, salud, EPG y carga diferida de logos.

### Performance
- En una prueba sintética con 10.000 entradas, preparar el modelo tardó
  aproximadamente 0,006 s y filtrar 0,003 s, frente a 0,469 s y 0,108 s con
  la lista basada en widgets.

El detalle de implementación y las mediciones está en
[PERFORMANCE_NOTES_7.6.3.1.md](PERFORMANCE_NOTES_7.6.3.1.md).

## [7.6.3.0] — 2026-09-04

### Changed
- Se crea esta rama de trabajo/versionado separado para continuar la mejora
  de rendimiento con catálogos grandes.
- El poblado de listas y tablas reduce repintados intermedios, reutiliza
  tamaños uniformes y evita ordenar de nuevo cuando se conserva el orden de
  origen.
- Los logos se solicitan solo para las filas visibles, con caché LRU en
  memoria y límite de 2.048 imágenes decodificadas.
- La carga y el parseo de listas M3U pasan a segundo plano y el buscador del
  editor usa un pequeño antirrebote.
- El diagnóstico de streams mantiene acotadas las tareas en vuelo y guarda
  todo el lote de resultados con una sola lectura/escritura del historial.
- Las cargas consecutivas de TV/radio descartan respuestas antiguas para que
  una actualización lenta no sobrescriba un catálogo más reciente.

### Fixed
- Restaurar canales o emisoras ocultos vuelve a usar el controlador de
  catálogo actual; ya no llama a métodos eliminados de `MainWindow`.
- El diálogo de diagnóstico ya no pasa un generador a `setEnabled()` y no
  recalcula todos los resúmenes ni inserta filas desde cero en cada resultado.

El detalle técnico, las mediciones y las siguientes líneas de trabajo están
en [PERFORMANCE_NOTES_7.6.3.0.md](PERFORMANCE_NOTES_7.6.3.0.md).

## [7.6.2.1] — 2026-09-01

### Fixed
- El ecualizador de VLC ya no fuga el objeto nativo cuando aplicarlo falla
  a medias.
- Cerrar la app (o los paneles de Torrents/Soulseek) mientras una conexión
  o búsqueda en segundo plano seguía en marcha podía destruir su QThread
  mientras corría; ahora el cierre espera cooperativamente en vez de un
  tope fijo de 1 segundo.
- La comprobación de actualizaciones valida también la URL del
  manifiesto (HTTPS con host), no solo la del instalador.
- La importación de copias de seguridad vuelve a comprobar el límite de
  tamaño sobre la lectura real, no solo sobre el `stat()` previo (evita
  un hueco TOCTOU entre comprobar y leer).
- La tarjeta "reproduciendo ahora" y el resumen de salud de streams de la
  portada de Inicio se habían quedado sin actualizarse tras un refactor
  anterior; vuelven a sincronizarse.

### Changed
- El texto "Ahora: <programa>" del mini-EPG ya no reordena ni reparsea la
  guía completa en cada repoblado de lista de canales -- se prepara una
  sola vez al cargar la guía. Con catálogos de varios miles de canales,
  esto es lo que hacía notarse la app lenta al arrancar.
- Cuando la guía EPG termina de descargarse ya no repuebla la lista de TV
  entera para refrescar el "Ahora: ..." de cada fila -- solo actualiza ese
  texto en las filas ya existentes. Repoblar recreaba todas las filas,
  las reordenaba y volvía a encolar el logo de cada canal, justo detrás
  del poblado inicial (canales, radio y EPG se cargan casi a la vez al
  arrancar); con catálogos de 500 canales o más esa reconstrucción
  duplicada era la que se notaba como "se pone lento y se bloquea" al
  cargar, reportado por usuarios.
- El diagnóstico automático de salud de streams ya no reconstruye las
  listas de TV/radio enteras al terminar -- actualiza solo las filas
  afectadas, evitando el tirón que se notaba si terminaba mientras se
  estaba reproduciendo algo.
- Rediseño de la marca: "TDT & Radio VIP" más grande en la barra de
  título, con la versión debajo. Se quita el banner duplicado del riel
  de navegación y "EXPLORAR" pasa a ser lo primero que se ve, más grande.

## [7.6.2] — En desarrollo

### Fixed
- La comprobación de actualizaciones rechaza enlaces que no sean HTTPS con
  host y versiones remotas desmesuradas, evitando abrir esquemas locales del
  sistema o romper el hilo ante un manifiesto manipulado.
- Las copias automáticas ya no quedan desactivadas indefinidamente por un
  archivo con fecha futura, ignoran directorios con apariencia de backup y
  evitan reescribir dos copias creadas en el mismo segundo. La importación
  también limita el tamaño antes de cargar el JSON en memoria.
- Los nombres de perfil ahora se comparan sin distinguir mayúsculas,
  igual que hace Windows con las carpetas. Esto impide que duplicar o
  renombrar `Familia` como `familia` opere sobre el mismo directorio y pueda
  mezclar o eliminar datos; la grafía original también se recupera al
  cargar el perfil activo.

### Changed
- Interfaz principal refinada: navegación activa sobre una superficie común
  con acento contextual, iconografía vectorial coherente y foco de teclado
  visible en botones, búsqueda y filtros.
- La portada y la barra "Ahora suena" adaptan su composición a ventanas
  estrechas sin solapar controles ni provocar desplazamiento horizontal.
- Los controles de reproducción dejan de depender de glifos Unicode y exponen
  nombres accesibles para tecnologías de asistencia.

## [7.6.1] — En desarrollo

### Fixed
- Al eliminar un grupo de Televisión desde el panel GRUPOS, los canales
  personalizados (importados a mano) de ese grupo volvían a aparecer al
  reabrir la app -- el borrado de grupos usaba siempre el mecanismo de
  "ocultar por nombre" pensado solo para la lista pública, que nunca se
  aplica a los canales personalizados al recargarlos. Ahora los canales
  personalizados del grupo se borran de verdad y los públicos se siguen
  ocultando como antes (reversible desde Archivo > Gestionar canales
  personalizados > Ocultados).
- Arranque mucho más rápido: el cálculo del ID de hardware (licencia)
  lanzaba WMIC y hasta tres procesos `powershell.exe` en cadena, uno tras
  otro; medido en una máquina real llegó a tardar 4m35s en un solo
  arranque. Ahora los tres componentes se lanzan en paralelo (peor caso
  ~3s en vez de la suma de los tres) y, sobre todo, el resultado se
  guarda en disco (`hardware_id_cache.json`) para no volver a lanzar
  ningún proceso en arranques posteriores.
- Los botones de la barra "en reproducción" (favorito, cast, stop,
  retroceder/avanzar, grabar, silenciar, más opciones) se solapaban y se
  veían cortados en ventanas estrechas; reducidos de 32px/46px a
  26px/38px con sus iconos y espaciados ajustados en proporción.

### Security
- El ID de hardware cacheado en disco es editable por cualquiera con
  acceso de escritura al perfil de la app, lo que en teoría permite
  clonar una activación a otro PC copiando ese archivo junto con un
  código de licencia válido. Riesgo aceptado deliberadamente a cambio de
  eliminar minutos de espera en cada arranque -- ver el docstring de
  `generate_hardware_id()` en `core/license.py`.

## [7.6.0] — En desarrollo

### Changed
- Nueva rama de desarrollo independiente de 7.5.11. La versión 7.6.0 usa
  su propia carpeta de datos y puede probarse sin modificar la versión anterior.
- El Editor M3U de la edición Free permite cargar HTTP(S) o archivos locales,
  editar, eliminar grupos completos, detectar duplicados y comprobar streams.

### Security
- Los nombres de perfil se validan en todas las operaciones para impedir que
  rutas manipuladas salgan de la carpeta de perfiles.

## [7.5.11] — En desarrollo

### Added
- La portada de Inicio muestra ahora un resumen de salud de streams: número
  de emisiones revisadas, estables, lentas y con incidencias, con acceso
  directo al diagnóstico completo.
- Nueva API `list_health()` para consultar los resultados persistidos del
  diagnóstico sin acoplar la interfaz al almacenamiento.
- La edición 7.5.11 se instala y guarda sus datos de usuario en directorios
  independientes, por lo que puede convivir con 7.5.10 sin modificarla.

### Fixed
- Eliminado código inalcanzable que quedaba tras la implementación vigente
  de duplicado de perfiles.

### Security
- `.gitignore` protege el registro de licencias emitidas, claves privadas y
  ficheros de entorno frente a inclusiones accidentales en un repositorio.

## [7.5.10] — En desarrollo

### Added
- Importación y exportación M3U separadas para TV y Radio: cada acceso abre
  su propio destino y las listas importadas se mantienen independientes.

### Fixed
- Duplicar el perfil Default ya no intenta copiar la carpeta de datos dentro
  de sí misma. La nueva copia conserva solo los datos personales del perfil
  y no arrastra ajustes globales, caché ni otros perfiles.
- No se permite sobrescribir un perfil existente al duplicar otro.

## [7.5.9] — En desarrollo

### Added
- Menú contextual en Televisión para ocultar un único canal de la lista
  pública, sin borrar ni alterar el resto de la fuente; se puede restaurar
  desde Archivo > Gestionar canales personalizados > Ocultados.
- Panel informativo de TDTChannels en Acerca de, visible en las ediciones
  Free y con licencia, con enlace directo a su lista oficial M3U8.
- Organización y rutas de datos unificadas bajo `CoderByXOR`.
- Descarga segura de actualizaciones mediante HTTPS, archivo temporal,
  límite de tamaño y verificación SHA-256 antes de ejecutar el instalador.
- Copias de seguridad automáticas con frecuencia y retención configurables.
- Centro de próximas grabaciones con estado y cancelación directa.
- Diagnóstico automático y limitado de streams sin comprobar o con resultados antiguos.
- Opción para reanudar automáticamente el último canal o emisora al iniciar.
- Perfiles duplicables, renombrables y eliminables, con protección del perfil Default.

### Fixed
- La navegación lateral ocupa solo el ancho necesario y el catálogo adapta
  búsqueda, filtros y tarjetas al estrechar la ventana, conservando los
  bordes redondeados de los canales.
- Los botones de destino de Descargas ahora pasan a su propia fila cuando
  falta espacio, por lo que Cambiar, Abrir y Actualizar no quedan cortados.
- La hora XMLTV con zona horaria explícita (p. ej. `+0200` o `Z`) ya no se
  descartaba al calcular "ahora/siguiente", los avisos EPG y el
  arranque/parada real de grabaciones programadas.
- La copia de seguridad ahora incluye también grabaciones programadas,
  reglas recurrentes (con su estado de sincronización) y canales/emisoras
  ocultos, que antes se perdían silenciosamente al restaurar en otro PC.
- Crear un perfil con un nombre reservado de Windows (`CON`, `PRN`, `COM1`...)
  ya no revienta con una excepción sin controlar.
- La guía EPG cae correctamente a la caché en disco si el archivo de caché
  tiene un formato inesperado, en vez de fallar y dejar la guía vacía.
- Corregidas fugas de memoria nativa del ecualizador de VLC (cada ajuste de
  slider o preset probado liberaba el objeto anterior).
- Cambiar de canal muy rápido, justo cuando el anterior estaba fallando, ya
  no puede mostrar un error falso ni disparar un auto-salto indebido sobre
  el canal nuevo (el reproductor ya desengancha los eventos del
  media_player anterior antes de sustituirlo).
- Ya no se acumulan hilos de descarga de episodios de podcast terminados en
  memoria durante la sesión.

### Security
- El campo de URL de descarga valida que sea http(s) antes de pasarla a
  yt-dlp, y el comando fuerza el fin de opciones (`--`) para que no pueda
  interpretarse como un flag de línea de comandos.
- Las descargas que se quedan sin actividad (red muerta, servidor colgado)
  se cancelan solas en vez de quedarse "descargando…" para siempre.
- El descubrimiento de dispositivos DLNA verifica que la URL de descripción
  del dispositivo apunte a la misma IP que respondió al SSDP, y limita el
  tamaño de la respuesta descargada.
- La URL de un stream a grabar debe ser http(s) antes de pasarla a ffmpeg.

## [7.5.8] — En desarrollo

### Added
- Renovación integral de la ventana principal: navegación lateral, portada,
  lenguaje visual navy con acentos configurables, catálogo en lista o
  cuadrícula para TV y Radio, mini reproductor PiP y controles de bandeja.
- La preferencia de vista lista/cuadrícula se conserva entre sesiones.
- La guía EPG detecta conflictos entre grabaciones programadas y evita
  reservar dos emisiones solapadas que no podrían grabarse simultáneamente.
- Recuperación automática de emisiones: se intenta reconectar dos veces la
  URL actual antes de saltar al siguiente canal y sin duplicar el historial.
- Ordenación persistente e independiente de TV y Radio: orden de la fuente,
  nombre alfabético o favoritos primero.
- TV y Radio recuerdan por separado la búsqueda y los filtros de categoría
  y estado al navegar entre secciones o reiniciar la aplicación.
- Las entradas duplicadas conservan sus URLs como fuentes de respaldo; la
  recuperación automática las prueba antes de abandonar la emisión.
- Tamaño configurable de tarjetas (compacto, mediano o grande) y temporizador
  de apagado con opciones rápidas o duración personalizada.
- Las reglas recurrentes detectan solapamientos semanales, también cuando una
  grabación cruza la medianoche o el cambio de domingo a lunes.
- El catálogo muestra cuándo se diagnosticó cada stream y permite filtrar
  resultados antiguos (más de siete días) para volver a comprobarlos.
- Información técnica del stream desde el reproductor y posibilidad de
  activar o pausar reglas recurrentes sin eliminarlas.

### Packaging
- Generadas y verificadas las ediciones ejecutables VIP y Free con
  PyInstaller 6.20, junto con sus paquetes ZIP portables y sumas SHA-256.

## [7.5.7] — 2026-08-22

### Added
- Estado de salud de streams persistente por perfil
  (`core/stream_health_store.py`): el diagnóstico clasifica cada stream como
  estable, lento, caído o restringido, y la lista muestra un indicador de
  color junto al canal sin volver a comprobarlo. Incluido en las copias de
  seguridad.
- Filtro por estado de stream en TV y Radio: nuevo desplegable junto al de
  categoría (Todos · Estables · Con incidencias · Sin diagnosticar) que
  filtra con los resultados ya guardados del diagnóstico — instantáneo, sin
  red.
- Exportación M3U editable (Archivo > Exportar lista M3U…): tabla de vista
  previa antes de guardar, con opción de desmarcar, quitar o editar nombre,
  URL y categoría de cada entrada sin tocar la biblioteca de la app.
- Biblioteca de grabaciones (Archivo > Biblioteca de grabaciones…): lista
  las grabaciones `.mp4` de TV y `.mka` de radio (recientes primero), abre
  con doble clic, abre su carpeta y borra en lote con confirmación,
  limpiando también el `.log` auxiliar de ffmpeg.
- Pantalla de bienvenida: botón «Copiar ID» al portapapeles y enlace que
  abre el correo a soporte con el ID del equipo ya incluido.
- Pantalla de bienvenida: selector de perfil para entrar directamente con
  el perfil elegido (solo si hay más de un perfil creado).
- Arranque directo en modo gratuito: tras elegir «Continuar en modo
  gratuito» una vez, el splash deja de aparecer en cada arranque. Nueva
  entrada Configuración > Activar VIP… para reabrir la activación cuando
  haga falta, con desbloqueo en la misma sesión.

### Changed
- Rendimiento de logos: se eliminó el límite que impedía cargarlos en
  listas grandes; el cargador mantiene una cola con un máximo de ocho
  descargas simultáneas y cada logo repinta solo su fila visible.
- El filtro de problemas del diagnóstico y la limpieza de resultados
  problemáticos actúan también sobre canales lentos y restringidos.
- Al recargar canales o emisoras se reaplica el filtro activo (búsqueda,
  categoría y estado) en vez de mostrar todas las filas.

### Fixed
- Las tarjetas Gratis/VIP del splash no aplicaban su estilo (llaves `}}`
  literales fuera de f-string rompían el parseo del QSS): recuperan fondo,
  borde y esquinas redondeadas.

## [7.5.6] — 2026-08-21

- Búsqueda universal mejorada mediante `Ctrl+K`.
- Búsqueda por nombre, categoría, etiquetas, país y TVG ID.
- Orden por relevancia con contexto de favoritos e historial reciente.
- Resultados recientes disponibles aunque ya no aparezcan en el catálogo actual.
- Mensaje orientativo cuando una consulta no produce resultados.
- Tarjeta «Reproduciendo ahora» en la portada, sincronizada con pausa y reanudación.
- Ventana flotante convertida en mini reproductor más compacto y despejado.
- Corregido el contraste del panel de canales y las celdas vacías de la guía EPG.
- Nuevo diagnóstico concurrente y cancelable de canales y emisoras.
- Informe de estado HTTP, latencia, redirecciones y tipo de contenido, con filtro de problemas.
- Pantalla de bienvenida y activación rediseñada con comparación clara entre Gratis y VIP.
- Información VIP actualizada con conversor MP3, editor, Soulseek, torrents, grabaciones y envío a TV.
- Diagnóstico ampliado con resumen TV/radio, ordenación y exportación CSV segura.

## [7.5.5] — 2026-08-21

- Licencias V2 con firma RSA-2048; la aplicación solo contiene la clave pública.
- Keygen actualizado y clave privada aislada en `tools/license_signing.py`.
- Verificación SHA-256 obligatoria para yt-dlp y slskd antes de ejecutarlos.
- Límites de descarga y extracción para herramientas externas.
- Corregido el campo de activación, que truncaba las licencias V2 a 24 caracteres.
Este archivo se empieza a mantener a partir de la versión 7.2.0 — no hay
trazabilidad fiable de versiones anteriores más allá de lo que ya vive en
el propio código (comentarios de cabecera, `final-residual-fix-report.md`),
así que no se reconstruye aquí para no inventar fechas ni alcance.

## [7.5.4.1] — 2026-08-21

### Added
- Grabación de emisoras de radio: el botón de grabar (compartido con TV)
  ya funciona también mientras suena una emisora. Antes reventaba nada
  más arrancar porque `Recorder.start()` intentaba montar la marca de agua
  de vídeo (`drawtext` + `libx264`) sobre un stream que no tiene ninguna
  pista de vídeo (`core/recorder.py`). Ahora `start()` recibe el tipo
  (`kind="tv"`/`"radio"`) desde `ui/playback_controller.py`; para radio se
  salta el pipeline de vídeo entero (`-vn -c:a copy`, sin marca de agua) y
  el archivo se guarda como `.mka` en vez de `.mp4` — Matroska admite
  copiar el códec de audio que traiga el stream (MP3, AAC, Opus...) sin
  arriesgarse a un contenedor que lo rechace.

## [7.5.4] — 2026-08-21

### Added
- Conversor "Convertir": acepta ahora el máximo de formatos de audio que
  ffmpeg sabe decodificar de forma habitual, además de WAV/FLAC/AIFF —
  Opus, WebM, OGG/OGA, Matroska Audio (.mka), M4A/AAC, WMA, Monkey's Audio
  (.ape), WavPack (.wv), MP2, AC3 y AMR (`core/audio_converter.py`,
  `ui/audio_converter_panel.py`). El filtro del diálogo de selección se
  genera ahora desde `INPUT_EXTENSIONS` en vez de estar hardcodeado, para
  que no se desincronicen. Sin cambios en el comando de conversión (`-vn`
  ya descarta cualquier pista de vídeo si el contenedor la trajera).

## [7.5.3] — 2026-08-20

### Added
- Conversor "Convertir": acepta también `.aif`/`.aiff` como entrada, además
  de WAV/FLAC (`core/audio_converter.py`, `ui/audio_converter_panel.py`) —
  ffmpeg detecta el formato por contenido, no por extensión.
- Listas de filas (Descargas recientes, Convertidos recientes, Podcasts,
  Soulseek, Torrents) con fuente algo más pequeña (`QLabel#mediaRowTitle`,
  10pt → 9pt) y filas más compactas en Soulseek, para que quepan más
  entradas visibles a la vez.

### Fixed
- Pestaña Soulseek: cancelar una descarga (una fila o "Cancelar todas")
  ahora la quita de la lista en el mismo paso, sin el paso aparte de
  "Borrar completadas" que hacía falta antes. `SoulseekClient.cancelar_descarga()`
  pasa `?remove=true` a la API de slskd — cancela y elimina esa
  transferencia concreta en una sola llamada, sin tocar otras descargas ya
  completadas o con error (a diferencia de `limpiar_completadas()`, que
  borra TODAS las transferencias terminadas de golpe).

## [7.5.2] — 2026-08-20

### Added
- Pestaña "Editor MP3": barra de progreso con % real durante "Unir" (antes
  era indeterminada). La duración de cada MP3 se lee al añadirlo
  (`core/mp3_info.probe`, en segundo plano) para poder estimar la
  duración total esperada; ffmpeg reporta avance con `-progress pipe:1`
  (`out_time_ms`) mientras stderr va a un log temporal aparte, en vez de
  a un segundo PIPE (evita el deadlock clásico de leer dos pipes con un
  único hilo lector). Si algún archivo no tiene duración conocida, la
  barra cae a indeterminada en vez de mostrar un % incorrecto.
- Nueva pestaña "Editar info" en Descargas: ver y editar los tags ID3
  (Título/Artista/Álbum/Año/Género/Pista) de uno o varios MP3
  (`core/mp3_info.py`, `ui/mp3_tag_editor_panel.py`). Reescribe el
  archivo con ffmpeg (`-c copy`, remux sin recodificar) y lo reemplaza
  atómicamente. A propósito no usa mutagen (GPL, incompatible con
  enlazarla en una app con licencias de pago) ni ffprobe (no
  empaquetado): lee duración y tags parseando la salida de texto de
  `ffmpeg -i archivo`. Solo en la versión con licencia, como el resto de
  Descargas.

## [7.5.1] — 2026-08-20

### Added
- Nueva pestaña "Convertir" en Descargas: convierte archivos WAV/FLAC a MP3
  (320kbps) con ffmpeg (`core/audio_converter.py`, `ui/audio_converter_panel.py`).
  Selección múltiple de archivos, carpeta de destino configurable, conversión
  secuencial con progreso y cancelación, escritura a temporal + rename
  atómico (mismo patrón que las descargas de yt-dlp).
- Nueva pestaña "Editor MP3" en Descargas: recorta y une varios MP3 en uno
  solo (`core/audio_editor.py`, `ui/mp3_editor_panel.py`), con un
  reproductor de vista previa ligero y propio, solo audio
  (`player/audio_preview.py`, no reutiliza el `VLCPlayer` de vídeo). La
  unión se hace con una sola llamada a ffmpeg: cada segmento se normaliza
  en volumen (`loudnorm`) y se encadena con fundido cruzado (`acrossfade`,
  duración configurable 1–5s) para que no se note ni el corte ni un salto
  de volumen entre pistas.
- Ambas pestañas solo existen en la versión con licencia (viven dentro de
  `DownloadPanel`, que la versión free ya excluye por completo) — no
  afecta a `TDTRadioVIP_Free.spec` ni a `tools/keygen.spec`.

## [7.5.0] — 2026-08-20

### Added
- Nueva pestaña "Soulseek" en Descargas: buscar y descargar archivos de la
  red Soulseek (`core/soulseek_account.py`, `core/soulseek_client.py`,
  `ui/soulseek_panel.py`). Habla por HTTP con `slskd`, un proceso externo
  descargado bajo demanda desde sus releases oficiales (nunca empaquetado
  ni enlazado: es AGPLv3), igual que ya se hace con `yt-dlp.exe`. Incluye
  selección múltiple de resultados, botones "Cancelar" (por descarga) y
  "Cancelar todas", y "Borrar completadas" para limpiar el historial de
  transferencias terminadas.

### Fixed
- Crash silencioso (sin traceback en `app.log`) al cancelar una descarga de
  Soulseek desde su fila: el botón vivía dentro del widget que la propia
  acción destruía al refrescar la lista, así que Qt volvía a un objeto C++
  ya liberado a mitad de su propia señal. Diferido con `QTimer.singleShot`,
  con test de regresión. Como el cierre no pasaba por `closeEvent()`,
  también dejaba `slskd.exe` huérfano — mismo síntoma que el bug ya
  resuelto con ffmpeg, causa distinta.
- `slskd` podía morir en silencio al arrancar (antes de exponer su API
  HTTP) si su puerto P2P fijo por defecto caía dentro de un rango que
  Windows excluye para aplicaciones (típico con Hyper-V/WSL activados) —
  ahora se pasa explícitamente y se varía junto con el puerto HTTP.
- Búsquedas de términos poco comunes en Soulseek se rendían sin resultados
  aunque la red sí los tuviera, por rendirse en cuanto `slskd` marcaba la
  búsqueda como completa sin haber recibido nada todavía.
- Lentitud creciente en el panel de Soulseek cuanto más se usaba la sesión:
  `slskd` no olvida las descargas ya terminadas por su cuenta, así que la
  lista solo crecía y cada refresco (cada 2s) reconstruía cada vez más
  filas — mitigado con el nuevo botón "Borrar completadas".

## [7.4.0] — 2026-08-17

### Changed
- El botón de navegación seleccionado en el raíl (Inicio/TV/Radio/Favoritos/
  Historial/Descargas) usa ahora el color propio de su sección en vez de
  mostrar siempre el acento elegido por el usuario en Configuración —
  Favoritos sigue siendo la única excepción, a propósito. Las tarjetas del
  carrusel de Inicio (TV/Radio) ganan además un tinte de fondo por
  categoría, no solo el borde inferior que ya tenían.
- La sección "Descargas" del raíl deja de compartir color con el botón de
  "Enviar a Chromecast" (ambos usaban turquesa por accidente); Descargas
  pasa a coral.
- Se corrigió de paso una inconsistencia preexistente: el título de
  "Inicio" e "Historial" usaba un verde/violeta ligeramente distinto al de
  su icono y su color de sección; ahora coinciden en toda la interfaz.

### Fixed
- Ampliada la cobertura de pruebas de `core/config.py` (sistema de
  perfiles, localización de ffmpeg/icono empaquetados) y `core/downloader.py`
  (incluida la clase `SearchWorker`, sin cubrir hasta ahora).

## [7.3.0] — 2026-08-15

### Changed
- Motor de torrents: aria2c (proceso externo + JSON-RPC sobre HTTP local)
  sustituido por **libtorrent** (bindings Python, en el propio proceso de
  la app). Ya no hay ningún binario que descargar, empaquetar ni apagar al
  cerrar la app — se instala como cualquier otra dependencia de pip. La
  API pública de `TorrentClient`/`TorrentInfo`/`paquete_disponible()` no
  cambió, así que `ui/torrent_panel.py` no necesitó tocarse salvo textos.
  Verificado con un torrent público real (metadatos, progreso, pares,
  pausar/reanudar/eliminar) además de la suite de tests con mocks.

### Added
- `eliminar(hash_, borrar_archivos=True)` ahora sí borra los archivos ya
  descargados — con aria2c esto quedaba documentado como limitación sin
  implementar; libtorrent lo soporta de forma nativa.

### Fixed
- Eliminada una clase entera de bug: al no haber ya un proceso externo
  (aria2c.exe) para el motor de torrents, no puede quedar huérfano al
  cerrar la app aunque Windows fuerce el cierre a mitad de un apagado.

## [7.2.0] — 2026-08-15

### Added
- Suite de tests para 9 módulos que no tenían cobertura dedicada:
  `core/bootstrap.py`, `core/logger.py`, `core/torrent_history.py`,
  `core/epg_reminders.py`, `core/recording_schedule.py`,
  `core/torrent_client.py`, `core/caster.py`, `core/dlna_caster.py` y el
  resto de `core/downloader.py` (antes solo cubierta la búsqueda
  multi-fuente). Cobertura total de `core`/`ui`/`player`: 48% → 53%.
- `pytest-cov` para medir cobertura real en vez de estimarla a ojo
  (`pytest --cov=core --cov=ui --cov=player --cov-report=term-missing`).
- Integración continua en GitHub Actions para el repo público
  (`tdt_7.2.0_free`): pytest + ruff en cada push/PR a `main`.
- `ruff` como linter del proyecto (`ruff.toml`), reglas conservadoras
  (pyflakes + pycodestyle, sin reordenar imports).
- Sistema de perfiles de usuario (favoritos/historial/canales propios
  independientes por persona en el mismo PC).

### Fixed
- `core/epg_reminders.check_due()` no persistía en disco la limpieza de
  avisos con hora corrupta o ya caducados hace tiempo, salvo que OTRO
  aviso distinto disparara en esa misma llamada — se quedaban
  reapareciendo indefinidamente. Encontrado escribiendo los tests nuevos
  de este módulo, corregido en el propio código.
- Versión Free: "Descargas" y "Enviar a TV" (Chromecast/DLNA) quedaban
  accesibles pese a que la propia app los describe como exclusivos de la
  versión con licencia. Corregido en los 3 puntos de activación
  (`ui/main_window.py`: navegación, botón de cast, paleta de comandos),
  con tests de regresión (`test_visual_contracts.py`).
- `#muteButton` seguía con un color de icono hardcodeado en vez de usar
  el sistema `uiVariant` ya adoptado por el resto de controles con estado.

### Changed
- `CLAUDE.md` corregido: el build real de PyInstaller es `--onedir` (no
  `--onefile`), y la versión Free excluye explícitamente Descargas y
  Chromecast, no "todo desbloqueado" como decía antes la documentación.

### Published
- Código fuente de la versión Free publicado en
  [github.com/xorgsm/tdt_7.2.0_free](https://github.com/xorgsm/tdt_7.2.0_free)
  (excluye `core/license.py`, `tools/keygen.py` y binarios pesados de
  `resources/`).
