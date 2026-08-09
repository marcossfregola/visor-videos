import contextlib
import inspect
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEvent, QPointF, Qt, QThread
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    conectar_bd,
    eliminar_marcador,
    guardar_marcador,
    guardar_videos,
    listar_marcadores,
    listar_videos,
)
from tareas import GestorTareas
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


def _esperar(predicado, timeout_ms=10000, paso_ms=20):
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
    if ventana.gestor_marcadores is not None:
        ventana.gestor_marcadores.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _crear_bd_vieja(filas):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = sqlite3.connect(ruta_db)
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
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas) VALUES (?,?,?,?,?,?,?,?,?)",
        filas,
    )
    conn.commit()
    conn.close()
    return temp, ruta_db


def _registro(nombre, duracion=100.0):
    return {
        "nombre": nombre,
        "ruta": f"C:\\v\\{nombre}",
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 3,
        "tamano_bytes": 1000,
    }


def _crear_bd_con_videos(nombres):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    guardar_videos([_registro(n) for n in nombres], ruta_db)
    return temp, ruta_db


def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


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
        temp.cleanup()


def _crear_previews(carpeta, prefijo, cantidad):
    for indice in range(1, cantidad + 1):
        ruta = os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        imagen = QImage(80, 45, QImage.Format_RGB32)
        imagen.fill(QColor(30 + indice * 20, 60, 120))
        imagen.save(ruta, "JPEG")


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _mouse_press(widget, x):
    evento = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(float(x), 6.0),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, evento)


def _clic_derecho(widget, x=5):
    evento = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(float(x), 6.0),
        Qt.RightButton,
        Qt.RightButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, evento)


