; ============================================================
;  TDT & Radio VIP — Instalador (Inno Setup 6.x)
;  Coder By X@R
;
;  Empaqueta la salida --onedir de ambos .spec (carpetas dist\...) en un
;  único instalador. El usuario elige en el asistente si quiere la versión
;  con licencia, la Free, o las dos.
;
;  ANTES DE COMPILAR ESTE SCRIPT:
;   1) Compila primero los dos .spec con PyInstaller como siempre
;      (pyinstaller TDTRadioVIP.spec / pyinstaller TDTRadioVIP_Free.spec).
;      Este instalador empaqueta lo que haya en dist\, no compila Python.
;   2) Coloca este .iss en la raíz del proyecto (junto a dist\, resources\).
;   3) Para una revisión 7.6.x cambia SOLO MyAppVersion aquí abajo. El AppId
;      debe mantenerse durante toda la rama; solo se crea otro al abrir una
;      rama que deba convivir con la anterior. Los nombres de carpeta/exe son
;      fijos a propósito -- ver [InstallDelete] -- y no cambian por release.
; ============================================================

#define MyAppName "TDT & Radio VIP"
#define MyAppVersion "7.6.2.1"
#define MyAppPublisher "Coder By X@R"
#define MyAppInstallName "TDT & Radio VIP 7.6.0"
; Fijos, SIN la versión incrustada (antes "TDTRadioVIP_v6.3.0.exe" etc.,
; recalculados a mano en cada release). Deben coincidir con el name= de
; TDTRadioVIP.spec / TDTRadioVIP_Free.spec (ambos ya usan nombres fijos por
; el mismo motivo). Ver [InstallDelete] para el porqué de fondo.
#define MyAppExeLicensed "TDTRadioVIP.exe"
#define MyAppExeFree "TDTRadioVIP_Free.exe"
#define FolderLicensed "TDTRadioVIP"
#define FolderFree "TDTRadioVIP_Free"

[Setup]
; AppId propio de la rama 7.6.0: debe ser distinto del de 7.5.11 para que
; ambas instalaciones puedan convivir sin sustituirse ni desinstalarse.
; Mantén este mismo valor durante futuras revisiones de 7.6.x.
AppId={{34D6C3B2-8D44-4CB8-AC56-2BEE9AC6D9A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppInstallName}
DefaultGroupName={#MyAppInstallName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=TDTRadioVIP_Setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=resources\icon.ico
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#FolderLicensed}\{#MyAppExeLicensed}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

; El usuario elige qué instalar: con licencia, Free, o las dos. Si algún
; día solo quieres repartir una de las dos, borra la sección [Types] entera
; y dile a [Components] que sean simplemente "Fixed" en vez de "full/free/both".
[Types]
Name: "full"; Description: "Versión con licencia (recomendada)"
Name: "free"; Description: "Versión Free (sin activación)"
Name: "both"; Description: "Las dos versiones"

[Components]
Name: "licensed"; Description: "{#MyAppName}"; Types: full both
Name: "free"; Description: "{#MyAppName} Free"; Types: free both

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos adicionales:"

[InstallDelete]
; Con AppId fijo, Inno Setup ya detecta solo que hay una instalación previa
; y actualiza en el mismo {app} -- pero antes las carpetas de destino
; llevaban la versión en el nombre (TDTRadioVIP_v6.3.0\), así que cada
; release nueva creaba una carpeta DISTINTA en vez de sustituir la de
; antes: la versión vieja se quedaba abandonada ocupando espacio en disco,
; y si algún archivo desaparecía de una versión a otra, seguía ahí para
; siempre. Con nombres de carpeta fijos (ver los #define de arriba) ya no
; se duplican, pero sin esto tampoco se limpiarían archivos sueltos que ya
; no existan en la nueva versión -- por eso se borra el contenido entero
; antes de copiar los archivos nuevos, en vez de fiarse de "ignoreversion"
; para ir sobrescribiendo archivo a archivo.
Type: filesandordirs; Name: "{app}\{#FolderLicensed}"; Components: licensed
Type: filesandordirs; Name: "{app}\{#FolderFree}"; Components: free

[Files]
; recursesubdirs+createallsubdirs: --onedir deja muchas DLLs/plugins de VLC
; sueltos en subcarpetas — hay que copiar la carpeta entera, no solo el exe.
Source: "dist\{#FolderLicensed}\*"; DestDir: "{app}\{#FolderLicensed}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: licensed
Source: "dist\{#FolderFree}\*"; DestDir: "{app}\{#FolderFree}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: free

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#FolderLicensed}\{#MyAppExeLicensed}"; Components: licensed
Name: "{group}\{#MyAppName} Free"; Filename: "{app}\{#FolderFree}\{#MyAppExeFree}"; Components: free
Name: "{group}\Desinstalar {#MyAppInstallName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} {#MyAppVersion}"; Filename: "{app}\{#FolderLicensed}\{#MyAppExeLicensed}"; Tasks: desktopicon; Components: licensed
Name: "{autodesktop}\{#MyAppName} Free {#MyAppVersion}"; Filename: "{app}\{#FolderFree}\{#MyAppExeFree}"; Tasks: desktopicon; Components: free

[Run]
; postinstall + skipifsilent: solo ofrece abrir la app si el usuario ha
; instalado a mano (no si el instalador se lanza en modo silencioso /S).
Filename: "{app}\{#FolderLicensed}\{#MyAppExeLicensed}"; Description: "Abrir {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent; Components: licensed
Filename: "{app}\{#FolderFree}\{#MyAppExeFree}"; Description: "Abrir {#MyAppName} Free ahora"; Flags: nowait postinstall skipifsilent; Components: free and not licensed

[UninstallDelete]
; Los datos del usuario (favoritos, historial, config, caché de canales)
; viven en %APPDATA%\CoderByXOR\TDTRadioVIP_7.6.0, FUERA de {app} — desinstalar no
; los toca. Si alguna vez quieres que el desinstalador también los borre,
; añade aquí: Type: filesandordirs; Name: "{userappdata}\CoderByXOR\TDTRadioVIP_7.6.0"
Type: filesandordirs; Name: "{app}"
