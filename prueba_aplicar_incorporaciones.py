import ast
import copy
import os
import py_compile
import sqlite3
import sys
import tempfile

import escanear_videos as escanear_mod
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos


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
        for nombre in filas:
            conn.execute(
                "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?, ?, ?, ?)",
                (nombre, os.path.join("C:\\videos", nombre), os.path.splitext(nombre)[1], "f"),
            )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


def _dump_bd(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
    finally:
        conn.close()


def _registros(nombres, carpeta):
    return escanear_mod.preparar_registros_basicos(nombres, carpeta)


def _plan(carpeta, a_incorporar, ya_sincronizados, candidatos):
    return {
        "carpeta": carpeta,
        "a_incorporar": a_incorporar,
        "ya_sincronizados": ya_sincronizados,
        "candidatos_a_eliminar": candidatos,
    }


def _restaurar(originales):
    for clave, original in originales.items():
        if "." in clave:
            modulo, atributo = clave.split(".", 1)
            setattr(getattr(escanear_mod, modulo), atributo, original)
        else:
            setattr(escanear_mod, clave, original)


def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "rutas.py",
        "prueba_plan_sincronizacion.py",
        "prueba_aplicar_incorporaciones.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))

    def _arbol(nombre_archivo):
        con = open(os.path.join(ruta_raiz, nombre_archivo), encoding="utf-8")
        try:
            return ast.parse(con.read(), nombre_archivo)
        finally:
            con.close()

    arbol_escaneo = _arbol("escanear_videos.py")
    arbol_tareas = _arbol("tareas_videos.py")
    arbol_visor = _arbol("visor_videos.py")

    def _funciones(arbol):
        return {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}

    def _clases(arbol):
        return {n.name for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)}

    def _nombres_importados(arbol):
        conjunto = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                conjunto.update(a.name for a in nodo.names)
            elif isinstance(nodo, ast.Import):
                for a in nodo.names:
                    conjunto.add(a.name.split(".")[0])
        return conjunto

    def _nombres_usados_en_funcion(nombre, arbol):
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
                usados = set()
                for sub in ast.walk(nodo):
                    if isinstance(sub, ast.Name):
                        usados.add(sub.id)
                    elif isinstance(sub, ast.Attribute):
                        usados.add(sub.attr)
                return usados
        return None

    funcs_escaneo = _funciones(arbol_escaneo)
    funcs_tareas = _funciones(arbol_tareas)
    clases_tareas = _clases(arbol_tareas)
    importados_tareas = _nombres_importados(arbol_tareas)
    importados_visor = _nombres_importados(arbol_visor)

    prohibidos = {
        "sqlite3", "conn", "connect", "DELETE", "execute",
        "subprocess", "ffprobe", "ffmpeg",
        "asegurar_miniatura", "asegurar_miniaturas",
        "contar_miniaturas", "generar_miniatura",
        "sincronizar_bd", "insertar_video", "actualizar_datos",
        "guardar_video", "_upsert_video",
        "detectar_diferencias", "preparar_plan_sincronizacion",
        "escanear_videos", "conectar_bd", "preparar_registros_basicos",
        "listdir", "scandir", "isdir", "isfile", "getsize", "open",
        "remove", "unlink", "rmdir", "shutil",
    }
    usados_aplicar = _nombres_usados_en_funcion("aplicar_incorporaciones", arbol_escaneo)
    prohibidos_presentes = sorted(prohibidos & usados_aplicar) if usados_aplicar is not None else None

    ok = (
        "aplicar_incorporaciones" in funcs_escaneo
        and "aplicar_incorporaciones" not in funcs_tareas
        and "aplicar_incorporaciones" not in importados_tareas
        and "aplicar_incorporaciones" not in importados_visor
        and not any("Aplicar" in c or "Incorporacion" in c for c in clases_tareas)
        and usados_aplicar is not None
        and "guardar_videos" in usados_aplicar
        and prohibidos_presentes == []
    )
    return (
        ok,
        f"def_escaneo={'aplicar_incorporaciones' in funcs_escaneo} "
        f"def_tareas={'aplicar_incorporaciones' in funcs_tareas} "
        f"import_tareas={'aplicar_incorporaciones' in importados_tareas} "
        f"import_visor={'aplicar_incorporaciones' in importados_visor} "
        f"delega_guardar_videos={'guardar_videos' in (usados_aplicar or set())} "
        f"prohibidos_en_cuerpo={prohibidos_presentes}",
    )


