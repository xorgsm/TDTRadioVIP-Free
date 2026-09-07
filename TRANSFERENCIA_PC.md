# Transferencia a otro PC

Este ZIP contiene el código fuente, recursos, pruebas y archivos de compilación
de TDT & Radio VIP 7.6.5.2. No incluye `venv`, cachés de usuario, instaladores
anteriores ni artefactos generados: el entorno virtual de Python no es portable
entre equipos.

## Preparación en Windows

Requisitos:

- Python 3.12 de 64 bits.
- VLC de 64 bits instalado para ejecutar o compilar la edición completa.

Desde esta carpeta:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Para ejecutar:

```powershell
.\venv\Scripts\python.exe main.py
```

La edición Free se inicia con `main_free.py`.

## Verificación

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check .
```

## Compilación

```powershell
.\venv\Scripts\python.exe setup_license.py build_ext --inplace
.\venv\Scripts\pyinstaller.exe TDTRadioVIP.spec
.\venv\Scripts\pyinstaller.exe TDTRadioVIP_Free.spec
```

Los datos personales de la aplicación permanecen fuera del ZIP, en `%APPDATA%\CoderByXOR\TDTRadioVIP_7.6.0`.
