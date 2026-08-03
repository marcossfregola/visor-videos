import ast
import contextlib
import os
import py_compile
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QPushButton

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
from tareas_videos import TareaEscaneo
from visor_videos import (
    MENSAJE_ESCANEANDO,
    MENSAJE_ERROR_ESCANEO,
    MENSAJE_ERROR_FFPROBE,
    MENSAJE_RUTA_INVALIDA,
    MENSAJE_SIN_ESCANEO,
    TAMANIO_PAGINA_INICIAL,
    VisorVideos,
)

QT_MENSAJES = []


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
                "2026-08-02T00:00:00",
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
                cantidad_miniaturas INTEGER
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


def _filas_resultado(nombres):
    return [(nombre, None, None, None, None, 0) for nombre in nombres]


def _resultado(nombres):
    filas = _filas_resultado(nombres)
    return {
        "videos": filas,
        "total": len(filas),
        "limite": TAMANIO_PAGINA_INICIAL,
        "desplazamiento": 0,
    }


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=6000, paso_ms=20):
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


def _escanear_terminado(ventana):
    return (
        ventana.gestor.hilo is None
        and not ventana._escaneo_pendiente
        and not ventana._ffprobe_pendiente
        and not ventana._guardado_pendiente
    )


@contextlib.contextmanager
def _dialogo_falso(ruta):
    original = visor_videos.QFileDialog.getExistingDirectory
    visor_videos.QFileDialog.getExistingDirectory = lambda *a, **k: ruta
    try:
        yield
    finally:
        visor_videos.QFileDialog.getExistingDirectory = original


class _ControlLectura:
    def __init__(self, resultado):
        self.resultado = resultado
        self.llamadas = 0
        self.empezada = threading.Event()
        self.soltar = threading.Event()
        self.ident = None

    def __call__(self, *args, **kwargs):
        self.llamadas += 1
        self.ident = threading.get_ident()
        self.empezada.set()
        self.soltar.wait(10)
        return self.resultado


@contextlib.contextmanager
def _lectura_controlada(resultado):
    control = _ControlLectura(resultado)
    original = tv.listar_videos_paginado
    tv.listar_videos_paginado = control
    try:
        yield control
    finally:
        control.soltar.set()
        tv.listar_videos_paginado = original


class _ControlEscaneo:
    def __init__(self, resultado):
        self.resultado = resultado
        self.llamadas = 0
        self.empezada = threading.Event()
        self.soltar = threading.Event()
        self.ident = None

    def __call__(self, *args, **kwargs):
        self.llamadas += 1
        self.ident = threading.get_ident()
        self.empezada.set()
        self.soltar.wait(10)
        return self.resultado


@contextlib.contextmanager
def _escaneo_controlado(resultado):
    control = _ControlEscaneo(resultado)
    original = tv.escanear_videos
    tv.escanear_videos = control
    try:
        yield control
    finally:
        control.soltar.set()
        tv.escanear_videos = original


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


