import os

import escanear_videos as escanear_mod
from escanear_videos import (
    asegurar_miniaturas,
    combinar_registros_con_ffprobe,
    combinar_registros_con_miniaturas,
    conectar_bd,
    escanear_videos,
    guardar_video,
    guardar_videos,
    listar_videos,
    listar_videos_paginado,
    obtener_datos_ffprobe,
    preparar_registros_basicos,
)
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


class TareaMiniaturas(TareaBase):
    def __init__(self, videos, carpeta, parent=None):
        super().__init__(parent)
        if videos is None:
            videos = []
        if isinstance(videos, str):
            videos = [videos]
        self._videos = list(videos)
        self._carpeta = carpeta

    @property
    def videos(self):
        return list(self._videos)

    @property
    def carpeta(self):
        return self._carpeta

    def _trabajo(self):
        return asegurar_miniaturas(self._videos, self._carpeta)


class TareaLecturaCatalogo(TareaBase):
    def __init__(self, ruta_db=None, parent=None):
        super().__init__(parent)
        self._ruta_db = ruta_db

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_videos(self._ruta_db)


class TareaLecturaCatalogoPaginada(TareaBase):
    def __init__(self, limite, desplazamiento=0, texto=None, ruta_db=None, parent=None):
        super().__init__(parent)
        self._limite = limite
        self._desplazamiento = desplazamiento
        self._texto = texto
        self._ruta_db = ruta_db

    @property
    def limite(self):
        return self._limite

    @property
    def desplazamiento(self):
        return self._desplazamiento

    @property
    def texto(self):
        return self._texto

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_videos_paginado(
            self._limite,
            self._desplazamiento,
            self._texto,
            self._ruta_db,
        )


class TareaGuardarVideo(TareaBase):
    def __init__(self, datos, ruta_db=None, parent=None):
        super().__init__(parent)
        try:
            self._datos = dict(datos)
            self._datos_invalidos = None
        except (TypeError, ValueError) as exc:
            self._datos = None
            self._datos_invalidos = exc
        self._ruta_db = ruta_db

    @property
    def datos(self):
        return dict(self._datos) if isinstance(self._datos, dict) else self._datos

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        if self._datos_invalidos is not None:
            raise TypeError(f"datos inválidos: {self._datos_invalidos}")
        return guardar_video(self._datos, self._ruta_db)


class TareaGuardarVideos(TareaBase):
    def __init__(self, datos_videos, ruta_db=None, parent=None):
        super().__init__(parent)
        try:
            if isinstance(datos_videos, (str, bytes, bytearray)):
                raise TypeError("datos_videos debe ser una colección, no texto")
            self._datos = [dict(d) for d in list(datos_videos)]
            self._datos_invalidos = None
        except Exception as exc:
            self._datos = []
            self._datos_invalidos = exc
        self._ruta_db = ruta_db

    @property
    def datos(self):
        return [dict(d) for d in self._datos]

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        if self._datos_invalidos is not None:
            raise TypeError(f"colección inválida: {self._datos_invalidos}")
        return guardar_videos(self._datos, self._ruta_db)


class TareaSincronizacionCatalogo(TareaBase):
    def __init__(self, carpeta, ruta_db=None, parent=None):
        super().__init__(parent)
        self._carpeta = carpeta
        self._ruta_db = ruta_db

    @property
    def carpeta(self):
        return self._carpeta

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        diferencias = escanear_mod.detectar_diferencias(self._carpeta, self._ruta_db)
        plan = escanear_mod.preparar_plan_sincronizacion(diferencias)
        incorporaciones = escanear_mod.aplicar_incorporaciones(plan, self._ruta_db)
        eliminaciones = escanear_mod.eliminar_candidatos(plan, self._ruta_db)
        return {
            "diferencias": diferencias,
            "plan": plan,
            "incorporaciones": incorporaciones,
            "eliminaciones": eliminaciones,
            "resumen": {
                "nuevos": len(diferencias["nuevos"]),
                "ya_sincronizados": len(plan["ya_sincronizados"]),
                "incorporados": incorporaciones["incorporados"],
                "eliminados": eliminaciones["eliminados"],
                "candidatos_restantes": eliminaciones["restantes"],
            },
        }
