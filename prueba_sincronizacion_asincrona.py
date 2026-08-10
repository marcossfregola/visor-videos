import ast
import os
import py_compile
import shutil
import sqlite3
import sys
import tempfile
import threading

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaSincronizacionCatalogo

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)

OPERACIONES = (
    "detectar_diferencias",
    "preparar_plan_sincronizacion",
    "aplicar_incorporaciones",
    "eliminar_candidatos",
)

PROHIBIDOS_SQL = {
    "sqlite3",
    "connect",
    "execute",
    "cursor",
    "check_same_thread",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "CREATE",
    "PRAGMA",
}

PROHIBIDOS_FFMIN = {
    "ffprobe",
    "ffmpeg",
    "subprocess",
    "asegurar_miniatura",
    "asegurar_miniaturas",
    "contar_miniaturas",
    "generar_miniatura",
    "ruta_miniatura",
    "miniatura",
    "miniaturas",
    "conectar_bd",
    "guardar_video",
    "guardar_videos",
    "preparar_registros_basicos",
    "sincronizar_bd",
    "insertar_video",
    "actualizar_datos",
    "_coleccion_nombres",
    "_validar_plan_sincronizacion",
    "QApplication",
    "QLabel",
    "QMainWindow",
    "QWidget",
    "VisorVideos",
    "visor_videos",
    "visor",
}

PALABRAS_SQL_LITERAL = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "PRAGMA")


def _arbol(ruta):
    with open(ruta, encoding="utf-8") as f:
        return ast.parse(f.read(), ruta)


def _clase(arbol, nombre):
    for n in ast.walk(arbol):
        if isinstance(n, ast.ClassDef) and n.name == nombre:
            return n
    return None


def _identificadores(nodo):
    ids = set()
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Name):
            ids.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            ids.add(sub.attr)
    return ids


def _textos(nodo):
    return [
        sub.value
        for sub in ast.walk(nodo)
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
    ]


def _importados(arbol):
    conjunto = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            conjunto.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.Import):
            for a in nodo.names:
                conjunto.add(a.name.split(".")[0])
    return conjunto


def _orden_llamadas_escanear(nodo):
    orden = []

    def visitar(n):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "escanear_mod"
        ):
            orden.append(n.attr)
            return
        for hijo in ast.iter_child_nodes(n):
            visitar(hijo)

    visitar(nodo)
    return orden


