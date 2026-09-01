"""
Compila core/license.py a una extensión nativa (.pyd en Windows) con Cython.
Coder By X@R

QUÉ HACE Y POR QUÉ
-------------------
PyInstaller, tal cual está configurado en TDTRadioVIP.spec, empaqueta el
resto de la app como bytecode Python normal dentro de un archivo .pyz —
cualquiera con pyinstxtractor + un descompilador (decompyle3) lo recupera
como código fuente legible en segundos. Para el módulo de licencias en
concreto (el que decide si la app está activada o no) eso es justo lo que
no interesa, aunque ya se ofuscó la clave secreta dentro de license.py.

Este script compila SOLO core/license.py a un binario nativo de verdad
(C compilado, no bytecode Python). Quien intente extraerlo del .exe se
encuentra con una extensión .pyd -- ingeniería inversa de binario real
(Ghidra/IDA), no "abrir con un descompilador de Python". El resto de la
app (interfaz, reproductor, descargas...) sigue siendo Python normal; no
merece la pena el riesgo de compilar todo eso y este módulo es el único
que de verdad importa proteger.

core/license.py SIGUE SIENDO la fuente de verdad -- edítalo como siempre.
Este script no lo borra ni lo toca; genera un .pyd junto a él, y Python
(tanto en desarrollo como dentro del propio proceso de build) prefiere
automáticamente el .pyd sobre el .py cuando ambos existen, así que no
hace falta ningún paso extra para probarlo en local. TDTRadioVIP.spec /
TDTRadioVIP_Free.spec ya están preparados para incluir el .pyd compilado
en vez del .py plano si lo encuentran (ver la sección "Módulo de licencia
compilado con Cython" en esos ficheros) -- si no lo encuentran, avisan y
siguen empaquetando el .py normal, así que nunca te bloquea una compilación.

USO (necesitas hacerlo cada vez que cambies core/license.py; para el resto
de la app no hace falta tocar esto)
----------------------------------------------------------------------
1. Instala Cython una vez:  pip install cython
2. Necesitas un compilador de C para Windows. El más sencillo: instala
   "Microsoft C++ Build Tools" (gratis) desde
   https://visualstudio.microsoft.com/visual-cpp-build-tools/
   marcando el paquete "Desktop development with C++".
3. Compila con EL MISMO intérprete que luego uses para PyInstaller (el
   proyecto usa Python 3.12 -- ver README, PyInstaller da problemas con
   3.14). Si tienes varias versiones instaladas, no confíes en que
   "python" del PATH sea la correcta: comprueba antes con
   "python --version" o usa la ruta completa del intérprete de 3.12
   (p. ej. "py -3.12 setup_license.py build_ext --inplace" con el
   launcher de Windows). El bloque IMPORTANTE de abajo imprime qué
   intérprete se está usando para que sea evidente si es el equivocado.
4. Compila:  python setup_license.py build_ext --inplace
5. Comprueba que se ha creado core/license.<algo>.pyd (el nombre exacto
   incluye tu versión de Python y arquitectura, p.ej.
   license.cp312-win_amd64.pyd). Puedes borrar la carpeta build/ que
   queda al lado, es temporal.
6. Compila la app como siempre (PyInstaller con el .spec) -- TDTRadioVIP.spec
   comprueba automáticamente que el tag del .pyd (p. ej. "cp312") coincide
   con el intérprete que corre PyInstaller, y si no coincide lo ignora con
   un aviso en vez de empaquetar un EXE roto -- pero es mejor no depender
   de esa red de seguridad y compilar ya con el intérprete correcto desde
   el principio.

Si algún día quieres deshacer esto: borra el .pyd de core/ y ya está,
la app vuelve a usar core/license.py normal sin tocar nada más.
"""
import sys

from setuptools import setup
from Cython.Build import cythonize

# IMPORTANTE: el .pyd resultante solo sirve si PyInstaller empaqueta la app
# con ESTE MISMO intérprete. Se imprime bien visible para detectar a
# tiempo un "python" del PATH apuntando a una versión distinta de la que
# se usará luego para compilar el EXE (ver TDTRadioVIP.spec para la
# comprobación automática en el otro extremo).
print(
    f"[setup_license] Compilando con {sys.executable} "
    f"(Python {sys.version_info.major}.{sys.version_info.minor}, "
    f"tag cp{sys.version_info.major}{sys.version_info.minor}). "
    "Usa este MISMO intérprete para compilar el EXE con PyInstaller."
)

setup(
    name="tdtradiovip_license_ext",
    ext_modules=cythonize(
        ["core/license.py"],
        language_level="3",
        # Sin esto, un error en tiempo de ejecución dentro del módulo
        # compilado señalaría números de línea del .c generado en vez del
        # license.py real -- inútil para depurar. Con annotate=True además
        # se genera un license.html que colorea qué líneas siguen tirando
        # de la API de Python (amarillo) frente a C puro (blanco); no hace
        # falta mirarlo nunca, pero está ahí si un día hay que optimizar.
        compiler_directives={"language_level": "3", "embedsignature": False},
        annotate=False,
    ),
)
