import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage

import escanear_videos as escanear_mod
from escanear_videos import (
    CANTIDAD_PREVIEWS,
    _es_archivo_preview,
    _metadata_reutilizable,
    asegurar_miniaturas,
    combinar_registros_con_ffprobe,
    combinar_registros_con_miniaturas,
    combinar_registros_con_tamanos,
    conectar_bd,
    eliminar_marcador,
    eliminar_segmento,
    escanear_videos,
    generar_previews_faltantes,
    guardar_marcador,
    guardar_segmento,
    guardar_video,
    guardar_videos,
    listar_marcadores,
    listar_marcadores_de,
    listar_registros_por_nombres,
    listar_segmentos,
    listar_videos,
    listar_videos_paginado,
    obtener_datos_ffprobe,
    obtener_tamanos_archivos,
    preparar_registros_basicos,
    previews_existentes,
)
from exploracion_cache import (
    FOTOGRAMAS_INICIALES,
    duracion_valida,
    duracion_video,
    generar_fotogramas,
    listar_fotogramas_version,
    objetivo_total_densidad,
    ruta_fotograma_version,
    version_actual,
)
from exploracion_temporal import tiempos_objetivo
from rutas import ruta_carpeta_videos
from tareas import TareaBase


def rutas_videos():
    carpeta = ruta_carpeta_videos()
    return [os.path.join(carpeta, nombre) for nombre in escanear_videos(carpeta)]


class TareaFFprobe(TareaBase):
    def __init__(
        self,
        rutas,
        nombres=None,
        stats=None,
        ruta_db=None,
        parent=None,
    ):
        super().__init__(parent)
        if rutas is None:
            rutas = []
        if isinstance(rutas, str):
            rutas = [rutas]
        self._rutas = list(rutas)
        self._nombres = list(nombres) if nombres is not None else None
        self._stats = stats
        self._ruta_db = ruta_db

    @property
    def rutas(self):
        return list(self._rutas)

    @property
    def nombres(self):
        return list(self._nombres) if self._nombres is not None else None

    @property
    def stats(self):
        return self._stats

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        resultados = []
        total = len(self._rutas)
        registros = None
        stats_por_ruta = {}
        if (
            self._nombres is not None
            and self._stats is not None
            and self._ruta_db is not None
        ):
            registros = listar_registros_por_nombres(
                self._nombres, self._ruta_db
            )
            for item in (self._stats.get("resultados") or []):
                if isinstance(item, dict) and isinstance(item.get("ruta"), str):
                    stats_por_ruta[item["ruta"]] = item
        for indice, ruta in enumerate(self._rutas):
            nombre = None
            if self._nombres is not None and indice < len(self._nombres):
                nombre = self._nombres[indice]
            reutilizado = False
            if registros is not None and nombre is not None:
                registro = registros.get(nombre)
                stat = stats_por_ruta.get(ruta)
                if _metadata_reutilizable(registro, ruta, stat):
                    resultados.append(
                        {
                            "ruta": ruta,
                            "datos": {
                                "duracion_segundos": registro[
                                    "duracion_segundos"
                                ],
                                "ancho": registro["ancho"],
                                "alto": registro["alto"],
                                "codec_video": registro["codec_video"],
                            },
                            "error": None,
                        }
                    )
                    reutilizado = True
            if not reutilizado:
                resultados.append(self._procesar_uno(ruta))
            self.reportar_progreso(indice + 1, total)
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


class TareaTamanosArchivos(TareaBase):
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
        return obtener_tamanos_archivos(
            self._videos, self._carpeta, self.reportar_progreso
        )


class TareaMiniaturas(TareaBase):
    def __init__(self, videos, carpeta, duraciones=None, parent=None):
        super().__init__(parent)
        if videos is None:
            videos = []
        if isinstance(videos, str):
            videos = [videos]
        self._videos = list(videos)
        self._carpeta = carpeta
        self._duraciones = dict(duraciones) if duraciones is not None else None

    @property
    def videos(self):
        return list(self._videos)

    @property
    def carpeta(self):
        return self._carpeta

    @property
    def duraciones(self):
        return dict(self._duraciones) if self._duraciones is not None else None

    def _trabajo(self):
        return asegurar_miniaturas(
            self._videos,
            self._carpeta,
            self.reportar_progreso,
            self._duraciones,
        )


