import contextlib
import json
import os
import py_compile
import sqlite3
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtCore import QEventLoop, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import visor_videos
import arbol_navegacion
from configuracion import (
    CLAVE_CARPETA,
    VARIABLE_ENTORNO,
    _resolver_ruta_config,
    guardar_ultima_carpeta,
    obtener_ultima_carpeta,
)
from rutas import ruta_configuracion, ruta_raiz
from visor_videos import (
    MENSAJE_SIN_CARPETA,
    TAMANIO_PAGINA_INICIAL,
    VisorVideos,
)

QT_MENSAJES = []

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ[VARIABLE_ENTORNO] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


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


def _leer_json(ruta_config):
    with open(ruta_config, encoding="utf-8") as f:
        return json.load(f)


def test_01():
    modulos = [
        "configuracion.py",
        "rutas.py",
        "visor_videos.py",
        "prueba_persistencia_carpeta.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    ruta_config = ruta_configuracion()
    ok = (
        ruta_config == os.path.join(ruta_raiz(), "configuracion.json")
        and os.path.isabs(ruta_config)
        and ruta_config.endswith("configuracion.json")
    )
    return ok, f"ruta={ruta_config}"


def test_03():
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        devuelta = guardar_ultima_carpeta(carpeta.name, ruta_config)
        datos = _leer_json(ruta_config)
        ok = (
            devuelta == os.path.abspath(carpeta.name)
            and datos.get(CLAVE_CARPETA) == os.path.abspath(carpeta.name)
        )
        return ok, f"devuelta={devuelta} datos={datos}"
    finally:
        carpeta.cleanup()
        config.cleanup()


def test_04():
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        guardar_ultima_carpeta(carpeta.name, ruta_config)
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada == os.path.abspath(carpeta.name)
        return ok, f"recuperada={recuperada}"
    finally:
        carpeta.cleanup()
        config.cleanup()


def test_05():
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        inexistente = os.path.join(config.name, "no_existe", "carpeta")
        devuelta = guardar_ultima_carpeta(inexistente, ruta_config)
        ok = devuelta is None and not os.path.exists(ruta_config)
        return ok, f"devuelta={devuelta} existe={os.path.exists(ruta_config)}"
    finally:
        config.cleanup()


def test_06():
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        guardar_ultima_carpeta(carpeta.name, ruta_config)
        carpeta.cleanup()
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada is None
        return ok, f"recuperada={recuperada}"
    finally:
        config.cleanup()


def test_07():
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada is None
        return ok, f"recuperada={recuperada} existe={os.path.exists(ruta_config)}"
    finally:
        config.cleanup()


def test_08():
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        with open(ruta_config, "w", encoding="utf-8") as f:
            f.write("esto no es json {")
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada is None
        return ok, f"recuperada={recuperada}"
    finally:
        config.cleanup()


def test_09():
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump(["no", "es", "diccionario"], f)
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada is None
        return ok, f"recuperada={recuperada}"
    finally:
        config.cleanup()


def test_10():
    temp = tempfile.TemporaryDirectory()
    carpeta = os.path.join(temp.name, "vídeos-áéíóú ñ", "sub")
    os.makedirs(carpeta)
    ruta_config = os.path.join(temp.name, "configuracion.json")
    try:
        guardar_ultima_carpeta(carpeta, ruta_config)
        recuperada = obtener_ultima_carpeta(ruta_config)
        ok = recuperada == os.path.abspath(carpeta)
        return ok, f"recuperada={recuperada}"
    finally:
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        inicial = ventana.carpeta_seleccionada
        etiqueta = ventana.etiqueta_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        datos = _leer_json(ruta_config) if os.path.exists(ruta_config) else None
        ok = (
            inicial is None
            and etiqueta == MENSAJE_SIN_CARPETA
            and (datos is None or CLAVE_CARPETA not in datos)
        )
        return ok, f"inicial={inicial} etiqueta={etiqueta!r}"
    finally:
        config.cleanup()
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        seleccionada = ventana.carpeta_seleccionada
        etiqueta = ventana.etiqueta_carpeta.text()
        datos = _leer_json(ruta_config)
        ventana.close()
        _limpiar(ventana)
        ok = (
            seleccionada == os.path.abspath(carpeta.name)
            and etiqueta == seleccionada
            and datos.get(CLAVE_CARPETA) == seleccionada
        )
        return ok, f"seleccionada={seleccionada} datos={datos}"
    finally:
        carpeta.cleanup()
        config.cleanup()
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)

        reabierta = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=reabierta: v._carga_completada and v.gestor.hilo is None)
        restaurada = reabierta.carpeta_seleccionada
        etiqueta = reabierta.etiqueta_carpeta.text()
        reabierta.close()
        _limpiar(reabierta)
        ok = (
            restaurada == guardada == os.path.abspath(carpeta.name)
            and etiqueta == restaurada
        )
        return ok, f"guardada={guardada} restaurada={restaurada} etiqueta={etiqueta!r}"
    finally:
        carpeta.cleanup()
        config.cleanup()
        temp.cleanup()


