import ast
import contextlib
import os
import py_compile
import shutil
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

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
from tareas_videos import TareaSincronizacionCatalogo
from visor_videos import (
    MENSAJE_ERROR_GUARDADO,
    MENSAJE_ERROR_SINCRONIZACION,
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


def _cadena_terminada(ventana):
    return (
        ventana.gestor.hilo is None
        and not ventana._escaneo_pendiente
        and not ventana._ffprobe_pendiente
        and not ventana._miniaturas_pendiente
        and not ventana._guardado_pendiente
        and not ventana._sincronizacion_pendiente
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
        "prueba_sincronizacion_interfaz.py",
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
        ventana.gestor.tarea_iniciada.connect(
            lambda: tipos.append(type(ventana.gestor.tarea).__name__)
        )
        control = _Control(escanear_mod.detectar_diferencias)
        escanear_mod.detectar_diferencias = control
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda: control.empezada.is_set())
            mismo_gestor = (
                ventana.gestor.tarea is ventana.tarea_sincronizacion
                and isinstance(
                    ventana.tarea_sincronizacion, TareaSincronizacionCatalogo
                )
            )
            gestor_activo = ventana.gestor.activo
            principal = control.principal
            control.soltar.set()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.detectar_diferencias = control.fn
        ventana.close()
        _limpiar(ventana)
        ok = (
            tipos
            == [
                "TareaEscaneo",
                "TareaFFprobe",
                "TareaMiniaturas",
                "TareaGuardarVideos",
                "TareaSincronizacionCatalogo",
            ]
            and mismo_gestor
            and gestor_activo
            and principal is False
        )
        return (
            ok,
            f"tipos={tipos} mismo_gestor={mismo_gestor} "
            f"activo={gestor_activo} principal={principal}",
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
        llamadas = {"sync": 0}
        orig_guardado = tv.guardar_videos
        orig_diff = escanear_mod.detectar_diferencias

        def _falla_guardado(datos_videos, ruta_db=None):
            raise RuntimeError("fallo controlado del guardado")

        def _no_sync(*a, **k):
            llamadas["sync"] += 1
            raise AssertionError("no debe sincronizarse tras error de guardado")

        tv.guardar_videos = _falla_guardado
        escanear_mod.detectar_diferencias = _no_sync
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig_guardado
            escanear_mod.detectar_diferencias = orig_diff
        estado = ventana.estado_escaneo.text()
        resultado = ventana.resultado_sincronizacion
        pendiente = ventana._sincronizacion_pendiente
        tarea = ventana.tarea_sincronizacion
        gestor = ventana.gestor.estado
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado == MENSAJE_ERROR_GUARDADO
            and llamadas == {"sync": 0}
            and resultado is None
            and not pendiente
            and tarea is None
            and gestor == Estado.INACTIVO
        )
        return (
            ok,
            f"estado={estado!r} sync_llamadas={llamadas} "
            f"pendiente={pendiente} gestor={gestor}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_04():
    origen = os.path.join(ruta_carpeta_videos(), "video_real.mp4")
    temp, ruta_db = _crear_bd([])
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        if not os.path.isfile(origen):
            return False, "no existe video_real.mp4 en videos_prueba"
        shutil.copyfile(origen, os.path.join(carpeta_temp.name, "video_real.mp4"))
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)

        def _metadatos():
            conn = sqlite3.connect(ruta_db)
            try:
                return conn.execute(
                    "SELECT nombre, duracion_segundos, ancho, alto, codec_video, "
                    "cantidad_miniaturas FROM videos ORDER BY nombre"
                ).fetchall()
            finally:
                conn.close()

        control = _Control(escanear_mod.detectar_diferencias)
        escanear_mod.detectar_diferencias = control
        try:
            with _miniaturas_temporales():
                with _dialogo_falso(carpeta_temp.name):
                    ventana.seleccionar_carpeta()
                ventana.boton_escanear.click()
                _esperar(lambda: control.empezada.is_set())
                antes = _metadatos()
                control.soltar.set()
                _esperar(lambda v=ventana: _cadena_terminada(v))
                despues = _metadatos()
        finally:
            escanear_mod.detectar_diferencias = control.fn
        ventana.close()
        _limpiar(ventana)
        esperados = ("video_real.mp4", 5.0, 640, 360, "h264", 1)
        ok = (
            antes == [esperados]
            and despues == antes
            and ventana.resultado_sincronizacion is not None
        )
        return ok, f"antes={antes} despues={despues}"
    finally:
        carpeta_temp.cleanup()
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd(_filas(["ausente.mp4", "presente.mp4"]))
    carpeta = _carpeta_con(["presente.mp4", "nuevo.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        resumen = ventana.resultado_sincronizacion["resumen"]
        ventana.close()
        _limpiar(ventana)
        ok = (
            [f[0] for f in filas] == ["nuevo.mkv", "presente.mp4"]
            and resumen["nuevos"] == 0
            and resumen["ya_sincronizados"] == 2
            and resumen["incorporados"] == 0
            and resumen["eliminados"] == 1
            and resumen["candidatos_restantes"] == 0
        )
        return ok, f"filas={[f[0] for f in filas]} resumen={resumen}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_06():
    origen = os.path.join(ruta_carpeta_videos(), "video_real.mp4")
    temp, ruta_db = _crear_bd(_filas(["ausente.mp4"]))
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        if not os.path.isfile(origen):
            return False, "no existe video_real.mp4 en videos_prueba"
        shutil.copyfile(origen, os.path.join(carpeta_temp.name, "video_real.mp4"))
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        control = _Control(escanear_mod.detectar_diferencias)
        escanear_mod.detectar_diferencias = control
        try:
            with _miniaturas_temporales() as carpeta_miniaturas:
                with _dialogo_falso(carpeta_temp.name):
                    ventana.seleccionar_carpeta()
                ventana.boton_escanear.click()
                _esperar(lambda: control.empezada.is_set())
                disco_antes = sorted(os.listdir(carpeta_temp.name))
                mini_antes = sorted(os.listdir(carpeta_miniaturas))
                control.soltar.set()
                _esperar(lambda v=ventana: _cadena_terminada(v))
                disco_despues = sorted(os.listdir(carpeta_temp.name))
                mini_despues = sorted(os.listdir(carpeta_miniaturas))
        finally:
            escanear_mod.detectar_diferencias = control.fn
        conn = sqlite3.connect(ruta_db)
        try:
            nombres = [f[0] for f in conn.execute("SELECT nombre FROM videos")]
        finally:
            conn.close()
        ventana.close()
        _limpiar(ventana)
        ok = (
            disco_antes == disco_despues
            and mini_antes == mini_despues
            and "ausente.mp4" not in nombres
            and "video_real.mp4" in nombres
        )
        return (
            ok,
            f"disco={disco_antes}=={disco_despues} "
            f"mini={mini_antes}=={mini_despues} nombres={nombres}",
        )
    finally:
        carpeta_temp.cleanup()
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd(_filas(["preexistente.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig = tv.guardar_videos

        def _falla(datos_videos, ruta_db=None):
            raise RuntimeError("fallo controlado del guardado")

        tv.guardar_videos = _falla
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig
        estado = ventana.estado_escaneo.text()
        filas = _filas_de(ruta_db)
        resultado = ventana.resultado_sincronizacion
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado == MENSAJE_ERROR_GUARDADO
            and [f[0] for f in filas] == ["preexistente.mp4"]
            and resultado is None
        )
        return ok, f"estado={estado!r} filas={[f[0] for f in filas]}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig = escanear_mod.detectar_diferencias

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado de sincronizacion")

        escanear_mod.detectar_diferencias = _falla
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.detectar_diferencias = orig
        estado_error = ventana.estado_escaneo.text()
        gestor_error = ventana.gestor.estado
        hab_error = ventana.boton_escanear.isEnabled()
        pendiente_error = ventana._sincronizacion_pendiente
        tarea_error = ventana.tarea_sincronizacion
        resultado_error = ventana.resultado_sincronizacion
        hilo_error = ventana.gestor.hilo
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        resultado_final = ventana.resultado_sincronizacion
        estado_final = ventana.estado_escaneo.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_error == MENSAJE_ERROR_SINCRONIZACION
            and gestor_error == Estado.INACTIVO
            and hab_error
            and not pendiente_error
            and tarea_error is None
            and resultado_error is None
            and hilo_error is None
            and [f[0] for f in filas] == ["x.mp4"]
            and resultado_final is not None
            and estado_final
            and "incorporados, 0 eliminados" in estado_final
        )
        return (
            ok,
            f"estado_error={estado_error!r} gestor={gestor_error} "
            f"hab={hab_error} pendiente={pendiente_error} "
            f"resultado_final={'si' if resultado_final else 'no'}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ok = (
            ventana.gestor.estado == Estado.INACTIVO
            and ventana.gestor.hilo is None
            and ventana.gestor.tarea is None
            and not ventana._sincronizacion_pendiente
            and ventana.tarea_sincronizacion is None
            and ventana.boton_escanear.isEnabled()
            and ventana.boton_seleccionar_carpeta.isEnabled()
            and len(_GESTORES_ACTIVOS) == 0
        )
        return (
            ok,
            f"estado={ventana.gestor.estado} hilo={ventana.gestor.hilo} "
            f"pendiente={ventana._sincronizacion_pendiente} "
            f"gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd(_filas(["ausente.mp4"]))
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        r = ventana.resultado_sincronizacion
        ventana.close()
        _limpiar(ventana)
        if r is None:
            return False, "resultado_sincronizacion no conservado"
        resumen = r["resumen"]
        ok = (
            set(r) == {"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}
            and set(resumen)
            == {"nuevos", "ya_sincronizados", "incorporados", "eliminados", "candidatos_restantes"}
            and resumen == {
                "nuevos": 0,
                "ya_sincronizados": 2,
                "incorporados": 0,
                "eliminados": 1,
                "candidatos_restantes": 0,
            }
            and r["eliminaciones"]["nombres"] == ["ausente.mp4"]
        )
        return ok, f"resumen={resumen}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
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


def test_12():
    ruta = os.path.join(ruta_raiz(), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "escanear_videos":
            for alias in nodo.names:
                nombres.add(alias.name)
    funciones = [
        "detectar_diferencias",
        "preparar_plan_sincronizacion",
        "aplicar_incorporaciones",
        "eliminar_candidatos",
    ]
    presentes = [fn for fn in funciones if fn in nombres]
    ok = not presentes
    return ok, f"funciones_en_interfaz={presentes}"


def test_13():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        llamadas = {"lectura": 0}
        orig = tv.listar_videos_paginado

        def _lectura(*a, **k):
            llamadas["lectura"] += 1
            raise AssertionError("la sincronizacion no debe recargar el catalogo")

        tv.listar_videos_paginado = _lectura
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig
        despues = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"lectura": 0} and despues == antes
        return ok, f"llamadas={llamadas} tarjetas={antes}->{despues}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_14():
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
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        nuevos = QT_MENSAJES[antes:]
        avisos = [m for m in nuevos if "Destroyed while thread" in m]
        ok = (
            [f[0] for f in filas] == ["a.mp4", "b.mkv"]
            and len(avisos) == 0
            and len(_GESTORES_ACTIVOS) == 0
        )
        return ok, f"filas={[f[0] for f in filas]} avisos={len(avisos)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        control = _Control(escanear_mod.detectar_diferencias)
        escanear_mod.detectar_diferencias = control
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda: control.empezada.is_set())
            activo_mientras = ventana.gestor.activo
            control.soltar.set()
            ventana.close()
            ventana.gestor.cerrar()
        finally:
            escanear_mod.detectar_diferencias = control.fn
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


def test_16():
    origen = os.path.join(ruta_carpeta_videos(), "video_real.mp4")
    temp, ruta_db = _crear_bd(_filas(["video_real.mp4", "ausente.mp4"]))
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        if not os.path.isfile(origen):
            return False, "no existe video_real.mp4 en videos_prueba"
        shutil.copyfile(origen, os.path.join(carpeta_temp.name, "video_real.mp4"))
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _miniaturas_temporales() as carpeta_miniaturas:
            with _dialogo_falso(carpeta_temp.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
            generadas = (
                sorted(os.listdir(carpeta_miniaturas))
                if os.path.isdir(carpeta_miniaturas)
                else []
            )
        guardado = ventana.registros_guardados
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute(
                "SELECT nombre, duracion_segundos, ancho, alto, codec_video, "
                "cantidad_miniaturas FROM videos ORDER BY nombre"
            ).fetchall()
        finally:
            conn.close()
        resumen = ventana.resultado_sincronizacion["resumen"]
        ventana.close()
        _limpiar(ventana)
        ok = (
            guardado == 1
            and [f[0] for f in filas] == ["video_real.mp4"]
            and filas[0][1:] == (5.0, 640, 360, "h264", 1)
            and generadas == ["video_real_01.jpg"]
            and resumen["nuevos"] == 0
            and resumen["ya_sincronizados"] == 1
            and resumen["incorporados"] == 0
            and resumen["eliminados"] == 1
            and resumen["candidatos_restantes"] == 0
        )
        return (
            ok,
            f"guardado={guardado} filas={filas} generadas={generadas} "
            f"resumen={resumen}",
        )
    finally:
        carpeta_temp.cleanup()
        temp.cleanup()


def test_17():
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


def test_18():
    temp, ruta_db = _crear_bd([])
    carpeta_a = _carpeta_con(["a.mp4"])
    carpeta_b = _carpeta_con(["b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta_a.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        hab_tras_primero = ventana.boton_escanear.isEnabled()
        primero = ventana.resultado_sincronizacion
        with _dialogo_falso(carpeta_b.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        detectados = ventana.videos_detectados
        filas = _filas_de(ruta_db)
        resumen = ventana.resultado_sincronizacion["resumen"]
        ventana.close()
        _limpiar(ventana)
        ok = (
            hab_tras_primero
            and primero is not None
            and detectados == ["b.mkv"]
            and [f[0] for f in filas] == ["b.mkv"]
            and resumen["nuevos"] == 0
            and resumen["ya_sincronizados"] == 1
            and resumen["incorporados"] == 0
            and resumen["eliminados"] == 1
        )
        return (
            ok,
            f"hab_tras_primero={hab_tras_primero} detectados={detectados} "
            f"filas={[f[0] for f in filas]} resumen={resumen}",
        )
    finally:
        carpeta_b.cleanup()
        carpeta_a.cleanup()
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
    print(f"TOTAL={aprobadas}/18")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
