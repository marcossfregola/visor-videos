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
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaLecturaCatalogoPaginada

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


class TareaLecturaPaginadaConHilo(TareaLecturaCatalogoPaginada):
    def __init__(self, limite, desplazamiento=0, texto=None, ruta_db=None):
        super().__init__(limite, desplazamiento, texto, ruta_db)
        self.identificador = None
        self.en_principal = None

    def _trabajo(self):
        self.identificador = threading.get_ident()
        self.en_principal = QThread.isMainThread()
        return super()._trabajo()


class Captura:
    def __init__(self):
        self.eventos = []
        self.resultado = None
        self.error = None
        self.ids = {}

    def al_inicio(self):
        self.eventos.append("inicio")
        self.ids["inicio"] = (threading.get_ident(), QThread.isMainThread())

    def al_resultado(self, valor):
        self.eventos.append("resultado")
        self.resultado = valor
        self.ids["resultado"] = (threading.get_ident(), QThread.isMainThread())

    def al_error(self, mensaje):
        self.eventos.append("error")
        self.error = mensaje
        self.ids["error"] = (threading.get_ident(), QThread.isMainThread())

    def al_finalizada(self):
        self.eventos.append("finalizada")
        self.ids["finalizada"] = (threading.get_ident(), QThread.isMainThread())


def correr(gestor, tarea, timeout_ms=6000):
    captura = Captura()
    gestor.tarea_iniciada.connect(captura.al_inicio)
    gestor.tarea_resultado.connect(captura.al_resultado)
    gestor.tarea_error.connect(captura.al_error)
    gestor.tarea_finalizada.connect(captura.al_finalizada)

    bucle = QEventLoop()
    flags = {"timeout": False}

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    gestor.tarea_finalizada.connect(fin)
    QTimer.singleShot(timeout_ms, por_si_acaso)

    ok = gestor.iniciar(tarea)
    if ok:
        bucle.exec()
    gestor.tarea_iniciada.disconnect(captura.al_inicio)
    gestor.tarea_resultado.disconnect(captura.al_resultado)
    gestor.tarea_error.disconnect(captura.al_error)
    gestor.tarea_finalizada.disconnect(captura.al_finalizada)
    gestor.tarea_finalizada.disconnect(fin)
    return captura, flags, ok


def _nombres(resultado):
    return [fila[0] for fila in resultado["videos"]]


def _rechazo_sincrono(**kwargs):
    llamadas = {"connect": 0}

    def _conectar(*args, **kw):
        llamadas["connect"] += 1
        raise AssertionError("sqlite3.connect no debe invocarse")

    original = sqlite3.connect
    sqlite3.connect = _conectar
    try:
        escanear_mod.listar_videos_paginado(**kwargs)
    except (TypeError, ValueError) as exc:
        return llamadas["connect"], type(exc).__name__
    finally:
        sqlite3.connect = original
    return llamadas["connect"], None


