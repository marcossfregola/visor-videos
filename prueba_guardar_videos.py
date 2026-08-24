import os
import py_compile
import sqlite3
import sys
import tempfile
import threading

from PySide6.QtCore import QThread, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
from escanear_videos import guardar_video, guardar_videos
from prueba_escaneo import Captura, correr
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaGuardarVideo, TareaGuardarVideos

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


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


def _datos(nombre, ruta=None, extension=".mp4", fecha="2026-08-02T00:00:00",
           duracion=None, ancho=None, alto=None, codec=None, miniaturas=None):
    if ruta is None:
        ruta = f"C:\\v\\{nombre}"
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": extension,
        "fecha_importacion": fecha,
        "duracion_segundos": duracion,
        "ancho": ancho,
        "alto": alto,
        "codec_video": codec,
        "cantidad_miniaturas": miniaturas,
    }


def _dump(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT id, nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes FROM videos ORDER BY nombre").fetchall()
    finally:
        conn.close()


def _bytes_de(ruta_db):
    with open(ruta_db, "rb") as f:
        return f.read()


def _generador_que_falla():
    yield _datos("a.mp4")
    raise RuntimeError("fallo del generador")


def _contador_conexiones():
    llamadas = {"connect": 0}
    original_connect = sqlite3.connect

    def _conectar(*a, **k):
        llamadas["connect"] += 1
        return original_connect(*a, **k)

    sqlite3.connect = _conectar
    return llamadas, original_connect


class TareaGuardarVideosConHilo(TareaGuardarVideos):
    def __init__(self, datos_videos, ruta_db=None):
        super().__init__(datos_videos, ruta_db)
        self.identificador = None
        self.en_principal = None

    def _trabajo(self):
        self.identificador = threading.get_ident()
        self.en_principal = QThread.isMainThread()
        return super()._trabajo()


class ConectorConHilo:
    def __init__(self, real, registro):
        self._real = real
        self._registro = registro
        self._registro["connect"].append(threading.get_ident())

    def execute(self, *args, **kwargs):
        return self._real.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._real.executemany(*args, **kwargs)

    def commit(self):
        self._registro["commit"].append(threading.get_ident())
        return self._real.commit()

    def rollback(self):
        self._registro["rollback"].append(threading.get_ident())
        return self._real.rollback()

    def close(self):
        self._registro["close"].append(threading.get_ident())
        return self._real.close()


class ConectorConFallo:
    def __init__(self, real, registro=None, falla_en_ejecucion=2):
        self._real = real
        self._registro = registro if registro is not None else {}
        self._falla_en = falla_en_ejecucion
        self._ejecuciones = 0

    def execute(self, *args, **kwargs):
        self._ejecuciones += 1
        if self._ejecuciones == self._falla_en:
            self._registro["fallo_activado"] = True
            raise RuntimeError("fallo controlado en el registro intermedio")
        return self._real.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._real.executemany(*args, **kwargs)

    def commit(self):
        return self._real.commit()

    def rollback(self):
        return self._real.rollback()

    def close(self):
        return self._real.close()


def test_01():
    temp, ruta_db = _crear_bd([])
    try:
        resultado = guardar_videos([], ruta_db)
        filas = _dump(ruta_db)
        ok = (
            (resultado.get("guardados") == 0 and resultado.get("nombres") == [] and isinstance(resultado.get("ids"), list))
            and filas == []
        )
        return ok, f"resultado={resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_02():
    temp, ruta_db = _crear_bd([])
    try:
        resultado = guardar_videos(
            [_datos("a.mp4", ruta="C:\\v\\a.mp4", duracion=3.5, ancho=640, alto=360, codec="h264", miniaturas=2)],
            ruta_db,
        )
        filas = _dump(ruta_db)
        esperado = [(1, "a.mp4", "C:\\v\\a.mp4", ".mp4", "2026-08-02T00:00:00", 3.5, 640, 360, "h264", 2, None)]
        ok = (
            (resultado.get("guardados") == 1 and resultado.get("nombres") == ["a.mp4"] and isinstance(resultado.get("ids"), list))
            and filas == esperado
        )
        return ok, f"resultado={resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd([])
    try:
        coleccion = [_datos("a.mp4"), _datos("b.mp4"), _datos("c.mp4")]
        resultado = guardar_videos(coleccion, ruta_db)
        nombres = [f[1] for f in _dump(ruta_db)]
        ok = (
            (resultado.get("guardados") == 3 and resultado.get("nombres") == ["a.mp4", "b.mp4", "c.mp4"] and isinstance(resultado.get("ids"), list))
            and nombres == ["a.mp4", "b.mp4", "c.mp4"]
        )
        return ok, f"resultado={resultado} nombres={nombres}"
    finally:
        temp.cleanup()


def test_04():
    filas = [
        ("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0),
        ("b.mp4", "C:\\v\\b.mp4", ".mp4", "f", 2.0, 2, 2, "d", 1),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        coleccion = [
            _datos("a.mp4", ruta="C:\\nueva\\a.mp4", duracion=9.0, ancho=90, alto=50, codec="x", miniaturas=7),
            _datos("b.mp4", ruta="C:\\nueva\\b.mp4", duracion=8.0, ancho=80, alto=40, codec="y", miniaturas=6),
        ]
        resultado = guardar_videos(coleccion, ruta_db)
        filas_db = _dump(ruta_db)
        esperado = [
            (1, "a.mp4", "C:\\nueva\\a.mp4", ".mp4", "2026-08-02T00:00:00", 9.0, 90, 50, "x", 7, None),
            (2, "b.mp4", "C:\\nueva\\b.mp4", ".mp4", "2026-08-02T00:00:00", 8.0, 80, 40, "y", 6, None),
        ]
        ok = (
            (resultado.get("guardados") == 2 and resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(resultado.get("ids"), list))
            and filas_db == esperado
        )
        return ok, f"resultado={resultado} filas={filas_db}"
    finally:
        temp.cleanup()


def test_05():
    filas = [
        ("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        coleccion = [
            _datos("a.mp4", ruta="C:\\nueva\\a.mp4", duracion=5.5),
            _datos("b.mp4", ruta="C:\\nueva\\b.mp4", duracion=6.5),
        ]
        resultado = guardar_videos(coleccion, ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            filas_db = conn.execute(
                "SELECT nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos ORDER BY nombre"
            ).fetchall()
        finally:
            conn.close()
        esperado = [
            ("a.mp4", "C:\\nueva\\a.mp4", ".mp4", "2026-08-02T00:00:00", 5.5, None, None, None, None),
            ("b.mp4", "C:\\nueva\\b.mp4", ".mp4", "2026-08-02T00:00:00", 6.5, None, None, None, None),
        ]
        ok = (
            (resultado.get("guardados") == 2 and resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(resultado.get("ids"), list))
            and len(filas_db) == 2
            and filas_db == esperado
        )
        return ok, f"resultado={resultado} filas={filas_db}"
    finally:
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd([])
    try:
        datos = _datos("full.mp4", ruta="C:\\full\\video.mp4", fecha="2026-08-02T12:00:00",
                       duracion=12.5, ancho=1280, alto=720, codec="hevc", miniaturas=5)
        resultado = guardar_videos([datos], ruta_db)
        filas = _dump(ruta_db)
        esperado = [(1, "full.mp4", "C:\\full\\video.mp4", ".mp4", "2026-08-02T12:00:00", 12.5, 1280, 720, "hevc", 5, None)]
        ok = (
            (resultado.get("guardados") == 1 and resultado.get("nombres") == ["full.mp4"] and isinstance(resultado.get("ids"), list))
            and filas == esperado
        )
        return ok, f"resultado={resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd([])
    try:
        coleccion = [
            {"nombre": "nulo1.mp4", "ruta": "C:\\v\\nulo1.mp4", "extension": ".mp4", "fecha_importacion": "f"},
            {"nombre": "nulo2.mp4", "ruta": "C:\\v\\nulo2.mp4", "extension": ".mp4", "fecha_importacion": "g",
             "duracion_segundos": None, "ancho": None, "alto": None, "codec_video": None, "cantidad_miniaturas": None},
        ]
        resultado = guardar_videos(coleccion, ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            extras = conn.execute(
                "SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos ORDER BY nombre"
            ).fetchall()
        finally:
            conn.close()
        esperado = [
            ("nulo1.mp4", None, None, None, None, None),
            ("nulo2.mp4", None, None, None, None, None),
        ]
        ok = (
            (resultado.get("guardados") == 2 and resultado.get("nombres") == ["nulo1.mp4", "nulo2.mp4"] and isinstance(resultado.get("ids"), list))
            and extras == esperado
        )
        return ok, f"resultado={resultado} extras={extras}"
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd([])
    try:
        coleccion = [_datos("c.mp4"), _datos("a.mp4"), _datos("b.mp4")]
        resultado = guardar_videos(coleccion, ruta_db)
        nombres_bd = [f[1] for f in _dump(ruta_db)]
        ok = (
            (resultado.get("guardados") == 3 and resultado.get("nombres") == ["c.mp4", "a.mp4", "b.mp4"] and isinstance(resultado.get("ids"), list))
            and nombres_bd == ["a.mp4", "b.mp4", "c.mp4"]
        )
        return ok, f"resultado={resultado} nombres_bd={nombres_bd}"
    finally:
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd([])
    try:
        registro = {"connect": [], "commit": [], "rollback": [], "close": []}
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConHilo(original_connect(*a, **k), registro)
        try:
            resultado = guardar_videos([_datos("a.mp4"), _datos("b.mp4"), _datos("c.mp4")], ruta_db)
        finally:
            sqlite3.connect = original_connect
        ok = (
            (resultado.get("guardados") == 3 and resultado.get("nombres") == ["a.mp4", "b.mp4", "c.mp4"] and isinstance(resultado.get("ids"), list))
            and len(registro["connect"]) == 1
            and len(registro["commit"]) == 1
            and len(registro["rollback"]) == 0
            and len(registro["close"]) == 1
        )
        return (
            ok,
            f"resultado={resultado} connects={len(registro['connect'])} "
            f"commits={len(registro['commit'])} closes={len(registro['close'])}",
        )
    finally:
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd([])
    try:
        registro = {"connect": [], "commit": [], "rollback": [], "close": []}
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConHilo(original_connect(*a, **k), registro)
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaGuardarVideos([_datos("a.mp4"), _datos("b.mp4")], ruta_db))
        finally:
            sqlite3.connect = original_connect
        ok = (
            ok
            and not fl["timeout"]
            and (cap.resultado.get("guardados") == 2 and cap.resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(cap.resultado.get("ids"), list))
            and len(registro["connect"]) == 1
            and len(registro["commit"]) == 1
            and len(registro["rollback"]) == 0
            and len(registro["close"]) == 1
        )
        return (
            ok,
            f"resultado={cap.resultado} connects={len(registro['connect'])} "
            f"commits={len(registro['commit'])} closes={len(registro['close'])}",
        )
    finally:
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd([])
    try:
        id_main = threading.get_ident()
        registro = {"connect": [], "commit": [], "rollback": [], "close": []}
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConHilo(original_connect(*a, **k), registro)
        try:
            g = GestorTareas()
            tarea = TareaGuardarVideosConHilo([_datos("a.mp4"), _datos("b.mp4")], ruta_db)
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original_connect

        worker = tarea.identificador
        sin_conexion = not any(isinstance(v, sqlite3.Connection) for v in vars(tarea).values())
        ok = (
            ok
            and not fl["timeout"]
            and worker not in (None, id_main)
            and tarea.en_principal is False
            and registro["connect"] == [worker]
            and registro["commit"] == [worker]
            and registro["close"] == [worker]
            and registro["rollback"] == []
            and sin_conexion
            and not hasattr(tarea, "_conexion")
            and not hasattr(tarea, "conn")
            and (cap.resultado.get("guardados") == 2 and cap.resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(cap.resultado.get("ids"), list))
        )
        return (
            ok,
            f"main={id_main} worker={worker} connect={registro['connect']} "
            f"commit={registro['commit']} close={registro['close']} rollback={registro['rollback']}",
        )
    finally:
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd([])
    try:
        id_main = threading.get_ident()
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos([_datos("a.mp4")], ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and set(cap.ids) == {"inicio", "resultado", "finalizada"}
            and all(py == id_main and qt for py, qt in cap.ids.values())
            and (cap.resultado.get("guardados") == 1 and cap.resultado.get("nombres") == ["a.mp4"] and isinstance(cap.resultado.get("ids"), list))
        )
        return ok, f"ids={cap.ids} resultado={cap.resultado}"
    finally:
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd([])
    try:
        lista = [_datos("a.mp4", ruta="C:\\orig\\a.mp4"), _datos("b.mp4", ruta="C:\\orig\\b.mp4")]
        tarea = TareaGuardarVideos(lista, ruta_db)
        lista.append(_datos("c.mp4"))
        lista[0] = _datos("mutado.mp4")
        lista.clear()
        g = GestorTareas()
        cap, fl, ok = correr(g, tarea)
        nombres = [f[1] for f in _dump(ruta_db)]
        ok = (
            ok
            and not fl["timeout"]
            and (cap.resultado.get("guardados") == 2 and cap.resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(cap.resultado.get("ids"), list))
            and nombres == ["a.mp4", "b.mp4"]
        )
        return ok, f"resultado={cap.resultado} nombres={nombres}"
    finally:
        temp.cleanup()


def test_14():
    temp, ruta_db = _crear_bd([])
    try:
        d1 = _datos("a.mp4", ruta="C:\\orig\\a.mp4", duracion=1.5)
        d2 = _datos("b.mp4", ruta="C:\\orig\\b.mp4", duracion=2.5)
        tarea = TareaGuardarVideos([d1, d2], ruta_db)
        d1["nombre"] = "mutado1.mp4"
        d1["ruta"] = "C:\\mutado\\a.mp4"
        d1["duracion_segundos"] = 999.0
        d2["nombre"] = "mutado2.mp4"
        d2["ancho"] = 42
        g = GestorTareas()
        cap, fl, ok = correr(g, tarea)
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute(
                "SELECT nombre, ruta, duracion_segundos, ancho FROM videos ORDER BY nombre"
            ).fetchall()
        finally:
            conn.close()
        esperado = [
            ("a.mp4", "C:\\orig\\a.mp4", 1.5, None),
            ("b.mp4", "C:\\orig\\b.mp4", 2.5, None),
        ]
        ok = (
            ok
            and not fl["timeout"]
            and (cap.resultado.get("guardados") == 2 and cap.resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(cap.resultado.get("ids"), list))
            and filas == esperado
        )
        return ok, f"resultado={cap.resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd([])
    try:
        errores_sync = []
        for invalido in (None, 7):
            try:
                guardar_videos(invalido, ruta_db)
                errores_sync.append(None)
            except TypeError as exc:
                errores_sync.append(str(exc))
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos(None, ruta_db))
        filas = _dump(ruta_db)
        ok = (
            all(e is not None and "colección" in e for e in errores_sync)
            and len(errores_sync) == 2
            and ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.error is not None
            and "TypeError" in cap.error
            and "colección inválida" in cap.error
            and filas == []
        )
        return ok, f"errores_sync={errores_sync} error={cap.error!r} filas={filas}"
    finally:
        temp.cleanup()


def test_16():
    temp, ruta_db = _crear_bd([])
    try:
        errores_sync = []
        for texto in ("hola", b"hola"):
            try:
                guardar_videos(texto, ruta_db)
                errores_sync.append(None)
            except TypeError as exc:
                errores_sync.append(str(exc))
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos("hola", ruta_db))
        filas = _dump(ruta_db)
        ok = (
            all(e is not None and "colección" in e and "texto" in e for e in errores_sync)
            and len(errores_sync) == 2
            and ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.error is not None
            and "TypeError" in cap.error
            and "colección inválida" in cap.error
            and filas == []
        )
        return ok, f"errores_sync={errores_sync} error={cap.error!r} filas={filas}"
    finally:
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd([])
    try:
        llamadas = {"connect": 0}
        original_connect = sqlite3.connect

        def _conectar(*a, **k):
            llamadas["connect"] += 1
            return original_connect(*a, **k)

        sqlite3.connect = _conectar
        try:
            try:
                guardar_videos([_datos("a.mp4"), 7], ruta_db)
                error = None
            except TypeError as exc:
                error = str(exc)
        finally:
            sqlite3.connect = original_connect

        filas = _dump(ruta_db)
        ok = (
            error is not None
            and "diccionario" in error
            and llamadas["connect"] == 0
            and filas == []
        )
        return ok, f"error={error!r} connects={llamadas['connect']} filas={filas}"
    finally:
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd([])
    try:
        datos_mal = _datos("x.mp4")
        del datos_mal["ruta"]
        llamadas = {"connect": 0}
        original_connect = sqlite3.connect

        def _conectar(*a, **k):
            llamadas["connect"] += 1
            return original_connect(*a, **k)

        sqlite3.connect = _conectar
        try:
            try:
                guardar_videos([_datos("a.mp4"), datos_mal], ruta_db)
                error = None
            except ValueError as exc:
                error = str(exc)
        finally:
            sqlite3.connect = original_connect

        filas = _dump(ruta_db)
        ok = (
            error is not None
            and "falta la clave obligatoria" in error
            and "ruta" in error
            and llamadas["connect"] == 0
            and filas == []
        )
        return ok, f"error={error!r} connects={llamadas['connect']} filas={filas}"
    finally:
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([])
    try:
        registro = {}
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConFallo(original_connect(*a, **k), registro, falla_en_ejecucion=2)
        try:
            g = GestorTareas()
            cap, fl, ok = correr(
                g,
                TareaGuardarVideos([_datos("a.mp4"), _datos("b.mp4"), _datos("c.mp4")], ruta_db),
            )
        finally:
            sqlite3.connect = original_connect

        filas = _dump(ruta_db)
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "RuntimeError" in cap.error
            and "fallo controlado en el registro intermedio" in cap.error
            and registro.get("fallo_activado") is True
            and filas == []
        )
        return ok, f"error={cap.error!r} fallo={registro.get('fallo_activado')} filas={filas}"
    finally:
        temp.cleanup()


def test_20():
    filas = [
        ("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        antes = _dump(ruta_db)
        bytes_antes = _bytes_de(ruta_db)
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConFallo(original_connect(*a, **k), {}, falla_en_ejecucion=2)
        try:
            g = GestorTareas()
            cap, fl, ok = correr(
                g,
                TareaGuardarVideos(
                    [
                        _datos("a.mp4", ruta="C:\\nueva\\a.mp4", duracion=9.9),
                        _datos("b.mp4"),
                        _datos("c.mp4"),
                    ],
                    ruta_db,
                ),
            )
        finally:
            sqlite3.connect = original_connect

        despues = _dump(ruta_db)
        bytes_despues = _bytes_de(ruta_db)
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and despues == antes
            and bytes_despues == bytes_antes
        )
        return (
            ok,
            f"filas_antes={len(antes)} filas_despues={len(despues)} "
            f"contenido_igual={despues == antes} bytes_iguales={bytes_despues == bytes_antes}",
        )
    finally:
        temp.cleanup()


def test_21():
    filas = [
        ("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0),
        ("b.mp4", "C:\\v\\b.mp4", ".mp4", "f", 2.0, 2, 2, "d", 1),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConFallo(original_connect(*a, **k), {}, falla_en_ejecucion=2)
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaGuardarVideos([_datos("c.mp4"), _datos("d.mp4")], ruta_db))
        finally:
            sqlite3.connect = original_connect

        nombres = [f[1] for f in _dump(ruta_db)]
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and nombres == ["a.mp4", "b.mp4"]
        )
        return ok, f"error={cap.error!r} nombres={nombres}"
    finally:
        temp.cleanup()


def test_22():
    filas = [
        ("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConFallo(original_connect(*a, **k), {}, falla_en_ejecucion=2)
        try:
            g = GestorTareas()
            cap, fl, ok = correr(
                g,
                TareaGuardarVideos(
                    [
                        _datos("a.mp4", ruta="C:\\cambiada\\a.mp4", duracion=9.9),
                        _datos("b.mp4"),
                    ],
                    ruta_db,
                ),
            )
        finally:
            sqlite3.connect = original_connect

        filas = _dump(ruta_db)
        esperado = [(1, "a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0, None)]
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and filas == esperado
        )
        return ok, f"error={cap.error!r} filas={filas}"
    finally:
        temp.cleanup()


def test_23():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        try:
            guardar_videos([_datos("a.mp4")], ruta_db)
            e1 = None
        except FileNotFoundError as exc:
            e1 = str(exc)
        ruta_db2 = os.path.join(temp.name, "padre_inexistente", "no_existe.db")
        try:
            guardar_videos([_datos("a.mp4")], ruta_db2)
            e2 = None
        except FileNotFoundError as exc:
            e2 = str(exc)
        ok = (
            e1 is not None
            and "Base de datos no encontrada" in e1
            and not os.path.exists(ruta_db)
            and e2 is not None
            and "Base de datos no encontrada" in e2
            and not os.path.exists(ruta_db2)
        )
        return (
            ok,
            f"e1={e1!r} e2={e2!r} creado1={os.path.exists(ruta_db)} creado2={os.path.exists(ruta_db2)}",
        )
    finally:
        temp.cleanup()


def test_24():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "corrupta.db")
        with open(ruta_db, "wb") as f:
            f.write(b"basura no sqlite" * 40)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos([_datos("a.mp4")], ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and ("DatabaseError" in cap.error or "OperationalError" in cap.error)
        )
        return ok, f"error={cap.error!r}"
    finally:
        temp.cleanup()


def test_25():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos([_datos("a.mp4"), _datos("b.mp4")], ruta_db))
        fin = cap.eventos.count("finalizada")
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and fin == 1
            and (cap.resultado.get("guardados") == 2 and cap.resultado.get("nombres") == ["a.mp4", "b.mp4"] and isinstance(cap.resultado.get("ids"), list))
        )
        return ok, f"eventos={cap.eventos} finalizada={fin} resultado={cap.resultado}"
    finally:
        temp.cleanup()


def test_26():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        tarea = TareaGuardarVideos([_datos("a.mp4")], ruta_db)
        cap, fl, ok = correr(g, tarea)
        hilos_python = [
            t for t in threading.enumerate() if t is not threading.main_thread()
        ]
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        sin_conexion = not any(isinstance(v, sqlite3.Connection) for v in vars(tarea).values())
        ok = (
            ok
            and not fl["timeout"]
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and len(hilos_python) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and not avisos
            and sin_conexion
        )
        return (
            ok,
            f"estado={g.estado} hilos={len(hilos_python)} gestores={len(_GESTORES_ACTIVOS)} "
            f"avisos={len(avisos)} conexion={sin_conexion}",
        )
    finally:
        temp.cleanup()


def test_27():
    temp, ruta_db = _crear_bd([])
    try:
        llamadas = {"escaneo": 0, "ffprobe": 0, "ffmpeg": 0, "subprocess": 0}
        originales = {
            "escaneo": escanear_mod.escanear_videos,
            "ffprobe": escanear_mod.obtener_datos_ffprobe,
            "miniaturas": escanear_mod.contar_miniaturas,
            "asegurar": escanear_mod.asegurar_miniatura,
            "generar": escanear_mod.generar_miniatura,
            "subprocess": escanear_mod.subprocess.run,
        }

        def _prohibido(clave):
            def _fn(*args, **kwargs):
                llamadas[clave] += 1
                raise AssertionError(f"no debe ejecutarse {clave}")
            return _fn

        escanear_mod.escanear_videos = _prohibido("escaneo")
        escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
        escanear_mod.contar_miniaturas = _prohibido("miniaturas")
        escanear_mod.asegurar_miniatura = _prohibido("asegurar")
        escanear_mod.generar_miniatura = _prohibido("generar")
        escanear_mod.subprocess.run = _prohibido("subprocess")
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaGuardarVideos([_datos("a.mp4")], ruta_db))
        finally:
            escanear_mod.escanear_videos = originales["escaneo"]
            escanear_mod.obtener_datos_ffprobe = originales["ffprobe"]
            escanear_mod.contar_miniaturas = originales["miniaturas"]
            escanear_mod.asegurar_miniatura = originales["asegurar"]
            escanear_mod.generar_miniatura = originales["generar"]
            escanear_mod.subprocess.run = originales["subprocess"]

        ok = (
            ok
            and not fl["timeout"]
            and (cap.resultado.get("guardados") == 1 and cap.resultado.get("nombres") == ["a.mp4"] and isinstance(cap.resultado.get("ids"), list))
            and llamadas == {"escaneo": 0, "ffprobe": 0, "ffmpeg": 0, "subprocess": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_28():
    miniaturas = ruta_carpeta_miniaturas()
    bd = ruta_biblioteca()
    videos = ruta_carpeta_videos()

    def estado_real():
        return (
            os.path.isfile(bd),
            os.path.getmtime(bd) if os.path.isfile(bd) else None,
            os.path.getsize(bd) if os.path.isfile(bd) else None,
            sorted(os.listdir(miniaturas)) if os.path.isdir(miniaturas) else None,
            sorted(os.listdir(videos)) if os.path.isdir(videos) else None,
        )

    antes = estado_real()
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideos([_datos("x.mp4")], ruta_db))
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and (cap.resultado.get("guardados") == 1 and cap.resultado.get("nombres") == ["x.mp4"] and isinstance(cap.resultado.get("ids"), list))
        and antes == despues
    )
    return ok, f"datos_reales_sin_cambios={antes == despues}"


def test_29():
    temp, ruta_db = _crear_bd([])
    try:
        resultado = guardar_video(
            _datos("a.mp4", ruta="C:\\v\\a.mp4", duracion=3.5, ancho=640, alto=360, codec="h264", miniaturas=2),
            ruta_db,
        )
        filas = _dump(ruta_db)
        esperado = [(1, "a.mp4", "C:\\v\\a.mp4", ".mp4", "2026-08-02T00:00:00", 3.5, 640, 360, "h264", 2, None)]
        ok = (
            (resultado.get("guardado") is True and resultado.get("nombre") == "a.mp4" and isinstance(resultado.get("video_id"), int))
            and filas == esperado
        )
        return ok, f"resultado={resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_30():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(
            g,
            TareaGuardarVideo(
                _datos("a.mp4", ruta="C:\\v\\a.mp4", duracion=1.5, ancho=2, alto=2, codec="x", miniaturas=1),
                ruta_db,
            ),
        )
        filas = _dump(ruta_db)
        esperado = [(1, "a.mp4", "C:\\v\\a.mp4", ".mp4", "2026-08-02T00:00:00", 1.5, 2, 2, "x", 1, None)]
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and (cap.resultado.get("guardado") is True and cap.resultado.get("nombre") == "a.mp4" and isinstance(cap.resultado.get("video_id"), int))
            and filas == esperado
        )
        return ok, f"resultado={cap.resultado} filas={filas}"
    finally:
        temp.cleanup()


