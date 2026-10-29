"""
Adelgazado del build de PyInstaller, común a TDTRadioVIP.spec y
TDTRadioVIP_Free.spec.

Dos problemas que tenía la carpeta dist/ y que se resuelven aquí:

1. Tamaño en disco: el hook de PySide6 y la copia entera de VLC/plugins
   metían ~70 MB que la app no usa nunca (Qt Quick/QML/teclado virtual/PDF,
   el OpenGL por software, la interfaz Qt/skins propia de VLC, la salida
   de streaming/transcodificación de VLC...).

2. RAM y arranque: PyInstaller copia los plugins de VLC con fecha nueva,
   así que el plugins.dat que viene del VLC instalado queda caducado
   (VLC compara tamaño y fecha de cada plugin). Con la caché caducada,
   libVLC abre los ~360 DLL de plugins uno a uno al crear la instancia y
   los deja cargados: decenas de MB de RAM y un arranque más lento. Tras
   el COLLECT se regenera la caché con vlc-cache-gen sobre la carpeta de
   salida (con 7 plugins cargados en vez de 360). Inno Setup conserva la
   fecha de los ficheros al instalar, así que la caché sigue valiendo en
   el PC del cliente.

Coder By X@R
"""
import fnmatch
import os
import subprocess

# Módulos Python que ningún camino real de la app importa. cryptography
# (~9 MB) solo lo arrastraba un import opcional de requests para pyOpenSSL,
# que no está instalado: requests funciona igual sin él.
EXCLUDED_MODULES = ["cryptography", "PySide6.QtTest"]

# Rutas de destino (relativas a _internal, con "/") que se quitan del bundle.
EXCLUDED_FILES = (
    # Qt: la app es solo Widgets. Quick/QML/Pdf/OpenGL entran por los plugins
    # de abajo (teclado virtual, imageformats/qpdf), no porque se usen.
    "PySide6/opengl32sw.dll",
    "PySide6/Qt6Quick*.dll",
    "PySide6/Qt6Qml*.dll",
    "PySide6/Qt6VirtualKeyboard*.dll",
    "PySide6/Qt6Pdf*.dll",
    "PySide6/Qt6OpenGL*.dll",
    "PySide6/plugins/platforminputcontexts/*",
    "PySide6/plugins/generic/*",
    "PySide6/plugins/networkinformation/*",
    "PySide6/plugins/platforms/qminimal.dll",
    "PySide6/plugins/platforms/qoffscreen.dll",
    "PySide6/plugins/platforms/qdirect2d.dll",
    "PySide6/plugins/imageformats/qpdf.dll",
    "PySide6/plugins/imageformats/qicns.dll",
    "PySide6/plugins/imageformats/qtga.dll",
    "PySide6/plugins/imageformats/qwbmp.dll",
    # VLC: se usa embebido como reproductor. Su propia interfaz (Qt/skins),
    # las visualizaciones, lua (sus scripts no se empaquetan) y toda la
    # salida de streaming/transcodificación (sout, mux, encoders x264/x265)
    # no se usan: la grabación y la conversión van por ffmpeg y el envío a
    # Chromecast/DLNA pasa la URL tal cual.
    "plugins/gui/*",
    "plugins/visualization/*",
    "plugins/lua/*",
    "plugins/access_output/*",
    "plugins/stream_out/*",
    "plugins/mux/*",
    "plugins/codec/libx264_plugin.dll",
    "plugins/codec/libx26410b_plugin.dll",
    "plugins/codec/libx265_plugin.dll",
    # Se regenera tras el COLLECT (ver regenerate_vlc_plugin_cache).
    "plugins/plugins.dat",
)


def _excluded(dest: str) -> bool:
    dest = dest.replace("\\", "/")
    return any(fnmatch.fnmatch(dest, pattern) for pattern in EXCLUDED_FILES)


def slim_toc(toc):
    """Devuelve el TOC (a.binaries / a.datas) sin las entradas de EXCLUDED_FILES."""
    kept = [entry for entry in toc if not _excluded(entry[0])]
    print(f"[pyinstaller_slim] Quitadas {len(toc) - len(kept)} entradas no usadas del bundle")
    return kept


def regenerate_vlc_plugin_cache(vlc_dir: str, dist_root: str) -> None:
    """Regenera plugins.dat de VLC para los plugins ya copiados a dist_root."""
    cache_gen = os.path.join(vlc_dir, "vlc-cache-gen.exe")
    # Ruta absoluta obligatoria: con una relativa vlc-cache-gen termina con
    # código 0 pero escribe una caché vacía (24 bytes).
    plugins_dir = os.path.abspath(os.path.join(dist_root, "_internal", "plugins"))
    if not os.path.isfile(cache_gen):
        raise SystemExit(
            f"\n[TDTRadioVIP] Falta {cache_gen}: sin el no se puede generar la "
            "cache de plugins de VLC y la app cargaria los ~300 plugins al arrancar.\n"
        )
    subprocess.run([cache_gen, plugins_dir], check=True)
    cache = os.path.join(plugins_dir, "plugins.dat")
    if not os.path.isfile(cache) or os.path.getsize(cache) < 1024:
        raise SystemExit(f"\n[TDTRadioVIP] vlc-cache-gen no genero una cache valida en {cache}\n")
    print(f"[pyinstaller_slim] Cache de plugins de VLC regenerada: {cache}")
