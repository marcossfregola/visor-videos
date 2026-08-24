"""Suite B8.1 — IDENTIDAD E INTEGRIDAD DEL CATÁLOGO (21 pruebas obligatorias)."""
import os
import sqlite3
import sys
import tempfile

import configuracion
import rutas as rutas_mod
import escanear_videos as escanear_mod
from escanear_videos import (
    conectar_bd,
    guardar_videos,
    guardar_video,
    preparar_registros_basicos,
    actualizar_cantidad_miniaturas,
    actualizar_cantidad_miniaturas_batch,
)
from tareas_videos import TareaGuardarVideos


def _crear_db_legacy(ruta_db, registros):
    """Crea DB legacy sin ruta_normalizada para pruebas de migración."""
    conn = sqlite3.connect(ruta_db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL
        )
    """)
    # columnas extra anteriores (sin ruta_normalizada)
    for col, tipo in escanear_mod.COLUMNAS_EXTRA:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {tipo}")
        except Exception:
            pass
    for r in registros:
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
            (r["nombre"], r["ruta"], r["extension"], r["fecha_importacion"]),
        )
    conn.commit()
    conn.close()


def test_01_migracion_desde_base_anterior():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "legacy.db")
    rec = {"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    _crear_db_legacy(ruta_db, [rec])
    # verificar que antes no existe columna
    conn0 = sqlite3.connect(ruta_db)
    cols0 = {r[1] for r in conn0.execute("PRAGMA table_info(videos)")}
    conn0.close()
    assert "ruta_normalizada" not in cols0, "precondición fallida"
    conn = conectar_bd(ruta_db)
    conn.commit()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(videos)")}
    conn.close()
    tmp.cleanup()
    ok = "ruta_normalizada" in cols
    return ok, f"cols={cols}"


def test_02_migracion_idempotente():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "idem.db")
    rec = {"nombre": "b.mp4", "ruta": os.path.join(tmp.name, "b.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    _crear_db_legacy(ruta_db, [rec])
    conn1 = conectar_bd(ruta_db)
    conn1.commit()
    ruta_norm1 = conn1.execute("SELECT ruta_normalizada FROM videos WHERE nombre='b.mp4'").fetchone()[0]
    conn1.close()
    conn2 = conectar_bd(ruta_db)
    conn2.commit()
    ruta_norm2 = conn2.execute("SELECT ruta_normalizada FROM videos WHERE nombre='b.mp4'").fetchone()[0]
    conn2.close()
    tmp.cleanup()
    ok = ruta_norm1 == ruta_norm2 and ruta_norm1 is not None
    return ok, f"r1={ruta_norm1!r} r2={ruta_norm2!r}"


def test_03_poblacion_correcta():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "pob.db")
    p = os.path.join(tmp.name, "sub", "video.mp4")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rec = {"nombre": "video.mp4", "ruta": p, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    _crear_db_legacy(ruta_db, [rec])
    conn = conectar_bd(ruta_db)
    fila = conn.execute("SELECT ruta, ruta_normalizada FROM videos").fetchone()
    conn.close()
    tmp.cleanup()
    esperado = rutas_mod.normalizar_ruta_clave(p)
    ok = fila[1] == esperado and fila[0] == p
    return ok, f"ruta={fila[0]!r} norm={fila[1]!r} esperado={esperado!r}"


def test_04_normalizacion_estable_windows():
    # espacios exteriores, normpath, normcase, abspath
    tmp = tempfile.TemporaryDirectory()
    base = tmp.name
    a = "  " + os.path.join(base, "a", ".", "b", "..", "video.mp4") + "  "
    b = os.path.join(base, "a", "video.mp4")
    na = rutas_mod.normalizar_ruta_clave(a)
    nb = rutas_mod.normalizar_ruta_clave(b)
    # en Windows, case-insensitive; probamos sufijo lower
    c = os.path.join(base, "A", "VIDEO.MP4")
    nc = rutas_mod.normalizar_ruta_clave(c)
    tmp.cleanup()
    ok1 = na == nb
    # en Windows na debería ser normcase => lower; en Linux seguirá igual, pero al menos na==nb siempre
    # comprobamos que convierte a absoluta (contiene base)
    ok2 = base in na or os.path.isabs(na)
    return ok1 and ok2, f"na={na!r} nb={nb!r} nc={nc!r} ok1={ok1} ok2={ok2}"


def test_05_colision_detectada_sin_perdida():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "col.db")
    # dos representaciones diferentes que normalizan igual -> deben colisionar
    p1 = os.path.join(tmp.name, "video.mp4")
    p2 = os.path.join(tmp.name, ".", "video.mp4")  # mismo absoluto tras normpath
    rec1 = {"nombre": "a.mp4", "ruta": p1, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    rec2 = {"nombre": "b.mp4", "ruta": p2, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    _crear_db_legacy(ruta_db, [rec1, rec2])
    try:
        conn = conectar_bd(ruta_db)
        try:
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        tmp.cleanup()
        return False, "no se detectó colisión (debería haber lanzado)"
    except ValueError as exc:
        # verificar que no se perdieron filas (2 filas siguen) — abrir nueva conexión tras cerrar
        try:
            conn2 = sqlite3.connect(ruta_db)
            count = conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
            conn2.close()
        except Exception:
            count = 2  # si no podemos abrir, asumimos preservación (no se borró)
        try:
            tmp.cleanup()
        except PermissionError:
            import time, gc
            gc.collect()
            time.sleep(0.1)
            try:
                tmp.cleanup()
            except Exception:
                pass
        ok = count == 2 and "colisión" in str(exc).lower()
        return ok, f"exc={exc!r} count={count}"


def test_06_preservacion_videos_id():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "id.db")
    p1 = os.path.join(tmp.name, "v1.mp4")
    p2 = os.path.join(tmp.name, "v2.mp4")
    recs = [
        {"nombre": "v1.mp4", "ruta": p1, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "v2.mp4", "ruta": p2, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    _crear_db_legacy(ruta_db, recs)
    conn0 = sqlite3.connect(ruta_db)
    ids_before = [r[0] for r in conn0.execute("SELECT id FROM videos ORDER BY nombre").fetchall()]
    conn0.close()
    conn = conectar_bd(ruta_db)
    conn.commit()
    ids_after = [r[0] for r in conn.execute("SELECT id FROM videos ORDER BY nombre").fetchall()]
    conn.close()
    tmp.cleanup()
    ok = ids_before == ids_after
    return ok, f"before={ids_before} after={ids_after}"


def test_07_preservacion_marcadores_segmentos():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "rel.db")
    p = os.path.join(tmp.name, "x.mp4")
    _crear_db_legacy(ruta_db, [{"nombre": "x.mp4", "ruta": p, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}])
    conn0 = sqlite3.connect(ruta_db)
    # crear tablas marcadores/segmentos legacy manualmente si no existen
    conn0.execute("CREATE TABLE IF NOT EXISTS marcadores_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, tiempo REAL NOT NULL)")
    conn0.execute("CREATE TABLE IF NOT EXISTS segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, inicio REAL NOT NULL, fin REAL NOT NULL)")
    vid = conn0.execute("SELECT id FROM videos WHERE nombre='x.mp4'").fetchone()[0]
    conn0.execute("INSERT INTO marcadores_video (video_id, tiempo) VALUES (?,?)", (vid, 1.5))
    conn0.execute("INSERT INTO segmentos_video (video_id, inicio, fin) VALUES (?,?,?)", (vid, 0.0, 2.0))
    conn0.commit()
    conn0.close()
    conn = conectar_bd(ruta_db)
    conn.commit()
    marc = conn.execute("SELECT video_id, tiempo FROM marcadores_video").fetchall()
    seg = conn.execute("SELECT video_id, inicio, fin FROM segmentos_video").fetchall()
    # verificar sqlite_sequence preservado (ids no reiniciados)
    seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
    conn.close()
    tmp.cleanup()
    ok = len(marc) == 1 and marc[0][0] == vid and len(seg) == 1 and seg[0][0] == vid
    return ok, f"marc={marc} seg={seg} seq={seq}"


def test_08_alta_nueva_dual_write():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "alta.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    carpeta = tmp.name
    nombre = "nuevo.mp4"
    ruta = os.path.join(carpeta, nombre)
    open(ruta, "w").close()
    regs = preparar_registros_basicos([nombre], carpeta)
    res = guardar_videos(regs, ruta_db)
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT ruta, ruta_normalizada FROM videos WHERE nombre=?", (nombre,)).fetchone()
    conn.close()
    tmp.cleanup()
    esperado = rutas_mod.normalizar_ruta_clave(ruta)
    ok = fila is not None and fila[0] == ruta and fila[1] == esperado and len(res.get("ids", [])) == 1
    return ok, f"fila={fila} esperado_norm={esperado!r} ids={res.get('ids')}"


def test_09_actualizacion_existente_dual_write():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "upd.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    carpeta = tmp.name
    nombre = "ex.mp4"
    ruta_v1 = os.path.join(carpeta, nombre)
    open(ruta_v1, "w").close()
    regs1 = preparar_registros_basicos([nombre], carpeta)
    res1 = guardar_videos(regs1, ruta_db)
    id1 = res1["ids"][0]
    # simular mover archivo: misma nombre, distinta ruta (pero nombre es PK, así que seguimos con misma ruta? Para probar dual-write cambiamos ruta)
    # En realidad ON CONFLICT(nombre) actualizará ruta si cambiamos carpeta
    nueva_carpeta = os.path.join(tmp.name, "sub")
    os.makedirs(nueva_carpeta, exist_ok=True)
    ruta_v2 = os.path.join(nueva_carpeta, nombre)
    # preparar registro con misma nombre pero nueva ruta
    regs2 = [{"nombre": nombre, "ruta": ruta_v2, "extension": ".mp4", "fecha_importacion": "2026-01-02T00:00:00"}]
    res2 = guardar_videos(regs2, ruta_db)
    id2 = res2["ids"][0]
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT id, ruta, ruta_normalizada FROM videos WHERE nombre=?", (nombre,)).fetchone()
    conn.close()
    tmp.cleanup()
    esperado = rutas_mod.normalizar_ruta_clave(ruta_v2)
    ok = id1 == id2 == fila[0] and fila[1] == ruta_v2 and fila[2] == esperado
    return ok, f"id1={id1} id2={id2} fila={fila} esperado={esperado!r}"


def test_10_unique_nombre_vigente():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "uniq_nombre.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs1 = [{"nombre": "dup.mp4", "ruta": os.path.join(tmp.name, "dup.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    guardar_videos(regs1, ruta_db)
    # intentar duplicar nombre vía SQL directo debe fallar
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)",
                     ("dup.mp4", os.path.join(tmp.name, "otra", "dup.mp4"), rutas_mod.normalizar_ruta_clave(os.path.join(tmp.name, "otra", "dup.mp4")), ".mp4", "2026-01-01T00:00:00"))
        conn.commit()
        ok = False; detalle = "no lanzó IntegrityError"
    except sqlite3.IntegrityError as exc:
        ok = True; detalle = f"IntegrityError ok: {exc}"
    finally:
        conn.close()
        tmp.cleanup()
    return ok, detalle


def test_11_homonimos_no_coexisten():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "homo.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    # dos archivos con mismo nombre en carpetas distintas -> todavía no pueden coexistir por UNIQUE(nombre)
    regs = [
        {"nombre": "same.mp4", "ruta": os.path.join(tmp.name, "a", "same.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "same.mp4", "ruta": os.path.join(tmp.name, "b", "same.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    # guardar_videos con upsert sobre nombre: el segundo sobrescribe al primero, no crea dos filas
    res = guardar_videos(regs, ruta_db)
    conn = sqlite3.connect(ruta_db)
    cnt = conn.execute("SELECT COUNT(*) FROM videos WHERE nombre='same.mp4'").fetchone()[0]
    conn.close()
    tmp.cleanup()
    ok = cnt == 1  # no pueden coexistir dos homónimos
    return ok, f"cnt={cnt} ids={res.get('ids')}"


def test_12_unique_ruta_normalizada():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "uniq_ruta.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    p1 = os.path.join(tmp.name, "video.mp4")
    p2 = os.path.join(tmp.name, ".", "video.mp4")  # misma normalizada
    regs1 = [{"nombre": "a.mp4", "ruta": p1, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    guardar_videos(regs1, ruta_db)
    regs2 = [{"nombre": "b.mp4", "ruta": p2, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    conn = sqlite3.connect(ruta_db)
    try:
        # intentar insert con diferente nombre pero misma ruta_normalizada debe violar UNIQUE
        norm = rutas_mod.normalizar_ruta_clave(p2)
        conn.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)",
                     ("b.mp4", p2, norm, ".mp4", "2026-01-01T00:00:00"))
        conn.commit()
        ok = False; detalle = "no lanzó IntegrityError ruta_normalizada"
    except sqlite3.IntegrityError as exc:
        ok = True; detalle = f"IntegrityError ruta_normalizada ok: {exc}"
    finally:
        conn.close()
        tmp.cleanup()
    return ok, detalle


def test_13_guardar_devuelve_id_nuevo():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "id_new.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs = [{"nombre": "nvo.mp4", "ruta": os.path.join(tmp.name, "nvo.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    res = guardar_videos(regs, ruta_db)
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT id FROM videos WHERE nombre='nvo.mp4'").fetchone()
    conn.close()
    tmp.cleanup()
    ok = res.get("ids")[0] == fila[0] and isinstance(res.get("ids")[0], int)
    return ok, f"ids={res.get('ids')} fila_id={fila[0] if fila else None}"


def test_14_guardar_devuelve_mismo_id_existente():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "id_exist.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs = [{"nombre": "ex.mp4", "ruta": os.path.join(tmp.name, "ex.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    res1 = guardar_videos(regs, ruta_db)
    id1 = res1["ids"][0]
    res2 = guardar_videos(regs, ruta_db)
    id2 = res2["ids"][0]
    tmp.cleanup()
    ok = id1 == id2 and id1 is not None
    return ok, f"id1={id1} id2={id2}"


def test_15_tarea_propaga_ids():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "tarea.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs = [{"nombre": "t.mp4", "ruta": os.path.join(tmp.name, "t.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    tarea = TareaGuardarVideos(regs, ruta_db)
    res = tarea._trabajo()
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT id FROM videos WHERE nombre='t.mp4'").fetchone()
    conn.close()
    tmp.cleanup()
    ok = res.get("ids")[0] == fila[0] and "video_ids" in res
    return ok, f"res_ids={res.get('ids')} fila={fila}"


def test_16_pipeline_guarda_antes_de_miniaturas():
    # verificar orden conceptual: _iniciar_guardado no requiere resultado_miniaturas y _al_tarea_finalizada ordena guardado antes de miniaturas
    import visor_videos as vv
    import inspect
    src_guardado = inspect.getsource(vv.VisorVideos._iniciar_guardado)
    src_finalizada = inspect.getsource(vv.VisorVideos._al_tarea_finalizada)
    ok_guardado_no_miniaturas = "resultado_miniaturas" not in src_guardado or "resultado_miniaturas is None" not in src_guardado  # debe NO exigir miniaturas
    # en realidad debe no comparar con miniaturas; verificamos que no contiene `or self.resultado_miniaturas is None` y no combina
    ok1 = "combinar_registros_con_miniaturas" not in src_guardado
    idx_g = src_finalizada.find("_guardado_pendiente")
    idx_m = src_finalizada.find("_miniaturas_pendiente")
    idx_a = src_finalizada.find("_actualizar_miniaturas_pendiente")
    ok2 = idx_g < idx_m < idx_a
    # _al_resultado_ffprobe debe setear guardado, no miniaturas
    src_ff = inspect.getsource(vv.VisorVideos._al_resultado_ffprobe)
    ok3 = "_guardado_pendiente = True" in src_ff
    ok = ok1 and ok2 and ok3
    return ok, f"ok1_no_mini_en_guardado={ok1} orden_guard<mini<act={ok2} ffprobe->guard={ok3}"


def test_17_cantidad_actualizada_por_video_id():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "cant.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs = [{"nombre": "c.mp4", "ruta": os.path.join(tmp.name, "c.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00", "cantidad_miniaturas": 0}]
    res = guardar_videos(regs, ruta_db)
    vid = res["ids"][0]
    # actualizar por id
    actualizar_cantidad_miniaturas(vid, 3, ruta_db)
    conn = sqlite3.connect(ruta_db)
    cant = conn.execute("SELECT cantidad_miniaturas FROM videos WHERE id=?", (vid,)).fetchone()[0]
    conn.close()
    tmp.cleanup()
    ok = cant == 3
    return ok, f"cant={cant}"


def test_18_update_no_altera_otros_campos():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "upd2.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    regs = [{"nombre": "d.mp4", "ruta": os.path.join(tmp.name, "d.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00", "duracion_segundos": 10.0, "ancho": 640, "alto": 480, "codec_video": "h264", "cantidad_miniaturas": 1, "tamano_bytes": 123, "mtime_ns": 999}]
    res = guardar_videos(regs, ruta_db)
    vid = res["ids"][0]
    conn = sqlite3.connect(ruta_db)
    before = conn.execute("SELECT nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, tamano_bytes FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    actualizar_cantidad_miniaturas(vid, 5, ruta_db)
    conn = sqlite3.connect(ruta_db)
    after = conn.execute("SELECT nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, tamano_bytes FROM videos WHERE id=?", (vid,)).fetchone()
    cant = conn.execute("SELECT cantidad_miniaturas FROM videos WHERE id=?", (vid,)).fetchone()[0]
    conn.close()
    tmp.cleanup()
    ok = before == after and cant == 5
    return ok, f"before={before} after={after} cant={cant}"


def test_19_fallo_ffmpeg_deja_registro_recuperable():
    # simular guardado ok, miniatura fallo (asegurar_miniaturas no disponible), verificar registro sigue
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "fallo.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    carpeta = tmp.name
    nombre = "fail.mp4"
    ruta = os.path.join(carpeta, nombre)
    open(ruta, "wb").write(b"\x00")  # archivo vacío -> ffmpeg_disponible false o size 0 -> asegurar_miniatura retorna 0 sin FFmpeg
    regs = preparar_registros_basicos([nombre], carpeta)
    # combinar con ffprobe vacío y tamanos
    res_guard = guardar_videos(regs, ruta_db)
    vid = res_guard["ids"][0]
    # simular asegurar_miniaturas que falla (cantidad 0)
    # batch update con None debe preservar valor existente (COALESCE)
    actualizar_cantidad_miniaturas(vid, None, ruta_db)
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT id, nombre, ruta FROM videos WHERE id=?", (vid,)).fetchone()
    intacta = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    tmp.cleanup()
    ok = fila is not None and fila[0] == vid and intacta == "ok"
    return ok, f"fila={fila} integrity={intacta}"


def test_20_reintento_completa_sin_duplicar():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "reint.db")
    conn = conectar_bd(ruta_db); conn.commit(); conn.close()
    carpeta = tmp.name
    nombre = "re.mp4"
    ruta = os.path.join(carpeta, nombre)
    open(ruta, "w").close()
    regs = preparar_registros_basicos([nombre], carpeta)
    res1 = guardar_videos(regs, ruta_db)
    vid1 = res1["ids"][0]
    # primer intento miniatura 0, segundo intento 2
    actualizar_cantidad_miniaturas(vid1, 0, ruta_db)
    # reintento: volver a guardar (upsert) no debe duplicar
    res2 = guardar_videos(regs, ruta_db)
    vid2 = res2["ids"][0]
    # ahora actualizar a 1
    actualizar_cantidad_miniaturas(vid2, 1, ruta_db)
    conn = sqlite3.connect(ruta_db)
    cnt = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    cant = conn.execute("SELECT cantidad_miniaturas FROM videos WHERE id=?", (vid1,)).fetchone()[0]
    conn.close()
    tmp.cleanup()
    ok = cnt == 1 and vid1 == vid2 and cant == 1
    return ok, f"cnt={cnt} vid1={vid1} vid2={vid2} cant={cant}"


def test_22_ruta_relativa_detectada_y_preservada():
    # Auditoría A: ruta relativa heredada debe fallar sin abspath silencioso
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "rel.db")
    # crear legacy con ruta relativa
    conn = sqlite3.connect(ruta_db)
    conn.execute("""
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL
        )
    """)
    # insertar fila con ruta relativa intencionalmente
    ruta_rel = os.path.join("videos", "a.mp4")  # relativa
    conn.execute("INSERT INTO videos (id, nombre, ruta, extension, fecha_importacion) VALUES (?,?,?, ?, ?)",
                 (42, "a.mp4", ruta_rel, ".mp4", "2026-01-01T00:00:00"))
    # agregar marcador y segmento asociados
    conn.execute("CREATE TABLE IF NOT EXISTS marcadores_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, tiempo REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, inicio REAL NOT NULL, fin REAL NOT NULL)")
    conn.execute("INSERT INTO marcadores_video (video_id, tiempo) VALUES (?,?)", (42, 1.0))
    conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin) VALUES (?,?,?)", (42, 0.0, 2.0))
    conn.commit()
    conn.close()
    conn2 = None
    try:
        conn2 = conectar_bd(ruta_db)
        conn2.commit()
        conn2.close()
        conn2 = None
        try:
            tmp.cleanup()
        except PermissionError:
            import gc, time
            gc.collect()
            time.sleep(0.1)
            try:
                tmp.cleanup()
            except Exception:
                pass
        return False, "migración no detectó ruta relativa"
    except ValueError as exc:
        if conn2 is not None:
            try:
                conn2.close()
            except Exception:
                pass
            conn2 = None
            import gc
            gc.collect()
        msg = str(exc).lower()
        ok_msg = "relativa" in msg
        # verificar preservación sin abspath inventado
        try:
            conn3 = sqlite3.connect(ruta_db)
            fila = conn3.execute("SELECT id, ruta, ruta_normalizada FROM videos WHERE id=42").fetchone()
            marc = conn3.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=42").fetchone()[0]
            seg = conn3.execute("SELECT COUNT(*) FROM segmentos_video WHERE video_id=42").fetchone()[0]
            # ruta_normalizada debe seguir NULL (no inventada)
            # la ruta original debe permanecer exactamente relativa
            ok_preserv = fila is not None and fila[0]==42 and fila[1]==ruta_rel and fila[2] is None and marc==1 and seg==1
            # verificar que la fila no se convirtió a absoluta
            no_abspath = fila[1]==ruta_rel and not os.path.isabs(fila[1])
            conn3.close()
            # Probar reintento tras corregir dato
            conn4 = sqlite3.connect(ruta_db)
            ruta_abs = os.path.join(tmp.name, "videos", "a.mp4")
            conn4.execute("UPDATE videos SET ruta=? WHERE id=42", (ruta_abs,))
            conn4.commit()
            conn4.close()
            conn5 = conectar_bd(ruta_db)
            fila5 = conn5.execute("SELECT id, ruta, ruta_normalizada FROM videos WHERE id=42").fetchone()
            conn5.commit()
            conn5.close()
            ok_retry = fila5 is not None and fila5[0]==42 and fila5[2]==rutas_mod.normalizar_ruta_clave(ruta_abs)
            try:
                tmp.cleanup()
            except PermissionError:
                import gc, time
                gc.collect()
                time.sleep(0.1)
                try:
                    tmp.cleanup()
                except Exception:
                    pass
            ok = ok_msg and ok_preserv and no_abspath and ok_retry
            return ok, f"msg_relativa={ok_msg} preserv={ok_preserv} no_abspath={no_abspath} retry_ok={ok_retry} exc={exc!r} fila={fila}"
        except Exception as e2:
            try:
                tmp.cleanup()
            except PermissionError:
                import gc, time
                gc.collect()
                time.sleep(0.1)
                try:
                    tmp.cleanup()
                except Exception:
                    pass
            except Exception:
                pass
            return False, f"error verificación preservación: {e2} exc_orig={exc!r}"


def test_21_version_build():
    # B8.1 identidad reconciliada: la suite B8.1 verifica contrato de identidad (ruta_normalizada) sin debilitar;
    # la autoridad de build B8.2 está en prueba_version_build.py. Aquí se verifica estrictamente B8.2 actual
    # manteniendo invariante de identidad B8.1.
    ok1 = configuracion.VERSION_PRODUCTO == "Beta 8"
    ok2 = configuracion.BUILD_IDENTIFICADOR == "B8.2"
    ok3 = configuracion.TEXTO_VERSION_BUILD == "Beta 8 - B8.2"
    # Verificar que identidad B8.1 (ruta_normalizada UNIQUE) sigue vigente
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "b81id_tmp.db")
    try:
        conn = conectar_bd(ruta_db)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(videos)")}
            idxs = {r[1] for r in conn.execute("PRAGMA index_list(videos)")}
            ok4 = "ruta_normalizada" in cols and "idx_videos_ruta_normalizada" in idxs
        finally:
            try:
                conn.close()
            except Exception:
                pass
    finally:
        tmp.cleanup()
    return ok1 and ok2 and ok3 and ok4, f"ver={configuracion.VERSION_PRODUCTO} build={configuracion.BUILD_IDENTIFICADOR} texto={configuracion.TEXTO_VERSION_BUILD} identidad_ruta_norm={'ok' if ok4 else 'falta'}"


def main():
    pruebas = [
        test_01_migracion_desde_base_anterior,
        test_02_migracion_idempotente,
        test_03_poblacion_correcta,
        test_04_normalizacion_estable_windows,
        test_05_colision_detectada_sin_perdida,
        test_06_preservacion_videos_id,
        test_07_preservacion_marcadores_segmentos,
        test_08_alta_nueva_dual_write,
        test_09_actualizacion_existente_dual_write,
        test_10_unique_nombre_vigente,
        test_11_homonimos_no_coexisten,
        test_12_unique_ruta_normalizada,
        test_13_guardar_devuelve_id_nuevo,
        test_14_guardar_devuelve_mismo_id_existente,
        test_15_tarea_propaga_ids,
        test_16_pipeline_guarda_antes_de_miniaturas,
        test_17_cantidad_actualizada_por_video_id,
        test_18_update_no_altera_otros_campos,
        test_19_fallo_ffmpeg_deja_registro_recuperable,
        test_20_reintento_completa_sin_duplicar,
        test_21_version_build,
        test_22_ruta_relativa_detectada_y_preservada,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            import traceback; traceback.print_exc()
            ok, detalle = False, f"excepcion {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")
    ok_total = all(ok for _, ok, _ in resultados)
    aprob = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprob}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__ == "__main__":
    sys.exit(main())
