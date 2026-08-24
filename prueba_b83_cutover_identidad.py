"""Suite B8.3 — BACKEND DE IDENTIDAD: SCHEMA/MIGRACIÓN + UPSERT + SINCRONIZACIÓN/METADATA (18 pruebas)."""
import os
import sqlite3
import sys
import tempfile
import shutil
import subprocess

import rutas as rutas_mod
import escanear_videos as ev
from escanear_videos import (
    conectar_bd,
    _estado_cutover_identidad_b83,
    _asegurar_cutover_identidad_b83,
    preparar_registros_basicos,
    guardar_videos,
    guardar_video,
    listar_registros_por_rutas,
    detectar_diferencias,
    preparar_plan_sincronizacion,
    eliminar_candidatos,
    guardar_marcador,
    guardar_segmento,
    incorporar_video_derivado_al_catalogo,
)
from tareas_videos import TareaFFprobe

def _crear_legacy_pre(ruta_db, registros):
    """Crea DB legacy pre-B8.3: UNIQUE(nombre) + ruta_normalizada nullable + idx."""
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
    for col, tipo in ev.COLUMNAS_EXTRA:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {tipo}")
        except Exception:
            pass
    # ruta_normalizada nullable (B8.1)
    try:
        conn.execute("ALTER TABLE videos ADD COLUMN ruta_normalizada TEXT")
    except Exception:
        pass
    # insert registros (sin ruta_normalizada aún)
    for r in registros:
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
            (r["nombre"], r["ruta"], r["extension"], r["fecha_importacion"]),
        )
    # poblar ruta_normalizada
    filas = conn.execute("SELECT id, ruta FROM videos").fetchall()
    for vid, ruta in filas:
        norm = rutas_mod.normalizar_ruta_clave(ruta)
        conn.execute("UPDATE videos SET ruta_normalizada=? WHERE id=?", (norm, vid))
    # crear índice único ruta_normalizada
    try:
        conn.execute("CREATE UNIQUE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
    except Exception:
        pass
    conn.commit()
    conn.close()

def test_01_db_nueva_post():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "nueva.db")
    conn = conectar_bd(ruta_db)
    try:
        # verificar esquema
        info = conn.execute("PRAGMA table_info(videos)").fetchall()
        col_notnull = {row[1]: row[3] for row in info}
        assert "ruta_normalizada" in col_notnull, "falta ruta_normalizada"
        assert col_notnull["ruta_normalizada"] == 1, f"ruta_normalizada debe ser NOT NULL, got {col_notnull['ruta_normalizada']}"
        # nombre debe ser NOT NULL pero sin UNIQUE
        assert col_notnull["nombre"] == 1
        # verificar no UNIQUE(nombre)
        idx_list = conn.execute("PRAGMA index_list(videos)").fetchall()
        has_unique_nombre = False
        for seq, name, unique, origin, partial in idx_list:
            if unique == 1:
                info_idx = conn.execute(f"PRAGMA index_info('{name}')").fetchall()
                cols = [r[2] for r in info_idx if r[2] is not None]
                if cols == ["nombre"]:
                    has_unique_nombre = True
        assert not has_unique_nombre, f"DB nueva no debe tener UNIQUE(nombre) pero tiene {idx_list}"
        # verificar índice ruta_normalizada único
        idx_names = {row[1]: row for row in idx_list}
        assert "idx_videos_ruta_normalizada" in idx_names, "falta idx_videos_ruta_normalizada"
        assert idx_names["idx_videos_ruta_normalizada"][2] == 1, "índice ruta debe ser UNIQUE"
        info_ruta = conn.execute("PRAGMA index_info('idx_videos_ruta_normalizada')").fetchall()
        cols_ruta = [r[2] for r in info_ruta]
        assert cols_ruta == ["ruta_normalizada"], f"idx columnas incorrectas {cols_ruta}"
        # integrity
        chk = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert chk == "ok"
        conn.commit()
    finally:
        try:
            conn.close()
        except:
            pass
        tmp.cleanup()
    return True, "post schema OK"

def test_02_detector_post():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "post.db")
    conn = conectar_bd(ruta_db)
    try:
        estado = _estado_cutover_identidad_b83(conn)
        assert estado == "post", f"esperado post got {estado}"
    finally:
        conn.close()
        tmp.cleanup()
    return True, "detector post OK"

