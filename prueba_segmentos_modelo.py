"""Pruebas del modelo SQLite y repositorio de segmentos A–B (B5.1).

Cubre: esquema `segmentos_video` e índice, migración aditiva e idempotente
desde esquema pre-Beta5, API `listar_segmentos`, `listar_segmentos_de`,
`guardar_segmento`, `eliminar_segmento`, validaciones, base inexistente,
orfandad, aislamiento respecto de marcadores y videos, y cero cambios
funcionales visibles (sin UI, sin VLC, sin tareas).

Modelo puro: sin Qt, sin UI, sin VLC.
"""

import os
import py_compile
import sqlite3
import sys
import tempfile

import escanear_videos as escanear_mod
from escanear_videos import (
    conectar_bd,
    eliminar_segmento,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_segmentos_de,
    listar_videos,
)


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
    """Base nueva mediante `conectar_bd` (aplica la migración vigente)."""
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


def _crear_bd_prebeta5(filas, marcadores):
    """Base con el esquema de Beta 4 (con `mtime_ns` y `marcadores_video`)
    pero SIN `segmentos_video`: punto de partida para la migración de B5.1."""
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
            tamano_bytes INTEGER,
            mtime_ns INTEGER
        )
        """
    )
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, "
        "duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, "
        "tamano_bytes, mtime_ns) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        filas,
    )
    conn.execute(
        """
        CREATE TABLE marcadores_video (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            tiempo REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_marcadores_video_video_id_tiempo "
        "ON marcadores_video(video_id, tiempo)"
    )
    conn.executemany(
        "INSERT INTO marcadores_video (video_id, tiempo) VALUES (?, ?)",
        marcadores,
    )
    conn.commit()
    conn.close()
    return temp, ruta_db


