import contextlib
import hashlib
import os
import py_compile
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEventLoop, QTimer, qInstallMessageHandler
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
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import (
    MENSAJE_RUTA_INVALIDA,
    MENSAJE_SIN_CARPETA,
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


def _filas_resultado(nombres):
    return [(nombre, None, None, None, None, 0, None) for nombre in nombres]


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


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_seleccion_carpeta.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd([])
    try:
        llamadas = {"dialogo": 0}

        def _dialogo(*a, **k):
            llamadas["dialogo"] += 1
            raise AssertionError("el diálogo no debe abrirse en la construcción")

        original = visor_videos.QFileDialog.getExistingDirectory
        ventana = None
        visor_videos.QFileDialog.getExistingDirectory = _dialogo
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
        finally:
            visor_videos.QFileDialog.getExistingDirectory = original
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ok = (
            ventana.carpeta_seleccionada is None
            and ventana.etiqueta_carpeta.text() == MENSAJE_SIN_CARPETA
            and llamadas["dialogo"] == 0
        )
        ventana.close()
        _limpiar(ventana)
        return (
            ok,
            f"dialogo={llamadas['dialogo']} carpeta={ventana.carpeta_seleccionada} "
            f"etiqueta={ventana.etiqueta_carpeta.text()!r}",
        )
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        es_boton = isinstance(ventana.boton_seleccionar_carpeta, QPushButton)
        texto = ventana.boton_seleccionar_carpeta.text()
        with _dialogo_falso(carpeta.name):
            ventana.boton_seleccionar_carpeta.click()
        seleccionada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = (
            es_boton
            and texto == "Seleccionar carpeta"
            and seleccionada == os.path.abspath(carpeta.name)
        )
        return ok, f"boton={es_boton} texto={texto!r} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        esperada = os.path.abspath(carpeta.name)
        ventana.close()
        _limpiar(ventana)
        ok = guardada == esperada and os.path.isabs(guardada) and os.path.isdir(guardada)
        return ok, f"guardada={guardada} esperada={esperada}"
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
        mostrada = ventana.etiqueta_carpeta.text()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = mostrada == guardada == os.path.abspath(carpeta.name)
        return ok, f"mostrada={mostrada!r} guardada={guardada!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd([])
    carpeta_a = tempfile.TemporaryDirectory()
    carpeta_b = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta_a.name):
            ventana.seleccionar_carpeta()
        primera = ventana.carpeta_seleccionada
        ventana.busqueda.setText("prueba")
        conservada = ventana.carpeta_seleccionada == primera
        with _dialogo_falso(carpeta_b.name):
            ventana.seleccionar_carpeta()
        segunda = ventana.carpeta_seleccionada
        with _dialogo_falso(""):
            ventana.seleccionar_carpeta()
        tras_cancelar = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = (
            conservada
            and primera == os.path.abspath(carpeta_a.name)
            and segunda == os.path.abspath(carpeta_b.name)
            and tras_cancelar == segunda
        )
        return ok, f"a={primera} b={segunda} tras_cancelar={tras_cancelar}"
    finally:
        carpeta_b.cleanup()
        carpeta_a.cleanup()
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd([])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(""):
            ventana.seleccionar_carpeta()
        inicial = ventana.carpeta_seleccionada
        etiqueta = ventana.etiqueta_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = inicial is None and etiqueta == MENSAJE_SIN_CARPETA
        return ok, f"inicial={inicial} etiqueta={etiqueta!r}"
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        anterior = ventana.carpeta_seleccionada
        with _dialogo_falso(""):
            ventana.seleccionar_carpeta()
        conservada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = anterior == os.path.abspath(carpeta.name) and conservada == anterior
        return ok, f"anterior={anterior} conservada={conservada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    try:
        inexistente = os.path.join(temp.name, "no_existe", "subcarpeta")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(inexistente):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        mensaje = ventana.mensaje_carpeta.text()
        etiqueta = ventana.etiqueta_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            guardada is None
            and mensaje == MENSAJE_RUTA_INVALIDA
            and etiqueta == MENSAJE_SIN_CARPETA
        )
        return ok, f"guardada={guardada} mensaje={mensaje!r}"
    finally:
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd([])
    try:
        ruta_archivo = os.path.join(temp.name, "archivo.txt")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write("contenido")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(ruta_archivo):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        mensaje = ventana.mensaje_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = guardada is None and mensaje == MENSAJE_RUTA_INVALIDA
        return ok, f"guardada={guardada} mensaje={mensaje!r}"
    finally:
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    subcarpeta = os.path.join(temp.name, "relativa")
    os.makedirs(subcarpeta)
    try:
        relativa = os.path.relpath(subcarpeta, os.getcwd())
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(relativa):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        esperada = os.path.abspath(relativa)
        ventana.close()
        _limpiar(ventana)
        ok = guardada == esperada and os.path.isabs(guardada) and os.path.isdir(guardada)
        return ok, f"relativa={relativa!r} guardada={guardada} esperada={esperada}"
    finally:
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd([])
    carpeta = os.path.join(temp.name, "mi carpeta con espacios")
    os.makedirs(carpeta)
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = guardada == os.path.abspath(carpeta) and os.path.isdir(guardada)
        return ok, f"guardada={guardada}"
    finally:
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd([])
    carpeta = os.path.join(temp.name, "vídeos-áéíóú ñ")
    os.makedirs(carpeta)
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        mostrada = ventana.etiqueta_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            guardada == os.path.abspath(carpeta)
            and mostrada == guardada
            and os.path.isdir(guardada)
        )
        return ok, f"guardada={guardada} mostrada={mostrada!r}"
    finally:
        temp.cleanup()


