import os

RUTA_RAIZ = os.path.dirname(os.path.abspath(__file__))


def ruta_raiz():
    return RUTA_RAIZ


def ruta_biblioteca():
    return os.path.join(ruta_raiz(), "biblioteca.db")


def ruta_carpeta_miniaturas():
    return os.path.join(ruta_raiz(), "miniaturas")


def ruta_carpeta_videos():
    return os.path.join(ruta_raiz(), "videos_prueba")