def test_14():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)

        carpeta.cleanup()
        reabierta = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=reabierta: v._carga_completada and v.gestor.hilo is None)
        restaurada = reabierta.carpeta_seleccionada
        etiqueta = reabierta.etiqueta_carpeta.text()
        reabierta.close()
        _limpiar(reabierta)
        ok = (
            restaurada is None
            and etiqueta == MENSAJE_SIN_CARPETA
            and not os.path.isdir(guardada)
        )
        return ok, f"restaurada={restaurada} etiqueta={etiqueta!r}"
    finally:
        config.cleanup()
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        anterior = ventana.carpeta_seleccionada
        con_antes = _leer_json(ruta_config)
        with _dialogo_falso(""):
            ventana.seleccionar_carpeta()
        conservada = ventana.carpeta_seleccionada
        con_despues = _leer_json(ruta_config)
        ventana.close()
        _limpiar(ventana)
        ok = (
            conservada == anterior
            and con_antes == con_despues
            and con_despues.get(CLAVE_CARPETA) == anterior
        )
        return ok, f"conservada={conservada} igual={con_antes == con_despues}"
    finally:
        carpeta.cleanup()
        config.cleanup()
        temp.cleanup()


def test_16():
    temp, ruta_db = _crear_bd([])
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        inexistente = os.path.join(config.name, "no_existe")
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(inexistente):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        ventana.close()
        _limpiar(ventana)
        datos = _leer_json(ruta_config) if os.path.exists(ruta_config) else None
        ok = guardada is None and (datos is None or CLAVE_CARPETA not in datos)
        return ok, f"guardada={guardada} existe={os.path.exists(ruta_config)}"
    finally:
        config.cleanup()
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    ruta_config_env = os.path.abspath(os.environ[VARIABLE_ENTORNO])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        por_defecto = ventana._ruta_config is None
        ventana.close()
        _limpiar(ventana)

        reabierta = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=reabierta: v._carga_completada and v.gestor.hilo is None)
        restaurada = reabierta.carpeta_seleccionada
        reabierta.close()
        _limpiar(reabierta)

        datos = _leer_json(ruta_config_env)
        ok = (
            por_defecto
            and guardada == os.path.abspath(carpeta.name)
            and restaurada == guardada
            and datos.get(CLAVE_CARPETA) == guardada
        )
        return (
            ok,
            f"por_defecto={por_defecto} guardada={guardada} "
            f"restaurada={restaurada} datos={datos}",
        )
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd([])
    carpeta = tempfile.TemporaryDirectory()
    config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(config.name, "configuracion.json")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        relativa = os.path.relpath(carpeta.name, os.getcwd())
        with _dialogo_falso(relativa):
            ventana.seleccionar_carpeta()
        guardada = ventana.carpeta_seleccionada
        datos = _leer_json(ruta_config)
        ventana.close()
        _limpiar(ventana)
        ok = (
            guardada == os.path.abspath(relativa)
            and os.path.isabs(guardada)
            and datos.get(CLAVE_CARPETA) == guardada
        )
        return ok, f"guardada={guardada} datos={datos}"
    finally:
        carpeta.cleanup()
        config.cleanup()
        temp.cleanup()


def test_19():
    carpeta = tempfile.TemporaryDirectory()
    env_tmp = tempfile.TemporaryDirectory()
    ruta_env = os.path.join(env_tmp.name, "configuracion.json")
    original = os.environ.get(VARIABLE_ENTORNO)
    try:
        os.environ[VARIABLE_ENTORNO] = ruta_env
        guardada = guardar_ultima_carpeta(carpeta.name)
        recuperada = obtener_ultima_carpeta()
        datos = _leer_json(ruta_env)
        ok = (
            guardada == os.path.abspath(carpeta.name)
            and recuperada == guardada
            and datos.get(CLAVE_CARPETA) == guardada
        )
        return ok, f"guardada={guardada} recuperada={recuperada} datos={datos}"
    finally:
        if original is None:
            os.environ.pop(VARIABLE_ENTORNO, None)
        else:
            os.environ[VARIABLE_ENTORNO] = original
        carpeta.cleanup()
        env_tmp.cleanup()


def test_20():
    original = os.environ.get(VARIABLE_ENTORNO)
    explicita = os.path.join("C:\\", "otra.json")
    try:
        os.environ.pop(VARIABLE_ENTORNO, None)
        por_defecto = _resolver_ruta_config(None)
        devuelta = _resolver_ruta_config(explicita)
        ok = por_defecto == ruta_configuracion() and devuelta == explicita
        return ok, f"por_defecto={por_defecto} devuelta={devuelta}"
    finally:
        if original is None:
            os.environ.pop(VARIABLE_ENTORNO, None)
        else:
            os.environ[VARIABLE_ENTORNO] = original


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
    with mock.patch.object(
        arbol_navegacion.ArbolNavegacion, "revelar_ruta", return_value=True
    ):
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
