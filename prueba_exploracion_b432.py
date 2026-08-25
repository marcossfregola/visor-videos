import contextlib
import gc
import json
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import exploracion_cache
import tareas_videos
import visor_videos
from exploracion_temporal import tiempos_objetivo
from tareas import TareaBase
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

_CANTIDAD_ORIGINAL_PREVIEWS = escanear_mod.CANTIDAD_PREVIEWS


class _TareaExploracionDensaFake(TareaBase):
    creadas = []
    resultado = None
    liberar = None
    parciales = []

    resultado_parcial = Signal(object)

    def __init__(
        self, video_id, ruta_video, duracion=None, cantidad=None, parent=None,
        objetivo_manual=None, tiempos_tira=None
    ):
        super().__init__(parent)
        self.video_id = video_id
        self.ruta_video = ruta_video
        self.duracion = duracion
        self.cantidad = cantidad
        self.objetivo_manual = objetivo_manual
        self.tiempos_tira = tiempos_tira
        self._cancelada = False
        _TareaExploracionDensaFake.creadas.append(self)

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        for parcial in _TareaExploracionDensaFake.parciales:
            self.resultado_parcial.emit(parcial)
        if _TareaExploracionDensaFake.liberar is not None:
            _TareaExploracionDensaFake.liberar.wait(3.0)
        if self._cancelada:
            return {"cancelado": True, "version": None, "fotogramas": []}
        return _TareaExploracionDensaFake.resultado


def _filas(nombres, duraciones, carpeta="C:\\"):
    filas = []
    for indice, (nombre, duracion) in enumerate(
        zip(nombres, duraciones), start=1
    ):
        filas.append(
            (
                nombre,
                os.path.join(carpeta, nombre),
                os.path.splitext(nombre)[1].lower(),
                "2026-08-09T00:00:00",
                float(duracion),
                1920,
                1080,
                "h264",
                indice % 3,
            )
        )
    return filas


def _crear_bd(filas):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute(
            """
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                ruta TEXT NOT NULL,
                extension TEXT NOT NULL,
                fecha_importacion TEXT NOT NULL,
                duracion_segundos REAL,
                ancho INTEGER,
                alto INTEGER,
                codec_video TEXT,
                cantidad_miniaturas INTEGER,
                tamano_bytes INTEGER
            )
            """
        )
        conn.executemany(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


def _crear_previews(carpeta, prefijo, cantidad, ancho=80, alto=45):
    creadas = []
    for indice in range(1, cantidad + 1):
        ruta = os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        imagen = QImage(ancho, alto, QImage.Format_RGB32)
        imagen.fill(QColor(30 + indice * 20, 60, 120))
        imagen.save(ruta, "JPEG")
        creadas.append(ruta)
    return creadas


def _crear_png(ruta, ancho=60, alto=40):
    imagen = QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(200, 40, 80))
    imagen.save(ruta, "PNG")
    return ruta


def _crear_qimage(ms, ancho=60, alto=40):
    imagen = QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(20 + ms % 200, 80, 140))
    return imagen


def _cerrar_temp(temp):
    for _ in range(10):
        try:
            temp.cleanup()
            return
        except PermissionError:
            gc.collect()
            QApplication.processEvents()
            time.sleep(0.1)
    temp.cleanup()


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        _cerrar_temp(temp)


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


@contextlib.contextmanager
def _config_con_previews(cantidad):
    ruta = os.environ["VISOR_CONFIG"]
    original = None
    if os.path.isfile(ruta):
        with open(ruta, encoding="utf-8") as f:
            original = f.read()
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(json.dumps({"cantidad_previews": cantidad}))
    try:
        yield
    finally:
        if original is None:
            if os.path.isfile(ruta):
                os.remove(ruta)
        else:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(original)


