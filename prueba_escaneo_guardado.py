import ast
import contextlib
import os
import py_compile
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
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_raiz
from tareas import Estado, _GESTORES_ACTIVOS
from tareas_videos import TareaGuardarVideos
from visor_videos import (
    MENSAJE_ERROR_GUARDADO,
    MENSAJE_SIN_ESCANEO,
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
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    def _marcas(ruta):
        with open(ruta, encoding="utf-8") as f:
            arbol = ast.parse(f.read(), ruta)
        definida = False
        importada = False
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.FunctionDef)
                and nodo.name == "preparar_registros_basicos"
            ):
                definida = True
            if (
                isinstance(nodo, ast.ImportFrom)
                and nodo.module == "escanear_videos"
                and any(
                    a.name == "preparar_registros_basicos" for a in nodo.names
                )
            ):
                importada = True
        return definida, importada

    definida_escaneo, _ = _marcas(
        os.path.join(ruta_raiz(), "escanear_videos.py")
    )
    definida_tareas, importada_tareas = _marcas(
        os.path.join(ruta_raiz(), "tareas_videos.py")
    )
    ok = definida_escaneo and not definida_tareas and importada_tareas
    return (
        ok,
        f"def_escaneo={definida_escaneo} def_tareas={definida_tareas} "
        f"import_tareas={importada_tareas}",
    )


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
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana.boton_escanear.click()
        _esperar(lambda v=ventana: _cadena_terminada(v))
        filas = _filas_de(ruta_db)
        guardado = ventana.registros_guardados
        tipo = type(ventana.tarea_guardado).__name__
        estado = ventana.estado_escaneo.text()
        detectados = ventana.videos_detectados
        pendiente_final = ventana._guardado_pendiente
        ventana.close()
        _limpiar(ventana)
        rutas_ok = all(
            f[1] == os.path.join(os.path.abspath(carpeta.name), f[0])
            and os.path.isabs(f[1])
            for f in filas
        )
        fechas_ok = all(f[3] for f in filas)
        ok = (
            tipo == "TareaGuardarVideos"
            and guardado == 3
            and estado == "3 videos detectados"
            and detectados == ["a.mp4", "b.mkv", "c.avi"]
            and [f[0] for f in filas] == ["a.mp4", "b.mkv", "c.avi"]
            and [f[2] for f in filas] == [".mp4", ".mkv", ".avi"]
            and rutas_ok
            and fechas_ok
            and not pendiente_final
        )
        return (
            ok,
            f"tipo={tipo} guardado={guardado} estado={estado!r} "
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

        def _espia(datos_videos, ruta_db=None):
            info["ident"] = threading.get_ident()
            info["principal"] = QThread.isMainThread()
            return orig(datos_videos, ruta_db)

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
        guardado_pendiente = ventana._guardado_pendiente
        tarea_guardado = ventana.tarea_guardado
        tarea_escaneo = ventana.tarea_escaneo
        registros_guardados = ventana.registros_guardados
        detectados = ventana.videos_detectados
        estado = ventana.estado_escaneo.text()
        tarjetas = [nombre for nombre, _ in ventana.tarjetas]
        ventana.close()
        _limpiar(ventana)
        ok = (
            not escaneo_pendiente
            and not guardado_pendiente
            and tarea_guardado is None
            and tarea_escaneo is None
            and registros_guardados is None
            and detectados is None
            and estado == MENSAJE_SIN_ESCANEO
            and tarjetas == ["a.mp4"]
        )
        return (
            ok,
            f"escaneo={escaneo_pendiente} guardado={guardado_pendiente} "
            f"tareas={tarea_guardado},{tarea_escaneo} estado={estado!r}",
        )
    finally:
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        conteo = {"guardar": 0}
        orig = tv.guardar_videos

        def _espia(datos_videos, ruta_db=None):
            conteo["guardar"] += 1
            return orig(datos_videos, ruta_db)

        tv.guardar_videos = _espia
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.guardar_videos = orig
        tipo = type(ventana.tarea_guardado).__name__
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            conteo["guardar"] == 1
            and tipo == "TareaGuardarVideos"
            and [f[0] for f in filas] == ["a.mp4", "b.mkv"]
        )
        return (
            ok,
            f"guardar={conteo['guardar']} tipo={tipo} "
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
        contador = {"subprocess": 0, "ffprobe": 0, "ffmpeg": 0}
        orig_run = escanear_mod.subprocess.run
        orig_ff_tv = tv.obtener_datos_ffprobe
        orig_ff_mod = escanear_mod.obtener_datos_ffprobe
        orig_ffmpeg = escanear_mod.ffmpeg_disponible
        escanear_mod.subprocess.run = _prohibido("subprocess", contador)
        tv.obtener_datos_ffprobe = _prohibido("ffprobe", contador)
        escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe", contador)
        escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg", contador)
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            escanear_mod.subprocess.run = orig_run
            tv.obtener_datos_ffprobe = orig_ff_tv
            escanear_mod.obtener_datos_ffprobe = orig_ff_mod
            escanear_mod.ffmpeg_disponible = orig_ffmpeg
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            contador == {"subprocess": 0, "ffprobe": 0, "ffmpeg": 0}
            and [f[0] for f in filas] == ["x.mp4"]
        )
        return ok, f"contador={contador} filas={filas}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        miniaturas_dir = ruta_carpeta_miniaturas()
        mini_antes = (
            sorted(os.listdir(miniaturas_dir))
            if os.path.isdir(miniaturas_dir)
            else None
        )
        contador = {
            "asegurar": 0,
            "generar": 0,
            "contar": 0,
            "ffmpeg": 0,
        }
        originales = {
            "asegurar": escanear_mod.asegurar_miniatura,
            "generar": escanear_mod.generar_miniatura,
            "contar": escanear_mod.contar_miniaturas,
            "ffmpeg": escanear_mod.ffmpeg_disponible,
        }
        escanear_mod.asegurar_miniatura = _prohibido("asegurar", contador)
        escanear_mod.generar_miniatura = _prohibido("generar", contador)
        escanear_mod.contar_miniaturas = _prohibido("contar", contador)
        escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg", contador)
        try:
            with _dialogo_falso(carpeta.name):
                ventana.seleccionar_carpeta()
            ventana.boton_escanear.click()
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            for clave, original in originales.items():
                setattr(escanear_mod, clave, original)
        mini_despues = (
            sorted(os.listdir(miniaturas_dir))
            if os.path.isdir(miniaturas_dir)
            else None
        )
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            contador == {"asegurar": 0, "generar": 0, "contar": 0, "ffmpeg": 0}
            and mini_antes == mini_despues
            and [f[0] for f in filas] == ["x.mp4"]
        )
        return (
            ok,
            f"contador={contador} miniaturas={mini_antes == mini_despues}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_12():
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
        conn = sqlite3.connect(ruta_db)
        try:
            viejo = conn.execute(
                "SELECT duracion_segundos, codec_video FROM videos WHERE nombre = 'viejo.mp4'"
            ).fetchone()
        finally:
            conn.close()
        ventana.close()
        _limpiar(ventana)
        ok = (
            [f[0] for f in filas] == ["nuevo.mp4", "viejo.mp4"]
            and viejo == (1.0, "h264")
        )
        return ok, f"filas={[f[0] for f in filas]} viejo={viejo}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_13():
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
        esperada = os.path.join(os.path.abspath(carpeta.name), "a.mp4")
        ok = (
            len(filas) == 1
            and filas[0][0] == "a.mp4"
            and filas[0][1] == esperada
        )
        return ok, f"filas={filas} esperada={esperada}"
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
            and gestor_error == Estado.INACTIVO
            and hab_tras_error
            and guardado_final == 1
            and [f[0] for f in filas] == ["x.mp4"]
        )
        return (
            ok,
            f"estado_error={estado_tras_error!r} pendiente={pendiente_error} "
            f"gestor={gestor_error} hab={hab_tras_error} "
            f"final={guardado_final} filas={[f[0] for f in filas]}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["x.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        tarjetas_antes = [nombre for nombre, _ in ventana.tarjetas]
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
            _esperar(lambda v=ventana: _cadena_terminada(v))
        finally:
            tv.listar_videos_paginado = orig
        tarjetas_despues = [nombre for nombre, _ in ventana.tarjetas]
        filas = _filas_de(ruta_db)
        ventana.close()
        _limpiar(ventana)
        ok = (
            llamadas == {"lectura": 0}
            and tarjetas_despues == tarjetas_antes
            and [f[0] for f in filas] == ["a.mp4", "x.mp4"]
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
    print(f"TOTAL={aprobadas}/16")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