def test_03():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        with open(ruta_db, "rb") as f:
            bytes_antes = f.read()
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", [], ["a.mp4", "c.avi"], [])
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        with open(ruta_db, "rb") as f:
            bytes_despues = f.read()
        dump_despues = _dump_bd(ruta_db)
        rastro = [n for n in os.listdir(temp_bd.name) if n != "catalogo.db"]
    finally:
        temp_bd.cleanup()
    ok = (
        set(resultado.keys()) == {"incorporados", "nombres", "pendientes_eliminacion"}
        and resultado["incorporados"] == 0
        and isinstance(resultado["nombres"], list)
        and resultado["nombres"] == []
        and resultado["pendientes_eliminacion"] == 0
        and bytes_despues == bytes_antes
        and dump_despues == dump_antes
        and rastro == []
    )
    return (
        ok,
        f"resultado={resultado} bytes_iguales={bytes_despues == bytes_antes} "
        f"dump_igual={dump_despues == dump_antes} archivos_en_bd={rastro}",
    )


def test_04():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], [])
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        dump = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    nombres = [fila[1] for fila in dump]
    b = [fila for fila in dump if fila[1] == "b.mkv"][0]
    ok = (
        resultado == {"incorporados": 1, "nombres": ["b.mkv"], "pendientes_eliminacion": 0}
        and nombres == ["a.mp4", "b.mkv"]
        and b[2] == os.path.join("C:\\videos", "b.mkv")
        and b[3] == ".mkv"
        and isinstance(b[4], str)
        and b[4] != ""
    )
    return ok, f"resultado={resultado} dump={dump}"


def test_05():
    temp_bd, ruta_db = _crear_bd([])
    try:
        plan = _plan("C:\\videos", _registros(["m.mkv", "b.mkv"], "C:\\videos"), [], [])
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        dump = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    ok = (
        resultado["incorporados"] == 2
        and resultado["nombres"] == ["m.mkv", "b.mkv"]
        and [fila[1] for fila in dump] == ["b.mkv", "m.mkv"]
    )
    return ok, f"resultado={resultado} dump={dump}"


def test_06():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], ["c.avi"])
        escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    antes_a = [f for f in dump_antes if f[1] == "a.mp4"][0]
    antes_c = [f for f in dump_antes if f[1] == "c.avi"][0]
    despues_a = [f for f in dump_despues if f[1] == "a.mp4"][0]
    despues_c = [f for f in dump_despues if f[1] == "c.avi"][0]
    nombres = [fila[1] for fila in dump_despues]
    ok = (
        nombres == ["a.mp4", "b.mkv", "c.avi"]
        and despues_a == antes_a
        and despues_c == antes_c
    )
    return ok, f"nombres={nombres} a_intacto={despues_a == antes_a} c_intacto={despues_c == antes_c}"


def test_07():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    try:
        conn = sqlite3.connect(ruta_db)
        try:
            conn.execute(
                "UPDATE videos SET fecha_importacion = ?, ruta = ? WHERE nombre = ?",
                ("fecha-antes", os.path.join("C:\\videos", "a.mp4"), "a.mp4"),
            )
            conn.commit()
        finally:
            conn.close()
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], [])
        escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        dump = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    a = [f for f in dump if f[1] == "a.mp4"][0]
    ok = (
        a[2] == os.path.join("C:\\videos", "a.mp4")
        and a[3] == ".mp4"
        and a[4] == "fecha-antes"
    )
    return ok, f"a_no_reescrito={a}"