@contextlib.contextmanager
def _ventana_con(nombres, duraciones):
    temp_min = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp_min.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp_min.name
    carpeta = tempfile.TemporaryDirectory()
    for nombre in nombres:
        ruta = os.path.join(carpeta.name, nombre)
        with open(ruta, "w") as f:
            f.write("fake")
        _crear_previews(
            temp_min.name, os.path.splitext(nombre)[0], 3
        )
    temp, ruta_db = _crear_bd(
        _filas(nombres, duraciones, carpeta=carpeta.name)
    )
    ventana = None
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        ventana.resize(900, 620)
        ventana.show()
        _esperar(
            lambda: ventana._carga_completada and ventana.gestor.hilo is None
        )
        _esperar(lambda: ventana.contenedor.findChildren(Tarjeta))
        yield ventana, dict(ventana.tarjetas), carpeta.name
    finally:
        if ventana is not None:
            _limpiar(ventana)
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        _cerrar_temp(temp)
        _cerrar_temp(temp_min)
        _cerrar_temp(carpeta)


def _limpiar(ventana):
    if ventana is None:
        return
    for gestor in (
        ventana.gestor,
        getattr(ventana, "gestor_exploracion", None),
    ):
        if gestor is not None and gestor.hilo is not None:
            gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()
    gc.collect()


def _fila_basica():
    return (
        "clip.mp4",
        100.0,
        1920,
        1080,
        "h264",
        3,
        1024,
        "C:\\videos\\clip.mp4",
        7,
    )


def _pixmap_color(color, ancho=50, alto=30):
    pix = QPixmap(ancho, alto)
    pix.fill(color)
    return pix


