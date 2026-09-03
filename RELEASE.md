# Cómo publicar una release (runbook)

Documenta el proceso completo para no tener que redescubrirlo cada vez.
Escrito tras publicar la 7.6.2.2 (fix de lentitud/bloqueo con 500+
canales).

## Mapa de repos

| Repo | Visibilidad | Contenido | Rama por defecto |
|---|---|---|---|
| `xorgsm/TDTRadioVIP-Source` (este repo) | **Privado** | Código fuente completo, ambas ediciones (VIP + Free) | `master` |
| `xorgsm/TDTRadioVIP-Free` | **Público** | Solo el código de la edición Free (subconjunto sincronizado a mano de este repo) | `main` |
| `xorgsm/TDTRadioVIP-Releases` | **Privado** | Solo el instalador compilado + su SHA-256, sin código fuente (archivo/histórico) | `main` |

**Importante:** los tres tienen **historiales de git no relacionados**
entre sí (no comparten ancestro común). No es un mono-repo con
submódulos ni nada parecido — son checkouts independientes que se
sincronizan a mano copiando contenido/commits.

## Cómo se autoactualiza la app

`core/updater.py` (`check_for_update`) descarga la URL de
`settings["update_check_url"]` (por defecto, ver `core/config.py`):

```
https://github.com/xorgsm/TDTRadioVIP-Free/releases/latest/download/manifest.json
```

Esa URL de GitHub siempre resuelve al asset `manifest.json` de la
**última release** de `TDTRadioVIP-Free` — no hay que tocar esta URL en
cada versión, solo subir un `manifest.json` nuevo en cada release.

El manifiesto tiene que ser exactamente:
```json
{
  "version": "X.Y.Z.W",
  "download_url": "https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/vX.Y.Z.W/TDTRadioVIP_Setup_vX.Y.Z.W.exe",
  "sha256": "<sha256 en minúsculas, 64 hex>"
}
```

`validate_download_manifest()` en `core/updater.py` exige: `download_url`
HTTPS con host, `sha256` con regex `^[0-9a-fA-F]{64}$`, y que el nombre de
archivo termine en `.exe`. Se puede validar en local antes de publicar:

```python
from core.updater import validate_download_manifest
import json
validate_download_manifest(json.load(open("installer_output/manifest.json")))
```

**El instalador combinado (ambas ediciones) se distribuye
deliberadamente desde el repo público `TDTRadioVIP-Free`** — ver el
comentario junto a `update_check_url` en `core/config.py`. Solo el
*código fuente* de la edición con licencia se mantiene privado; el
binario compilado sí es público (la activación por licencia sigue
protegida en tiempo de ejecución por `core/license.py` + ID de
hardware).

## Antes de nada: sincronizar el fix a los 3 repos

Este repo (`TDTRadioVIP-Source`) es la fuente de verdad. Los cambios de
código que también apliquen a la edición Free (la mayoría de la UI, casi
todo `core/` salvo licencia/torrents/soulseek/downloads) hay que
llevarlos también a `TDTRadioVIP-Free`.

Como los historiales no están relacionados, `git cherry-pick` de un commit
de este repo sobre una rama basada en `free/main` funciona igual (aplica
el diff por contenido, no por ancestro común) — solo puede haber
conflictos si el archivo divergió (p. ej. `CHANGELOG.md`, que en el repo
Free está desactualizado desde la 7.5.7 a propósito — no intentes
volcarle el historial completo de este repo, basta una entrada nueva
mínima arriba del todo).

```bash
# una sola vez por sesión de trabajo
git remote add origin https://github.com/xorgsm/TDTRadioVIP-Source.git   # si no existe
git remote add free   https://github.com/xorgsm/TDTRadioVIP-Free.git     # si no existe
git fetch origin && git fetch free

# IMPORTANTE: no trabajes sobre una rama local "master" que no rastree
# origin/master de verdad -- comprueba primero que hay ancestro común:
git merge-base origin/master HEAD   # si falla, tu copia local no es la real; usa origin/master como base

# aplica el mismo fix a Free
git checkout -b free-<nombre-fix> free/main
git cherry-pick <hash-del-commit-en-este-repo>
# resuelve conflictos de CHANGELOG.md a mano (ver arriba), luego:
git cherry-pick --continue
python -m pytest tests/ -q   # el repo Free tiene menos tests (~54 vs ~122), es normal
git push free free-<nombre-fix>:main
```

Sube el commit a este repo (`TDTRadioVIP-Source`) de la misma forma
(rama basada en `origin/master`, fast-forward, sin `--force`).

## Bump de versión (en los 2 repos con código)

En **cada** checkout (este repo y el de Free) hay que tocar:

1. `core/config.py` → `APP_VERSION = "X.Y.Z.W"`
2. Solo en este repo (el `.iss` no vive en el repo Free):
   `TDTRadioVIP_Setup.iss` → `#define MyAppVersion "X.Y.Z.W"`

## Compilar (desde este repo, con AMBOS `main*.py`/`*.spec` presentes)

Requiere: Python con `PySide6`, `pyinstaller`, `python-vlc`, `requests`
instalados; VLC de 64 bits instalado en
`C:\Program Files\VideoLAN\VLC\libvlc.dll` (o la ruta x86); Inno Setup 6
— en esta máquina vive en
`C:\Users\xor\AppData\Local\Programs\Inno Setup 6\ISCC.exe` (**no** en
`Program Files`, por eso cuesta encontrarlo con búsquedas típicas).

