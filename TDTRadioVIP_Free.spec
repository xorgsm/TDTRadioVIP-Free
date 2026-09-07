# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para TDT & Radio VIP - VERSION FREE.
TV y Radio incluidos; sin Descargas (yt-dlp/Torrents/Soulseek/audio/
Podcasts) ni Chromecast/DLNA -- ver
ui.dialog_actions.DialogActionsController.show_about(), que es la fuente
de verdad de este límite. Sin splash ni código de activación tampoco
(main_free.py entra directo).
Compilar con:  pyinstaller TDTRadioVIP_Free.spec
"""
import os, sys

# Sin hidden_imports de pychromecast/zeroconf/libtorrent aquí a propósito:
# ui/main_window.py solo los importa (dentro de sus métodos, no arriba del
# módulo) cuando es_version_free es False, así que un Analysis normal no
# los encuentra en el camino real de ejecución de esta build. `excludes`
# de abajo es lo que de verdad los deja fuera del bundle -- ver el
# comentario junto a self._cast_session en ui/main_window.py para el
# porqué de fondo (un import a nivel de módulo los habría colado aquí
# igual, sin importar ningún condicional en tiempo de ejecución).
excludes = [
    'pychromecast', 'zeroconf', 'libtorrent',
    'ui.download_panel', 'ui.cast_controller',
    'core.caster', 'core.dlna_caster',
    # Activación/licencia: ui/application.py y ui/dialog_actions.py importan
    # core.license/ui.splash de forma local (dentro de run_vip()/
    # DialogActionsController.open_activation_dialog(), no arriba del
    # módulo) precisamente para que este build pueda excluirlos de verdad.
    'core.license', 'ui.splash',
]


def buscar_vlc():
    candidatos = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]
    for ruta in candidatos:
        if os.path.isfile(os.path.join(ruta, "libvlc.dll")):
            return ruta
    raise SystemExit(
        "\n[TDTRadioVIP] No se encontro VLC.\n"
        "Instala VLC 64 bits desde https://www.videolan.org/\n"
    )


VLC_DIR = buscar_vlc()
FFMPEG_DIR = os.path.join("resources", "ffmpeg")

if not os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
    raise SystemExit(
        "\n[TDTRadioVIP] Falta ffmpeg en resources\\ffmpeg\\ffmpeg.exe\n"
        "Descargalo de https://www.gyan.dev/ffmpeg/builds/\n"
    )

binaries = [
    (os.path.join(VLC_DIR, "libvlc.dll"), "."),
    (os.path.join(VLC_DIR, "libvlccore.dll"), "."),
]

datas = [
    (os.path.join(VLC_DIR, "plugins"), "plugins"),
    (os.path.join(FFMPEG_DIR, "ffmpeg.exe"), FFMPEG_DIR),
]

# ffprobe.exe (~97 MB) no se usa en el código — solo ffmpeg, en
# core/recorder.py. No aporta nada empaquetado y solo engordaría la
# carpeta de salida --onedir en ~97 MB sin motivo.

ICONO = os.path.join("resources", "icon.ico")
if os.path.isfile(ICONO):
    datas.append((ICONO, "resources"))
else:
    ICONO = None

FUENTE = os.path.join("resources", "fonts", "Inter-Variable.ttf")
if os.path.isfile(FUENTE):
    datas.append((FUENTE, os.path.join("resources", "fonts")))

a = Analysis(
    ['main_free.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    # Nombre fijo, sin versión (ver el mismo comentario en TDTRadioVIP.spec):
    # necesario para que el instalador pueda sustituir limpiamente una
    # instalación anterior en vez de dejarla abandonada al lado.
    name='TDTRadioVIP_Free',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TDTRadioVIP_Free',
)

# Ver el mismo bloque al final de TDTRadioVIP.spec para el porqué completo:
# el backend TLS propio de Qt (con su copia de OpenSSL, libssl-3-x64.dll/
# libcrypto-3-x64.dll -- distintas de libssl-3.dll/libcrypto-3.dll que usa
# el _ssl de Python, esas se quedan) crashea esta app con una violación de
# acceso bajo carga, y Qt lo carga igual aunque el código no use
# QNetworkAccessManager/QSslSocket para nada. Se borra del todo tras el
# COLLECT.
_dist_root = os.path.join('dist', 'TDTRadioVIP_Free')
_tls_dir = os.path.join(_dist_root, '_internal', 'PySide6', 'plugins', 'tls')
if os.path.isdir(_tls_dir):
    import shutil
    shutil.rmtree(_tls_dir, ignore_errors=True)
    print(f'[TDTRadioVIP_Free] Quitado el backend TLS de Qt (no usado): {_tls_dir}')
for _dll_name in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll'):
    _dll_path = os.path.join(_dist_root, '_internal', _dll_name)
    if os.path.isfile(_dll_path):
        os.remove(_dll_path)
        print(f'[TDTRadioVIP_Free] Quitado {_dll_name} (copia de OpenSSL de Qt, no usada)')