def test_01():
    modulos = [
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_lectura_paginada.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd([])
    try:
        resultado = escanear_mod.listar_videos_paginado(5, 0, None, ruta_db)
        ok = (
            resultado["videos"] == []
            and resultado["total"] == 0
            and resultado["limite"] == 5
            and resultado["desplazamiento"] == 0
            and set(resultado.keys()) == {"videos", "total", "limite", "desplazamiento"}
        )
        return ok, f"resultado={resultado}"
    finally:
        temp.cleanup()


def test_03():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(2, 0, None, ruta_db)
        ok = (
            _nombres(resultado) == nombres[:2]
            and resultado["total"] == 5
            and resultado["limite"] == 2
            and resultado["desplazamiento"] == 0
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_04():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(2, 2, None, ruta_db)
        ok = (
            _nombres(resultado) == ["v03.mp4", "v04.mp4"]
            and resultado["total"] == 5
            and resultado["desplazamiento"] == 2
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_05():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(2, 4, None, ruta_db)
        ok = (
            _nombres(resultado) == ["v05.mp4"]
            and resultado["total"] == 5
            and resultado["desplazamiento"] == 4
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_06():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(2, 10, None, ruta_db)
        ok = (
            _nombres(resultado) == []
            and resultado["total"] == 5
            and resultado["desplazamiento"] == 10
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_07():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(1, 0, None, ruta_db)
        total = resultado["total"]
        videos = _nombres(resultado)
        ok = (
            len(videos) == 1
            and videos == ["v01.mp4"]
            and total == 5
            and resultado["limite"] == 1
        )
        return ok, f"videos={videos} total={total}"
    finally:
        temp.cleanup()


def test_08():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 8)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        completo = escanear_mod.listar_videos(ruta_db)
        paginas = []
        desplazamiento = 0
        while True:
            pagina = escanear_mod.listar_videos_paginado(3, desplazamiento, None, ruta_db)
            paginas.append(pagina)
            if not pagina["videos"]:
                break
            desplazamiento += 3
        concatenado = []
        for pagina in paginas:
            concatenado.extend(pagina["videos"])
        ok = (
            concatenado == completo
            and len(concatenado) == 7
            and paginas[-1]["videos"] == []
            and paginas[0]["total"] == 7
        )
        return (
            ok,
            f"paginas={len(paginas)} filas_concatenadas={len(concatenado)} "
            f"completo={len(completo)}",
        )
    finally:
        temp.cleanup()


def test_09():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 8)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        completos = []
        desplazamiento = 0
        while True:
            pagina = escanear_mod.listar_videos_paginado(3, desplazamiento, None, ruta_db)
            if not pagina["videos"]:
                break
            completos.extend(_nombres(pagina))
            desplazamiento += 3
        ok = len(completos) == 7 and len(set(completos)) == 7
        return ok, f"cantidad={len(completos)} unicos={len(set(completos))}"
    finally:
        temp.cleanup()


def test_10():
    nombres = ["zeta.mp4", "beta.mp4", "alfa.mp4", "milo.avi", "delta.mp4", "kilo.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        esperado = [fila[0] for fila in escanear_mod.listar_videos(ruta_db)]
        paginas = []
        desplazamiento = 0
        while True:
            pagina = escanear_mod.listar_videos_paginado(2, desplazamiento, None, ruta_db)
            if not pagina["videos"]:
                break
            paginas.append(_nombres(pagina))
            desplazamiento += 2
        concatenado = [n for pagina in paginas for n in pagina]
        ok = (
            concatenado == esperado
            and concatenado == sorted(concatenado)
            and all(pagina == sorted(pagina) for pagina in paginas)
            and concatenado[0] == "alfa.mp4"
        )
        return ok, f"concatenado={concatenado} esperado={esperado}"
    finally:
        temp.cleanup()


def test_11():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(100, 0, None, ruta_db)
        ok = (
            resultado["total"] == 5
            and len(resultado["videos"]) == 5
            and resultado["total"] == len(escanear_mod.listar_videos(ruta_db))
        )
        return ok, f"total={resultado['total']} videos={len(resultado['videos'])}"
    finally:
        temp.cleanup()


def test_12():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi", "uvas.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(100, 0, "man", ruta_db)
        esperado = ["mango.mkv", "manzana.mp4"]
        ok = (
            _nombres(resultado) == esperado
            and resultado["total"] == 2
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_13():
    nombres = ["apolo.mp4", "apolo2.mp4", "beta.mkv", "gamma.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(100, 0, "xyzabc", ruta_db)
        ok = (
            resultado["videos"] == []
            and resultado["total"] == 0
        )
        return ok, f"videos={resultado['videos']} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_14():
    nombres = ["apolo.mp4", "apolo2.mp4", "beta.mkv", "gamma.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        resultado = escanear_mod.listar_videos_paginado(1, 0, "po", ruta_db)
        completo = escanear_mod.listar_videos_paginado(100, 0, "po", ruta_db)
        ok = (
            _nombres(resultado) == ["apolo.mp4"]
            and resultado["total"] == 2
            and len(completo["videos"]) == 2
            and completo["total"] == 2
        )
        return (
            ok,
            f"videos={_nombres(resultado)} total={resultado['total']} "
            f"completo={len(completo['videos'])}",
        )
    finally:
        temp.cleanup()


def test_15():
    nombres = ["el_50%.mp4", "l'apostrofe.mp4", "otro.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        con_porcentaje = escanear_mod.listar_videos_paginado(100, 0, "50%", ruta_db)
        con_apostrofe = escanear_mod.listar_videos_paginado(100, 0, "l'apo", ruta_db)
        ok = (
            _nombres(con_porcentaje) == ["el_50%.mp4"]
            and con_porcentaje["total"] == 1
            and _nombres(con_apostrofe) == ["l'apostrofe.mp4"]
            and con_apostrofe["total"] == 1
            and len(escanear_mod.listar_videos(ruta_db)) == 3
        )
        return (
            ok,
            f"porcentaje={_nombres(con_porcentaje)} "
            f"apostrofe={_nombres(con_apostrofe)}",
        )
    finally:
        temp.cleanup()


def test_16():
    filas = [
        ("con_null.mp4", "r", ".mp4", "f", None, None, None, None, None),
        ("con_datos.mp4", "r", ".mp4", "f", 2.5, 640, 360, "h264", 4),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        resultado = escanear_mod.listar_videos_paginado(100, 0, None, ruta_db)
        por_nombre = {fila[0]: fila for fila in resultado["videos"]}
        con_null = por_nombre.get("con_null.mp4")
        con_datos = por_nombre.get("con_datos.mp4")
        ok = (
            con_null == ("con_null.mp4", None, None, None, None, None, None)
            and con_datos == ("con_datos.mp4", 2.5, 640, 360, "h264", 4, None)
            and resultado["total"] == 2
        )
        return ok, f"con_null={con_null} con_datos={con_datos}"
    finally:
        temp.cleanup()


def test_17():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 8)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        esperado = escanear_mod.listar_videos_paginado(3, 2, "v", ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(3, 2, "v", ruta_db))
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


def test_18():
    id_main = threading.get_ident()
    nombres = [f"v{i:02d}.mp4" for i in range(1, 8)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        g = GestorTareas()
        tarea = TareaLecturaPaginadaConHilo(3, 1, "v", ruta_db)
        cap, fl, ok = correr(g, tarea)
        ok = (
            ok
            and not fl["timeout"]
            and tarea.identificador is not None
            and tarea.identificador != id_main
            and tarea.en_principal is False
            and cap.resultado is not None
            and set(cap.ids) == {"inicio", "resultado", "finalizada"}
            and all(py == id_main and qt for py, qt in cap.ids.values())
        )
        return (
            ok,
            f"main={id_main} worker={tarea.identificador} "
            f"en_principal={tarea.en_principal}",
        )
    finally:
        temp.cleanup()


def test_19():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
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
            tarea = TareaLecturaPaginadaConHilo(5, 0, None, ruta_db)
            cap, fl, ok = correr(g, tarea)
        finally:
            sqlite3.connect = original

        conn = datos.get("conn")
        try:
            conn.execute("SELECT 1")
            cerrada = False
        except sqlite3.ProgrammingError:
            cerrada = True
        esperado = {
            "videos": [("a.mp4", 1.0, 1, 1, "c", 0, None)],
            "total": 1,
            "limite": 5,
            "desplazamiento": 0,
        }
        ok = (
            ok
            and not fl["timeout"]
            and tarea.identificador not in (None, id_main)
            and tarea.en_principal is False
            and datos.get("hilo") == tarea.identificador
            and datos.get("hilo") != id_main
            and cerrada
            and not hasattr(tarea, "_conexion")
            and cap.resultado == esperado
        )
        return (
            ok,
            f"main={id_main} worker={tarea.identificador} "
            f"connect_hilo={datos.get('hilo')} cerrada={cerrada}",
        )
    finally:
        temp.cleanup()


def test_20():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(2, 0, None, ruta_db))
        fin = cap.eventos.count("finalizada")
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and fin == 1
        )
        return ok, f"eventos={cap.eventos} finalizadas={fin}"
    finally:
        temp.cleanup()


def test_21():
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(2, 0, None, ruta_db))
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


def test_22():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "no_existe.db")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
        try:
            escanear_mod.listar_videos_paginado(5, 0, None, ruta_db)
            sincrono_error = None
        except FileNotFoundError:
            sincrono_error = "FileNotFoundError"
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and not os.path.exists(ruta_db)
            and sincrono_error == "FileNotFoundError"
        )
        return (
            ok,
            f"error={cap.error!r} archivo_creado={os.path.exists(ruta_db)} "
            f"sincrono={sincrono_error}",
        )
    finally:
        temp.cleanup()


def test_23():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "padre_inexistente", "no_existe.db")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and not os.path.exists(ruta_db)
            and not os.path.exists(os.path.join(temp.name, "padre_inexistente"))
        )
        return (
            ok,
            f"error={cap.error!r} padre_creado="
            f"{os.path.exists(os.path.join(temp.name, 'padre_inexistente'))}",
        )
    finally:
        temp.cleanup()


def test_24():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_db = os.path.join(temp.name, "corrupta.db")
        with open(ruta_db, "wb") as f:
            f.write(b"esto no es una base sqlite valida" * 50)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
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
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        casos = [
            ("entero_cero", 0, "ValueError"),
            ("entero_negativo", -1, "ValueError"),
            ("flotante", 1.5, "TypeError"),
            ("booleano", True, "TypeError"),
            ("texto", "5", "TypeError"),
            ("none", None, "TypeError"),
        ]
        ok = True
        detalle = []
        for etiqueta, valor, esperado in casos:
            llamadas, excepcion = _rechazo_sincrono(limite=valor, ruta_db=ruta_db)
            if llamadas != 0 or excepcion != esperado:
                ok = False
            detalle.append(f"{etiqueta}={excepcion}/conn={llamadas}")
        return ok, "; ".join(detalle)
    finally:
        temp.cleanup()


def test_26():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        casos = [
            ("entero_negativo", -1, "ValueError"),
            ("flotante", 1.5, "TypeError"),
            ("booleano", True, "TypeError"),
            ("texto", "0", "TypeError"),
            ("none", None, "TypeError"),
        ]
        ok = True
        detalle = []
        for etiqueta, valor, esperado in casos:
            llamadas, excepcion = _rechazo_sincrono(
                limite=5, desplazamiento=valor, ruta_db=ruta_db
            )
            if llamadas != 0 or excepcion != esperado:
                ok = False
            detalle.append(f"{etiqueta}={excepcion}/conn={llamadas}")
        return ok, "; ".join(detalle)
    finally:
        temp.cleanup()


def test_27():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        casos = [
            ("entero", 123, "TypeError"),
            ("flotante", 3.5, "TypeError"),
            ("booleano", True, "TypeError"),
            ("bytes", b"x", "TypeError"),
            ("lista", ["a"], "TypeError"),
        ]
        ok = True
        detalle = []
        for etiqueta, valor, esperado in casos:
            llamadas, excepcion = _rechazo_sincrono(
                limite=5, texto=valor, ruta_db=ruta_db
            )
            if llamadas != 0 or excepcion != esperado:
                ok = False
            detalle.append(f"{etiqueta}={excepcion}/conn={llamadas}")
        return ok, "; ".join(detalle)
    finally:
        temp.cleanup()


def test_28():
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
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(1, 0, None, ruta_db))
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


def test_29():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        llamadas = {"escaneo": 0}
        escaneo_tv_original = tv.escanear_videos
        escaneo_mod_original = escanear_mod.escanear_videos

        def _escaneo(*args, **kwargs):
            llamadas["escaneo"] += 1
            raise AssertionError("no debe escanearse")

        tv.escanear_videos = _escaneo
        escanear_mod.escanear_videos = _escaneo
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
        finally:
            tv.escanear_videos = escaneo_tv_original
            escanear_mod.escanear_videos = escaneo_mod_original
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado is not None
            and llamadas == {"escaneo": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_30():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        llamadas = {"ffprobe": 0}
        ffprobe_original = tv.obtener_datos_ffprobe

        def _ffprobe(*args, **kwargs):
            llamadas["ffprobe"] += 1
            raise AssertionError("no debe invocarse ffprobe")

        tv.obtener_datos_ffprobe = _ffprobe
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
        finally:
            tv.obtener_datos_ffprobe = ffprobe_original
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado is not None
            and llamadas == {"ffprobe": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_31():
    temp, ruta_db = _crear_bd([("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0)])
    try:
        llamadas = {"subprocess": 0}
        subprocess_original = escanear_mod.subprocess.run

        def _run(*args, **kwargs):
            llamadas["subprocess"] += 1
            raise AssertionError("no debe ejecutarse subproceso")

        escanear_mod.subprocess.run = _run
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(5, 0, None, ruta_db))
        finally:
            escanear_mod.subprocess.run = subprocess_original
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado is not None
            and llamadas == {"subprocess": 0}
        )
        return ok, f"llamadas={llamadas}"
    finally:
        temp.cleanup()


def test_32():
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
    nombres = [f"v{i:02d}.mp4" for i in range(1, 6)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaLecturaCatalogoPaginada(2, 1, "v", ruta_db))
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and cap.resultado is not None
        and antes == despues
    )
    return ok, f"datos_reales_sin_cambios={antes == despues}"


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
        test_30,
        test_31,
        test_32,
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
    print(f"TOTAL={aprobadas}/32")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
