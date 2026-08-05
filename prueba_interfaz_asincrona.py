import ast
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
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from rutas import ruta_raiz, ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, _GESTORES_ACTIVOS
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import (
    MENSAJE_CARGANDO,
    MENSAJE_ERROR,
    TAMANIO_PAGINA_INICIAL,
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


def _lectura_lenta(segundos, resultado):
    inicio = threading.Event()

    def _lenta(*args, **kwargs):
        inicio.set()
        time.sleep(segundos)
        return resultado

    return _lenta, inicio


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_interfaz_asincrona.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        llamadas = {"connect": 0}
        original = sqlite3.connect

        def _conectar(*args, **kwargs):
            llamadas["connect"] += 1
            return original(*args, **kwargs)

        ventana = None
        with _lectura_controlada(_resultado(["a.mp4"])) as control:
            sqlite3.connect = _conectar
            try:
                ventana = VisorVideos(ruta_db=ruta_db)
                construccion = llamadas["connect"]
            finally:
                sqlite3.connect = original
            control.empezada.wait(5)
            sin_resultado = ventana.tarjetas == [] and not ventana._carga_completada
            control.soltar.set()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        ok = construccion == 0 and sin_resultado
        return ok, f"connect_durante_construccion={construccion} sin_resultado={sin_resultado}"
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = None
        with _lectura_controlada(_resultado(["a.mp4"])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)
            ok = (
                isinstance(ventana.tarea_lectura, TareaLecturaCatalogoPaginada)
                and ventana.tarea_lectura.limite == TAMANIO_PAGINA_INICIAL
                and ventana.tarea_lectura.desplazamiento == 0
                and ventana.tarea_lectura.texto is None
                and ventana.gestor.tarea is ventana.tarea_lectura
            )
            control.soltar.set()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        return ok, f"tipo={type(ventana.tarea_lectura).__name__}"
    finally:
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        id_main = threading.get_ident()
        conecta = {"ident": None}
        wrapped = {"ident": None}
        original_connect = sqlite3.connect
        original_lectura = tv.listar_videos_paginado

        def _conectar(*args, **kwargs):
            conecta["ident"] = threading.get_ident()
            return original_connect(*args, **kwargs)

        def _wrapped(*args, **kwargs):
            wrapped["ident"] = threading.get_ident()
            return original_lectura(*args, **kwargs)

        ventana = None
        sqlite3.connect = _conectar
        tv.listar_videos_paginado = _wrapped
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        finally:
            sqlite3.connect = original_connect
            tv.listar_videos_paginado = original_lectura
        ventana.close()
        _limpiar(ventana)
        ok = (
            conecta["ident"] is not None
            and wrapped["ident"] is not None
            and conecta["ident"] == wrapped["ident"]
            and conecta["ident"] != id_main
            and wrapped["ident"] != id_main
        )
        return (
            ok,
            f"main={id_main} lectura={wrapped['ident']} connect={conecta['ident']}",
        )
    finally:
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = None
        with _lectura_controlada(_resultado(["a.mp4"])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)
            ok = (
                ventana.tarjetas == []
                and ventana.tarjetas_visibles() == []
                and ventana.contador.text() == "0 videos"
                and ventana.estado_carga.text() == MENSAJE_CARGANDO
            )
            control.soltar.set()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        return ok, f"tarjetas={len(ventana.tarjetas)} estado={ventana.estado_carga.text()}"
    finally:
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        marcado = {"valor": False, "mientras": False}
        ventana = None
        with _lectura_controlada(_resultado(["a.mp4"])) as control:
            ventana = VisorVideos(ruta_db=ruta_db)
            control.empezada.wait(5)

            def _marcar():
                marcado["valor"] = True
                marcado["mientras"] = ventana.gestor.estado == Estado.OCUPADO

            QTimer.singleShot(200, _marcar)
            _procesar(400)
            ok = (
                marcado["valor"]
                and marcado["mientras"]
                and not control.soltar.is_set()
                and ventana.tarjetas == []
            )
            control.soltar.set()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        return (
            ok,
            f"timer_disp={marcado['valor']} mientras_ocupado={marcado['mientras']}",
        )
    finally:
        temp.cleanup()


def test_07():
    nombres = ["zeta.mp4", "alfa.mp4", "beta.mp4", "kilo.mp4", "milo.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cargados = [nombre for nombre, _ in ventana.tarjetas]
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            cargados == sorted(nombres)
            and len(ventana.tarjetas) == 5
            and contador == "5 videos"
        )
        return ok, f"cargados={cargados} contador={contador}"
    finally:
        temp.cleanup()


def test_08():
    nombres = [f"v{i:03d}.mp4" for i in range(1, 201)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        original = visor_videos.TAMANIO_PAGINA_INICIAL
        visor_videos.TAMANIO_PAGINA_INICIAL = 50
        ventana = None
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        finally:
            visor_videos.TAMANIO_PAGINA_INICIAL = original
        cantidad = len(ventana.tarjetas)
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = cantidad == 50 and cantidad <= 50 and contador == "50 videos"
        return ok, f"tarjetas={cantidad} contador={contador}"
    finally:
        temp.cleanup()


def test_09():
    nombres = ["gamma.mp4", "alfa.mp4", "beta.mkv", "delta.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cargados = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = cargados == sorted(nombres)
        return ok, f"orden={cargados}"
    finally:
        temp.cleanup()


def test_10():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 4)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        texto = ventana.contador.text()
        visibles = ventana.tarjetas_visibles()
        ventana.close()
        _limpiar(ventana)
        ok = texto == "3 videos" and len(visibles) == 3
        return ok, f"contador={texto}"
    finally:
        temp.cleanup()


def test_11():
    nombres = [f"v{i:03d}.mp4" for i in range(1, 151)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        original = visor_videos.TAMANIO_PAGINA_INICIAL
        visor_videos.TAMANIO_PAGINA_INICIAL = 50
        ventana = None
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        finally:
            visor_videos.TAMANIO_PAGINA_INICIAL = original
        cantidad = len(ventana.tarjetas)
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = cantidad == 50 and cantidad < 150 and contador == "50 videos"
        return (
            ok,
            f"tarjetas={cantidad} filas_bd=150 total_no_crea_extra={cantidad == 50}",
        )
    finally:
        temp.cleanup()


def test_12():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi", "uvas.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.busqueda.setText("man")
        visibles = ventana.tarjetas_visibles()
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = visibles == ["mango.mkv", "manzana.mp4"] and contador == "2 videos"
        return ok, f"visibles={visibles} contador={contador}"
    finally:
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd([])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        contador = ventana.contador.text()
        estado = ventana.estado_carga.text()
        ok = (
            ventana.tarjetas == []
            and ventana.tarjetas_visibles() == []
            and contador == "0 videos"
            and estado == MENSAJE_CARGANDO
        )
        ventana.close()
        _limpiar(ventana)
        return ok, f"contador={contador}"
    finally:
        temp.cleanup()


def test_14():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        estado = ventana.estado_carga.text()
        creado = os.path.exists(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = estado == MENSAJE_ERROR and ventana.tarjetas == [] and not creado
        return ok, f"estado={estado!r} archivo_creado={creado}"
    finally:
        temp.cleanup()


def test_15():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "corrupta.db")
        with open(ruta_db, "wb") as f:
            f.write(b"esto no es una base sqlite valida" * 50)
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        estado = ventana.estado_carga.text()
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
            estado == MENSAJE_ERROR
            and ventana.tarjetas == []
            and usable
            and ventana._carga_completada
        )
        return ok, f"estado={estado!r} usable={usable}"
    finally:
        temp.cleanup()


def test_16():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        ventana = VisorVideos(ruta_db=ruta_db)
        conteo = {"fin": 0}

        def _contar():
            conteo["fin"] += 1

        ventana.gestor.tarea_finalizada.connect(_contar)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        estado = ventana.estado_carga.text()
        ventana.close()
        _limpiar(ventana)
        ok = conteo["fin"] == 1 and estado == MENSAJE_ERROR
        return ok, f"finalizadas={conteo['fin']}"
    finally:
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
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
        temp.cleanup()


def test_18():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
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
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        lenta, inicio = _lectura_lenta(1.5, _resultado(["a.mp4"]))
        original = tv.listar_videos_paginado
        tv.listar_videos_paginado = lenta
        ventana = None
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            inicio.wait(5)
            antes = ventana.gestor.hilo is not None and ventana.tarjetas == []
            ventana.close()
        finally:
            tv.listar_videos_paginado = original
        despues_hilo = ventana.gestor.hilo
        despues_estado = ventana.gestor.estado
        _limpiar(ventana)
        ok = (
            antes
            and despues_hilo is None
            and despues_estado in (Estado.INACTIVO, Estado.CERRADO)
            and len(_GESTORES_ACTIVOS) == 0
        )
        return (
            ok,
            f"antes_activo={antes} estado={despues_estado} gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        temp.cleanup()


def test_20():
    temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mp4"]))
    try:
        antes = len(QT_MENSAJES)
        for _ in range(3):
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ventana.close()
            _limpiar(ventana)
        ruta_err = os.path.join(temp.name, "no_existe.db")
        ventana = VisorVideos(ruta_db=ruta_err)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
        nuevos = QT_MENSAJES[antes:]
        avisos = [m for m in nuevos if "Destroyed while thread" in m]
        ok = len(avisos) == 0
        return ok, f"avisos_nuevos={len(avisos)}"
    finally:
        temp.cleanup()


def test_21():
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


def test_22():
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
    no_importa = (
        "listar_videos" not in importadas
        and "listar_videos_paginado" not in importadas
    )
    no_atributo = (
        not hasattr(visor_videos, "listar_videos")
        and not hasattr(visor_videos, "listar_videos_paginado")
    )
    llamadas = {"lista": 0, "paginado": 0}
    lista_orig = escanear_mod.listar_videos
    paginado_orig = escanear_mod.listar_videos_paginado

    def _lista(*a, **k):
        llamadas["lista"] += 1
        raise AssertionError("no debe llamarse listar_videos directamente")

    def _paginado(*a, **k):
        llamadas["paginado"] += 1
        raise AssertionError("no debe llamarse listar_videos_paginado directamente")

    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    ventana = None
    escanear_mod.listar_videos = _lista
    escanear_mod.listar_videos_paginado = _paginado
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    finally:
        escanear_mod.listar_videos = lista_orig
        escanear_mod.listar_videos_paginado = paginado_orig
    cargados = len(ventana.tarjetas)
    ventana.close()
    _limpiar(ventana)
    ok = no_importa and no_atributo and llamadas == {"lista": 0, "paginado": 0} and cargados == 1
    return (
        ok,
        f"importa={no_importa} atributo={no_atributo} llamadas={llamadas} cargados={cargados}",
    )


def test_23():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
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
        finally:
            tv.escanear_videos = orig_tv
            escanear_mod.escanear_videos = orig_mod
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"escaneo": 0}
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_24():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        llamadas = {"ffprobe": 0}
        orig = tv.obtener_datos_ffprobe

        def _ffprobe(*a, **k):
            llamadas["ffprobe"] += 1
            raise AssertionError("no debe invocarse ffprobe")

        ventana = None
        tv.obtener_datos_ffprobe = _ffprobe
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        finally:
            tv.obtener_datos_ffprobe = orig
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"ffprobe": 0}
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_25():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
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
        finally:
            escanear_mod.subprocess.run = orig
        ventana.close()
        _limpiar(ventana)
        ok = llamadas == {"subprocess": 0}
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_26():
    filas = [
        ("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0),
        ("b.avi", "r", ".avi", "f", 2.0, 2, 2, "c", 1),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        def _snap():
            with open(ruta_db, "rb") as f:
                datos = f.read()
            return hashlib.sha256(datos).hexdigest(), datos

        h1, b1 = _snap()
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
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
        temp.cleanup()


def test_27():
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
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.close()
        _limpiar(ventana)
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = antes == despues
    return ok, f"reales_intactos={antes == despues}"


def test_28():
    comando = [sys.executable, "prueba_smoke.py"]
    resultado = subprocess.run(
        comando,
        cwd=ruta_raiz(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    ok = (
        resultado.returncode == 0
        and "visibles_cargados=" in salida
        and "contador_cargado=" in salida
        and "visibles_filtro=" in salida
        and "contador_final=" in salida
        and "Destroyed while thread" not in salida
        and "No se pudo cargar el catálogo" not in salida
    )
    return (
        ok,
        f"exit={resultado.returncode} marcadores_ok={'visibles_cargados=' in salida} "
        f"avisos={('Destroyed while thread' in salida)}",
    )


def test_29():
    avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
    ok = len(avisos) == 0
    return ok, f"avisos_totales={len(avisos)}"


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
