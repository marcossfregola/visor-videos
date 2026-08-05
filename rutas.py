import os
import sys


def _directorio_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


RUTA_RAIZ = _directorio_base()


def ruta_raiz():
    return RUTA_RAIZ


def ruta_biblioteca():
    return os.path.join(ruta_raiz(), "biblioteca.db")


def ruta_carpeta_miniaturas():
    return os.path.join(ruta_raiz(), "miniaturas")


def ruta_carpeta_videos():
    return os.path.join(ruta_raiz(), "videos_prueba")


def ruta_configuracion():
    return os.path.join(ruta_raiz(), "configuracion.json")