def test_31():
    temp, ruta_db = _crear_bd([])
    try:
        try:
            tarea = TareaGuardarVideos(_generador_que_falla(), ruta_db)
            error_construccion = None
        except Exception as exc:
            error_construccion = f"{type(exc).__name__}: {exc}"
        llamadas, original = _contador_conexiones()
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original
        filas = _dump(ruta_db)
        ok = (
            error_construccion is None
            and ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.eventos.count("finalizada") == 1
            and cap.resultado is None
            and cap.error is not None
            and "colección inválida" in cap.error
            and "fallo del generador" in cap.error
            and llamadas["connect"] == 0
            and filas == []
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
        )
        return (
            ok,
            f"error_construccion={error_construccion} error={cap.error!r} "
            f"connects={llamadas['connect']} filas={filas}",
        )
    finally:
        temp.cleanup()


def test_32():
    temp, ruta_db = _crear_bd([])
    try:
        casos = [None, 7, "hola", b"hola", [_datos("a.mp4"), 7]]
        resultados = []
        for entrada in casos:
            try:
                tarea = TareaGuardarVideos(entrada, ruta_db)
                error_construccion = None
            except Exception as exc:
                error_construccion = f"{type(exc).__name__}: {exc}"
            llamadas, original = _contador_conexiones()
            try:
                g = GestorTareas()
                cap, fl, ok = correr(g, tarea)
            finally:
                sqlite3.connect = original
            filas = _dump(ruta_db)
            resultados.append(
                (
                    error_construccion is None,
                    ok,
                    not fl["timeout"],
                    cap.eventos == ["inicio", "error", "finalizada"],
                    cap.eventos.count("finalizada") == 1,
                    cap.resultado is None,
                    cap.error is not None and "colección inválida" in cap.error,
                    llamadas["connect"] == 0,
                    filas == [],
                    g.estado == Estado.INACTIVO and g.hilo is None and g.tarea is None,
                )
            )
        ok = all(all(r) for r in resultados)
        return ok, f"casos={len(resultados)} todos_ok={ok} detalle={resultados}"
    finally:
        temp.cleanup()


def test_33():
    temp, ruta_db = _crear_bd([])
    try:
        datos_mal = _datos("x.mp4")
        del datos_mal["ruta"]
        try:
            tarea = TareaGuardarVideos([_datos("a.mp4"), datos_mal], ruta_db)
            error_construccion = None
        except Exception as exc:
            error_construccion = f"{type(exc).__name__}: {exc}"
        llamadas, original = _contador_conexiones()
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original
        filas = _dump(ruta_db)
        ok = (
            error_construccion is None
            and ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.eventos.count("finalizada") == 1
            and cap.resultado is None
            and cap.error is not None
            and "falta la clave obligatoria" in cap.error
            and "ruta" in cap.error
            and llamadas["connect"] == 0
            and filas == []
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
        )
        return (
            ok,
            f"error_construccion={error_construccion} error={cap.error!r} "
            f"connects={llamadas['connect']} filas={filas}",
        )
    finally:
        temp.cleanup()


def test_01_compilacion():
    modulos = [
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_guardar_videos.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01_compilacion,
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
    print(f"TOTAL={aprobadas}/34")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
