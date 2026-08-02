import os

from escanear_videos import escanear_videos, listar_videos, obtener_datos_ffprobe
from rutas import ruta_carpeta_videos
from tareas import TareaBase


def rutas_videos():
    carpeta = ruta_carpeta_videos()
    return [os.path.join(carpeta, nombre) for nombre in escanear_videos(carpeta)]


class TareaFFprobe(TareaBase):
    def __init__(self, rutas, parent=None):
        super().__init__(parent)
        if rutas is None:
            rutas = []
        if isinstance(rutas, str):
            rutas = [rutas]
        self._rutas = list(rutas)

    @property
    def rutas(self):
        return list(self._rutas)

    def _trabajo(self):
        resultados = [self._procesar_uno(ruta) for ruta in self._rutas]
        return {
            "rutas": list(self._rutas),
            "resultados": resultados,
            "procesados": len(resultados),
            "con_datos": sum(1 for r in resultados if r["datos"] is not None),
            "con_error": sum(1 for r in resultados if r["error"] is not None),
        }

    def _procesar_uno(self, ruta):
        if not os.path.isfile(ruta):
            return self._resultado(ruta, error="archivo inexistente")
        if os.path.getsize(ruta) == 0:
            return self._resultado(ruta, error="archivo vacio")
        try:
            datos = obtener_datos_ffprobe(ruta)
        except Exception as exc:
            return self._resultado(ruta, error=f"{type(exc).__name__}: {exc}")
        if datos is None:
            return self._resultado(ruta, error="sin metadatos")
        return self._resultado(ruta, datos=datos)

    @staticmethod
    def _resultado(ruta, datos=None, error=None):
        return {"ruta": ruta, "datos": datos, "error": error}


class TareaEscaneo(TareaBase):
    def __init__(self, carpeta, parent=None):
        super().__init__(parent)
        self._carpeta = carpeta

    @property
    def carpeta(self):
        return self._carpeta

    def _trabajo(self):
        return escanear_videos(self._carpeta)


class TareaLecturaCatalogo(TareaBase):
    def __init__(self, ruta_db=None, parent=None):
        super().__init__(parent)
        self._ruta_db = ruta_db

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_videos(self._ruta_db)
