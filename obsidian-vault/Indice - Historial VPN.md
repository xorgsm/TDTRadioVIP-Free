---
tags: [tdtradiovip, vpn, indice]
---

# Historial de VPN (8.1.0 → 8.6.5)

Mapa de contenido (MOC) del cliente VPN de la edición VIP: desde la
primera versión con WireGuard hasta los tres fixes de estado/procesos
sobre OpenVPN, a raíz de varios reportes reales de un usuario probando
servidores gratuitos de VPNGate.

## Cronología

### Features

1. [[8.1.0 - Cliente VPN inicial con WireGuard]] — primera versión:
   cliente VPN bring-your-own basado en WireGuard, con UAC en cada
   conexión/desconexión.
2. [[8.3.0 - WireGuard a OpenVPN]] — sustituye WireGuard por OpenVPN
   para eliminar el UAC por conexión; introduce la limitación de fondo
   que arrastran los tres fixes posteriores (`status()` sin comando de
   solo-lectura por CLI).
3. [[8.4.0 - Servidores VPN gratuitos via VPNGate]] — añade VPNGate
   como segunda fuente de servidores (gratuitos, pero inestables) junto
   al modelo bring-your-own; esta inestabilidad es la causa raíz
   externa de los bugs siguientes.

### Fixes (8.6.x)

4. [[8.6.2 - Estado VPN atascado en Conectado]] — el bug original: la
   app mostraba "Conectado" para siempre al arrancar, y "Desconectar"
   no hacía nada.
5. [[8.6.3 - Procesos openvpn huerfanos y estado cruzado]] — al probar
   el fix de 8.6.2 contra un servidor VPNGate caído, aparecieron
   procesos `openvpn.exe` huérfanos, y el chequeo de estado nuevo no
   distinguía entre túneles.
6. [[8.6.4 - Desconectar VPN durante un reconecte automatico]] — un
   túnel real (Japón, VPNGate) se reconectaba solo por inestabilidad
   del adaptador TAP y fallos de autenticación del servidor,
   compitiendo con el botón "Desconectar".
7. [[8.6.5 - Dialogo VPN congelaba la app entera]] — ortogonal a los
   tres anteriores: no toca la detección de estado, corrige que
   `status()`/`connect()`/`disconnect()` se llamaran directamente en
   el hilo de la UI, congelando toda la app mientras duraban.

## El hilo común

Los tres fixes de 8.6.x giran sobre el mismo problema de fondo:
**`openvpn-gui.exe` no da a esta app ninguna fuente de verdad fiable
sobre el estado real del túnel** (no expone un comando de solo-lectura
por CLI — [issue #104](https://github.com/OpenVPN/openvpn-gui/issues/104)).
Cada versión resolvió una capa distinta de esa carencia:

| Versión | Lo que faltaba | Lo que se añadió |
|---|---|---|
| 8.6.2 | Comprobar que el proceso siga vivo, no solo el log | `_is_openvpn_process_running()` (vía `tasklist`) |
| 8.6.3 | Distinguir DE QUÉ túnel es el proceso vivo | `_is_tunnel_process_running(tunnel)` (vía PowerShell/`Win32_Process`, mira la línea de comandos) |
| 8.6.4 | Garantizar que "Desconectar" mata el túnel de verdad | `disconnect()` verifica y, si hace falta, fuerza el cierre con `_kill_orphaned_tunnel_process()` |

## Componentes relacionados

- `core/vpn_client.py` — todo el pilotaje de `openvpn-gui.exe` y la
  detección de estado real.
- `core/vpn_profiles.py` — CRUD de perfiles VPN, resuelve el nombre de
  túnel (`_sanitize_tunnel_name`) que usan los tres fixes.
- `core/vpngate.py` / `ui/dialogs/vpngate_picker.py` — de aquí salen
  servidores VPNGate inestables (voluntarios que se caen o fallan
  autenticación), la causa raíz externa que dispara estos bugs.
- `docs/superpowers/specs/2026-09-11-vpn-client-design.md` — diseño
  original que documentaba estas limitaciones como conocidas, sin
  resolverlas todavía.

## Ver también

- `CHANGELOG.md` (raíz del proyecto) — entradas oficiales de cada
  versión, en español, formato Keep a Changelog.
- `RELEASE.md` (raíz del proyecto) — runbook de cómo se publica cada
  release (los tres repos, el manifest.json, etc.).