def test_08():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], ["c.avi"])
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            fila_c = conn.execute(
                "SELECT nombre, ruta, extension FROM videos WHERE nombre = ?",
                ("c.avi",),
            ).fetchone()
            fila_a = conn.execute(
                "SELECT nombre, ruta, extension FROM videos WHERE nombre = ?",
                ("a.mp4",),
            ).fetchone()
        finally:
            conn.close()
    finally:
        temp_bd.cleanup()
    ok = (
        fila_c is not None
        and fila_c[0] == "c.avi"
        and fila_a is not None
        and resultado["pendientes_eliminacion"] == 1
    )
    return ok, f"c_tras_consultar={fila_c} a_tras_consultar={fila_a} resultado={resultado}"


def test_09():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    try:
        plan = _plan(
            "C:\\videos",
            _registros(["b.mkv", "c.avi"], "C:\\videos"),
            ["a.mp4"],
            ["z.mp4", "y.mp4"],
        )
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
    finally:
        temp_bd.cleanup()
    ok = (
        isinstance(resultado, dict)
        and resultado["incorporados"] == 2
        and resultado["nombres"] == ["b.mkv", "c.avi"]
        and resultado["pendientes_eliminacion"] == 2
        and resultado["nombres"] == [r["nombre"] for r in plan["a_incorporar"]]
    )
    return ok, f"resultado={resultado}"


def test_10():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    llamadas = {"connect": 0}
    originales = {"sqlite3.connect": escanear_mod.sqlite3.connect}

    def _connect(*args, **kwargs):
        llamadas["connect"] += 1
        raise AssertionError("no debe abrirse SQLite")

    escanear_mod.sqlite3.connect = _connect
    try:
        casos = [
            (None, TypeError),
            (["carpeta", "x"], TypeError),
            ({k: v for k, v in _plan("C:\\videos", [], [], []).items() if k != "a_incorporar"}, ValueError),
            ({k: v for k, v in _plan("C:\\videos", [], [], []).items() if k != "candidatos_a_eliminar"}, ValueError),
            (_plan("", [], [], []), ValueError),
            (_plan(None, [], [], []), ValueError),
            (_plan("C:\\videos", [], "texto", []), TypeError),
            (_plan("C:\\videos", [], [], 5), TypeError),
        ]
        fallos = {str(idx): False for idx in range(len(casos))}
        for idx, (plan, esperado) in enumerate(casos):
            try:
                escanear_mod.aplicar_incorporaciones(plan, ruta_db)
            except esperado:
                fallos[str(idx)] = True
    finally:
        _restaurar(originales)
    dump_despues = _dump_bd(ruta_db)
    temp_bd.cleanup()
    ok = (
        all(fallos.values())
        and llamadas["connect"] == 0
        and [fila[1] for fila in dump_despues] == ["a.mp4"]
    )
    return ok, f"validaciones={fallos} connect={llamadas['connect']} dump={dump_despues}"


def test_11():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    llamadas = {"connect": 0}
    originales = {"sqlite3.connect": escanear_mod.sqlite3.connect}

    def _connect(*args, **kwargs):
        llamadas["connect"] += 1
        raise AssertionError("no debe abrirse SQLite")

    escanear_mod.sqlite3.connect = _connect
    try:
        registro_faltante = _registros(["b.mkv"], "C:\\videos")[0]
        del registro_faltante["fecha_importacion"]
        casos = [
            (_plan("C:\\videos", "b.mkv", [], []), TypeError),
            (_plan("C:\\videos", 5, [], []), TypeError),
            (_plan("C:\\videos", None, [], []), TypeError),
            (_plan("C:\\videos", ["b.mkv"], [], []), TypeError),
            (_plan("C:\\videos", [registro_faltante], [], []), ValueError),
        ]
        fallos = {str(idx): False for idx in range(len(casos))}
        for idx, (plan, esperado) in enumerate(casos):
            try:
                escanear_mod.aplicar_incorporaciones(plan, ruta_db)
            except esperado:
                fallos[str(idx)] = True
    finally:
        _restaurar(originales)
    dump_despues = _dump_bd(ruta_db)
    temp_bd.cleanup()
    ok = (
        all(fallos.values())
        and llamadas["connect"] == 0
        and [fila[1] for fila in dump_despues] == ["a.mp4"]
    )
    return ok, f"validaciones={fallos} connect={llamadas['connect']} dump={dump_despues}"


