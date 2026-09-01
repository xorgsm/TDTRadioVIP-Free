# Changelog — TDT & Radio VIP (Coder By X@R)

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [7.6.2] \u2014 En desarrollo

### Fixed
- La comprobación de actualizaciones rechaza enlaces que no sean HTTPS con
  host y versiones remotas desmesuradas, evitando abrir esquemas locales del
  sistema o romper el hilo ante un manifiesto manipulado.
- Las copias automáticas ya no quedan desactivadas indefinidamente por un
  archivo con fecha futura, ignoran directorios con apariencia de backup y
  evitan reescribir dos copias creadas en el mismo segundo. La importación
  también limita el tamaño antes de cargar el JSON en memoria.
- Los nombres de perfil ahora se comparan sin distinguir may\u00fasculas,
  igual que hace Windows con las carpetas. Esto impide que duplicar o
  renombrar `Familia` como `familia` opere sobre el mismo directorio y pueda
  mezclar o eliminar datos; la graf\u00eda original tambi\u00e9n se recupera al
  cargar el perfil activo.

### Changed
- Interfaz principal refinada: navegación activa sobre una superficie común
  con acento contextual, iconografía vectorial coherente y foco de teclado
  visible en botones, búsqueda y filtros.
- La portada y la barra "Ahora suena" adaptan su composición a ventanas
  estrechas sin solapar controles ni provocar desplazamiento horizontal.
- Los controles de reproducción dejan de depender de glifos Unicode y exponen
  nombres accesibles para tecnologías de asistencia.

## [7.6.1] \u2014 En desarrollo

### Fixed
- Al eliminar un grupo de Televisi\u00f3n desde el panel GRUPOS, los canales
  personalizados (importados a mano) de ese grupo volv\u00edan a aparecer al
  reabrir la app -- el borrado de grupos usaba siempre el mecanismo de
  "ocultar por nombre" pensado solo para la lista p\u00fablica, que nunca se
  aplica a los canales personalizados al recargarlos. Ahora los canales
  personalizados del grupo se borran de verdad y los p\u00fablicos se siguen
  ocultando como antes (reversible desde Archivo > Gestionar canales
  personalizados > Ocultados).
- Arranque mucho m\u00e1s r\u00e1pido: el c\u00e1lculo del ID de hardware (licencia)
  lanzaba WMIC y hasta tres procesos `powershell.exe` en cadena, uno tras
  otro; medido en una m\u00e1quina real lleg\u00f3 a tardar 4m35s en un solo
  arranque. Ahora los tres componentes se lanzan en paralelo (peor caso
  ~3s en vez de la suma de los tres) y, sobre todo, el resultado se
  guarda en disco (`hardware_id_cache.json`) para no volver a lanzar
  ning\u00fan proceso en arranques posteriores.
- Los botones de la barra "en reproducci\u00f3n" (favorito, cast, stop,
  retroceder/avanzar, grabar, silenciar, m\u00e1s opciones) se solapaban y se
  ve\u00edan cortados en ventanas estrechas; reducidos de 32px/46px a
  26px/38px con sus iconos y espaciados ajustados en proporci\u00f3n.

### Security
- El ID de hardware cacheado en disco es editable por cualquiera con
  acceso de escritura al perfil de la app, lo que en teor\u00eda permite
  clonar una activaci\u00f3n a otro PC copiando ese archivo junto con un
  c\u00f3digo de licencia v\u00e1lido. Riesgo aceptado deliberadamente a cambio de
  eliminar minutos de espera en cada arranque -- ver el docstring de
  `generate_hardware_id()` en `core/license.py`.

## [7.6.0] \u2014 En desarrollo

### Changed
- Nueva rama de desarrollo independiente de 7.5.11. La versión 7.6.0 usa
  su propia carpeta de datos y puede probarse sin modificar la versión anterior.
- El Editor M3U de la edición Free permite cargar HTTP(S) o archivos locales,
  editar, eliminar grupos completos, detectar duplicados y comprobar streams.

### Security
- Los nombres de perfil se validan en todas las operaciones para impedir que
  rutas manipuladas salgan de la carpeta de perfiles.

## [7.5.11] \u2014 En desarrollo

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

## [7.5.10] \u2014 En desarrollo

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
