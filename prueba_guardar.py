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
from escanear_videos import guardar_video
from prueba_escaneo import Captura, correr
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaGuardarVideo

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


def _datos(nombre, ruta="C:\\v\\a.mp4", extension=".mp4", fecha="2026-08-02T00:00:00",
           duracion=None, ancho=None, alto=None, codec=None, miniaturas=None):
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


class TareaGuardarConHilo(TareaGuardarVideo):
    def __init__(self, datos, ruta_db=None):
        super().__init__(datos, ruta_db)
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

    def commit(self):
        self._registro["commit"].append(threading.get_ident())
        return self._real.commit()

    def rollback(self):
        return self._real.rollback()

    def close(self):
        self._registro["close"].append(threading.get_ident())
        return self._real.close()


def test_01():
    modulos = [
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_guardar.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    datos = _datos("a.mp4", ruta="C:\\v\\a.mp4", fecha="2026-08-02T00:00:00",
                   duracion=3.5, ancho=640, alto=360, codec="h264", miniaturas=2)
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(datos, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute("SELECT * FROM videos").fetchall()
        finally:
            conn.close()
        esperado = (1, "a.mp4", "C:\\v\\a.mp4", ".mp4", "2026-08-02T00:00:00", 3.5, 640, 360, "h264", 2, None)
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == {"guardado": True, "nombre": "a.mp4"}
            and len(filas) == 1
            and filas[0] == esperado
        )
        return ok, f"filas={filas}"
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd([])
    try:
        datos1 = _datos("a.mp4", ruta="C:\\v\\a_v1.mp4", duracion=1.0, ancho=1, alto=1, codec="h264", miniaturas=0)
        g1 = GestorTareas()
        cap1, fl1, ok1 = correr(g1, TareaGuardarVideo(datos1, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            id_v1 = conn.execute("SELECT id FROM videos WHERE nombre = 'a.mp4'").fetchone()[0]
        finally:
            conn.close()

        datos2 = _datos("a.mp4", ruta="C:\\v\\a_v2.mp4", duracion=9.5, ancho=1920, alto=1080, codec="av1", miniaturas=3)
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(g2, TareaGuardarVideo(datos2, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute("SELECT * FROM videos").fetchall()
        finally:
            conn.close()
        esperado = (id_v1, "a.mp4", "C:\\v\\a_v2.mp4", ".mp4", "2026-08-02T00:00:00", 9.5, 1920, 1080, "av1", 3, None)
        ok = (
            ok1
            and ok2
            and not fl1["timeout"]
            and not fl2["timeout"]
            and cap1.resultado == {"guardado": True, "nombre": "a.mp4"}
            and cap2.resultado == {"guardado": True, "nombre": "a.mp4"}
            and len(filas) == 1
            and filas[0] == esperado
        )
        return ok, f"filas={filas} esperado={esperado}"
    finally:
        temp.cleanup()


def test_04():
    datos = _datos("full.mp4", ruta="C:\\full\\video.mp4", fecha="2026-08-02T12:00:00",
                   duracion=12.5, ancho=1280, alto=720, codec="hevc", miniaturas=5)
    temp, ruta_db = _crear_bd([])
    try:
        resultado = guardar_video(datos, ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            fila = conn.execute(
                "SELECT nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE nombre = ?",
                ("full.mp4",),
            ).fetchone()
        finally:
            conn.close()
        esperado = ("full.mp4", "C:\\full\\video.mp4", ".mp4", "2026-08-02T12:00:00", 12.5, 1280, 720, "hevc", 5)
        ok = (
            resultado == {"guardado": True, "nombre": "full.mp4"}
            and fila == esperado
        )
        return ok, f"resultado={resultado} fila={fila}"
    finally:
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd([])
    try:
        datos_null = {
            "nombre": "nulo.mp4",
            "ruta": "C:\\v\\nulo.mp4",
            "extension": ".mp4",
            "fecha_importacion": "f",
        }
        g1 = GestorTareas()
        cap1, fl1, ok1 = correr(g1, TareaGuardarVideo(datos_null, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            fila1 = conn.execute(
                "SELECT duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE nombre = 'nulo.mp4'"
            ).fetchone()
        finally:
            conn.close()

        datos_llenos = dict(datos_null)
        datos_llenos.update({
            "duracion_segundos": 4.0, "ancho": 2, "alto": 2, "codec_video": "x", "cantidad_miniaturas": 1,
        })
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(g2, TareaGuardarVideo(datos_llenos, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            fila2 = conn.execute(
                "SELECT duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE nombre = 'nulo.mp4'"
            ).fetchone()
            cuenta = conn.execute("SELECT COUNT(*) FROM videos WHERE nombre = 'nulo.mp4'").fetchone()[0]
        finally:
            conn.close()
        ok = (
            ok1
            and ok2
            and not fl1["timeout"]
            and not fl2["timeout"]
            and fila1 == (None, None, None, None, None)
            and fila2 == (4.0, 2, 2, "x", 1)
            and cuenta == 1
        )
        return ok, f"fila1={fila1} fila2={fila2} cuenta={cuenta}"
    finally:
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd([])
    try:
        id_main = threading.get_ident()
        g = GestorTareas()
        cap, fl, ok = correr(
            g,
            TareaGuardarVideo(
                _datos("a.mp4", ruta="C:\\v\\a.mp4", duracion=3.5, ancho=640, alto=360, codec="h264", miniaturas=2),
                ruta_db,
            ),
        )
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute("SELECT * FROM videos").fetchall()
        finally:
            conn.close()
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.resultado == {"guardado": True, "nombre": "a.mp4"}
            and len(filas) == 1
            and set(cap.ids) == {"inicio", "resultado", "finalizada"}
            and all(py == id_main and qt for py, qt in cap.ids.values())
        )
        return ok, f"filas={len(filas)} ids={cap.ids}"
    finally:
        temp.cleanup()


def test_07():
    temp, ruta_db = _crear_bd([])
    try:
        id_main = threading.get_ident()
        hilos = {"connect": [], "commit": [], "close": []}
        original_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **k: ConectorConHilo(original_connect(*a, **k), hilos)
        try:
            g = GestorTareas()
            tarea = TareaGuardarConHilo(_datos("a.mp4"), ruta_db)
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original_connect

        worker = tarea.identificador
        ok = (
            ok
            and not fl["timeout"]
            and worker not in (None, id_main)
            and tarea.en_principal is False
            and hilos["connect"] == [worker]
            and hilos["commit"] == [worker]
            and hilos["close"] == [worker]
            and not hasattr(tarea, "_conexion")
            and not hasattr(tarea, "conn")
            and not any(isinstance(v, sqlite3.Connection) for v in vars(tarea).values())
            and cap.resultado == {"guardado": True, "nombre": "a.mp4"}
        )
        return (
            ok,
            f"main={id_main} worker={worker} connect={hilos['connect']} "
            f"commit={hilos['commit']} close={hilos['close']}",
        )
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
        fin = cap.eventos.count("finalizada")
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and fin == 1
        )
        return ok, f"eventos={cap.eventos} finalizada={fin}"
    finally:
        temp.cleanup()


def test_09():
    filas = [("a.mp4", "C:\\v\\a.mp4", ".mp4", "f", 1.0, 1, 1, "c", 0)]
    temp, ruta_db = _crear_bd(filas)
    try:
        def _dump():
            conn = sqlite3.connect(ruta_db)
            try:
                return conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
            finally:
                conn.close()

        def _bytes():
            with open(ruta_db, "rb") as f:
                return f.read()

        antes = _dump()
        bytes_antes = _bytes()
        original_connect = sqlite3.connect
        se_llamo_commit = {"ok": False}

        class ConectorFallaCommit:
            def __init__(self, real):
                self._real = real

            def execute(self, *args, **kwargs):
                return self._real.execute(*args, **kwargs)

            def commit(self):
                se_llamo_commit["ok"] = True
                raise RuntimeError("fallo controlado en commit")

            def rollback(self):
                return self._real.rollback()

            def close(self):
                return self._real.close()

        sqlite3.connect = lambda *a, **k: ConectorFallaCommit(original_connect(*a, **k))
        try:
            g = GestorTareas()
            cap, fl, ok = correr(
                g,
                TareaGuardarVideo(
                    _datos("b.mp4", ruta="C:\\v\\b.mp4", duracion=2.0, ancho=2, alto=2, codec="h264", miniaturas=1),
                    ruta_db,
                ),
            )
        finally:
            sqlite3.connect = original_connect

        despues = _dump()
        bytes_despues = _bytes()
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "RuntimeError" in cap.error
            and "fallo controlado en commit" in cap.error
            and se_llamo_commit["ok"]
            and despues == antes
            and bytes_despues == bytes_antes
        )
        return (
            ok,
            f"commit_llamado={se_llamo_commit['ok']} filas_antes={len(antes)} "
            f"filas_despues={len(despues)} contenido_igual={despues == antes} bytes_iguales={bytes_despues == bytes_antes}",
        )
    finally:
        temp.cleanup()


def test_10():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
        ok1 = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and not os.path.exists(ruta_db)
        )
        ruta_db2 = os.path.join(temp.name, "padre_inexistente", "no_existe.db")
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(g2, TareaGuardarVideo(_datos("a.mp4"), ruta_db2))
        ok = (
            ok1
            and ok2
            and not fl2["timeout"]
            and cap2.eventos == ["inicio", "error", "finalizada"]
            and cap2.error is not None
            and "FileNotFoundError" in cap2.error
            and not os.path.exists(ruta_db2)
        )
        return ok, f"e1={cap.error!r} e2={cap2.error!r} creado={os.path.exists(ruta_db)}"
    finally:
        temp.cleanup()


def test_11():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "corrupta.db")
        with open(ruta_db, "wb") as f:
            f.write(b"basura no sqlite" * 40)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
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


def test_12():
    temp, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
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


def test_13():
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
            cap, fl, ok = correr(g, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
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
            and cap.resultado == {"guardado": True, "nombre": "a.mp4"}
            and llamadas == {"escaneo": 0, "ffprobe": 0, "ffmpeg": 0, "subprocess": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_14():
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
        cap, fl, ok = correr(g, TareaGuardarVideo(_datos("x.mp4"), ruta_db))
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and cap.resultado == {"guardado": True, "nombre": "x.mp4"}
        and antes == despues
    )
    return ok, f"datos_reales_sin_cambios={antes == despues}"


def test_15():
    temp, ruta_db = _crear_bd([])
    try:
        datos = _datos("a.mp4", ruta="C:\\orig\\a.mp4", duracion=1.5, ancho=1, alto=1, codec="h264", miniaturas=0)
        tarea = TareaGuardarVideo(datos, ruta_db)
        datos["nombre"] = "modificado.mp4"
        datos["ruta"] = "C:\\mutado\\a.mp4"
        datos["duracion_segundos"] = 999.0
        g = GestorTareas()
        cap, fl, ok = correr(g, tarea)
        conn = sqlite3.connect(ruta_db)
        try:
            fila = conn.execute(
                "SELECT nombre, ruta, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos"
            ).fetchone()
        finally:
            conn.close()
        esperado = ("a.mp4", "C:\\orig\\a.mp4", 1.5, 1, 1, "h264", 0)
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == {"guardado": True, "nombre": "a.mp4"}
            and fila == esperado
        )
        return ok, f"fila={fila} esperado={esperado}"
    finally:
        temp.cleanup()


def test_16():
    temp, ruta_db = _crear_bd([])
    try:
        def _dump():
            conn = sqlite3.connect(ruta_db)
            try:
                return conn.execute("SELECT * FROM videos").fetchall()
            finally:
                conn.close()

        antes = _dump()
        resultados = []
        for valor_invalido in (None, 7, "no-soy-un-dict"):
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaGuardarVideo(valor_invalido, ruta_db))
            resultados.append((cap, fl, ok))
        despues = _dump()
        ok = (
            all(not fl["timeout"] for _, fl, _ in resultados)
            and all(ok for _, _, ok in resultados)
            and all(
                cap.eventos == ["inicio", "error", "finalizada"]
                and cap.error is not None
                and "TypeError" in cap.error
                and "datos inválidos" in cap.error
                for cap, _, _ in resultados
            )
            and despues == antes
        )
        return ok, f"errores={[cap.error for cap, _, _ in resultados]} iguales={despues == antes}"
    finally:
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd([])
    try:
        def _dump():
            conn = sqlite3.connect(ruta_db)
            try:
                return conn.execute("SELECT * FROM videos").fetchall()
            finally:
                conn.close()

        antes = _dump()
        claves = ["nombre", "ruta", "extension", "fecha_importacion"]
        resultados = []
        for clave in claves:
            datos = _datos("a.mp4")
            del datos[clave]
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaGuardarVideo(datos, ruta_db))
            resultados.append((clave, cap, fl, ok))
        despues = _dump()
        ok = (
            all(not fl["timeout"] for _, _, fl, _ in resultados)
            and all(ok for _, _, _, ok in resultados)
            and all(
                cap.eventos == ["inicio", "error", "finalizada"]
                and cap.error is not None
                and "ValueError" in cap.error
                and clave in cap.error
                for clave, cap, _, _ in resultados
            )
            and despues == antes
        )
        return ok, f"errores={[(c, cap.error) for c, cap, _, _ in resultados]} iguales={despues == antes}"
    finally:
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd([])
    try:
        datos = {
            "nombre": "basico.mp4",
            "ruta": "C:\\v\\basico.mp4",
            "extension": ".mp4",
            "fecha_importacion": "f",
        }
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaGuardarVideo(datos, ruta_db))
        conn = sqlite3.connect(ruta_db)
        try:
            fila = conn.execute(
                "SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE nombre = 'basico.mp4'"
            ).fetchone()
        finally:
            conn.close()
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == {"guardado": True, "nombre": "basico.mp4"}
            and fila == ("basico.mp4", None, None, None, None, None)
        )
        return ok, f"fila={fila}"
    finally:
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([])
    try:
        g1 = GestorTareas()
        cap1, fl1, ok1 = correr(g1, TareaGuardarVideo(None, ruta_db))
        datos = _datos("a.mp4")
        del datos["ruta"]
        g2 = GestorTareas()
        cap2, fl2, ok2 = correr(g2, TareaGuardarVideo(datos, ruta_db))
        g3 = GestorTareas()
        cap3, fl3, ok3 = correr(g3, TareaGuardarVideo(_datos("a.mp4"), ruta_db))
        hilos_python = [
            t for t in threading.enumerate() if t is not threading.main_thread()
        ]
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        ok = (
            ok1
            and ok2
            and ok3
            and not fl1["timeout"]
            and not fl2["timeout"]
            and not fl3["timeout"]
            and cap1.eventos == ["inicio", "error", "finalizada"]
            and cap2.eventos == ["inicio", "error", "finalizada"]
            and cap3.eventos == ["inicio", "resultado", "finalizada"]
            and g1.estado == Estado.INACTIVO
            and g2.estado == Estado.INACTIVO
            and g3.estado == Estado.INACTIVO
            and g1.hilo is None
            and g2.hilo is None
            and g3.hilo is None
            and g1.tarea is None
            and g2.tarea is None
            and g3.tarea is None
            and len(hilos_python) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and not avisos
        )
        return ok, f"hilos={len(hilos_python)} gestores={len(_GESTORES_ACTIVOS)} avisos={len(avisos)}"
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
        test_16,
        test_17,
        test_18,
        test_19,
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
    print(f"TOTAL={aprobadas}/19")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
