import ast
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
                cantidad_miniaturas INTEGER,
                tamano_bytes INTEGER
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


def _crear_carpeta(nombres):
    temp = tempfile.TemporaryDirectory()
    carpeta = temp.name
    for nombre in nombres:
        with open(os.path.join(carpeta, nombre), "wb") as f:
            f.write(b"x")
    return temp, carpeta


def _dump_bd(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT * FROM videos ORDER BY nombre").fetchall()
    finally:
        conn.close()


def _diferencias(carpeta, presentes, nuevos, ausentes):
    return {
        "carpeta": carpeta,
        "presentes_en_ambos": presentes,
        "nuevos": nuevos,
        "ausentes_del_disco": ausentes,
    }


def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "rutas.py",
        "prueba_plan_sincronizacion.py",
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
        "guardar_video", "guardar_videos", "_upsert_video",
        "listdir", "isdir", "isfile", "getsize", "open",
    }
    usados_plan = _nombres_usados_en_funcion("preparar_plan_sincronizacion", arbol_escaneo)
    prohibidos_presentes = sorted(prohibidos & usados_plan) if usados_plan is not None else None

    ok = (
        "preparar_plan_sincronizacion" in funcs_escaneo
        and "preparar_plan_sincronizacion" not in funcs_tareas
        and "preparar_plan_sincronizacion" not in importados_tareas
        and "preparar_plan_sincronizacion" not in importados_visor
        and not any(
            ("Plan" in c or "Sincronizacion" in c)
            and c != "TareaSincronizacionCatalogo"
            for c in clases_tareas
        )
        and usados_plan is not None
        and prohibidos_presentes == []
    )
    return (
        ok,
        f"def_escaneo={'preparar_plan_sincronizacion' in funcs_escaneo} "
        f"def_tareas={'preparar_plan_sincronizacion' in funcs_tareas} "
        f"import_tareas={'preparar_plan_sincronizacion' in importados_tareas} "
        f"import_visor={'preparar_plan_sincronizacion' in importados_visor} "
        f"prohibidos_en_cuerpo={prohibidos_presentes}",
    )


def test_03():
    temp_carpeta, carpeta = _crear_carpeta([])
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, [], [], [])
        )
    finally:
        temp_carpeta.cleanup()
    ok = (
        isinstance(plan, dict)
        and set(plan.keys()) == {"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}
        and plan["carpeta"] == carpeta
        and plan["a_incorporar"] == []
        and plan["ya_sincronizados"] == []
        and plan["candidatos_a_eliminar"] == []
    )
    return ok, f"plan={plan}"


def test_04():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, ["a.mp4"], ["b.mkv"], ["d.mp4"])
        )
    finally:
        temp_carpeta.cleanup()
    incorporar = plan["a_incorporar"]
    ok = (
        [r["nombre"] for r in incorporar] == ["b.mkv"]
        and plan["ya_sincronizados"] == ["a.mp4"]
        and plan["candidatos_a_eliminar"] == ["d.mp4"]
        and incorporar[0]["ruta"] == os.path.join(carpeta, "b.mkv")
        and incorporar[0]["extension"] == ".mkv"
        and isinstance(incorporar[0]["fecha_importacion"], str)
        and incorporar[0]["fecha_importacion"] != ""
    )
    return ok, f"incorporar={incorporar} ya={plan['ya_sincronizados']} candidatos={plan['candidatos_a_eliminar']}"


def test_05():
    temp_carpeta, carpeta = _crear_carpeta(["b.mkv", "a.mp4"])
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, [], ["b.mkv", "a.mp4"], [])
        )
    finally:
        temp_carpeta.cleanup()
    incorporar = plan["a_incorporar"]
    claves_esperadas = {"nombre", "ruta", "extension", "fecha_importacion"}
    ok = (
        len(incorporar) == 2
        and [r["nombre"] for r in incorporar] == ["a.mp4", "b.mkv"]
        and all(set(r.keys()) == claves_esperadas for r in incorporar)
        and all(r["ruta"] == os.path.join(carpeta, r["nombre"]) for r in incorporar)
        and all(r["extension"] == os.path.splitext(r["nombre"])[1].lower() for r in incorporar)
        and incorporar[0]["fecha_importacion"] == incorporar[1]["fecha_importacion"]
    )
    return ok, f"incorporar={incorporar}"


def test_06():
    temp_carpeta, carpeta = _crear_carpeta([])
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, ["z.mp4", "a.mp4"], ["m.mkv", "b.mkv"], ["y.avi", "x.avi"])
        )
    finally:
        temp_carpeta.cleanup()
    ok = (
        [r["nombre"] for r in plan["a_incorporar"]] == ["b.mkv", "m.mkv"]
        and plan["ya_sincronizados"] == ["a.mp4", "z.mp4"]
        and plan["candidatos_a_eliminar"] == ["x.avi", "y.avi"]
    )
    return (
        ok,
        f"incorporar={[r['nombre'] for r in plan['a_incorporar']]} "
        f"ya={plan['ya_sincronizados']} candidatos={plan['candidatos_a_eliminar']}",
    )


