# TDT & Radio VIP 8.1

Aplicación de escritorio para Windows construida con Python, PySide6 y VLC.
Reúne televisión, radio, EPG, podcasts, grabaciones y herramientas multimedia.

## Desarrollo

Requiere Python 3.12 y VLC de 64 bits instalado.

```powershell
python -m pip install -r requirements-dev.txt
python main.py
```

La edición Free se inicia con:

```powershell
python main_free.py
```

## Verificación

```powershell
python -m pytest -q
python -m ruff check .
```

## Construcción

El módulo de licencia puede recompilarse antes de PyInstaller:

```powershell
python setup_license.py build_ext --inplace
pyinstaller TDTRadioVIP.spec
pyinstaller TDTRadioVIP_Free.spec
```

Tras generar ambas carpetas bajo `dist`, el instalador conjunto se construye
con Inno Setup usando `TDTRadioVIP_Setup.iss`.

## Datos y privacidad

Los perfiles y ajustes de las ramas 7.6.x y 8.x comparten la carpeta de datos
`TDTRadioVIP_7.6.0` (`APP_DATA_NAME` no cambia con el salto a 8.0, para que la
actualización conserve perfiles, licencia, favoritos y ajustes). Backups
personales, listas M3U, claves privadas, registros
de licencias y herramientas internas de emisión de licencias no forman parte
del paquete de fuentes limpio.

La sección VPN (edición VIP con licencia activada, ver
`docs/superpowers/specs/2026-09-11-vpn-client-design.md`) guarda los
perfiles OpenVPN que el usuario importa en `vpn/*.ovpn` dentro de la
carpeta del perfil activo, sin cifrar -- mismo nivel de protección que el
resto de datos de perfil (favoritos, cuenta de Soulseek, etc.). La app no
opera servidores VPN propios: además de un servidor gratuito elegido de
VPNGate (ver
`docs/superpowers/specs/2026-09-14-vpngate-free-servers-design.md`),
también admite importar un `.ovpn` propio de otro proveedor gratuito
(reactivado en 8.6.0 junto a VPNGate, no en su lugar). Desde 8.6.6,
cualquier `.ovpn` (VPNGate o importado) se sanea antes de guardarse:
`core.vpn_profiles._strip_dangerous_directives()` quita directivas
capaces de ejecutar código (`up`/`down`/`client-connect`/`plugin`...) y
fuerza `script-security 0`.

Cada perfil VPN se copia además, por diseño del servicio interactivo de
OpenVPN, a una carpeta de configuración **compartida por toda la
máquina** (`core.vpn_client.find_config_dir()`, normalmente bajo
`Archivos de programa\OpenVPN\config`) -- así es como ese servicio
encuentra los túneles por nombre. Desde 8.6.6 cada copia se restringe
con `icacls` (`core.vpn_client.restrict_config_file_to_current_user()`)
para que solo el usuario de Windows actual pueda leerla, ya no cualquier
otra cuenta del grupo "OpenVPN Administrators" en el mismo PC. Sigue
existiendo un límite conocido: como esa carpeta es una única carpeta del
sistema, los distintos "perfiles" de la propia app (pensados para varias
personas que comparten un mismo PC y una misma cuenta de Windows, ver
`core/config.py`) no quedan aislados entre sí a este nivel -- solo el
resto de datos de perfil (favoritos, historial, etc.) sí lo están.