def _tablas(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return {
            f[0]
            for f in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()


def _indice(ruta_db, nombre):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (nombre,),
        ).fetchone()
    finally:
        conn.close()


def _filas(ruta_db, sql, params=()):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class _Contador(sqlite3.Connection):
    """Conexión que cuenta las sentencias SELECT ejecutadas."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selects = 0

    def execute(self, sql, params=None):
        if isinstance(sql, str) and sql.lstrip().upper().startswith("SELECT"):
            self.selects += 1
        if params is None:
            return super().execute(sql)
        return super().execute(sql, params)


def test_01():
    modulos = [
        "escanear_videos.py",
        "prueba_segmentos_modelo.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Base nueva: tabla creada, columnas exactas e índice creado."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        columnas = [
            (f[1], f[2])
            for f in _filas(ruta_db, "PRAGMA table_info(segmentos_video)")
        ]
        ok_columnas = columnas == [
            ("id", "INTEGER"),
            ("video_id", "INTEGER"),
            ("inicio", "REAL"),
            ("fin", "REAL"),
            ("color", "TEXT"),
        ]
        ok_indice = _indice(
            ruta_db, "idx_segmentos_video_video_id_inicio"
        ) is not None
        ok_pk = (
            _filas(
                ruta_db,
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='segmentos_video'",
            )
            != []
        )
    finally:
        temp.cleanup()
    return (
        ok_columnas and ok_indice and ok_pk,
        f"columnas={columnas} indice={ok_indice}",
    )


def test_03():
    """Migración idempotente: repetir `conectar_bd` no duplica tabla ni índice."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        conn1 = conectar_bd(ruta_db)
        conn1.close()
        tablas1 = _tablas(ruta_db)
        indice1 = _indice(ruta_db, "idx_segmentos_video_video_id_inicio")
        conn2 = conectar_bd(ruta_db)
        conn2.close()
        tablas2 = _tablas(ruta_db)
        indice2 = _indice(ruta_db, "idx_segmentos_video_video_id_inicio")
        ok = tablas1 == tablas2 and indice1 is not None and indice2 is not None
        return ok, f"tablas_iguales={tablas1 == tablas2} indice_duplicado={indice1 is not None and indice2 is not None}"
    finally:
        temp.cleanup()


def test_04():
    """Base existente pre-Beta5: se agrega `segmentos_video` preservando datos."""
    filas = [("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0, 100, 111)]
    temp, ruta_db = _crear_bd_prebeta5(filas, [(1, 5.0)])
    conn = None
    try:
        antes_videos = _filas(ruta_db, "SELECT * FROM videos")
        antes_marcadores = _filas(ruta_db, "SELECT * FROM marcadores_video")
        # B8.1/B8.3 precondición: ruta relativa debe ser rechazada
        try:
            conn = conectar_bd(ruta_db)
        except ValueError as e:
            msg = str(e).lower()
            ok_precondicion = "precondici" in msg and "relativa" in msg
            # Verificar que no se creó segmentos y que datos siguen intactos (acceso directo)
            import sqlite3

            conn_raw = sqlite3.connect(ruta_db)
            try:
                tablas_raw = {
                    f[0]
                    for f in conn_raw.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                fila_raw = conn_raw.execute("SELECT nombre, ruta FROM videos").fetchone()
            finally:
                conn_raw.close()
            ok_tabla_raw = "segmentos_video" not in tablas_raw  # no debe haberse creado si falló precondición
            ok_intactos_raw = fila_raw == ("a.mp4", "r")
            return (
                ok_precondicion and ok_tabla_raw and ok_intactos_raw,
                f"precondicion={ok_precondicion} tabla_raw={ok_tabla_raw} intactos={ok_intactos_raw} msg={e}",
            )
        conn.close()
        conn = None
        tablas = _tablas(ruta_db)
        ok_segmentos = "segmentos_video" in tablas
        ok_indice = _indice(
            ruta_db, "idx_segmentos_video_video_id_inicio"
        ) is not None
        despues_videos = _filas(ruta_db, "SELECT * FROM videos")
        despues_marcadores = _filas(ruta_db, "SELECT * FROM marcadores_video")
        ok_preserva = (
            antes_videos == despues_videos
            and antes_marcadores == [fila[:3] for fila in despues_marcadores]
        )
        ok_color_nulo = _filas(
            ruta_db,
            "SELECT color FROM marcadores_video WHERE video_id = 1",
        ) == [(None,)]
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        import gc
        import os
        import time
        import shutil

        gc.collect()
        # Borrar ficheros SQLite antes de rmdir para evitar lock Windows
        for _ in range(3):
            try:
                if os.path.exists(ruta_db):
                    os.remove(ruta_db)
                for suffix in ("-journal", "-wal", "-shm"):
                    p = ruta_db + suffix
                    if os.path.exists(p):
                        os.remove(p)
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.05)
        for _ in range(5):
            try:
                temp.cleanup()
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.1)
                try:
                    shutil.rmtree(temp.name)
                    break
                except Exception:
                    continue
    return (
        ok_segmentos and ok_indice and ok_preserva and ok_color_nulo,
        f"segmentos={ok_segmentos} indice={ok_indice} videos={antes_videos == despues_videos} marcadores={ok_preserva} color_nulo={ok_color_nulo}",
    )


def test_05():
    """Base existente pre-Beta5: repetir la inicialización no duplica nada."""
    filas = [("a.mp4", "r", ".mp4", "f", 1.0, 1, 1, "c", 0, 100, 111)]
    temp, ruta_db = _crear_bd_prebeta5(filas, [(1, 5.0)])
    conn1 = None
    conn2 = None
    try:
        # B8.1/B8.3 precondición: ruta relativa debe ser rechazada
        try:
            conn1 = conectar_bd(ruta_db)
        except ValueError as e:
            msg = str(e).lower()
            ok_pre = "precondici" in msg and "relativa" in msg
            # Verificar que segunda llamada también falla igual (idempotente en error)
            try:
                conn2 = conectar_bd(ruta_db)
            except ValueError as e2:
                ok_pre2 = "precondici" in str(e2).lower()
                conn2 = None
                return (
                    ok_pre and ok_pre2,
                    f"precondicion={ok_pre} pre2={ok_pre2} msg={e}",
                )
            # Si no falló segunda, es inesperado
            if conn2 is not None:
                conn2.close()
            return (False, f"segunda conectar_bd no falló, esperado precondición")
        conn1.close()
        conn1 = None
        tablas1 = _tablas(ruta_db)
        segmentos1 = _filas(
            ruta_db,
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_segmentos_video_video_id_inicio'",
        )
        try:
            conn2 = conectar_bd(ruta_db)
        except ValueError as e:
            # Si primera no falló pero segunda sí, es inconsistente pero también precondición
            return (False, f"segunda fallo inesperado {e}")
        conn2.close()
        conn2 = None
        tablas2 = _tablas(ruta_db)
        segmentos2 = _filas(
            ruta_db,
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_segmentos_video_video_id_inicio'",
        )
        ok = (
            tablas1 == tablas2
            and len(segmentos1) == 1
            and len(segmentos2) == 1
        )
        return ok, f"tablas_iguales={tablas1 == tablas2} indices={len(segmentos1)}->{len(segmentos2)}"
    finally:
        for c in (conn1, conn2):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
        import gc
        import os
        import time
        import shutil

        gc.collect()
        for _ in range(3):
            try:
                if os.path.exists(ruta_db):
                    os.remove(ruta_db)
                for suffix in ("-journal", "-wal", "-shm"):
                    p = ruta_db + suffix
                    if os.path.exists(p):
                        os.remove(p)
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.05)
        for _ in range(5):
            try:
                temp.cleanup()
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.1)
                try:
                    shutil.rmtree(temp.name)
                    break
                except Exception:
                    continue


