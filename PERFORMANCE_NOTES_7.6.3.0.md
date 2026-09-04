# Registro técnico de rendimiento — 7.6.3.0

Fecha de apertura: 2026-09-04  
Base: `7.6.2.2`  
Objetivo: que la aplicación siga respondiendo al trabajar con cientos o miles
de canales/emisoras.

## Diagnóstico inicial

La revisión se centró en los caminos que se ejecutan al cargar, cambiar de
pestaña, buscar, refrescar EPG, pedir logos y comprobar la salud de streams.

Problemas encontrados en la base anterior:

- El diálogo de diagnóstico insertaba una fila y volvía a recorrer todos los
  resultados por cada respuesta. Además, el historial JSON se leía y escribía
  una vez por resultado. En una prueba sintética del almacén, registrar 100,
  200 y 400 resultados tardó aproximadamente 1,365 s, 3,563 s y 10,952 s:
  crecimiento cuadrático provocado por E/S repetida.
- Al poblar una lista se solicitaban logos para todo el catálogo. Aunque la
  descarga estaba limitada, la decodificación de la caché de disco ocurría en
  el hilo de interfaz y la caché en memoria no tenía límite.
- Cargar una M3U desde URL/archivo y parsearla ocurría en el hilo de interfaz.
  La tabla se rellenaba fila a fila sin reservar previamente sus filas.
- Filtrar una lista recorría todos sus elementos en cada pulsación. El orden
  de origen reconstruía innecesariamente toda la `QListWidget`, que es el modo
  predeterminado.
- La selección de streams antiguos llamaba a `get()` para cada entrada y
  releía el mismo JSON repetidamente.
- El diagnóstico creaba un `Future` por entrada, incluso cuando el catálogo
  era mucho mayor que el número de workers.
- Una segunda carga de TV o radio podía terminar después de una carga más
  reciente y sobrescribirla con datos antiguos.
- Se detectaron también dos fallos funcionales: `unhide` llamaba métodos ya
  extraídos de `MainWindow`, y el diálogo usaba un generador en
  `setEnabled()`.

## Cambios aplicados

### Núcleo y segundo plano

- `core/stream_health_store.py`
  - `record_results()` procesa el lote en memoria y hace una sola escritura
    atómica al terminar.
  - `select_stale_entries()` carga el historial una vez y usa un índice por
    `(kind, url)`.
- `core/stream_health.py`
  - `diagnose_catalog()` mantiene solo hasta `max_workers` tareas pendientes,
    repone cada tarea al completar otra y cancela la cola al cerrar.
- `ui/catalog_load_controller.py`
  - cancela el worker anterior de TV/radio y usa un contador de generación
    para ignorar respuestas tardías.
- `ui/library_controller.py`
  - `unhide_entries()` llama a `win.catalog.load_tv_channels()` o
    `win.catalog.load_radio_stations()`.

### Interfaz y catálogos

- `ui/stream_diagnostics_dialog.py`
  - reserva las filas de la tabla, mantiene contadores incrementales y solo
    oculta la fila que acaba de llegar; al cancelar recorta las filas no
    utilizadas.
  - persiste el lote completo una sola vez y corrige el estado del botón de
    eliminación.
- `ui/dialogs.py`
  - mueve lectura HTTP/local y parseo M3U a `FetchWorker`.
  - rellena la tabla con `setRowCount()` y pausa actualizaciones mientras se
    construye; el buscador aplica filtro tras 150 ms sin pulsaciones.
- `ui/main_window.py`
  - activa `setUniformItemSizes(True)` y carga logos al desplazarse por la
    lista visible.
- `ui/channel_lists_controller.py`
  - limita las solicitudes de logos al rango visible y evita repetirlas.
  - evita reconstruir el catálogo en orden de origen y acelera favoritos con
    índices/conjuntos.
  - mantiene los cambios de salud y EPG sobre las filas existentes.
- `ui/widgets.py`
  - añade una caché LRU de 2.048 pixmaps por `(URL, tamaño)` para evitar
    decodificaciones repetidas y limitar el consumo de memoria.

### Versión y trazabilidad

- `core/config.py`, `README.md` y `TDTRadioVIP_Setup.iss` identifican la
  versión como `7.6.3.0`.
- Este archivo conserva el razonamiento, las mediciones y las tareas que
  deben continuar en la siguiente iteración.

## Medición posterior

La batería sintética se ejecutó en esta copia el 2026-09-04. Los tiempos son
orientativos y dependen del equipo, pero sirven como prueba de regresión:

| Caso | Antes (`7.6.2.2`) | Después (`7.6.3.0`) |
|---|---:|---:|
| `record_results()` — 100 resultados | 1,365 s | 0,0182 s |
| `record_results()` — 200 resultados | 3,563 s | 0,0269 s |
| `record_results()` — 400 resultados | 10,952 s | 0,0480 s |
| Poblado — 1.000 filas | 0,092 s | 0,0217 s |
| Poblado — 5.000 filas | 0,458 s | 0,1502 s |
| Poblado — 10.000 filas | 1,196 s | 0,4689 s |
| Filtro — 1.000 filas | 0,011–0,013 s | 0,0100 s |
| Filtro — 5.000 filas | 0,066–0,078 s | 0,0416 s |
| Filtro — 10.000 filas | 0,116–0,127 s | 0,1084 s |
| `select_stale_entries()` — 1.000 estados | 4,186 s | 0,0262 s |

La búsqueda universal no cambió en esta iteración: como referencia, la misma
prueba tardó aproximadamente 0,007 s con 1.000 entradas, 0,084 s con 10.000
y 0,465 s con 50.000.

Pruebas usadas:

1. tiempo de `record_results()` para 100/200/400 resultados;
2. tiempo de poblar/filtrar 1.000/5.000/10.000 filas;
3. tiempo de búsqueda universal con 1.000/10.000/50.000 entradas;
4. tiempo de `select_stale_entries()` con 1.000 estados guardados.

La prueba sintética no sustituye a una medición en un equipo real: también
conviene medir el arranque, el cambio TV/radio, el scroll y la carga de logos
con una lista M3U representativa.

## Próximas mejoras recomendadas

1. **Completado en 7.6.3.1:** sustituir `QListWidget` por
   `QAbstractListModel` + `QListView` para los catálogos grandes de TV y radio.
2. Crear índices en memoria para la búsqueda universal y para el acceso
   `tvg_id -> programa actual` del EPG.
3. Aplicar el filtro en un modelo proxy para no recorrer ni ocultar todas las
   filas en cada búsqueda.
4. Agrupar las señales de progreso del diagnóstico (por ejemplo, una
   actualización visual cada 50–100 ms) si se comprueba que el hilo GUI sigue
   recibiendo demasiados eventos.
5. Añadir perfiles de rendimiento reproducibles y una prueba de regresión con
   10.000 entradas antes de publicar otra versión.

## Verificación local

Desde la carpeta `7.6.3.0`:

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check .
```

Para publicar, revisar primero `git status`, comprobar que no entren cachés o
artefactos generados, crear el commit de esta versión y subir la rama/remoto
correspondientes.
