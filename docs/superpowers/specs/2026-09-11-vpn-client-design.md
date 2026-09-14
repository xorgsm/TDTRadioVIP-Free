# Cliente VPN (OpenVPN) en la edición VIP — v8.3

**Estado:** Diseño aprobado e implementado (2026-09-14). Reemplaza la v8.1 (WireGuard).
**Clasificación:** Arquitectónico (brainstorming completo: preguntas → enfoques → diseño → spec).

## 1. Motivación

Algunas listas públicas de M3U/radio están restringidas por país (geobloqueo).
La app ya centraliza descubrimiento y reproducción de TV, radio y podcasts
(ver `PRODUCT.md`); sin poder salir de la IP local del usuario, esas listas
quedan fuera de alcance aunque sean públicas y gratuitas. La v8.1 añadió un
cliente VPN basado en WireGuard para esto (edición VIP con licencia
activada), pero el cliente oficial de WireGuard para Windows pide UAC en
**cada** conexión/desconexión (instala/quita un servicio por túnel cada
vez) y su modelo de un solo `.conf` por perfil resultó confuso en la
interfaz. Esta revisión sustituye WireGuard por OpenVPN sin cambiar el
modelo de fondo: el usuario sigue aportando su propia suscripción VPN.

## 2. Qué cambia respecto a v8.1

- **Protocolo: OpenVPN en vez de WireGuard.** El usuario importa un
  `.ovpn` (en vez de un `.conf` de WireGuard) que le da su proveedor.
  Sigue siendo bring-your-own: la app no opera servidores VPN propios.
