# Manifiesto de actualización firmado — v8.6.25

**Estado:** Diseño aprobado e implementado (2026-10-01). Pendiente del autor: generar la clave real y pegar la clave pública (ver `RELEASE.md`, "Firmar el manifiesto").
**Clasificación:** Arquitectónico (cambia el formato del manifiesto, el proceso de publicación y la verificación en la app).
**Origen:** punto 8 de la revisión general de 8.6.24 (ver más abajo, "Contexto").

## 1. Contexto y motivación

`core/updater.py` descarga el instalador de una actualización y comprueba su
SHA-256 (`validate_download_manifest`, `download_verified_update`). Ese hash
viaja en el **mismo** `manifest.json` que la URL del instalador, y ambos viven
en la release de GitHub de `xorgsm/TDTRadioVIP-Free` (ver `RELEASE.md`).

El SHA-256 garantiza que la descarga no se corrompió, pero **no** que sea
auténtica: quien comprometa esa release (cuenta de GitHub, token filtrado,
asset sustituido) cambia a la vez el instalador y su hash, y la app lo
ejecuta tras mostrar "El instalador superó la verificación SHA-256".

Falta una prueba de autenticidad que dependa de un secreto que **no** esté en
GitHub: una firma digital con una clave privada que solo tiene el autor.

## 2. Alcance decidido

- **Firma obligatoria** para "Descargar y verificar". Decisión del usuario
  frente a las alternativas "firma opcional (transición)" y "no hacerlo".