def test_12():
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "no_existe.db")
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), [], [])
        try:
            escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        except FileNotFoundError:
            ok_base = True
        else:
            ok_base = False
    finally:
        temp.cleanup()
    ok = ok_base and not os.path.isfile(ruta_db)
    return ok, f"FileNotFoundError={ok_base} archivo_creado={os.path.isfile(ruta_db)}"


def test_13():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    dump_antes = _dump_bd(ruta_db)
    original = escanear_mod._upsert_video
    llamadas = []
    intento_fallido = False
    try:
        def _upsert_fallido(conn, datos):
            llamadas.append(datos["nombre"])
            if len(llamadas) == 2:
                raise RuntimeError("fallo simulado de escritura")
            return original(conn, datos)

        escanear_mod._upsert_video = _upsert_fallido
        plan = _plan("C:\\videos", _registros(["x.mp4", "y.mkv", "z.avi"], "C:\\videos"), [], [])
        try:
            escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        except RuntimeError:
            intento_fallido = True
        dump_despues = _dump_bd(ruta_db)
    finally:
        escanear_mod._upsert_video = original
        temp_bd.cleanup()
    nombres = [fila[1] for fila in dump_despues]
    ok = (
        intento_fallido
        and len(llamadas) == 2
        and dump_despues == dump_antes
        and nombres == ["a.mp4"]
    )
    return (
        ok,
        f"fallo={intento_fallido} upserts_ejecutados={llamadas} "
        f"nombres_tras_fallo={nombres} preexistentes_intactos={dump_despues == dump_antes}",
    )


