# -*- mode: python ; coding: utf-8 -*-
"""
Configuración de PyInstaller para TDT & Radio VIP.

Comprueba las dependencias externas antes de empezar y avisa con un mensaje
claro si falta alguna, en vez de fallar a mitad con un error críptico.
"""
import glob
import os
import re
import sys

from PyInstaller.utils.hooks import collect_submodules

# yt-dlp NO se empaqueta: la app descarga el ejecutable oficial en tiempo de
# ejecución para que pueda autoactualizarse cuando YouTube cambie su web.
# libtorrent va como hidden import porque PyInstaller no siempre detecta
# solo sus submódulos binarios (mismo motivo que pychromecast/zeroconf).
hidden_imports = (
    collect_submodules('pychromecast') + collect_submodules('zeroconf')
    + collect_submodules('libtorrent')
)


def buscar_vlc():
    """Localiza la instalación de VLC de la que tomar libvlc y sus plugins."""
    candidatos = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]
    for ruta in candidatos:
        if os.path.isfile(os.path.join(ruta, "libvlc.dll")):
            return ruta
    raise SystemExit(
        "\n[TDTRadioVIP] No se encontro VLC.\n"
        "Instala VLC de 64 bits desde https://www.videolan.org/ , o edita\n"
        "la lista 'candidatos' de este .spec con tu ruta de instalacion.\n"
        f"Rutas comprobadas: {candidatos}\n"
    )


VLC_DIR = buscar_vlc()

FFMPEG_DIR = os.path.join("resources", "ffmpeg")
if not os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
    raise SystemExit(
        "\n[TDTRadioVIP] Falta ffmpeg.\n"
        "Descarga https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip ,\n"
        "descomprimelo y copia ffmpeg.exe (esta en la carpeta bin\\)\n"
        f"a la carpeta: {os.path.abspath(FFMPEG_DIR)}\n"
    )

binaries = [
    (os.path.join(VLC_DIR, "libvlc.dll"), "."),
    (os.path.join(VLC_DIR, "libvlccore.dll"), "."),
]

datas = [
    (os.path.join(VLC_DIR, "plugins"), "plugins"),
    (os.path.join(FFMPEG_DIR, "ffmpeg.exe"), FFMPEG_DIR),
]

# ffprobe.exe (~97 MB) no se usa en ningún sitio del código: core/recorder.py
# y core/audio_converter.py solo llaman a ffmpeg, y core/mp3_info.py lee
# duración/tags parseando la salida de texto de 'ffmpeg -i archivo' en vez
# de usar ffprobe (ver cabecera de ese módulo). Empaquetarlo no aporta nada
# y solo engordaría la carpeta de salida --onedir en ~97 MB sin motivo.
# Si algún día lo necesitas para algo, basta con quitar este comentario y
# volver a añadirlo a datas.

ICONO = os.path.join("resources", "icon.ico")
if os.path.isfile(ICONO):
    datas.append((ICONO, "resources"))
else:
    print("[TDTRadioVIP] Aviso: no hay resources\\icon.ico; se compila sin icono.")
    ICONO = None

FUENTE = os.path.join("resources", "fonts", "Inter-Variable.ttf")
if os.path.isfile(FUENTE):
    datas.append((FUENTE, os.path.join("resources", "fonts")))
else:
    print("[TDTRadioVIP] Aviso: no hay resources\\fonts\\Inter-Variable.ttf; se compila con la tipografía del sistema.")

# ── Módulo de licencia compilado con Cython (opcional) ──────────────────────
# `python setup_license.py build_ext --inplace` (ver ese fichero para el
# porqué) genera un core/license*.pyd junto al license.py de siempre. Si
# existe, se le dice a PyInstaller que empaquete ESE binario en vez de
# tracear core/license.py como bytecode Python normal -- así el .exe final
# no lleva la lógica de licencias en un formato trivial de descompilar.
# Si no se ha compilado (setup_license.py no se ha ejecutado nunca, o se
# borró el .pyd a propósito), no pasa nada: se sigue empaquetando el .py
# tal cual se ha hecho siempre, sin bloquear la compilación por esto.
#
# IMPORTANTE -- comprobación de versión: un .pyd de extensión lleva en su
# propio nombre el ABI de Python con el que se compiló (p. ej.
# "license.cp312-win_amd64.pyd" = Python 3.12). Si ese tag no coincide con
# el intérprete que está corriendo ESTE .spec (el que usa PyInstaller para
# el build), el binario es incompatible: no es un error que se vea al
# compilar, sino un import que falla dentro del EXE ya construido, con
# excludes=["core.license"] quitando de en medio el .py de respaldo -- la
# app no arrancaría en el PC del cliente y el fallo solo se detecta al
# probar el ejecutable final. Se compara el tag antes de decidir usarlo en
# vez de confiar a ciegas en que quien compiló el .pyd usó el mismo Python
# que quien empaqueta.
def _tag_interprete_actual() -> str:
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def _tag_del_pyd(ruta: str):
    m = re.search(r"\.(cp\d+)-", os.path.basename(ruta))
    return m.group(1) if m else None


