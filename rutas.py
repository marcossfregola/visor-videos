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


def ruta_carpeta_exploracion():
    return os.path.join(ruta_raiz(), "miniaturas", "exploracion")


def ruta_carpeta_videos():
    return os.path.join(ruta_raiz(), "videos_prueba")


def ruta_configuracion():
    return os.path.join(ruta_raiz(), "configuracion.json")


def ruta_video_existente(carpeta, nombre):
    """Devuelve la ruta absoluta de un video si la carpeta y el archivo existen.

    La UI delega aqui la comprobacion de existencia para no acceder
    directamente al filesystem. Devuelve `None` si `carpeta` no es una
    carpeta valida, `nombre` no es texto o el archivo no existe.
    """
    if not isinstance(nombre, str) or not nombre:
        return None
    if not isinstance(carpeta, str) or not carpeta:
        return None
    ruta = os.path.join(carpeta, nombre)
    if not os.path.isdir(carpeta) or not os.path.isfile(ruta):
        return None
    return ruta