def test_01():
    modulos = [
        "tareas_videos.py",
        "visor_videos.py",
        "exploracion_cache.py",
        "exploracion_temporal.py",
        "tareas.py",
        "prueba_exploracion_b432.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        ok_vacio = tarjeta._previews_densos == []
        tarjeta.expandir()
        ok_tras_expandir = tarjeta._previews_densos == []
        densos = [
            {"instante": 10.0, "pixmap": _pixmap_color(QColor("red"))},
            {"instante": 10.0, "pixmap": _pixmap_color(QColor("blue"))},
            {"instante": "raro", "pixmap": _pixmap_color(QColor("green"))},
            {"instante": 20.0, "pixmap": None},
            {"instante": 30.0, "pixmap": QPixmap()},
            {"instante": True, "pixmap": _pixmap_color(QColor("black"))},
        ]
        nuevos = tarjeta.agregar_fotogramas_densos(densos)
        ok_nuevos = nuevos is True
        ok_cantidad = len(tarjeta._previews_densos) == 1
        entrada = tarjeta._previews_densos[0]
        ok_instante = entrada["instante"] == 10.0 and entrada.get("ms") == 10000
        # B9.3: metadata ligera sin QPixmap retenido
        ok_sin_pixmap = "pixmap" not in entrada and "pixmap_escalado" not in entrada and "QImage" not in str(type(entrada))
        # cache visual derivada no debe crecer con metadata (requiere viewport)
        ok_cache_acotada = len(getattr(tarjeta, "_cache_visual", {})) == 0
        repetido = tarjeta.agregar_fotogramas_densos(
            [{"instante": 10.0, "pixmap": _pixmap_color(QColor("red"))}]
        )
        ok_repetido = repetido is False and len(tarjeta._previews_densos) == 1
    return (
        ok_vacio
        and ok_tras_expandir
        and ok_nuevos
        and ok_cantidad
        and ok_instante
        and ok_sin_pixmap
        and ok_cache_acotada
        and ok_repetido,
        f"densos={len(tarjeta._previews_densos)} sin_pixmap={ok_sin_pixmap} cache={len(getattr(tarjeta,'_cache_visual',{}))}",
    )


def test_03():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        tarjeta.expandir()
        refrescos = []
        original = tarjeta._refrescar_exploracion
        tarjeta._refrescar_exploracion = lambda: refrescos.append(1)
        a = tarjeta.agregar_fotogramas_densos(
            [
                {"instante": 10.0000001, "pixmap": _pixmap_color(QColor("red"))},
                {"instante": 10.0, "pixmap": _pixmap_color(QColor("blue"))},
            ]
        )
        ok_dedupe = len(tarjeta._previews_densos) == 1
        b = tarjeta.agregar_fotogramas_densos(
            [{"instante": 20.0, "pixmap": _pixmap_color(QColor("green"))}]
        )
        ok_refresco = len(refrescos) == 2
        tarjeta._refrescar_exploracion = original
    return ok_dedupe and a is True and b is True and ok_refresco, (
        f"n={len(tarjeta._previews_densos)} refrescos={len(refrescos)}"
    )


def test_04():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        p0 = _pixmap_color(QColor(255, 0, 0))
        p100 = _pixmap_color(QColor(0, 255, 0))
        tarjeta._previews_exploracion = [
            {"instante": 0.0, "pixmap_escalado": p0},
            {"instante": 100.0, "pixmap_escalado": p100},
        ]
        elegida = tarjeta._pixmap_para_instante(60.0)
        ok_60 = elegida.cacheKey() == p100.cacheKey()
        elegida = tarjeta._pixmap_para_instante(40.0)
        ok_40 = elegida.cacheKey() == p0.cacheKey()
        ok_none = tarjeta._pixmap_para_instante(None) is None
    return ok_60 and ok_40 and ok_none, (
        f"60->{'p100' if ok_60 else 'otra'} 40->{'p0' if ok_40 else 'otra'}"
    )


def test_05():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        p0 = _pixmap_color(QColor(255, 0, 0))
        p100 = _pixmap_color(QColor(0, 255, 0))
        pd5 = _pixmap_color(QColor(0, 0, 255))
        pd95 = _pixmap_color(QColor(255, 255, 0))
        tarjeta._previews_exploracion = [
            {"instante": 0.0, "pixmap_escalado": p0},
            {"instante": 100.0, "pixmap_escalado": p100},
        ]
        # B9.3: densos metadata ligera + cache_visual acotada por necesidad
        tarjeta._previews_densos = [
            {"instante": 5.0, "ms": 5000},
            {"instante": 95.0, "ms": 95000},
        ]
        tarjeta._cache_visual = {5000: pd5, 95000: pd95}
        tarjeta._hover_instante_actual = 6.0
        tarjeta._cache_visual_pending = set()
        ok_6 = tarjeta._pixmap_para_instante(6.0).cacheKey() == pd5.cacheKey()
        ok_90 = tarjeta._pixmap_para_instante(90.0).cacheKey() == pd95.cacheKey()
        ok_10 = tarjeta._pixmap_para_instante(10.0).cacheKey() == pd5.cacheKey()
        ok_0 = tarjeta._pixmap_para_instante(0.0).cacheKey() == p0.cacheKey()
        ok_none = tarjeta._pixmap_para_instante(None) is None
    return ok_6 and ok_90 and ok_10 and ok_0 and ok_none, (
        f"6->{ok_6} 90->{ok_90} 10->{ok_10} 0->{ok_0}"
    )


def test_06():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        p50 = _pixmap_color(QColor(255, 0, 0))
        pd50 = _pixmap_color(QColor(0, 0, 255))
        tarjeta._previews_exploracion = [
            {"instante": 50.0, "pixmap_escalado": p50}
        ]
        tarjeta._previews_densos = [
            {"instante": 50.0, "ms": 50000}
        ]
        tarjeta._cache_visual = {50000: pd50}
        elegida = tarjeta._pixmap_para_instante(50.0)
        ok_empate = elegida.cacheKey() == p50.cacheKey()
    return ok_empate, (
        f"empate->{'preview' if ok_empate else 'denso'}"
    )


def test_07():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        p100 = _pixmap_color(QColor(0, 255, 0))
        tarjeta._previews_exploracion = [
            {"instante": 0.0, "pixmap_escalado": _pixmap_color(QColor(255, 0, 0))},
            {"instante": 100.0, "pixmap_escalado": p100},
        ]
        # B9.3 metadata ligera: dense sin cache no afecta elección
        tarjeta._previews_densos = [
            {"instante": "raro", "ms": 1000},
            {"instante": 55.0, "ms": 55000},
            {"instante": None, "ms": 0},
            {"instante": 90.0, "ms": 90000},
        ]
        tarjeta._cache_visual = {}
        # no cache para esos ms, debe ignorar basura y devolver preview más cercano
        elegida = tarjeta._pixmap_para_instante(60.0)
        ok_ignora_basura = elegida is not None and elegida.cacheKey() == p100.cacheKey()
    return ok_ignora_basura, f"60->{'p100' if ok_ignora_basura else 'otra'}"


def test_08():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        tarjeta.expandir()
        tarjeta.agregar_fotogramas_densos(
            [
                {"instante": 5.0, "pixmap": _pixmap_color(QColor("red"))},
                {"instante": 15.0, "pixmap": _pixmap_color(QColor("blue"))},
            ]
        )
        ok_llena = len(tarjeta._previews_densos) == 2
        tarjeta.colapsar()
        ok_libera = (
            tarjeta._previews_densos == []
            and tarjeta._previews_exploracion == []
        )
    return ok_llena and ok_libera, (
        f"antes={2} despues={len(tarjeta._previews_densos)}"
    )


def test_09():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        tarjeta.expandir()
        tarjeta.agregar_fotogramas_densos(
            [{"instante": 10.0, "pixmap": _pixmap_color(QColor("red"), 50, 30)}]
        )
        # B9.3: metadata pura, sin pixmap_escalado retenido
        entrada = tarjeta._previews_densos[0]
        ok_sin_pixmap = "pixmap_escalado" not in entrada and "pixmap" not in entrada
        ok_metadata = entrada.get("instante") == 10.0 and entrada.get("ms") == 10000
        ancho_grande, alto_grande = 640, 360
        original = visor_videos.dimensiones_miniatura
        visor_videos.dimensiones_miniatura = lambda: (ancho_grande, alto_grande)
        try:
            tarjeta.aplicar_tamano()
        finally:
            visor_videos.dimensiones_miniatura = original
        # aplicar_tamano no debe crear pixmap_escalado en metadata
        ok_sigue_sin_pixmap = "pixmap_escalado" not in tarjeta._previews_densos[0]
        ok_reescala = ok_sin_pixmap and ok_metadata and ok_sigue_sin_pixmap
    return ok_reescala, f"metadata={entrada} sin_pixmap={ok_sin_pixmap}"


def test_10():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    _TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432.png")
    )
    original_ruta = exploracion_cache.ruta_fotograma_version

    def _ruta_fake(video_id, ms, version):
        return ruta_png

    exploracion_cache.ruta_fotograma_version = _ruta_fake
    try:
        with _ventana_con(["clip1.mp4", "clip2.mp4"], [100.0, 50.0]) as (
            ventana,
            tarjetas,
            carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            ok_objetivo = ventana._exploracion_objetivo == "clip1.mp4"
            ok_colapsada = not tarjetas["clip2.mp4"]._expandida
            ok_pendiente = _esperar(
                lambda: ventana.gestor_exploracion.hilo is None
            )
            ok_op_limpia = (
                ventana._exploracion_op_actual is None
                and ventana._cola_exploracion == []
            )
            ok_densos = len(tarjeta1._previews_densos) == 3
            instantes = [
                round(d["instante"], 4) for d in tarjeta1._previews_densos
            ]
            ok_instantes = instantes == [0.0, 5.0, 10.0]
            tarea = _TareaExploracionDensaFake.creadas[0]
            ok_tarea = (
                tarea.video_id == 1
                and tarea.ruta_video == os.path.join(carpeta, "clip1.mp4")
                and tarea.duracion == 100.0
                and tarea.cantidad == visor_videos.FOTOGRAMAS_INICIALES
            )
    finally:
        exploracion_cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_objetivo
        and ok_colapsada
        and ok_pendiente
        and ok_op_limpia
        and ok_densos
        and ok_instantes
        and ok_tarea,
        f"objetivo={ventana._exploracion_objetivo} densos={len(tarjeta1._previews_densos)} instantes={instantes}",
    )


