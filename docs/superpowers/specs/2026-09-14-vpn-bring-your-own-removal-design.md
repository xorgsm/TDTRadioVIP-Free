# Retirada del modelo "trae tu propia VPN" — v8.5

**Estado:** Diseño aprobado e implementado (2026-09-14).
**Clasificación:** Arquitectónico (decisión de producto, cambio pequeño de código).

## 1. Motivación

Tras publicar VPNGate en 8.4.0 (ver
`docs/superpowers/specs/2026-09-14-vpngate-free-servers-design.md`), la
sección VPN seguía ofreciendo dos caminos: "Importar perfil (.ovpn)…"
(traer tu propia suscripción, normalmente de pago) y "Servidor gratuito
(VPNGate)…" (gratis, sin cuenta). Decisión de producto: mantener las dos
opciones diluía el mensaje de "VPN gratis dentro de la app" -- un usuario
nuevo veía primero el botón de importar su propio perfil y podía asumir
que hacía falta pagar. Se retira el bring-your-own; VPNGate pasa a ser la
única vía.

## 2. Alcance decidido

- **Se quita** el botón "Importar perfil (.ovpn)…" y su manejador
  (`SettingsDialog._on_vpn_import` en `ui/dialogs/settings.py`).
- **Se mantiene** `core/vpn_profiles.import_profile()` (primitiva interna
  que lee un `.ovpn` de disco) porque `import_profile_from_text()` la
  comparte por dentro (`_import_text()`) y sigue teniendo tests propios;
  ya no la llama ningún camino de UI.
- **Se mantiene** todo lo demás igual: conectar/desconectar/eliminar
  perfiles ya importados (incluidos los que un usuario ya hubiera traído
  a mano antes de 8.5.0), el transporte OpenVPN, el registro con
  "OpenVPN Administrators".
- **Cambio incompatible:** ya no hay forma de importar un `.ovpn` propio
  desde la UI. Perfiles bring-your-own ya guardados en un perfil de app
  existente (de 8.1.0–8.4.0) siguen funcionando -- no se borran ni se
  desregistran, solo no se puede añadir uno nuevo así.

**Fuera de alcance:** no se toca el protocolo (sigue siendo OpenVPN, es
lo que publica VPNGate); no se monta infraestructura propia (sigue el
principio "sin servidor propio de la app" de los specs anteriores).

## 3. Testing

- No hacía falta tocar tests: ningún test de `tests/test_vpn_profiles.py`
  ni `tests/test_dialogs_package_contract.py` referenciaba el botón o el
  método retirado (verificado con grep antes de borrar).
- `python -m pytest tests/ -q` tras el cambio, sin regresiones.

## 4. Decisión de versión

Cambio incompatible de cara al usuario (una vía de configurar VPN
desaparece de la UI, aunque perfiles ya creados siguen vivos) sobre lo
publicado en 8.4.0. Se publica como **8.5.0**, coherente con `MINOR` en
SemVer (sin romper compatibilidad de datos/API interna, solo UI).