def _carpeta_con(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        with open(os.path.join(temp.name, nombre), "w", encoding="utf-8") as f:
            f.write("contenido")
    return temp


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_escaneo_interfaz.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd([])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        es_boton = isinstance(ventana.boton_escanear, QPushButton)
        texto = ventana.boton_escanear.text()
        habilitado = ventana.boton_escanear.isEnabled()
        estado = ventana.estado_escaneo.text()
        detectados = ventana.videos_detectados
        tarea = ventana.tarea_escaneo
        ventana.close()
        _limpiar(ventana)
        ok = (
            es_boton
            and texto == "Escanear carpeta"
            and not habilitado
            and estado == MENSAJE_SIN_ESCANEO
            and detectados is None
            and tarea is None
        )
        return (
            ok,
            f"boton={es_boton} texto={texto!r} habilitado={habilitado} "
            f"estado={estado!r} detectados={detectados}",
        )
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd([])
    try:
        llamadas = {"escaneo": 0}
        orig = tv.escanear_videos

        def _escaneo(*a, **k):
            llamadas["escaneo"] += 1
            raise AssertionError("no debe escanearse automáticamente")

        ventana = None
        tv.escanear_videos = _escaneo
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        finally:
            tv.escanear_videos = orig
        habilitado = ventana.boton_escanear.isEnabled()
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"escaneo": 0} and not habilitado and estado == MENSAJE_SIN_ESCANEO
        return ok, f"llamadas={llamadas} habilitado={habilitado} estado={estado!r}"
    finally:
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        llamadas = {"escaneo": 0}
        orig = tv.escanear_videos

        def _escaneo(*a, **k):
            llamadas["escaneo"] += 1
            raise AssertionError("no debe escanearse al seleccionar carpeta")

        ventana = None
        tv.escanear_videos = _escaneo
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            habilitado = ventana.boton_escanear.isEnabled()
        finally:
            tv.escanear_videos = orig
        estado = ventana.estado_escaneo.text()
        detectados = ventana.videos_detectados
        ventana.close()
        _limpiar(ventana)
        ok = (
            llamadas == {"escaneo": 0}
            and habilitado
            and estado == MENSAJE_SIN_ESCANEO
            and detectados is None
        )
        return ok, f"llamadas={llamadas} habilitado={habilitado} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        habilitado = ventana.boton_escanear.isEnabled()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = habilitado and guardada == os.path.abspath(carpeta.name)
        return ok, f"habilitado={habilitado} guardada={guardada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        previa = ventana.carpeta_seleccionada
        hab_a = ventana.boton_escanear.isEnabled()
        with _dialogo_falso(""):
            ventana.seleccionar_carpeta()
        conservada = ventana.carpeta_seleccionada
        hab_b = ventana.boton_escanear.isEnabled()
        ventana.close()
        _limpiar(ventana)
        ok = conservada == previa and hab_a and hab_b
        return ok, f"previa={previa} conservada={conservada} hab={hab_a},{hab_b}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd([])
    try:
        inexistente = os.path.join(temp.name, "no_existe")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(inexistente):
            ventana.seleccionar_carpeta()
        habilitado = ventana.boton_escanear.isEnabled()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = not habilitado and guardada is None
        return ok, f"habilitado={habilitado} guardada={guardada}"
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = None
        with _lectura_controlada(_resultado([])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)
            habilitado = ventana.boton_escanear.isEnabled()
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.iniciar_escaneo()
            pendiente = ventana._escaneo_pendiente
            tarea = ventana.tarea_escaneo
            control.soltar.set()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        ok = not habilitado and not pendiente and tarea is None
        return ok, f"habilitado={habilitado} pendiente={pendiente} tarea={tarea}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _escaneo_controlado(["a.mp4", "b.mkv"]) as control_escaneo:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            control_escaneo.empezada.wait(5)
            tarea = ventana.tarea_escaneo
            es_escaneo = isinstance(tarea, TareaEscaneo)
            carpeta_tarea = tarea.carpeta if tarea else None
            gestor_tarea = ventana.gestor.tarea
            mismas = tarea is gestor_tarea
            pendiente = ventana._escaneo_pendiente
            estado = ventana.estado_escaneo.text()
            hab_escanear = ventana.boton_escanear.isEnabled()
            hab_seleccionar = ventana.boton_seleccionar_carpeta.isEnabled()
            control_escaneo.soltar.set()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.close()
        _limpiar(ventana)
        ok = (
            es_escaneo
            and carpeta_tarea == os.path.abspath(carpeta.name)
            and mismas
            and pendiente
            and estado == MENSAJE_ESCANEANDO
            and not hab_escanear
            and not hab_seleccionar
        )
        return (
            ok,
            f"tipo={type(tarea).__name__} carpeta={carpeta_tarea} mismas={mismas} "
            f"estado={estado!r} hab_escanear={hab_escanear} hab_seleccionar={hab_seleccionar}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        marcado = {"valor": False, "mientras": False}
        with _escaneo_controlado(["a.mp4"]) as control_escaneo:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            control_escaneo.empezada.wait(5)

            def _marcar():
                marcado["valor"] = True
                marcado["mientras"] = (
                    ventana.gestor.estado == Estado.OCUPADO
                    and ventana._escaneo_pendiente
                )

            QTimer.singleShot(200, _marcar)
            _procesar(400)
            control_escaneo.soltar.set()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.close()
        _limpiar(ventana)
        ok = marcado["valor"] and marcado["mientras"]
        return ok, f"timer_disp={marcado['valor']} mientras={marcado['mientras']}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _escaneo_controlado(["a.mp4", "b.mkv", "c.avi"]) as control_escaneo:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            control_escaneo.empezada.wait(5)
            tarea_original = ventana.tarea_escaneo
            gestor_original = ventana.gestor.tarea
            ventana.iniciar_escaneo()
            tarea_segunda = ventana.tarea_escaneo
            gestor_segunda = ventana.gestor.tarea
            pendiente = ventana._escaneo_pendiente
            hab_escanear = ventana.boton_escanear.isEnabled()
            control_escaneo.soltar.set()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.close()
        _limpiar(ventana)
        ok = (
            tarea_original is tarea_segunda
            and gestor_original is gestor_segunda
            and pendiente
            and not hab_escanear
        )
        return (
            ok,
            f"misma_tarea={tarea_original is tarea_segunda} "
            f"pendiente={pendiente} hab_escanear={hab_escanear}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        hab_escanear = ventana.boton_escanear.isEnabled()
        hab_seleccionar = ventana.boton_seleccionar_carpeta.isEnabled()
        ventana.close()
        _limpiar(ventana)
        ok = (
            detectados == []
            and estado == "0 videos detectados"
            and hab_escanear
            and hab_seleccionar
            and ventana.gestor.hilo is None
        )
        return ok, f"detectados={detectados} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_13():
    nombres = ["z.mp4", "a.avi", "m.mkv", "b.mp4", "doc.txt", "imagen.png"]
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(nombres)
    try:
        esperado = sorted(
            n for n in nombres
            if os.path.splitext(n)[1].lower() in {".mp4", ".mkv", ".avi"}
        )
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            detectados == esperado
            and detectados == sorted(esperado)
            and estado == f"{len(esperado)} videos detectados"
        )
        return ok, f"detectados={detectados} esperado={esperado} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_14():
    nombres = ["doc.txt", "nota.log", "imagen.png", "sin_ext"]
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(nombres)
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = detectados == [] and estado == "0 videos detectados"
        return ok, f"detectados={detectados} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["unico.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = detectados == ["unico.mp4"] and estado == "1 video detectado"
        return ok, f"detectados={detectados} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_16():
    nombres = ["Beta.mp4", "alfa.mp4", "Gama.mkv", "delta.avi"]
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(nombres)
    try:
        esperado = sorted(
            n for n in nombres
            if os.path.splitext(n)[1].lower() in {".mp4", ".mkv", ".avi"}
        )
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        ventana.close()
        _limpiar(ventana)
        ok = (
            type(detectados) is list
            and detectados == esperado
            and detectados == sorted(detectados)
        )
        return ok, f"detectados={detectados} esperado={esperado}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_17():
    nombres = ["a.mp4", "b.mkv", "c.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = list(ventana.tarjetas)
        nombres_antes = [nombre for nombre, _ in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        nombres_despues = [nombre for nombre, _ in ventana.tarjetas]
        mismas = all(
            ventana.tarjetas[i][1] is antes[i][1]
            for i in range(len(antes))
        )
        visibles = ventana.tarjetas_visibles()
        ventana.close()
        _limpiar(ventana)
        ok = (
            nombres_despues == nombres_antes
            and mismas
            and len(ventana.tarjetas) == len(nombres)
            and visibles == sorted(nombres)
        )
        return (
            ok,
            f"antes={len(antes)} despues={len(ventana.tarjetas)} "
            f"mismas_tarjetas={mismas} visibles={visibles}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_18():
    nombres = ["a.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        llamadas = {"lectura": 0}
        orig = tv.listar_videos_paginado

        def _lectura(*a, **k):
            llamadas["lectura"] += 1
            raise AssertionError("el escaneo no debe recargar el catálogo")

        tv.listar_videos_paginado = _lectura
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            tv.listar_videos_paginado = orig
        tarjetas = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"lectura": 0} and tarjetas == ["a.mp4"]
        return ok, f"llamadas={llamadas} tarjetas={tarjetas}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        tipos = []
        ventana.gestor.tarea_iniciada.connect(
            lambda: tipos.append(type(ventana.gestor.tarea).__name__)
        )
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute(
                "SELECT nombre, ruta, extension, fecha_importacion FROM videos"
            ).fetchall()
        finally:
            conn.close()
        guardado = ventana.registros_guardados
        ventana.close()
        _limpiar(ventana)
        ok = (
            len(filas) == 1
            and filas[0][0] == "x.mp4"
            and filas[0][1] == os.path.join(os.path.abspath(carpeta.name), "x.mp4")
            and filas[0][2] == ".mp4"
            and filas[0][3]
            and guardado == 1
            and tipos == ["TareaEscaneo", "TareaFFprobe", "TareaGuardarVideos"]
        )
        return ok, f"filas={filas} guardado={guardado} tipos={tipos}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_20():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        info = {"llamadas": 0}
        orig_ff_tv = tv.obtener_datos_ffprobe
        orig_ff_mod = escanear_mod.obtener_datos_ffprobe

        def _ff(ruta):
            info["llamadas"] += 1
            info["ident"] = threading.get_ident()
            info["principal"] = QThread.isMainThread()
            return orig_ff_tv(ruta)

        tv.obtener_datos_ffprobe = _ff
        escanear_mod.obtener_datos_ffprobe = _ff
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            tv.obtener_datos_ffprobe = orig_ff_tv
            escanear_mod.obtener_datos_ffprobe = orig_ff_mod
        detectados = ventana.videos_detectados
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute(
                "SELECT nombre, duracion_segundos, ancho, alto, codec_video "
                "FROM videos"
            ).fetchall()
        finally:
            conn.close()
        ventana.close()
        _limpiar(ventana)
        ok = (
            info["llamadas"] == 1
            and info.get("principal") is False
            and detectados == ["x.mp4"]
            and filas == [("x.mp4", None, None, None, None)]
        )
        return (
            ok,
            f"ffprobe={info.get('llamadas')} principal={info.get('principal')} "
            f"filas={filas}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_21():
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
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.close()
        _limpiar(ventana)
        despues = estado_real()
        conn = sqlite3.connect(ruta_db)
        try:
            filas = [f[0] for f in conn.execute("SELECT nombre FROM videos")]
        finally:
            conn.close()
        ok = antes == despues and filas == ["x.mp4"]
        return ok, f"reales_intactos={antes == despues} filas={filas}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_22():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    ruta = carpeta.name
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(ruta):
            ventana.seleccionar_carpeta()
        previa = ventana.carpeta_seleccionada
        carpeta.cleanup()
        ventana.iniciar_escaneo()
        mensaje = ventana.mensaje_carpeta.text()
        pendiente = ventana._escaneo_pendiente
        tarea = ventana.tarea_escaneo
        hilo = ventana.gestor.hilo
        detectados = ventana.videos_detectados
        ventana.close()
        _limpiar(ventana)
        ok = (
            previa == os.path.abspath(ruta)
            and mensaje == MENSAJE_RUTA_INVALIDA
            and not pendiente
            and tarea is None
            and hilo is None
            and detectados is None
        )
        return (
            ok,
            f"mensaje={mensaje!r} pendiente={pendiente} hilo={hilo} "
            f"detectados={detectados}",
        )
    finally:
        temp.cleanup()


def test_23():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig = tv.escanear_videos

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado")

        tv.escanear_videos = _falla
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            tv.escanear_videos = orig
        estado = ventana.estado_escaneo.text()
        hab_escanear = ventana.boton_escanear.isEnabled()
        hab_seleccionar = ventana.boton_seleccionar_carpeta.isEnabled()
        usable = True
        try:
            ventana.busqueda.setText("x")
            ventana.filtrar("x")
            _ = ventana.contador.text()
        except Exception:
            usable = False
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado == MENSAJE_ERROR_ESCANEO
            and hab_escanear
            and hab_seleccionar
            and usable
            and ventana.gestor.hilo is None
        )
        return (
            ok,
            f"estado={estado!r} usable={usable} hab={hab_escanear},{hab_seleccionar}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_24():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["exito.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        previo = ventana.videos_detectados
        estado_previo = ventana.estado_escaneo.text()
        orig = tv.escanear_videos

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado")

        tv.escanear_videos = _falla
        try:
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            tv.escanear_videos = orig
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            previo == ["exito.mp4"]
            and estado_previo == "1 video detectado"
            and detectados == previo
            and estado == MENSAJE_ERROR_ESCANEO
        )
        return ok, f"previo={previo} despues={detectados} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_25():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["exito.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        orig = tv.escanear_videos

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado")

        tv.escanear_videos = _falla
        try:
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            tv.escanear_videos = orig
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = detectados == ["exito.mp4"] and estado == "1 video detectado"
        return ok, f"detectados={detectados} estado={estado!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_26():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        secuencia = []
        tareas_vistas = []
        ventana.gestor.tarea_iniciada.connect(
            lambda: secuencia.append(type(ventana.gestor.tarea).__name__)
        )
        ventana.gestor.tarea_iniciada.connect(
            lambda: tareas_vistas.append(ventana.gestor.tarea)
        )
        control_escaneo = _Control(tv.escanear_videos)
        control_ffprobe = _Control(tv.obtener_datos_ffprobe)
        control_guardado = _Control(tv.guardar_videos)
        originales = (
            tv.escanear_videos,
            tv.obtener_datos_ffprobe,
            tv.guardar_videos,
        )
        tv.escanear_videos = control_escaneo
        tv.obtener_datos_ffprobe = control_ffprobe
        tv.guardar_videos = control_guardado
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()

            control_escaneo.empezada.wait(5)
            _procesar(300)
            paso_uno = list(secuencia)
            estado_uno = ventana.gestor.estado
            _procesar(300)
            paso_uno_b = list(secuencia)

            control_escaneo.soltar.set()
            control_ffprobe.empezada.wait(5)
            _procesar(300)
            paso_dos = list(secuencia)
            estado_dos = ventana.gestor.estado
            _procesar(300)
            paso_dos_b = list(secuencia)

            control_ffprobe.soltar.set()
            control_guardado.empezada.wait(5)
            _procesar(300)
            paso_tres = list(secuencia)
            estado_tres = ventana.gestor.estado
            _procesar(300)
            paso_tres_b = list(secuencia)

            control_guardado.soltar.set()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            (
                tv.escanear_videos,
                tv.obtener_datos_ffprobe,
                tv.guardar_videos,
            ) = originales
        ventana.close()
        _limpiar(ventana)
        ok = (
            paso_uno == ["TareaEscaneo"]
            and paso_uno_b == paso_uno
            and estado_uno == Estado.OCUPADO
            and paso_dos == ["TareaEscaneo", "TareaFFprobe"]
            and paso_dos_b == paso_dos
            and estado_dos == Estado.OCUPADO
            and paso_tres
            == ["TareaEscaneo", "TareaFFprobe", "TareaGuardarVideos"]
            and paso_tres_b == paso_tres
            and estado_tres == Estado.OCUPADO
            and len(tareas_vistas) == 3
            and len(set(tareas_vistas)) == 3
            and control_ffprobe.principal is False
            and control_guardado.principal is False
            and ventana.gestor.hilo is None
            and len(_GESTORES_ACTIVOS) == 0
        )
        return (
            ok,
            f"secuencia={secuencia} "
            f"estados={estado_uno},{estado_dos},{estado_tres} "
            f"ffprobe_principal={control_ffprobe.principal} "
            f"guardado_principal={control_guardado.principal} "
            f"gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_27():
    temp, ruta_db = _crear_bd([])
    carpeta_a = _carpeta_con(["a1.mp4", "a2.avi"])
    carpeta_b = _carpeta_con(["b1.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta_a.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        primero = ventana.videos_detectados
        estado_uno = ventana.estado_escaneo.text()
        with _dialogo_falso(carpeta_b.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        segundo = ventana.videos_detectados
        estado_dos = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            primero == ["a1.mp4", "a2.avi"]
            and estado_uno == "2 videos detectados"
            and segundo == ["b1.mkv"]
            and estado_dos == "1 video detectado"
        )
        return (
            ok,
            f"primero={primero} segundo={segundo} "
            f"estados={estado_uno!r},{estado_dos!r}",
        )
    finally:
        carpeta_b.cleanup()
        carpeta_a.cleanup()
        temp.cleanup()


def test_28():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _escaneo_controlado(["x.mp4"]) as control_escaneo:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            control_escaneo.empezada.wait(5)
            control_escaneo.soltar.set()
            ventana.close()
            ventana.gestor.cerrar()
        _procesar(50)
        _limpiar(ventana)
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        hilos = [t for t in threading.enumerate() if t is not threading.main_thread()]
        ok = (
            len(avisos) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and len(hilos) == 0
        )
        return (
            ok,
            f"avisos={len(avisos)} hilos={len(hilos)} "
            f"gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_29():
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
            _esperar(lambda v=ventana: _escanear_terminado(v))
        detectados = ventana.videos_detectados
        ventana.close()
        _limpiar(ventana)
        nuevos = QT_MENSAJES[antes:]
        avisos = [m for m in nuevos if "Destroyed while thread" in m]
        ok = detectados == ["a.mp4", "b.mkv"] and len(avisos) == 0
        return ok, f"detectados={detectados} avisos_nuevos={len(avisos)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_30():
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


def test_31():
    ruta = os.path.join(ruta_raiz(), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)
    importadas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                importadas.add(nodo.module)
            for alias in nodo.names:
                if alias.name != "*":
                    importadas.add(alias.name)
    ok = (
        "TareaEscaneo" in importadas
        and "TareaFFprobe" in importadas
        and "combinar_registros_con_ffprobe" in importadas
        and "obtener_datos_ffprobe" not in importadas
        and "listar_videos" not in importadas
        and "listar_videos_paginado" not in importadas
        and "escanear_videos" not in importadas
    )
    return ok, f"importaciones={sorted(importadas)}"


def test_32():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        llamadas = {"mod": 0}
        orig_mod = escanear_mod.escanear_videos

        def _mod(*a, **k):
            llamadas["mod"] += 1
            raise AssertionError("no debe llamarse escanear_videos directamente")

        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        escanear_mod.escanear_videos = _mod
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _escanear_terminado(v))
        finally:
            escanear_mod.escanear_videos = orig_mod
        detectados = ventana.videos_detectados
        tipo = type(ventana.tarea_escaneo).__name__
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"mod": 0} and detectados == ["x.mp4"] and tipo == "TareaEscaneo"
        return ok, f"llamadas={llamadas} tipo={tipo} detectados={detectados}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_33():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi", "uvas.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cargados = sorted(nombre for nombre, _ in ventana.tarjetas)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.busqueda.setText("man")
        visibles = ventana.tarjetas_visibles()
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            cargados == sorted(nombres)
            and visibles == ["mango.mkv", "manzana.mp4"]
            and contador == "2 videos"
            and ventana.videos_detectados == ["x.mp4"]
        )
        return ok, f"cargados={cargados} visibles={visibles} contador={contador}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_34():
    comando = [sys.executable, "visor_videos.py"]
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
        and "carpeta_inicio=None" in salida
        and "escanear_boton_inicio=False" in salida
        and "escanear_boton_habilitado=True" in salida
        and "estado_escaneo_mientras=Escaneando carpeta" in salida
        and "estado_escaneo_final=3 videos detectados" in salida
        and "videos_detectados=['clip.avi'" in salida
        and "escanear_boton_final=True" in salida
        and "guardado_total=3" in salida
        and "visibles_cargados=" in salida
        and "contador_cargado=" in salida
        and "visibles_filtro=" in salida
        and "contador_final=" in salida
        and "Destroyed while thread" not in salida
        and "No se pudo cargar el catálogo" not in salida
    )
    return (
        ok,
        f"exit={resultado.returncode} "
        f"escaneo_ok={'estado_escaneo_final=3 videos detectados' in salida} "
        f"guardado_ok={'guardado_total=3' in salida} "
        f"avisos={('Destroyed while thread' in salida)}",
    )


def test_35():
    avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
    ok = len(avisos) == 0
    return ok, f"avisos_totales={len(avisos)}"


def test_36():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _escanear_terminado(v))
        ventana.close()
        _limpiar(ventana)
        ok = (
            ventana.gestor.hilo is None
            and ventana.gestor.tarea is None
            and ventana.gestor.estado in (Estado.INACTIVO, Estado.CERRADO)
            and len(_GESTORES_ACTIVOS) == 0
        )
        return (
            ok,
            f"estado={ventana.gestor.estado} gestores={len(_GESTORES_ACTIVOS)}",
        )
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
        test_21,
        test_22,
        test_23,
        test_24,
        test_25,
        test_26,
        test_27,
        test_28,
        test_29,
        test_30,
        test_31,
        test_32,
        test_33,
        test_34,
        test_35,
        test_36,
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
    print(f"TOTAL={aprobadas}/36")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