def test_11():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    try:
        with _ventana_con(["clip1.mp4", "clip2.mp4"], [100.0, 50.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            _esperar(lambda: ventana.gestor_exploracion.hilo is None)
            ok_op_none = ventana._al_resultado_exploracion(
                {"version": "v1", "fotogramas": [0]}
            ) is None
            ventana._exploracion_objetivo = "clip2.mp4"
            ventana._exploracion_op_actual = {
                "nombre": "clip1.mp4",
                "video_id": 1,
            }
            ventana._al_resultado_exploracion(
                {"version": "v1", "fotogramas": [0]}
            )
            ok_obsoleto = len(tarjeta1._previews_densos) == 0
            ventana._exploracion_objetivo = "clip1.mp4"
            ventana._al_resultado_exploracion(
                {"cancelado": True, "version": None, "fotogramas": []}
            )
            ok_cancelado = len(tarjeta1._previews_densos) == 0
            tarjeta1.colapsar()
            ventana._al_resultado_exploracion(
                {"version": "v1", "fotogramas": [0]}
            )
            ok_colapsada = len(tarjeta1._previews_densos) == 0
            ventana._al_error_exploracion("error simulado")
            ok_error = True
            ventana._aplicar_exploracion_densa(
                tarjeta1, {"video_id": 1}, {"version": None, "fotogramas": []}
            )
            ventana._aplicar_exploracion_densa(
                tarjeta1, {"video_id": 1}, {}
            )
            ok_sin_resultado = True
    finally:
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_op_none
        and ok_obsoleto
        and ok_cancelado
        and ok_colapsada
        and ok_error
        and ok_sin_resultado,
        f"densos={len(tarjeta1._previews_densos)}",
    )


def test_12():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    _TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    try:
        with _ventana_con(["clip1.mp4", "clip2.mp4"], [100.0, 50.0]) as (
            ventana,
            tarjetas,
            carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            ventana._exploracion_objetivo = "fantasma.mp4"
            ventana._cola_exploracion = ["fantasma.mp4"]
            ventana._procesar_siguiente_exploracion()
            ok_sin_tarjeta = (
                ventana._cola_exploracion == []
                and _TareaExploracionDensaFake.creadas == []
            )
            _TareaExploracionDensaFake.liberar = threading.Event()
            bloqueo = _TareaExploracionDensaFake(99, "C:\\x\\clip1.mp4")
            ventana.gestor_exploracion.iniciar(bloqueo)
            _esperar(
                lambda: ventana.gestor_exploracion.hilo is not None
            )
            ventana._exploracion_objetivo = "clip1.mp4"
            ventana._encolar_exploracion("otro.mp4")
            ok_objetivo_guard = ventana._cola_exploracion == []
            ventana._encolar_exploracion("clip1.mp4")
            ventana._encolar_exploracion("clip1.mp4")
            ok_dedupe = ventana._cola_exploracion == ["clip1.mp4"]
            ventana._exploracion_objetivo = None
            ventana._cola_exploracion = []
            _TareaExploracionDensaFake.liberar.set()
            _esperar(lambda: ventana.gestor_exploracion.hilo is None)
            tarjeta1._video_id = None
            tarjeta1.expandir()
            ok_sin_id = (
                ventana._cola_exploracion == []
                and tarjeta1._expandida
            )
            tarjeta1._video_id = 1
            tarjeta1._carpeta_video = os.path.join(
                carpeta, "carpeta_inexistente"
            )
            ventana._encolar_exploracion("clip1.mp4")
            ok_sin_ruta = (
                ventana._cola_exploracion == []
                and len(_TareaExploracionDensaFake.creadas) == 1
            )
    finally:
        if _TareaExploracionDensaFake.liberar is not None:
            _TareaExploracionDensaFake.liberar.set()
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_sin_tarjeta
        and ok_objetivo_guard
        and ok_dedupe
        and ok_sin_id
        and ok_sin_ruta,
        f"cola={ventana._cola_exploracion} creadas={len(_TareaExploracionDensaFake.creadas)}",
    )


def test_13():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = threading.Event()
    _TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_cancel.png")
    )
    original_ruta = exploracion_cache.ruta_fotograma_version
    exploracion_cache.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    try:
        with _ventana_con(["clip1.mp4", "clip2.mp4"], [100.0, 50.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta2 = tarjetas["clip2.mp4"]
            tarjeta1.expandir()
            ok_en_curso = _esperar(
                lambda: ventana.tarea_exploracion is not None
                and ventana.gestor_exploracion.hilo is not None
            )
            tarea1 = ventana.tarea_exploracion
            tarjeta2.expandir()
            ok_cancelada = tarea1._cancelada is True
            ok_objetivo = ventana._exploracion_objetivo == "clip2.mp4"
            _TareaExploracionDensaFake.liberar.set()
            _esperar(lambda: ventana.gestor_exploracion.hilo is None)
            _esperar(
                lambda: ventana._exploracion_op_actual is None
                and ventana._cola_exploracion == []
            )
            ok_final = (
                not tarjeta1._expandida
                and tarjeta2._expandida
                and len(tarjeta2._previews_densos) == 3
            )
    finally:
        _TareaExploracionDensaFake.liberar.set()
        exploracion_cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_en_curso and ok_cancelada and ok_objetivo and ok_final, (
        f"cancelada={tarea1._cancelada} objetivo={ventana._exploracion_objetivo} densos2={len(tarjeta2._previews_densos)}"
    )


def test_14():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    try:
        with _ventana_con(["clip1.mp4"], [100.0]) as (
            ventana,
            _tarjetas,
            _carpeta,
        ):
            tarea = _TareaExploracionDensaFake(1, "C:\\x\\clip1.mp4")
            ventana._exploracion_op_actual = {
                "nombre": "clip1.mp4",
                "video_id": 1,
            }
            ventana.tarea_exploracion = tarea
            ventana._al_exploracion_finalizada()
            ok_limpia = (
                ventana._exploracion_op_actual is None
                and ventana.tarea_exploracion is None
            )
    finally:
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_limpia, (
        f"op={ventana._exploracion_op_actual} tarea={ventana.tarea_exploracion}"
    )


def test_15():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    _TareaExploracionDensaFake.resultado = {
        "version": "v9",
        "fotogramas": [0],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_aplicar.png")
    )
    original_ruta = exploracion_cache.ruta_fotograma_version
    exploracion_cache.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    try:
        with _ventana_con(["clip1.mp4"], [100.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            ventana._aplicar_exploracion_densa(
                tarjeta1,
                {"video_id": 1},
                {"version": "v9", "fotogramas": [0, 2500, 33333]},
            )
            ok_instantes = [
                round(d["instante"], 4)
                for d in tarjeta1._previews_densos
            ] == [0.0, 2.5, 33.333]
            ok_cantidad = len(tarjeta1._previews_densos) == 3
            exploracion_cache.ruta_fotograma_version = (
                lambda video_id, ms, version: os.path.join(
                    _CONFIG_TEMPORAL.name, "no_existe.png"
                )
            )
            ventana._aplicar_exploracion_densa(
                tarjeta1,
                {"video_id": 1},
                {"version": "v9", "fotogramas": [4000]},
            )
            ok_omitidos = len(tarjeta1._previews_densos) == 3
    finally:
        exploracion_cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_instantes and ok_cantidad and ok_omitidos, (
        f"densos={len(tarjeta1._previews_densos)}"
    )


def test_16():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = threading.Event()
    _TareaExploracionDensaFake.parciales = [
        {
            "video_id": 1,
            "version": "v1",
            "fotogramas": [
                (0, _crear_qimage(0)),
                (5000, _crear_qimage(5000)),
            ],
        }
    ]
    _TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_progresivo.png")
    )
    original_ruta = exploracion_cache.ruta_fotograma_version
    exploracion_cache.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    try:
        with _ventana_con(["clip1.mp4"], [100.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            ok_en_curso = _esperar(
                lambda: ventana.gestor_exploracion.hilo is not None
            )
            ok_parcial = _esperar(
                lambda: len(tarjeta1._previews_densos) == 2
            )
            instantes_parciales = sorted(
                d["instante"] for d in tarjeta1._previews_densos
            )
            ok_parcial_instantes = instantes_parciales == [0.0, 5.0]
            ok_sigue_activa = ventana.gestor_exploracion.hilo is not None
            _TareaExploracionDensaFake.liberar.set()
            ok_final = _esperar(
                lambda: len(tarjeta1._previews_densos) == 3
            )
            instantes_finales = sorted(
                d["instante"] for d in tarjeta1._previews_densos
            )
            ok_final_instantes = instantes_finales == [0.0, 5.0, 10.0]
    finally:
        _TareaExploracionDensaFake.liberar.set()
        _TareaExploracionDensaFake.parciales = []
        exploracion_cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_en_curso
        and ok_parcial
        and ok_parcial_instantes
        and ok_sigue_activa
        and ok_final
        and ok_final_instantes,
        f"parciales={instantes_parciales} finales={instantes_finales}",
    )


def test_17():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    _TareaExploracionDensaFake.parciales = []
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    try:
        with _ventana_con(["clip1.mp4", "clip2.mp4"], [100.0, 50.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            _esperar(lambda: ventana.gestor_exploracion.hilo is None)
            ventana._exploracion_objetivo = "clip2.mp4"
            ventana._exploracion_op_actual = {
                "nombre": "clip1.mp4",
                "video_id": 1,
            }
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 1,
                    "version": "v1",
                    "fotogramas": [(5000, _crear_qimage(5000))],
                }
            )
            ok_obsoleto = len(tarjeta1._previews_densos) == 0
            ventana._exploracion_objetivo = "clip1.mp4"
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 2,
                    "version": "v1",
                    "fotogramas": [(5000, _crear_qimage(5000))],
                }
            )
            ok_video_distinto = len(tarjeta1._previews_densos) == 0
            tarjeta1.colapsar()
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 1,
                    "version": "v1",
                    "fotogramas": [(5000, _crear_qimage(5000))],
                }
            )
            ok_colapsada = len(tarjeta1._previews_densos) == 0
            tarjeta1.expandir()
            ventana._al_resultado_parcial_exploracion(
                {"video_id": 1, "version": "v1", "fotogramas": []}
            )
            ok_vacio = len(tarjeta1._previews_densos) == 0
            ventana._exploracion_op_actual = None
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 1,
                    "version": "v1",
                    "fotogramas": [(5000, _crear_qimage(5000))],
                }
            )
            ok_sin_op = len(tarjeta1._previews_densos) == 0
    finally:
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_obsoleto
        and ok_video_distinto
        and ok_colapsada
        and ok_vacio
        and ok_sin_op,
        f"densos={len(tarjeta1._previews_densos)}",
    )


