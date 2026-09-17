---
tags: [tdtradiovip, vpn, indice]
---

# Historial de fixes de VPN (8.6.2 → 8.6.4)

Mapa de contenido (MOC) de la investigación y los arreglos hechos sobre
el cliente OpenVPN de la edición VIP (`core/vpn_client.py`), a raíz de
varios reportes reales de un usuario probando servidores gratuitos de
VPNGate.

## Cronología

1. [[8.6.2 - Estado VPN atascado en Conectado]] — el bug original: la
   app mostraba "Conectado" para siempre al arrancar, y "Desconectar"
   no hacía nada.
2. [[8.6.3 - Procesos openvpn huerfanos y estado cruzado]] — al probar
   el fix de 8.6.2 contra un servidor VPNGate caído, aparecieron
   procesos `openvpn.exe` huérfanos, y el chequeo de estado nuevo no
   distinguía entre túneles.
3. [[8.6.4 - Desconectar VPN durante un reconecte automatico]] — un
   túnel real (Japón, VPNGate) se reconectaba solo por inestabilidad
   del adaptador TAP y fallos de autenticación del servidor,
   compitiendo con el botón "Desconectar".

## El hilo común

Las tres versiones giran sobre el mismo problema de fondo:
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
