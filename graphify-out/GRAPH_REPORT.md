# Graph Report - TDTRadioVIP_v.7.6.2  (2026-08-31)

## Corpus Check
- 3 files · ~125,041 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1999 nodes · 3845 edges · 151 communities (100 shown, 48 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 108 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 147
- Community 148
- Community 149
- Community 150

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 56 edges
2. `VLCPlayer` - 50 edges
3. `write_json_atomic()` - 43 edges
4. `set_visual_state()` - 40 edges
5. `DownloadPanel` - 38 edges
6. `PlaybackController` - 38 edges
7. `Mp3EditorPanel` - 38 edges
8. `get_profile_data_dir()` - 37 edges
9. `set_surface()` - 37 edges
10. `TorrentPanel` - 35 edges

## Surprising Connections (you probably didn't know these)
- `Hardware ID Cache Security Trade-off` --references--> `generate_hardware_id()`  [EXTRACTED]
  CHANGELOG.md → core/license.py
- `list_health()` --references--> `Changelog 7.5.11 Release Notes`  [EXTRACTED]
  core/stream_health_store.py → CHANGELOG.md
- `check_due()` --references--> `Changelog 7.2.0 Release Notes`  [EXTRACTED]
  core/epg_reminders.py → CHANGELOG.md
- `CastDeviceDialog` --uses--> `DLNADiscoveryWorker`  [INFERRED]
  ui/cast_dialog.py → core/dlna_caster.py
- `AudioConverterPanel` --uses--> `AudioConvertWorker`  [INFERRED]
  ui/audio_converter_panel.py → core/audio_converter.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Descargas Audio Tooling Suite (Convertir, Editor MP3, Editar info)** — core_audio_converter, core_audio_editor, core_mp3_info_probe, player_audio_preview, ui_mp3_editor_panel, ui_mp3_tag_editor_panel [EXTRACTED 1.00]
- **Three-Pane Main Panel Layout (Sidebar / Now Playing / Player Bar)** — resources_design_panel_principal_mockup_sidebarchannellist, resources_design_panel_principal_mockup_nowplayingpanel, resources_design_panel_principal_mockup_playercontrolsbar [EXTRACTED 1.00]
- **7.6.2 Release Documentation Set** — changelog_v7_6_2, continuacion_7_6_2_overview, readme_data_privacy [INFERRED 0.85]
- **860x580 Minimum Window Size Consensus** — design_essential_controls_survive_rule, continuacion_7_6_2_verification, product_capabilities_constraints [INFERRED 0.95]

## Communities (151 total, 48 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (74): create_automatic_backup(), export_backup(), import_backup(), datetime, Path, Copia de seguridad de los datos del usuario en un solo archivo. Reúne en un…, Nombre de archivo sugerido para el diálogo de guardar., Crea como máximo una copia por intervalo y aplica retención. (+66 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (28): Torrent Engine Migration: aria2c to libtorrent, Changelog 7.3.0 Release Notes, eliminar(hash_, borrar_archivos=True) (core/torrent_client.py), paquete_disponible(), A diferencia de aria2 (que nunca llegó a borrar los archivos ya descargados al…, Libera la sesión de libtorrent. A diferencia de aria2c.exe antes (proceso…, Antes comprobaba si aria2c.exe venía empaquetado con la app; ahora comprueba si…, TorrentClient (+20 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (54): QRectF, QStyledItemDelegate, _blank(), icon_cast(), icon_download(), icon_favorite(), icon_fullscreen(), icon_grid_view() (+46 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (49): add_scheduled(), check_starts_due(), check_stops_due(), _es_la_misma(), find_conflicts(), has_scheduled(), load_scheduled(), mark_done() (+41 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (28): Evidence on Hand, panel-principal-mockup.png, Carrusel horizontal de tarjetas de canal/emisora, estilo "Recientes" /…, Controlador del menú contextual de canales/emisoras de TDT & Radio VIP:…, Diálogos de la aplicación: preferencias, añadir canal/emisora manual e importar…, Parrilla de programación (guía de TV tipo "qué echan ahora"), a partir de los…, Diálogo "Ecualizador": graves/medios/agudos reales sobre el audio en curso (TV…, Controlador de la página de Inicio de TDT & Radio VIP: sincroniza la tarjeta… (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (15): PlaybackController, QListWidget, QListWidgetItem, Género/tags de Radio-Browser para 'name', o '' si no se encuentra (emisora…, tipo_accent: color de reserva (azul TV / naranja radio) ya puesto por play()…, Pequeño fundido de entrada en el nombre/logo de "reproduciendo ahora" al…, Salta offset_ms hacia adelante (positivo) o atrás (negativo) -- botones ⏪/⏩ de…, Reconecta la emisión actual sin duplicarla en el historial. (+7 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (29): _BITMAPINFOHEADER, _call_com(), _disponible(), _GUID, _guid_from_string(), _hacer_hicon_texto(), _ICONINFO, _MSG (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (21): accent_shades(), _blend(), build_style(), _contrast_ratio(), _hex_to_rgb(), normalize_accent(), Tema oscuro 'Coder By X@R' v2 (navy + dorado) para TDT & Radio VIP., Construye el tema oscuro moderno con los tonos derivados del acento elegido y… (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (28): MP3 Tag Editor Avoids mutagen and ffprobe, Soulseek Cancel-Row Use-After-Free Fix, Soulseek slskd Kept as External Process (AGPLv3), Changelog 7.5.0 Release Notes, Changelog 7.5.2 Release Notes, _parse_probe_output(), probe(), Extrae duración y tags de formato (no de stream) de la salida de 'ffmpeg -i… (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (10): QMainWindow, MainWindow, Sincroniza el indicador visual con la emisión actual., Menú de pistas de audio y subtítulos del stream actual (solo TV: las emisoras…, Configuración > Activar VIP…: reabre el diálogo de activación para quien entró…, Búsqueda global (Ctrl+K / menú Archivo). Las "acciones rápidas" se arman aquí,…, Enruta los mensajes nativos de Windows hacia TaskbarControls, para que los…, Salta a la pestaña de Favoritos y, si se indica una carpeta, la deja… (+2 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (33): Changelog 7.5.11 Release Notes, Changelog 7.5.7 Release Notes, _as_int(), clear_health(), _event_from_result(), get_status(), is_health_stale(), _is_stream() (+25 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (16): Slot, Controlador de carga de catálogo de TDT & Radio VIP: descarga (en segundo…, EpgController, Controlador de la guía de programación (EPG) de TDT & Radio VIP: cargarla en…, Carga, diálogo y sintonía de la guía de programación (XMLTV)., Para el panel "Ahora en antena" de la portada de Inicio: qué está emitiendo…, FetchWorker, process_events_during_shutdown() (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (15): Pestaña "Convertir" dentro del panel de Descargas: convierte archivos de audio…, Panel 'Descargas': pega una URL y descarga el vídeo (MP4) o solo el audio…, Pestaña "Editor MP3" dentro del panel de Descargas: recorta y une varios MP3 en…, Mp3TagEditorPanel, QWidget, Pestaña "Editar info" dentro del panel de Descargas: ver y editar los tags ID3…, Recalcula si 'Guardar' debe estar habilitado a partir de la selección ACTUAL --…, Pestaña "Podcasts" dentro del panel de Descargas: añadir un feed RSS, elegirlo… (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (19): add_feed(), _cache_path_for(), Episode, EpisodeDownloadWorker, _feeds_path(), fetch_episodes(), load_feeds(), PodcastFeed (+11 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (31): add_custom_station(), add_custom_stations(), _cache_path_for(), dedupe_stations(), _failcount_path(), fetch_radio_stations(), filter_hidden(), _hidden_path() (+23 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (9): DownloadPanel, QListWidgetItem, QWidget, Elide la ruta al ancho máximo del label -- una ruta larga sin elidir fuerza el…, Sección de descargas: URL -> vídeo MP4 o audio MP3, vía yt-dlp; búsqueda de…, Espejo de _change_dest, pero disparado desde la pestaña de Torrents — mantiene…, Abre 'path' en el explorador; si es un archivo, lo deja seleccionado., Único punto que decide el estado visual del panel durante una descarga. (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (10): _esta_activa(), _formatear_tamano(), _formatear_velocidad(), QWidget, Una descarga sigue viva (y por tanto se puede cancelar) mientras slskd no la…, Slot del botón "Cancelar" de una fila. NO hace el trabajo aquí: ese botón vive…, Cancela de golpe todas las descargas que sigan vivas. Se pide la lista de nuevo…, Limpia del lado de slskd las descargas que ya no están activas (completadas,… (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (5): _fmt_ms(), Mp3EditorPanel, QWidget, Lee la duración del archivo en segundo plano (ffmpeg -i, ver core/mp3_info.py)…, Duración total esperada del resultado, para poder traducir el progreso de…

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (26): add_custom_channel(), add_custom_channels(), _cache_path_for(), Channel, dedupe_channels(), fetch_tv_channels(), load_custom_channels(), parse_m3u() (+18 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (21): check_for_update(), download_verified_update(), _is_https_url(), Path, Comprobación de actualizaciones "de solo consulta": ni descarga ni reemplaza el…, Descarga a `.part`, verifica SHA-256 y publica el EXE atómicamente., '6.10.2' -> (6, 10, 2). Componentes no numéricos (sufijos tipo '6.4.0-beta') se…, Acepta solo HTTPS absoluto con host, nunca esquemas del sistema. (+13 more)

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (12): AddEntryDialog, ImportPlaylistDialog, QDialog, Añadir (o editar) un único canal de TV o emisora de radio a mano., Importar una lista M3U/M3U8 completa desde una URL o un archivo local., LibraryController, Elimina de inmediato (sin diálogo de confirmación bloqueante) y muestra un…, Borrado por lotes: mismo efecto neto que llamar a delete_custom_entry() una vez… (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (20): delete_folder(), get_folders(), load_favorites(), _path(), Gestión de canales y emisoras marcados como favoritos. Se guardan en un JSON…, Asigna (o quita, con folder='') la carpeta de un favorito ya existente., Persiste 'favorites' tal cual, ya reordenado por quien llama (p. ej. tras…, Los favoritos de esa carpeta no se borran, solo pasan a 'sin carpeta'. (+12 more)

### Community 22 - "Community 22"
Cohesion: 0.13
Nodes (9): ChannelListsController, QListWidget, QListWidgetItem, Pide los logos en tandas pequeñas con QTimer.singleShot(0, ...) en vez de las…, Ordena TV/Radio conservando cada QListWidgetItem y su logo., Poblado, refresco, filtro y búsqueda de las listas de canales., Llamado tras arrastrar una fila en la pestaña de Favoritos…, "Ahora: <programa>" para el mini-EPG de cada fila de la lista de TV, o "" si no… (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.15
Nodes (3): AudioConverterPanel, QWidget, dest_dir: carpeta donde se guardan los MP3 convertidos.

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (10): QWidget, RadioHeroWidget, Llamado desde PlaybackController.play() al arrancar una emisora., Llamado desde VLCPlayer.meta_changed -- '' significa 'sin dato'., Nota musical dorada -- mismo lenguaje visual que el resto de la app cuando no…, Sustituye al ecualizador "a pelo" en player_stack cuando suena radio. Contiene…, EqualizerWidget, QWidget (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.13
Nodes (14): _describe_device(), discover_dlna_devices(), DLNADevice, DLNASession, _escape_xml(), Envío de contenido (canal/emisora en directo, o archivo local) a un televisor…, Busca renderizadores DLNA en la red local y devuelve los que exponen…, Conexión activa con un renderizador DLNA y control de qué se le envía. (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.15
Nodes (13): normalize(), Motor independiente de Qt para la búsqueda universal de la aplicación., Busca por nombre, categoría, país, etiquetas y TVG ID, ordenando por relevancia., search_catalog(), test_normalize_ignores_case_accents_and_extra_spaces(), test_search_deduplicates_catalog_and_history_by_kind_and_name(), test_search_keeps_recent_item_missing_from_catalog(), test_search_matches_metadata_and_prioritizes_favorites() (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.16
Nodes (9): QFrame, QStackedWidget, QVBoxLayout, QWidget, QListWidget, Línea vertical fina entre grupos de botones de control. Antes todos los botones…, Barra de título propia. Antes esto se montaba con los 'corner widgets' de…, Portada de bienvenida: accesos rápidos a TV/Radio, y un vistazo a lo último… (+1 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (14): AudioEditWorker, build_join_command(), estimated_output_seconds(), _parse_out_time_ms(), QThread, Unión de varios MP3 (con recorte opcional de cada uno) en un solo MP3, con…, Mensaje de error si algún segmento tiene el fin marcado antes (o igual) que el…, Duración aproximada del resultado: suma de cada segmento menos el tramo que… (+6 more)

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (3): QFrame, Reproductor de streams. Si libVLC no puede cargarse, el widget sigue existiendo…, VLCPlayer

### Community 30 - "Community 30"
Cohesion: 0.13
Nodes (14): _configurar_raiz(), get_logger(), log_file_path(), Logging centralizado a disco. Hasta ahora, casi todos los fallos de zonas…, Configura el logger raíz una sola vez, la primera vez que algo pide un logger.…, Logger con el nombre del módulo que lo pide (típicamente __name__)., Ruta del archivo de log actual, para mostrarla en la UI (p. ej. un botón "Abrir…, _estado_legible() (+6 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (10): _normalise_stream(), _public_stream(), Path, Registra un resultado y devuelve el estado actualizado. ``kind`` normalmente es…, Registra un lote de resultados válidos y devuelve sus estados., Devuelve el estado de un stream o ``None`` si no se ha medido., Lista estados, con los comprobados más recientemente primero., Elimina estados y devuelve cuántos streams se han retirado. (+2 more)

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (4): M3UEditorDialog, Path, Editor visual para revisar una lista M3U antes de exportarla., Abre el editor visual de listas personales M3U.

### Community 33 - "Community 33"
Cohesion: 0.20
Nodes (17): Hardware ID Cache Security Trade-off, Changelog 7.6.1 Release Notes, generate_hardware_id(), _get_board_uuid(), _get_cpu_id(), _get_disk_serial(), _get_machine_guid(), _hardware_id_cache_path() (+9 more)

### Community 34 - "Community 34"
Cohesion: 0.12
Nodes (13): Radio Recording kind Dispatch Fix, Changelog 7.5.4.1 Release Notes, Grabación de streams en curso mediante ffmpeg. Usa el ffmpeg empaquetado con la…, Recorder.start() (core/recorder.py), Controlador de reproducción de TDT & Radio VIP. Extraído de ui/main_window.py…, QFrame, QWidget, Aviso flotante anclado a la esquina inferior de `parent`. (+5 more)

### Community 35 - "Community 35"
Cohesion: 0.16
Nodes (16): get_font_path(), get_icon_path(), Ruta al icono de la app (resources/icon.ico), empaquetado con el EXE o presente…, Ruta a la tipografía Inter empaquetada (resources/fonts/Inter-Variable.ttf), o…, main(), TDT & Radio VIP - Versión FREE COMPLETA Coder By X@R Arranca directamente sin…, Comprobación temprana, antes de crear la ventana principal: ¿hay VLC…, vlc_disponible_al_arrancar() (+8 more)

### Community 36 - "Community 36"
Cohesion: 0.18
Nodes (16): Path, Lectura y escritura segura de los pequeños almacenes JSON de la app., Intenta limpiar un artefacto sin ocultar la excepción en curso., Carga JSON o devuelve ``default`` si falta, está corrupto o es ilegible., Escribe ``value`` en ``path`` sin exponer nunca un JSON parcial., Sustituye varios JSON como una única transacción con rollback., read_json(), replace_json_files_atomically() (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.19
Nodes (3): Cancela Y elimina esa transferencia concreta en una sola llamada (?remove=true)…, Borra del lado de slskd las descargas ya terminadas (completadas, canceladas,…, SoulseekClient

### Community 38 - "Community 38"
Cohesion: 0.12
Nodes (3): AudioPreviewPlayer, Reproductor de audio mínimo: cargar un archivo, reproducir/pausar, y leer/mover…, QObject

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (9): QFormLayout, _NuevaReglaDialog, QDialog, Lista las reglas existentes, con botones para añadir/eliminar., Formulario para dar de alta una regla nueva., RecurringRecordingsDialog, _CuentaSoulseekDialog, QDialog (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.14
Nodes (8): Changelog 7.4.0 Release Notes, QThread, Fuerza (bajo demanda) una comprobación de actualización de yt-dlp.exe., Busca música por título/artista en segundo plano (ver SEARCH_SOURCES más…, SearchWorker, UpdateCheckWorker, The Functional Color Rule, Navigation Rail Component

### Community 41 - "Community 41"
Cohesion: 0.15
Nodes (10): Changelog 7.5.1 Release Notes, AudioConvertWorker, _build_command(), build_output_path(), QThread, Conversión de archivos de audio a MP3 (320kbps) mediante ffmpeg.…, Nombre de salida en dest_dir a partir del nombre del archivo de entrada, sin…, Convierte una lista de archivos WAV/FLAC a MP3, uno a uno. Señales:… (+2 more)

### Community 42 - "Community 42"
Cohesion: 0.14
Nodes (7): CastSession, _local_lan_ip(), LocalFileServer, Servidor HTTP en segundo plano para exponer un archivo local en la red, de…, Arranca el servidor para 'filepath'. Devuelve (url_lan, content_type)., Conexión activa con un Chromecast/TV y control de qué se le envía., IP de este PC en la red local (la que la TV puede alcanzar; no 127.0.0.1).

### Community 43 - "Community 43"
Cohesion: 0.22
Nodes (12): _build_search_command(), ensure_yt_dlp(), _last_check_file(), mark_update_checked(), _parse_search_line(), Descarga de vídeos por URL: vídeo (MP4) o solo audio (MP3). Se usa el…, Devuelve la ruta a yt-dlp.exe, descargándolo la primera vez si hace falta. Se…, Pide a yt-dlp que se autoactualice ('yt-dlp -U'). Si no hay red o falla, no es… (+4 more)

### Community 44 - "Community 44"
Cohesion: 0.17
Nodes (8): _escape_drawtext(), Path, Últimas líneas del log de ffmpeg, para mostrar en el aviso de error., Comprueba si ffmpeg ya ha muerto -- pensada para llamarse desde un QTimer un…, Espera a que el proceso termine sin un único communicate()/wait() bloqueante…, Detiene la grabación pidiéndole a ffmpeg que cierre limpiamente ('q'), de forma…, Escapa los caracteres que el propio filtro drawtext de ffmpeg interpreta como…, Recorder

### Community 45 - "Community 45"
Cohesion: 0.15
Nodes (8): QAbstractNativeEventFilter, _disponible(), _HotkeyFilter, _MSG, Atajos de teclado multimedia del sistema: play/pausa, siguiente, anterior y…, Estructura MSG de Win32. ctypes.wintypes no la incluye en todas las versiones…, Registra las teclas multimedia del teclado como atajos globales de Windows.…, SystemMediaKeys

### Community 46 - "Community 46"
Cohesion: 0.17
Nodes (7): GroupsSidebar, QWidget, Panel lateral de grupos/categorías del catálogo de TV: lista cada group-title…, Selecciona por nombre desde fuera (p.ej. al restaurar un filtro guardado)., Grupos seleccionados ahora mismo (None = "(Todos)"). Público para que quien…, Panel de grupos de TV, con contador de canales por grupo., Repuebla la lista a partir de {nombre_de_grupo: nº_canales}. Conserva la…

### Community 47 - "Community 47"
Cohesion: 0.32
Nodes (7): QComboBox, _header(), _panel(), QFrame, QVBoxLayout, tv_datos / radio_datos: {"custom": [Channel/Station...], "public":…, Panel con textura (mismo lenguaje visual que la barra de reproducción) y una…

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (7): HomeController, Reproduce una tarjeta de los carruseles de Inicio (Recientes o Recomendado para…, Heurística de "Recomendado para ti" sin necesidad de trackear nada nuevo: el…, Refresco y comportamiento de la página de Inicio., Sincroniza la tarjeta de portada con el reproductor real., Puebla los carruseles de 'Recientes' y 'Recomendado para ti', y la lista de…, Muestra un resumen claro de los últimos diagnósticos guardados.

### Community 49 - "Community 49"
Cohesion: 0.23
Nodes (4): QueueController, Gestiona la cola "Reproduciendo a continuación" de MainWindow., Añade un canal/emisora al final de la cola., Reproduce y saca de la cola el primer elemento pendiente. Devuelve True si…

### Community 50 - "Community 50"
Cohesion: 0.19
Nodes (8): get_ffmpeg_dir(), Carpeta del ffmpeg empaquetado con la app, o None si no viaja incluido. Al…, DownloadWorker, _fmt_eta(), _fmt_velocidad(), _num(), Descarga una URL en segundo plano usando yt-dlp.exe (externo,…, Convierte un campo de yt-dlp a float, o None si viene vacío/'NA'/'None'.

### Community 51 - "Community 51"
Cohesion: 0.18
Nodes (6): ChannelMenuController, QListWidget, Menú contextual de listas de canales/emisoras y borrado de grupos., Oculta un canal público desde su menú contextual, de forma reversible., Elimina de golpe todos los canales de uno o varios grupos, desde el menú…, Atajos a nivel de ventana. Con keyPressEvent no bastaba: si el foco estaba en…

### Community 52 - "Community 52"
Cohesion: 0.23
Nodes (5): _MosaicTile, QWidget, Paso 1 del diálogo: elegir hasta MAX_TILES canales de TV., Un canal dentro del mosaico: vídeo + nombre, con borde resaltado cuando tiene…, _SelectorCanales

### Community 53 - "Community 53"
Cohesion: 0.21
Nodes (11): bootstrap(), prepare_bundled_vlc(), Arranque común a los distintos puntos de entrada (main.py, main_free.py). Antes…, Fija el AppUserModelID de Windows para este proceso. Sin esto, Windows a veces…, Prepara el entorno para que python-vlc encuentre libvlc y sus plugins cuando…, Atajo para las dos llamadas anteriores, en el orden correcto., set_app_user_model_id(), main() (+3 more)

### Community 54 - "Community 54"
Cohesion: 0.21
Nodes (12): filter_hidden(), _hidden_path(), hide_channels(), load_hidden_channel_names(), Añade nombres a la lista de ocultos. Devuelve cuántos son nuevos (nombres ya…, Quita nombres de la lista de ocultos (los vuelve a mostrar)., Quita de `channels` los que estén en la lista de ocultos., _save_hidden() (+4 more)

### Community 55 - "Community 55"
Cohesion: 0.21
Nodes (7): derive_health_status(), Persiste un lote de resultados del diagnóstico en el perfil activo., Clasifica un resultado de :func:`core.stream_health.probe_stream`. Las…, record_results(), HealthStatus, QDialog, StreamDiagnosticsDialog

### Community 56 - "Community 56"
Cohesion: 0.19
Nodes (6): Mismo chequeo tardío que PlaybackController._check_recording_alive (ver ese…, Aviso de bandeja genérico y reutilizable (en Windows 10/11, Qt lo muestra como…, Bandeja del sistema, avisos EPG y grabaciones programadas., Icono de bandeja del sistema para poder avisar de un programa marcado en la…, Arranca/para grabaciones programadas desde la guía EPG (ver ui/epg_dialog.py,…, TrayReminderController

### Community 57 - "Community 57"
Cohesion: 0.18
Nodes (12): Changelog 7.5.8 Release Notes, Creative North Star: La Cabina Nocturna, Inter Typography System, Midnight Naval Neutral Palette, The One Family Rule, Signal Gold Accent (configurable), The Signal, Not Wallpaper Rule, Brand Commitments (+4 more)

### Community 58 - "Community 58"
Cohesion: 0.38
Nodes (11): add_reminder(), check_due(), has_reminder(), load_reminders(), _path(), Avisos de "empieza ahora" para programas de la parrilla EPG. Se guarda una…, Añade un aviso si no existía ya uno igual (mismo canal+programa+hora)., Devuelve los avisos cuya hora de inicio ya llegó (y no ha pasado tanto tiempo… (+3 more)

### Community 59 - "Community 59"
Cohesion: 0.26
Nodes (9): _attribute(), build_m3u(), export_m3u(), Path, Exportación segura de canales y emisoras a listas M3U compatibles., Guarda una lista M3U y devuelve el número de streams exportados., Devuelve una lista M3U UTF-8 a partir de entradas de TV o radio. Se ignoran…, test_build_m3u_preserves_compatible_metadata_and_skips_incomplete_entries() (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.29
Nodes (10): ensure_slskd(), _extraer_zip_seguro(), Path, Cliente de Soulseek -- vía slskd, un proceso externo (nunca empaquetado ni…, Busca slskd.exe ya extraído, en cualquier profundidad -- el zip oficial lo trae…, Como ZipFile.extractall(), pero rechaza cualquier entrada que intente escapar…, Devuelve la ruta a slskd.exe, descargándolo la primera vez si hace falta. A…, _slskd_dir() (+2 more)

### Community 61 - "Community 61"
Cohesion: 0.29
Nodes (11): add_entry(), clear_history(), has_entry(), load_history(), _path(), Historial persistente de torrents completados. libtorrent (igual que aria2…, Devuelve el historial guardado, del más reciente al más antiguo., Registra un torrent completado al principio del historial. Si ese mismo… (+3 more)

### Community 62 - "Community 62"
Cohesion: 0.21
Nodes (5): CastDeviceDialog, QDialog, Al cerrarse el diálogo, desconecta las señales de los hilos de búsqueda. Sin…, Libera el explorador zeroconf de Chromecast y espera a que ambos hilos de…, Busca dispositivos Google Cast y DLNA, y deja elegir uno para enviar contenido.

### Community 63 - "Community 63"
Cohesion: 0.29
Nodes (10): add_entry(), clear_history(), load_history(), _path(), Historial de lo último reproducido. Cada entrada es un diccionario con: type…, Devuelve el historial guardado, del más reciente al más antiguo., Registra una reproducción al principio del historial y devuelve la lista…, Devuelve las entradas más reproducidas (por play_count, de mayor a menor), para… (+2 more)

### Community 64 - "Community 64"
Cohesion: 0.20
Nodes (10): is_activated(), _license_path(), load_activation(), Path, Verifica una licencia V2 usando solo la clave pública RSA., Devuelve {'activated': bool, 'code': str}. Valida tipos, no solo que el JSON…, Valida el código contra el hardware de este PC y, si es correcto, lo guarda en…, Comprueba si la app está activada en este PC. Revalida el código guardado… (+2 more)

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (6): build_write_tags_command(), Mp3TagWriteWorker, QThread, Lectura y escritura de metadatos (tags ID3) y duración de archivos MP3, vía…, tags: {clave_ffmpeg: valor}. Una clave ausente o con valor vacío borra ese tag…, Reescribe los tags de un único MP3 (remux con -c copy) y lo deja en el mismo…

### Community 66 - "Community 66"
Cohesion: 0.22
Nodes (6): Carousel, CarouselCard, QFrame, QWidget, Tarjeta compacta clicable: logo arriba, nombre y tipo debajo., Fila horizontal de CarouselCard con scroll propio y mensaje vacío.

### Community 67 - "Community 67"
Cohesion: 0.25
Nodes (3): CatalogLoadController, Muestra el total del catálogo solo durante la exploración., Carga de canales de TV/radio y diagnóstico automático de streams.

### Community 69 - "Community 69"
Cohesion: 0.29
Nodes (3): EqualizerDialog, QDialog, Ecualizador de audio real (graves/medios/agudos) para TV y radio.

### Community 70 - "Community 70"
Cohesion: 0.29
Nodes (4): BaseHTTPRequestHandler, Devuelve (inicio, fin) inclusivos, o None si no hay Range utilizable., Handler HTTP que sirve un único archivo local con soporte real de rangos (HTTP…, _SingleFileHandler

### Community 71 - "Community 71"
Cohesion: 0.24
Nodes (7): guess_stream_content_type(), pychromecast_available(), Envío de contenido (canal/emisora en directo o archivo descargado) a…, Antes esto era una constante calculada al cargar el módulo…, Adivina el content-type para un canal/emisora en directo a partir de la URL., Controlador de envío a la TV (Chromecast / Google Cast / DLNA) de TDT & Radio…, Diálogo 'Enviar a la TV': busca Chromecasts / TVs con Google Cast Y televisores…

### Community 72 - "Community 72"
Cohesion: 0.29
Nodes (8): list_recordings(), Path, Utilidades para mostrar de forma segura las grabaciones del usuario., Metadatos mínimos de una grabación que ya terminó de escribirse., Devuelve los archivos de grabación, recientes primero. Los logs auxiliares de…, RecordingFile, test_list_recordings_only_returns_supported_media_newest_first(), test_list_recordings_treats_missing_directory_as_empty()

### Community 73 - "Community 73"
Cohesion: 0.20
Nodes (5): Activa o desactiva la pista de vídeo del stream actual sin tocar el audio --…, Recorre la lista enlazada en C y la libera con…, Lista de (id, nombre) de pistas de audio disponibles en el stream actual., Lista de (id, nombre) de pistas de vídeo disponibles en el stream actual., Lista de (id, nombre) de pistas de subtítulos disponibles (-1 = 'Desactivados').

### Community 74 - "Community 74"
Cohesion: 0.38
Nodes (3): ManageChannelsDialog, Gestión de canales/emisoras en tres ámbitos, elegibles con un combo: -…, Abre el gestor de canales/emisoras en sus tres ámbitos: borrar personalizados…

### Community 75 - "Community 75"
Cohesion: 0.29
Nodes (3): Biblioteca local de grabaciones sin modificar el catálogo de canales., RecordingsLibraryDialog, Abre la biblioteca local usando la carpeta configurada actualmente.

### Community 76 - "Community 76"
Cohesion: 0.33
Nodes (4): LibrarySidebar, QListWidgetItem, QWidget, Panel de biblioteca: Recientes + Playlists (carpetas de favoritos).

### Community 77 - "Community 77"
Cohesion: 0.22
Nodes (4): _EnsureWorker, QThread, Descargar slskd (si falta) y arrancarlo puede tardar -- en un hilo aparte para…, _SearchWorker

### Community 78 - "Community 78"
Cohesion: 0.22
Nodes (3): ActiveWorkerRegistry, Mantiene referencias fuertes a los FetchWorker activos de la app., Registra y arranca un worker como una sola transición de cierre.

### Community 79 - "Community 79"
Cohesion: 0.36
Nodes (3): MosaicView, QDialog, Diálogo de multivista: selector de canales, luego mosaico 2x2.

### Community 80 - "Community 80"
Cohesion: 0.22
Nodes (6): _HWWorker, QDialog, QThread, Obtiene el hardware ID en segundo plano (las llamadas a WMIC tardan)., Diálogo de bienvenida / activación. Resultado: self.activated -> bool: True si…, SplashDialog

### Community 81 - "Community 81"
Cohesion: 0.36
Nodes (5): LogoLoader, QPixmap, Descarga logos de canales/emisoras en segundo plano y los cachea en disco, con…, Recorta y redondea un pixmap para usarlo como miniatura de tarjeta., rounded_pixmap()

### Community 82 - "Community 82"
Cohesion: 0.25
Nodes (8): Backup Import Size Limit and Future-Date Fix, Profile Names Compared Case-Insensitively, Update Checker HTTPS/Host Validation, Changelog 7.6.2 Release Notes, APP_VERSION / MyAppVersion set to 7.6.2, TDTRadioVIP 7.6.2 Continuation Notes, Accessibility & Inclusion, requests dependency

### Community 83 - "Community 83"
Cohesion: 0.25
Nodes (6): XMLTV Timezone Handling Fix, Fast Channel Switch Race Condition Fix, Changelog 7.5.9 Release Notes, VLC Equalizer Native Memory Leak Fix, README Development Setup, python-vlc dependency

### Community 84 - "Community 84"
Cohesion: 0.29
Nodes (8): Category Filter Tabs (Todos/Musica/Noticias/Deportes), Dark Navy + Gold Accent Theme, Live Indicator Badge (EN DIRECTO), Main Panel Mockup (TDT Radio VIP), Now Playing Panel (Reproduciendo ahora), Bottom Player Controls Bar, Channel Search Bar (Buscar canal...), Sidebar Channel List

### Community 85 - "Community 85"
Cohesion: 0.39
Nodes (3): CastController, Selección de dispositivo y envío de la reproducción actual o un archivo local a…, Sesión de casting con un dispositivo conectado ahora mismo, o None.

### Community 86 - "Community 86"
Cohesion: 0.29
Nodes (7): Continuous Integration (pytest + ruff on GitHub Actions), Free Edition Feature Gating Fix (Downloads/Cast), User Profile System, Public Free Edition Source Repo (tdt_7.2.0_free), Changelog 7.2.0 Release Notes, pychromecast dependency, test_visual_contracts.py

### Community 87 - "Community 87"
Cohesion: 0.38
Nodes (7): 7.6.2 Verification Pass (103 tests, ruff clean, 860x580), The Essential Controls Survive Rule, Capabilities and Constraints, README Verification Steps, pytest dependency, ruff dependency, PySide6 dependency

### Community 88 - "Community 88"
Cohesion: 0.29
Nodes (4): CastDiscoveryWorker, QThread, Busca Chromecasts / TVs con Google Cast en la red local (Wi-Fi/LAN)., Cierra el explorador zeroconf. Es idempotente: puede llamarse varias veces sin…

### Community 89 - "Community 89"
Cohesion: 0.38
Nodes (7): _failcount_path(), _load_failcounts(), Suma un fallo consecutivo para ese canal y devuelve el total acumulado., Se llama cuando el canal responde bien -- limpia su contador si tenía alguno., record_channel_failure(), reset_channel_failures(), _save_failcounts()

### Community 90 - "Community 90"
Cohesion: 0.43
Nodes (6): Solo se acepta una URL http(s) explícita con host. yt-dlp interpreta cualquier…, url_valida_para_descarga(), parametrize, test_construir_comando_uses_double_dash_separator_before_url(), test_non_http_or_flag_like_values_are_rejected(), test_valid_http_urls_are_accepted()

### Community 93 - "Community 93"
Cohesion: 0.29
Nodes (3): Activa (o actualiza, si ya estaba activo) el ecualizador con esta…, Desactiva el ecualizador: deja pasar la señal de audio sin procesar., AudioEqualizer no tiene __del__ (confirmado en python-vlc): hay que llamar a…

### Community 94 - "Community 94"
Cohesion: 0.29
Nodes (3): ExportPlaylistDialog, Vista previa editable antes de exportar TV y radio como M3U., Exporta la biblioteca elegida (o ambas, por compatibilidad) a M3U.

### Community 95 - "Community 95"
Cohesion: 0.29
Nodes (3): Comprobación manual de actualizaciones y descarga verificada del instalador., Comprobación manual desde Ayuda > Buscar actualizaciones. Solo avisa y ofrece…, UpdateCheckController

### Community 96 - "Community 96"
Cohesion: 0.33
Nodes (3): DLNADiscoveryWorker, QThread, Busca TV/renderizadores DLNA en la red local (Wi-Fi/LAN), en un hilo aparte.

### Community 97 - "Community 97"
Cohesion: 0.33
Nodes (6): README Build Process, pyinstaller dependency, setup_license.py, TDTRadioVIP_Free.spec, TDTRadioVIP_Setup.iss, TDTRadioVIP.spec

### Community 98 - "Community 98"
Cohesion: 0.47
Nodes (3): _format_xmltv(), QDialog, ScheduledRecordingsDialog

### Community 99 - "Community 99"
Cohesion: 0.40
Nodes (4): QDialog, Se abre desde Ayuda > Estadísticas de uso. Solo lectura., Devuelve (item, widget): widget se asigna con setItemWidget() en el sitio donde…, StatsDialog

### Community 100 - "Community 100"
Cohesion: 0.40
Nodes (3): country_name(), Lista de países soportados para canales de TV (iptv-org) y emisoras de radio…, Nombre en español de un código, o el propio código si no está en la lista.

### Community 101 - "Community 101"
Cohesion: 0.50
Nodes (3): QColor, QGraphicsDropShadowEffect, Halo de color alrededor de un botón, vía QGraphicsDropShadowEffect (esto sí…

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): APP_DATA_NAME shared across 7.6.x branch (TDTRadioVIP_7.6.0), Source ZIP Packaging Exclusions, README Data & Privacy Notes

## Ambiguous Edges - Review These
- `SoulseekClient.cancelar_descarga() (core/soulseek_client.py)` → `Soulseek Cancel-Row Use-After-Free Fix`  [AMBIGUOUS]
  CHANGELOG.md · relation: references

## Knowledge Gaps
- **54 isolated node(s):** `_THUMBBUTTON`, `Recorder.start() (core/recorder.py)`, `Changelog 7.5.4.1 Release Notes`, `setup_license.py`, `TDTRadioVIP_Free.spec` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 782 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `SoulseekClient.cancelar_descarga() (core/soulseek_client.py)` and `Soulseek Cancel-Row Use-After-Free Fix`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `VLCPlayer` connect `Community 29` to `Community 4`, `Community 104`, `Community 73`, `Community 106`, `Community 107`, `Community 108`, `Community 109`, `Community 110`, `Community 111`, `Community 52`, `Community 91`, `Community 92`, `Community 93`, `Community 30`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `DownloadPanel` connect `Community 15` to `Community 1`, `Community 40`, `Community 12`, `Community 13`, `Community 16`, `Community 17`, `Community 50`, `Community 23`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `Community 9` to `Community 35`, `Community 4`, `Community 101`, `Community 102`, `Community 48`, `Community 112`, `Community 114`, `Community 51`, `Community 115`, `Community 53`, `Community 116`, `Community 27`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `MainWindow` (e.g. with `ChannelMenuController` and `HomeController`) actually correct?**
  _`MainWindow` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DownloadPanel` (e.g. with `DownloadWorker` and `SearchWorker`) actually correct?**
  _`DownloadPanel` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_THUMBBUTTON`, `Recorder.start() (core/recorder.py)`, `Changelog 7.5.4.1 Release Notes` to the rest of the system?**
  _54 weakly-connected nodes found - possible documentation gaps or missing edges._