- **Firma RSA-2048 con SHA-256 (PKCS#1 v1.5)**, verificada en Python puro con
  la clave pública embebida. No añade dependencias a la app: `cryptography`
  no está instalado y `core/license.py` ya verifica RSA del mismo modo.
- **Clave nueva, distinta de la de licencias.** Reutilizar la clave de
  `core/license.py` permitiría a quien firme actualizaciones generar licencias
  válidas, y viceversa.
- **Las versiones ya instaladas no cambian:** ignoran el campo `signature`
  que no conocen y siguen usando el flujo actual.

### Fuera de alcance

- **Repetición de un manifiesto antiguo firmado (rollback):** la app solo
  ofrece versiones mayores que la instalada, así que un manifiesto viejo se
  trata como "ya estás al día". Sin cambios.
- **Ocultar actualizaciones (freeze):** quien bloquee o sirva un manifiesto
  viejo impide ver versiones nuevas; una firma no lo resuelve.
- **Revocación/rotación automática de clave:** ver §8, Riesgos.
- **Firma del propio instalador (Authenticode):** es un mecanismo distinto
  (SmartScreen) y no se aborda aquí.

## 3. Formato

El manifiesto gana un campo:

```json
{
  "version": "X.Y.Z.W",
  "download_url": "https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/vX.Y.Z.W/TDTRadioVIP_Setup_vX.Y.Z.W.exe",
  "sha256": "<64 hex en minúsculas>",
  "signature": "<512 hex>"
}
```

`signature` son los 256 bytes de la firma RSA-2048, en hexadecimal.

### Mensaje firmado

Se firma exactamente esta cadena (UTF-8, sin salto de línea final):

```
TDTRadioVIP-update-v1
<version>
<filename>
<sha256>
```

- `version`: el valor de `version` del manifiesto, con `strip()`.
- `filename`: el nombre de archivo que `validate_download_manifest` ya deriva
  de la URL (último segmento de la ruta, sin query).
- `sha256`: en minúsculas, ya validado con `SHA256_RE`.
- La primera línea es un prefijo de dominio: impide que una firma hecha para
  otro propósito con la misma clave se reutilice aquí.
- Ningún campo puede contener `\n` ni `\r`; si lo contiene, el manifiesto se
  rechaza antes de verificar (evita ambigüedad entre campos).

**Por qué no se firma `download_url`:** el nombre de archivo y el SHA-256
firmados ya fijan qué instalador es válido. Cambiar el host de descarga no
permite colar otro binario, y no se firma la URL para poder alojar el mismo
instalador en otro sitio sin volver a firmar.

## 4. Componentes

### 4.1 `core/update_signature.py` (nuevo)

Responsabilidad única: verificar la firma de un manifiesto ya validado.

```python
UPDATE_PUBLIC_KEY_N_B64: str   # módulo RSA en base64; "" hasta que el autor la configure
UPDATE_PUBLIC_KEY_E: int = 65537

def signed_message(version: str, filename: str, sha256: str) -> bytes: ...
def verify_signature(version: str, filename: str, sha256: str, signature_hex: str) -> bool: ...
```

- `verify_signature` devuelve `False` (no lanza) si la firma no es hex, no
  mide 256 bytes, o no coincide.
- Compara **el bloque completo de 256 bytes** con `hmac.compare_digest`, nunca
  un prefijo (misma invariante que `core/license.py`, ver su comentario sobre
  Bleichenbacher).
- **Falla cerrado:** si `UPDATE_PUBLIC_KEY_N_B64` está vacío, devuelve `False`
  siempre y registra un aviso. Una app sin clave configurada no acepta
  ninguna actualización descargable.
- `signed_message` rechaza (ValueError) campos con `\n`/`\r`.

### 4.2 `core/updater.py` (modificado)

- `validate_download_manifest(data)`: tras las comprobaciones actuales
  (HTTPS, SHA-256, `.exe`), exige `signature` presente y válida mediante
  `verify_signature`. Si falta o no verifica, lanza `ValueError` con un
  mensaje claro ("El manifiesto no está firmado" / "La firma del manifiesto
  no es válida").
- Función nueva `has_valid_signature(data) -> bool`: la misma comprobación
  sin lanzar, para decidir qué ofrecer en la interfaz.
- `check_update_status` / `check_for_update` **no cambian**: siguen
  informando de que hay una versión nueva; la firma solo gobierna la
  descarga.

### 4.3 `ui/update_check_controller.py` (modificado)

`secure_download` pasa de `bool(sha256 and enlace)` a
`has_valid_signature(resultado) and enlace`.

- Con firma válida: igual que hoy ("¿Descargar y verificar el instalador?").
- Sin firma o con firma inválida: se degrada al flujo existente "¿Abrir la
  página de descarga?" (`QDesktopServices.openUrl`), y se registra un aviso en
  el log. **Nunca** se ofrece ejecutar un instalador no verificado.
- El texto "superó la verificación SHA-256" pasa a "superó la verificación de
  firma y SHA-256".

### 4.4 `tools/sign_manifest.py` (nuevo, solo desarrollo)

Herramienta de línea de comandos para el autor. Usa `cryptography`
(dependencia **solo de desarrollo**, en `requirements-dev.txt`).

- `keygen --out <carpeta>`: genera un par RSA-2048; escribe la clave privada
  en `<carpeta>/update_signing_key.pem` (permisos restringidos) y **solo
  imprime** el módulo público en base64 para pegarlo en
  `core/update_signature.py`. Se niega a escribir dentro del repositorio
  (comprueba que la ruta no esté bajo la raíz de git) y a sobrescribir una
  clave existente.
- `sign --key <pem> --manifest <manifest.json>`: lee el manifiesto, valida
  sus campos con las mismas reglas que la app, calcula la firma y escribe
  `signature` en el JSON. Tras firmar, **verifica** la firma con
  `core.update_signature` antes de dar el resultado por bueno.
- `.gitignore`: añade `*.pem` y `update_signing_key*` como defensa extra.

### 4.5 Documentación y CI

- `RELEASE.md`: nuevo paso "Firmar el manifiesto" antes de subir
  `manifest.json`, con el comando exacto, y el formato con `signature`.
- `.github/workflows/ci.yml`: instalar `cryptography` en el job de tests para
  que los tests de firma se ejecuten (no se saltan).

## 5. Flujo

1. El autor compila el instalador y genera `manifest.json` (sin firma).
2. `python tools/sign_manifest.py sign --key <pem> --manifest manifest.json`
   añade `signature`.
3. Sube `manifest.json` firmado a la release de `TDTRadioVIP-Free`.
4. La app descarga el manifiesto (`check_update_status`), ve una versión
   mayor y comprueba `has_valid_signature`:
   - válida → ofrece "Descargar y verificar"; `download_verified_update`
     vuelve a validar firma + SHA-256 antes de publicar el `.exe`;
   - inválida/ausente → ofrece abrir la página de descarga.

## 6. Manejo de errores

| Situación | Resultado |
|---|---|
| `signature` ausente | `validate_download_manifest` lanza `ValueError`; la UI ofrece la página de descarga |
| `signature` no hexadecimal o de longitud ≠ 512 | igual que firma inválida |
| Firma válida para otro `version`/`sha256`/`filename` | firma inválida |
| Clave pública no configurada | firma inválida (falla cerrado) + aviso en el log |
| Campo del manifiesto con `\n`/`\r` | se rechaza antes de verificar |
| Fallo de red/descarga | sin cambios respecto a hoy |

Ningún camino ejecuta un instalador cuya firma no haya verificado.

## 7. Pruebas

Los tests generan un par de claves RSA de prueba con `cryptography`
(`pytest.importorskip` para entornos sin ella) y parchean la clave pública del
módulo; **nunca** usan la clave real.

- `tests/test_update_signature.py`: firma válida verifica; manipular
  `version`, `filename` o `sha256` invalida; firma de 255/257 bytes, no hex,
  vacía o `None`; bloque con relleno corrupto (comparación del bloque
  completo); clave sin configurar falla cerrado; `signed_message` rechaza
  saltos de línea; el prefijo de dominio importa (firma sobre otro prefijo no
  verifica).
- `tests/test_updater_secure.py` (ampliado): `validate_download_manifest`
  rechaza manifiestos sin firma o con firma inválida y acepta uno firmado;
  `download_verified_update` no escribe ni deja `.part` si la firma falla;
  los tests actuales se actualizan para usar manifiestos firmados.
- `tests/test_update_check_controller.py` (ampliado): con firma válida ofrece
  descarga segura; sin firma ofrece abrir la página y no lanza
  `download_verified_update`.
- `tests/test_sign_manifest.py`: `sign` produce una firma que la app
  verifica; `keygen` se niega a escribir dentro del repo y a sobrescribir.

## 8. Riesgos y decisiones abiertas

- **Custodia de la clave privada.** La genera y guarda el autor, fuera del
  repo y con copia de seguridad. Si se **pierde**, ninguna versión instalada
  podrá verificar actualizaciones nuevas: habría que publicar a mano una
  versión con otra clave pública. Si se **filtra**, quien la tenga puede
  firmar instaladores maliciosos que las versiones instaladas aceptarán; la
  única mitigación es publicar a mano una versión con clave nueva.
- **Sin rotación de claves.** Hay una sola clave embebida. Soportar varias
  claves o una cadena de confianza queda fuera de esta versión (YAGNI hasta
  que haga falta).
- **Orden de despliegue.** El código y la herramienta se pueden publicar
  antes de que exista la clave real, pero hasta que el autor ejecute `keygen`
  y pegue la clave pública, las versiones nuevas no podrán descargar
  actualizaciones automáticamente (caen a "abrir la página de descarga").
  Por eso el orden recomendado es: `keygen` → pegar la clave pública →
  publicar la versión con la verificación → firmar los manifiestos desde
  entonces.
- **Mantenimiento de dos repos.** El código de la app vive también en
  `TDTRadioVIP-Free` (sincronización manual, ver `RELEASE.md`); estos cambios
  deben llevarse allí para que la edición Free verifique firmas.
- **Implementación en Python puro.** La verificación RSA con `pow()` no es de
  tiempo constante, pero opera solo con datos públicos (clave pública, firma
  y mensaje), así que no hay secreto que filtrar por canal lateral.

## 9. Archivos afectados

Nuevos: `core/update_signature.py`, `tools/sign_manifest.py`,
`tests/test_update_signature.py`, `tests/test_sign_manifest.py`.
Modificados: `core/updater.py`, `ui/update_check_controller.py`,
`tests/test_updater_secure.py`, `tests/test_update_check_controller.py`,
`RELEASE.md`, `requirements-dev.txt`, `.gitignore`,
`.github/workflows/ci.yml`.
