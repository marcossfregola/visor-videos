import hashlib
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
from prueba_escaneo import Captura, correr
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaLecturaCatalogo

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


class TareaLecturaConHilo(TareaLecturaCatalogo):
    def __init__(self, ruta_db=None):
        super().__init__(ruta_db)
        self.identificador = None
        self.en_principal = None

    def _trabajo(self):
        self.identificador = threading.get_ident()
        self.en_principal = QThread.isMainThread()
        return super()._trabajo()


def test_01():
    modulos = [
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_lectura.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    filas = [
        ("zeta.mp4", "C:\\z\\zeta.mp4", ".mp4", "2026-08-02T00:00:00", 3.5, 320, 240, "h264", 1),
        ("alfa.mp4", "C:\\a\\alfa.mp4", ".mp4", "2026-08-02T00:00:00", 5.0, 640, 360, "h264", 2),
        ("milo.avi", "C:\\m\\milo.avi", ".avi", "2026-08-02T00:00:00", 1.0, 100, 100, "mjpeg", 0),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        esperado = escanear_mod.listar_videos(ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.error is None
            and cap.resultado == esperado
            and g.estado == Estado.INACTIVO
            and g.hilo is None
        )
        return (
            ok,
            f"resultado={cap.resultado} esperado={esperado} eventos={cap.eventos}",
        )
    finally:
        temp.cleanup()


def test_03():
    filas = [("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)]
    temp, ruta_db = _crear_bd(filas)
    try:
        id_main = threading.get_ident()
        datos = {}
        original = sqlite3.connect

        def _conectar(*args, **kwargs):
            conn = original(*args, **kwargs)
            datos["hilo"] = threading.get_ident()
            datos["conn"] = conn
            return conn

        sqlite3.connect = _conectar
        try:
            g = GestorTareas()
            tarea = TareaLecturaConHilo(ruta_db)
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original

        conn = datos.get("conn")
        try:
            conn.execute("SELECT 1")
            cerrada = False
        except sqlite3.ProgrammingError:
            cerrada = True
        ok = (
            ok
            and not fl["timeout"]
            and tarea.identificador not in (None, id_main)
            and tarea.en_principal is False
            and datos.get("hilo") == tarea.identificador
            and datos.get("hilo") != id_main
            and cerrada
            and not hasattr(tarea, "_conexion")
            and cap.resultado == [("a.mp4", 1.0, 1, 1, "c", 0, None)]
            and set(cap.ids) == {"inicio", "resultado", "finalizada"}
            and all(py == id_main and qt for py, qt in cap.ids.values())
        )
        return (
            ok,
            f"main={id_main} worker={tarea.identificador} "
            f"connect_hilo={datos.get('hilo')} cerrada={cerrada}",
        )
    finally:
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.resultado == []
            and cap.error is None
        )
        return ok, f"resultado={cap.resultado} eventos={cap.eventos}"
    finally:
        temp.cleanup()


def test_05():
    filas = [
        ("zeta.mp4", "r", ".mp4", "f", 3.0, 640, 360, "h264", 2),
        ("beta.mkv", "r", ".mkv", "f", 2.0, 320, 240, "h264", 0),
        ("alfa.mp4", "r", ".mp4", "f", 5.0, 640, 360, "h264", 1),
        ("gamma.avi", "r", ".avi", "f", 1.0, 100, 100, "mjpeg", 3),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        esperado = escanear_mod.listar_videos(ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        nombres = [fila[0] for fila in cap.resultado or []]
        ok = (
            ok
            and not fl["timeout"]
            and len(cap.resultado) == 4
            and cap.resultado == esperado
            and nombres == sorted(nombres)
            and nombres[0] == "alfa.mp4"
        )
        return ok, f"nombres={nombres}"
    finally:
        temp.cleanup()


def test_06():
    filas = [
        ("con_null.mp4", "r", ".mp4", "f", None, None, None, None, None),
        ("con_datos.mp4", "r", ".mp4", "f", 2.5, 640, 360, "h264", 4),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        por_nombre = {fila[0]: fila for fila in cap.resultado or []}
        con_null = por_nombre.get("con_null.mp4")
        con_datos = por_nombre.get("con_datos.mp4")
        ok = (
            ok
            and not fl["timeout"]
            and con_null == ("con_null.mp4", None, None, None, None, None, None)
            and con_datos == ("con_datos.mp4", 2.5, 640, 360, "h264", 4, None)
        )
        return ok, f"con_null={con_null} con_datos={con_datos}"
    finally:
        temp.cleanup()


def test_07():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and not os.path.exists(ruta_db)
        )
        return ok, f"error={cap.error!r} archivo_creado={os.path.exists(ruta_db)}"
    finally:
        temp.cleanup()


def test_08():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "corrupta.db")
        with open(ruta_db, "wb") as f:
            f.write(b"esto no es una base sqlite valida" * 50)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
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


def test_09():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        g1 = GestorTareas()
        cap1, fl1, ok1 = correr(g1, TareaLecturaCatalogo(ruta_db))
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(
            g2, TareaLecturaCatalogo(os.path.join(temp.name, "no_existe2.db"))
        )
        fin1 = cap1.eventos.count("finalizada")
        fin2 = cap2.eventos.count("finalizada")
        ok = (
            ok1
            and ok2
            and not fl1["timeout"]
            and not fl2["timeout"]
            and cap1.eventos == ["inicio", "resultado", "finalizada"]
            and cap2.eventos == ["inicio", "error", "finalizada"]
            and fin1 == 1
            and fin2 == 1
        )
        return ok, f"e1={cap1.eventos} e2={cap2.eventos}"
    finally:
        temp.cleanup()


def test_10():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        hilos_python = [
            t for t in threading.enumerate() if t is not threading.main_thread()
        ]
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        ok = (
            ok
            and not fl["timeout"]
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and len(hilos_python) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and not avisos
        )
        return (
            ok,
            f"estado={g.estado} hilos={len(hilos_python)} "
            f"gestores={len(_GESTORES_ACTIVOS)} avisos={len(avisos)}",
        )
    finally:
        temp.cleanup()


def test_11():
    filas = [
        ("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0),
        ("b.avi", "r", ".avi", "f", 2.0, 2, 2, "c", 1),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        def _contenido(ruta):
            with open(ruta, "rb") as f:
                datos = f.read()
            return hashlib.sha256(datos).hexdigest(), datos

        hash_antes, bytes_antes = _contenido(ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        hash_despues, bytes_despues = _contenido(ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            filas_ahora = conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
        finally:
            conn.close()
        ok = (
            ok
            and not fl["timeout"]
            and bytes_antes == bytes_despues
            and hash_antes == hash_despues
            and len(filas_ahora) == 2
        )
        return (
            ok,
            f"bytes_iguales={bytes_antes == bytes_despues} filas={len(filas_ahora)}",
        )
    finally:
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        llamadas = {"escaneo": 0, "ffprobe": 0, "subprocess": 0}
        escaneo_original = tv.escanear_videos
        ffprobe_original = tv.obtener_datos_ffprobe
        subprocess_original = escanear_mod.subprocess.run

        def _escaneo(*args, **kwargs):
            llamadas["escaneo"] += 1
            raise AssertionError("no debe escanearse")

        def _ffprobe(*args, **kwargs):
            llamadas["ffprobe"] += 1
            raise AssertionError("no debe invocarse ffprobe")

        def _run(*args, **kwargs):
            llamadas["subprocess"] += 1
            raise AssertionError("no debe ejecutarse subproceso")

        tv.escanear_videos = _escaneo
        tv.obtener_datos_ffprobe = _ffprobe
        escanear_mod.subprocess.run = _run
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        finally:
            tv.escanear_videos = escaneo_original
            tv.obtener_datos_ffprobe = ffprobe_original
            escanear_mod.subprocess.run = subprocess_original
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == [("a.mp4", 1.0, 1, 1, "c", 0, None)]
            and llamadas == {"escaneo": 0, "ffprobe": 0, "subprocess": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_13():
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
    temp, ruta_db = _crear_bd([("x.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and cap.resultado == [("x.mp4", 1.0, 1, 1, "c", 0, None)]
        and antes == despues
    )
    return ok, f"datos_reales_sin_cambios={antes == despues}"


def test_14():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "padre_inexistente", "no_existe.db")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogo(ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and not os.path.exists(ruta_db)
        )
        return ok, f"error={cap.error!r} archivo_creado={os.path.exists(ruta_db)}"
    finally:
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        with open(os.path.join(temp.name, "nota.txt"), "w", encoding="utf-8") as f:
            f.write("preexistente")
        ruta_corrupta = os.path.join(temp.name, "corrupta.db")
        with open(ruta_corrupta, "wb") as f:
            f.write(b"basura no sqlite" * 30)

        def _listado():
            return sorted(os.listdir(temp.name))

        antes = _listado()
        g1 = GestorTareas()
        cap1, fl1, ok1 = correr(g1, TareaLecturaCatalogo(ruta_db))
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(g2, TareaLecturaCatalogo(ruta_corrupta))
        g3 = GestorTareas()
        cap3, fl3, ok3 = correr(
            g3, TareaLecturaCatalogo(os.path.join(temp.name, "no_existe.db"))
        )
        despues = _listado()
        ok = (
            ok1
            and ok2
            and ok3
            and not fl1["timeout"]
            and not fl2["timeout"]
            and not fl3["timeout"]
            and cap1.eventos == ["inicio", "resultado", "finalizada"]
            and cap2.eventos == ["inicio", "error", "finalizada"]
            and cap3.eventos == ["inicio", "error", "finalizada"]
            and antes == despues
        )
        return ok, f"listado_antes={antes} listado_despues={despues}"
    finally:
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
    print(f"TOTAL={aprobadas}/15")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