def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_marcadores_b42.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    filas = [("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)]
    temp, ruta_db = _crear_bd_vieja(filas)
    try:
        conn = conectar_bd(ruta_db)
        tablas = {
            f[0]
            for f in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        conn.close()
        ok_tabla = "marcadores_video" in tablas
        conn = conectar_bd(ruta_db)
        tablas2 = {
            f[0]
            for f in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indice = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_marcadores_video_video_id_tiempo'"
        ).fetchone()
        conn.close()
        ok_idempotente = tablas2 == tablas
        ok_indice = indice is not None
        videos = listar_videos(ruta_db)
        ok_intactos = videos == [("a.mp4", 1.0, 1, 1, "c", 0, None, "r", 1)]
    finally:
        temp.cleanup()
    return (
        ok_tabla and ok_idempotente and ok_indice and ok_intactos,
        f"tabla={ok_tabla} idempotente={ok_idempotente} indice={ok_indice} videos={videos}",
    )


def test_03():
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        id_b = _video_id(ruta_db, "b.mp4")
        id1 = guardar_marcador(id_a, 10.0, ruta_db)
        id2 = guardar_marcador(id_a, 30.0, ruta_db)
        id3 = guardar_marcador(id_a, 20.0, ruta_db)
        id4 = guardar_marcador(id_b, 10.0, ruta_db)
        ok_ids = all(isinstance(x, int) and x > 0 for x in (id1, id2, id3, id4))
        marcadores_a = listar_marcadores(id_a, ruta_db)
        ok_orden = [t for _, _, t in marcadores_a] == [10.0, 20.0, 30.0]
        ok_no_mezcla = [v for _, v, _ in marcadores_a] == [id_a, id_a, id_a]
        ok_mismo_tiempo = listar_marcadores(id_b, ruta_db) == [
            (id4, id_b, 10.0)
        ]
        ok_borrado = eliminar_marcador(id3, ruta_db) is True
        restantes_a = listar_marcadores(id_a, ruta_db)
        ok_restantes = [t for _, _, t in restantes_a] == [10.0, 30.0]
        ok_eliminar_inexistente = eliminar_marcador(999999, ruta_db) is False
    finally:
        temp.cleanup()
    return (
        ok_ids
        and ok_orden
        and ok_no_mezcla
        and ok_mismo_tiempo
        and ok_borrado
        and ok_restantes
        and ok_eliminar_inexistente,
        f"a={marcadores_a} restantes={restantes_a}",
    )


def test_04():
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        mid = guardar_marcador(id_a, 5.5, ruta_db)
        m = listar_marcadores(id_a, ruta_db)
        ok = m == [(mid, id_a, 5.5)]
    finally:
        temp.cleanup()
    return ok, f"m={m}"


def test_05():
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_antes = _video_id(ruta_db, "a.mp4")
        mid = guardar_marcador(id_antes, 12.0, ruta_db)
        guardar_videos(
            [
                {
                    **_registro("a.mp4", 120.0),
                    "fecha_importacion": "f2",
                    "duracion_segundos": 120.0,
                    "ancho": 1280,
                    "alto": 720,
                    "cantidad_miniaturas": 5,
                    "tamano_bytes": 2000,
                }
            ],
            ruta_db,
        )
        id_despues = _video_id(ruta_db, "a.mp4")
        marcadores = listar_marcadores(id_despues, ruta_db)
        ok = (
            id_antes == id_despues
            and marcadores == [(mid, id_antes, 12.0)]
        )
    finally:
        temp.cleanup()
    return ok, f"id={id_antes}/{id_despues} marcadores={marcadores}"


def test_06():
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        mid = guardar_marcador(id_a, 7.0, ruta_db)
        conn = sqlite3.connect(ruta_db)
        conn.execute("DELETE FROM videos WHERE nombre='a.mp4'")
        conn.commit()
        conn.close()
        marcadores = listar_marcadores(id_a, ruta_db)
        ok = marcadores == [(mid, id_a, 7.0)]
    finally:
        temp.cleanup()
    return ok, f"marcadores={marcadores}"


def test_07():
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_old = _video_id(ruta_db, "a.mp4")
        mid = guardar_marcador(id_old, 7.0, ruta_db)
        conn = sqlite3.connect(ruta_db)
        conn.execute("DELETE FROM videos WHERE nombre='a.mp4'")
        conn.commit()
        conn.close()
        guardar_videos([_registro("a.mp4", 90.0)], ruta_db)
        id_new = _video_id(ruta_db, "a.mp4")
        marcadores_new = listar_marcadores(id_new, ruta_db)
        marcadores_old = listar_marcadores(id_old, ruta_db)
        ok = (
            id_new != id_old
            and marcadores_new == []
            and marcadores_old == [(mid, id_old, 7.0)]
        )
    finally:
        temp.cleanup()
    return (
        ok,
        f"id_old={id_old} id_new={id_new} new={marcadores_new} old={marcadores_old}",
    )


def test_08():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            _crear_previews(carpeta_min, "a", 3)
            temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
            try:
                id_a = _video_id(ruta_db, "a.mp4")
                mid1 = guardar_marcador(id_a, 10.0, ruta_db)
                mid2 = guardar_marcador(id_a, 30.0, ruta_db)
                ventana = _abrir_ventana(ruta_db)
                try:
                    tarjeta = dict(ventana.tarjetas)["a.mp4"]
                    ok_video_id = tarjeta._video_id == id_a
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    ok_carga = _esperar(
                        lambda t=tarjeta: len(t._marcadores) == 2
                        and not ventana.gestor_marcadores.activo
                    )
                    tiempos = sorted(m["tiempo"] for m in tarjeta._marcadores)
                    ids = sorted(m["id"] for m in tarjeta._marcadores)
                    ok_datos = (
                        tiempos == [10.0, 30.0]
                        and ids == sorted([mid1, mid2])
                    )
                    QApplication.processEvents()
                    ok_pixmaps = all(
                        m["pixmap"] is not None for m in tarjeta._marcadores
                    )
                    ventana.close()
                    _limpiar(ventana)
                    ventana2 = _abrir_ventana(ruta_db)
                    try:
                        tarjeta2 = dict(ventana2.tarjetas)["a.mp4"]
                        tarjeta2.expandir()
                        _esperar(lambda: tarjeta2._franja.width() > 0)
                        _esperar(
                            lambda t=tarjeta2: len(t._marcadores) == 2
                            and not ventana2.gestor_marcadores.activo
                        )
                        ok_reaparece = sorted(
                            m["tiempo"] for m in tarjeta2._marcadores
                        ) == [10.0, 30.0]
                    finally:
                        ventana2.close()
                        _limpiar(ventana2)
                finally:
                    ventana.close()
                    _limpiar(ventana)
            finally:
                temp.cleanup()
            return (
                ok_video_id and ok_carga and ok_datos and ok_pixmaps and ok_reaparece,
                f"tiempos={tiempos} ids={ids} video_id={id_a} reaparece={ok_reaparece}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_09():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
            try:
                id_a = _video_id(ruta_db, "a.mp4")
                guardar_marcador(id_a, 15.0, ruta_db)
                ventana = _abrir_ventana(ruta_db)
                try:
                    tarjeta = dict(ventana.tarjetas)["a.mp4"]
                    _esperar(lambda t=tarjeta: len(t._marcadores) == 1)
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    QApplication.processEvents()
                    ok_sin_preview = (
                        len(tarjeta._marcadores) == 1
                        and tarjeta._marcadores[0]["pixmap"] is None
                    )
                    _crear_previews(carpeta_min, "a", 3)
                    tarjeta.actualizar_previews(
                        visor_videos.previews_de("a.mp4")
                    )
                    QApplication.processEvents()
                    ok_actualiza = (
                        tarjeta._marcadores[0]["pixmap"] is not None
                    )
                finally:
                    ventana.close()
                    _limpiar(ventana)
                    temp.cleanup()
                return (
                    ok_sin_preview and ok_actualiza,
                    f"sin_preview={ok_sin_preview} actualiza={ok_actualiza}",
                )
            finally:
                temp.cleanup()
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_10():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            _crear_previews(carpeta_min, "a", 3)
            temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
            try:
                id_a = _video_id(ruta_db, "a.mp4")
                ventana = _abrir_ventana(ruta_db)
                try:
                    tarjeta = dict(ventana.tarjetas)["a.mp4"]
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _mouse_press(superficie, ancho * 0.3)
                    QApplication.processEvents()
                    ok_visual = len(tarjeta._marcadores) == 1
                    ok_persiste = _esperar(
                        lambda t=tarjeta: t._marcadores
                        and t._marcadores[0]["id"] is not None
                        and not ventana.gestor_marcadores.activo
                    )
                    mid = tarjeta._marcadores[0]["id"]
                    ok_persistido = listar_marcadores(id_a, ruta_db) == [
                        (mid, id_a, 30.0)
                    ]
                    _clic_derecho(tarjeta._marcadores[0]["etiqueta"])
                    ok_borrado = _esperar(
                        lambda: listar_marcadores(id_a, ruta_db) == []
                        and not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    ok_visual_vacio = len(tarjeta._marcadores) == 0
                finally:
                    ventana.close()
                    _limpiar(ventana)
                ventana2 = _abrir_ventana(ruta_db)
                try:
                    tarjeta2 = dict(ventana2.tarjetas)["a.mp4"]
                    _esperar(
                        lambda t=tarjeta2: not ventana2.gestor_marcadores.activo
                        and not ventana2._cola_marcadores
                    )
                    ok_reabrir = tarjeta2._marcadores == []
                finally:
                    ventana2.close()
                    _limpiar(ventana2)
            finally:
                temp.cleanup()
            return (
                ok_visual
                and ok_persiste
                and ok_persistido
                and ok_borrado
                and ok_visual_vacio
                and ok_reabrir,
                f"mid={mid} persistido={ok_persistido} borrado={ok_borrado} reabrir={ok_reabrir}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_11():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            _crear_previews(carpeta_min, "a", 3)
            temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
            try:
                id_a = _video_id(ruta_db, "a.mp4")
                ventana = _abrir_ventana(ruta_db)
                try:
                    tarjeta = dict(ventana.tarjetas)["a.mp4"]
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _mouse_press(superficie, ancho * 0.5)
                    registro = tarjeta._marcadores[0]
                    _clic_derecho(registro["etiqueta"])
                    ok_vacio = _esperar(
                        lambda: listar_marcadores(id_a, ruta_db) == []
                        and not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores,
                        timeout_ms=15000,
                    )
                    filas = listar_marcadores(id_a, ruta_db)
                    ok = ok_vacio and filas == []
                finally:
                    ventana.close()
                    _limpiar(ventana)
                    temp.cleanup()
            finally:
                temp.cleanup()
            return ok, f"filas={filas} vacio={ok_vacio}"
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_12():
    codigo_ui = inspect.getsource(Tarjeta) + inspect.getsource(VisorVideos)
    ok_no_sql = (
        "sqlite3.connect" not in codigo_ui
        and "conectar_bd(" not in codigo_ui
        and "conn.execute" not in codigo_ui
    )
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    info = {}
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        guardar_marcador(id_a, 5.0, ruta_db)
        original = tv.listar_marcadores

        def _en_hilo(*args, **kwargs):
            info["hilo"] = threading.get_ident()
            info["principal"] = QThread.isMainThread()
            return original(*args, **kwargs)

        tv.listar_marcadores = _en_hilo
        gestor = GestorTareas()
        try:
            tarea = tv.TareaListarMarcadores(id_a, ruta_db)
            aceptada = gestor.iniciar(tarea)
            _esperar(lambda g=gestor: not g.activo and g.hilo is None)
            finalizada = not gestor.activo and gestor.hilo is None
        finally:
            tv.listar_marcadores = original
            gestor.cerrar()
        ok_hilo = (
            aceptada
            and finalizada
            and info.get("hilo") is not None
            and info.get("principal") is False
        )
    finally:
        temp.cleanup()
    return (
        ok_no_sql and ok_hilo,
        f"no_sql={ok_no_sql} aceptada={aceptada} info={info}",
    )


def _instalar_bloqueo_listar(desde=0):
    """Intercepta `listar_marcadores` para controlar cuándo se entrega el resultado.

    Las llamadas con índice >= `desde` se bloquean en un evento hasta que el
    hilo principal las libera. La consulta real se ejecuta recién en el
    momento de la liberación, de modo que el snapshot de SQLite queda
    atrasado respecto de los cambios locales hechos mientras tanto.
    Devuelve `(control, restaurar)`.
    """
    control = {
        "liberar": threading.Event(),
        "en_cola": threading.Event(),
        "llamadas": [],
        "resultados": [],
    }
    original = tv.listar_marcadores

    def _bloqueado(*args, **kwargs):
        control["llamadas"].append((args, kwargs))
        indice = len(control["llamadas"]) - 1
        if indice >= desde:
            control["en_cola"].set()
            if not control["liberar"].wait(timeout=20):
                raise TimeoutError(
                    "listar_marcadores bloqueada demasiado tiempo"
                )
        resultado = original(*args, **kwargs)
        control["resultados"].append(resultado)
        return resultado

    def _restaurar():
        tv.listar_marcadores = original

    tv.listar_marcadores = _bloqueado
    return control, _restaurar


def test_13():
    """Caso A: crear un marcador mientras la carga está pendiente.

    SQLite contiene 20 s. Se expande (carga en vuelo), el usuario crea 60 s
    y solo después se entrega el resultado antiguo de `cargar` con 20 s.
    """
    escanear_mod.configurar_cantidad_previews(3)
    try:
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            mid = guardar_marcador(id_a, 20.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                control, restaurar = _instalar_bloqueo_listar(desde=0)
                try:
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    _esperar(lambda: control["en_cola"].is_set())
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _mouse_press(superficie, ancho * 0.6)
                    QApplication.processEvents()
                    ok_pendiente = (
                        len(tarjeta._marcadores) == 1
                        and tarjeta._marcadores[0]["tiempo"] == 60.0
                        and tarjeta._marcadores[0]["id"] is None
                        and tarjeta._marcadores[0]["eliminada"] is False
                    )
                    ok_cola = any(
                        op.get("tipo") == "crear"
                        and op.get("tiempo") == 60.0
                        for op in ventana._cola_marcadores
                    )
                    control["liberar"].set()
                    ok_merge = _esperar(
                        lambda t=tarjeta: len(t._marcadores) == 2
                    )
                    tiempos = sorted(
                        m["tiempo"] for m in tarjeta._marcadores
                    )
                    m60 = next(
                        m for m in tarjeta._marcadores
                        if m["tiempo"] == 60.0
                    )
                    ok_conserva = (
                        tiempos == [20.0, 60.0]
                        and m60["id"] is None
                        and not any(
                            m["eliminada"] for m in tarjeta._marcadores
                        )
                    )
                    ok_drena = _esperar(
                        lambda: not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    m20 = next(
                        m for m in tarjeta._marcadores
                        if m["tiempo"] == 20.0
                    )
                    ok_final = (
                        m20["id"] == mid
                        and m60["id"] is not None
                        and not m60["eliminada"]
                    )
                    filas = listar_marcadores(id_a, ruta_db)
                    ok_sqlite = (
                        sorted(t for _, _, t in filas) == [20.0, 60.0]
                        and {i for i, _, _ in filas} == {mid, m60["id"]}
                    )
                finally:
                    restaurar()
            finally:
                ventana.close()
                _limpiar(ventana)
        finally:
            temp.cleanup()
        return (
            ok_pendiente and ok_cola and ok_merge and ok_conserva
            and ok_drena and ok_final and ok_sqlite,
            f"pendiente={ok_pendiente} cola={ok_cola} merge={ok_merge} "
            f"conserva={ok_conserva} drena={ok_drena} final={ok_final} "
            f"sqlite={ok_sqlite} filas={filas}",
        )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_14():
    """Caso B: marcador local exactamente coincidente con uno persistido.

    SQLite ya contiene 20 s. Antes de que termine `cargar`, el usuario crea
    un marcador en el mismo instante. No deben quedar dos equivalentes ni
    generarse una segunda fila persistente; se conserva el `marcador_id`.
    """
    escanear_mod.configurar_cantidad_previews(3)
    try:
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            mid = guardar_marcador(id_a, 20.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                control, restaurar = _instalar_bloqueo_listar(desde=0)
                try:
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    _esperar(lambda: control["en_cola"].is_set())
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _mouse_press(superficie, ancho * 0.2)
                    QApplication.processEvents()
                    ok_creado = (
                        len(tarjeta._marcadores) == 1
                        and tarjeta._marcadores[0]["id"] is None
                    )
                    ok_crear_en_cola = any(
                        op.get("tipo") == "crear"
                        for op in ventana._cola_marcadores
                    )
                    control["liberar"].set()
                    ok_drena = _esperar(
                        lambda: not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    ok_uno = len(tarjeta._marcadores) == 1
                    m = (
                        tarjeta._marcadores[0]
                        if tarjeta._marcadores
                        else {}
                    )
                    ok_id = m.get("id") == mid
                    filas = listar_marcadores(id_a, ruta_db)
                    ok_sqlite = filas == [(mid, id_a, 20.0)]
                finally:
                    restaurar()
            finally:
                ventana.close()
                _limpiar(ventana)
        finally:
            temp.cleanup()
        return (
            ok_creado and ok_crear_en_cola and ok_drena
            and ok_uno and ok_id and ok_sqlite,
            f"creado={ok_creado} crear_cola={ok_crear_en_cola} "
            f"drena={ok_drena} uno={ok_uno} id={ok_id} "
            f"sqlite={ok_sqlite} filas={filas}",
        )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_15():
    """Caso B (tolerancia): marcador local dentro de la tolerancia, no exacto.

    SQLite contiene 20 s. El usuario crea un marcador a menos de la
    tolerancia temporal de ese instante (pero no igual). Debe deduplicarse
    contra la fila persistida y conservarse el `marcador_id`.
    """
    escanear_mod.configurar_cantidad_previews(3)
    try:
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            mid = guardar_marcador(id_a, 20.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                control, restaurar = _instalar_bloqueo_listar(desde=0)
                try:
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    _esperar(lambda: control["en_cola"].is_set())
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    tolerancia = (
                        tarjeta._duracion / ancho * 0.5
                        if ancho > 0
                        else 0.0
                    )
                    objetivo = 20.0 + tolerancia * 0.5
                    _mouse_press(
                        superficie,
                        ancho * objetivo / tarjeta._duracion,
                    )
                    QApplication.processEvents()
                    ok_creado = (
                        len(tarjeta._marcadores) == 1
                        and abs(
                            tarjeta._marcadores[0]["tiempo"] - objetivo
                        ) <= tolerancia
                        and tarjeta._marcadores[0]["id"] is None
                    )
                    control["liberar"].set()
                    ok_drena = _esperar(
                        lambda: not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    ok_uno = len(tarjeta._marcadores) == 1
                    m = (
                        tarjeta._marcadores[0]
                        if tarjeta._marcadores
                        else {}
                    )
                    ok_id = m.get("id") == mid
                    filas = listar_marcadores(id_a, ruta_db)
                    ok_sqlite = filas == [(mid, id_a, 20.0)]
                finally:
                    restaurar()
            finally:
                ventana.close()
                _limpiar(ventana)
        finally:
            temp.cleanup()
        return (
            ok_creado and ok_drena and ok_uno and ok_id and ok_sqlite,
            f"creado={ok_creado} objetivo={objetivo} drena={ok_drena} "
            f"uno={ok_uno} id={ok_id} sqlite={ok_sqlite} filas={filas}",
        )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_16():
    """Caso C: eliminar durante la carga (no debe resucitar el marcador).

    El usuario crea y elimina un marcador mientras `cargar` está en vuelo.
    El resultado antiguo no debe volver a mostrarlo ni dejar la fila
    persistida huérfana en SQLite.
    """
    escanear_mod.configurar_cantidad_previews(3)
    try:
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            mid = guardar_marcador(id_a, 20.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                control, restaurar = _instalar_bloqueo_listar(desde=0)
                try:
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    _esperar(lambda: control["en_cola"].is_set())
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _mouse_press(superficie, ancho * 0.2)
                    QApplication.processEvents()
                    _clic_derecho(superficie, ancho * 0.2)
                    QApplication.processEvents()
                    ok_vacio = tarjeta._marcadores == []
                    ok_sin_crear = not any(
                        op.get("tipo") == "crear"
                        for op in ventana._cola_marcadores
                    )
                    control["liberar"].set()
                    ok_drena = _esperar(
                        lambda: not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    ok_no_resurge = tarjeta._marcadores == []
                    filas = listar_marcadores(id_a, ruta_db)
                    ok_sqlite = filas == []
                finally:
                    restaurar()
            finally:
                ventana.close()
                _limpiar(ventana)
        finally:
            temp.cleanup()
        return (
            ok_vacio and ok_sin_crear and ok_drena
            and ok_no_resurge and ok_sqlite,
            f"vacio={ok_vacio} sin_crear={ok_sin_crear} drena={ok_drena} "
            f"no_resurge={ok_no_resurge} sqlite={ok_sqlite} filas={filas}",
        )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


def test_17():
    """Caso D: reconsulta de recuperación tras un error de DELETE.

    Fallan los eliminar, se encola una nueva carga. La reconsulta no debe
    borrar un alta reciente todavía pendiente (60 s) ni duplicar marcadores.
    """
    escanear_mod.configurar_cantidad_previews(3)
    try:
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 10.0, ruta_db)
            guardar_marcador(id_a, 30.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                control, restaurar = _instalar_bloqueo_listar(desde=1)
                original_eliminar = tv.eliminar_marcador
                estado = {"llamadas": 0}

                def _eliminar_falla(*args, **kwargs):
                    estado["llamadas"] += 1
                    if estado["llamadas"] == 1:
                        raise RuntimeError("falla controlada")
                    return original_eliminar(*args, **kwargs)

                tv.eliminar_marcador = _eliminar_falla
                try:
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    ok_carga = _esperar(
                        lambda t=tarjeta: len(t._marcadores) == 2
                        and not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    superficie = tarjeta._franja
                    ancho = superficie.width()
                    _clic_derecho(superficie, ancho * 0.3)
                    ok_recarga = _esperar(
                        lambda: control["en_cola"].is_set()
                        and len(control["llamadas"]) == 2
                    )
                    _mouse_press(superficie, ancho * 0.6)
                    QApplication.processEvents()
                    m60 = next(
                        (
                            m for m in tarjeta._marcadores
                            if m["tiempo"] == 60.0
                        ),
                        None,
                    )
                    ok_pendiente = (
                        m60 is not None
                        and m60["id"] is None
                        and any(
                            op.get("tipo") == "crear"
                            and op.get("tiempo") == 60.0
                            for op in ventana._cola_marcadores
                        )
                    )
                    control["liberar"].set()
                    ok_drena = _esperar(
                        lambda: not ventana.gestor_marcadores.activo
                        and not ventana._cola_marcadores
                    )
                    tiempos = sorted(
                        m["tiempo"] for m in tarjeta._marcadores
                    )
                    ok_final = tiempos == [10.0, 30.0, 60.0]
                    filas = listar_marcadores(id_a, ruta_db)
                    ok_sqlite = (
                        sorted(t for _, _, t in filas)
                        == [10.0, 30.0, 60.0]
                        and len(filas) == len(set(i for i, _, _ in filas))
                    )
                finally:
                    tv.eliminar_marcador = original_eliminar
                    restaurar()
            finally:
                ventana.close()
                _limpiar(ventana)
        finally:
            temp.cleanup()
        return (
            ok_carga and ok_recarga and ok_pendiente
            and ok_drena and ok_final and ok_sqlite,
            f"carga={ok_carga} recarga={ok_recarga} pendiente={ok_pendiente} "
            f"drena={ok_drena} final={ok_final} sqlite={ok_sqlite} "
            f"tiempos={tiempos} filas={filas}",
        )
    finally:
        escanear_mod.configurar_cantidad_previews(3)


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
