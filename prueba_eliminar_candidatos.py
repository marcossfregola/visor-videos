import ast
import os
import py_compile
import shutil
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
        "prueba_aplicar_incorporaciones.py",
        "prueba_eliminar_candidatos.py",
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
        "subprocess", "ffprobe", "ffmpeg",
        "asegurar_miniatura", "asegurar_miniaturas",
        "contar_miniaturas", "generar_miniatura",
        "sincronizar_bd", "insertar_video", "actualizar_datos",
        "guardar_video", "guardar_videos", "_upsert_video", "conectar_bd",
        "escanear_videos", "detectar_diferencias", "preparar_plan_sincronizacion",
        "aplicar_incorporaciones", "preparar_registros_basicos",
        "listdir", "scandir", "getsize", "open", "remove", "unlink", "rmdir", "shutil",
    }
    usados_eliminar = _nombres_usados_en_funcion("eliminar_candidatos", arbol_escaneo)
    usados_aplicar = _nombres_usados_en_funcion("aplicar_incorporaciones", arbol_escaneo)
    prohibidos_eliminar = sorted(prohibidos & usados_eliminar) if usados_eliminar is not None else None

    ok = (
        "_validar_plan_sincronizacion" in funcs_escaneo
        and "eliminar_candidatos" in funcs_escaneo
        and "eliminar_candidatos" not in funcs_tareas
        and "eliminar_candidatos" not in importados_tareas
        and "eliminar_candidatos" not in importados_visor
        and not any("Eliminar" in c or "Eliminacion" in c for c in clases_tareas)
        and usados_eliminar is not None
        and "_validar_plan_sincronizacion" in usados_eliminar
        and "sqlite3" in usados_eliminar
        and "conn" in usados_eliminar
        and usados_aplicar is not None
        and "_validar_plan_sincronizacion" in usados_aplicar
        and "guardar_videos" in usados_aplicar
        and prohibidos_eliminar == []
    )
    return (
        ok,
        f"def_escaneo={'eliminar_candidatos' in funcs_escaneo} "
        f"def_tareas={'eliminar_candidatos' in funcs_tareas} "
        f"import_tareas={'eliminar_candidatos' in importados_tareas} "
        f"import_visor={'eliminar_candidatos' in importados_visor} "
        f"comparte_validacion={'_validar_plan_sincronizacion' in (usados_aplicar or set())} "
        f"delega_validacion={'_validar_plan_sincronizacion' in (usados_eliminar or set())} "
        f"sqlite_en_eliminar={'sqlite3' in (usados_eliminar or set())} "
        f"prohibidos_en_cuerpo={prohibidos_eliminar}",
    )