def test_14():
    temp, ruta_db = _crear_bd([])
    try:
        inexistente = os.path.join(temp.name, "no_existe")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.show()
        _procesar(50)
        visible_antes = ventana.isVisible()
        with _dialogo_falso(inexistente):
            ventana.seleccionar_carpeta()
        visible_despues = ventana.isVisible()
        mensaje = ventana.mensaje_carpeta.text()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        ok = (
            visible_antes
            and visible_despues
            and mensaje == MENSAJE_RUTA_INVALIDA
            and guardada is None
        )
        return (
            ok,
            f"visible_antes={visible_antes} visible_despues={visible_despues} "
            f"mensaje={mensaje!r} guardada={guardada}",
        )
    finally:
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mp4"]))
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = None
        with _lectura_controlada(_resultado(["a.mp4", "b.mp4"])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            seleccionada = ventana.carpeta_seleccionada
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cargados = sorted(nombre for nombre, _ in ventana.tarjetas)
        ventana.close()
        _limpiar(ventana)
        ok = (
            seleccionada == os.path.abspath(carpeta.name)
            and cargados == ["a.mp4", "b.mp4"]
            and ventana._carga_completada
        )
        return ok, f"cargados={cargados} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_16():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi", "uvas.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.busqueda.setText("man")
        visibles = ventana.tarjetas_visibles()
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = visibles == ["mango.mkv", "manzana.mp4"] and contador == "2 videos"
        return ok, f"visibles={visibles} contador={contador}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        llamadas = {"escaneo": 0}
        orig_tv = tv.escanear_videos
        orig_mod = escanear_mod.escanear_videos

        def _escaneo(*a, **k):
            llamadas["escaneo"] += 1
            raise AssertionError("no debe escanearse")

        ventana = None
        tv.escanear_videos = _escaneo
        escanear_mod.escanear_videos = _escaneo
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            seleccionada = ventana.carpeta_seleccionada
        finally:
            tv.escanear_videos = orig_tv
            escanear_mod.escanear_videos = orig_mod
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"escaneo": 0} and seleccionada == os.path.abspath(carpeta.name)
        return ok, f"llamadas={llamadas} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        llamadas = []
        original = os.listdir

        def _listar(ruta):
            llamadas.append(ruta)
            return original(ruta)

        ventana = None
        with _lectura_controlada(_resultado([])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)
            os.listdir = _listar
            try:
                with _dialogo_falso(carpeta.name):
                    ventana.seleccionar_carpeta()
                seleccionada = ventana.carpeta_seleccionada
            finally:
                os.listdir = original
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        sobre_carpeta = [
            r for r in llamadas if r == os.path.abspath(carpeta.name)
        ]
        ok = (
            seleccionada == os.path.abspath(carpeta.name)
            and len(sobre_carpeta) == 0
        )
        return ok, f"seleccionada={seleccionada} llamadas={len(llamadas)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        llamadas = {"ffprobe": 0}
        orig_tv = tv.obtener_datos_ffprobe
        orig_mod = escanear_mod.obtener_datos_ffprobe

        def _ffprobe(*a, **k):
            llamadas["ffprobe"] += 1
            raise AssertionError("no debe invocarse ffprobe")

        ventana = None
        tv.obtener_datos_ffprobe = _ffprobe
        escanear_mod.obtener_datos_ffprobe = _ffprobe
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            seleccionada = ventana.carpeta_seleccionada
        finally:
            tv.obtener_datos_ffprobe = orig_tv
            escanear_mod.obtener_datos_ffprobe = orig_mod
        ventana.close()
        _limpiar(ventana)
        ok = (
            llamadas == {"ffprobe": 0}
            and seleccionada == os.path.abspath(carpeta.name)
        )
        return ok, f"llamadas={llamadas} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_20():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        llamadas = {"subprocess": 0}
        orig = escanear_mod.subprocess.run

        def _run(*a, **k):
            llamadas["subprocess"] += 1
            raise AssertionError("no debe ejecutarse subproceso")

        ventana = None
        escanear_mod.subprocess.run = _run
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            seleccionada = ventana.carpeta_seleccionada
        finally:
            escanear_mod.subprocess.run = orig
        ventana.close()
        _limpiar(ventana)
        ok = (
            llamadas == {"subprocess": 0}
            and seleccionada == os.path.abspath(carpeta.name)
        )
        return ok, f"llamadas={llamadas} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_21():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        llamadas = {"connect": 0}
        original = sqlite3.connect

        def _conectar(*args, **kwargs):
            llamadas["connect"] += 1
            return original(*args, **kwargs)

        sqlite3.connect = _conectar
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            seleccionada = ventana.carpeta_seleccionada
        finally:
            sqlite3.connect = original
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"connect": 0} and seleccionada == os.path.abspath(carpeta.name)
        return ok, f"llamadas={llamadas} seleccionada={seleccionada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_22():
    filas = [
        ("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0),
        ("b.avi", "r", ".avi", "f", 2.0, 2, 2, "c", 1),
    ]
    temp, ruta_db = _crear_bd(filas)
    carpeta = tempfile.TemporaryDirectory()
    try:
        def _snap():
            with open(ruta_db, "rb") as f:
                datos = f.read()
            return hashlib.sha256(datos).hexdigest(), datos

        h1, b1 = _snap()
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.close()
        _limpiar(ventana)
        h2, b2 = _snap()
        conn = sqlite3.connect(ruta_db)
        try:
            filas_ahora = conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
        finally:
            conn.close()
        ok = h1 == h2 and b1 == b2 and len(filas_ahora) == 2
        return ok, f"bytes_iguales={b1 == b2} filas={len(filas_ahora)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_23():
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
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.close()
        _limpiar(ventana)
    finally:
        carpeta.cleanup()
        temp.cleanup()
    despues = estado_real()
    ok = antes == despues
    return ok, f"reales_intactos={antes == despues}"


def test_24():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
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


def test_25():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        antes = len(QT_MENSAJES)
        for _ in range(3):
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.close()
            _limpiar(ventana)
        nuevos = QT_MENSAJES[antes:]
        avisos = [m for m in nuevos if "Destroyed while thread" in m]
        ok = len(avisos) == 0
        return ok, f"avisos_nuevos={len(avisos)}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_26():
    comando = [sys.executable, "visor_videos.py"]
    resultado = subprocess.run(
        comando,
        cwd=ruta_raiz(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    lineas = {}
    for linea in salida.splitlines():
        if "=" in linea and not linea.startswith("T"):
            clave, _, valor = linea.partition("=")
            lineas[clave] = valor
    carpeta_inicio = lineas.get("carpeta_inicio")
    carpeta_seleccion = lineas.get("carpeta_seleccion")
    carpeta_tras_cancelar = lineas.get("carpeta_tras_cancelar")
    etiqueta_tras_cancelar = lineas.get("etiqueta_tras_cancelar")
    ok = (
        resultado.returncode == 0
        and carpeta_inicio == "None"
        and carpeta_seleccion == carpeta_tras_cancelar
        and carpeta_seleccion not in (None, "None")
        and etiqueta_tras_cancelar == carpeta_tras_cancelar
        and "visibles_cargados=" in salida
        and "contador_cargado=" in salida
        and "visibles_filtro=" in salida
        and "contador_final=" in salida
        and "Destroyed while thread" not in salida
        and "No se pudo cargar el catálogo" not in salida
    )
    return (
        ok,
        f"exit={resultado.returncode} inicio={carpeta_inicio} "
        f"seleccion={carpeta_seleccion} cancelar={carpeta_tras_cancelar} "
        f"avisos={('Destroyed while thread' in salida)}",
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
        test_21,
        test_22,
        test_23,
        test_24,
        test_25,
        test_26,
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
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
