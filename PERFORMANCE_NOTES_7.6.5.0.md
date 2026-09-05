# Registro técnico de rendimiento — 7.6.5.0

## Cambios

Esta versión continúa la virtualización de catálogos introducida en 7.6.3.1.

- `MainWindow._run_automatic_backup()` delega la escritura JSON a `FetchWorker`.
  La ruta de datos global y la del perfil se capturan antes de arrancar para
  que cambiar de perfil durante la copia no mezcle datos.
- `ChannelListsController.mark_playing_everywhere()` y
  `mark_favorites_everywhere()` solo emiten `dataChanged` cuando el valor
  realmente cambia.
- `DownloadPanel` crea Torrents, Podcasts, Soulseek, Convertir y los dos
  editores al seleccionar cada pestaña. Esto reduce el coste de arranque de la
  edición VIP.
- `LogoLoader` lee y escala imágenes en el worker. La interfaz solo crea el
  `QPixmap` final y descarta callbacks de tarjetas ya sustituidas.
- `Carousel` conserva las tarjetas que siguen representando el mismo stream y
  actualiza texto, programa y logo sin destruir el árbol Qt.

## Verificación

- `python -m pytest -q`: 137 pruebas correctas.
- `python -m ruff check .`: sin errores.
- `python -m compileall -q core ui player main.py main_free.py`: correcto.

La prueba de catálogo usa 10.000 entradas y comprueba que una actualización
de reproducción no recorre toda la vista con señales redundantes. La medición
de tiempo de arranque real depende de red, VLC, logos y hardware; debe repetirse
al compilar el instalador.
