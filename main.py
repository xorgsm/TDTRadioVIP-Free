"""
TDT & Radio VIP - Coder By X@R
Punto de entrada de la aplicación.
"""
# Debe hacerse ANTES de crear QApplication y antes de importar player.vlc_player
# -- ver los porqués en core/bootstrap.py (id distinto de main_free.py para
# que Windows no mezcle ambas builds en la barra de tareas si están las dos
# instaladas a la vez).
from core.bootstrap import bootstrap

bootstrap("CoderByXR.TDTRadioVIP.Licenciada")

from ui.application import run_vip


def main():
    return run_vip()


if __name__ == "__main__":
    raise SystemExit(main())