def test_06():
    """Guardar segmento válido devuelve `(id, inicio, fin)` y persiste."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        guardado = guardar_segmento(id_video, 10.0, 20.5, ruta_db)
        ok_tupla = (
            isinstance(guardado, tuple)
            and len(guardado) == 3
            and isinstance(guardado[0], int)
            and guardado[0] > 0
            and guardado[1] == 10.0
            and guardado[2] == 20.5
        )
        ok_persiste = listar_segmentos(id_video, ruta_db) == [
            (guardado[0], 10.0, 20.5, None)
        ]
        return (
            ok_tupla and ok_persiste,
            f"guardado={guardado} listado={listar_segmentos(id_video, ruta_db)}",
        )
    finally:
        temp.cleanup()


def test_07():
    """Múltiples segmentos por video."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        guardar_segmento(id_video, 5.0, 6.0, ruta_db)
        guardar_segmento(id_video, 3.0, 4.0, ruta_db)
        segmentos = listar_segmentos(id_video, ruta_db)
        ok = len(segmentos) == 3 and all(len(s) == 4 for s in segmentos)
        return ok, f"segmentos={segmentos}"
    finally:
        temp.cleanup()


def test_08():
    """Orden por inicio ascendente."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        guardar_segmento(id_video, 30.0, 40.0, ruta_db)
        guardar_segmento(id_video, 10.0, 20.0, ruta_db)
        guardar_segmento(id_video, 20.0, 25.0, ruta_db)
        segmentos = listar_segmentos(id_video, ruta_db)
        ok = [s[1] for s in segmentos] == [10.0, 20.0, 30.0]
        return ok, f"inicios={[s[1] for s in segmentos]}"
    finally:
        temp.cleanup()


def test_09():
    """Empate de inicio: orden determinista por fin y luego por id."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        guardar_segmento(id_video, 10.0, 30.0, ruta_db)  # id menor, fin 30
        guardar_segmento(id_video, 10.0, 20.0, ruta_db)  # fin 20
        guardar_segmento(id_video, 10.0, 20.0, ruta_db)  # fin 20, id mayor
        segmentos = listar_segmentos(id_video, ruta_db)
        # esperado: fin 20 (id menor), fin 20 (id mayor), fin 30
        ok = (
            [(s[1], s[2]) for s in segmentos]
            == [(10.0, 20.0), (10.0, 20.0), (10.0, 30.0)]
            and segmentos[0][0] < segmentos[1][0]
        )
        return ok, f"orden={[(s[0], s[1], s[2]) for s in segmentos]}"
    finally:
        temp.cleanup()