license_pyd = glob.glob(os.path.join("core", "license*.pyd"))
excludes = []
if license_pyd:
    ruta_pyd = license_pyd[0]
    tag_pyd = _tag_del_pyd(ruta_pyd)
    tag_actual = _tag_interprete_actual()
    if tag_pyd != tag_actual:
        print(
            f"[TDTRadioVIP] AVISO: {ruta_pyd} esta compilado para {tag_pyd or '?'} "
            f"pero este build corre con {tag_actual} -- son incompatibles. "
            "Se ignora el .pyd y se empaqueta core/license.py normal para no "
            "generar un EXE que falle al arrancar. Recompila con: "
            f"\"{sys.executable}\" setup_license.py build_ext --inplace"
        )
    else:
        print(f"[TDTRadioVIP] Usando modulo de licencia compilado: {ruta_pyd} ({tag_pyd})")
        binaries.append((ruta_pyd, "core"))
        excludes = ["core.license"]
if not excludes:
    print(
        "[TDTRadioVIP] Aviso: core/license.py sin compilar (ver setup_license.py "
        "si quieres protegerlo). Se empaqueta como Python normal, igual que antes."
    )


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Nombre fijo, SIN la versión incrustada (antes 'TDTRadioVIP_v6.3.0'): con
# el nombre cambiando en cada release, el instalador (TDTRadioVIP_Setup.iss)
# no podía detectar y sustituir limpiamente una instalación anterior -- cada
# versión nueva se instalaba en una carpeta distinta, dejando la vieja
# abandonada ocupando espacio. Con un nombre fijo + limpieza de carpeta en
# el instalador (ver [InstallDelete] en el .iss), cada instalación nueva
# reemplaza a la anterior de verdad. La versión sigue viéndose en
# Configuración y en las propiedades del archivo -- solo deja de estar en
# el nombre del ejecutable.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TDTRadioVIP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICONO] if ICONO else None,
)

# --onedir en vez de --onefile: antes EXE() se llevaba a.binaries/a.datas
# directamente y con runtime_tmpdir=None se descomprimía todo (VLC + lo que
# quedaba de ffmpeg) a una carpeta temporal EN CADA arranque — el mayor
# causante de arranque lento en PCs con disco más flojo. Con
# exclude_binaries=True + COLLECT, todo queda ya suelto en la carpeta de
# salida de una vez, y arrancar es directo, sin descomprimir nada.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TDTRadioVIP',
)

# Qt trae su propio backend TLS (PySide6/plugins/tls/) con su propia copia
# de OpenSSL -- libssl-3-x64.dll/libcrypto-3-x64.dll, DISTINTAS de
# libssl-3.dll/libcrypto-3.dll (esas sí se quedan: son las que usa el _ssl
# de Python para las peticiones HTTPS de requests/urllib3 -- EPG, canales,
# radio, actualizaciones -- que nunca han dado problema).
#
# Nada en esta app usa QNetworkAccessManager/QSslSocket (ver el comentario
# de LogoLoader en ui/widgets.py, que se pasó a requests+FetchWorker por
# este mismo motivo), pero Qt igual prueba/carga ese backend al arrancar,
# y esa copia de libssl/libcrypto que trae PySide6 crashea la app entera
# con una violación de acceso (0xc0000005, llamada a través de un puntero
# de función nulo dentro de libssl/libcrypto) bajo la carga de arrancar
# con un catálogo grande -- confirmado con volcados de memoria reales
# (Windows los deja en %LOCALAPPDATA%\CrashDumps), reproducido en la
# máquina que lo reportó, y AÚN presente después de quitar el único uso
# de QNetworkAccessManager del código: Qt sigue cargando el plugin igual.
# Se borra del todo tras el COLLECT para que Qt ni pueda intentar
# cargarlo -- la app no pierde nada (no usa TLS por el lado de Qt).
_dist_root = os.path.join('dist', 'TDTRadioVIP')
_tls_dir = os.path.join(_dist_root, '_internal', 'PySide6', 'plugins', 'tls')
if os.path.isdir(_tls_dir):
    import shutil
    shutil.rmtree(_tls_dir, ignore_errors=True)
    print(f'[TDTRadioVIP] Quitado el backend TLS de Qt (no usado): {_tls_dir}')
for _dll_name in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll'):
    _dll_path = os.path.join(_dist_root, '_internal', _dll_name)
    if os.path.isfile(_dll_path):
        os.remove(_dll_path)
        print(f'[TDTRadioVIP] Quitado {_dll_name} (copia de OpenSSL de Qt, no usada)')