def test_18():
    with _miniaturas_temporales():
        tarjeta = Tarjeta(_fila_basica())
        tarjeta.expandir()
        original_ruta = exploracion_cache.ruta_fotograma_version
        ruta_png = _crear_png(
            os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_qimage.png")
        )
        exploracion_cache.ruta_fotograma_version = (
            lambda video_id, ms, version: ruta_png
        )
        ventana = VisorVideos.__new__(VisorVideos)
        try:
            ventana._aplicar_exploracion_densa(
                tarjeta,
                {"video_id": 1},
                {
                    "version": "v9",
                    "fotogramas": [0, 2500],
                    "imagenes": [
                        (0, _crear_qimage(0)),
                        (2500, _crear_qimage(2500)),
                    ],
                },
            )
            ok_qimage = len(tarjeta._previews_densos) == 2
            instantes = sorted(
                d["instante"] for d in tarjeta._previews_densos
            )
            ok_instantes = instantes == [0.0, 2.5]
            ventana._aplicar_exploracion_densa(
                tarjeta,
                {"video_id": 1},
                {"version": "v9", "fotogramas": [0, 2500, 5000]},
            )
            ok_reusa = len(tarjeta._previews_densos) == 3
            instantes_finales = sorted(
                d["instante"] for d in tarjeta._previews_densos
            )
            ok_finales = instantes_finales == [0.0, 2.5, 5.0]
        finally:
            exploracion_cache.ruta_fotograma_version = original_ruta
    return ok_qimage and ok_instantes and ok_reusa and ok_finales, (
        f"densos={len(tarjeta._previews_densos)}"
    )