class TareaPreviewsProgresivas(TareaBase):
    def __init__(self, videos, carpeta, duraciones=None, parent=None):
        super().__init__(parent)
        if videos is None:
            videos = []
        if isinstance(videos, str):
            videos = [videos]
        self._videos = list(videos)
        self._carpeta = carpeta
        self._duraciones = dict(duraciones) if duraciones is not None else None

    @property
    def videos(self):
        return list(self._videos)

    @property
    def carpeta(self):
        return self._carpeta

    @property
    def duraciones(self):
        return dict(self._duraciones) if self._duraciones is not None else None

    def _trabajo(self):
        return generar_previews_faltantes(
            self._videos, self._carpeta, self._duraciones
        )


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
        return guardar_videos(
            self._datos, self._ruta_db, self.reportar_progreso
        )


class TareaSincronizacionCatalogo(TareaBase):
    def __init__(
        self, carpeta, ruta_db=None, parent=None, carpetas_protegidas=None
    ):
        super().__init__(parent)
        self._carpeta = carpeta
        self._ruta_db = ruta_db
        self._carpetas_protegidas = carpetas_protegidas

    @property
    def carpeta(self):
        return self._carpeta

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        diferencias = escanear_mod.detectar_diferencias(
            self._carpeta, self._ruta_db, self._carpetas_protegidas
        )
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