def test_07():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    diferencias = _diferencias(carpeta, ["a.mp4"], ["b.mkv"], ["d.mp4"])
    try:
        plan_a = escanear_mod.preparar_plan_sincronizacion(diferencias)
        plan_b = escanear_mod.preparar_plan_sincronizacion(diferencias)
    finally:
        temp_carpeta.cleanup()
    nombres_a = [r["nombre"] for r in plan_a["a_incorporar"]]
    nombres_b = [r["nombre"] for r in plan_b["a_incorporar"]]
    ok = (
        nombres_a == nombres_b
        and plan_a["ya_sincronizados"] == plan_b["ya_sincronizados"]
        and plan_a["candidatos_a_eliminar"] == plan_b["candidatos_a_eliminar"]
        and plan_a["carpeta"] == plan_b["carpeta"]
    )
    return ok, f"determinista={ok} nombres={nombres_a}"


def test_08():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        with open(ruta_db, "rb") as f:
            bytes_antes = f.read()
        dump_antes = _dump_bd(ruta_db)
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, ["a.mp4"], ["b.mkv"], ["c.avi"])
        )
        with open(ruta_db, "rb") as f:
            bytes_despues = f.read()
        dump_despues = _dump_bd(ruta_db)
        rastro = [n for n in os.listdir(temp_bd.name) if n != "catalogo.db"]
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        plan["a_incorporar"][0]["nombre"] == "b.mkv"
        and plan["candidatos_a_eliminar"] == ["c.avi"]
        and bytes_despues == bytes_antes
        and dump_despues == dump_antes
        and rastro == []
    )
    return (
        ok,
        f"bytes_iguales={bytes_despues == bytes_antes} "
        f"dump_igual={dump_despues == dump_antes} archivos_en_bd={rastro}",
    )


def test_09():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    llamadas = {
        "connect": 0,
        "sincronizar": 0,
        "insertar": 0,
        "actualizar": 0,
        "upsert": 0,
        "guardar_video": 0,
        "guardar_videos": 0,
    }
    originales = {
        "sqlite3.connect": escanear_mod.sqlite3.connect,
        "sincronizar_bd": escanear_mod.sincronizar_bd,
        "insertar_video": escanear_mod.insertar_video,
        "actualizar_datos": escanear_mod.actualizar_datos,
        "_upsert_video": escanear_mod._upsert_video,
        "guardar_video": escanear_mod.guardar_video,
        "guardar_videos": escanear_mod.guardar_videos,
    }

    def _connect(*args, **kwargs):
        llamadas["connect"] += 1
        raise AssertionError("no debe abrirse SQLite")

    def _prohibido(clave):
        def _fn(*args, **kwargs):
            llamadas[clave] += 1
            raise AssertionError(f"no debe ejecutarse {clave}")
        return _fn

    escanear_mod.sqlite3.connect = _connect
    escanear_mod.sincronizar_bd = _prohibido("sincronizar")
    escanear_mod.insertar_video = _prohibido("insertar")
    escanear_mod.actualizar_datos = _prohibido("actualizar")
    escanear_mod._upsert_video = _prohibido("upsert")
    escanear_mod.guardar_video = _prohibido("guardar_video")
    escanear_mod.guardar_videos = _prohibido("guardar_videos")
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, ["a.mp4"], ["b.mkv"], ["c.avi"])
        )
    finally:
        for clave, original in originales.items():
            if "." in clave:
                modulo, atributo = clave.split(".", 1)
                setattr(getattr(escanear_mod, modulo), atributo, original)
            else:
                setattr(escanear_mod, clave, original)
    temp_carpeta.cleanup()
    temp_bd.cleanup()
    ok = (
        plan["a_incorporar"][0]["nombre"] == "b.mkv"
        and plan["candidatos_a_eliminar"] == ["c.avi"]
        and llamadas == {
            "connect": 0,
            "sincronizar": 0,
            "insertar": 0,
            "actualizar": 0,
            "upsert": 0,
            "guardar_video": 0,
            "guardar_videos": 0,
        }
    )
    return ok, f"llamadas={llamadas}"