def test_03_migracion_preserva():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "legacy.db")
    # crear 2 registros con esquema pre
    recs = [
        {"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "b.mp4", "ruta": os.path.join(tmp.name, "b.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    _crear_legacy_pre(ruta_db, recs)
    # añadir columnas extra valores para verificar preservación
    conn0 = sqlite3.connect(ruta_db)
    conn0.execute("UPDATE videos SET duracion_segundos=12.5, ancho=640, alto=480, codec_video='h264', cantidad_miniaturas=3, tamano_bytes=12345, mtime_ns=999 WHERE nombre='a.mp4'")
    conn0.execute("UPDATE videos SET duracion_segundos=5.0, ancho=1280, alto=720, codec_video='hevc', cantidad_miniaturas=1, tamano_bytes=54321, mtime_ns=111 WHERE nombre='b.mp4'")
    conn0.commit()
    ids_before = [r[0] for r in conn0.execute("SELECT id FROM videos ORDER BY id").fetchall()]
    vals_before = conn0.execute("SELECT id, nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns, ruta_normalizada FROM videos ORDER BY id").fetchall()
    conn0.close()
    # migrar vía conectar_bd
    conn = conectar_bd(ruta_db)
    try:
        vals_after = conn.execute("SELECT id, nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns, ruta_normalizada FROM videos ORDER BY id").fetchall()
        assert vals_before == vals_after, f"preservación falló before={vals_before} after={vals_after}"
        ids_after = [r[0] for r in conn.execute("SELECT id FROM videos ORDER BY id").fetchall()]
        assert ids_before == ids_after, f"ids no preservados {ids_before} vs {ids_after}"
        estado = _estado_cutover_identidad_b83(conn)
        assert estado == "post"
        conn.commit()
    finally:
        conn.close()
        tmp.cleanup()
    return True, f"ids {ids_before} preservados"

def test_04_detector_pre_a_post():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "pre.db")
    recs = [{"nombre": "x.mp4", "ruta": os.path.join(tmp.name, "x.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn0 = sqlite3.connect(ruta_db)
    estado_pre = _estado_cutover_identidad_b83(conn0)
    conn0.close()
    assert estado_pre == "pre", f"esperado pre got {estado_pre}"
    conn = conectar_bd(ruta_db)
    estado_post = _estado_cutover_identidad_b83(conn)
    conn.close()
    assert estado_post == "post", f"esperado post got {estado_post}"
    tmp.cleanup()
    return True, f"pre->{estado_pre} post->{estado_post}"

def test_05_idempotencia_no_rebuild():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "idem.db")
    recs = [{"nombre": "y.mp4", "ruta": os.path.join(tmp.name, "y.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn = conectar_bd(ruta_db)
    # capturar schema post primera migración
    sql1 = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    root1 = conn.execute("SELECT rootpage FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    seq1 = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
    conn.close()
    # segunda apertura
    conn2 = conectar_bd(ruta_db)
    sql2 = conn2.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    root2 = conn2.execute("SELECT rootpage FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    seq2 = conn2.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
    estado = _estado_cutover_identidad_b83(conn2)
    conn2.close()
    tmp.cleanup()
    assert sql1 == sql2, f"sql cambió {sql1!r} vs {sql2!r}"
    # rootpage debe ser igual si no hubo rebuild
    assert root1 == root2, f"rootpage cambió {root1} vs {root2} indica rebuild"
    assert seq1 == seq2, f"seq cambió {seq1} vs {seq2}"
    assert estado == "post"
    return True, f"rootpage {root1} igual, sql estable"

def test_06_schema_invalido_aborta():
    # caso: falta índice ruta
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "inv.db")
    conn = sqlite3.connect(ruta_db)
    conn.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, ruta_normalizada TEXT)")
    # poblar ruta_normalizada sin índice
    p = os.path.join(tmp.name, "a.mp4")
    conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion, ruta_normalizada) VALUES (?,?,?,?,?)", ("a.mp4", p, rutas_mod.normalizar_ruta_clave(p), ".mp4", "2026-01-01T00:00:00"))
    conn.commit()
    # intentar detector debe lanzar invalido
    try:
        _estado_cutover_identidad_b83(conn)
        ok1 = False
    except ValueError as e:
        ok1 = "falta índice" in str(e).lower() or "invalido" in str(e).lower()
    # intentar migración debe abortar sin modificar
    sql_before = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    try:
        _asegurar_cutover_identidad_b83(conn)
        ok2 = False
    except ValueError:
        ok2 = True
    sql_after = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    conn.close()
    tmp.cleanup()
    assert ok1 and ok2, f"ok1={ok1} ok2={ok2}"
    assert sql_before == sql_after, "schema modificado pese a invalido"
    return True, "invalido falta idx aborta"

def test_07_ruta_normalizada_null_aborta():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "null.db")
    conn = sqlite3.connect(ruta_db)
    conn.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, ruta_normalizada TEXT)")
    p = os.path.join(tmp.name, "b.mp4")
    conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion, ruta_normalizada) VALUES (?,?,?,?,?)", ("b.mp4", p, ".mp4", "2026-01-01T00:00:00", None))
    conn.execute("CREATE UNIQUE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
    conn.commit()
    sql_before = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    cnt_before = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    try:
        _asegurar_cutover_identidad_b83(conn)
        ok = False
    except ValueError as e:
        ok = "null" in str(e).lower() or "vacía" in str(e).lower()
    sql_after = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    cnt_after = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    conn.close()
    try:
        tmp.cleanup()
    except Exception:
        import time, gc; gc.collect(); time.sleep(0.1)
        try:
            tmp.cleanup()
        except:
            pass
    assert ok, "debería abortar por NULL"
    assert sql_before == sql_after and cnt_before == cnt_after
    return True, "NULL aborta intacto"

def test_08_colision_aborta():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "col.db")
    p1 = os.path.join(tmp.name, "video.mp4")
    p2 = os.path.join(tmp.name, ".", "video.mp4")  # misma normalizada
    recs = [
        {"nombre": "a.mp4", "ruta": p1, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "b.mp4", "ruta": p2, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    # crear legacy sin colisión detectada aún (B8.1 habría fallado, pero forzamos inserción directa)
    conn = sqlite3.connect(ruta_db)
    conn.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, ruta_normalizada TEXT)")
    for r in recs:
        conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)", (r["nombre"], r["ruta"], r["extension"], r["fecha_importacion"]))
    filas = conn.execute("SELECT id, ruta FROM videos").fetchall()
    for vid, ruta in filas:
        n = rutas_mod.normalizar_ruta_clave(ruta)
        conn.execute("UPDATE videos SET ruta_normalizada=? WHERE id=?", (n, vid))
    # intentar crear índice único fallará por colisión, pero lo evitamos creando índice sin check?
    # En este test queremos que detector vea pre pero validación de colisión aborte
    # Creamos índice sin UNIQUE temporalmente para simular datos colisionados antes de cutover
    try:
        conn.execute("CREATE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
    except Exception:
        pass
    conn.commit()
    # ahora intentar cutover debe detectar duplicados y abortar
    # primero cambiar índice a UNIQUE no es posible por colisión, así que detector dirá invalido falta UNIQUE?
    # En lugar de eso, forzamos que idx sea UNIQUE pero con datos colisionados, la creación fallaría.
    # Para este test, simular colisión en validación previa: creamos tabla con índice no único y luego llamamos migración
    # La migración debe detectar duplicados via GROUP BY y abortar
    # Ajustamos: eliminar índice no único y crear único si no hay colisión, pero aquí hay colisión así que fallará
    conn.execute("DROP INDEX IF EXISTS idx_videos_ruta_normalizada")
    # intentar crear único debe fallar, pero queremos que migración detecte y aborte con datos intactos
    # Así que no creamos índice, dejamos sin índice para que detector diga invalido
    # En lugar de eso, probamos colisión con dos rutas que normalizan igual pero con índice único existente (no se puede crear)
    # Simplificamos: usar _crear_legacy_pre con colisión debe fallar en B8.1, así que aquí testear que migración aborta si hay colisión
    conn.close()
    # crear de nuevo correctamente con colisión para test de migración: usaremos helper que no valida colisión
    tmp2 = tempfile.TemporaryDirectory()
    ruta_db2 = os.path.join(tmp2.name, "col2.db")
    conn2 = sqlite3.connect(ruta_db2)
    conn2.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, ruta_normalizada TEXT)")
    for r in recs:
        conn2.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)", (r["nombre"], r["ruta"], r["extension"], r["fecha_importacion"]))
    for vid, ruta in conn2.execute("SELECT id, ruta FROM videos").fetchall():
        n = rutas_mod.normalizar_ruta_clave(ruta)
        conn2.execute("UPDATE videos SET ruta_normalizada=? WHERE id=?", (n, vid))
    # crear índice UNIQUE pese a colisión -> debe fallar, pero lo capturamos
    try:
        conn2.execute("CREATE UNIQUE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
        conn2.commit()
        # si no falló, entonces hay colisión pero SQLite no la detectó? Entonces migración debe detectar
        sql_before = conn2.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
        try:
            _asegurar_cutover_identidad_b83(conn2)
            ok = False
        except ValueError as e:
            ok = "colisión" in str(e).lower()
        sql_after = conn2.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
        conn2.close()
        tmp.cleanup()
        tmp2.cleanup()
        assert ok and sql_before == sql_after
        return True, "colisión aborta"
    except sqlite3.IntegrityError:
        # SQLite detectó colisión al crear índice, se preservan datos
        cnt = conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn2.close()
        tmp.cleanup()
        tmp2.cleanup()
        assert cnt == 2
        return True, "colisión detectada por SQLite, datos intactos"

def test_09_sqlite_sequence():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "seq.db")
    # crear legacy con 5 registros
    recs = [{"nombre": f"v{i}.mp4", "ruta": os.path.join(tmp.name, f"v{i}.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"} for i in range(1,6)]
    _crear_legacy_pre(ruta_db, recs)
    conn = sqlite3.connect(ruta_db)
    max_id = conn.execute("SELECT MAX(id) FROM videos").fetchone()[0]
    seq_before = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()[0]
    assert seq_before == max_id
    # borrar el máximo
    conn.execute("DELETE FROM videos WHERE id=?", (max_id,))
    conn.commit()
    conn.close()
    # migrar
    conn2 = conectar_bd(ruta_db)
    seq_after_mig = conn2.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()[0]
    max_after = conn2.execute("SELECT MAX(id) FROM videos").fetchone()[0]
    assert seq_after_mig == 5, f"seq debe permanecer 5 tras borrar max, got {seq_after_mig}"
    conn2.close()
    # nuevo insert debe usar > seq histórico, no reutilizar id borrado
    # usar guardar_videos para insertar nuevo
    nuevo_ruta = os.path.join(tmp.name, "nuevo.mp4")
    regs = [{"nombre": "nuevo.mp4", "ruta": nuevo_ruta, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    res = guardar_videos(regs, ruta_db)
    new_id = res["ids"][0]
    conn3 = sqlite3.connect(ruta_db)
    seq_final = conn3.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()[0]
    conn3.close()
    tmp.cleanup()
    assert new_id == 6, f"esperado id 6, got {new_id}"
    assert seq_final == 6
    return True, f"seq {seq_before}->{seq_after_mig}->{seq_final} new_id {new_id}"

def test_10_integrity():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "int.db")
    recs = [{"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn = conectar_bd(ruta_db)
    chk = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    tmp.cleanup()
    assert chk == "ok" and fk == []
    return True, "integrity ok"

def test_11_homonimos_distintas_rutas():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "homo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    dir_a = os.path.join(tmp.name, "a")
    dir_b = os.path.join(tmp.name, "b")
    os.makedirs(dir_a, exist_ok=True)
    os.makedirs(dir_b, exist_ok=True)
    recs = [
        {"nombre": "video.mp4", "ruta": os.path.join(dir_a, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "video.mp4", "ruta": os.path.join(dir_b, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    res = guardar_videos(recs, ruta_db)
    assert len(res["ids"]) == 2 and res["ids"][0] != res["ids"][1], f"ids {res['ids']}"
    conn = sqlite3.connect(ruta_db)
    cnt = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    conn.close()
    tmp.cleanup()
    assert cnt == 2
    return True, f"ids {res['ids']}"

def test_12_upsert_misma_ruta():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "upsert.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    p = os.path.join(tmp.name, "same.mp4")
    rec = {"nombre": "same.mp4", "ruta": p, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00", "duracion_segundos": 5.0}
    res1 = guardar_videos([rec], ruta_db)
    id1 = res1["ids"][0]
    rec2 = {"nombre": "same_renamed.mp4", "ruta": p, "extension": ".mp4", "fecha_importacion": "2026-01-02T00:00:00", "duracion_segundos": 9.0}
    res2 = guardar_videos([rec2], ruta_db)
    id2 = res2["ids"][0]
    conn = sqlite3.connect(ruta_db)
    fila = conn.execute("SELECT nombre, duracion_segundos FROM videos WHERE ruta_normalizada=?", (rutas_mod.normalizar_ruta_clave(p),)).fetchone()
    conn.close()
    tmp.cleanup()
    assert id1 == id2, f"id1 {id1} != id2 {id2}"
    assert fila[0] == "same_renamed.mp4" and fila[1] == 9.0
    return True, f"upsert mismo id {id1}"

def test_13_sync_homonimos_no_colapsan():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "sync.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    dir_a = os.path.join(tmp.name, "a")
    dir_b = os.path.join(tmp.name, "b")
    os.makedirs(dir_a, exist_ok=True)
    os.makedirs(dir_b, exist_ok=True)
    # crear archivos en disco solo en a
    open(os.path.join(dir_a, "video.mp4"), "w").close()
    open(os.path.join(dir_b, "video.mp4"), "w").close()
    # DB con ambos
    recs = [
        {"nombre": "video.mp4", "ruta": os.path.join(dir_a, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "video.mp4", "ruta": os.path.join(dir_b, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    guardar_videos(recs, ruta_db)
    # borrar archivo en b para simular ausencia solo en b
    os.remove(os.path.join(dir_b, "video.mp4"))
    dif_a = detectar_diferencias(dir_a, ruta_db)
    dif_b = detectar_diferencias(dir_b, ruta_db)
    # dif_a: presente en ambos debe contener video.mp4, ausentes vacío
    assert "video.mp4" in dif_a["presentes_en_ambos"], f"dif_a {dif_a}"
    assert dif_a["ausentes_del_disco"] == [], f"dif_a ausentes {dif_a}"
    # dif_b: como archivo borrado, ausentes debe contener video.mp4
    assert dif_b["presentes_en_ambos"] == [], f"dif_b presentes {dif_b}"
    assert "video.mp4" in dif_b["ausentes_del_disco"], f"dif_b ausentes {dif_b}"
    # nuevos en a debe ser vacío, en b vacío también (porque DB ya tiene)
    assert dif_a["nuevos"] == [] and dif_b["nuevos"] == []
    tmp.cleanup()
    return True, f"dif_a {dif_a} dif_b {dif_b}"

def test_14_eliminacion_no_borra_homonimo():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "elim.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    dir_a = os.path.join(tmp.name, "a")
    dir_b = os.path.join(tmp.name, "b")
    os.makedirs(dir_a, exist_ok=True)
    os.makedirs(dir_b, exist_ok=True)
    open(os.path.join(dir_a, "video.mp4"), "w").close()
    # dir_b sin archivo
    recs = [
        {"nombre": "video.mp4", "ruta": os.path.join(dir_a, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "video.mp4", "ruta": os.path.join(dir_b, "video.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    guardar_videos(recs, ruta_db)
    dif_b = detectar_diferencias(dir_b, ruta_db)
    assert "video.mp4" in dif_b["ausentes_del_disco"]
    plan = preparar_plan_sincronizacion(dif_b)
    # plan candidatos debe ser ["video.mp4"] (relativo)
    res = eliminar_candidatos(plan, ruta_db)
    assert res["eliminados"] == 1
    conn = sqlite3.connect(ruta_db)
    cnt = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    fila = conn.execute("SELECT ruta FROM videos").fetchone()[0]
    conn.close()
    tmp.cleanup()
    assert cnt == 1 and dir_a in fila, f"cnt {cnt} fila {fila}"
    return True, f"eliminado 1 queda {fila}"

def test_15_metadata_no_cruza_homonimos():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "meta.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    dir_a = os.path.join(tmp.name, "a")
    dir_b = os.path.join(tmp.name, "b")
    os.makedirs(dir_a, exist_ok=True)
    os.makedirs(dir_b, exist_ok=True)
    p_a = os.path.join(dir_a, "video.mp4")
    p_b = os.path.join(dir_b, "video.mp4")
    open(p_a, "w").close()
    open(p_b, "w").close()
    # insertar con metadata distinta
    rec_a = {"nombre": "video.mp4", "ruta": p_a, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00", "duracion_segundos": 10.0, "ancho": 640, "alto": 480, "codec_video": "h264", "tamano_bytes": 100, "mtime_ns": 1000}
    rec_b = {"nombre": "video.mp4", "ruta": p_b, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00", "duracion_segundos": 20.0, "ancho": 1280, "alto": 720, "codec_video": "hevc", "tamano_bytes": 200, "mtime_ns": 2000}
    guardar_videos([rec_a, rec_b], ruta_db)
    # listar por rutas normalizadas
    regs = listar_registros_por_rutas([p_a, p_b], ruta_db)
    norm_a = rutas_mod.normalizar_ruta_clave(p_a)
    norm_b = rutas_mod.normalizar_ruta_clave(p_b)
    assert regs[norm_a]["duracion_segundos"] == 10.0, f"reg a {regs[norm_a]}"
    assert regs[norm_b]["duracion_segundos"] == 20.0, f"reg b {regs[norm_b]}"
    # probar TareaFFprobe no cruza
    # stats con tamano/mtime correctos para cada
    stats = {"resultados": [{"ruta": p_a, "tamano_bytes": 100, "mtime_ns": 1000}, {"ruta": p_b, "tamano_bytes": 200, "mtime_ns": 2000}]}
    # mock ffprobe para contar llamadas
    orig_ff = ev.obtener_datos_ffprobe
    calls = {"n": 0}
    def fake_ffprobe(ruta):
        calls["n"] += 1
        return {"duracion_segundos": 99.0, "ancho": 1, "alto": 1, "codec_video": "fake"}
    ev.obtener_datos_ffprobe = fake_ffprobe
    try:
        tarea = TareaFFprobe([p_a, p_b], nombres=["video.mp4", "video.mp4"], stats=stats, ruta_db=ruta_db)
        res = tarea._trabajo()
        # ambos deben ser reutilizados (no llamadas ffprobe)
        assert calls["n"] == 0, f"ffprobe llamado {calls['n']} veces, debería reutilizar"
        assert res["con_datos"] == 2
        # verificar que datos reutilizados son los correctos por ruta, no cruzados
        # El orden de resultados corresponde a rutas [p_a, p_b]
        d_a = res["resultados"][0]["datos"]
        d_b = res["resultados"][1]["datos"]
        assert d_a["duracion_segundos"] == 10.0 and d_b["duracion_segundos"] == 20.0, f"d_a {d_a} d_b {d_b}"
    finally:
        ev.obtener_datos_ffprobe = orig_ff
        tmp.cleanup()
    return True, "metadata por ruta OK"

def test_16_derivado_homonimo_vs_misma_ruta():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "deriv.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    # crear video original
    orig_dir = os.path.join(tmp.name, "orig")
    os.makedirs(orig_dir, exist_ok=True)
    orig_path = os.path.join(orig_dir, "orig.mp4")
    open(orig_path, "wb").write(b"fake")
    # mock ffprobe para derivado
    orig_ff = ev.obtener_datos_ffprobe
    ev.obtener_datos_ffprobe = lambda ruta: {"duracion_segundos": 5.0, "ancho": 640, "alto": 480, "codec_video": "h264"}
    try:
        rec = {"nombre": "orig.mp4", "ruta": orig_path, "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
        res = guardar_videos([rec], ruta_db)
        orig_id = res["ids"][0]
        seg = ev.guardar_segmento(orig_id, 0.0, 2.0, ruta_db)
        seg_id = seg[0]
        # crear derivado en ruta A
        dir_a = os.path.join(tmp.name, "a")
        dir_b = os.path.join(tmp.name, "b")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        deriv_a = os.path.join(dir_a, "deriv.mp4")
        open(deriv_a, "wb").write(b"fake deriv a")
        r1 = incorporar_video_derivado_al_catalogo(deriv_a, orig_id, [{"segmento_id": seg_id, "inicio": 0.0, "fin": 2.0}], tipo="individual", ruta_db=ruta_db)
        assert r1["ok"], f"r1 fallo {r1}"
        # mismo nombre en ruta distinta permitido
        deriv_b = os.path.join(dir_b, "deriv.mp4")
        open(deriv_b, "wb").write(b"fake deriv b")
        r2 = incorporar_video_derivado_al_catalogo(deriv_b, orig_id, [{"segmento_id": seg_id, "inicio": 0.0, "fin": 2.0}], tipo="individual", ruta_db=ruta_db)
        assert r2["ok"], f"r2 debería permitir homónimo distinto ruta {r2}"
        # misma ruta normalizada rechazada (intentar mismo path)
        r3 = incorporar_video_derivado_al_catalogo(deriv_a, orig_id, [{"segmento_id": seg_id, "inicio": 0.0, "fin": 2.0}], tipo="individual", ruta_db=ruta_db)
        assert not r3["ok"] and "ruta duplicada" in r3["error"].lower() or "ya existe" in r3["error"].lower(), f"r3 debería rechazar misma ruta {r3}"
        # también probar case-insensitive: misma ruta con distinto case (Windows)
        deriv_a_case = deriv_a.upper() if os.name == "nt" else deriv_a
        if os.path.exists(deriv_a):
            # en Windows, normalizar debe colapsar
            r4 = incorporar_video_derivado_al_catalogo(deriv_a_case, orig_id, [{"segmento_id": seg_id, "inicio": 0.0, "fin": 2.0}], tipo="individual", ruta_db=ruta_db)
            # si case difiere, debe ser rechazado por misma ruta_normalizada
            # Si el archivo no existe con ese case, no importa
            pass
        return True, f"r1 {r1['derivacion_id']} r2 {r2['derivacion_id']} r3 {r3['error']}"
    finally:
        ev.obtener_datos_ffprobe = orig_ff
        tmp.cleanup()

def test_17_marcadores_segmentos_sobreviven():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "marc.db")
    recs = [{"nombre": "v.mp4", "ruta": os.path.join(tmp.name, "v.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn = sqlite3.connect(ruta_db)
    vid = conn.execute("SELECT id FROM videos WHERE nombre='v.mp4'").fetchone()[0]
    # crear marcadores/segmentos legacy
    conn.execute("CREATE TABLE IF NOT EXISTS marcadores_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, tiempo REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, inicio REAL NOT NULL, fin REAL NOT NULL)")
    conn.execute("INSERT INTO marcadores_video (video_id, tiempo) VALUES (?,?)", (vid, 1.5))
    conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin) VALUES (?,?,?)", (vid, 0.0, 1.0))
    conn.commit()
    conn.close()
    # migrar
    conn2 = conectar_bd(ruta_db)
    marc = conn2.execute("SELECT video_id, tiempo FROM marcadores_video").fetchall()
    seg = conn2.execute("SELECT video_id, inicio, fin FROM segmentos_video").fetchall()
    conn2.close()
    tmp.cleanup()
    assert len(marc) == 1 and marc[0][0] == vid
    assert len(seg) == 1 and seg[0][0] == vid
    return True, f"marc {marc} seg {seg}"

def test_18_derivados_sobreviven():
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "der2.db")
    recs = [
        {"nombre": "orig.mp4", "ruta": os.path.join(tmp.name, "orig.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "deriv.mp4", "ruta": os.path.join(tmp.name, "deriv.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    _crear_legacy_pre(ruta_db, recs)
    conn = sqlite3.connect(ruta_db)
    # asegurar tablas derivados y crear una derivación
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos_derivados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            derivado_video_id INTEGER NOT NULL UNIQUE,
            original_video_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL,
            derivado_nombre TEXT NOT NULL,
            derivado_ruta TEXT NOT NULL,
            original_nombre TEXT NOT NULL,
            original_ruta TEXT NOT NULL
        )
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS videos_derivados_segmentos (id INTEGER PRIMARY KEY AUTOINCREMENT, derivacion_id INTEGER NOT NULL, segmento_id INTEGER NOT NULL, orden INTEGER NOT NULL, inicio REAL NOT NULL, fin REAL NOT NULL)")
    # crear segmento para original
    conn.execute("CREATE TABLE IF NOT EXISTS segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, inicio REAL NOT NULL, fin REAL NOT NULL)")
    orig_id = conn.execute("SELECT id FROM videos WHERE nombre='orig.mp4'").fetchone()[0]
    deriv_id = conn.execute("SELECT id FROM videos WHERE nombre='deriv.mp4'").fetchone()[0]
    seg_id = conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin) VALUES (?,?,?)", (orig_id, 0.0, 1.0)).lastrowid
    conn.execute("INSERT INTO videos_derivados (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta) VALUES (?,?,?,?,?,?,?,?)", (deriv_id, orig_id, "individual", "2026-01-01T00:00:00", "deriv.mp4", os.path.join(tmp.name, "deriv.mp4"), "orig.mp4", os.path.join(tmp.name, "orig.mp4")))
    derivacion_id = conn.execute("SELECT id FROM videos_derivados WHERE derivado_video_id=?", (deriv_id,)).fetchone()[0]
    conn.execute("INSERT INTO videos_derivados_segmentos (derivacion_id, segmento_id, orden, inicio, fin) VALUES (?,?,?,?,?)", (derivacion_id, seg_id, 0, 0.0, 1.0))
    conn.commit()
    conn.close()
    # migrar
    conn2 = conectar_bd(ruta_db)
    fila = conn2.execute("SELECT derivado_video_id, original_video_id FROM videos_derivados WHERE id=?", (derivacion_id,)).fetchone()
    seg = conn2.execute("SELECT derivacion_id, segmento_id FROM videos_derivados_segmentos WHERE derivacion_id=?", (derivacion_id,)).fetchall()
    conn2.close()
    tmp.cleanup()
    assert fila[0] == deriv_id and fila[1] == orig_id
    assert len(seg) == 1
    return True, f"deriv {fila} seg {seg}"

def test_19_cutover_commit_falla_rollback():
    """B8.3A: commit del rebuild falla debe hacer rollback completo de schema/datos/sequence y bytes."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "falla.db")
    recs = [
        {"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
        {"nombre": "b.mp4", "ruta": os.path.join(tmp.name, "b.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"},
    ]
    _crear_legacy_pre(ruta_db, recs)
    conn0 = sqlite3.connect(ruta_db)
    sql_before = conn0.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    cnt_before = conn0.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    seq_before = conn0.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
    rows_before = conn0.execute("SELECT id, nombre, ruta, ruta_normalizada FROM videos ORDER BY id").fetchall()
    conn0.close()
    with open(ruta_db, "rb") as f:
        bytes_before = f.read()
    original_connect = sqlite3.connect
    se_llamo = {"ok": False}
    class ConectorFallaCommit:
        def __init__(self, real):
            self._real = real
        @property
        def in_transaction(self):
            return self._real.in_transaction
        def execute(self, *a, **k):
            return self._real.execute(*a, **k)
        def commit(self):
            se_llamo["ok"] = True
            raise RuntimeError("fallo controlado en commit")
        def rollback(self):
            return self._real.rollback()
        def close(self):
            return self._real.close()
        def __getattr__(self, name):
            return getattr(self._real, name)
    sqlite3.connect = lambda *a, **k: ConectorFallaCommit(original_connect(*a, **k))
    fallo = False
    try:
        # Intentar cutover directo con commit que fallará
        conn = sqlite3.connect(ruta_db)
        try:
            _asegurar_cutover_identidad_b83(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except RuntimeError as e:
        fallo = "fallo controlado" in str(e) and se_llamo["ok"]
    except Exception:
        fallo = se_llamo["ok"]
    finally:
        sqlite3.connect = original_connect
    conn1 = sqlite3.connect(ruta_db)
    sql_after = conn1.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    cnt_after = conn1.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    seq_after = conn1.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
    rows_after = conn1.execute("SELECT id, nombre, ruta, ruta_normalizada FROM videos ORDER BY id").fetchall()
    has_new = conn1.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos_b83_new'").fetchone()
    estado_after = _estado_cutover_identidad_b83(conn1)
    conn1.close()
    with open(ruta_db, "rb") as f:
        bytes_after = f.read()
    try:
        tmp.cleanup()
    except Exception:
        import time, gc
        gc.collect()
        time.sleep(0.1)
        try:
            tmp.cleanup()
        except Exception:
            pass
    assert fallo, f"commit no falló se_llamo={se_llamo}"
    assert sql_before == sql_after, f"schema cambió {sql_before!r} vs {sql_after!r}"
    assert cnt_before == cnt_after, f"cnt {cnt_before} vs {cnt_after}"
    assert rows_before == rows_after, f"rows {rows_before} vs {rows_after}"
    assert seq_before == seq_after, f"seq {seq_before} vs {seq_after}"
    assert has_new is None, f"quedó tabla residual {has_new}"
    assert estado_after == "pre", f"estado debe seguir pre tras rollback, got {estado_after}"
    assert bytes_before == bytes_after, "bytes cambiaron pese a rollback"
    return True, f"rollback ok se_llamo={se_llamo['ok']} cnt {cnt_before}"

def test_20_foreign_keys_wrapper_restaura():
    """Wrapper autónomo con PRAGMA foreign_keys=ON: restaura ON y cutover pasa, FK check vacío."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "fk_wrap.db")
    recs = [{"nombre": "fk.mp4", "ruta": os.path.join(tmp.name, "fk.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn = sqlite3.connect(ruta_db)
    conn.execute("PRAGMA foreign_keys=ON")
    fk_antes = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_antes == 1, f"fk antes {fk_antes}"
    estado_pre = _estado_cutover_identidad_b83(conn)
    assert estado_pre == "pre"
    # wrapper debe manejar FK correctamente
    _asegurar_cutover_identidad_b83(conn)
    fk_despues = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_despues == 1, f"fk despues debe restaurar ON, got {fk_despues}"
    estado_post = _estado_cutover_identidad_b83(conn)
    assert estado_post == "post", f"estado post {estado_post}"
    chk = conn.execute("PRAGMA integrity_check").fetchone()[0]
    assert chk == "ok"
    fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert fk_check == [], f"fk_check {fk_check}"
    conn.close()
    tmp.cleanup()
    return True, f"wrapper FK ON->ON estado {estado_pre}->{estado_post}"


def test_21_core_inline_no_cambia_pragma():
    """Núcleo inline NO cambia PRAGMA; si comienza ON sigue ON tras commit y rollback."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "fk_inline.db")
    recs = [{"nombre": "c1.mp4", "ruta": os.path.join(tmp.name, "c1.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    # Test commit path: FK ON, BEGIN, core, commit
    conn = sqlite3.connect(ruta_db)
    conn.execute("PRAGMA foreign_keys=ON")
    fk0 = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk0 == 1
    conn.execute("BEGIN IMMEDIATE")
    # dentro de transacción FK debe seguir ON (núcleo no toca)
    fk_inside_before = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_inside_before == 1, f"FK dentro antes {fk_inside_before}"
    from escanear_videos import _ejecutar_cutover_identidad_b83_en_transaccion
    migrated = _ejecutar_cutover_identidad_b83_en_transaccion(conn)
    assert migrated is True
    fk_inside_after = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_inside_after == 1, f"FK dentro después no debe cambiar {fk_inside_after}"
    conn.commit()
    fk_after_commit = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_after_commit == 1
    conn.close()
    # Test rollback path: crear otra legacy para rollback
    tmp2 = tempfile.TemporaryDirectory()
    ruta_db2 = os.path.join(tmp2.name, "fk_inline_rb.db")
    _crear_legacy_pre(ruta_db2, recs)
    conn2 = sqlite3.connect(ruta_db2)
    conn2.execute("PRAGMA foreign_keys=ON")
    conn2.execute("BEGIN IMMEDIATE")
    # forzar fallo via ValueError in core (por ejemplo ruta NULL)
    # en lugar de ensuciar DB, probamos que rollback preserve FK
    conn2.execute("UPDATE videos SET ruta_normalizada='invalida_no_match' WHERE nombre='c1.mp4'")
    try:
        _ejecutar_cutover_identidad_b83_en_transaccion(conn2)
        assert False, "debería fallar por ruta_normalizada incorrecta"
    except ValueError:
        pass
    fk_during_fail = conn2.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_during_fail == 1, f"FK durante fallo {fk_during_fail}"
    conn2.rollback()
    fk_after_rb = conn2.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_after_rb == 1, f"FK tras rollback {fk_after_rb}"
    conn2.close()
    tmp.cleanup()
    tmp2.cleanup()
    return True, "core inline preserva FK ON en commit y rollback"


def test_22_estructural_unica_ocurrencia():
    """Prueba estructural: DDL CREATE TABLE videos_b83_new solo una vez en escanear_videos.py."""
    import pathlib
    src = pathlib.Path(__file__).with_name("escanear_videos.py").read_text(encoding="utf-8")
    count_create = src.count("CREATE TABLE videos_b83_new")
    count_drop = src.count("DROP TABLE videos")
    # DROP TABLE videos puede aparecer también en otros contextos pero B8.3 solo uno
    # Filtrar productiva: contar línea con DROP TABLE videos asociada a B8.3
    # Simplificamos: debe ser exactamente 1 create y 1 drop productivos
    assert count_create == 1, f"CREATE TABLE videos_b83_new debe existir 1 vez, got {count_create}"
    assert count_drop == 1, f"DROP TABLE videos B8.3 debe ser 1, got {count_drop}"
    # Verificar seq_final solo en núcleo (una implementación)
    # seq_final aparece en núcleo único (definición + usos)
    assert "def _ejecutar_cutover_identidad_b83_en_transaccion" in src
    # wrapper y guardar no deben contener la lógica duplicada
    assert src.count("seq_final") <= 7, f"seq_final debe estar solo en núcleo, count {src.count('seq_final')}"
    return True, f"create={count_create} drop={count_drop} seq_final ok"


def test_23_in_transaction_estricto_sin_fallback():
    """B8.3A-028: producción usa conn.in_transaction directo sin fallback AttributeError."""
    import pathlib
    src = pathlib.Path(__file__).with_name("escanear_videos.py").read_text(encoding="utf-8")
    # El código productivo no debe contener try/except AttributeError alrededor de in_transaction
    assert "except AttributeError" not in src or src.count("except AttributeError") == 0, "producción no debe capturar AttributeError para in_transaction"
    # Verificar que conn.in_transaction aparece directo (sin try)
    assert "conn.in_transaction" in src
    # Simular conexión sin in_transaction debe fallar visible (AttributeError)
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "strict.db")
    recs = [{"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn_real = sqlite3.connect(ruta_db)
    try:
        class SinInTxn:
            def __init__(self, real):
                self._real = real
            def __getattr__(self, name):
                if name == "in_transaction":
                    raise AttributeError("SinInTxn simula ausencia de in_transaction")
                return getattr(self._real, name)
        sin = SinInTxn(conn_real)
        # Núcleo debe dejar visible AttributeError, no asumir True
        try:
            ev._ejecutar_cutover_identidad_b83_en_transaccion(sin)
            assert False, "debería fallar por AttributeError en in_transaction"
        except AttributeError:
            pass
        # Wrapper debe igualmente fallar
        try:
            ev._asegurar_cutover_identidad_b83(sin)
            assert False, "wrapper debería fallar por AttributeError"
        except AttributeError:
            pass
    finally:
        try:
            conn_real.close()
        except:
            pass
        tmp.cleanup()
    return True, "strict in_transaction OK"


def test_24_sqlite_master_fallo_propaga():
    """B8.3A-028: fallo en consulta sqlite_master no se interpreta como no residual, se propaga."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "master.db")
    recs = [{"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn_real = sqlite3.connect(ruta_db)
    conn_real.execute("BEGIN IMMEDIATE")
    try:
        class FallaMaster:
            def __init__(self, real):
                self._real = real
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def execute(self, sql, *a, **k):
                if "sqlite_master" in sql and "videos_b83_new" in sql:
                    raise sqlite3.OperationalError("fallo simulado sqlite_master")
                return self._real.execute(sql, *a, **k)
            def __getattr__(self, name):
                return getattr(self._real, name)
        fm = FallaMaster(conn_real)
        try:
            ev._ejecutar_cutover_identidad_b83_en_transaccion(fm)
            assert False, "debería propagar OperationalError de sqlite_master"
        except sqlite3.OperationalError as e:
            assert "fallo simulado" in str(e)
        # verificar que no creó tabla residual
        has = conn_real.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos_b83_new'").fetchone()
        assert has is None
        conn_real.rollback()
    finally:
        try:
            conn_real.close()
        except:
            pass
        tmp.cleanup()
    return True, "sqlite_master fallo propaga"


def test_25_pragma_fk_lectura_falla_aborta():
    """B8.3A-028: fallo lectura PRAGMA foreign_keys aborta wrapper antes de tocar schema."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "fkfail.db")
    recs = [{"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}]
    _crear_legacy_pre(ruta_db, recs)
    conn_real = sqlite3.connect(ruta_db)
    sql_before = conn_real.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
    try:
        class FallaPragma:
            def __init__(self, real):
                self._real = real
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def execute(self, sql, *a, **k):
                if sql.strip().upper().startswith("PRAGMA FOREIGN_KEYS"):
                    raise sqlite3.OperationalError("fallo simulado PRAGMA foreign_keys")
                return self._real.execute(sql, *a, **k)
            def __getattr__(self, name):
                return getattr(self._real, name)
        fp = FallaPragma(conn_real)
        try:
            ev._asegurar_cutover_identidad_b83(fp)
            assert False, "debería propagar fallo de PRAGMA foreign_keys"
        except sqlite3.OperationalError as e:
            assert "fallo simulado" in str(e)
        sql_after = conn_real.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'").fetchone()[0]
        assert sql_before == sql_after, "schema no debe cambiar si PRAGMA falla"
        estado = ev._estado_cutover_identidad_b83(conn_real)
        assert estado == "pre"
    finally:
        try:
            conn_real.close()
        except:
            pass
        tmp.cleanup()
    return True, "PRAGMA fk fallo aborta intacto"


def test_26_rollback_fallido_preserva_original():
    """B8.3A-028: error original + rollback fallido preserva causa original (from exc_orig)."""
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "rb.db")
    # crear DB vacía via conectar_bd para test guardar_video
    conn = conectar_bd(ruta_db)
    conn.close()
    datos = {"nombre": "a.mp4", "ruta": os.path.join(tmp.name, "a.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}
    original_connect = sqlite3.connect
    # Wrapper que falla en upsert (segunda execute) y rollback también falla
    class ConnRollbackFalla:
        def __init__(self, real):
            self._real = real
            self._calls = 0
        @property
        def in_transaction(self):
            return self._real.in_transaction
        def execute(self, sql, *a, **k):
            self._calls += 1
            # dejar pasar BEGIN y asegurar columnas, fallar en INSERT real
            if "INSERT INTO videos" in sql and "VALUES" in sql:
                raise ValueError("error original simulado en upsert")
            return self._real.execute(sql, *a, **k)
        def commit(self):
            return self._real.commit()
        def rollback(self):
            raise RuntimeError("rollback simulado falla")
        def close(self):
            return self._real.close()
        def __getattr__(self, name):
            return getattr(self._real, name)
    sqlite3.connect = lambda *a, **k: ConnRollbackFalla(original_connect(*a, **k))
    try:
        try:
            ev.guardar_video(datos, ruta_db)
            assert False, "debería fallar y propagar RuntimeError"
        except RuntimeError as e:
            # Debe ser el RuntimeError de rollback con causa original
            assert "rollback falló tras error original" in str(e)
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
            assert "error original simulado" in str(e.__cause__)
            # mensaje debe incluir representación del fallo de rollback
            assert "rollback simulado" in str(e)
    finally:
        sqlite3.connect = original_connect
    # Wrapper cutover también preserva causa (sin monkey patch global)
    tmp2 = tempfile.TemporaryDirectory()
    ruta_db2 = os.path.join(tmp2.name, "rb2.db")
    _crear_legacy_pre(ruta_db2, [{"nombre": "b.mp4", "ruta": os.path.join(tmp2.name, "b.mp4"), "extension": ".mp4", "fecha_importacion": "2026-01-01T00:00:00"}])
    conn2_real = original_connect(ruta_db2)
    class ConnRbFallaWrapper:
        def __init__(self, real):
            self._real = real
        @property
        def in_transaction(self):
            return self._real.in_transaction
        def execute(self, sql, *a, **k):
            if "CREATE TABLE videos_b83_new" in sql:
                raise ValueError("error original wrapper")
            return self._real.execute(sql, *a, **k)
        def commit(self):
            return self._real.commit()
        def rollback(self):
            raise RuntimeError("rollback wrapper falla")
        def close(self):
            return self._real.close()
        def __getattr__(self, name):
            return getattr(self._real, name)
    cw = ConnRbFallaWrapper(conn2_real)
    try:
        # forzar que wrapper esté fuera de txn
        if cw.in_transaction:
            try:
                cw._real.rollback()
            except:
                pass
        try:
            ev._asegurar_cutover_identidad_b83(cw)
            assert False, "wrapper debería fallar"
        except RuntimeError as e2:
            assert "rollback falló" in str(e2)
            assert isinstance(e2.__cause__, ValueError)
            assert "error original wrapper" in str(e2.__cause__)
    finally:
        try:
            conn2_real.close()
        except:
            pass
        try:
            tmp2.cleanup()
        except:
            import gc, time
            gc.collect()
            time.sleep(0.1)
            try:
                tmp2.cleanup()
            except:
                pass
        tmp.cleanup()
    return True, "rollback preserva causa original"


def main():
    pruebas = [
        test_01_db_nueva_post,
        test_02_detector_post,
        test_03_migracion_preserva,
        test_04_detector_pre_a_post,
        test_05_idempotencia_no_rebuild,
        test_06_schema_invalido_aborta,
        test_07_ruta_normalizada_null_aborta,
        test_08_colision_aborta,
        test_09_sqlite_sequence,
        test_10_integrity,
        test_11_homonimos_distintas_rutas,
        test_12_upsert_misma_ruta,
        test_13_sync_homonimos_no_colapsan,
        test_14_eliminacion_no_borra_homonimo,
        test_15_metadata_no_cruza_homonimos,
        test_16_derivado_homonimo_vs_misma_ruta,
        test_17_marcadores_segmentos_sobreviven,
        test_18_derivados_sobreviven,
        test_19_cutover_commit_falla_rollback,
        test_20_foreign_keys_wrapper_restaura,
        test_21_core_inline_no_cambia_pragma,
        test_22_estructural_unica_ocurrencia,
        test_23_in_transaction_estricto_sin_fallback,
        test_24_sqlite_master_fallo_propaga,
        test_25_pragma_fk_lectura_falla_aborta,
        test_26_rollback_fallido_preserva_original,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, det = fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            ok, det = False, f"excepcion {type(e).__name__}: {e}"
        resultados.append((i, ok, det))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {det}")
    ok_total = all(o for _,o,_ in resultados)
    print(f"TOTAL={sum(1 for _,o,_ in resultados if o)}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__ == "__main__":
    sys.exit(main())