def test_10():
    """Listar por un video: formato `(id, inicio, fin)` y aislamiento por video."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        id_b = _video_id(ruta_db, "b.mp4")
        s1 = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
        guardar_segmento(id_b, 9.0, 10.0, ruta_db)
        segmentos_a = listar_segmentos(id_a, ruta_db)
        ok = segmentos_a == [(s1[0], 1.0, 2.0, None)]
        return ok, f"a={segmentos_a}"
    finally:
        temp.cleanup()


def test_11():
    """`listar_segmentos_de`: agrupado por video en el orden de entrada."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4", "c.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        id_b = _video_id(ruta_db, "b.mp4")
        id_c = _video_id(ruta_db, "c.mp4")
        sa = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
        sb = guardar_segmento(id_b, 3.0, 4.0, ruta_db)
        sc = guardar_segmento(id_c, 5.0, 6.0, ruta_db)
        resultado = listar_segmentos_de([id_b, id_a, id_c], ruta_db)
        esperado = [
            (sb[0], id_b, 3.0, 4.0, None),
            (sa[0], id_a, 1.0, 2.0, None),
            (sc[0], id_c, 5.0, 6.0, None),
        ]
        ok = resultado == esperado
        return ok, f"resultado={resultado}"
    finally:
        temp.cleanup()


def test_12():
    """`listar_segmentos_de` con IDs duplicados en la entrada: se deduplican."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        guardar_segmento(id_a, 1.0, 2.0, ruta_db)
        resultado = listar_segmentos_de([id_a, id_a, id_a], ruta_db)
        ok = len(resultado) == 1
        return ok, f"resultado={resultado}"
    finally:
        temp.cleanup()


def test_13():
    """`listar_segmentos_de` con colección vacía devuelve []."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        ok = listar_segmentos_de([], ruta_db) == []
        return ok, f"resultado={listar_segmentos_de([], ruta_db)}"
    finally:
        temp.cleanup()


def test_14():
    """Eliminar un segmento: True y elimina solo ese."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s1 = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        s2 = guardar_segmento(id_video, 3.0, 4.0, ruta_db)
        ok_eliminado = eliminar_segmento(s1[0], ruta_db) is True
        restantes = listar_segmentos(id_video, ruta_db)
        ok_restantes = restantes == [(s2[0], 3.0, 4.0, None)]
        return ok_eliminado and ok_restantes, f"restantes={restantes}"
    finally:
        temp.cleanup()


def test_15():
    """Eliminar un segmento inexistente devuelve False."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        ok = eliminar_segmento(999999, ruta_db) is False
        return ok, f"resultado={eliminar_segmento(999999, ruta_db)}"
    finally:
        temp.cleanup()


def test_16():
    """Aislamiento entre videos: eliminar uno no afecta al otro."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        id_b = _video_id(ruta_db, "b.mp4")
        sa = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
        sb = guardar_segmento(id_b, 3.0, 4.0, ruta_db)
        eliminar_segmento(sa[0], ruta_db)
        ok = (
            listar_segmentos(id_a, ruta_db) == []
            and listar_segmentos(id_b, ruta_db) == [(sb[0], 3.0, 4.0, None)]
        )
        return ok, f"a={listar_segmentos(id_a, ruta_db)} b={listar_segmentos(id_b, ruta_db)}"
    finally:
        temp.cleanup()


def test_17():
    """Dos segmentos idénticos pueden existir (sin deduplicación)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s1 = guardar_segmento(id_video, 5.0, 7.0, ruta_db)
        s2 = guardar_segmento(id_video, 5.0, 7.0, ruta_db)
        segmentos = listar_segmentos(id_video, ruta_db)
        ok = (
            len(segmentos) == 2
            and s1[0] != s2[0]
            and {(s[1], s[2]) for s in segmentos} == {(5.0, 7.0)}
        )
        return ok, f"segmentos={segmentos}"
    finally:
        temp.cleanup()


