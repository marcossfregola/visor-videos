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


def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "rutas.py",
        "prueba_detectar.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    ruta_raiz = os.path.dirname(os.path.abspath(__file__))
    con_escaneo = open(os.path.join(ruta_raiz, "escanear_videos.py"), encoding="utf-8")
    try:
        arbol_escaneo = ast.parse(con_escaneo.read(), "escanear_videos.py")
    finally:
        con_escaneo.close()
    con_tareas = open(os.path.join(ruta_raiz, "tareas_videos.py"), encoding="utf-8")
    try:
        arbol_tareas = ast.parse(con_tareas.read(), "tareas_videos.py")
    finally:
        con_tareas.close()
    con_visor = open(os.path.join(ruta_raiz, "visor_videos.py"), encoding="utf-8")
    try:
        arbol_visor = ast.parse(con_visor.read(), "visor_videos.py")
    finally:
        con_visor.close()

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

    funcs_escaneo = _funciones(arbol_escaneo)
    funcs_tareas = _funciones(arbol_tareas)
    clases_tareas = _clases(arbol_tareas)
    importados_tareas = _nombres_importados(arbol_tareas)
    importados_visor = _nombres_importados(arbol_visor)
    ok = (
        "detectar_diferencias" in funcs_escaneo
        and "detectar_diferencias" not in funcs_tareas
        and "detectar_diferencias" not in importados_tareas
        and "detectar_diferencias" not in importados_visor
        and not any("Detectar" in c for c in clases_tareas)
    )
    return (
        ok,
        f"def_escaneo={'detectar_diferencias' in funcs_escaneo} "
        f"def_tareas={'detectar_diferencias' in funcs_tareas} "
        f"import_tareas={'detectar_diferencias' in importados_tareas} "
        f"import_visor={'detectar_diferencias' in importados_visor}",
    )


def test_03():
    temp_carpeta, carpeta = _crear_carpeta([])
    temp_bd, ruta_db = _crear_bd([])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["carpeta"] == carpeta
        and resultado["presentes_en_ambos"] == []
        and resultado["nuevos"] == []
        and resultado["ausentes_del_disco"] == []
    )
    return ok, f"resultado={resultado}"


def test_04():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd([])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["presentes_en_ambos"] == []
        and resultado["nuevos"] == ["a.mp4", "b.mkv"]
        and resultado["ausentes_del_disco"] == []
    )
    return ok, f"nuevos={resultado['nuevos']}"


def test_05():
    temp_carpeta, carpeta = _crear_carpeta([])
    temp_bd, ruta_db = _crear_bd(["x.mp4", "y.avi"])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["presentes_en_ambos"] == []
        and resultado["nuevos"] == []
        and resultado["ausentes_del_disco"] == ["x.mp4", "y.avi"]
    )
    return ok, f"ausentes={resultado['ausentes_del_disco']}"


def test_06():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "b.mkv"])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["presentes_en_ambos"] == ["a.mp4", "b.mkv"]
        and resultado["nuevos"] == []
        and resultado["ausentes_del_disco"] == []
    )
    return ok, f"presentes={resultado['presentes_en_ambos']}"


def test_07():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv", "c.avi"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi", "d.mp4"])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["presentes_en_ambos"] == ["a.mp4", "c.avi"]
        and resultado["nuevos"] == ["b.mkv"]
        and resultado["ausentes_del_disco"] == ["d.mp4"]
    )
    return ok, f"presentes={resultado['presentes_en_ambos']} nuevos={resultado['nuevos']} ausentes={resultado['ausentes_del_disco']}"


def test_08():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv", "c.avi"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi", "d.mp4"])
    try:
        dump_antes = _dump_bd(ruta_db)
        nombres_antes = sorted(os.listdir(carpeta))
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
        dump_despues = _dump_bd(ruta_db)
        nombres_despues = sorted(os.listdir(carpeta))
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["nuevos"] == ["b.mkv"]
        and resultado["ausentes_del_disco"] == ["d.mp4"]
        and dump_despues == dump_antes
        and nombres_despues == nombres_antes
    )
    return (
        ok,
        f"filas_antes={len(dump_antes)} filas_despues={len(dump_despues)} "
        f"contenido_igual={dump_despues == dump_antes} "
        f"carpeta_igual={nombres_despues == nombres_antes}",
    )


def test_09():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    try:
        with open(ruta_db, "rb") as f:
            bytes_antes = f.read()
        escanear_mod.detectar_diferencias(carpeta, ruta_db)
        with open(ruta_db, "rb") as f:
            bytes_despues = f.read()
        rastro = [
            n for n in os.listdir(temp_bd.name)
            if n != "catalogo.db"
        ]
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = bytes_despues == bytes_antes and rastro == []
    return (
        ok,
        f"bytes_iguales={bytes_despues == bytes_antes} "
        f"archivos_en_bd={rastro}",
    )


def test_10():
    temp_carpeta, carpeta = _crear_carpeta(["z.mp4", "a.mp4", "m.mkv"])
    temp_bd, ruta_db = _crear_bd(["m.mkv", "z.mp4", "a.mp4"])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        resultado["presentes_en_ambos"] == sorted(resultado["presentes_en_ambos"])
        and resultado["nuevos"] == sorted(resultado["nuevos"])
        and resultado["ausentes_del_disco"] == sorted(resultado["ausentes_del_disco"])
        and resultado["presentes_en_ambos"] == ["a.mp4", "m.mkv", "z.mp4"]
        and resultado["nuevos"] == []
        and resultado["ausentes_del_disco"] == []
    )
    return ok, f"resultado={resultado}"