def test_03():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        with open(ruta_db, "rb") as f:
            bytes_antes = f.read()
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", [], ["a.mp4", "c.avi"], [])
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        with open(ruta_db, "rb") as f:
            bytes_despues = f.read()
        dump_despues = _dump_bd(ruta_db)
        rastro = [n for n in os.listdir(temp_bd.name) if n != "catalogo.db"]
    finally:
        temp_bd.cleanup()
    ok = (
        resultado == {"eliminados": 0, "nombres": [], "incorporados": 0, "restantes": 0}
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
    temp_bd, ruta_db = _crear_bd(["a.mp4", "viejo.avi"])
    try:
        plan = _plan("C:\\videos", [], ["a.mp4"], ["viejo.avi"])
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    ok = (
        resultado == {"eliminados": 1, "nombres": ["viejo.avi"], "incorporados": 0, "restantes": 0}
        and [fila[1] for fila in dump] == ["a.mp4"]
    )
    return ok, f"resultado={resultado} dump={dump}"


def test_05():
    temp_bd, ruta_db = _crear_bd(["z.avi", "a.mp4", "m.mkv", "b.avi"])
    try:
        plan = _plan(
            "C:\\videos",
            _registros(["nuevo1.mp4"], "C:\\videos"),
            ["a.mp4"],
            ["z.avi", "m.mkv", "b.avi"],
        )
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    ok = (
        resultado["eliminados"] == 3
        and resultado["nombres"] == ["b.avi", "m.mkv", "z.avi"]
        and resultado["incorporados"] == 1
        and resultado["restantes"] == 0
        and [fila[1] for fila in dump] == ["a.mp4"]
    )
    return ok, f"resultado={resultado} dump={dump}"


def test_06():
    temp_bd, ruta_db = _crear_bd(["x.mp4", "y.mkv", "z.avi", "k.mp4", "l.avi"])
    try:
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", [], ["k.mp4", "l.avi"], ["x.mp4", "y.mkv", "z.avi"])
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            presentes = {fila[0] for fila in conn.execute("SELECT nombre FROM videos")}
        finally:
            conn.close()
    finally:
        temp_bd.cleanup()
    supervivientes = [f for f in dump_antes if f[1] in ("k.mp4", "l.avi")]
    ok = (
        resultado["eliminados"] == 3
        and presentes == {"k.mp4", "l.avi"}
        and [fila[1] for fila in dump_despues] == ["k.mp4", "l.avi"]
        and dump_despues == supervivientes
    )
    return ok, f"presentes={presentes} dump={dump_despues} resultado={resultado}"


def test_07():
    temp_bd, ruta_db = _crear_bd(["nuevo1.mp4", "nuevo2.mkv", "viejo1.avi"])
    try:
        dump_antes = _dump_bd(ruta_db)
        incorporar = _registros(["nuevo1.mp4", "nuevo2.mkv"], "C:\\videos")
        plan = _plan("C:\\videos", incorporar, [], ["viejo1.avi"])
        escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    nuevo1_antes = [f for f in dump_antes if f[1] == "nuevo1.mp4"][0]
    nuevo2_antes = [f for f in dump_antes if f[1] == "nuevo2.mkv"][0]
    nuevo1_despues = [f for f in dump_despues if f[1] == "nuevo1.mp4"][0]
    nuevo2_despues = [f for f in dump_despues if f[1] == "nuevo2.mkv"][0]
    nombres = [fila[1] for fila in dump_despues]
    ok = (
        nombres == ["nuevo1.mp4", "nuevo2.mkv"]
        and nuevo1_despues == nuevo1_antes
        and nuevo2_despues == nuevo2_antes
    )
    return (
        ok,
        f"nombres={nombres} nuevo1_intacto={nuevo1_despues == nuevo1_antes} "
        f"nuevo2_intacto={nuevo2_despues == nuevo2_antes}",
    )


def test_08():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", [], ["a.mp4"], ["c.avi"])
        escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    a_antes = [f for f in dump_antes if f[1] == "a.mp4"][0]
    a_despues = [f for f in dump_despues if f[1] == "a.mp4"][0]
    nombres = [fila[1] for fila in dump_despues]
    ok = nombres == ["a.mp4"] and a_despues == a_antes
    return ok, f"nombres={nombres} a_intacto={a_despues == a_antes}"


def test_09():
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "no_existe.db")
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), [], ["x.avi"])
        try:
            escanear_mod.eliminar_candidatos(plan, ruta_db)
        except FileNotFoundError:
            ok_base = True
        else:
            ok_base = False
    finally:
        temp.cleanup()
    ok = ok_base and not os.path.isfile(ruta_db)
    return ok, f"FileNotFoundError={ok_base} archivo_creado={os.path.isfile(ruta_db)}"


def test_10():
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "corrupta.db")
    try:
        with open(ruta_db, "wb") as f:
            f.write(b"esto no es una base sqlite" * 10)
        with open(ruta_db, "rb") as f:
            bytes_antes = f.read()
        plan = _plan("C:\\videos", [], [], ["x.avi"])
        try:
            escanear_mod.eliminar_candidatos(plan, ruta_db)
        except sqlite3.Error:
            error_ok = True
        except Exception:
            error_ok = False
        else:
            error_ok = False
        with open(ruta_db, "rb") as f:
            bytes_despues = f.read()
        rastro = [n for n in os.listdir(temp.name) if n != "corrupta.db"]
    finally:
        temp.cleanup()
    ok = error_ok and bytes_despues == bytes_antes and rastro == []
    return (
        ok,
        f"sqlite_error={error_ok} bytes_iguales={bytes_despues == bytes_antes} archivos={rastro}",
    )


