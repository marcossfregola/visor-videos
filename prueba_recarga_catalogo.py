import ast
import contextlib
import os
import py_compile
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QLabel

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from rutas import (
    ruta_biblioteca,
    ruta_carpeta_miniaturas,
    ruta_carpeta_videos,
    ruta_raiz,
)
from tareas import Estado, _GESTORES_ACTIVOS
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import (
    MENSAJE_ERROR_GUARDADO,
    MENSAJE_ERROR_RECARGA,
    MENSAJE_ERROR_SINCRONIZACION,
    TAMANIO_PAGINA_INICIAL,
    Tarjeta,
    VisorVideos,
)

QT_MENSAJES = []

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


def _filas(nombres):
    filas = []
    for i, nombre in enumerate(nombres, start=1):
        filas.append(
            (
                nombre,
                os.path.join("C:\\", nombre),
                os.path.splitext(nombre)[1].lower(),
                "2026-08-03T00:00:00",
                float(i % 5),
                i,
                i,
                "h264",
                i % 3,
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


def _filas_de(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(
            "SELECT nombre, ruta, extension, fecha_importacion, duracion_segundos, "
            "ancho, alto, codec_video, cantidad_miniaturas "
            "FROM videos ORDER BY nombre"
        ).fetchall()
    finally:
        conn.close()


def _carpeta_con(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        with open(os.path.join(temp.name, nombre), "w", encoding="utf-8") as f:
            f.write("contenido")
    return temp


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _cadena_terminada(ventana):
    return (
        ventana.gestor.hilo is None
        and not ventana._escaneo_pendiente
        and not ventana._tamanos_pendiente
        and not ventana._ffprobe_pendiente
        and not ventana._miniaturas_pendiente
        and not ventana._guardado_pendiente
        and not ventana._sincronizacion_pendiente
        and not ventana._recarga_catalogo_pendiente
    )


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original = escanear_mod.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original
        temp.cleanup()


@contextlib.contextmanager
def _dialogo_falso(ruta):
    original = visor_videos.QFileDialog.getExistingDirectory
    visor_videos.QFileDialog.getExistingDirectory = lambda *a, **k: ruta
    try:
        yield
    finally:
        visor_videos.QFileDialog.getExistingDirectory = original


class _Control:
    def __init__(self, fn):
        self.fn = fn
        self.llamadas = 0
        self.empezada = threading.Event()
        self.soltar = threading.Event()
        self.ident = None
        self.principal = None

    def __call__(self, *args, **kwargs):
        self.llamadas += 1
        self.ident = threading.get_ident()
        self.principal = QThread.isMainThread()
        self.empezada.set()
        self.soltar.wait(10)
        return self.fn(*args, **kwargs)


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_recarga_catalogo.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        tipos = []
        tareas_vistas = []
        ventana.gestor.tarea_iniciada.connect(
            lambda: tipos.append(type(ventana.gestor.tarea).__name__)
        )
        ventana.gestor.tarea_iniciada.connect(
            lambda: tareas_vistas.append(ventana.gestor.tarea)
        )
        orig_diff = escanear_mod.detectar_diferencias
        orig_listar = tv.listar_videos_paginado
        control_sync = _Control(orig_diff)
        control_recarga = _Control(orig_listar)
        escanear_mod.detectar_diferencias = control_sync
        tv.listar_videos_paginado = control_recarga
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda: control_sync.empezada.is_set())
            mismo_gestor = (
                ventana.gestor.tarea is ventana.tarea_sincronizacion
            )
            control_sync.soltar.set()
            _esperar(lambda: control_recarga.empezada.is_set())
            es_recarga = isinstance(
                ventana.tarea_recarga_catalogo, TareaLecturaCatalogoPaginada
            )
            misma_tarea = ventana.gestor.tarea is ventana.tarea_recarga_catalogo
            activo_recarga = ventana.gestor.activo
            principal = control_recarga.principal
            control_recarga.soltar.set()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.detectar_diferencias = orig_diff
            tv.listar_videos_paginado = orig_listar
        ventana.close()
        _limpiar(ventana)
        esperados = [
            "TareaEscaneo",
            "TareaTamanosArchivos",
            "TareaFFprobe",
            "TareaGuardarVideos",
            "TareaMiniaturasPorId",
            "TareaActualizarCantidadMiniaturas",
            "TareaSincronizacionCatalogo",
            "TareaLecturaCatalogoPaginada",
        ]
        ok = (
            tipos == esperados
            and len(tareas_vistas) == 8
            and len(set(tareas_vistas)) == 8
            and mismo_gestor
            and es_recarga
            and misma_tarea
            and activo_recarga
            and principal is False
        )
        return (
            ok,
            f"tipos={tipos} mismo_gestor={mismo_gestor} es_recarga={es_recarga} "
            f"misma_tarea={misma_tarea} activo={activo_recarga} "
            f"principal={principal}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        llamadas = {"recarga": 0}
        orig_guardado = tv.guardar_videos
        orig_listar_guardado = tv.listar_videos_paginado

        def _falla_guardado(datos_videos, ruta_db=None):
            raise RuntimeError("fallo controlado del guardado")

        def _recarga(*a, **k):
            llamadas["recarga"] += 1
            raise AssertionError("no debe recargarse tras error de guardado")

        tv.guardar_videos = _falla_guardado
        tv.listar_videos_paginado = _recarga
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig_guardado
            tv.listar_videos_paginado = orig_listar_guardado
        estado = ventana.estado_escaneo.text()
        despues = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado == MENSAJE_ERROR_GUARDADO
            and llamadas == {"recarga": 0}
            and despues == antes
        )
        return (
            ok,
            f"estado={estado!r} recarga_llamadas={llamadas} "
            f"tarjetas={antes}->{despues}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["nuevo.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues = [nombre for nombre, _ in ventana.tarjetas]
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            antes == []
            and despues == ["nuevo.mkv"]
            and [f[0] for f in filas] == ["nuevo.mkv"]
        )
        return ok, f"antes={antes} despues={despues} filas={[f[0] for f in filas]}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_05():
    # B8.3: a.mp4 en C:\ no es subcarpeta de temp, se preserva; b.mkv en C:\ y temp son homónimos distintos
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mkv"]))
    carpeta = _carpeta_con(["b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues = [nombre for nombre, _ in ventana.tarjetas]
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        # B8.3: DB debe preservar a.mp4 de C:\ (no es subcarpeta) y b.mkv orig en C:\ + nuevo b.mkv en temp (homónimos)
        filas_nombres = sorted([f[0] for f in filas])
        ok = (
            antes == ["a.mp4", "b.mkv"]
            and despues == ["b.mkv"]
            and "a.mp4" not in despues
            and filas_nombres.count("b.mkv") == 2
            and "a.mp4" in filas_nombres
        )
        return ok, f"antes={antes} despues={despues} filas={[f[0] for f in filas]}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_06():
    origen = os.path.join(ruta_carpeta_videos(), "video_real.mp4")
    temp, ruta_db = _crear_bd(_filas(["video_real.mp4", "ausente.mp4"]))
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        if not os.path.isfile(origen):
            return False, "no existe video_real.mp4 en videos_prueba"
        shutil.copyfile(origen, os.path.join(carpeta_temp.name, "video_real.mp4"))
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _miniaturas_temporales():
            with _dialogo_falso(carpeta_temp.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        nombres = [nombre for nombre, _ in ventana.tarjetas]
        campos = {}
        for nombre, tarjeta in ventana.tarjetas:
            if nombre != "video_real.mp4":
                continue
            for etiqueta in tarjeta.findChildren(QLabel):
                texto = etiqueta.text()
                if not texto.startswith("<b>"):
                    continue
                partes = texto.split("</b>")
                clave = partes[0][len("<b>"):]
                campos[clave] = partes[1].strip()
        conservado = ventana.resultado_sincronizacion is not None
        ventana.close()
        _limpiar(ventana)
        ok = (
            nombres == ["video_real.mp4"]
            and campos.get("Duración:") == "0:05"
            and campos.get("Resolución:") == "640x360"
            and campos.get("Codec:") == "h264"
            and campos.get("Miniaturas:") == "1"
            and conservado
        )
        return (
            ok,
            f"nombres={nombres} campos={campos} conservado={conservado}",
        )
    finally:
        carpeta_temp.cleanup()
        temp.cleanup()


def test_07():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    carpeta = _carpeta_con(["manzana.mp4", "uva.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.busqueda.setText("man")
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        visibles = ventana.tarjetas_visibles()
        contador = ventana.contador.text()
        tarjetas = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            ventana.busqueda.text() == "man"
            and visibles == ["manzana.mp4"]
            and contador == "1 video"
            and tarjetas == ["manzana.mp4", "uva.mp4"]
        )
        return (
            ok,
            f"filtro={ventana.busqueda.text()!r} visibles={visibles} "
            f"contador={contador!r} tarjetas={tarjetas}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mkv", "c.avi"]))
    carpeta = _carpeta_con(["x.mp4", "y.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        contador_inicial = ventana.contador.text()
        tarjetas_inicial = [nombre for nombre, _ in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        contador_final = ventana.contador.text()
        tarjetas_final = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            contador_inicial == "3 videos"
            and tarjetas_inicial == ["a.mp4", "b.mkv", "c.avi"]
            and contador_final == "2 videos"
            and tarjetas_final == ["x.mp4", "y.mkv"]
        )
        return (
            ok,
            f"inicial={contador_inicial!r}/{tarjetas_inicial} "
            f"final={contador_final!r}/{tarjetas_final}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mkv", "c.avi"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        viejas = [tarjeta for _, tarjeta in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        _esperar(
            lambda v=ventana: len(v.contenedor.findChildren(Tarjeta))
            == len(v.tarjetas)
        )
        widgets_grilla = [
            ventana.cuadricula.itemAt(i).widget()
            for i in range(ventana.cuadricula.count())
        ]
        vivas = [t for t in viejas if t in widgets_grilla]
        hijas = ventana.contenedor.findChildren(Tarjeta)
        todas_nuevas = all(t in [tt for _, tt in ventana.tarjetas] for t in hijas)
        ventana.close()
        _limpiar(ventana)
        ok = (
            len(hijas) == len(ventana.tarjetas) == 1
            and vivas == []
            and todas_nuevas
            and ventana.cuadricula.count() == 1
        )
        return (
            ok,
            f"hijas={len(hijas)} tarjetas={len(ventana.tarjetas)} "
            f"vivas={len(vivas)} grilla={ventana.cuadricula.count()}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mkv"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cuadricula = ventana.cuadricula
        area = ventana.area
        contenedor = ventana.contenedor
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ok = (
            ventana.cuadricula is cuadricula
            and ventana.area is area
            and ventana.contenedor is contenedor
            and ventana.cuadricula.count() == len(ventana.tarjetas) == 1
        )
        return (
            ok,
            f"misma_grilla={ventana.cuadricula is cuadricula} "
            f"misma_area={ventana.area is area} "
            f"cuenta={ventana.cuadricula.count()}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        llamadas = {"recarga": 0}
        orig_diff = escanear_mod.detectar_diferencias
        orig_listar_error = tv.listar_videos_paginado

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado de sincronizacion")

        def _recarga(*a, **k):
            llamadas["recarga"] += 1
            raise AssertionError("no debe recargarse tras error de sincronizacion")

        escanear_mod.detectar_diferencias = _falla
        tv.listar_videos_paginado = _recarga
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.detectar_diferencias = orig_diff
            tv.listar_videos_paginado = orig_listar_error
        estado = ventana.estado_escaneo.text()
        despues = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado == MENSAJE_ERROR_SINCRONIZACION
            and llamadas == {"recarga": 0}
            and despues == antes
        )
        return (
            ok,
            f"estado={estado!r} recarga_llamadas={llamadas} "
            f"tarjetas={antes}->{despues}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        orig_listar = tv.listar_videos_paginado

        def _falla_lectura(*a, **k):
            raise RuntimeError("fallo controlado de la recarga")

        tv.listar_videos_paginado = _falla_lectura
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig_listar
        estado_error = ventana.estado_escaneo.text()
        gestor_error = ventana.gestor.estado
        hab_error = ventana.boton_escanear.isEnabled()
        pendiente_error = ventana._recarga_catalogo_pendiente
        tarea_error = ventana.tarea_recarga_catalogo
        despues_error = [nombre for nombre, _ in ventana.tarjetas]
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues_recuperado = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_error == MENSAJE_ERROR_RECARGA
            and gestor_error == Estado.INACTIVO
            and hab_error
            and not pendiente_error
            and tarea_error is None
            and despues_error == antes
            and despues_recuperado == ["x.mp4"]
        )
        return (
            ok,
            f"estado_error={estado_error!r} gestor={gestor_error} hab={hab_error} "
            f"pendiente={pendiente_error} tarjetas={antes}->{despues_error} "
            f"recuperado={despues_recuperado}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        _esperar(lambda v=ventana: not getattr(v, "gestor_resumen", None) or (not v.gestor_resumen.activo and not v._cola_resumen), timeout_ms=5000)
        ok_exito = (
            ventana.gestor.estado == Estado.INACTIVO
            and ventana.gestor.hilo is None
            and ventana.gestor.tarea is None
            and not ventana._recarga_catalogo_pendiente
            and ventana.tarea_recarga_catalogo is None
            and not ventana._sincronizacion_pendiente
            and ventana.boton_escanear.isEnabled()
            and ventana.boton_seleccionar_carpeta.isEnabled()
            and len(_GESTORES_ACTIVOS) == 0
        )
        ventana.close()
        _limpiar(ventana)

        ventana2 = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana2: v._carga_completada and v.gestor.hilo is None)
        orig_listar = tv.listar_videos_paginado

        def _falla_lectura(*a, **k):
            raise RuntimeError("fallo controlado de la recarga")

        tv.listar_videos_paginado = _falla_lectura
        try:
            with _dialogo_falso(carpeta.name):
                ventana2.seleccionar_carpeta()
            ventana2.boton_escanear.click()
            _esperar(lambda v=ventana2: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig_listar
        _esperar(
            lambda v=ventana2: not v.gestor_previews.activo
            and not v._cola_previews
            and not v._timer_previews.isActive()
        )
        _esperar(lambda v=ventana2: not getattr(v, "gestor_resumen", None) or (not v.gestor_resumen.activo and not v._cola_resumen), timeout_ms=5000)
        ok_error = (
            ventana2.gestor.estado == Estado.INACTIVO
            and ventana2.gestor.hilo is None
            and ventana2.gestor.tarea is None
            and not ventana2._recarga_catalogo_pendiente
            and ventana2.tarea_recarga_catalogo is None
            and ventana2.boton_escanear.isEnabled()
            and len(_GESTORES_ACTIVOS) == 0
        )
        ventana2.close()
        _limpiar(ventana2)
        return (
            ok_exito and ok_error,
            f"exito={ok_exito} error={ok_error} "
            f"gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_14():
    ruta = os.path.join(ruta_raiz(), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)
    importadas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                importadas.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                importadas.add(nodo.module.split(".")[0])
            for alias in nodo.names:
                if alias.name != "*":
                    importadas.add(alias.name)
    ok = (
        "sqlite3" not in importadas
        and not hasattr(visor_videos, "sqlite3")
        and not hasattr(visor_videos, "connect")
    )
    return ok, f"importaciones={sorted(importadas)}"


def test_15():
    ruta = os.path.join(ruta_raiz(), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
    llamadas = [
        n
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "listar_videos_paginado"
    ]
    ok = (
        "listar_videos_paginado" not in nombres
        and not hasattr(visor_videos, "listar_videos_paginado")
        and not llamadas
    )
    return ok, f"llamadas_directas={len(llamadas)}"


def test_16():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig_diff = escanear_mod.detectar_diferencias
        orig_listar = tv.listar_videos_paginado
        control_sync = _Control(orig_diff)
        control_recarga = _Control(orig_listar)
        escanear_mod.detectar_diferencias = control_sync
        tv.listar_videos_paginado = control_recarga
        conteos = {
            "ffprobe": 0,
            "ffmpeg": 0,
            "miniaturas": 0,
        }
        originales = {
            "ffprobe_tv": tv.obtener_datos_ffprobe,
            "ffprobe_mod": escanear_mod.obtener_datos_ffprobe,
            "run": escanear_mod.subprocess.run,
            "asegurar_tv": tv.asegurar_miniaturas,
            "asegurar_mod": escanear_mod.asegurar_miniaturas,
            "contar_mod": escanear_mod.contar_miniaturas,
        }

        def _prohibido(clave):
            def f(*a, **k):
                conteos[clave] += 1
                raise AssertionError(
                    f"no debe ejecutarse {clave} durante la recarga"
                )

            return f

        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda: control_sync.empezada.is_set())
            tv.obtener_datos_ffprobe = _prohibido("ffprobe")
            escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
            escanear_mod.subprocess.run = _prohibido("ffmpeg")
            tv.asegurar_miniaturas = _prohibido("miniaturas")
            escanear_mod.asegurar_miniaturas = _prohibido("miniaturas")
            escanear_mod.contar_miniaturas = _prohibido("miniaturas")
            control_sync.soltar.set()
            _esperar(lambda: control_recarga.empezada.is_set())
            durante = dict(conteos)
            control_recarga.soltar.set()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.detectar_diferencias = orig_diff
            tv.listar_videos_paginado = orig_listar
            tv.obtener_datos_ffprobe = originales["ffprobe_tv"]
            escanear_mod.obtener_datos_ffprobe = originales["ffprobe_mod"]
            escanear_mod.subprocess.run = originales["run"]
            tv.asegurar_miniaturas = originales["asegurar_tv"]
            escanear_mod.asegurar_miniaturas = originales["asegurar_mod"]
            escanear_mod.contar_miniaturas = originales["contar_mod"]
        ventana.close()
        _limpiar(ventana)
        ok = durante == {"ffprobe": 0, "ffmpeg": 0, "miniaturas": 0}
        return ok, f"durante={durante}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        antes = len(QT_MENSAJES)
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        for _ in range(3):
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        ventana.close()
        _limpiar(ventana)
        nuevos = QT_MENSAJES[antes:]
        avisos = [m for m in nuevos if "Destroyed while thread" in m]
        ok = len(avisos) == 0 and len(_GESTORES_ACTIVOS) == 0
        return ok, f"avisos={len(avisos)} gestores={len(_GESTORES_ACTIVOS)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig_diff = escanear_mod.detectar_diferencias
        orig_listar = tv.listar_videos_paginado
        control_sync = _Control(orig_diff)
        control_recarga = _Control(orig_listar)
        escanear_mod.detectar_diferencias = control_sync
        tv.listar_videos_paginado = control_recarga
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda: control_sync.empezada.is_set())
            control_sync.soltar.set()
            _esperar(lambda: control_recarga.empezada.is_set())
            activo_mientras = ventana.gestor.activo
            control_recarga.soltar.set()
            ventana.close()
            ventana.gestor.cerrar()
        finally:
            escanear_mod.detectar_diferencias = orig_diff
            tv.listar_videos_paginado = orig_listar
        _procesar(50)
        _limpiar(ventana)
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        hilos = [t for t in threading.enumerate() if t is not threading.main_thread()]
        ok = (
            activo_mientras
            and len(avisos) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and len(hilos) == 0
        )
        return (
            ok,
            f"activo_mientras={activo_mientras} avisos={len(avisos)} "
            f"hilos={len(hilos)} gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_19():
    comando = [sys.executable, "prueba_smoke.py"]
    resultado = subprocess.run(
        comando,
        cwd=ruta_raiz(),
        capture_output=True,
        text=True,
        timeout=90,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    ok = (
        resultado.returncode == 0
        and "guardado_total=3" in salida
        and "resumen_sincronizacion=" in salida
        and "0 incorporados, 0 eliminados, 0 candidatos restantes" in salida
        and "tarjetas_finales=['clip.avi', 'peli.mp4', 'serie.mkv']" in salida
        and "escanear_boton_final=True" in salida
        and "visibles_filtro=" in salida
        and "contador_final=" in salida
        and "Destroyed while thread" not in salida
        and "No se pudo actualizar el catálogo" not in salida
        and "No se pudo sincronizar el catálogo" not in salida
    )
    return (
        ok,
        f"exit={resultado.returncode} "
        f"tarjetas={'tarjetas_finales=[' in salida} "
        f"avisos={('Destroyed while thread' in salida)}",
    )


def test_20():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        def estado_real():
            bd = ruta_biblioteca()
            mini = ruta_carpeta_miniaturas()
            vid = ruta_carpeta_videos()
            return (
                os.path.isfile(bd),
                os.path.getmtime(bd) if os.path.isfile(bd) else None,
                os.path.getsize(bd) if os.path.isfile(bd) else None,
                sorted(os.listdir(mini)) if os.path.isdir(mini) else None,
                sorted(os.listdir(vid)) if os.path.isdir(vid) else None,
            )

        antes = estado_real()
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ventana.close()
        _limpiar(ventana)
        despues = estado_real()
        ok = antes == despues
        return ok, f"reales_intactos={antes == despues}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


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
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/20")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