def test_19():
    original_generar = tareas_videos.generar_fotogramas
    original_listar = tareas_videos.listar_fotogramas_version
    original_ruta = tareas_videos.ruta_fotograma_version
    original_version = tareas_videos.version_actual
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_tarea.png")
    )
    tareas_videos.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    tareas_videos.version_actual = lambda *args, **kwargs: "v9"
    objetivos = tiempos_objetivo(100.0, 15)
    presentes = []
    llamadas = {"n": 0}

    def _generar_fake(
        video_id,
        ruta_video,
        duracion=None,
        cantidad=None,
        on_progreso=None,
        cancelar=None,
    ):
        total = len(objetivos)
        for i in range(3):
            presentes.append(objetivos[i])
            if on_progreso is not None:
                on_progreso(i + 1, total)
        return {
            "version": "v9",
            "fotogramas": list(objetivos),
            "cancelado": False,
        }

    def _listar_fake(video_id, version, duracion=None):
        return list(presentes)

    tareas_videos.generar_fotogramas = _generar_fake
    tareas_videos.listar_fotogramas_version = _listar_fake
    parciales = []
    try:
        tarea = tareas_videos.TareaExploracionDensa(
            1, "C:\\videos\\clip.mp4", duracion=100.0, cantidad=15
        )
        tarea.resultado_parcial.connect(
            lambda d: parciales.append(d)
        )
        resultado = tarea._trabajo()
        # B9.3 virtualización REAL: parciales ahora son lista de ms ints sin QImage masivo
        def _extraer_ms(p):
            f=p.get("fotogramas") or []
            if not f:
                return []
            if isinstance(f[0], (list,tuple)):
                return [ms for ms,_ in f]
            return list(f)
        emitidos = sorted(ms for p in parciales for ms in _extraer_ms(p))
        ok_parciales = len(parciales) == 3
        ok_emitidos = emitidos == sorted(objetivos[:3])
        ok_emitidos_set = tarea._emitidos == set(objetivos[:3])
        ok_version = all(p["version"] == "v9" for p in parciales)
        imagenes = resultado.get("imagenes") or []
        if imagenes and isinstance(imagenes[0], (list,tuple)):
            ms_imagenes = sorted(ms for ms, _ in imagenes)
        else:
            ms_imagenes = sorted(imagenes) if imagenes else []
        if ms_imagenes:
            ok_cola = ms_imagenes == sorted(objetivos[3:])
            ok_todas_qimage = all(isinstance(img, QImage) and not img.isNull() for _, img in imagenes)
        else:
            ok_cola = True
            ok_todas_qimage = True
        ok_resultado = resultado.get("fotogramas") == list(objetivos)
        ok_no_duplicadas = len(emitidos) == len(set(emitidos))
    finally:
        tareas_videos.generar_fotogramas = original_generar
        tareas_videos.listar_fotogramas_version = original_listar
        tareas_videos.ruta_fotograma_version = original_ruta
        tareas_videos.version_actual = original_version
    return (
        ok_parciales
        and ok_emitidos
        and ok_emitidos_set
        and ok_version
        and ok_cola
        and ok_todas_qimage
        and ok_resultado
        and ok_no_duplicadas,
        f"parciales={len(parciales)} emitidos={len(emitidos)} cola={len(ms_imagenes)}",
    )


