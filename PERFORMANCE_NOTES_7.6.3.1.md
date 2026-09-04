# Registro técnico de rendimiento — 7.6.3.1

Esta iteración continúa el trabajo documentado en
`PERFORMANCE_NOTES_7.6.3.0.md`.

## Cambio principal

TV y radio dejaron de depender de `QListWidget` y ahora usan
`ChannelListModel` (`QAbstractListModel`) junto con `ChannelListView`
(`QListView`). Favoritos, historial y listas pequeñas siguen con
`QListWidget`, porque favoritos necesita `InternalMove` y no justifican una
migración que complicaría su comportamiento.

El modelo mantiene los datos de todo el catálogo, pero el delegado de Qt solo
trabaja con las filas visibles. El filtrado conserva una lista de índices
visibles y el orden reorganiza los diccionarios sin crear/destruir un objeto
Qt por canal. `ChannelListItem` conserva la pequeña interfaz que necesitan los
controladores de reproducción y menú contextual.

## Compatibilidad cubierta

- clic para reproducir y navegación anterior/siguiente;
- menú contextual y acciones de favoritos;
- orden por nombre, favoritos primero y orden de origen;
- filtros de texto, categoría y salud;
- actualización incremental de salud y subtítulos EPG;
- carga de logos visibles y actualización al hacer scroll;
- selección de la fila activa después de ordenar.

## Medición

Prueba sintética local con PySide6 en modo `offscreen`, sin red ni logos:

| Entradas | `QListWidget` poblado | Modelo poblado | Filtro widget | Filtro modelo |
|---:|---:|---:|---:|---:|
| 1.000 | 0,0217 s | 0,0005 s | 0,0100 s | 0,0004 s |
| 5.000 | 0,1502 s | 0,0019 s | 0,0416 s | 0,0017 s |
| 10.000 | 0,4689 s | 0,0062 s | 0,1084 s | 0,0032 s |

El beneficio mayor es estructural: la vista no mantiene un widget completo por
fila y el coste de repintado deja de crecer con todos los elementos del
catálogo. La prueba no sustituye la validación en un equipo real con logos,
EPG y una lista M3U auténtica.

## Verificación realizada

- `127 passed in 2.25s` antes de esta migración.
- Tests específicos del modelo y compatibilidad: `9 passed in 1.59s`.
- Ruff: `All checks passed`.
- Debe repetirse la batería completa después del bump a `7.6.3.1` y antes de
  compilar el instalador.

## Publicación para usuarios

El actualizador de la aplicación consulta el último `manifest.json` del repo
público `xorgsm/TDTRadioVIP-Free`, no el código de `TDTRadioVIP-Source`.
Para que los usuarios reciban esta versión hay que:

1. sincronizar el cambio compatible con Free en su rama `main`;
2. compilar el instalador combinado `TDTRadioVIP_Setup_v7.6.3.1.exe`;
3. calcular su SHA-256 y crear `manifest.json` con versión `7.6.3.1`;
4. publicar instalador, portable y manifiesto en la release pública `v7.6.3.1`;
5. comprobar que `/releases/latest/download/manifest.json` devuelve la nueva
   versión.

El procedimiento exacto está en `RELEASE.md`.