def test_11():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4"])
    temp_bd, ruta_db = _crear_bd(["a.mp4"])
    base = os.path.dirname(carpeta)
    carpeta_inexistente = os.path.join(base, "carpeta_que_no_existe")
    ruta_db_inexistente = os.path.join(base, "no_existe.db")
    fallos = {"texto": False, "vacio": False, "carpeta": False, "bd": False}
    nombres_bd = None
    try:
        try:
            escanear_mod.detectar_diferencias(None, ruta_db)
        except ValueError:
            fallos["texto"] = True
        try:
            escanear_mod.detectar_diferencias("", ruta_db)
        except ValueError:
            fallos["vacio"] = True
        try:
            escanear_mod.detectar_diferencias(carpeta_inexistente, ruta_db)
        except FileNotFoundError as exc:
            fallos["carpeta"] = "Carpeta no encontrada" in str(exc)
        try:
            escanear_mod.detectar_diferencias(carpeta, ruta_db_inexistente)
        except FileNotFoundError as exc:
            fallos["bd"] = "Base de datos no encontrada" in str(exc)
        nombres_bd = _nombres_bd(ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = (
        all(fallos.values())
        and not os.path.exists(ruta_db_inexistente)
        and nombres_bd == ["a.mp4"]
    )
    return ok, f"validaciones={fallos} bd_no_creada={not os.path.exists(ruta_db_inexistente)}"


def test_12():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    temp_bd, ruta_db = _crear_bd(["a.mp4", "c.avi"])
    llamadas = {
        "ffprobe": 0,
        "ffmpeg": 0,
        "subprocess": 0,
        "asegurar": 0,
        "contar": 0,
        "generar": 0,
        "sincronizar": 0,
    }
    originales = {
        "ffprobe": escanear_mod.obtener_datos_ffprobe,
        "ffmpeg": escanear_mod.ffmpeg_disponible,
        "subprocess": escanear_mod.subprocess.run,
        "asegurar": escanear_mod.asegurar_miniatura,
        "contar": escanear_mod.contar_miniaturas,
        "generar": escanear_mod.generar_miniatura,
        "sincronizar": escanear_mod.sincronizar_bd,
    }

    def _prohibido(clave):
        def _fn(*args, **kwargs):
            llamadas[clave] += 1
            raise AssertionError(f"no debe ejecutarse {clave}")
        return _fn

    escanear_mod.obtener_datos_ffprobe = _prohibido("ffprobe")
    escanear_mod.ffmpeg_disponible = _prohibido("ffmpeg")
    escanear_mod.subprocess.run = _prohibido("subprocess")
    escanear_mod.asegurar_miniatura = _prohibido("asegurar")
    escanear_mod.contar_miniaturas = _prohibido("contar")
    escanear_mod.generar_miniatura = _prohibido("generar")
    escanear_mod.sincronizar_bd = _prohibido("sincronizar")
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        for clave, original in originales.items():
            setattr(escanear_mod, clave, original)
    temp_carpeta.cleanup()
    temp_bd.cleanup()
    ok = (
        resultado["nuevos"] == ["b.mkv"]
        and resultado["ausentes_del_disco"] == ["c.avi"]
        and llamadas == {
            "ffprobe": 0,
            "ffmpeg": 0,
            "subprocess": 0,
            "asegurar": 0,
            "contar": 0,
            "generar": 0,
            "sincronizar": 0,
        }
    )
    return ok, f"llamadas={llamadas} resultado={resultado}"


def test_13():
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
    temp_carpeta, carpeta = _crear_carpeta(["x.mp4"])
    temp_bd, ruta_db = _crear_bd(["x.mp4"])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    despues = estado_real()
    ok = (
        resultado["presentes_en_ambos"] == ["x.mp4"]
        and antes == despues
    )
    return ok, f"datos_reales_sin_cambios={antes == despues}"


def test_14():
    carpeta = ruta_carpeta_videos()
    ruta_db = ruta_biblioteca()
    en_disco = set(escanear_mod.escanear_videos(carpeta))
    en_bd = set(_nombres_bd(ruta_db))
    resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    presentes = set(resultado["presentes_en_ambos"])
    nuevos = set(resultado["nuevos"])
    ausentes = set(resultado["ausentes_del_disco"])
    ok = (
        presentes | nuevos == en_disco
        and presentes | ausentes == en_bd
        and not (presentes & nuevos)
        and not (presentes & ausentes)
        and not (nuevos & ausentes)
    )
    return (
        ok,
        f"presentes={resultado['presentes_en_ambos']} "
        f"nuevos={resultado['nuevos']} "
        f"ausentes={resultado['ausentes_del_disco']} "
        f"consistencia={presentes | nuevos == en_disco}",
    )


def test_15():
    temp_carpeta, carpeta = _crear_carpeta(["a.mp4", "notas.txt", "imagen.png", "sin_ext", "b.AVI"])
    temp_bd, ruta_db = _crear_bd([])
    try:
        resultado = escanear_mod.detectar_diferencias(carpeta, ruta_db)
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()
    ok = resultado["nuevos"] == ["a.mp4", "b.AVI"]
    return ok, f"nuevos={resultado['nuevos']}"


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
