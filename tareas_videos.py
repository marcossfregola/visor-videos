import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage

import escanear_videos as escanear_mod
from escanear_videos import (
    CANTIDAD_PREVIEWS,
    _es_archivo_preview,
    _metadata_reutilizable,
    actualizar_segmento,
    asignar_color_marcador,
    asignar_color_segmento,
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
    listar_segmentos_de,
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
    def __init__(
        self,
        limite,
        desplazamiento=0,
        texto=None,
        ruta_db=None,
        orden_clave=None,
        orden_direccion=None,
        filtro=None,
        carpeta=None,
        incluir_subcarpetas=False,
        parent=None,
    ):
        super().__init__(parent)
        self._limite = limite
        self._desplazamiento = desplazamiento
        self._texto = texto
        self._ruta_db = ruta_db
        self._orden_clave = orden_clave
        self._orden_direccion = orden_direccion
        self._filtro = filtro
        self._carpeta = carpeta
        self._incluir_subcarpetas = bool(incluir_subcarpetas) if isinstance(incluir_subcarpetas, bool) else False

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

    @property
    def orden_clave(self):
        return self._orden_clave

    @property
    def orden_direccion(self):
        return self._orden_direccion

    @property
    def filtro(self):
        return self._filtro

    @property
    def carpeta(self):
        return self._carpeta

    @property
    def incluir_subcarpetas(self):
        return self._incluir_subcarpetas

    def _trabajo(self):
        return listar_videos_paginado(
            self._limite,
            self._desplazamiento,
            self._texto,
            self._ruta_db,
            orden_clave=self._orden_clave,
            orden_direccion=self._orden_direccion,
            filtro=self._filtro,
            carpeta=self._carpeta,
            incluir_subcarpetas=self._incluir_subcarpetas,
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
    """Persiste un marcador y devuelve su `id` de la base (B4.2).

    `color` (B6.3) es opcional: clave estable de `COLORES_CLASIFICACION` o
    `None`. Se persiste en el mismo INSERT de creación.
    """

    def __init__(self, video_id, tiempo, ruta_db=None, parent=None, color=None):
        super().__init__(parent)
        self._video_id = video_id
        self._tiempo = tiempo
        self._color = color
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def tiempo(self):
        return self._tiempo

    @property
    def color(self):
        return self._color

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return guardar_marcador(
            self._video_id, self._tiempo, self._ruta_db, self._color
        )


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


class TareaAsignarColorMarcador(TareaBase):
    """Asigna (o quita) el color de clasificación de un marcador (B6.3).

    `color` es una clave estable de `COLORES_CLASIFICACION` o `None`.
    Devuelve la fila persistida `(id, video_id, tiempo, color)` o `None`.
    """

    def __init__(self, marcador_id, color, ruta_db=None, parent=None):
        super().__init__(parent)
        self._marcador_id = marcador_id
        self._color = color
        self._ruta_db = ruta_db

    @property
    def marcador_id(self):
        return self._marcador_id

    @property
    def color(self):
        return self._color

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return asignar_color_marcador(
            self._marcador_id, self._color, self._ruta_db
        )


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


class TareaListarSegmentosVarios(TareaBase):
    """Lee los segmentos persistidos de varios videos (B5.8).

    Delegación exclusiva en `listar_segmentos_de` (una sola consulta SQL);
    devuelve el contrato `[(id, video_id, inicio, fin)]`.
    """

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
        return listar_segmentos_de(self._video_ids, self._ruta_db)


class TareaGuardarSegmento(TareaBase):
    """Persiste un segmento y devuelve `(id, inicio, fin)` (B5.2).

    `color` (B6.3) es opcional: clave estable de `COLORES_CLASIFICACION` o
    `None`. Se persiste en el mismo INSERT de creación.

    Disponible para la UI desde B5.4; en B5.2 no existe todavía ninguna
    acción de usuario que lo invoque.
    """

    def __init__(
        self, video_id, inicio, fin, ruta_db=None, parent=None, color=None
    ):
        super().__init__(parent)
        self._video_id = video_id
        self._inicio = inicio
        self._fin = fin
        self._color = color
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
    def color(self):
        return self._color

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return guardar_segmento(
            self._video_id,
            self._inicio,
            self._fin,
            self._ruta_db,
            self._color,
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


class TareaAsignarColorSegmento(TareaBase):
    """Asigna (o quita) el color de clasificación de un segmento (B6.3).

    `color` es una clave estable de `COLORES_CLASIFICACION` o `None`.
    Devuelve la fila persistida `(id, inicio, fin, color)` o `None`.
    """

    def __init__(self, segmento_id, color, ruta_db=None, parent=None):
        super().__init__(parent)
        self._segmento_id = segmento_id
        self._color = color
        self._ruta_db = ruta_db

    @property
    def segmento_id(self):
        return self._segmento_id

    @property
    def color(self):
        return self._color

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        return asignar_color_segmento(
            self._segmento_id, self._color, self._ruta_db
        )


class TareaActualizarSegmento(TareaBase):
    """Actualiza los límites de un segmento persistido por su `id` (Pulido #4).

    Conserva `id` y `video_id` (UPDATE, nunca delete+insert). Devuelve
    `(segmento_id, inicio, fin)` o `None` si el segmento no existía.
    """

    def __init__(self, segmento_id, inicio, fin, ruta_db=None, parent=None):
        super().__init__(parent)
        self._segmento_id = segmento_id
        self._inicio = inicio
        self._fin = fin
        self._ruta_db = ruta_db

    @property
    def segmento_id(self):
        return self._segmento_id

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
        return actualizar_segmento(
            self._segmento_id, self._inicio, self._fin, self._ruta_db
        )


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


class TareaExportarSegmento(TareaBase):
    """Exporta un segmento existente a un archivo nuevo mediante recodificación CPU precisa (B6.7).

    Delegación exclusiva en `exportar_segmento.exportar_segmento` (servicio sin
    Qt). La tarea corre fuera del hilo principal (GestorTareas), sin FFmpeg ni
    SQLite directos desde la UI. Soporta cancelación real: `cancelar()` marca
    el flag y el servicio termina FFmpeg y limpia el temporal.

    B6.11: si se provee `original_video_id` + `segmento_id` + `ruta_db`, tras
    verificación exitosa intenta alta incremental en catálogo con trazabilidad
    (sin reescaneo completo, fuera del hilo UI, sin borrar archivo si falla
    catalogación). El resultado añade `alta_catalogo` con el dict de
    `incorporar_video_derivado_al_catalogo` sin romper el contrato previo.
    """

    def __init__(self, fuente, inicio, fin, destino, parent=None, original_video_id=None, segmento_id=None, ruta_db=None):
        super().__init__(parent)
        self._fuente = fuente
        self._inicio = inicio
        self._fin = fin
        self._destino = destino
        self._cancelada = False
        self._original_video_id = original_video_id
        self._segmento_id = segmento_id
        self._ruta_db = ruta_db

    @property
    def fuente(self):
        return self._fuente

    @property
    def inicio(self):
        return self._inicio

    @property
    def fin(self):
        return self._fin

    @property
    def destino(self):
        return self._destino

    @property
    def original_video_id(self):
        return self._original_video_id

    @property
    def segmento_id(self):
        return self._segmento_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        import exportar_segmento as exp
        import escanear_videos as escanear_mod

        resultado = exp.exportar_segmento(
            self._fuente,
            self._inicio,
            self._fin,
            self._destino,
            cancel_check=lambda: self._cancelada,
        )
        # B6.11 alta incremental si corresponde (solo si exportación ok y no cancelada)
        if (
            resultado.get("ok")
            and not resultado.get("cancelado")
            and self._original_video_id is not None
            and self._segmento_id is not None
            and self._ruta_db is not None
        ):
            # Evitar trabajo si fue cancelado entre tanto
            if not self._cancelada:
                try:
                    alta = escanear_mod.incorporar_video_derivado_al_catalogo(
                        resultado.get("salida"),
                        self._original_video_id,
                        [{"segmento_id": int(self._segmento_id), "inicio": float(self._inicio), "fin": float(self._fin)}],
                        tipo="individual",
                        ruta_db=self._ruta_db,
                    )
                except Exception as exc:
                    alta = {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"excepción en alta: {exc}", "catalog_error": True}
                resultado = dict(resultado)
                resultado["alta_catalogo"] = alta
                # Si alta falla, conservar archivo y exponer error claramente (no revertir exportación)
                if not alta.get("ok"):
                    resultado["alta_catalogo_error"] = alta.get("error")
        return resultado


class TareaResumenColapsado(TareaBase):
    """Carga batch del resumen colapsado (B6.4).

    En un único worker (fuera del hilo principal) y sin SQLite desde la UI,
    obtiene para un lote de `video_ids` la metadata mínima necesaria para
    pintar la barra colapsada: marcadores `(id, video_id, tiempo, color)` y
    segmentos `(id, video_id, inicio, fin, color)`. No carga pixmaps ni
    previews densos. Usa las operaciones batch existentes
    `listar_marcadores_de` / `listar_segmentos_de` (una sola consulta por
    tipo), por lo que un lote de N tarjetas se resuelve con 2 consultas en
    1 tarea, no N tareas.
    """

    def __init__(self, video_ids, ruta_db=None, parent=None):
        super().__init__(parent)
        if isinstance(video_ids, (str, bytes, bytearray)):
            raise TypeError("video_ids debe ser una colección, no texto")
        try:
            self._video_ids = list(video_ids)
        except TypeError:
            raise TypeError("video_ids debe ser una colección iterable") from None
        self._ruta_db = ruta_db

    @property
    def video_ids(self):
        return list(self._video_ids)

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        # Solo metadata mínima; nunca pixmaps.
        marcadores = listar_marcadores_de(self._video_ids, self._ruta_db)
        segmentos = listar_segmentos_de(self._video_ids, self._ruta_db)
        return {
            "video_ids": list(self._video_ids),
            "marcadores": marcadores,
            "segmentos": segmentos,
        }


class TareaExportarLoteSegmentos(TareaBase):
    """Exportación múltiple de segmentos separados (B6.9).

    Procesa un lote secuencialmente (un solo FFmpeg activo), planificando
    nombres mediante el motor B6.8 y delegando cada item a B6.7
    `exportar_segmento`. Recibe items ya resueltos (desacoplados de widgets)
    o bien `video_ids` + `filtro_color` para resolverlos en background sin
    SQLite/FFmpeg desde la UI. Emite progreso `actual/total` vía
    `reportar_progreso` y devuelve resultado estructurado
    `{exitos, fallos, omitidos, cancelados, total, cancelado}`.
    Arquitectura preparada para recibir lista explícita de IDs (items).
    """

    def __init__(
        self,
        carpeta_destino,
        video_ids=None,
        filtro_color=escanear_mod._SIN_FILTRO_LOTE,
        items=None,
        extension=".mp4",
        ruta_db=None,
        parent=None,
    ):
        super().__init__(parent)
        self._carpeta_destino = carpeta_destino
        self._video_ids = list(video_ids) if video_ids is not None else None
        self._filtro_color = filtro_color
        self._items_input = None
        if items is not None:
            if isinstance(items, (str, bytes, bytearray)):
                raise TypeError("items debe ser una colección, no texto")
            try:
                self._items_input = [dict(it) for it in list(items)]
            except Exception as exc:
                raise TypeError(f"items inválidos: {exc}") from None
        self._extension = extension if isinstance(extension, str) and extension else ".mp4"
        self._ruta_db = ruta_db
        self._cancelada = False

    @property
    def carpeta_destino(self):
        return self._carpeta_destino

    @property
    def video_ids(self):
        return list(self._video_ids) if self._video_ids is not None else None

    @property
    def filtro_color(self):
        return self._filtro_color

    @property
    def extension(self):
        return self._extension

    @property
    def ruta_db(self):
        return self._ruta_db

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        import exportar_segmento as exp
        import nombres as nom
        import escanear_videos as escanear_mod

        carpeta = self._carpeta_destino
        # Validar destino base (no escribible se reportará por item, pero lote vacío y destino inválido se maneja)
        if not isinstance(carpeta, str) or not carpeta.strip():
            return {
                "exitos": [],
                "fallos": [{"error": "carpeta destino inválida"}],
                "omitidos": [],
                "cancelados": [],
                "total": 0,
                "cancelado": False,
                "procesados": 0,
            }
        if not os.path.isdir(carpeta):
            return {
                "exitos": [],
                "fallos": [{"error": f"carpeta destino no existe: {carpeta}"}],
                "omitidos": [],
                "cancelados": [],
                "total": 1 if self._items_input or self._video_ids else 0,
                "cancelado": False,
                "procesados": 0,
            }

        # Resolver items si no vienen explícitos
        items = self._items_input
        if items is None:
            if self._video_ids is None or not self._video_ids:
                # lote vacío: sin video_ids ni items
                return {
                    "exitos": [],
                    "fallos": [],
                    "omitidos": [],
                    "cancelados": [],
                    "total": 0,
                    "cancelado": False,
                    "procesados": 0,
                }
            # Validar filtro color
            try:
                escanear_mod._validar_filtro_color_lote(self._filtro_color)
            except Exception as exc:
                return {
                    "exitos": [],
                    "fallos": [{"error": f"filtro color inválido: {exc}"}],
                    "omitidos": [],
                    "cancelados": [],
                    "total": 0,
                    "cancelado": False,
                    "procesados": 0,
                }
            # Obtener segmentos filtrados en batch (sin SQLite desde UI, aquí en worker)
            try:
                segmentos = escanear_mod.listar_segmentos_por_videos(
                    self._video_ids, color=self._filtro_color, ruta_db=self._ruta_db
                )
            except Exception as exc:
                return {
                    "exitos": [],
                    "fallos": [{"error": f"no se pudieron listar segmentos: {exc}"}],
                    "omitidos": [],
                    "cancelados": [],
                    "total": 0,
                    "cancelado": False,
                    "procesados": 0,
                }
            if not segmentos:
                return {
                    "exitos": [],
                    "fallos": [],
                    "omitidos": [],
                    "cancelados": [],
                    "total": 0,
                    "cancelado": False,
                    "procesados": 0,
                }
            # Mapear video_id -> nombre/ruta
            try:
                vmap = escanear_mod.listar_videos_por_ids(self._video_ids, self._ruta_db)
            except Exception as exc:
                return {
                    "exitos": [],
                    "fallos": [{"error": f"no se pudieron listar videos: {exc}"}],
                    "omitidos": [],
                    "cancelados": [],
                    "total": len(segmentos),
                    "cancelado": False,
                    "procesados": 0,
                }
            items = []
            for seg_id, vid, inicio, fin, color in segmentos:
                info = vmap.get(vid)
                if info is None:
                    continue
                # Validar inicio/fin básicos
                try:
                    ini_f = float(inicio)
                    fin_f = float(fin)
                except Exception:
                    continue
                if not (fin_f > ini_f and ini_f >= 0):
                    continue
                items.append(
                    {
                        "segmento_id": seg_id,
                        "video_id": vid,
                        "ruta_fuente": info["ruta"],
                        "nombre_original": info["nombre"],
                        "inicio": ini_f,
                        "fin": fin_f,
                        "color": color,
                    }
                )
        else:
            # Items explícitos ya desacoplados: validar mínimo
            validados = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                seg_id = it.get("segmento_id")
                vid = it.get("video_id")
                ruta = it.get("ruta_fuente")
                nombre = it.get("nombre_original")
                ini = it.get("inicio")
                fin = it.get("fin")
                if ruta is None and nombre is None:
                    continue
                if ruta is None:
                    ruta = nombre
                if nombre is None:
                    nombre = os.path.basename(ruta) if isinstance(ruta, str) else "video.mp4"
                try:
                    ini_f = float(ini)
                    fin_f = float(fin)
                except Exception:
                    continue
                validados.append(
                    {
                        "segmento_id": seg_id,
                        "video_id": vid,
                        "ruta_fuente": ruta,
                        "nombre_original": nombre,
                        "inicio": ini_f,
                        "fin": fin_f,
                        "color": it.get("color"),
                    }
                )
            items = validados

        total = len(items)
        if total == 0:
            return {
                "exitos": [],
                "fallos": [],
                "omitidos": [],
                "cancelados": [],
                "total": 0,
                "cancelado": False,
                "procesados": 0,
            }

        # Validar extensión
        try:
            ext_norm = nom.validar_extension(self._extension)
        except Exception as exc:
            return {
                "exitos": [],
                "fallos": [{"error": f"extensión inválida: {exc}", "items": items}],
                "omitidos": [],
                "cancelados": [],
                "total": total,
                "cancelado": False,
                "procesados": 0,
            }
        # Verificar escritura en carpeta destino (intento de crear archivo temporal de prueba no, solo check de permiso)
        if not os.access(carpeta, os.W_OK):
            return {
                "exitos": [],
                "fallos": [{"error": "carpeta destino no escribible", "items": items}],
                "omitidos": [],
                "cancelados": [],
                "total": total,
                "cancelado": False,
                "procesados": 0,
            }

        # Planificación de nombres determinista mediante B6.8 (sin crear archivos)
        # Usamos existe_fn que mira FS + lote_set
        lote_set = set()

        def existe_fn(nombre_completo):
            return os.path.exists(os.path.join(carpeta, nombre_completo))

        destinos = []
        fallos_plan = []
        for it in items:
            if self._cancelada:
                # cancelación antes de planificar resto -> omitidos
                break
            try:
                ctx = {
                    "original": it["nombre_original"],
                    "inicio": it["inicio"],
                    "fin": it["fin"],
                }
                # generar nombre único con motor B6.8
                nombre = nom.generar_nombre_unico(
                    nom.PLANTILLA_DEFAULT_B67,
                    ctx,
                    ext_norm,
                    existe_fn=existe_fn,
                    nombres_en_lote=lote_set,
                )
                dest = os.path.join(carpeta, nombre)
                # Validar que no sea el mismo que fuente (no sobrescribir original)
                # Solo errores de normalización se silencian; coincidencia real es fallo de planificación
                norm_dest = None
                norm_src = None
                try:
                    norm_dest = os.path.normcase(os.path.normpath(os.path.abspath(dest)))
                except Exception:
                    norm_dest = None
                try:
                    norm_src = os.path.normcase(os.path.normpath(os.path.abspath(it["ruta_fuente"])))
                except Exception:
                    norm_src = None
                if norm_dest is not None and norm_src is not None and norm_dest == norm_src:
                    raise ValueError("destino coincide con fuente")
                destinos.append(dest)
                lote_set.add(nombre.lower())
            except Exception as exc:
                # nombre inválido -> fallo de ese item, continuar con resto
                fallos_plan.append({"item": it, "error": str(exc)})
                destinos.append(None)

        # Si cancelación durante planificación
        if self._cancelada:
            omitidos_rest = total - len(destinos)
            return {
                "exitos": [],
                "fallos": fallos_plan,
                "omitidos": [{"item": items[i]} for i in range(len(destinos), total)],
                "cancelados": [],
                "total": total,
                "cancelado": True,
                "procesados": 0,
            }

        exitos = []
        fallos = list(fallos_plan)
        omitidos = []
        cancelados = []
        # Conteo de plan fallidos ya en fallos
        # Procesar secuencialmente
        for idx, it in enumerate(items):
            dest = destinos[idx] if idx < len(destinos) else None
            if dest is None:
                # ya contabilizado como fallo de planificación
                self.reportar_progreso(idx + 1, total)
                continue
            if self._cancelada:
                # no iniciar restantes -> omitidos
                omitidos.extend([{"item": items[j], "destino": destinos[j]} for j in range(idx, total) if destinos[j] is not None])
                # los fallos de plan que quedan ya están
                break
            # Validar origen existe y no vacío
            ruta_fuente = it["ruta_fuente"]
            if not isinstance(ruta_fuente, str) or not os.path.isfile(ruta_fuente):
                fallos.append({"item": it, "destino": dest, "error": "origen faltante"})
                self.reportar_progreso(idx + 1, total)
                continue
            try:
                if os.path.getsize(ruta_fuente) == 0:
                    fallos.append({"item": it, "destino": dest, "error": "origen vacío"})
                    self.reportar_progreso(idx + 1, total)
                    continue
            except OSError as exc:
                fallos.append({"item": it, "destino": dest, "error": str(exc)})
                self.reportar_progreso(idx + 1, total)
                continue
            # Validar inicio/fin
            ini = it["inicio"]
            fin = it["fin"]
            if not (isinstance(ini, (int, float)) and isinstance(fin, (int, float)) and fin > ini and ini >= 0):
                fallos.append({"item": it, "destino": dest, "error": "segmento inválido"})
                self.reportar_progreso(idx + 1, total)
                continue
            # Segunda comprobación de colisión justo antes de FFmpeg (no sobrescribir)
            if os.path.exists(dest):
                fallos.append({"item": it, "destino": dest, "error": "destino ya existe, no se sobrescribirá"})
                self.reportar_progreso(idx + 1, total)
                continue
            # Ejecutar exportar_segmento secuencialmente con cancel_check
            res = exp.exportar_segmento(
                ruta_fuente, float(ini), float(fin), dest, cancel_check=lambda: self._cancelada
            )
            if res.get("cancelado"):
                # limpiar item en curso ya lo hace exportar_segmento; contar como cancelado y omitir resto
                cancelados.append({"item": it, "destino": dest, "resultado": res})
                # restantes como omitidos
                for j in range(idx + 1, total):
                    if destinos[j] is not None:
                        omitidos.append({"item": items[j], "destino": destinos[j]})
                self.reportar_progreso(idx + 1, total)
                break
            if res.get("ok"):
                entry = {"item": it, "destino": dest, "resultado": res}
                # B6.11 alta incremental por cada salida exitosa (si ruta_db disponible y no cancelado)
                if self._ruta_db is not None and not self._cancelada and it.get("segmento_id") is not None and it.get("video_id") is not None:
                    try:
                        import escanear_videos as escanear_mod
                        alta = escanear_mod.incorporar_video_derivado_al_catalogo(
                            dest,
                            int(it["video_id"]),
                            [{"segmento_id": int(it["segmento_id"]), "inicio": float(ini), "fin": float(fin)}],
                            tipo="lote",
                            ruta_db=self._ruta_db,
                        )
                        entry["alta_catalogo"] = alta
                        if not alta.get("ok"):
                            entry["alta_catalogo_error"] = alta.get("error")
                    except Exception as exc:
                        entry["alta_catalogo"] = {"ok": False, "error": f"excepción en alta: {exc}", "catalog_error": True}
                        entry["alta_catalogo_error"] = str(exc)
                exitos.append(entry)
            else:
                fallos.append({"item": it, "destino": dest, "error": res.get("error"), "resultado": res})
            self.reportar_progreso(idx + 1, total)

        cancelado_flag = bool(self._cancelada or cancelados)
        return {
            "exitos": exitos,
            "fallos": fallos,
            "omitidos": omitidos,
            "cancelados": cancelados,
            "total": total,
            "cancelado": cancelado_flag,
            "procesados": len(exitos) + len(fallos) + len(cancelados),
            "exitosos": len(exitos),
            "fallidos": len(fallos),
            "omitidos_count": len(omitidos),
            "cancelados_count": len(cancelados),
        }


class TareaExportarSecuencia(TareaBase):
    """Une N>=2 segmentos del mismo original en un único derivado (B6.10).

    Delegación exclusiva en `exportar_secuencia.exportar_secuencia` (servicio sin Qt).
    Corre fuera del hilo UI (GestorTareas), sin FFmpeg/SQLite directos desde UI.
    Soporta cancelación real: `cancelar()` marca flag y el servicio termina FFmpeg y limpia temporales.
    Usa vía principal trim/atrim+concat recodificado o fallback por extracción precisa si hay subs compatibles.

    B6.11: si se provee `original_video_id` + `segmentos_info_orden` + `ruta_db`,
    tras verificación exitosa intenta alta incremental con trazabilidad ordenada.
    `segmentos_info_orden` es lista de dicts `{segmento_id, inicio, fin}` en orden
    explícito (preservado tal cual). Mantiene compatibilidad con callers B6.10.
    """

    def __init__(self, fuente, segmentos, destino, parent=None, original_video_id=None, segmentos_info_orden=None, ruta_db=None):
        super().__init__(parent)
        self._fuente = fuente
        # segmentos: lista de (inicio, fin) en orden explícito
        try:
            self._segmentos = [(float(a), float(b)) for a, b in list(segmentos)]
        except Exception as exc:
            raise TypeError(f"segmentos inválidos: {exc}") from None
        self._destino = destino
        self._cancelada = False
        self._original_video_id = original_video_id
        self._segmentos_info_orden = list(segmentos_info_orden) if segmentos_info_orden is not None else None
        self._ruta_db = ruta_db

    @property
    def fuente(self):
        return self._fuente

    @property
    def segmentos(self):
        return list(self._segmentos)

    @property
    def destino(self):
        return self._destino

    @property
    def original_video_id(self):
        return self._original_video_id

    @property
    def segmentos_info_orden(self):
        return list(self._segmentos_info_orden) if self._segmentos_info_orden is not None else None

    @property
    def ruta_db(self):
        return self._ruta_db

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        import exportar_secuencia as seq
        import escanear_videos as escanear_mod

        resultado = seq.exportar_secuencia(
            self._fuente,
            self._segmentos,
            self._destino,
            cancel_check=lambda: self._cancelada,
        )
        if (
            resultado.get("ok")
            and not resultado.get("cancelado")
            and self._original_video_id is not None
            and self._segmentos_info_orden is not None
            and self._ruta_db is not None
            and not self._cancelada
        ):
            try:
                # B6.11 validación estricta: longitud y correspondencia inicio/fin en mismo orden.
                # Ante mismatch, conservar archivo exportado pero fallar alta sin relación falsa.
                segmentos_info = self._segmentos_info_orden
                segmentos_exportados = self._segmentos
                mismatch = None
                if not isinstance(segmentos_info, (list, tuple)):
                    mismatch = "segmentos_info_orden no es lista"
                elif len(segmentos_info) != len(segmentos_exportados):
                    mismatch = f"mismatch longitud: info {len(segmentos_info)} vs exportados {len(segmentos_exportados)}"
                else:
                    for idx, (seg_info, seg_exp) in enumerate(zip(segmentos_info, segmentos_exportados)):
                        if not isinstance(seg_info, dict):
                            mismatch = f"segmento_info {idx} no es dict"
                            break
                        try:
                            ini_info = float(seg_info.get("inicio"))
                            fin_info = float(seg_info.get("fin"))
                        except Exception:
                            mismatch = f"segmento_info {idx} inicio/fin no numéricos"
                            break
                        ini_exp, fin_exp = seg_exp
                        if abs(ini_info - float(ini_exp)) > 1e-6 or abs(fin_info - float(fin_exp)) > 1e-6:
                            mismatch = f"mismatch correspondencia en orden {idx}: info ({ini_info},{fin_info}) vs exportado ({ini_exp},{fin_exp})"
                            break
                if mismatch is not None:
                    resultado = dict(resultado)
                    resultado["alta_catalogo"] = {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"validación secuencia falló: {mismatch}", "catalog_error": False}
                    resultado["alta_catalogo_error"] = mismatch
                    return resultado
                alta = escanear_mod.incorporar_video_derivado_al_catalogo(
                    resultado.get("salida"),
                    int(self._original_video_id),
                    segmentos_info,
                    tipo="secuencia",
                    ruta_db=self._ruta_db,
                )
                resultado = dict(resultado)
                resultado["alta_catalogo"] = alta
                if not alta.get("ok"):
                    resultado["alta_catalogo_error"] = alta.get("error")
            except Exception as exc:
                resultado = dict(resultado)
                resultado["alta_catalogo"] = {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"excepción en alta: {exc}", "catalog_error": True}
                resultado["alta_catalogo_error"] = str(exc)
        return resultado


class TareaRenombrarVideo(TareaBase):
    """Renombra un video preservando video_id (B7.1).

    Corre fuera del hilo UI. Delega exclusivamente en
    `renombrar_video.renombrar_video` (sin SQLite/FS directo desde UI).
    """

    def __init__(self, video_id, nuevo_nombre, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._nuevo_nombre = nuevo_nombre
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def nuevo_nombre(self):
        return self._nuevo_nombre

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        import renombrar_video as svc
        return svc.renombrar_video(self._video_id, self._nuevo_nombre, self._ruta_db)


class TareaMoverVideo(TareaBase):
    """Mueve un video a carpeta existente preservando video_id y nombre (B7.2).

    Corre fuera del hilo UI. Delega exclusivamente en
    `mover_video.mover_video` (sin SQLite/FS directo desde UI).
    Soporta forzar cross-volume para pruebas sin dos discos.
    """

    def __init__(self, video_id, carpeta_destino, ruta_db=None, forzar_cross_volume=False, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._carpeta_destino = carpeta_destino
        self._ruta_db = ruta_db
        self._forzar_cross = bool(forzar_cross_volume)

    @property
    def video_id(self):
        return self._video_id

    @property
    def carpeta_destino(self):
        return self._carpeta_destino

    @property
    def ruta_db(self):
        return self._ruta_db

    @property
    def forzar_cross_volume(self):
        return self._forzar_cross

    def _trabajo(self):
        import mover_video as svc
        return svc.mover_video(self._video_id, self._carpeta_destino, self._ruta_db, forzar_cross_volume=self._forzar_cross)


class TareaCrearCarpeta(TareaBase):
    """Crea una carpeta hija directa de forma segura (B7.3).

    Corre fuera del hilo UI. Delega exclusivamente en
    `crear_carpeta.crear_carpeta` (sin SQLite/FS directo desde UI).
    """

    def __init__(self, carpeta_padre, nombre, parent=None):
        super().__init__(parent)
        self._carpeta_padre = carpeta_padre
        self._nombre = nombre

    @property
    def carpeta_padre(self):
        return self._carpeta_padre

    @property
    def nombre(self):
        return self._nombre

    def _trabajo(self):
        import crear_carpeta as svc
        return svc.crear_carpeta(self._carpeta_padre, self._nombre)


class TareaCopiarVideo(TareaBase):
    """Copia un video catalogado a carpeta existente (B7.4).

    Corre fuera del hilo UI. Delega exclusivamente en
    `copiar_video.copiar_video` (sin SQLite/FS directo desde UI).
    """

    def __init__(self, video_id, carpeta_destino, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._carpeta_destino = carpeta_destino
        self._ruta_db = ruta_db

    @property
    def video_id(self):
        return self._video_id

    @property
    def carpeta_destino(self):
        return self._carpeta_destino

    @property
    def ruta_db(self):
        return self._ruta_db

    def _trabajo(self):
        import copiar_video as svc
        return svc.copiar_video(self._video_id, self._carpeta_destino, self._ruta_db)


class TareaEliminarVideo(TareaBase):
    """Elimina un video enviándolo a la Papelera (B7.5).

    Corre fuera del hilo UI. Delega exclusivamente en
    `eliminar_video.eliminar_video` (sin SQLite/FS directo desde UI,
    sin os.remove, sin FFmpeg). Soporta cancelación cooperativa
    solo antes del punto de no retorno (antes de Papelera).
    """

    def __init__(self, video_id, ruta_db=None, parent=None):
        super().__init__(parent)
        self._video_id = video_id
        self._ruta_db = ruta_db
        self._cancelada = False

    @property
    def video_id(self):
        return self._video_id

    @property
    def ruta_db(self):
        return self._ruta_db

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        if self._cancelada:
            return {"ok": False, "cancelado": True, "video_id": self._video_id}
        import eliminar_video as svc
        # Punto de no retorno: después de Papelera no hay cancelación
        resultado = svc.eliminar_video(self._video_id, self._ruta_db)
        if self._cancelada:
            # Si se canceló inmediatamente después, el servicio ya ejecutó
            # Papelera+DB; no revertir, informar que no fue cancelable
            resultado["cancelado_tardio"] = True
        return resultado


class TareaLoteOperaciones(TareaBase):
    """Orquestador lote B7.6 — mueve/copia/elimina en lote secuencial (sin Qt, sin FFmpeg).

    Delega exclusivamente en lote_operaciones.lote_operaciones (puro, sin Qt).
    Soporta cancelación cooperativa antes de cada ítem y reporta progreso por ítem (actual/total).
    No hace pre-vuelo global; cada servicio resuelve colisiones/destino inválido.
    No revierte ítems completados. Un fallo parcial no cancela el lote.
    """

    def __init__(self, operacion, video_ids, ruta_db, carpeta_destino=None, parent=None):
        super().__init__(parent)
        if operacion not in ("mover", "copiar", "eliminar"):
            raise ValueError(f"operacion debe ser mover|copiar|eliminar, got {operacion!r}")
        if isinstance(video_ids, (str, bytes, bytearray)):
            raise TypeError("video_ids debe ser colección, no texto")
        try:
            self._video_ids = list(video_ids)
        except TypeError:
            raise TypeError("video_ids debe ser iterable") from None
        self._operacion = operacion
        self._ruta_db = ruta_db
        self._carpeta_destino = carpeta_destino
        self._cancelada = False

    @property
    def operacion(self):
        return self._operacion

    @property
    def video_ids(self):
        return list(self._video_ids)

    @property
    def ruta_db(self):
        return self._ruta_db

    @property
    def carpeta_destino(self):
        return self._carpeta_destino

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        import lote_operaciones as lote
        return lote.lote_operaciones(
            self._operacion,
            self._video_ids,
            self._ruta_db,
            carpeta_destino=self._carpeta_destino,
            cancel_check=lambda: self._cancelada,
            progreso_callback=self.reportar_progreso,
        )


class TareaListarSubcarpetasDestino(TareaBase):
    """Lista subcarpetas inmediatas del destino (B7.10) en background.

    Usa helper centralizado rutas.listar_subcarpetas sin duplicar lógica.
    No toca SQLite/FFmpeg/shutil. Retorna dict {ok, valido, subcarpetas, error, destino}.
    """

    def __init__(self, carpeta, parent=None):
        super().__init__(parent)
        self._carpeta = carpeta

    @property
    def carpeta(self):
        return self._carpeta

    def _trabajo(self):
        import rutas as rutas_mod
        res = rutas_mod.listar_subcarpetas(self._carpeta)
        # Validar contrato dict explícitamente; sin except genérico
        if not isinstance(res, dict):
            res = {"ok": False, "valido": False, "subcarpetas": [], "error": "helper contrato inválido: no dict", "destino": self._carpeta}
            return res
        # Copia superficial para añadir trazabilidad sin mutar original
        res = dict(res)
        res["destino"] = self._carpeta
        return res


class TareaRenombrarMasivo(TareaBase):
    """Renombrado masivo seguro B7.7 — plantilla cerrada, preview exacta, ciclos con temporales.

    Corre fuera del hilo UI. Delega exclusivamente en `renombrar_masivo`
    (sin SQLite/FS directo desde UI, sin FFmpeg). Soporta cancelación
    cooperativa antes de cada ítem y reporta progreso por ítem (actual/total).
    El plan es exactamente el mostrado en preview; no recalcula diferente.
    """

    def __init__(self, video_infos, plantilla, ruta_db=None, texto=None, fecha_hoy=None, parent=None):
        super().__init__(parent)
        if isinstance(video_infos, (str, bytes, bytearray)):
            raise TypeError("video_infos debe ser colección, no texto")
        try:
            self._video_infos = [dict(v) for v in list(video_infos)]
        except Exception as exc:
            raise TypeError(f"video_infos inválidos: {exc}") from None
        if not isinstance(plantilla, str) or not plantilla.strip():
            raise ValueError("plantilla debe ser texto no vacío")
        self._plantilla = plantilla
        self._ruta_db = ruta_db
        self._texto = texto
        self._fecha_hoy = fecha_hoy
        self._cancelada = False
        # plan pre-construido para garantizar preview == ejecución (inyectado o construido en _trabajo)
        self._plan_preconstruido = None

    @property
    def video_infos(self):
        return [dict(v) for v in self._video_infos]

    @property
    def plantilla(self):
        return self._plantilla

    @property
    def ruta_db(self):
        return self._ruta_db

    @property
    def texto(self):
        return self._texto

    @property
    def fecha_hoy(self):
        return self._fecha_hoy

    def set_plan(self, plan):
        """Inyecta plan exacto de preview para que ejecución use mismo objeto (no recalcular)."""
        if not isinstance(plan, list):
            raise TypeError("plan debe ser lista")
        self._plan_preconstruido = list(plan)

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        import renombrar_masivo as rm
        # Si hay plan pre-construido (preview exacta), usarlo directamente sin recalcular
        if self._plan_preconstruido is not None:
            plan = self._plan_preconstruido
            # validar que plan no contiene errores
            for item in plan:
                if item.get("error"):
                    raise ValueError(f"plan contiene error en video_id {item.get('video_id')}: {item.get('error')}")
            return rm.ejecutar_plan(
                plan,
                ruta_db=self._ruta_db,
                cancel_check=lambda: self._cancelada,
                progreso_callback=self.reportar_progreso,
            )
        # Sin plan inyectado: construir y ejecutar (fallback para tests directos)
        construido = rm.construir_plan(
            self._video_infos,
            self._plantilla,
            texto=self._texto,
            fecha_hoy=self._fecha_hoy,
            ruta_db=self._ruta_db,
        )
        if not construido.get("ok"):
            errores = construido.get("errores") or []
            # incluir errores por item
            for p in construido.get("plan", []):
                if p.get("error"):
                    errores.append(f"video_id {p.get('video_id')}: {p.get('error')}")
            raise ValueError(f"plan inválido: {'; '.join(errores) if errores else 'error desconocido'}")
        plan = construido["plan"]
        return rm.ejecutar_plan(
            plan,
            ruta_db=self._ruta_db,
            cancel_check=lambda: self._cancelada,
            progreso_callback=self.reportar_progreso,
        )