- **Sin UAC por conexión.** OpenVPN ≥ 2.4 instala un *Interactive
  Service* una sola vez (con privilegios de administrador, durante la
  instalación de OpenVPN — no la hace esta app). A partir de ahí,
  cualquier usuario del grupo local de Windows **"OpenVPN
  Administrators"** puede conectar/desconectar sin UAC, pilotando
  `openvpn-gui.exe` por línea de comandos (`--command connect <nombre>` /
  `--command disconnect <nombre>`). Ver
  [OpenVPN/openvpn-gui](https://github.com/OpenVPN/openvpn-gui) y el
  [ticket #811](https://community.openvpn.net/openvpn/ticket/811).
- **Detección de instalación:** igual que antes pero busca
  `openvpn-gui.exe` (ruta estándar `Program Files\OpenVPN\bin\` o PATH)
  en vez de `wireguard.exe`.
- **Migración:** no automática. Los perfiles `.conf` de WireGuard
  importados en v8.1/8.2 **no** son compatibles con este formato; el
  usuario tiene que volver a importar sus perfiles como `.ovpn`. Se
  documenta como cambio incompatible en `CHANGELOG.md`, no se escribe
  lógica de migración (YAGNI: proyecto en fase temprana, sin base de
  usuarios con perfiles VPN ya guardados que justifique el coste).

**Sigue fuera de alcance (igual que v1):** sin auto-conexión, sin
detección automática de "lista bloqueada por región", sin selección
automática de servidor, sin más de un túnel activo a la vez.

## 3. Componentes

- **`core/vpn_profiles.py`** — CRUD de perfiles. Copia el `.ovpn`
  importado a `get_profile_data_dir() / "vpn" / <túnel>.ovpn` (misma
  carpeta de datos del perfil de siempre) y mantiene el índice
  `vpn_profiles.json`. Valida que el archivo importado tenga pinta de
  `.ovpn` (directivas `client` y `remote`) antes de aceptarlo.
  **Novedad respecto a v8.1:** además de guardar su propia copia,
  registra el perfil con OpenVPN copiándolo también a
  `vpn_client.find_config_dir()` (carpeta que vigila el servicio
  interactivo) y pide un `rescan` — si esa copia falla (p. ej. el
  usuario no pertenece al grupo "OpenVPN Administrators" y no tiene
  permiso de escritura ahí), se aborta el import con un
  `VpnProfileError` explicando el motivo. Esto acopla `vpn_profiles.py`
  a `vpn_client.py` (antes eran independientes) — es necesario porque
  OpenVPN conecta perfiles **por nombre** desde una carpeta conocida por
  el GUI, no por ruta explícita como hacía `wireguard.exe`.
- **`core/vpn_client.py`** — controla `openvpn-gui.exe`:
  - `connect()`/`disconnect()` mandan `--command connect|disconnect
    <túnel>` sin elevar (el propio GUI habla con el servicio
    interactivo, ya elevado de antemano). Son *fire-and-forget*: no
    bloquean hasta que el túnel termine de levantarse, a diferencia de
    WireGuard que sí esperaba a que `/installtunnelservice` terminara.
    Limitación conocida de v8.3: el estado puede tardar unos segundos en
    reflejar "Conectado" tras pulsar el botón.
  - `status()` no tiene un comando de solo-lectura por CLI (ver
    [issue #104](https://github.com/OpenVPN/openvpn-gui/issues/104)), así
    que lee el log por perfil que ya escribe el servicio interactivo
    (`<config_dir>/../log/<túnel>.log`) buscando la última aparición de
    "Initialization Sequence Completed" frente a la de
    "SIGTERM"/"process exiting".
  - `find_config_dir()` lee `HKLM\SOFTWARE\OpenVPN-GUI\config_dir` del
    registro (valor que usa el propio GUI internamente); si no existe,
    cae a `Program Files\OpenVPN\config`.
  - Procesos auxiliares lanzados con `creationflags=CREATE_NO_WINDOW`,
    igual que antes.
- **UI** — misma sección «VPN» en `SettingsDialog`, gated a
  `parent.activated and not parent.es_version_free` (sin cambios en el
  criterio de licencia). Cambia el texto de los avisos (ya no menciona
  UAC en cada conexión) y el filtro del diálogo de importar
  (`*.ovpn` en vez de `*.conf`).

## 4. Manejo de errores

- OpenVPN no instalado → aviso + botón "Descargar OpenVPN…"
  (`QDesktopServices.openUrl` a `openvpn.net/community-downloads`), sin
  mostrar los controles de conectar/perfiles.
- `.ovpn` importado sin `client`/`remote` → rechazado con
  `VpnProfileError` antes de copiarlo, no se llega a crear el perfil.
- No se puede registrar el perfil en la carpeta de configs de OpenVPN
  (permiso denegado, normalmente por no estar en el grupo "OpenVPN
  Administrators") → se deshace la copia local y se aborta el import con
  un mensaje explicando el motivo y el grupo necesario.
- Eliminar un perfil cuyo túnel está en marcha → se intenta desconectar
  primero (mismo criterio que v8.1); si falla, se aborta el borrado.

## 5. Testing

- `tests/test_vpn_profiles.py` — CRUD sobre un directorio de perfil
  temporal más el registro/baja en la carpeta de configs de OpenVPN
  (con `vpn_client.find_config_dir` y `vpn_client.rescan` sustituidos
  por dobles de prueba).
- `tests/test_vpn_client.py` — construcción de argumentos de
  `connect()`/`disconnect()`, lectura de `find_config_dir()` desde el
  registro (con `winreg` sustituido por un doble), y parseo del log en
  `status()`. No cubre el servicio interactivo real ni el propio
  `openvpn-gui.exe`: no son reproducibles en CI.

## 6. Decisión de versión

Cambio incompatible en el formato de perfiles VPN guardados (WireGuard →
OpenVPN, sin migración) sobre una función que ya se publicó en 8.1.0/8.2.0.
Se publica como **8.3.0**: aunque no rompe ninguna API pública del
proyecto, sí rompe los perfiles VPN ya guardados por quien actualice,
coherente con tratarlo como cambio de comportamiento notable (se
documenta explícitamente en `CHANGELOG.md`, no se sube a `MAJOR` porque
el proyecto no seguía SemVer estricto de compatibilidad de datos de
usuario antes de esto).