def test_20():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = threading.Event()
    _TareaExploracionDensaFake.parciales = []
    _TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = _crear_png(
        os.path.join(_CONFIG_TEMPORAL.name, "fotograma_b432_guard.png")
    )
    original_ruta = exploracion_cache.ruta_fotograma_version
    exploracion_cache.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    try:
        with _ventana_con(["clip1.mp4"], [100.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            ok_objetivo = ventana._exploracion_objetivo == "clip1.mp4"
            _esperar(lambda: ventana.gestor_exploracion.hilo is not None)
            tarea = ventana.tarea_exploracion
            tarea.cancelar()
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 1,
                    "version": "v1",
                    "fotogramas": [(0, _crear_qimage(0))],
                }
            )
            ok_parcial_sigue = len(tarjeta1._previews_densos) == 1
            _TareaExploracionDensaFake.liberar.set()
            _esperar(lambda: ventana.gestor_exploracion.hilo is None)
            ok_final_ignorado = len(tarjeta1._previews_densos) == 1
    finally:
        _TareaExploracionDensaFake.liberar.set()
        _TareaExploracionDensaFake.parciales = []
        exploracion_cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_objetivo and ok_parcial_sigue and ok_final_ignorado, (
        f"densos={len(tarjeta1._previews_densos)}"
    )


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
        test_09,
        test_10,
        test_11,
        test_12,
        test_13,
        test_14,
        test_15,
        test_16,
        test_17,
        test_18,
        test_19,
        test_20,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