def test_11():
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
                escanear_mod.eliminar_candidatos(plan, ruta_db)
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
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    llamadas = {"connect": 0}
    originales = {"sqlite3.connect": escanear_mod.sqlite3.connect}

    def _connect(*args, **kwargs):
        llamadas["connect"] += 1
        raise AssertionError("no debe abrirse SQLite")

    escanear_mod.sqlite3.connect = _connect
    try:
        casos = [
            (_plan("C:\\videos", "b.mkv", [], []), TypeError),
            (_plan("C:\\videos", 5, [], []), TypeError),
            (_plan("C:\\videos", None, [], []), TypeError),
        ]
        fallos = {str(idx): False for idx in range(len(casos))}
        for idx, (plan, esperado) in enumerate(casos):
            try:
                escanear_mod.eliminar_candidatos(plan, ruta_db)
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


def test_13():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "b.mkv", "c.avi", "d.mkv", "e.mp4"])
    try:
        conn = sqlite3.connect(ruta_db)
        try:
            conn.execute(
                """
                CREATE TRIGGER bloquear_c BEFORE DELETE ON videos
                WHEN OLD.nombre = 'c.avi'
                BEGIN
                    SELECT RAISE(ABORT, 'fallo simulado');
                END
                """
            )
            conn.commit()
        finally:
            conn.close()
        dump_antes = _dump_bd(ruta_db)
        plan = _plan("C:\\videos", [], [], ["a.mp4", "c.avi", "d.mkv"])
        try:
            escanear_mod.eliminar_candidatos(plan, ruta_db)
        except sqlite3.Error:
            fallo = True
        except Exception:
            fallo = False
        else:
            fallo = False
        dump_despues = _dump_bd(ruta_db)
    finally:
        temp_bd.cleanup()
    ok = (
        fallo
        and dump_despues == dump_antes
        and [fila[1] for fila in dump_despues] == ["a.mp4", "b.mkv", "c.avi", "d.mkv", "e.mp4"]
    )
    return (
        ok,
        f"fallo={fallo} dump_igual={dump_despues == dump_antes} dump={dump_despues}",
    )


def test_14():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        plan = _plan("C:\\videos", [], ["a.mp4"], ["c.avi", "fantasma.mkv"])
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        conn = sqlite3.connect(ruta_db)
        try:
            presentes = {fila[0] for fila in conn.execute("SELECT nombre FROM videos")}
        finally:
            conn.close()
    finally:
        temp_bd.cleanup()
    ok = (
        resultado["eliminados"] == 1
        and resultado["nombres"] == ["c.avi"]
        and resultado["restantes"] == 1
        and presentes == {"a.mp4"}
    )
    return ok, f"resultado={resultado} presentes={presentes}"


