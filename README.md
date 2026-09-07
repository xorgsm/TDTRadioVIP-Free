# TDT & Radio VIP 7.6.5.1

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

Los perfiles y ajustes de toda la rama 7.6.x comparten la carpeta de datos
`TDTRadioVIP_7.6.0`. Backups personales, listas M3U, claves privadas, registros
de licencias y herramientas internas de emisión de licencias no forman parte
del paquete de fuentes limpio.