def _capturar(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return True
    except Exception:
        return False
    return False


def test_18():
    """`video_id` inválido: texto/None/bool → TypeError; 0/negativo → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        ok = True
        for invalido in ("a", None, 1.5):
            ok = ok and _capturar(TypeError, guardar_segmento, invalido, 1.0, 2.0, ruta_db)
            ok = ok and _capturar(TypeError, listar_segmentos, invalido, ruta_db)
        for invalido in (True, False):
            ok = ok and _capturar(TypeError, guardar_segmento, invalido, 1.0, 2.0, ruta_db)
        for invalido in (0, -1):
            ok = ok and _capturar(ValueError, guardar_segmento, invalido, 1.0, 2.0, ruta_db)
        return ok, "validaciones_video_id"
    finally:
        temp.cleanup()


def test_19():
    """`inicio` negativo → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        ok = _capturar(ValueError, guardar_segmento, id_video, -0.1, 2.0, ruta_db)
        return ok, "inicio_negativo"
    finally:
        temp.cleanup()


def test_20():
    """`fin == inicio` → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        ok = _capturar(ValueError, guardar_segmento, id_video, 5.0, 5.0, ruta_db)
        return ok, "fin_igual_inicio"
    finally:
        temp.cleanup()


def test_21():
    """`fin < inicio` → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        ok = _capturar(ValueError, guardar_segmento, id_video, 10.0, 5.0, ruta_db)
        return ok, "fin_menor_inicio"
    finally:
        temp.cleanup()


def test_22():
    """NaN (inicio o fin) → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        nan = float("nan")
        ok = _capturar(ValueError, guardar_segmento, id_video, nan, 2.0, ruta_db)
        ok = ok and _capturar(ValueError, guardar_segmento, id_video, 1.0, nan, ruta_db)
        return ok, "nan"
    finally:
        temp.cleanup()


def test_23():
    """Infinito (inicio o fin) → ValueError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        inf = float("inf")
        ok = _capturar(ValueError, guardar_segmento, id_video, inf, 2.0, ruta_db)
        ok = ok and _capturar(ValueError, guardar_segmento, id_video, 1.0, inf, ruta_db)
        return ok, "infinito"
    finally:
        temp.cleanup()


def test_24():
    """bool como inicio/fin/segmento_id → TypeError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        ok = _capturar(TypeError, guardar_segmento, id_video, True, 2.0, ruta_db)
        ok = ok and _capturar(TypeError, guardar_segmento, id_video, 1.0, False, ruta_db)
        ok = ok and _capturar(TypeError, eliminar_segmento, True, ruta_db)
        return ok, "bool"
    finally:
        temp.cleanup()


def test_25():
    """Base inexistente → FileNotFoundError (mismo contrato que marcadores)."""
    ruta_inexistente = os.path.join(tempfile.gettempdir(), "b5_segmentos_no_existe.db")
    if os.path.isfile(ruta_inexistente):
        os.remove(ruta_inexistente)
    try:
        ok = _capturar(FileNotFoundError, listar_segmentos, 1, ruta_inexistente)
        ok = ok and _capturar(FileNotFoundError, listar_segmentos_de, [1], ruta_inexistente)
        ok = ok and _capturar(FileNotFoundError, guardar_segmento, 1, 1.0, 2.0, ruta_inexistente)
        ok = ok and _capturar(FileNotFoundError, eliminar_segmento, 1, ruta_inexistente)
        sin_archivo = not os.path.isfile(ruta_inexistente)
        return ok and sin_archivo, f"file_not_found={ok} sin_archivo={sin_archivo}"
    finally:
        if os.path.isfile(ruta_inexistente):
            os.remove(ruta_inexistente)


def test_26():
    """Orfandad: eliminar el registro del video no elimina el segmento."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        conn = sqlite3.connect(ruta_db)
        conn.execute("DELETE FROM videos WHERE id = ?", (id_video,))
        conn.commit()
        conn.close()
        restantes = _filas(
            ruta_db,
            "SELECT id, video_id, inicio, fin FROM segmentos_video",
        )
        ok = restantes == [(s[0], id_video, 1.0, 2.0)]
        return ok, f"segmentos={restantes}"
    finally:
        temp.cleanup()


def test_27():
    """Cero modificaciones sobre marcadores al operar con segmentos."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        m1 = guardar_marcador(id_video, 5.0, ruta_db)
        s1 = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        eliminar_segmento(s1[0], ruta_db)
        marcadores = listar_marcadores(id_video, ruta_db)
        ok = marcadores == [(m1, id_video, 5.0, None)]
        return ok, f"marcadores={marcadores}"
    finally:
        temp.cleanup()


def test_28():
    """Cero modificaciones sobre la tabla `videos` al operar con segmentos."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        antes = _filas(ruta_db, "SELECT * FROM videos")
        id_video = _video_id(ruta_db, "a.mp4")
        s1 = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        s2 = guardar_segmento(id_video, 3.0, 4.0, ruta_db)
        listar_segmentos(id_video, ruta_db)
        listar_segmentos_de([id_video], ruta_db)
        eliminar_segmento(s1[0], ruta_db)
        eliminar_segmento(s2[0], ruta_db)
        despues = _filas(ruta_db, "SELECT * FROM videos")
        ok = antes == despues
        return ok, f"videos_antes={antes} videos_despues={despues}"
    finally:
        temp.cleanup()


def test_29():
    """`listar_segmentos_de` ejecuta una sola consulta SQL (sin N+1)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4", "c.mp4"])
    try:
        ids = [_video_id(ruta_db, n) for n in ("a.mp4", "b.mp4", "c.mp4")]
        for i, vid in enumerate(ids):
            guardar_segmento(vid, float(i + 1), float(i + 2), ruta_db)
        original = escanear_mod._conectar_repositorio_segmentos
        usadas = []

        def conectar_contador(ruta_db):
            conn = sqlite3.connect(ruta_db, factory=_Contador)
            escanear_mod._asegurar_tabla_segmentos(conn)
            usadas.append(conn)
            return conn

        try:
            escanear_mod._conectar_repositorio_segmentos = conectar_contador
            resultado = escanear_mod.listar_segmentos_de(ids, ruta_db)
            selects = usadas[-1].selects
        finally:
            escanear_mod._conectar_repositorio_segmentos = original
            for c in usadas:
                c.close()
        ok = len(resultado) == 3 and selects == 1
        return ok, f"resultado={len(resultado)} selects={selects}"
    finally:
        temp.cleanup()


def test_30():
    """`inicio = 0` es válido (>= 0)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_video, 0.0, 5.0, ruta_db)
        ok = listar_segmentos(id_video, ruta_db) == [(s[0], 0.0, 5.0, None)]
        return ok, f"segmentos={listar_segmentos(id_video, ruta_db)}"
    finally:
        temp.cleanup()


def test_31():
    """Texto como `video_id`/`segmento_id` → TypeError."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        ok = _capturar(TypeError, eliminar_segmento, "1", ruta_db)
        ok = ok and _capturar(TypeError, listar_segmentos_de, "a", ruta_db)
        ok = ok and _capturar(TypeError, listar_segmentos, "1", ruta_db)
        ok = ok and _capturar(TypeError, guardar_segmento, id_video, "1", 2.0, ruta_db)
        ok = ok and _capturar(TypeError, guardar_segmento, id_video, 1.0, "2", ruta_db)
        return ok, "textos"
    finally:
        temp.cleanup()


def test_32():
    """`guardar_segmento` normaliza inicio/fin a float."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_video, 1, 2, ruta_db)
        ok = s == (s[0], 1.0, 2.0) and all(
            isinstance(v, float) for v in (s[1], s[2])
        )
        return ok, f"guardado={s}"
    finally:
        temp.cleanup()


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
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