class TareaListarMarcadores(TareaBase):
    """Lee los marcadores persistidos de un video (B4.2)."""

    def __init__(self, video_id, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_marcadores(self._video_id, self._ruta_db)


class TareaListarMarcadoresVarios(TareaBase):
    """Lee los marcadores persistidos de varios videos (B4.4)."""

    def __init__(self, video_ids, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_ids = list(video_ids)
        self._ruta_db = ruta_db

    @property
    def video_ids(self):
        return list(self._video_ids)

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_marcadores_de(self._video_ids, self._ruta_db)


class TareaGuardarMarcador(TareaBase):
    """Persiste un marcador y devuelve su `id` de la base (B4.2)."""

    def __init__(self, video_id, tiempo, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._tiempo = tiempo
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def tiempo(self):
        return self._tiempo

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return guardar_marcador(self._video_id, self._tiempo, self._ruta_db)


class TareaEliminarMarcador(TareaBase):
    """Elimina un marcador persistido por su `id` (B4.2)."""

    def __init__(self, marcador_id, ruta_db=None, parent=None):
        super().__init__(parent)
        self._marcador_id = marcador_id
        self._ruta_db = ruta_db

    @property
    def marcador_id(self):
        return self._marcador_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return eliminar_marcador(self._marcador_id, self._ruta_db)


class TareaListarSegmentos(TareaBase):
    """Lee los segmentos persistidos de un video (B5.2).

    Delegación exclusiva en `listar_segmentos`; devuelve el contrato
    `[(id, inicio, fin)]`.
    """

    def __init__(self, video_id, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return listar_segmentos(self._video_id, self._ruta_db)


class TareaGuardarSegmento(TareaBase):
    """Persiste un segmento y devuelve `(id, inicio, fin)` (B5.2).

    Disponible para la UI desde B5.4; en B5.2 no existe todavía ninguna
    acción de usuario que lo invoque.
    """

    def __init__(self, video_id, inicio, fin, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._inicio = inicio
        self._fin = fin
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def inicio(self):
        return self._inicio

    @property
    def fin(self):
        return self._fin

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return guardar_segmento(
            self._video_id, self._inicio, self._fin, self._ruta_db
        )


class TareaEliminarSegmento(TareaBase):
    """Elimina un segmento persistido por su `id` (B5.2).

    Devuelve el booleano de `eliminar_segmento`. Disponible para la UI
    desde B5.4; en B5.2 no existe todavía ninguna acción de usuario que lo
    invoque.
    """

    def __init__(self, segmento_id, ruta_db=None, parent=None):
        super().__init__(parent)
        self._segmento_id = segmento_id
        self._ruta_db = ruta_db

    @property
    def segmento_id(self):
        return self._segmento_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return eliminar_segmento(self._segmento_id, self._ruta_db)


class TareaExploracionDensa(TareaBase):
    """Genera o completa la caché densa de exploración temporal (B4.3.2).

    El trabajo corre en el hilo del gestor: `generar_fotogramas` invoca
    FFmpeg una vez por fotograma faltante de la versión actual y la
    cancelación es cooperativa (se revisa entre fotogramas). Un solo
    FFmpeg activo en todo momento.

    La generación es en dos fases secuenciales:
    - Fase rápida: los `FOTOGRAMAS_INICIALES` prioritarios, sin cambio de
      comportamiento respecto de Etapa 1.
    - Fase secundaria: solo si el objetivo total (auto por duración o
      manual `objetivo_manual`) supera la fase rápida, se completa hasta
      ese total reutilizando lo ya existente y generando únicamente los
      faltantes (nunca se regeneran los ya presentes). El objetivo manual
      (B4.3.3) permite pedir una cantidad fija incluso en videos cortos;
      la distribución siempre usa `tiempos_objetivo(duración, total)`.

    Además de reportar progreso, emite `resultado_parcial` con los
    fotogramas que ya están disponibles en disco (ms + QImage decodificada
    en el hilo del worker) en ambas fases. Así la GUI incorpora resultados
    de forma progresiva y la lectura/decodificación JPEG queda en el
    worker, no en el hilo de la GUI.
    """

    resultado_parcial = Signal(object)

    def __init__(self, video_id, ruta_video, duracion=None, cantidad=None,
                 parent=None, objetivo_manual=None):
        super().__init__(parent)
        self._video_id = video_id
        self._ruta_video = ruta_video
        self._duracion = duracion
        self._cantidad = cantidad
        self._objetivo_manual = objetivo_manual
        self._cancelada = False
        self._emitidos = set()

    @property
    def video_id(self):
        return self._video_id

    @property
    def ruta_video(self):
        return self._ruta_video

    @property
    def duracion(self):
        return self._duracion

    @property
    def cantidad(self):
        return self._cantidad

    @property
    def objetivo_manual(self):
        return self._objetivo_manual

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        duracion = self._duracion
        if not duracion_valida(duracion):
            duracion = duracion_video(self._ruta_video)
        fase_rapida = self._cantidad
        if fase_rapida is None or fase_rapida <= 0:
            fase_rapida = FOTOGRAMAS_INICIALES
        manual = self._objetivo_manual
        if isinstance(manual, bool) or not isinstance(manual, int):
            manual = None
        if manual is not None and manual > 0:
            objetivo_total = manual
        elif duracion_valida(duracion):
            objetivo_total = objetivo_total_densidad(duracion)
        else:
            objetivo_total = 0
        emitidos = self._emitidos
        permitidos = set()

        def _fase(cantidad):
            nonlocal permitidos
            if not duracion_valida(duracion):
                version = None
                permitidos = set()
            else:
                # Conjunto permitido de esta fase: exactamente los instantes
                # objetivo de `cantidad`. La caché en disco puede contener un
                # superset (densidades manuales previas); la tarea decide qué
                # subconjunto utiliza y nunca emite fotogramas ajenos a él.
                permitidos = set(tiempos_objetivo(duracion, cantidad))
                version = version_actual(
                    self._video_id, self._ruta_video, duracion
                )

            def al_progreso(procesado, total):
                self.reportar_progreso(procesado, total)
                if self._cancelada or version is None or not permitidos:
                    return
                presentes = listar_fotogramas_version(
                    self._video_id, version
                )
                nuevos = [
                    ms
                    for ms in presentes
                    if ms in permitidos and ms not in emitidos
                ]
                if not nuevos:
                    return
                imagenes = []
                for ms in nuevos:
                    ruta = ruta_fotograma_version(self._video_id, ms, version)
                    imagen = QImage(ruta)
                    if imagen.isNull():
                        continue
                    imagenes.append((ms, imagen))
                    emitidos.add(ms)
                if imagenes:
                    self.resultado_parcial.emit({
                        "video_id": self._video_id,
                        "version": version,
                        "fotogramas": imagenes,
                    })

            return generar_fotogramas(
                self._video_id,
                self._ruta_video,
                duracion=duracion,
                cantidad=cantidad,
                on_progreso=al_progreso,
                cancelar=lambda: self._cancelada,
            )

        resultado = _fase(fase_rapida)
        if (
            objetivo_total > fase_rapida
            and isinstance(resultado, dict)
            and not resultado.get("cancelado")
            and resultado.get("version")
            and not self._cancelada
        ):
            resultado = _fase(objetivo_total)
        if (
            isinstance(resultado, dict)
            and resultado.get("version")
            and not resultado.get("cancelado")
            and permitidos
        ):
            imagenes = []
            for ms in resultado.get("fotogramas") or []:
                if ms in permitidos and ms not in emitidos:
                    ruta = ruta_fotograma_version(
                        self._video_id, ms, resultado["version"]
                    )
                    imagen = QImage(ruta)
                    if not imagen.isNull():
                        imagenes.append((ms, imagen))
            if imagenes:
                resultado = dict(resultado)
                resultado["imagenes"] = imagenes
        return resultado