def _crear_carpeta(nombres):
    temp = tempfile.TemporaryDirectory()
    carpeta = temp.name
    for nombre in nombres:
        with open(os.path.join(carpeta, nombre), "wb") as f:
            f.write(b"x")
    return temp, carpeta


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
                tamano_bytes INTEGER,
                mtime_ns INTEGER
            )
            """
        )
        for nombre in filas:
            conn.execute(
                "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?, ?, ?, ?)",
                (nombre, os.path.join("C:\\videos", nombre), os.path.splitext(nombre)[1], "f"),
            )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


def _nombres_bd(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return [fila[0] for fila in conn.execute("SELECT nombre FROM videos ORDER BY nombre")]
    finally:
        conn.close()


def _dump_bd(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
    finally:
        conn.close()


def _leer_bytes(ruta):
    with open(ruta, "rb") as f:
        return f.read()


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


def correr(gestor, tarea, timeout_ms=8000):
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


class TareaSincronizacionConHilo(TareaSincronizacionCatalogo):
    def __init__(self, carpeta, ruta_db=None):
        super().__init__(carpeta, ruta_db)
        self.id_hilo = None
        self.en_principal_trabajo = None

    def _trabajo(self):
        self.id_hilo = threading.get_ident()
        self.en_principal_trabajo = QThread.isMainThread()
        return super()._trabajo()


def _restaurar(originales):
    for clave, original in originales.items():
        setattr(escanear_mod, clave, original)


def test_01():
    modulos = [
        "tareas_videos.py",
        "prueba_plan_sincronizacion.py",
        "prueba_sincronizacion_asincrona.py",
        "escanear_videos.py",
        "tareas.py",
        "rutas.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    arbol_tareas = _arbol(os.path.join(ruta_raiz, "tareas_videos.py"))
    arbol_escaneo = _arbol(os.path.join(ruta_raiz, "escanear_videos.py"))
    arbol_visor = _arbol(os.path.join(ruta_raiz, "visor_videos.py"))
    arbol_prueba = _arbol(os.path.join(ruta_raiz, "prueba_sincronizacion_asincrona.py"))

    clase_tareas = _clase(arbol_tareas, "TareaSincronizacionCatalogo")
    bases = (
        {b.id for b in clase_tareas.bases if isinstance(b, ast.Name)}
        if clase_tareas is not None
        else set()
    )
    apariciones = sum(
        1
        for n in ast.walk(arbol_tareas)
        if isinstance(n, ast.ClassDef) and n.name == "TareaSincronizacionCatalogo"
    )
    ok = (
        clase_tareas is not None
        and "TareaBase" in bases
        and _clase(arbol_escaneo, "TareaSincronizacionCatalogo") is None
        and _clase(arbol_visor, "TareaSincronizacionCatalogo") is None
        and _clase(arbol_prueba, "TareaSincronizacionCatalogo") is None
        and apariciones == 1
    )
    return ok, f"definida_en_tareas={clase_tareas is not None} bases={sorted(bases)} apariciones={apariciones}"


def test_03():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    arbol_tareas = _arbol(os.path.join(ruta_raiz, "tareas_videos.py"))
    clase = _clase(arbol_tareas, "TareaSincronizacionCatalogo")
    ids = _identificadores(clase)
    textos = _textos(clase)
    presentes = sorted(PROHIBIDOS_SQL & ids)
    literales = [
        t for t in textos for p in PALABRAS_SQL_LITERAL if p in t.upper()
    ]
    ok = clase is not None and presentes == [] and literales == []
    return ok, f"ids_sql={presentes} literales_sql={literales}"


def test_04():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    arbol_tareas = _arbol(os.path.join(ruta_raiz, "tareas_videos.py"))
    clase = _clase(arbol_tareas, "TareaSincronizacionCatalogo")
    ids = _identificadores(clase)
    presentes = sorted(PROHIBIDOS_FFMIN & ids)
    ok = clase is not None and presentes == []
    return ok, f"prohibidos_ffmin_interfaz={presentes}"


def test_05():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    arbol_tareas = _arbol(os.path.join(ruta_raiz, "tareas_videos.py"))
    clase = _clase(arbol_tareas, "TareaSincronizacionCatalogo")
    metodo = next(
        (
            n
            for n in clase.body
            if isinstance(n, ast.FunctionDef) and n.name == "_trabajo"
        ),
        None,
    )
    orden = _orden_llamadas_escanear(metodo) if metodo is not None else []
    metodos = {
        n.name for n in ast.walk(clase) if isinstance(n, ast.FunctionDef)
    }
    redefinidas = sorted(set(OPERACIONES) & metodos)
    funcs_modulo = {
        n.name for n in ast.walk(arbol_tareas) if isinstance(n, ast.FunctionDef)
    }
    importados = _importados(arbol_tareas)
    importadas_directas = sorted(set(OPERACIONES) & importados)
    importa_modulo = any(
        isinstance(n, ast.Import)
        and any(a.name == "escanear_videos" for a in n.names)
        for n in ast.walk(arbol_tareas)
    )
    ok = (
        clase is not None
        and metodo is not None
        and orden == list(OPERACIONES)
        and metodos == {"__init__", "carpeta", "ruta_db", "_trabajo"}
        and redefinidas == []
        and not (set(OPERACIONES) & funcs_modulo)
        and importadas_directas == []
        and importa_modulo
    )
    return (
        ok,
        f"orden={orden} metodos={sorted(metodos)} redefinidas={redefinidas} "
        f"importadas_directas={importadas_directas} importa_modulo={importa_modulo}",
    )


def test_06():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    ruta = os.path.join(ruta_raiz, "tareas_videos.py")
    with open(ruta, encoding="utf-8") as f:
        texto = f.read()
    prohibidos = [
        "sqlite3",
        "check_same_thread",
        ".execute(",
        "CREATE TABLE",
        "INSERT INTO",
        "DELETE FROM",
        "UPDATE videos",
        "PRAGMA",
        "cursor",
    ]
    presentes = [p for p in prohibidos if p in texto]
    ok = presentes == []
    return ok, f"presentes={presentes}"


def test_07():
    carpeta = "C:\\videos"
    t = TareaSincronizacionCatalogo(carpeta, None)
    carpeta_cambiado = "C:\\otra"
    ruta_db_cambiado = "C:\\otra\\x.db"
    t2 = TareaSincronizacionCatalogo(carpeta_cambiado, ruta_db_cambiado)
    ok = (
        t.carpeta == "C:\\videos"
        and t.ruta_db is None
        and t.parent() is None
        and t._iniciada is False
        and t2.carpeta == carpeta_cambiado
        and t2.ruta_db == ruta_db_cambiado
        and isinstance(t.carpeta, str)
        and (t.ruta_db is None or isinstance(t.ruta_db, str))
    )
    return ok, f"t1={t.carpeta}/{t.ruta_db} t2={t2.carpeta}/{t2.ruta_db}"


def test_08():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.error is None
            and cap.resultado is not None
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and g not in _GESTORES_ACTIVOS
        )
        return ok, f"eventos={cap.eventos} estado={g.estado}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_09():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        resultado = cap.resultado or {}
        resumen = resultado.get("resumen") or {}
        incorporaciones = resultado.get("incorporaciones") or {}
        eliminaciones = resultado.get("eliminaciones") or {}
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and set(resultado.keys())
            == {"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}
            and set(resumen.keys())
            == {
                "nuevos",
                "ya_sincronizados",
                "incorporados",
                "eliminados",
                "candidatos_restantes",
            }
            and set(incorporaciones.keys())
            == {"incorporados", "nombres", "pendientes_eliminacion"}
            and set(eliminaciones.keys())
            == {"eliminados", "nombres", "incorporados", "restantes"}
        )
        return (
            ok,
            f"resultado_claves={sorted(resultado.keys())} resumen_claves={sorted(resumen.keys())}",
        )
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_10():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        resumen = cap.resultado["resumen"]
        nombres = _nombres_bd(ruta_db)
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and cap.resultado["diferencias"]["nuevos"] == ["a.mp4", "b.mkv"]
            and cap.resultado["plan"]["ya_sincronizados"] == []
            and cap.resultado["incorporaciones"]["incorporados"] == 2
            and cap.resultado["eliminaciones"]["eliminados"] == 0
            and resumen
            == {
                "nuevos": 2,
                "ya_sincronizados": 0,
                "incorporados": 2,
                "eliminados": 0,
                "candidatos_restantes": 0,
            }
            and nombres == ["a.mp4", "b.mkv"]
        )
        return ok, f"resumen={resumen} bd={nombres}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_11():
    temp_carpeta, carpeta = _crear_carpeta([])
    temp_bd, ruta_db = _crear_bd(["x.mp4", "y.avi"])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        resumen = cap.resultado["resumen"]
        nombres = _nombres_bd(ruta_db)
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and cap.resultado["diferencias"]["ausentes_del_disco"] == ["x.mp4", "y.avi"]
            and cap.resultado["plan"]["candidatos_a_eliminar"] == ["x.mp4", "y.avi"]
            and resumen
            == {
                "nuevos": 0,
                "ya_sincronizados": 0,
                "incorporados": 0,
                "eliminados": 2,
                "candidatos_restantes": 0,
            }
            and nombres == []
        )
        return ok, f"resumen={resumen} bd={nombres}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_12():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        resumen = cap.resultado["resumen"]
        nombres = _nombres_bd(ruta_db)
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and cap.resultado["plan"]["ya_sincronizados"] == ["a.mp4"]
            and cap.resultado["plan"]["candidatos_a_eliminar"] == ["c.avi"]
            and resumen
            == {
                "nuevos": 1,
                "ya_sincronizados": 1,
                "incorporados": 1,
                "eliminados": 1,
                "candidatos_restantes": 0,
            }
            and nombres == ["a.mp4", "b.mkv"]
        )
        return ok, f"resumen={resumen} bd={nombres}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_13():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        dump_antes = _dump_bd(ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        dump_despues = _dump_bd(ruta_db)
        a_antes = [f for f in dump_antes if f[1] == "a.mp4"][0]
        a_despues = [f for f in dump_despues if f[1] == "a.mp4"][0]
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and cap.resultado["plan"]["ya_sincronizados"] == ["a.mp4"]
            and a_despues == a_antes
        )
        return ok, f"ya={cap.resultado['plan']['ya_sincronizados']} a_intacta={a_despues == a_antes}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_14():
    nombres = ["a.mp4"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        bytes_antes = _leer_bytes(ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        bytes_despues = _leer_bytes(ruta_db)
        resumen = cap.resultado["resumen"]
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and resumen
            == {
                "nuevos": 0,
                "ya_sincronizados": 1,
                "incorporados": 0,
                "eliminados": 0,
                "candidatos_restantes": 0,
            }
            and bytes_despues == bytes_antes
        )
        return ok, f"resumen={resumen} bytes_iguales={bytes_despues == bytes_antes}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_15():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4"])
    temp = tempfile.TemporaryDirectory()
    ruta_db_inexistente = os.path.join(temp.name, "no_existe.db")
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db_inexistente))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and "Base de datos no encontrada" in cap.error
            and not os.path.isfile(ruta_db_inexistente)
            and g.estado == Estado.INACTIVO
        )
        return ok, f"error={cap.error} archivo_creado={os.path.isfile(ruta_db_inexistente)}"
    finally:
        temp_carpeta.cleanup()
        temp.cleanup()


def test_16():
    temp = tempfile.TemporaryDirectory()
    carpeta_inexistente = os.path.join(temp.name, "carpeta_que_no_existe")
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta_inexistente, ruta_db))
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is not None
            and "FileNotFoundError" in cap.error
            and "Carpeta no encontrada" in cap.error
            and _nombres_bd(ruta_db) == ["a.mp4"]
        )
        return ok, f"error={cap.error} bd={_nombres_bd(ruta_db)}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_17():
    temp = tempfile.TemporaryDirectory()
    ruta_corrupta = os.path.join(temp.name, "corrupta.db")
    try:
        with open(ruta_corrupta, "wb") as f:
            f.write(b"esto no es una base sqlite" * 10)
        bytes_antes = _leer_bytes(ruta_corrupta)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(ruta_carpeta_videos(), ruta_corrupta))
        bytes_despues = _leer_bytes(ruta_corrupta)
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is not None
            and "DatabaseError" in cap.error
            and bytes_despues == bytes_antes
        )
        return ok, f"error={cap.error} bytes_iguales={bytes_despues == bytes_antes}"
    finally:
        temp.cleanup()


def test_18():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    originales = {
        "detectar_diferencias": escanear_mod.detectar_diferencias,
        "preparar_plan_sincronizacion": escanear_mod.preparar_plan_sincronizacion,
        "aplicar_incorporaciones": escanear_mod.aplicar_incorporaciones,
        "eliminar_candidatos": escanear_mod.eliminar_candidatos,
    }
    llamadas = {"plan": 0, "incorporar": 0, "eliminar": 0}
    try:
        def _fallar(*args, **kwargs):
            raise RuntimeError("fallo en deteccion")

        def _contar(clave):
            def _fn(*args, **kwargs):
                llamadas[clave] += 1
                return {}
            return _fn

        escanear_mod.detectar_diferencias = _fallar
        escanear_mod.preparar_plan_sincronizacion = _contar("plan")
        escanear_mod.aplicar_incorporaciones = _contar("incorporar")
        escanear_mod.eliminar_candidatos = _contar("eliminar")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
    finally:
        _restaurar(originales)
    dump = _dump_bd(ruta_db)
    temp_carpeta.cleanup()
    temp_bd.cleanup()
    ok = (
        ok
        and not fl["timeout"]
        and cap.error is not None
        and "RuntimeError: fallo en deteccion" == cap.error
        and llamadas == {"plan": 0, "incorporar": 0, "eliminar": 0}
        and [fila[1] for fila in dump] == ["a.mp4"]
    )
    return ok, f"error={cap.error} llamadas={llamadas} dump={[f[1] for f in dump]}"


def test_19():
    temp_carpeta, carpeta = _crear_carpeta(["x.mp4", "y.mkv", "z.avi"])
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    dump_antes = _dump_bd(ruta_db)
    original_upsert = escanear_mod._upsert_video
    original_eliminar = escanear_mod.eliminar_candidatos
    upserts = []
    eliminaciones = []
    try:
        def _upsert_fallido(conn, datos):
            upserts.append(datos["nombre"])
            if len(upserts) == 2:
                raise RuntimeError("fallo simulado de escritura")
            return original_upsert(conn, datos)

        def _eliminar(*args, **kwargs):
            eliminaciones.append(args)
            return {}

        escanear_mod._upsert_video = _upsert_fallido
        escanear_mod.eliminar_candidatos = _eliminar
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
    finally:
        escanear_mod._upsert_video = original_upsert
        escanear_mod.eliminar_candidatos = original_eliminar
    dump_despues = _dump_bd(ruta_db)
    temp_carpeta.cleanup()
    temp_bd.cleanup()
    ok = (
        ok
        and not fl["timeout"]
        and cap.eventos == ["inicio", "error", "finalizada"]
        and cap.error == "RuntimeError: fallo simulado de escritura"
        and len(upserts) == 2
        and eliminaciones == []
        and dump_despues == dump_antes
    )
    return (
        ok,
        f"upserts={upserts} eliminacion_ejecutada={len(eliminaciones)} "
        f"rollback_total={dump_despues == dump_antes} dump={[f[1] for f in dump_despues]}",
    )


def test_20():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        conn = sqlite3.connect(ruta_db)
        try:
            conn.execute(
                """
                CREATE TRIGGER bloquear_c BEFORE DELETE ON videos
                WHEN OLD.nombre = 'c.avi'
                BEGIN
                    SELECT RAISE(ABORT, 'fallo simulado eliminacion');
                END
                """
            )
            conn.commit()
        finally:
            conn.close()
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        dump_despues = _dump_bd(ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    nombres = [fila[1] for fila in dump_despues]
    incorporado_presente = "b.mkv" in nombres
    candidato_preservado = "c.avi" in nombres
    ok = (
        ok
        and not fl["timeout"]
        and cap.error is not None
        and "fallo simulado eliminacion" in cap.error
        and incorporado_presente
        and candidato_preservado
        and set(nombres) == {"a.mp4", "b.mkv", "c.avi"}
    )
    return (
        ok,
        f"error={cap.error} nombres={nombres} "
        f"incorporacion_confirmada={incorporado_presente} rollback_solo_eliminacion={candidato_preservado}",
    )


def test_21():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        finalizadas = cap.eventos.count("finalizada")
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and finalizadas == 1
            and cap.eventos.count("inicio") == 1
        )
        return ok, f"eventos={cap.eventos}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_22():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4"])
    temp = tempfile.TemporaryDirectory()
    ruta_db_inexistente = os.path.join(temp.name, "no_existe.db")
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db_inexistente))
        finalizadas = cap.eventos.count("finalizada")
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is not None
            and finalizadas == 1
            and cap.eventos.count("error") == 1
        )
        return ok, f"eventos={cap.eventos}"
    finally:
        temp_carpeta.cleanup()
        temp.cleanup()


def test_23():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        g = GestorTareas()
        cap1, fl1, ok1 = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        limpio_1 = (
            g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and g not in _GESTORES_ACTIVOS
        )
        cap2, fl2, ok2 = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        limpio_2 = (
            g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and g not in _GESTORES_ACTIVOS
        )
        ok = (
            ok1
            and ok2
            and not fl1["timeout"]
            and not fl2["timeout"]
            and cap1.error is None
            and cap2.error is None
            and limpio_1
            and limpio_2
        )
        return ok, f"limpio_1={limpio_1} limpio_2={limpio_2} estado={g.estado}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_24():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        main_id = threading.get_ident()
        tarea = TareaSincronizacionConHilo(carpeta, ruta_db)
        g = GestorTareas()
        cap, fl, ok = correr(g, tarea)
        ok = (
            ok
            and not fl["timeout"]
            and cap.error is None
            and tarea.id_hilo is not None
            and tarea.id_hilo != main_id
            and tarea.en_principal_trabajo is False
            and cap.ids.get("inicio") is not None
            and cap.ids.get("resultado") is not None
            and cap.ids.get("finalizada") is not None
            and cap.ids["inicio"][1] is True
            and cap.ids["resultado"][1] is True
            and cap.ids["finalizada"][1] is True
            and cap.ids["resultado"][0] == main_id
        )
        return (
            ok,
            f"trabajo_en_hilo_distinto={tarea.id_hilo != main_id} "
            f"trabajo_fuera_del_principal={tarea.en_principal_trabajo is False} "
            f"resultado_en_principal={cap.ids.get('resultado')}",
        )
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_25():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    llamadas = {
        "ffprobe": 0,
        "ffmpeg": 0,
        "subprocess": 0,
        "asegurar_miniatura": 0,
        "asegurar_miniaturas": 0,
        "contar": 0,
        "generar": 0,
        "sincronizar": 0,
    }
    originales = {
        "obtener_datos_ffprobe": escanear_mod.obtener_datos_ffprobe,
        "ffmpeg_disponible": escanear_mod.ffmpeg_disponible,
        "subprocess": escanear_mod.subprocess,
        "asegurar_miniatura": escanear_mod.asegurar_miniatura,
        "asegurar_miniaturas": escanear_mod.asegurar_miniaturas,
        "contar_miniaturas": escanear_mod.contar_miniaturas,
        "generar_miniatura": escanear_mod.generar_miniatura,
        "sincronizar_bd": escanear_mod.sincronizar_bd,
    }

    def _prohibido(clave):
        def _fn(*args, **kwargs):
            llamadas[clave] += 1
            raise AssertionError(f"no debe ejecutarse {clave}")
        return _fn

    escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
    escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg")
    escanear_mod.subprocess.run = _prohibido("subprocess")
    escanear_mod.asegurar_miniatura = _prohibido("asegurar_miniatura")
    escanear_mod.asegurar_miniaturas = _prohibido("asegurar_miniaturas")
    escanear_mod.contar_miniaturas = _prohibido("contar")
    escanear_mod.generar_miniatura = _prohibido("generar")
    escanear_mod.sincronizar_bd = _prohibido("sincronizar")
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(carpeta, ruta_db))
        nombres = _nombres_bd(ruta_db)
    finally:
        escanear_mod.subprocess = originales["subprocess"]
        del originales["subprocess"]
        _restaurar(originales)
    temp_carpeta.cleanup()
    temp_bd.cleanup()
    ok = (
        ok
        and not fl["timeout"]
        and cap.error is None
        and llamadas == {
            "ffprobe": 0,
            "ffmpeg": 0,
            "subprocess": 0,
            "asegurar_miniatura": 0,
            "asegurar_miniaturas": 0,
            "contar": 0,
            "generar": 0,
            "sincronizar": 0,
        }
        and nombres == ["a.mp4", "b.mkv"]
    )
    return ok, f"llamadas={llamadas} bd={nombres}"


def test_26():
    nombres = ["a.mp4", "b.mkv"]
    temp_carpeta, carpeta = _crear_carpeta(nombres)
    temp_bd, ruta_db = _crear_bd(nombres)
    try:
        padre = QObject()
        tarea_con_padre = TareaSincronizacionCatalogo(carpeta, ruta_db, parent=padre)
        g = GestorTareas()
        rechazo_padre = False
        try:
            g.iniciar(tarea_con_padre)
        except TypeError:
            rechazo_padre = True

        tarea = TareaSincronizacionCatalogo(carpeta, ruta_db)
        cap, fl, ok = correr(g, tarea)
        reutilizada = g.iniciar(tarea)
        rechazo_reuso = g.ultimo_rechazo == "la tarea ya fue ejecutada y no se reutiliza"
        ok = (
            rechazo_padre
            and ok
            and not fl["timeout"]
            and cap.error is None
            and reutilizada is False
            and rechazo_reuso
        )
        return ok, f"rechazo_padre={rechazo_padre} reuso_rechazado={rechazo_reuso}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_27():
    bd = ruta_biblioteca()
    miniaturas = ruta_carpeta_miniaturas()
    videos = ruta_carpeta_videos()

    def estado_real():
        return (
            _leer_bytes(bd) if os.path.isfile(bd) else None,
            sorted(os.listdir(miniaturas)) if os.path.isdir(miniaturas) else None,
            sorted(os.listdir(videos)) if os.path.isdir(videos) else None,
        )

    antes = estado_real()
    diferencias = escanear_mod.detectar_diferencias(videos, bd)
    plan = escanear_mod.preparar_plan_sincronizacion(diferencias)
    esperado = {
        "nuevos": len(plan["a_incorporar"]),
        "ya_sincronizados": len(plan["ya_sincronizados"]),
        "incorporados": len(plan["a_incorporar"]),
        "eliminados": len(plan["candidatos_a_eliminar"]),
        "candidatos_restantes": 0,
    }
    nombres_esperados = sorted(
        (set(_nombres_bd(bd)) | {r["nombre"] for r in plan["a_incorporar"]})
        - set(plan["candidatos_a_eliminar"])
    )
    temp = tempfile.TemporaryDirectory()
    try:
        copia = os.path.join(temp.name, "copia_biblioteca.db")
        shutil.copy2(bd, copia)
        conn = escanear_mod.conectar_bd(copia)
        conn.commit()
        conn.close()
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaSincronizacionCatalogo(videos, copia))
        resumen = cap.resultado["resumen"]
        nombres_copia = _nombres_bd(copia)
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and cap.error is None
        and resumen == esperado
        and nombres_copia == nombres_esperados
        and antes == despues
    )
    return (
        ok,
        f"resumen={resumen} esperado={esperado} copia_ok={nombres_copia == nombres_esperados} "
        f"datos_reales_sin_cambios={antes == despues}",
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
        test_25,
        test_26,
        test_27,
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

    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
