# TDTRadioVIP 7.6.2 — Punto de continuación

Actualizado: 31 de agosto de 2026

## Cambios principales

- Perfiles protegidos frente a colisiones de mayúsculas/minúsculas en
  Windows, evitando que dos grafías apunten accidentalmente a la misma
  carpeta.
- Actualizador limitado a manifiestos con enlaces HTTPS válidos y protegido
  frente a componentes de versión desmesurados.
- Importación de backups limitada a 100 MB; backups automáticos resistentes a
  fechas futuras, directorios con nombres coincidentes y duplicados creados en
  el mismo segundo.
- Interfaz principal refinada y adaptable: navegación más consistente,
  iconografía QPainter, foco visible, nombres accesibles y composición compacta
  de Inicio y Ahora suena.

## Compatibilidad

- `APP_VERSION` y `MyAppVersion` pasan a `7.6.2`.
- `APP_DATA_NAME` sigue siendo `TDTRadioVIP_7.6.0`: toda la rama 7.6.x comparte
  perfiles, licencia, favoritos y ajustes.
- El `AppId`, las carpetas de instalación y los nombres de ejecutable permanecen
  sin cambios para que el instalador actualice limpiamente la rama 7.6.x.

## Verificación

- 103 tests superados.
- `ruff check .` limpio.
- Arranque real de `MainWindow` comprobado con Qt en modo aislado.
- Interfaz revisada a 1440 × 900 y al mínimo soportado de 860 × 580.

## Empaquetado

El ZIP de fuentes debe excluir datos personales, backups, listas M3U, cachés,
capturas de revisión, claves privadas, registros de licencias y artefactos de
compilación. Debe conservar fuentes, recursos de ejecución, tests, requisitos,
scripts de build y especificaciones de instalador.
