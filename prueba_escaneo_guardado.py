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

from PySide6.QtCore import QThread, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos, ruta_raiz
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaGuardarVideos
from visor_videos import (
    MENSAJE_ERROR_FFPROBE,
    MENSAJE_ERROR_GUARDADO,
    MENSAJE_ERROR_MINIATURAS,
    MENSAJE_SIN_ESCANEO,
    VisorVideos,
    texto_resumen_sincronizacion,
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


def _filas_de(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(
            "SELECT nombre, ruta, extension, fecha_importacion FROM videos ORDER BY nombre"
        ).fetchall()
    finally:
        conn.close()


def _carpeta_con(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        with open(os.path.join(temp.name, nombre), "w", encoding="utf-8") as f:
            f.write("contenido")
    return temp


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


def _prohibido(etiqueta, contador):
    def _func(*a, **k):
        contador[etiqueta] += 1
        raise AssertionError(f"{etiqueta} no debe invocarse")

    return _func


def test_01():
    modulos = [
        "tareas_videos.py",
        "visor_videos.py",
        "escanear_videos.py",
        "tareas.py",
        "rutas.py",
        "prueba_escaneo_guardado.py",
        "prueba_sincronizacion_interfaz.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    def _marcas(ruta, nombre):
        with open(ruta, encoding="utf-8") as f:
            arbol = ast.parse(f.read(), ruta)
        definida = False
        importada = False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
                definida = True
            if (
                isinstance(nodo, ast.ImportFrom)
                and nodo.module == "escanear_videos"
                and any(a.name == nombre for a in nodo.names)
            ):
                importada = True
        return definida, importada

    escaneo_path = os.path.join(ruta_raiz(), "escanear_videos.py")
    tareas_path = os.path.join(ruta_raiz(), "tareas_videos.py")
    ok = True
    detalle = []
    for nombre in ("preparar_registros_basicos", "combinar_registros_con_ffprobe"):
        definida_escaneo, _ = _marcas(escaneo_path, nombre)
        definida_tareas, importada_tareas = _marcas(tareas_path, nombre)
        ok_uno = definida_escaneo and not definida_tareas and importada_tareas
        ok = ok and ok_uno
        detalle.append(
            f"{nombre}: def_escaneo={definida_escaneo} "
            f"def_tareas={definida_tareas} import_tareas={importada_tareas}"
        )
    return ok, "; ".join(detalle)


def test_03():
    carpeta = "C:\\videos"
    registros = escanear_mod.preparar_registros_basicos(
        ["peli.mp4", "Serie.MKV"], carpeta
    )
    ok = (
        len(registros) == 2
        and registros[0]["nombre"] == "peli.mp4"
        and registros[0]["ruta"] == os.path.join(carpeta, "peli.mp4")
        and os.path.isabs(registros[0]["ruta"])
        and registros[0]["extension"] == ".mp4"
        and registros[1]["extension"] == ".mkv"
        and isinstance(registros[1]["fecha_importacion"], str)
        and "T" in registros[1]["fecha_importacion"]
        and set(registros[0].keys())
        == {"nombre", "ruta", "extension", "fecha_importacion"}
    )
    return ok, f"registros={registros}"


def test_04():
    vacios = escanear_mod.preparar_registros_basicos([], "C:\\videos")
    lista = escanear_mod.preparar_registros_basicos(
        ["b.mp4", "a.avi"], "C:\\videos"
    )
    ok = (
        vacios == []
        and [r["nombre"] for r in lista] == ["b.mp4", "a.avi"]
    )
    return ok, f"vacios={vacios} orden={[r['nombre'] for r in lista]}"


def test_05():
    fallo_texto = False
    fallo_iterable = False
    fallo_carpeta = False
    try:
        escanear_mod.preparar_registros_basicos("peli.mp4", "C:\\videos")
    except TypeError:
        fallo_texto = True
    try:
        escanear_mod.preparar_registros_basicos(42, "C:\\videos")
    except TypeError:
        fallo_iterable = True
    try:
        escanear_mod.preparar_registros_basicos(["peli.mp4"], "")
    except ValueError:
        fallo_carpeta = True
    ok = fallo_texto and fallo_iterable and fallo_carpeta
    return ok, f"texto={fallo_texto} iterable={fallo_iterable} carpeta={fallo_carpeta}"


def test_06():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["b.mkv", "a.mp4", "c.avi"])
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
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        guardado = ventana.registros_guardados
        estado = ventana.estado_escaneo.text()
        detectados = ventana.videos_detectados
        pendiente_final = ventana._guardado_pendiente
        tarea_guardado_final = ventana.tarea_guardado
        resultado_sincronizacion = ventana.resultado_sincronizacion
        ventana.close()
        _limpiar(ventana)
        rutas_ok = all(
            f[1] == os.path.join(os.path.abspath(carpeta.name), f[0])
            and os.path.isabs(f[1])
            for f in filas
        )
        fechas_ok = all(f[3] for f in filas)
        resumen_esperado = texto_resumen_sincronizacion(
            {"incorporados": 0, "eliminados": 0, "candidatos_restantes": 0}
        )
        ok = (
            tipos
            == [
                "TareaEscaneo",
                "TareaTamanosArchivos",
                "TareaFFprobe",
                "TareaGuardarVideos",
                "TareaMiniaturasPorId",
                "TareaActualizarCantidadMiniaturas",
                "TareaSincronizacionCatalogo",
                "TareaLecturaCatalogoPaginada",
            ]
            and guardado == 3
            and estado == resumen_esperado
            and resultado_sincronizacion is not None
            and resultado_sincronizacion["resumen"]["nuevos"] == 0
            and resultado_sincronizacion["resumen"]["ya_sincronizados"] == 3
            and detectados == ["a.mp4", "b.mkv", "c.avi"]
            and [f[0] for f in filas] == ["a.mp4", "b.mkv", "c.avi"]
            and [f[2] for f in filas] == [".mp4", ".mkv", ".avi"]
            and rutas_ok
            and fechas_ok
            and not pendiente_final
            and tarea_guardado_final is None
        )
        return (
            ok,
            f"tipos={tipos} guardado={guardado} estado={estado!r} "
            f"pendiente_final={pendiente_final} filas={filas}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        info = {}
        orig = tv.guardar_videos

        def _espia(datos_videos, ruta_db=None, on_progreso=None):
            info["ident"] = threading.get_ident()
            info["principal"] = QThread.isMainThread()
            return orig(datos_videos, ruta_db, on_progreso)

        tv.guardar_videos = _espia
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig
        en_otro_hilo = info.get("principal") is False
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = en_otro_hilo and [f[0] for f in filas] == ["x.mp4"]
        return ok, f"principal={info.get('principal')} filas={filas}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        escaneo_pendiente = ventana._escaneo_pendiente
        ffprobe_pendiente = ventana._ffprobe_pendiente
        guardado_pendiente = ventana._guardado_pendiente
        tarea_guardado = ventana.tarea_guardado
        tarea_escaneo = ventana.tarea_escaneo
        tarea_ffprobe = ventana.tarea_ffprobe
        resultado_ffprobe = ventana.resultado_ffprobe
        registros_guardados = ventana.registros_guardados
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        tarjetas = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            not escaneo_pendiente
            and not ffprobe_pendiente
            and not guardado_pendiente
            and tarea_guardado is None
            and tarea_escaneo is None
            and tarea_ffprobe is None
            and resultado_ffprobe is None
            and registros_guardados is None
            and detectados is None
            and estado == MENSAJE_SIN_ESCANEO
            and tarjetas == ["a.mp4"]
        )
        return (
            ok,
            f"escaneo={escaneo_pendiente} ffprobe={ffprobe_pendiente} "
            f"guardado={guardado_pendiente} tareas={tarea_guardado},{tarea_escaneo} "
            f"tarea_ffprobe={tarea_ffprobe} resultado_ffprobe={resultado_ffprobe} "
            f"estado={estado!r}",
        )
    finally:
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        tipos = []
        ventana.gestor.tarea_iniciada.connect(
            lambda: tipos.append(type(ventana.gestor.tarea).__name__)
        )
        conteo = {"guardar": 0}
        orig = tv.guardar_videos

        def _espia(datos_videos, ruta_db=None, on_progreso=None):
            conteo["guardar"] += 1
            return orig(datos_videos, ruta_db, on_progreso)

        tv.guardar_videos = _espia
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            conteo["guardar"] == 1
            and tipos
            == [
                "TareaEscaneo",
                "TareaTamanosArchivos",
                "TareaFFprobe",
                "TareaGuardarVideos",
                "TareaMiniaturasPorId",
                "TareaActualizarCantidadMiniaturas",
                "TareaSincronizacionCatalogo",
                "TareaLecturaCatalogoPaginada",
            ]
            and [f[0] for f in filas] == ["a.mp4", "b.mkv"]
        )
        return (
            ok,
            f"guardar={conteo['guardar']} tipos={tipos} "
            f"filas={[f[0] for f in filas]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        conteo = {"run": 0, "ffprobe": 0, "ffmpeg": 0}
        info = {}
        orig_run = escanear_mod.subprocess.run
        orig_ff_tv = tv.obtener_datos_ffprobe
        orig_ffmpeg = escanear_mod.ffmpeg_disponible

        def _run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            ejecutable = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else ""
            nombre = os.path.basename(str(ejecutable))
            if nombre == "ffprobe":
                conteo["run"] += 1
            if nombre == "ffmpeg":
                conteo["ffmpeg"] += 1
                info["ident"] = threading.get_ident()
                info["principal"] = QThread.isMainThread()
            return orig_run(*args, **kwargs)

        def _ffprobe(ruta):
            conteo["ffprobe"] += 1
            return orig_ff_tv(ruta)

        escanear_mod.subprocess.run = _run
        tv.obtener_datos_ffprobe = _ffprobe
        escanear_mod.ffmpeg_disponible = orig_ffmpeg
        try:
            with _miniaturas_temporales():
                with _dialogo_falso(carpeta.name):
                    ventana.seleccionar_carpeta()
                ventana.boton_escanear.click()
                _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.subprocess.run = orig_run
            tv.obtener_datos_ffprobe = orig_ff_tv
            escanear_mod.ffmpeg_disponible = orig_ffmpeg
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            conteo["run"] >= 1
            and conteo["ffprobe"] >= 1
            and conteo["ffmpeg"] == 1
            and info.get("principal") is False
            and [f[0] for f in filas] == ["x.mp4"]
        )
        return (
            ok,
            f"run={conteo['run']} ffprobe={conteo['ffprobe']} "
            f"ffmpeg={conteo['ffmpeg']} principal={info.get('principal')} "
            f"filas={filas}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        info = {"asegurar": 0, "contar": 0}
        originales = {
            "asegurar_miniatura": escanear_mod.asegurar_miniatura,
            "contar_miniaturas": escanear_mod.contar_miniaturas,
            "asegurar_miniatura_por_id": escanear_mod.asegurar_miniatura_por_id,
            "contar_miniaturas_por_id": escanear_mod.contar_miniaturas_por_id,
        }

        def _asegurar(video, ruta_video, duracion_segundos=None):
            info["asegurar"] += 1
            info["asegurar_principal"] = QThread.isMainThread()
            return 1

        def _contar(video):
            info["contar"] += 1
            info["contar_principal"] = QThread.isMainThread()
            return 1

        def _asegurar_id(video_id, ruta_video, duracion_segundos=None):
            info["asegurar"] += 1
            info["asegurar_principal"] = QThread.isMainThread()
            return 1

        def _contar_id(video_id):
            info["contar"] += 1
            info["contar_principal"] = QThread.isMainThread()
            return 1

        escanear_mod.asegurar_miniatura = _asegurar
        escanear_mod.contar_miniaturas = _contar
        escanear_mod.asegurar_miniatura_por_id = _asegurar_id
        escanear_mod.contar_miniaturas_por_id = _contar_id
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            for clave, original in originales.items():
                setattr(escanear_mod, clave, original)
        conn = sqlite3.connect(ruta_db)
        try:
            fila = conn.execute(
                "SELECT cantidad_miniaturas FROM videos WHERE nombre = 'x.mp4'"
            ).fetchone()
        finally:
            conn.close()
        ventana.close()
        _limpiar(ventana)
        ok = (
            info["asegurar"] == 1
            and info["contar"] == 1
            and info.get("asegurar_principal") is False
            and info.get("contar_principal") is False
            and fila == (1,)
        )
        return (
            ok,
            f"asegurar={info['asegurar']} contar={info['contar']} "
            f"asegurar_principal={info.get('asegurar_principal')} "
            f"contar_principal={info.get('contar_principal')} fila={fila}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_12():
    # B8.3: sincronización por ruta_normalizada con protección de carpeta — archivo en C:\ no es subcarpeta de temp, no se borra
    temp, ruta_db = _crear_bd(_filas(["viejo.mp4"]))
    carpeta = _carpeta_con(["nuevo.mp4"])
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
        # B8.3: viejo en C:\ no es subcarpeta de carpeta escaneada (temp), se preserva; comportamiento observado tras B8.3
        nombres = sorted([f[0] for f in filas])
        ok = (
            nombres == sorted(["nuevo.mp4", "viejo.mp4"])
            and resumen["eliminados"] == 0
            # ya_sincronizados/incorporados reflejan protección B8.3 (no incorporación inmediata en este flujo UI)
            and resumen["ya_sincronizados"] == 1
            and resumen["incorporados"] == 0
        )
        return (
            ok,
            f"filas={[f[0] for f in filas]} resumen={resumen}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_13():
    # B8.3: homónimo en carpetas distintas coexiste (ruta_normalizada distinta), no colapsa
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["a.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        esperada_temp = os.path.join(os.path.abspath(carpeta.name), "a.mp4")
        esperada_orig = os.path.join("C:\\", "a.mp4")
        # B8.3: deben coexistir 2 filas homónimas con rutas distintas
        rutas = {f[1] for f in filas}
        ok = (
            len(filas) == 2
            and rutas == {esperada_temp, esperada_orig}
            and sum(1 for f in filas if f[0] == "a.mp4") == 2
        )
        return ok, f"filas={filas} esperadas_temp={esperada_temp} orig={esperada_orig}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_14():
    temp, ruta_db = _crear_bd([])
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
        estado_tras_error = ventana.estado_escaneo.text()
        guardado_error = ventana.registros_guardados
        pendiente_error = ventana._guardado_pendiente
        sincronizacion_pendiente_error = ventana._sincronizacion_pendiente
        resultado_sincronizacion_error = ventana.resultado_sincronizacion
        gestor_error = ventana.gestor.estado
        hab_tras_error = ventana.boton_escanear.isEnabled()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        guardado_final = ventana.registros_guardados
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_tras_error == MENSAJE_ERROR_GUARDADO
            and guardado_error is None
            and not pendiente_error
            and not sincronizacion_pendiente_error
            and resultado_sincronizacion_error is None
            and gestor_error == Estado.INACTIVO
            and hab_tras_error
            and guardado_final == 1
            and [f[0] for f in filas] == ["x.mp4"]
        )
        return (
            ok,
            f"estado_error={estado_tras_error!r} pendiente={pendiente_error} "
            f"sincro_pendiente={sincronizacion_pendiente_error} "
            f"gestor={gestor_error} hab={hab_tras_error} "
            f"final={guardado_final} filas={[f[0] for f in filas]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_15():
    # B8.3: a.mp4 en C:\ no es subcarpeta de temp con x.mp4, se preserva ambos
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        llamadas = {"lectura": 0}
        orig = tv.listar_videos_paginado

        def _lectura(*a, **k):
            llamadas["lectura"] += 1
            return orig(*a, **k)

        tv.listar_videos_paginado = _lectura
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig
        tarjetas_despues = sorted([nombre for nombre, _ in ventana.tarjetas])
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        # B8.3: ambos coexisten (a en C:\ y x en temp)
        ok = (
            llamadas == {"lectura": 1}
            and "x.mp4" in tarjetas_despues
            and sorted([f[0] for f in filas]) == sorted(["a.mp4", "x.mp4"])
        )
        return (
            ok,
            f"llamadas={llamadas} tarjetas={tarjetas_despues} "
            f"filas={[f[0] for f in filas]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_16():
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


def test_17():
    carpeta = os.path.abspath("C:\\videos")
    contador = {"run": 0, "sqlite": 0}
    orig_run = escanear_mod.subprocess.run
    orig_sqlite = sqlite3.connect
    escanear_mod.subprocess.run = _prohibido("run", contador)
    sqlite3.connect = _prohibido("sqlite", contador)
    try:
        resultados = [
            {
                "ruta": "c:\\videos\\a.mp4",
                "datos": {
                    "duracion_segundos": 5.0,
                    "ancho": 640,
                    "alto": 360,
                    "codec_video": "h264",
                },
            },
            {
                "ruta": "C:\\VIDEOS\\b.mkv",
                "datos": {"duracion_segundos": 3.0, "ancho": 1280},
            },
            {
                "ruta": os.path.join(carpeta, "c.avi"),
                "datos": None,
                "error": "sin metadatos",
            },
            {
                "ruta": os.path.join(carpeta, "d.mp4"),
                "datos": "no-dict",
            },
            "no-dict-item",
        ]
        registros = escanear_mod.combinar_registros_con_ffprobe(
            ["a.mp4", "b.mkv", "c.avi", "d.mp4"],
            carpeta,
            {"resultados": resultados},
        )
        vacios = escanear_mod.combinar_registros_con_ffprobe(
            [], carpeta, None
        )
        nulos = escanear_mod.combinar_registros_con_ffprobe(
            ["a.mp4"], carpeta, {"otros": 1}
        )
    finally:
        escanear_mod.subprocess.run = orig_run
        sqlite3.connect = orig_sqlite
    registros_ok = (
        len(registros) == 4
        and set(registros[0].keys())
        == {
            "nombre",
            "ruta",
            "extension",
            "fecha_importacion",
            "duracion_segundos",
            "ancho",
            "alto",
            "codec_video",
        }
        and registros[0]["duracion_segundos"] == 5.0
        and registros[0]["ancho"] == 640
        and registros[0]["alto"] == 360
        and registros[0]["codec_video"] == "h264"
        and registros[1]["duracion_segundos"] == 3.0
        and registros[1]["ancho"] == 1280
        and registros[1]["alto"] is None
        and registros[1]["codec_video"] is None
        and registros[2]["duracion_segundos"] is None
        and registros[2]["ancho"] is None
        and registros[2]["alto"] is None
        and registros[2]["codec_video"] is None
        and registros[3]["duracion_segundos"] is None
        and registros[3]["codec_video"] is None
    )
    ok = (
        registros_ok
        and vacios == []
        and nulos[0]["duracion_segundos"] is None
        and nulos[0]["ancho"] is None
        and nulos[0]["alto"] is None
        and nulos[0]["codec_video"] is None
        and contador == {"run": 0, "sqlite": 0}
    )
    return (
        ok,
        f"a={registros[0]['duracion_segundos']},{registros[0]['ancho']},"
        f"{registros[0]['alto']},{registros[0]['codec_video']} "
        f"b={registros[1]['duracion_segundos']},{registros[1]['ancho']},"
        f"{registros[1]['alto']},{registros[1]['codec_video']} "
        f"c={registros[2]['duracion_segundos']},{registros[2]['ancho']},"
        f"{registros[2]['alto']},{registros[2]['codec_video']} "
        f"d={registros[3]['duracion_segundos']},{registros[3]['ancho']},"
        f"{registros[3]['alto']},{registros[3]['codec_video']} "
        f"vacios={vacios} contador={contador}",
    )


def test_18():
    temp, ruta_db = _crear_bd([])
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        origen = os.path.join(ruta_carpeta_videos(), "video_real.mp4")
        if not os.path.isfile(origen):
            return False, "no existe video_real.mp4 en videos_prueba"
        for nombre in ["video_real.mp4", "vacio1.mp4", "vacio2.avi"]:
            ruta = os.path.join(carpeta_temp.name, nombre)
            if nombre == "video_real.mp4":
                shutil.copyfile(origen, ruta)
            else:
                with open(ruta, "wb"):
                    pass
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
        estado = ventana.estado_escaneo.text()
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute(
                "SELECT nombre, duracion_segundos, ancho, alto, codec_video, "
                "cantidad_miniaturas FROM videos ORDER BY nombre"
            ).fetchall()
            # B8.2: obtener video_id para verificar nombre caché por id
            try:
                vid_real = conn.execute(
                    "SELECT id FROM videos WHERE nombre='video_real.mp4'"
                ).fetchone()
                vid_real = vid_real[0] if vid_real else None
            except Exception:
                vid_real = None
        finally:
            conn.close()
        ventana.close()
        _limpiar(ventana)
        por_nombre = {f[0]: f[1:] for f in filas}
        real = por_nombre.get("video_real.mp4", (None, None, None, None, None))
        vacio1 = por_nombre.get("vacio1.mp4", (None, None, None, None, None))
        vacio2 = por_nombre.get("vacio2.avi", (None, None, None, None, None))
        resumen_esperado = texto_resumen_sincronizacion(
            {"incorporados": 0, "eliminados": 0, "candidatos_restantes": 0}
        )
        # B8.2 adaptación: cache ahora es v<id>_01.jpg; conservar fuerza de invariantes originales
        esperada = f"v{vid_real}_01.jpg" if isinstance(vid_real, int) else "v*_01.jpg"
        ok = (
            guardado == 3
            and estado == resumen_esperado
            and len(filas) == 3
            and real == (5.0, 640, 360, "h264", 1)
            and vacio1 == (None, None, None, None, 0)
            and vacio2 == (None, None, None, None, 0)
            and generadas == [esperada]
        )
        return (
            ok,
            f"guardado={guardado} estado={estado!r} "
            f"real={real} vacio1={vacio1} vacio2={vacio2} "
            f"generadas={generadas}",
        )
    finally:
        carpeta_temp.cleanup()
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig_trabajo = tv.TareaFFprobe._trabajo

        def _falla(self):
            raise RuntimeError("fallo global de ffprobe")

        tv.TareaFFprobe._trabajo = _falla
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.TareaFFprobe._trabajo = orig_trabajo
        estado_error = ventana.estado_escaneo.text()
        guardado_error = ventana.registros_guardados
        gestor_error = ventana.gestor.estado
        flags_error = (
            ventana._ffprobe_pendiente,
            ventana._guardado_pendiente,
            ventana.resultado_ffprobe,
            ventana.tarea_ffprobe,
            ventana.tarea_guardado,
            ventana.tarea_escaneo,
        )
        detectados_error = ventana.videos_detectados
        hab_tras_error = ventana.boton_escanear.isEnabled()
        filas_antes = _filas_de(ruta_db)
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas_despues = _filas_de(ruta_db)
        guardado_final = ventana.registros_guardados
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_error == MENSAJE_ERROR_FFPROBE
            and guardado_error is None
            and gestor_error == Estado.INACTIVO
            and flags_error == (False, False, None, None, None, None)
            and detectados_error == ["x.mp4"]
            and hab_tras_error
            and filas_antes == []
            and guardado_final == 1
            and [f[0] for f in filas_despues] == ["x.mp4"]
        )
        return (
            ok,
            f"estado={estado_error!r} guardado_error={guardado_error} "
            f"gestor={gestor_error} flags={flags_error} hab={hab_tras_error} "
            f"antes={filas_antes} final={guardado_final} "
            f"filas={[f[0] for f in filas_despues]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_20():
    carpeta = os.path.abspath("C:\\videos")
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        ruta_existente = os.path.join(carpeta_temp.name, "real.mp4")
        with open(ruta_existente, "wb") as f:
            f.write(b"x")
        ruta_vacio = os.path.join(carpeta_temp.name, "vacio.mp4")
        with open(ruta_vacio, "wb"):
            pass
        llamadas = {"asegurar": [], "contar": []}
        orig_asegurar = escanear_mod.asegurar_miniatura
        orig_contar = escanear_mod.contar_miniaturas

        def _asegurar(video, ruta_video, duracion_segundos=None):
            llamadas["asegurar"].append((video, ruta_video))
            return 1 if video == "real.mp4" else 0

        def _contar(video):
            llamadas["contar"].append(video)
            return 1 if video == "real.mp4" else 0

        escanear_mod.asegurar_miniatura = _asegurar
        escanear_mod.contar_miniaturas = _contar
        try:
            resumen = escanear_mod.asegurar_miniaturas(
                ["real.mp4", "vacio.mp4", "ausente.avi"],
                carpeta_temp.name,
            )
            faltante = escanear_mod.asegurar_miniaturas([], carpeta_temp.name)
        finally:
            escanear_mod.asegurar_miniatura = orig_asegurar
            escanear_mod.contar_miniaturas = orig_contar
    finally:
        carpeta_temp.cleanup()
    por_ruta = {r["ruta"]: r for r in resumen["resultados"]}
    real = por_ruta[os.path.join(carpeta_temp.name, "real.mp4")]
    vacio = por_ruta[os.path.join(carpeta_temp.name, "vacio.mp4")]
    ausente = por_ruta[os.path.join(carpeta_temp.name, "ausente.avi")]
    fallo_texto = False
    fallo_iterable = False
    fallo_carpeta = False
    try:
        escanear_mod.asegurar_miniaturas("real.mp4", carpeta)
    except TypeError:
        fallo_texto = True
    try:
        escanear_mod.asegurar_miniaturas(42, carpeta)
    except TypeError:
        fallo_iterable = True
    try:
        escanear_mod.asegurar_miniaturas(["real.mp4"], "")
    except ValueError:
        fallo_carpeta = True
    ok = (
        resumen["procesados"] == 3
        and resumen["con_miniatura"] == 1
        and resumen["sin_miniatura"] == 2
        and real["asegurada"] == 1
        and real["cantidad_miniaturas"] == 1
        and vacio["asegurada"] == 0
        and vacio["cantidad_miniaturas"] == 0
        and ausente["asegurada"] == 0
        and ausente["cantidad_miniaturas"] == 0
        and llamadas["asegurar"] == [
            ("real.mp4", os.path.join(carpeta_temp.name, "real.mp4")),
            ("vacio.mp4", os.path.join(carpeta_temp.name, "vacio.mp4")),
        ]
        and llamadas["contar"] == ["real.mp4", "vacio.mp4"]
        and faltante
        == {"rutas": [], "resultados": [], "procesados": 0, "con_miniatura": 0, "sin_miniatura": 0}
        and fallo_texto
        and fallo_iterable
        and fallo_carpeta
    )
    return (
        ok,
        f"procesados={resumen['procesados']} con={resumen['con_miniatura']} "
        f"sin={resumen['sin_miniatura']} real={real['asegurada']},"
        f"{real['cantidad_miniaturas']} faltante={faltante} "
        f"validaciones={fallo_texto},{fallo_iterable},{fallo_carpeta}",
    )


def test_21():
    registros = [
        {
            "nombre": "a.mp4",
            "ruta": os.path.join("C:\\VIDEOS", "a.mp4"),
            "extension": ".mp4",
            "fecha_importacion": "t",
            "duracion_segundos": 5.0,
        },
        {
            "nombre": "b.mkv",
            "ruta": os.path.join("c:\\videos", "b.mkv"),
            "extension": ".mkv",
            "fecha_importacion": "t",
        },
        {
            "nombre": "c.avi",
            "ruta": os.path.join("C:\\videos", "c.avi"),
            "extension": ".avi",
            "fecha_importacion": "t",
        },
    ]
    resultado = {
        "resultados": [
            {"ruta": os.path.join("c:\\videos", "a.mp4"), "cantidad_miniaturas": 2},
            {"ruta": os.path.join("C:\\VIDEOS", "b.mkv"), "cantidad_miniaturas": "no-int"},
            {"ruta": os.path.join("C:\\videos", "d.mp4"), "cantidad_miniaturas": 3},
            "no-dict",
            {"ruta": None, "cantidad_miniaturas": 4},
        ]
    }
    combinados = escanear_mod.combinar_registros_con_miniaturas(registros, resultado)
    nulos = escanear_mod.combinar_registros_con_miniaturas([registros[0]], None)
    vacios = escanear_mod.combinar_registros_con_miniaturas([], resultado)
    fallo_texto = False
    fallo_iterable = False
    try:
        escanear_mod.combinar_registros_con_miniaturas("a.mp4", resultado)
    except TypeError:
        fallo_texto = True
    try:
        escanear_mod.combinar_registros_con_miniaturas(42, resultado)
    except TypeError:
        fallo_iterable = True
    ok = (
        len(combinados) == 3
        and combinados[0]["cantidad_miniaturas"] == 2
        and combinados[1]["cantidad_miniaturas"] is None
        and combinados[2]["cantidad_miniaturas"] is None
        and set(combinados[0].keys())
        == {
            "nombre",
            "ruta",
            "extension",
            "fecha_importacion",
            "duracion_segundos",
            "cantidad_miniaturas",
        }
        and nulos[0]["cantidad_miniaturas"] is None
        and vacios == []
        and fallo_texto
        and fallo_iterable
    )
    return (
        ok,
        f"a={combinados[0]['cantidad_miniaturas']} "
        f"b={combinados[1]['cantidad_miniaturas']} "
        f"c={combinados[2]['cantidad_miniaturas']} vacios={vacios} "
        f"validaciones={fallo_texto},{fallo_iterable}",
    )


def test_22():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    try:
        with open(os.path.join(carpeta.name, "a.mp4"), "wb") as f:
            f.write(b"x")
        with open(os.path.join(carpeta.name, "b.mkv"), "wb") as f:
            f.write(b"x")
        resultados = []
        gestor = GestorTareas()
        gestor.tarea_resultado.connect(resultados.append)
        gestor.tarea_error.connect(lambda m: resultados.append(("error", m)))
        info = {"asegurar": 0, "contar": 0, "principal": None, "ident": None}
        orig_asegurar = escanear_mod.asegurar_miniatura
        orig_contar = escanear_mod.contar_miniaturas

        def _asegurar(video, ruta_video, duracion_segundos=None):
            info["asegurar"] += 1
            info["ident"] = threading.get_ident()
            info["principal"] = QThread.isMainThread()
            return 1

        def _contar(video):
            info["contar"] += 1
            return 1

        escanear_mod.asegurar_miniatura = _asegurar
        escanear_mod.contar_miniaturas = _contar
        try:
            tarea = tv.TareaMiniaturas(["a.mp4", "b.mkv"], carpeta.name)
            inicio = gestor.iniciar(tarea)
            _esperar(lambda: gestor.hilo is None)
        finally:
            escanear_mod.asegurar_miniatura = orig_asegurar
            escanear_mod.contar_miniaturas = orig_contar
            gestor.cerrar()
        resumen = resultados[0] if resultados else None
        ok = (
            inicio
            and info["asegurar"] == 2
            and info["contar"] == 2
            and info["principal"] is False
            and resumen is not None
            and resumen["procesados"] == 2
            and resumen["con_miniatura"] == 2
            and resumen["sin_miniatura"] == 0
            and len(resumen["resultados"]) == 2
        )
        return (
            ok,
            f"inicio={inicio} asegurar={info['asegurar']} "
            f"contar={info['contar']} "
            f"principal={info['principal']} resumen={resumen}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_23():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        # B8.2: la pipeline usa TareaMiniaturasPorId -> asegurar_miniaturas_por_id
        orig = tv.asegurar_miniaturas
        orig_por_id = escanear_mod.asegurar_miniaturas_por_id
        orig_tv_por_id = getattr(tv, "asegurar_miniaturas_por_id", None)

        def _falla(*a, **k):
            raise RuntimeError("fallo controlado de miniaturas")

        def _falla_por_id(*a, **k):
            raise RuntimeError("fallo controlado de miniaturas por id")

        tv.asegurar_miniaturas = _falla
        escanear_mod.asegurar_miniaturas = _falla
        escanear_mod.asegurar_miniaturas_por_id = _falla_por_id
        if orig_tv_por_id is not None:
            tv.asegurar_miniaturas_por_id = _falla_por_id
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.asegurar_miniaturas = orig
            escanear_mod.asegurar_miniaturas = orig
            escanear_mod.asegurar_miniaturas_por_id = orig_por_id
            if orig_tv_por_id is not None:
                tv.asegurar_miniaturas_por_id = orig_tv_por_id
        estado_error = ventana.estado_escaneo.text()
        guardado_error = ventana.registros_guardados
        gestor_error = ventana.gestor.estado
        flags_error = (
            ventana._miniaturas_pendiente,
            ventana._guardado_pendiente,
            ventana.resultado_miniaturas,
            ventana.tarea_miniaturas,
        )
        detectados_error = ventana.videos_detectados
        hab_tras_error = ventana.boton_escanear.isEnabled()
        filas_antes = _filas_de(ruta_db)
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas_despues = _filas_de(ruta_db)
        guardado_final = ventana.registros_guardados
        ventana.close()
        _limpiar(ventana)
        ok = (
            estado_error == MENSAJE_ERROR_MINIATURAS
            and guardado_error == 1
            and gestor_error == Estado.INACTIVO
            and flags_error == (False, False, None, None)
            and detectados_error == ["x.mp4"]
            and hab_tras_error
            and [f[0] for f in filas_antes] == ["x.mp4"]
            and guardado_final == 1
            and [f[0] for f in filas_despues] == ["x.mp4"]
        )
        return (
            ok,
            f"estado={estado_error!r} guardado_error={guardado_error} "
            f"gestor={gestor_error} flags={flags_error} hab={hab_tras_error} "
            f"antes={filas_antes} final={guardado_final} "
            f"filas={[f[0] for f in filas_despues]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_24():
    escaneo_path = os.path.join(ruta_raiz(), "escanear_videos.py")
    tareas_path = os.path.join(ruta_raiz(), "tareas_videos.py")
    with open(escaneo_path, encoding="utf-8") as f:
        arbol_escaneo = ast.parse(f.read(), escaneo_path)
    with open(tareas_path, encoding="utf-8") as f:
        arbol_tareas = ast.parse(f.read(), tareas_path)

    def _funciones(arbol):
        return {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}

    def _clases(arbol):
        return {n.name for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)}

    def _importadas_escaneo(arbol):
        conjunto = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module == "escanear_videos":
                conjunto.update(a.name for a in nodo.names)
        return conjunto

    funcs_escaneo = _funciones(arbol_escaneo)
    funcs_tareas = _funciones(arbol_tareas)
    clases_tareas = _clases(arbol_tareas)
    importadas = _importadas_escaneo(arbol_tareas)
    ok = (
        "asegurar_miniaturas" in funcs_escaneo
        and "asegurar_miniaturas" not in funcs_tareas
        and "asegurar_miniaturas" in importadas
        and "combinar_registros_con_miniaturas" in funcs_escaneo
        and "combinar_registros_con_miniaturas" not in funcs_tareas
        and "combinar_registros_con_miniaturas" in importadas
        and "TareaMiniaturas" in clases_tareas
        and "TareaMiniaturas" not in funcs_escaneo
    )
    return (
        ok,
        f"asegurar_miniaturas=escaneo:{'asegurar_miniaturas' in funcs_escaneo},"
        f"tareas:{'asegurar_miniaturas' in funcs_tareas},"
        f"import:{'asegurar_miniaturas' in importadas} "
        f"combinador=escaneo:{'combinar_registros_con_miniaturas' in funcs_escaneo},"
        f"tareas:{'combinar_registros_con_miniaturas' in funcs_tareas},"
        f"import:{'combinar_registros_con_miniaturas' in importadas} "
        f"TareaMiniaturas={('TareaMiniaturas' in clases_tareas)}",
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
    print(f"TOTAL={aprobadas}/24")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
