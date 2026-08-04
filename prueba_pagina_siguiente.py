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
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos, ruta_raiz
from tareas import Estado, _GESTORES_ACTIVOS
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import (
    MENSAJE_ERROR_PAGINA,
    TAMANIO_PAGINA_INICIAL,
    Tarjeta,
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
        and not ventana._ffprobe_pendiente
        and not ventana._miniaturas_pendiente
        and not ventana._guardado_pendiente
        and not ventana._sincronizacion_pendiente
        and not ventana._recarga_catalogo_pendiente
        and not ventana._pagina_pendiente
    )


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
        self.args = None
        self.kwargs = None

    def __call__(self, *args, **kwargs):
        self.llamadas += 1
        self.args = args
        self.kwargs = kwargs
        self.ident = threading.get_ident()
        self.principal = QThread.isMainThread()
        self.empezada.set()
        self.soltar.wait(10)
        return self.fn(*args, **kwargs)


def _nombres(n, prefijo="v"):
    return [f"{prefijo}{i:03d}.mp4" for i in range(1, n + 1)]


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_pagina_siguiente.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd(_filas(_nombres(200)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cantidad = len(ventana.tarjetas)
        contador = ventana.contador.text()
        habilitado = ventana.boton_cargar_mas.isEnabled()
        total = ventana._total_catalogo
        ventana.close()
        _limpiar(ventana)
        ok = (
            cantidad == TAMANIO_PAGINA_INICIAL == 100
            and contador == "100 videos"
            and total == 200
            and habilitado
        )
        return (
            ok,
            f"tarjetas={cantidad} contador={contador!r} total={total} "
            f"habilitado={habilitado}",
        )
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd(_filas(_nombres(50)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cantidad = len(ventana.tarjetas)
        habilitado = ventana.boton_cargar_mas.isEnabled()
        ventana.close()
        _limpiar(ventana)
        ok = cantidad == 50 and not habilitado
        return ok, f"tarjetas={cantidad} habilitado={habilitado}"
    finally:
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd(_filas(_nombres(250)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig_listar = tv.listar_videos_paginado
        control = _Control(orig_listar)
        tv.listar_videos_paginado = control
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda: control.empezada.is_set())
            tarea = ventana.tarea_pagina
            es_paginada = isinstance(tarea, TareaLecturaCatalogoPaginada)
            misma_tarea = ventana.gestor.tarea is tarea
            pendiente = ventana._pagina_pendiente
            activo = ventana.gestor.activo
            limite = tarea.limite
            desplazamiento = tarea.desplazamiento
            principal = control.principal
            control.soltar.set()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig_listar
        ventana.close()
        _limpiar(ventana)
        ok = (
            es_paginada
            and misma_tarea
            and pendiente
            and activo
            and limite == TAMANIO_PAGINA_INICIAL
            and desplazamiento == TAMANIO_PAGINA_INICIAL
            and principal is False
        )
        return (
            ok,
            f"es_paginada={es_paginada} misma_tarea={misma_tarea} "
            f"pendiente={pendiente} activo={activo} limite={limite} "
            f"desplazamiento={desplazamiento} principal={principal}",
        )
    finally:
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues = [nombre for nombre, _ in ventana.tarjetas]
        contador = ventana.contador.text()
        total = ventana._total_catalogo
        ventana.close()
        _limpiar(ventana)
        ok = (
            len(antes) == 100
            and len(despues) == 150
            and despues[:100] == antes
            and len(set(despues)) == len(despues)
            and contador == "150 videos"
            and total == 150
        )
        return (
            ok,
            f"antes={len(antes)} despues={len(despues)} "
            f"conservadas={despues[:100] == antes} "
            f"duplicados={len(despues) - len(set(despues))} "
            f"contador={contador!r} total={total}",
        )
    finally:
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd(_filas(_nombres(350)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        conteos = []
        estados_boton = []
        while ventana.boton_cargar_mas.isEnabled() and len(conteos) < 5:
            estados_boton.append(ventana.boton_cargar_mas.isEnabled())
            ventana.boton_cargar_mas.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
            conteos.append(len(ventana.tarjetas))
        nombres = [n for n, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            conteos == [200, 300, 350]
            and len(nombres) == 350
            and estados_boton == [True, True, True]
            and not ventana.boton_cargar_mas.isEnabled()
            and len(set(nombres)) == len(nombres)
            and nombres == _nombres(350)
        )
        return (
            ok,
            f"conteos={conteos} boton={estados_boton} "
            f"final={len(nombres)} habilitado_final="
            f"{ventana.boton_cargar_mas.isEnabled()} "
            f"duplicados={len(nombres) - len(set(nombres))}",
        )
    finally:
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        nombres_primera = [n for n, _ in ventana.tarjetas]
        filas_primera = [
            fila for fila in _filas(_nombres(150)) if fila[0] in set(nombres_primera)
        ]
        orig_listar = tv.listar_videos_paginado

        def _pagina_duplicada(limite, desplazamiento=0, texto=None, ruta_db=None):
            return {
                "videos": filas_primera,
                "total": 100,
                "limite": limite,
                "desplazamiento": desplazamiento,
            }

        tv.listar_videos_paginado = _pagina_duplicada
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig_listar
        despues = [n for n, _ in ventana.tarjetas]
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            len(despues) == 100
            and despues == nombres_primera
            and len(set(despues)) == len(despues)
            and contador == "100 videos"
        )
        return (
            ok,
            f"despues={len(despues)} duplicados="
            f"{len(despues) - len(set(despues))} contador={contador!r}",
        )
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd(_filas(_nombres(250)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.busqueda.setText("v12")
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        visibles = ventana.tarjetas_visibles()
        contador = ventana.contador.text()
        tarjetas = [n for n, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        esperados = [f"v{i:03d}.mp4" for i in range(1, 251) if "v12" in f"v{i:03d}"]
        ok = (
            visibles == esperados
            and contador == f"{len(esperados)} videos"
            and len(tarjetas) == 200
            and len(set(tarjetas)) == 200
        )
        return (
            ok,
            f"visibles={len(visibles)} contador={contador!r} "
            f"tarjetas={len(tarjetas)}",
        )
    finally:
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cuadricula = ventana.cuadricula
        area = ventana.area
        contenedor = ventana.contenedor
        viejas = [t for _, t in ventana.tarjetas]
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        widgets_grilla = [
            ventana.cuadricula.itemAt(i).widget()
            for i in range(ventana.cuadricula.count())
        ]
        vivas = [t for t in viejas if t in widgets_grilla]
        hijas = ventana.contenedor.findChildren(Tarjeta)
        ventana.close()
        _limpiar(ventana)
        ok = (
            ventana.cuadricula is cuadricula
            and ventana.area is area
            and ventana.contenedor is contenedor
            and ventana.cuadricula.count() == len(ventana.tarjetas) == 150
            and len(vivas) == 100
            and len(hijas) == len(ventana.tarjetas)
        )
        return (
            ok,
            f"misma_grilla={ventana.cuadricula is cuadricula} "
            f"vivas={len(vivas)} grilla={ventana.cuadricula.count()} "
            f"hijas={len(hijas)}",
        )
    finally:
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    carpeta = _carpeta_con(["nuevo.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        antes = [nombre for nombre, _ in ventana.tarjetas]
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues = [nombre for nombre, _ in ventana.tarjetas]
        total = ventana._total_catalogo
        contador = ventana.contador.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            len(antes) == 150
            and despues == ["nuevo.mkv"]
            and total == 1
            and contador == "1 video"
            and len(set(despues)) == len(despues)
        )
        return (
            ok,
            f"antes={len(antes)} despues={despues} total={total} "
            f"contador={contador!r}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        antes = [nombre for nombre, _ in ventana.tarjetas]
        orig_listar = tv.listar_videos_paginado

        def _falla_lectura(*a, **k):
            raise RuntimeError("fallo controlado de la pagina")

        tv.listar_videos_paginado = _falla_lectura
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig_listar
        estado_error = ventana.estado_escaneo.text()
        gestor_error = ventana.gestor.estado
        pendiente_error = ventana._pagina_pendiente
        tarea_error = ventana.tarea_pagina
        despues_error = [nombre for nombre, _ in ventana.tarjetas]
        hab = ventana.boton_cargar_mas.isEnabled()
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        despues_recuperado = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_error == MENSAJE_ERROR_PAGINA
            and gestor_error == Estado.INACTIVO
            and not pendiente_error
            and tarea_error is None
            and despues_error == antes
            and despues_recuperado == _nombres(150)
            and hab
        )
        return (
            ok,
            f"estado_error={estado_error!r} gestor={gestor_error} "
            f"pendiente={pendiente_error} tarjetas={len(antes)}->"
            f"{len(despues_error)} recuperado={len(despues_recuperado)} "
            f"hab={hab}",
        )
    finally:
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        conteos = {"ffprobe": 0, "ffmpeg": 0, "miniaturas": 0}
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
                    f"no debe ejecutarse {clave} durante la carga de pagina"
                )

            return f

        try:
            tv.obtener_datos_ffprobe = _prohibido("ffprobe")
            escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
            escanear_mod.subprocess.run = _prohibido("ffmpeg")
            tv.asegurar_miniaturas = _prohibido("miniaturas")
            escanear_mod.asegurar_miniaturas = _prohibido("miniaturas")
            escanear_mod.contar_miniaturas = _prohibido("miniaturas")
            ventana.boton_cargar_mas.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.obtener_datos_ffprobe = originales["ffprobe_tv"]
            escanear_mod.obtener_datos_ffprobe = originales["ffprobe_mod"]
            escanear_mod.subprocess.run = originales["run"]
            tv.asegurar_miniaturas = originales["asegurar_tv"]
            escanear_mod.asegurar_miniaturas = originales["asegurar_mod"]
            escanear_mod.contar_miniaturas = originales["contar_mod"]
        ventana.close()
        _limpiar(ventana)
        ok = conteos == {"ffprobe": 0, "ffmpeg": 0, "miniaturas": 0}
        return ok, f"durante={conteos}"
    finally:
        temp.cleanup()


def test_13():
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


def test_14():
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


def test_15():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        cargados = [nombre for nombre, _ in ventana.tarjetas]
        contador = ventana.contador.text()
        total = ventana._total_catalogo
        ventana.close()
        _limpiar(ventana)
        ok = (
            cargados == _nombres(100)
            and contador == "100 videos"
            and total == 150
            and ventana._carga_completada
        )
        return (
            ok,
            f"cargados={len(cargados)} contador={contador!r} total={total}",
        )
    finally:
        temp.cleanup()


def test_16():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        antes = len(QT_MENSAJES)
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig_listar = tv.listar_videos_paginado
        original_close = ventana.closeEvent
        control = _Control(orig_listar)
        tv.listar_videos_paginado = control
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda: control.empezada.is_set())
            activo_mientras = ventana.gestor.activo
            ventana.closeEvent = lambda event: None
            ventana.close()
            control.soltar.set()
            _esperar(
                lambda v=ventana: v.gestor.hilo is None
                and len(_GESTORES_ACTIVOS) == 0
            )
        finally:
            tv.listar_videos_paginado = orig_listar
            ventana.closeEvent = original_close
        _limpiar(ventana)
        avisos = [m for m in QT_MENSAJES[antes:] if "Destroyed while thread" in m]
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
        temp.cleanup()


def test_17():
    comando = [sys.executable, "visor_videos.py"]
    resultado = subprocess.run(
        comando,
        cwd=ruta_raiz(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    ok = (
        resultado.returncode == 0
        and "primera_pagina=100" in salida
        and "contador_primera_pagina=100 videos" in salida
        and "cargar_mas_habilitado=True" in salida
        and "total_tras_cargar_mas=150" in salida
        and "duplicados_tras_cargar_mas=0" in salida
        and "primeras_conservadas=True" in salida
        and "contador_tras_cargar_mas=150 videos" in salida
        and "guardado_total=3" in salida
        and "resumen_sincronizacion=" in salida
        and "0 incorporados, 0 eliminados, 0 candidatos restantes" in salida
        and "tarjetas_finales=['clip.avi', 'peli.mp4', 'serie.mkv']" in salida
        and "escanear_boton_final=True" in salida
        and "Destroyed while thread" not in salida
        and "No se pudo actualizar el catálogo" not in salida
        and "No se pudo cargar la página" not in salida
    )
    return (
        ok,
        f"exit={resultado.returncode} "
        f"paginacion={'total_tras_cargar_mas=150' in salida} "
        f"recarga={'tarjetas_finales=[' in salida} "
        f"avisos={('Destroyed while thread' in salida)}",
    )


def test_18():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
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
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ventana.close()
        _limpiar(ventana)
        despues = estado_real()
        ok = antes == despues
        return ok, f"reales_intactos={antes == despues}"
    finally:
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ok_estado = (
            ventana.gestor.estado == Estado.INACTIVO
            and ventana.gestor.hilo is None
            and ventana.gestor.tarea is None
            and not ventana._pagina_pendiente
            and ventana.tarea_pagina is None
            and len(_GESTORES_ACTIVOS) == 0
        )
        ventana.close()
        _limpiar(ventana)
        return (
            ok_estado,
            f"estado={ventana.gestor.estado} pendiente="
            f"{ventana._pagina_pendiente} gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        temp.cleanup()


def test_20():
    temp, ruta_db = _crear_bd(_filas(_nombres(150)))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana.boton_cargar_mas.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        ventana._pagina_pendiente = True
        ventana.tarea_pagina = object()
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.iniciar_escaneo()
        reseteado = (
            not ventana._pagina_pendiente and ventana.tarea_pagina is None
        )
        _esperar(lambda v=ventana: _cadena_terminada(v))
        tarjetas_finales = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = reseteado and tarjetas_finales == ["x.mp4"]
        return (
            ok,
            f"reseteado={reseteado} tarjetas_finales={tarjetas_finales}",
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
