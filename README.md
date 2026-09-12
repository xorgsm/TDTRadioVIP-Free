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
perfiles WireGuard que el usuario importa en `vpn/*.conf` dentro de la
carpeta del perfil activo, sin cifrar -- mismo nivel de protección que el
resto de datos de perfil (favoritos, cuenta de Soulseek, etc.). La app no
opera servidores VPN propios: cada perfil es la suscripción VPN del propio
usuario.