def test_15():
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    llamadas = {
        "escanear_videos": 0,
        "detectar_diferencias": 0,
        "preparar_plan_sincronizacion": 0,
        "aplicar_incorporaciones": 0,
        "sincronizar_bd": 0,
        "insertar_video": 0,
        "actualizar_datos": 0,
        "guardar_video": 0,
        "guardar_videos": 0,
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
        "aplicar_incorporaciones": escanear_mod.aplicar_incorporaciones,
        "sincronizar_bd": escanear_mod.sincronizar_bd,
        "insertar_video": escanear_mod.insertar_video,
        "actualizar_datos": escanear_mod.actualizar_datos,
        "guardar_video": escanear_mod.guardar_video,
        "guardar_videos": escanear_mod.guardar_videos,
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
    escanear_mod.aplicar_incorporaciones = _prohibido("aplicar_incorporaciones")
    escanear_mod.sincronizar_bd = _prohibido("sincronizar_bd")
    escanear_mod.insertar_video = _prohibido("insertar_video")
    escanear_mod.actualizar_datos = _prohibido("actualizar_datos")
    escanear_mod.guardar_video = _prohibido("guardar_video")
    escanear_mod.guardar_videos = _prohibido("guardar_videos")
    escanear_mod.conectar_bd = _prohibido("conectar_bd")
    escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
    escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg")
    escanear_mod.subprocess.run = _prohibido("subprocess")
    escanear_mod.asegurar_miniatura = _prohibido("asegurar_miniatura")
    escanear_mod.asegurar_miniaturas = _prohibido("asegurar_miniaturas")
    escanear_mod.contar_miniaturas = _prohibido("contar")
    escanear_mod.generar_miniatura = _prohibido("generar")
    try:
        plan = _plan("C:\\videos", _registros(["b.mkv"], "C:\\videos"), ["a.mp4"], ["c.avi"])
        resultado = escanear_mod.eliminar_candidatos(plan, ruta_db)
        dump_despues = _dump_bd(ruta_db)
    finally:
        _restaurar(originales)
    nombres = [fila[1] for fila in dump_despues]
    temp_bd.cleanup()
    ok = (
        resultado == {"eliminados": 1, "nombres": ["c.avi"], "incorporados": 1, "restantes": 0}
        and llamadas == {
            "escanear_videos": 0,
            "detectar_diferencias": 0,
            "preparar_plan_sincronizacion": 0,
            "aplicar_incorporaciones": 0,
            "sincronizar_bd": 0,
            "insertar_video": 0,
            "actualizar_datos": 0,
            "guardar_video": 0,
            "guardar_videos": 0,
            "conectar_bd": 0,
            "ffprobe": 0,
            "ffmpeg": 0,
            "subprocess": 0,
            "asegurar_miniatura": 0,
            "asegurar_miniaturas": 0,
            "contar": 0,
            "generar": 0,
        }
        and nombres == ["a.mp4"]
    )
    return ok, f"resultado={resultado} llamadas={llamadas} nombres={nombres}"


def test_16():
    bd = ruta_biblioteca()
    miniaturas = ruta_carpeta_miniaturas()
    videos = ruta_carpeta_videos()

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

    temp = tempfile.TemporaryDirectory()
    try:
        copia = os.path.join(temp.name, "copia_biblioteca.db")
        shutil.copy2(bd, copia)
        resultado_copia = escanear_mod.eliminar_candidatos(plan, copia)
        dump_copia = _dump_bd(copia)
    finally:
        temp.cleanup()

    despues = estado_archivos()
    bytes_despues = bytes_bd()
    dump_despues = _dump_bd(bd)

    eliminados_en_copia = set(resultado_copia["nombres"])
    nombres_antes = {fila[1] for fila in dump_antes}
    dump_esperado_copia = {
        fila for fila in dump_antes if fila[1] not in eliminados_en_copia
    }

    ok = (
        resultado_copia["incorporados"] == len(plan["a_incorporar"])
        and eliminados_en_copia.issubset(set(plan["candidatos_a_eliminar"]))
        and set(dump_copia) == dump_esperado_copia
        and resultado_copia["restantes"]
        == len(plan["candidatos_a_eliminar"]) - len(eliminados_en_copia)
        and {fila[1] for fila in dump_despues} == nombres_antes
        and bytes_despues == bytes_antes
        and dump_despues == dump_antes
        and antes == despues
    )
    return (
        ok,
        f"candidatos={plan['candidatos_a_eliminar']} "
        f"eliminados_en_copia={resultado_copia['nombres']} "
        f"bd_real_igual={dump_despues == dump_antes} "
        f"bytes_real_igual={bytes_despues == bytes_antes} "
        f"estado_real_igual={antes == despues}",
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

    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