def test_10():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    llamadas = {
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
        "obtener_datos_ffprobe": escanear_mod.obtener_datos_ffprobe,
        "ffmpeg_disponible": escanear_mod.ffmpeg_disponible,
        "subprocess.run": escanear_mod.subprocess.run,
        "asegurar_miniatura": escanear_mod.asegurar_miniatura,
        "asegurar_miniaturas": escanear_mod.asegurar_miniaturas,
        "contar_miniaturas": escanear_mod.contar_miniaturas,
        "generar_miniatura": escanear_mod.generar_miniatura,
    }

    escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
    escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg")
    escanear_mod.subprocess.run = _prohibido("subprocess")
    escanear_mod.asegurar_miniatura = _prohibido("asegurar_miniatura")
    escanear_mod.asegurar_miniaturas = _prohibido("asegurar_miniaturas")
    escanear_mod.contar_miniaturas = _prohibido("contar")
    escanear_mod.generar_miniatura = _prohibido("generar")
    try:
        plan = escanear_mod.preparar_plan_sincronizacion(
            _diferencias(carpeta, [], ["a.mp4", "b.mkv"], [])
        )
    finally:
        for clave, original in originales.items():
            if "." in clave:
                modulo, atributo = clave.split(".", 1)
                setattr(getattr(escanear_mod, modulo), atributo, original)
            else:
                setattr(escanear_mod, clave, original)
    temp_carpeta.cleanup()
    ok = (
        [r["nombre"] for r in plan["a_incorporar"]] == ["a.mp4", "b.mkv"]
        and llamadas == {
            "ffprobe": 0,
            "ffmpeg": 0,
            "subprocess": 0,
            "asegurar_miniatura": 0,
            "asegurar_miniaturas": 0,
            "contar": 0,
            "generar": 0,
        }
    )
    return ok, f"llamadas={llamadas}"


def test_11():
    temp_carpeta, carpeta = _crear_carpeta([])
    fallos = {
        "no_dict": False,
        "no_dict_lista": False,
        "clave": False,
        "carpeta_vacia": False,
        "carpeta_no_texto": False,
        "nuevos_texto": False,
        "presentes_no_iterable": False,
        "ausentes_none": False,
        "extra_ignorada": False,
    }
    try:
        try:
            escanear_mod.preparar_plan_sincronizacion(None)
        except TypeError:
            fallos["no_dict"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(["carpeta", "x"])
        except TypeError:
            fallos["no_dict_lista"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias(carpeta, [], [], []) | {"carpeta_extra": "x"}
            )
        except (TypeError, ValueError):
            pass
        else:
            fallos["extra_ignorada"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                {clave: valor for clave, valor in _diferencias(carpeta, [], [], []).items() if clave != "nuevos"}
            )
        except ValueError:
            fallos["clave"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias("", [], [], [])
            )
        except ValueError:
            fallos["carpeta_vacia"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias(None, [], [], [])
            )
        except ValueError:
            fallos["carpeta_no_texto"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias(carpeta, [], "a.mp4", [])
            )
        except TypeError:
            fallos["nuevos_texto"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias(carpeta, 5, [], [])
            )
        except TypeError:
            fallos["presentes_no_iterable"] = True
        try:
            escanear_mod.preparar_plan_sincronizacion(
                _diferencias(carpeta, [], [], None)
            )
        except TypeError:
            fallos["ausentes_none"] = True
    finally:
        temp_carpeta.cleanup()
    ok = all(fallos.values())
    return ok, f"validaciones={fallos}"


def test_12():
    bd = ruta_biblioteca()
    miniaturas = ruta_carpeta_miniaturas()
    videos = ruta_carpeta_videos()

    def estado_real():
        return (
            os.path.getmtime(bd) if os.path.isfile(bd) else None,
            os.path.getsize(bd) if os.path.isfile(bd) else None,
            sorted(os.listdir(miniaturas)) if os.path.isdir(miniaturas) else None,
            sorted(os.listdir(videos)) if os.path.isdir(videos) else None,
        )

    antes = estado_real()
    diferencias = escanear_mod.detectar_diferencias(videos, bd)
    plan = escanear_mod.preparar_plan_sincronizacion(diferencias)
    despues = estado_real()

    nombres_incorporar = [r["nombre"] for r in plan["a_incorporar"]]
    ok = (
        plan["carpeta"] == videos
        and set(nombres_incorporar) == set(diferencias["nuevos"])
        and plan["ya_sincronizados"] == diferencias["presentes_en_ambos"]
        and plan["candidatos_a_eliminar"] == diferencias["ausentes_del_disco"]
        and len(plan["a_incorporar"]) + len(plan["ya_sincronizados"]) + len(plan["candidatos_a_eliminar"])
        == len(set(diferencias["nuevos"]) | set(diferencias["presentes_en_ambos"]) | set(diferencias["ausentes_del_disco"]))
        and antes == despues
    )
    return (
        ok,
        f"incorporar={nombres_incorporar} ya={plan['ya_sincronizados']} "
        f"candidatos={plan['candidatos_a_eliminar']} datos_reales_sin_cambios={antes == despues}",
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
    print(f"TOTAL={aprobadas}/12")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
