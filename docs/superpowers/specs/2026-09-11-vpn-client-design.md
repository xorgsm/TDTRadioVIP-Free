# Cliente VPN (WireGuard) en la edición VIP — v8.1

**Estado:** Diseño aprobado e implementado (2026-09-11). Versión publicada: **8.1.0**.
**Clasificación:** Arquitectónico (brainstorming completo: preguntas → enfoques → diseño → spec).

## 1. Motivación

Algunas listas públicas de M3U/radio están restringidas por país (geobloqueo).
La app ya centraliza descubrimiento y reproducción de TV, radio y podcasts
(ver `PRODUCT.md`); sin poder salir de la IP local del usuario, esas listas
quedan fuera de alcance aunque sean públicas y gratuitas. Se añade un
cliente VPN a la parte licenciada (edición VIP con licencia activada) para
que el usuario pueda conectar con un servidor de otro país usando **su
propia** suscripción VPN.

## 2. Alcance decidido

Preguntas resueltas con el usuario antes de implementar (ver conversación):

- **Modelo: bring-your-own.** El usuario aporta su propia suscripción VPN
  (archivo `.conf` de WireGuard que le da su proveedor). La app **no**
  opera servidores VPN propios ni integra la API de un proveedor
  comercial — sin coste de infraestructura ni responsabilidad legal por
  el tráfico que pase por servidores propios.
- **Protocolo: WireGuard.** Un solo archivo de configuración, cliente
  oficial ligero y moderno.
- **WireGuard debe estar instalado aparte.** La app detecta
  `wireguard.exe` (ruta estándar de instalación o PATH); si no lo
  encuentra, muestra un aviso con enlace a la descarga oficial en vez de
  bundlearlo con el instalador.
- **Ubicación: nueva sección «VPN» dentro del diálogo de Ajustes**
  existente (`ui/dialogs/settings.py`), gated a VIP con licencia activada
  de verdad.
- **Varios perfiles guardados.** El usuario puede importar más de un
  `.conf` (p. ej. uno por país) y elegir cuál activar desde un combo,
  igual que ya gestiona perfiles de usuario en el mismo diálogo.

**Fuera de alcance v1 (YAGNI):** sin auto-conexión, sin detección
automática de "lista bloqueada por región", sin selección automática de
servidor, sin más de un túnel activo a la vez.

## 3. Componentes

- **`core/vpn_profiles.py`** — CRUD puro de perfiles. Copia el `.conf`
  importado a `get_profile_data_dir() / "vpn" / <túnel>.conf` (misma
  carpeta de datos del perfil que ya usa `core/soulseek_account.py`) y
  mantiene un índice `vpn_profiles.json` (nombre visible → nombre de
  túnel saneado). Sin cifrado: mismo nivel de protección que el resto de
  datos de perfil ya existentes en el proyecto, no es una regresión.
  Valida que el archivo importado tenga pinta de `.conf` de WireGuard
  (`[Interface]` / `[Peer]`) antes de aceptarlo.
- **`core/vpn_client.py`** — controla `wireguard.exe`:
  - `connect()` / `disconnect()` usan `/installtunnelservice` y
    `/uninstalltunnelservice`. Estas dos operaciones **requieren
    elevación** (mismo comportamiento que la app oficial de WireGuard),
    así que se lanzan con `ShellExecuteExW` y el verbo `runas` — Windows
    muestra un UAC cada vez que se conecta o desconecta. Se documenta
    como limitación conocida de v1: no hay forma de evitarlo con el
    cliente oficial de WireGuard.
  - `status()` consulta `sc query WireGuardTunnel$<túnel>`, que no
    necesita elevación, para refrescar el estado sin lanzar ningún UAC.
  - Procesos auxiliares (`sc query`) lanzados con
    `creationflags=CREATE_NO_WINDOW`, igual que ya hace
    `core/recorder.py` para ffmpeg.
- **UI** — sección «VPN» en `SettingsDialog`, construida solo si
  `parent.activated and not parent.es_version_free` (mismo criterio ya
  usado en `ui/dialog_actions.py` para "Ir a Descargas" en la paleta de
  comandos: `win.activated` también vale `True` en la build Free, que
  arranca "activada" para desbloquear todo — hay que excluirla aparte).
  Combo de perfiles, etiqueta de estado, y tres botones que actúan al
  momento (Importar, Eliminar, Conectar/Desconectar), sin esperar al
  "Guardar" del diálogo — mismo patrón que los botones de gestión de
  perfil de usuario ya presentes en la misma pantalla.

## 4. Manejo de errores

- WireGuard no instalado → aviso + botón "Descargar WireGuard…"
  (`QDesktopServices.openUrl` a `wireguard.com/install`), sin mostrar los
  controles de conectar/perfiles.
- UAC cancelado por el usuario o `wireguard.exe` devuelve código de
  salida distinto de cero → `VpnClientError` con mensaje explicando el
  motivo, mostrado con `QMessageBox.warning`.
- Eliminar un perfil cuyo túnel está en marcha → se intenta desconectar
  primero; si la desconexión falla (p. ej. UAC cancelado), se aborta el
  borrado en vez de dejar un servicio de Windows huérfano sin perfil que
  lo referencie.
- `.conf` importado sin `[Interface]`/`[Peer]` → rechazado con
  `VpnProfileError` antes de copiarlo, no se llega a crear el perfil.

## 5. Testing

- `tests/test_vpn_profiles.py` — CRUD puro sobre un directorio de perfil
  temporal: importar, listar, obtener, eliminar, colisión de nombres,
  saneado de nombre de túnel, rechazo de `.conf` inválido.
- `tests/test_vpn_client.py` — construcción de argumentos de
  `connect()`/`disconnect()` y parseo de `sc query` en `status()`, con
  `subprocess` y `_run_elevated` sustituidos por dobles de prueba. No
  cubre el UAC real ni el servicio de Windows real: no son reproducibles
  en CI ni deseables en una suite automática.

## 6. Decisión de versión

Este cambio, sumado al trabajo ya completado y documentado como "sin
publicar" en `CHANGELOG.md` (atajos de teclado, CI en GitHub Actions,
reparto de `ui/dialogs.py`/`ui/style.py` en paquetes), se publica como
**8.1.0**: funcionalidad nueva sin ruptura de compatibilidad, coherente
con `MINOR` en SemVer.
