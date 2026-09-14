# Servidores VPN gratuitos vía VPNGate — v8.4

**Estado:** Diseño aprobado e implementado (2026-09-14).
**Clasificación:** Arquitectónico (brainstorming completo: preguntas → enfoques → diseño → spec).

## 1. Motivación

El cliente VPN de la edición VIP (v8.3, ver
`docs/superpowers/specs/2026-09-11-vpn-client-design.md`) usa un modelo
bring-your-own: el usuario aporta su propia suscripción VPN. Al probarlo,
salió a relucir que eso **no** es gratis de verdad -- OpenVPN (el
programa) es gratuito, pero conseguir un `.ovpn` que funcione sigue
requiriendo pagar a algún proveedor. Esto no cumplía el objetivo original
de tener una opción realmente gratuita dentro de la app.

## 2. Alcance decidido

- **VPNGate como origen de servidores gratuitos.** Proyecto público de la
  Universidad de Tsukuba (Japón): servidores OpenVPN mantenidos por
  voluntarios, sin cuenta ni suscripción, publicados en
  `https://www.vpngate.net/api/iphone/` como CSV con el `.ovpn` de cada
  servidor en Base64. Es exactamente el caso de uso original: acceder a
  listas públicas de TV/radio con restricción geográfica.
- **Complementa, no sustituye, el modelo bring-your-own.** Quien ya tenga
  su propia suscripción sigue pudiendo importar su `.ovpn` (v8.3, sin
  cambios). VPNGate es una segunda fuente, no la única.
- **Sin servidor propio de la app.** Igual que antes: la app no opera
  infraestructura VPN, solo consulta la lista pública de VPNGate y deja
  elegir.

**Fuera de alcance (YAGNI):** sin caché en disco de la lista (se pide
fresca cada vez que se abre el selector -- los servidores de VPNGate
cambian constantemente, una caché añadiría complejidad para un ahorro
mínimo en una acción explícita y poco frecuente), sin filtro por
velocidad/ping (solo por país, ver §3), sin selección automática del
"mejor" servidor.

## 3. Componentes

- **`core/vpngate.py`** (nuevo) — `fetch_servers()` descarga y parsea el
  CSV de VPNGate: ignora la línea `*vpn_servers` y usa la línea `#...`
  como cabecera, decodifica el Base64 de `OpenVPN_ConfigData_Base64` a
  texto `.ovpn`, descarta filas sin ese campo o con Base64 corrupto, y
  ordena por `Score` descendente (el propio VPNGate puntúa velocidad +
  estabilidad). `request_get` es inyectable para tests sin red real.
  Lanza `VpnGateError` si falla la descarga o la lista viene vacía.
- **`ui/dialogs/vpngate_picker.py`** (nuevo) — `VpnGatePickerDialog`:
  descarga la lista al abrirse, la muestra en una `QListWidget` (país,
  ping, velocidad, host) con un filtro de texto por país, y devuelve el
  servidor elegido en `self.selected_server`. No importa nada por su
  cuenta -- eso lo hace quien lo abre.
- **`core/vpn_profiles.py`** — se añade `import_profile_from_text()`,
  hermana de `import_profile()` pero a partir de texto ya en memoria en
  vez de un archivo en disco (evita escribir un `.ovpn` temporal solo
  para volver a leerlo). Ambas funciones comparten ahora un núcleo
  privado `_import_text()` con toda la validación/registro que antes
  tenía solo `import_profile()`.
- **UI** — en la sección VPN de Ajustes, nuevo botón "Servidor gratuito
  (VPNGate)…" junto a "Importar perfil (.ovpn)…". Abre
  `VpnGatePickerDialog`, pide un nombre para el perfil (por defecto
  `"<País> (VPNGate)"`) y lo importa con `import_profile_from_text()` --
  a partir de ahí es un perfil VPN más, mismo combo/Conectar/Eliminar de
  siempre.

## 4. Manejo de errores

- Sin red o VPNGate caído → `VpnGateError`, el selector lo muestra como
  texto de estado en vez de una lista vacía sin explicación.
- Fila del CSV sin el campo Base64, o Base64 corrupto → se descarta esa
  fila en silencio (son cientos de servidores, uno mal formado no debe
  tumbar toda la lista).
- El `.ovpn` de VPNGate no pasa la validación de `_import_text()` (caso
  raro, pero posible si VPNGate cambia su formato) → mismo
  `VpnProfileError` que ya mostraba `import_profile()` para un archivo
  inválido.
- Registro con OpenVPN falla (grupo "OpenVPN Administrators") → mismo
  mensaje ya existente de v8.3, sin duplicar lógica.

## 5. Testing

- `tests/test_vpngate.py` — parseo del CSV (país, ping, velocidad,
  decodificación Base64), orden por score, filas inválidas descartadas,
  y los dos casos de error (`VpnGateError`), todo con `request_get`
  sustituido por un doble de prueba, sin red real.
- `tests/test_vpn_profiles.py` — dos tests nuevos para
  `import_profile_from_text()` (registro correcto sin archivo de origen,
  y rechazo de contenido inválido).
- Prueba manual del diálogo (`VpnGatePickerDialog(fetch_servers=...)`
  con una lista falsa) para confirmar filtro y selección antes de
  publicar -- no hay test automático de UI de Qt en este proyecto para
  diálogos modales, sigue el mismo criterio que el resto de `ui/dialogs/`.

## 6. Decisión de versión

Funcionalidad nueva, sin romper nada de lo publicado en 8.3.0 (el modelo
bring-your-own sigue igual). Se publica como **8.4.0**, coherente con
`MINOR` en SemVer.