```bash
rm -rf build dist
python -m PyInstaller TDTRadioVIP.spec --noconfirm        # ~369 MB en dist/TDTRadioVIP/
python -m PyInstaller TDTRadioVIP_Free.spec --noconfirm   # ~351 MB en dist/TDTRadioVIP_Free/

mkdir -p installer_output
"/c/Users/xor/AppData/Local/Programs/Inno Setup 6/ISCC.exe" TDTRadioVIP_Setup.iss
# -> installer_output/TDTRadioVIP_Setup_vX.Y.Z.W.exe (~200 MB, ambas ediciones)

# zip portable de la edición Free (Compress-Archive, no zip/7z -- ya está en PATH vía PowerShell)
cd dist/TDTRadioVIP_Free
powershell -NoProfile -Command "Compress-Archive -Path * -DestinationPath '../../installer_output/TDTRadioVIP_Free_vX.Y.Z.W_portable.zip' -CompressionLevel Optimal"
cd ../..

sha256sum installer_output/TDTRadioVIP_Setup_vX.Y.Z.W.exe installer_output/TDTRadioVIP_Free_vX.Y.Z.W_portable.zip
```

Cada `pyinstaller` tarda varios minutos; el `.iss` (comprime ~720 MB entre
las dos ediciones) puede tardar bastante más. Lánzalos en segundo plano.

## Smoke test antes de publicar (obligatorio)

No hay forma de probar visualmente la UI aquí, pero sí de descartar
errores de empaquetado (DLL/módulo faltante = crash inmediato):

```bash
./dist/TDTRadioVIP_Free/TDTRadioVIP_Free.exe &
sleep 6 && tasklist | grep -i TDTRadioVIP_Free   # debe seguir vivo, sin log de error
taskkill //F //IM TDTRadioVIP_Free.exe

./dist/TDTRadioVIP/TDTRadioVIP.exe &
sleep 6 && tasklist | grep -i "TDTRadioVIP.exe"
taskkill //F //IM TDTRadioVIP.exe
```

## `manifest.json`

```json
{
  "version": "X.Y.Z.W",
  "download_url": "https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/vX.Y.Z.W/TDTRadioVIP_Setup_vX.Y.Z.W.exe",
  "sha256": "<el sha256 del .exe calculado arriba>"
}
```

## Publicar

**1) Release pública (la que activa el autoactualizador) — `TDTRadioVIP-Free`:**

```bash
cd installer_output
gh release create vX.Y.Z.W \
  TDTRadioVIP_Setup_vX.Y.Z.W.exe \
  TDTRadioVIP_Free_vX.Y.Z.W_portable.zip \
  manifest.json \
  --repo xorgsm/TDTRadioVIP-Free \
  --title "TDT & Radio VIP Free X.Y.Z.W" \
  --notes "..."
```

Verificar que quedó bien enlazada como "latest" (importante: si se marca
como prerelease o no es la más reciente por fecha, `/releases/latest/...`
no apuntará a ella):

```bash
curl -sL "https://github.com/xorgsm/TDTRadioVIP-Free/releases/latest/download/manifest.json"
# debe devolver el manifest.json recién subido
```

**2) Copia privada (histórico de builds, opcional pero es la convención
del repo) — `TDTRadioVIP-Releases`:**

```bash
gh release create vX.Y.Z.W \
  installer_output/TDTRadioVIP_Setup_vX.Y.Z.W.exe \
  --repo xorgsm/TDTRadioVIP-Releases \
  --title "TDT & Radio VIP X.Y.Z.W — Instalador (Licenciada + Free)" \
  --notes "..."
```

Formato de `--notes` esperado ahí (ver releases anteriores con
`gh release view vX.Y.Z.W --repo xorgsm/TDTRadioVIP-Releases`): descripción
corta + el SHA-256 del instalador en el cuerpo del texto + apartado de
"Requisitos" (Windows 64 bits, VLC empaquetado).

## Cosas que se aprendieron a las malas (no repetir)

- **Nunca hagas `push --force`** a ninguno de los tres repos. Si tu rama
  local diverge del remoto (historiales no relacionados, o tu copia local
  quedó desincronizada), crea una rama nueva basada en el remoto real
  (`git checkout -b tmp origin/master`), haz `cherry-pick` del commit que
  quieras llevar, y empuja esa rama como fast-forward. Comprueba antes con
  `git merge-base --is-ancestor <remoto> <tu-rama>`.
- El push a un repo **público** (`TDTRadioVIP-Free`) lo bloquea el
  clasificador de permisos de Claude Code por defecto — hace falta
  confirmación explícita del usuario, no basta con "sigue".
- El `CHANGELOG.md` de `TDTRadioVIP-Free` **no está sincronizado** con
  el de este repo (se quedó en la 7.5.7 aunque el código sí sigue
  actualizado) — es intencional/histórico, no lo "arregles" volcando
  todo el changelog de VIP ahí; entradas VIP-only (p. ej. sobre
  `core/license.py`, hardware ID) no aplican a la edición Free y
  confundirían.
- Inno Setup en esta máquina está instalado en
  `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, **no** en
  `C:\Program Files`, así que una búsqueda ingenua en las rutas típicas
  falla aunque sí esté instalado.
- El instalador combinado (`TDTRadioVIP_Setup.iss`) necesita
  `dist\TDTRadioVIP\` **y** `dist\TDTRadioVIP_Free\` presentes a la vez
  en la raíz del proyecto — compila los dos `.spec` antes de lanzar
  `ISCC.exe`, en ese orden.