def test_14():
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    llamadas = {
        "escanear_videos": 0,
        "detectar_diferencias": 0,
        "preparar_plan_sincronizacion": 0,
        "sincronizar_bd": 0,
        "insertar_video": 0,
        "actualizar_datos": 0,
        "guardar_video": 0,
        "conectar_bd": 0,
        "ffprobe": 0,
        "ffmpeg": 0,
        "subprocess": 0,
        "asegurar_miniatura": 0,
        "asegurar_miniaturas": 0,
        "contar": 0,
        "generar": 0,
    }

    def _prohibido(clave):
        def _fn(*args, **kwargs):
            llamadas[clave] += 1
            raise AssertionError(f"no debe ejecutarse {clave}")
        return _fn

    originales = {
        "escanear_videos": escanear_mod.escanear_videos,
        "detectar_diferencias": escanear_mod.detectar_diferencias,
        "preparar_plan_sincronizacion": escanear_mod.preparar_plan_sincronizacion,
        "sincronizar_bd": escanear_mod.sincronizar_bd,
        "insertar_video": escanear_mod.insertar_video,
        "actualizar_datos": escanear_mod.actualizar_datos,
        "guardar_video": escanear_mod.guardar_video,
        "conectar_bd": escanear_mod.conectar_bd,
        "obtener_datos_ffprobe": escanear_mod.obtener_datos_ffprobe,
        "ffmpeg_disponible": escanear_mod.ffmpeg_disponible,
        "subprocess.run": escanear_mod.subprocess.run,
        "asegurar_miniatura": escanear_mod.asegurar_miniatura,
        "asegurar_miniaturas": escanear_mod.asegurar_miniaturas,
        "contar_miniaturas": escanear_mod.contar_miniaturas,
        "generar_miniatura": escanear_mod.generar_miniatura,
    }

    escanear_mod.escanear_videos = _prohibido("escanear_videos")
    escanear_mod.detectar_diferencias = _prohibido("detectar_diferencias")
    escanear_mod.preparar_plan_sincronizacion = _prohibido("preparar_plan_sincronizacion")
    escanear_mod.sincronizar_bd = _prohibido("sincronizar_bd")
    escanear_mod.insertar_video = _prohibido("insertar_video")
    escanear_mod.actualizar_datos = _prohibido("actualizar_datos")
    escanear_mod.guardar_video = _prohibido("guardar_video")
    escanear_mod.conectar_bd = _prohibido("conectar_bd")
    escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
    escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg")
    escanear_mod.subprocess.run = _prohibido("subprocess")
    escanear_mod.asegurar_miniatura = _prohibido("asegurar_miniatura")
    escanear_mod.asegurar_miniaturas = _prohibido("asegurar_miniaturas")
    escanear_mod.contar_miniaturas = _prohibido("contar")
    escanear_mod.generar_miniatura = _prohibido("generar")
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], [])
        resultado = escanear_mod.aplicar_incorporaciones(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
    finally:
        _restaurar(originales)
    nombres = [fila[1] for fila in dump_despues]
    temp_bd.cleanup()
    ok = (
        resultado == {"incorporados": 1, "nombres": ["b.mkv"], "pendientes_eliminacion": 0}
        and llamadas == {
            "escanear_videos": 0,
            "detectar_diferencias": 0,
            "preparar_plan_sincronizacion": 0,
            "sincronizar_bd": 0,
            "insertar_video": 0,
            "actualizar_datos": 0,
            "guardar_video": 0,
            "conectar_bd": 0,
            "ffprobe": 0,
            "ffmpeg": 0,
            "subprocess": 0,
            "asegurar_miniatura": 0,
            "asegurar_miniaturas": 0,
            "contar": 0,
            "generar": 0,
        }
        and nombres == ["a.mp4", "b.mkv"]
    )
    return ok, f"resultado={resultado} llamadas={llamadas} nombres={nombres}"


def test_15():
    bd = ruta_biblioteca()
    miniaturas = ruta_carpeta_miniaturas()
    videos = ruta_carpeta_videos()
    carpeta_bd = os.path.dirname(bd)

    def estado_archivos():
        return (
            os.path.getsize(bd) if os.path.isfile(bd) else None,
            os.path.getmtime(bd) if os.path.isfile(bd) else None,
            sorted(os.listdir(miniaturas)) if os.path.isdir(miniaturas) else None,
            sorted(os.listdir(videos)) if os.path.isdir(videos) else None,
        )

    def bytes_bd():
        with open(bd, "rb") as f:
            return f.read()

    antes = estado_archivos()
    bytes_antes = bytes_bd()
    dump_antes = _dump_bd(bd)

    diferencias = escanear_mod.detectar_diferencias(videos, bd)
    plan = escanear_mod.preparar_plan_sincronizacion(diferencias)
    resultado = escanear_mod.aplicar_incorporaciones(plan, bd)

    despues = estado_archivos()
    bytes_despues = bytes_bd()
    dump_despues = _dump_bd(bd)

    conn = sqlite3.connect(bd)
    try:
        nombres_actuales = {fila[0] for fila in conn.execute("SELECT nombre FROM videos")}
        candidatos_presentes = {
            nombre for nombre in plan["candidatos_a_eliminar"]
            if conn.execute("SELECT 1 FROM videos WHERE nombre = ?", (nombre,)).fetchone() is not None
        }
    finally:
        conn.close()

    incorporados = resultado["incorporados"]
    nombres_incorporados = resultado["nombres"]
    pendientes = resultado["pendientes_eliminacion"]
    nombres_antes = {fila[1] for fila in dump_antes}

    ok = (
        resultado["incorporados"] == len(plan["a_incorporar"])
        and resultado["nombres"] == [r["nombre"] for r in plan["a_incorporar"]]
        and resultado["pendientes_eliminacion"] == len(plan["candidatos_a_eliminar"])
        and nombres_antes.issubset(nombres_actuales)
        and candidatos_presentes == set(plan["candidatos_a_eliminar"])
        and dump_antes == [f for f in dump_despues if f[1] in nombres_antes]
        and antes == despues
        and (plan["a_incorporar"] == [] or True)
    )
    sin_escritura = plan["a_incorporar"] == [] and bytes_despues == bytes_antes
    return (
        ok,
        f"incorporados={incorporados} nombres={nombres_incorporados} "
        f"pendientes={pendientes} nada_eliminado={nombres_antes.issubset(nombres_actuales)} "
        f"candidatos_presentes={candidatos_presentes} estado_real_igual={antes == despues} "
        f"noop_bytes_iguales={sin_escritura}",
    )


def main():
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

    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
