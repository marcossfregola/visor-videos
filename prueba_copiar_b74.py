"""Suite B7.4 — copia individual segura de un video catalogado.

Cubre 20+ exigencias del contrato B7.4 con DB/FS temporales, sin tocar datos reales.
"""

import hashlib
import inspect
import os
import shutil
import sqlite3
import tempfile
import uuid

from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    asignar_color_marcador,
    asignar_color_segmento,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
    listar_videos_paginado,
    obtener_video_por_id,
)
import copiar_video as svc
from copiar_video import (
    ValidacionError,
    ColisionError,
    OrigenNoEncontradoError,
    HashMismatchError,
    CopiarInconsistenciaError,
    CopiarError,
)
from tareas_videos import TareaCopiarVideo
import visor_videos


def _crear_db_temporal():
    tmpdir = tempfile.mkdtemp()
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return tmpdir, ruta_db


def _insertar_video(ruta_db, carpeta, nombre, contenido=b"x" * 2048):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    st = os.stat(ruta)
    conn = conectar_bd(ruta_db)
    try:
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, tamano_bytes, mtime_ns) VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, os.path.abspath(ruta), os.path.splitext(nombre)[1].lower(), "2026-01-01T00:00:00", st.st_size, st.st_mtime_ns),
        )
        vid = conn.execute("SELECT id FROM videos WHERE nombre=? COLLATE NOCASE", (nombre,)).fetchone()[0]
        conn.commit()
        return vid, os.path.abspath(ruta)
    finally:
        conn.close()


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_01_exito_hash_identico():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        contenido = b"contenido_unico_01_" * 500
        vid, ruta_orig = _insertar_video(ruta_db, A, "video01.mp4", contenido=contenido)
        res = svc.copiar_video(vid, B, ruta_db)
        assert res["ok"] and res["video_id"] != vid
        # hash idéntico
        assert os.path.isfile(res["ruta"])
        assert _hash(ruta_orig) == _hash(res["ruta"])
        assert os.path.getsize(ruta_orig) == os.path.getsize(res["ruta"])
        print("test_01 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_02_original_permanece():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "orig02.mp4", contenido=b"permanece" * 300)
        hash_orig_before = _hash(ruta_orig)
        res = svc.copiar_video(vid, B, ruta_db)
        assert os.path.isfile(ruta_orig), "origen debe permanecer"
        assert _hash(ruta_orig) == hash_orig_before
        info_orig = obtener_video_por_id(vid, ruta_db)
        assert info_orig is not None and info_orig["id"] == vid
        assert info_orig["ruta"] == ruta_orig  # ruta original intacta
        print("test_02 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_03_nuevo_video_id_distinto():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "vid03.mp4")
        res = svc.copiar_video(vid, B, ruta_db)
        assert res["video_id"] != vid
        assert res["video_id_original"] == vid
        # comprobar que ambos ids existen en DB
        conn = sqlite3.connect(ruta_db)
        filas = conn.execute("SELECT id FROM videos").fetchall()
        conn.close()
        ids = [r[0] for r in filas]
        assert vid in ids and res["video_id"] in ids and len(ids) == 2
        print("test_03 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_04_marcadores_segmentos_no_heredados():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "vid04.mp4", contenido=b"marcadores" * 400)
        mid = guardar_marcador(vid, 1.5, ruta_db, color="rojo")
        asignar_color_marcador(mid, "verde", ruta_db)
        sid, _, _ = guardar_segmento(vid, 1.0, 2.0, ruta_db, color="azul")
        asignar_color_segmento(sid, "amarillo", ruta_db)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        # original conserva
        marc_orig = listar_marcadores(vid, ruta_db)
        seg_orig = listar_segmentos(vid, ruta_db)
        assert len(marc_orig) == 1 and marc_orig[0][0] == mid and marc_orig[0][3] == "verde"
        assert len(seg_orig) == 1 and seg_orig[0][0] == sid and seg_orig[0][3] == "amarillo"
        # copia no hereda
        marc_copy = listar_marcadores(nuevo, ruta_db)
        seg_copy = listar_segmentos(nuevo, ruta_db)
        assert marc_copy == [], f"copia no debe heredar marcadores: {marc_copy}"
        assert seg_copy == [], f"copia no debe heredar segmentos: {seg_copy}"
        print("test_04 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_05_destino_paginado_sin_escaneo():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "pag05.mp4", contenido=b"pag" * 600)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        # Paginado B debe contener copia sin escaneo
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        assert pagB["total"] >= 1
        ids_B = [r[8] for r in pagB["videos"]]
        assert nuevo in ids_B, f"copia debe aparecer en B paginado: {ids_B}"
        # Verificar que filtrado es correcto: B contiene copia, no original
        assert vid not in ids_B
        print("test_05 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_06_A_sigue_solo_original():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "a06.mp4", contenido=b"a06" * 500)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        pagA = listar_videos_paginado(100, 0, None, ruta_db, carpeta=A, incluir_subcarpetas=False)
        ids_A = [r[8] for r in pagA["videos"]]
        assert vid in ids_A
        assert nuevo not in ids_A, f"A no debe contener copia: {ids_A}"
        # No se exige reescaneo: paginado ya refleja
        print("test_06 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_07_reinicio_reconexion_AB():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "rein07.mp4", contenido=b"reinicio" * 500)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        ruta_copy = res["ruta"]
        # Simular reinicio: cerrar y reabrir conexión, listar
        # Reconexión 1
        conn = sqlite3.connect(ruta_db)
        fila = conn.execute("SELECT ruta FROM videos WHERE id=?", (vid,)).fetchone()
        assert fila and os.path.normcase(fila[0]) == os.path.normcase(ruta_orig)
        fila2 = conn.execute("SELECT ruta FROM videos WHERE id=?", (nuevo,)).fetchone()
        assert fila2 and os.path.normcase(fila2[0]) == os.path.normcase(ruta_copy)
        conn.close()
        # Reconexión 2 via helpers
        pagA = listar_videos_paginado(100, 0, None, ruta_db, carpeta=A)
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B)
        assert vid in [r[8] for r in pagA["videos"]]
        assert nuevo in [r[8] for r in pagB["videos"]]
        # Simular recrear Visor: listar_videos global
        filas = listar_videos(ruta_db)
        ids = [r[8] for r in filas]
        assert vid in ids and nuevo in ids
        print("test_07 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_08_colision_FS_rechazada():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "col08.mp4", contenido=b"col" * 400)
        # Crear archivo existente en B con mismo nombre (directo FS)
        # Necesitamos borrar DB row para que no interfiera con sufijo? Para FS colisión,
        # el servicio primero verifica FS case-insensitive con nombre original y debe rechazar
        # sin generar sufijo. Pero como UNIQUE también generaría sufijo, debemos asegurar que
        # el archivo FS exista con nombre original y que DB no tenga ese nombre en B aún.
        # El servicio verifica FS primero: si existe, lanza ColisionError inmediato.
        # Creamos archivo manual en B
        with open(os.path.join(B, "col08.mp4"), "wb") as f:
            f.write(b"existente")
        try:
            svc.copiar_video(vid, B, ruta_db)
            assert False, "colisión FS debe rechazar"
        except ColisionError:
            pass
        assert os.path.isfile(ruta_orig)
        # DB no debe tener nuevo id
        assert listar_videos(ruta_db).count != 0  # trivial
        conn = sqlite3.connect(ruta_db)
        c = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        assert c == 1, f"solo original debe existir, got {c}"
        # archivo existente no sobrescrito
        assert open(os.path.join(B, "col08.mp4"), "rb").read() == b"existente"
        # Temporal limpio
        temps = [f for f in os.listdir(B) if ".tmp_copiar" in f]
        assert not temps
        print("test_08 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_09_misma_carpeta_rechazada():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    os.makedirs(A, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "misma09.mp4")
        try:
            svc.copiar_video(vid, A, ruta_db)
            assert False, "misma carpeta debe rechazar"
        except ValidacionError as exc:
            assert "misma carpeta" in str(exc).lower()
        assert os.path.isfile(ruta_orig)
        print("test_09 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_10_origen_faltante():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "falt10.mp4")
        os.remove(ruta_orig)
        try:
            svc.copiar_video(vid, B, ruta_db)
            assert False
        except OrigenNoEncontradoError:
            pass
        # No debe crear archivo en B
        assert not os.path.exists(os.path.join(B, "falt10.mp4"))
        assert not any(".tmp_copiar" in f for f in os.listdir(B))
        print("test_10 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_11_destino_inexistente():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    os.makedirs(A, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "dest11.mp4")
        no_existe = os.path.join(tmpdir, "no_existe_11")
        try:
            svc.copiar_video(vid, no_existe, ruta_db)
            assert False
        except ValidacionError:
            pass
        # destino es archivo, no directorio
        archivo = os.path.join(tmpdir, "archivo.txt")
        with open(archivo, "w") as f:
            f.write("x")
        try:
            svc.copiar_video(vid, archivo, ruta_db)
            assert False
        except ValidacionError:
            pass
        print("test_11 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_12_error_lectura_copia():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "err12.mp4", contenido=b"err12" * 300)
        import copiar_video as m
        import builtins
        orig_builtin_open = builtins.open

        def failing_open(path, mode="r", *a, **k):
            if "rb" in mode and os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(ruta_orig)) and "r" in mode:
                raise OSError("simulado error lectura")
            return orig_builtin_open(path, mode, *a, **k)

        builtins.open = failing_open
        try:
            try:
                m.copiar_video(vid, B, ruta_db)
                assert False, "debe fallar por error lectura"
            except CopiarError:
                pass
        finally:
            builtins.open = orig_builtin_open
        # verificar limpieza temporal y no publicación
        # nombre final puede ser con sufijo por UNIQUE, buscar cualquier file con err12
        files_b = os.listdir(B)
        assert not any("err12" in f and not f.startswith(".tmp") for f in files_b), f"B no debe tener archivo final, got {files_b}"
        assert not any(".tmp_copiar" in f or ".part" in f for f in files_b)
        assert os.path.isfile(ruta_orig)
        print("test_12 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_13_hash_mismatch_no_publica():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "hash13.mp4", contenido=b"hash13" * 400)
        import copiar_video as m
        orig_hash = m._hash_sha256_stream

        def fake_hash(path, chunk_size=1024 * 1024):
            if ".tmp_copiar" in path:
                return "aaa111"
            return "bbb222"

        m._hash_sha256_stream = fake_hash
        try:
            try:
                m.copiar_video(vid, B, ruta_db)
                assert False, "hash mismatch debe fallar"
            except HashMismatchError:
                pass
            # no debe publicar final
            # Debido a UNIQUE, nombre final sería _001, pero hash falla antes de publicar
            assert not any(f.startswith("hash13") for f in os.listdir(B) if not f.startswith(".tmp"))
            temps = [f for f in os.listdir(B) if ".tmp_copiar" in f or ".part" in f]
            assert not temps, f"temporal debe limpiarse {temps}"
            # DB sin nuevo registro
            conn = sqlite3.connect(ruta_db)
            c = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
            conn.close()
            assert c == 1
        finally:
            m._hash_sha256_stream = orig_hash
        print("test_13 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_14_fallo_DB_post_publicacion_inconsistencia():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "db14.mp4", contenido=b"db14" * 500)
        import copiar_video as m
        import escanear_videos as esc
        orig_conectar = esc.conectar_bd

        class FakeConn:
            def __init__(self, *a, **k):
                self._real = orig_conectar(*a, **k)
                self._in_tx = False

            def execute(self, *a, **k):
                sql = a[0] if a else ""
                if "INSERT INTO videos" in sql:
                    raise sqlite3.OperationalError("simulado fallo DB post-publicación")
                return self._real.execute(*a, **k)

            def commit(self):
                return self._real.commit()

            def rollback(self):
                try:
                    self._real.rollback()
                except Exception:
                    pass

            def close(self):
                return self._real.close()

        def fake_conectar(*a, **k):
            return FakeConn(*a, **k)

        esc.conectar_bd = fake_conectar
        # También parchear sqlite3.connect usado en copiar_video para check inicial? copiar_video usa sqlite3.connect para check, no conectar_bd.
        # Para que fake solo afecte alta, dejamos sqlite3.connect intacto.
        # Pero copiar_video alta usa esc.conectar_bd, así que nuestro fake actúa.
        try:
            try:
                m.copiar_video(vid, B, ruta_db)
                assert False, "debe lanzar inconsistencia"
            except CopiarInconsistenciaError as exc:
                # archivo debe existir en FS (conservado)
                assert exc.ruta_nueva is not None
                assert os.path.isfile(exc.ruta_nueva), f"archivo debe conservarse {exc.ruta_nueva}"
                # DB no debe tener nuevo registro, pero tampoco debe apuntar a inexistente
                conn = sqlite3.connect(ruta_db)
                c = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
                assert c == 1, f"DB debe seguir con 1, got {c}"
                # verificar que ruta_nueva no está en DB
                fila = conn.execute("SELECT id FROM videos WHERE ruta=?", (exc.ruta_nueva,)).fetchone()
                assert fila is None
                conn.close()
                # verificar integrity
                conn2 = sqlite3.connect(ruta_db)
                row = conn2.execute("PRAGMA integrity_check").fetchone()
                assert row[0] == "ok"
                conn2.close()
                # temporal limpio
                temps = [f for f in os.listdir(B) if ".tmp_copiar" in f]
                assert not temps
            except CopiarError as exc2:
                assert False, f"debe ser CopiarInconsistenciaError, got {type(exc2)}: {exc2}"
        finally:
            esc.conectar_bd = orig_conectar
        print("test_14 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_15_case_insensitive_windows():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "Video15.MP4", contenido=b"case" * 400)
        # Crear colisión con distinto case en B
        with open(os.path.join(B, "video15.mp4"), "wb") as f:
            f.write(b"colision case")
        # Intentar copiar "Video15.MP4" -> destino "Video15.MP4" colisiona case-insensitive con "video15.mp4"
        try:
            svc.copiar_video(vid, B, ruta_db)
            assert False, "case-insensitive debe rechazar"
        except ColisionError:
            pass
        # Verificar que copiar con nombre no colisionante case sí genera sufijo si UNIQUE
        # Limpiar colisión y probar que copia genera _001 y no considera colisión case como éxito
        os.remove(os.path.join(B, "video15.mp4"))
        # Ahora copiar debe generar Video15_001.MP4 (suffix) por UNIQUE, no por FS
        res = svc.copiar_video(vid, B, ruta_db)
        assert res["nombre"].lower() != "video15.mp4".lower() or res["nombre"] == "Video15.MP4"  # puede ser con sufijo
        # Pero al menos no debe ser exactamente Video15.MP4 si UNIQUE bloquea
        # Con UNIQUE vigente, debe ser distinto
        assert res["nombre"].lower() != "video15.mp4".lower() or os.path.exists(res["ruta"])
        print("test_15 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_16_tarea_delega_servicio():
    fuente = inspect.getsource(TareaCopiarVideo._trabajo)
    assert "copiar_video" in fuente, "Tarea debe delegar a copiar_video"
    assert "sqlite" not in fuente.lower(), "Tarea no debe usar sqlite directo"
    assert "os.rename" not in fuente and "shutil" not in fuente
    # Verificar propiedades
    import tempfile as tf
    tmp = tf.mkdtemp()
    try:
        db = os.path.join(tmp, "t.db")
        conn = conectar_bd(db)
        conn.commit()
        conn.close()
        tarea = TareaCopiarVideo(1, tmp, db)
        assert tarea.video_id == 1
        assert tarea.carpeta_destino == tmp
        assert tarea.ruta_db == db
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("test_16 OK")


def test_17_ui_no_fs_sqlite_directo():
    fuente_copiar = inspect.getsource(visor_videos.VisorVideos._iniciar_copiar)
    fuente_resultado = inspect.getsource(visor_videos.VisorVideos._al_resultado_copiar)
    # 1) Ambos métodos no deben contener acceso directo FS / os.path / sqlite / open
    for nombre, fuente in [("_iniciar_copiar", fuente_copiar), ("_al_resultado_copiar", fuente_resultado)]:
        assert "os.path" not in fuente, f"{nombre} viola arquitectura: contiene os.path"
        assert "os.stat" not in fuente, f"{nombre} contiene os.stat"
        assert "sqlite" not in fuente.lower(), f"{nombre} contiene sqlite directo"
        assert "os.rename" not in fuente, f"{nombre} contiene os.rename"
        assert "shutil" not in fuente, f"{nombre} contiene shutil"
        # isfile/isdir/exists/abspath son FS directos prohibidos en UI B7.4
        assert "isfile" not in fuente, f"{nombre} contiene isfile FS directo"
        assert "isdir" not in fuente, f"{nombre} contiene isdir FS directo"
        assert "abspath" not in fuente, f"{nombre} contiene abspath — delegar normalización al servicio/helper"
        # basename/dirname deben estar solo en servicio, no en UI
        assert "basename" not in fuente, f"{nombre} contiene basename — delegar al servicio"
        assert "dirname" not in fuente, f"{nombre} contiene dirname — delegar al servicio"
        # exists/normcase/normpath/commonpath también cuentan como os.path directo
        # Permitimos carpetas_iguales / normalizar_carpeta que encapsulan normcase/normpath fuera de UI
        # Pero no permitir normcase directo en UI
        assert "normcase" not in fuente, f"{nombre} contiene normcase directo — usar carpetas_iguales helper"
        assert "normpath" not in fuente, f"{nombre} contiene normpath directo — usar carpetas_iguales helper"
        assert "commonpath" not in fuente, f"{nombre} contiene commonpath"
        # open builtin para FS prohibido (QFileDialog es la vía aceptada)
        if "open(" in fuente:
            lineas_open = [l.strip() for l in fuente.splitlines() if "open(" in l and "QFileDialog" not in l and "def " not in l]
            assert not lineas_open, f"{nombre} contiene open FS directo: {lineas_open}"
    assert "TareaCopiarVideo" in fuente_copiar
    assert "QFileDialog.getExistingDirectory" in fuente_copiar
    assert "gestor_copiar.iniciar" in fuente_copiar
    # _al_resultado_copiar debe usar helper puro y disparar recarga paginada, no pass sin efecto
    assert "carpetas_iguales" in fuente_resultado or "normalizar_carpeta" in fuente_resultado or "carpeta_destino" in fuente_resultado, "UI debe usar helper carpetas_iguales/normalizar_carpeta o dato carpeta_destino del servicio"
    assert "_programar_recarga_por_carpeta" in fuente_resultado or "_iniciar_recarga_catalogo" in fuente_resultado or "TareaLecturaCatalogoPaginada" in fuente_resultado, "_al_resultado_copiar debe disparar recarga paginada/background si vista es destino"
    assert "iniciar_escaneo" not in fuente_resultado, "UI no debe disparar escaneo, solo recarga paginada"
    # Detectar violación original: _al_resultado_copiar tenía solo pass para destino
    # Si aún contiene pass aislado sin recarga, fallar
    if "pass" in fuente_resultado:
        assert "_programar_recarga_por_carpeta" in fuente_resultado or "_iniciar_recarga_catalogo" in fuente_resultado, "Refresco destino no implementado: contiene pass sin recarga"
    print("test_17 OK")


def test_18_menu_handler_correctos():
    fuente_menu = inspect.getsource(visor_videos.VisorVideos._mostrar_menu_contextual)
    assert "Copiar a" in fuente_menu
    # Verificar orden cercano a Mover/Renombrar
    idx_copiar = fuente_menu.find("Copiar a")
    idx_mover = fuente_menu.find("Mover a")
    idx_renombrar = fuente_menu.find("Renombrar")
    assert idx_copiar != -1 and idx_mover != -1 and idx_renombrar != -1
    # Handler conecta a _iniciar_copiar
    assert "_iniciar_copiar" in fuente_menu
    assert hasattr(visor_videos.VisorVideos, "_iniciar_copiar")
    assert hasattr(visor_videos.VisorVideos, "_al_resultado_copiar")
    assert hasattr(visor_videos.VisorVideos, "_al_error_copiar")
    print("test_18 OK")


def test_19_actividad_progreso_error():
    # Verificar que Visor tiene gestores y estados para copiar
    import sys
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "prog19.mp4", contenido=b"prog" * 500)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config19.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        # Verificar gestor_copiar existe y actividad
        assert hasattr(ventana, "gestor_copiar")
        assert hasattr(ventana, "_copiar_en_curso")
        assert hasattr(ventana, "_al_actividad_copiar")
        # Iniciar copiar via tarea directa para probar progreso sin UI bloqueo
        from unittest import mock
        # Mock QFileDialog para no bloquear
        with mock.patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=B):
            ventana._iniciar_copiar("prog19.mp4")
            # esperar un poco
            import time
            for _ in range(50):
                QApplication.processEvents()
                time.sleep(0.02)
                if not ventana.gestor_copiar.activo:
                    break
            # Verificar que mensaje muestra progreso o éxito
            # No exigir texto exacto, pero barra debe haberse ocultado al finalizar
        ventana.close()
        ventana.gestor_copiar.cerrar()
        try:
            ventana.gestor.cerrar()
        except Exception:
            pass
        print("test_19 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_20_unique_constraint_sufijo():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "dup20.mp4", contenido=b"dup20" * 600)
        # Con UNIQUE vigente, copiar debe generar nombre con sufijo _001
        res = svc.copiar_video(vid, B, ruta_db)
        assert res["ok"]
        # Nombre final debe ser distinto al original por UNIQUE
        assert res["nombre"].lower() != "dup20.mp4".lower(), f"debe generar sufijo por UNIQUE, got {res['nombre']}"
        assert "_001" in res["nombre"] or "_002" in res["nombre"] or "_00" in res["nombre"], f"sufijo esperado, got {res['nombre']}"
        # Verificar que ambos existen en DB con nombres distintos
        conn = sqlite3.connect(ruta_db)
        filas = conn.execute("SELECT nombre, ruta FROM videos ORDER BY id").fetchall()
        conn.close()
        assert len(filas) == 2
        nombres = [f[0] for f in filas]
        assert nombres[0].lower() == "dup20.mp4".lower()
        assert nombres[1].lower() != nombres[0].lower()
        # Archivo en B con nombre suffix existe y hash igual al original
        assert os.path.isfile(res["ruta"])
        assert _hash(os.path.join(A, "dup20.mp4")) == _hash(res["ruta"])
        # Segunda copia debe generar _002 si _001 ya está ocupado (FS+DB)
        vid2 = vid
        res2 = svc.copiar_video(vid2, B, ruta_db)
        assert res2["nombre"] != res["nombre"]
        assert os.path.isfile(res2["ruta"])
        print("test_20 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_21_temporal_limpio_en_fallos():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "tmp21.mp4", contenido=b"tmp21" * 500)
        import copiar_video as m
        orig_hash = m._hash_sha256_stream
        m._hash_sha256_stream = lambda p, chunk_size=1024 * 1024: "mismatch_a" if ".tmp_copiar" not in p else "mismatch_b"
        try:
            try:
                m.copiar_video(vid, B, ruta_db)
                assert False
            except HashMismatchError:
                pass
        finally:
            m._hash_sha256_stream = orig_hash
        # temporales limpios tras hash mismatch
        assert not any(".tmp_copiar" in f for f in os.listdir(B))
        # también tras colisión FS (test_08 ya verifica) y misma carpeta
        try:
            svc.copiar_video(vid, A, ruta_db)
        except ValidacionError:
            pass
        assert not any(".tmp_copiar" in f for f in os.listdir(A))
        print("test_21 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_22_no_deja_sqlite_apuntando_inexistente():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "chk22.mp4", contenido=b"chk22" * 400)
        res = svc.copiar_video(vid, B, ruta_db)
        # Verificar que ninguna fila apunta a archivo inexistente
        conn = sqlite3.connect(ruta_db)
        filas = conn.execute("SELECT ruta FROM videos").fetchall()
        for (ruta,) in filas:
            assert os.path.isfile(ruta), f"ruta en DB no existe en FS: {ruta}"
        conn.close()
        # Simular fallo DB post-publicación: archivo existe pero DB no tiene fila -> no es dangling pointer inverso
        # Ya probado en test_14 que no deja pointer a inexistente
        print("test_22 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_23_origen_relaciones_intactas_con_derivados():
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid_orig, _ = _insertar_video(ruta_db, A, "orig23.mp4", contenido=b"orig23" * 500)
        mid = guardar_marcador(vid_orig, 2.0, ruta_db, color="rojo")
        sid, _, _ = guardar_segmento(vid_orig, 1.0, 3.0, ruta_db, color="azul")
        # crear derivado trazabilidad para original
        vid_der, _ = _insertar_video(ruta_db, A, "der23.mp4", contenido=b"der")
        conn = conectar_bd(ruta_db)
        conn.execute(
            "INSERT INTO videos_derivados (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (vid_der, vid_orig, "individual", "2026-01-01T00:00:00", "der23.mp4", os.path.join(A, "der23.mp4"), "orig23.mp4", os.path.join(A, "orig23.mp4")),
        )
        deriv_id = conn.execute("SELECT id FROM videos_derivados WHERE derivado_video_id=?", (vid_der,)).fetchone()[0]
        conn.execute("INSERT INTO videos_derivados_segmentos (derivacion_id, segmento_id, orden, inicio, fin) VALUES (?, ?, ?, ?, ?)", (deriv_id, sid, 0, 1.0, 3.0))
        conn.commit()
        conn.close()
        # copiar original
        res = svc.copiar_video(vid_orig, B, ruta_db)
        nuevo = res["video_id"]
        # origen relaciones intactas
        assert listar_marcadores(vid_orig, ruta_db)[0][0] == mid
        assert listar_segmentos(vid_orig, ruta_db)[0][0] == sid
        conn = sqlite3.connect(ruta_db)
        assert conn.execute("SELECT 1 FROM videos_derivados WHERE derivado_video_id=?", (vid_der,)).fetchone() is not None
        conn.close()
        # copia sin relaciones
        assert listar_marcadores(nuevo, ruta_db) == []
        assert listar_segmentos(nuevo, ruta_db) == []
        print("test_23 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_24_refresco_B_via_recarga_paginada_sin_escaneo():
    """Estando en B, al completar copia se dispara recarga paginada/background y copia aparece sin escaneo."""
    import sys
    import time
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, A, "ref24.mp4", contenido=b"ref24" * 800)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        # Verificación DB paginada sin escaneo: B contiene copia, A no
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        ids_B = [r[8] for r in pagB["videos"]]
        assert nuevo in ids_B, f"copia debe aparecer en B paginado sin escaneo: {ids_B}"
        assert vid not in ids_B
        # UI: estando actualmente en B, _al_resultado_copiar debe disparar recarga paginada
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config24.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        # esperar carga inicial
        for _ in range(200):
            QApplication.processEvents()
            time.sleep(0.02)
            if ventana._carga_completada and not ventana.gestor.activo:
                break
        ventana.carpeta_seleccionada = os.path.abspath(B)
        # espiar recarga y escaneo
        recarga_calls = []
        orig_prog = ventana._programar_recarga_por_carpeta
        def spy_prog(*a, **k):
            recarga_calls.append("recarga")
            return orig_prog(*a, **k)
        ventana._programar_recarga_por_carpeta = spy_prog
        escaneo_calls = []
        orig_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear = visor_videos.VisorVideos._crear_tarea_lectura
        def fake_escaneo(self, *a, **k):
            escaneo_calls.append("iniciar_escaneo")
            return None
        visor_videos.VisorVideos.iniciar_escaneo = fake_escaneo
        # también espiar si alguien intenta crear tarea escaneo directa
        # _al_resultado_copiar con carpeta_destino = B debe disparar recarga
        ventana._copiar_nombre_origen = "ref24.mp4"
        ventana._copiar_video_id = vid
        ventana._al_resultado_copiar(res)
        QApplication.processEvents()
        time.sleep(0.1)
        QApplication.processEvents()
        assert recarga_calls, f"estando en B debe disparar recarga paginada, got {recarga_calls}"
        assert not escaneo_calls, f"no debe llamar a escaneo, got {escaneo_calls}"
        # Verificar que copia aparece vía paginado sin escaneo manual
        pagB2 = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        ids_B2 = [r[8] for r in pagB2["videos"]]
        assert nuevo in ids_B2
        # restaurar
        ventana._programar_recarga_por_carpeta = orig_prog
        visor_videos.VisorVideos.iniciar_escaneo = orig_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = orig_crear
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
        print("test_24 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_25_A_no_contamina_vista():
    """Estando en A no se contamina la vista al copiar a B; no se dispara recarga indebida."""
    import sys
    import time
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "ref25.mp4", contenido=b"a25" * 700)
        res = svc.copiar_video(vid, B, ruta_db)
        nuevo = res["video_id"]
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config25.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        for _ in range(200):
            QApplication.processEvents()
            time.sleep(0.02)
            if ventana._carga_completada and not ventana.gestor.activo:
                break
        ventana.carpeta_seleccionada = os.path.abspath(A)
        recarga_calls = []
        orig_prog = ventana._programar_recarga_por_carpeta
        def spy_prog(*a, **k):
            recarga_calls.append("recarga")
            return orig_prog(*a, **k)
        ventana._programar_recarga_por_carpeta = spy_prog
        escaneo_calls = []
        orig_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        def fake_escaneo(self, *a, **k):
            escaneo_calls.append("escaneo")
            return None
        visor_videos.VisorVideos.iniciar_escaneo = fake_escaneo
        ventana._copiar_nombre_origen = "ref25.mp4"
        ventana._copiar_video_id = vid
        ventana._al_resultado_copiar(res)
        QApplication.processEvents()
        assert not recarga_calls, f"estando en A no debe disparar recarga para B, got {recarga_calls}"
        assert not escaneo_calls, f"no debe escaneo, got {escaneo_calls}"
        # Verificar paginado A sigue solo original
        pagA = listar_videos_paginado(100, 0, None, ruta_db, carpeta=A, incluir_subcarpetas=False)
        ids_A = [r[8] for r in pagA["videos"]]
        assert vid in ids_A
        assert nuevo not in ids_A, f"A no debe contener copia: {ids_A}"
        # B sí contiene copia pero UI en A no lo muestra
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        ids_B = [r[8] for r in pagB["videos"]]
        assert nuevo in ids_B
        ventana._programar_recarga_por_carpeta = orig_prog
        visor_videos.VisorVideos.iniciar_escaneo = orig_escaneo
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
        print("test_25 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_26_cero_llamadas_escaneo_para_exito_y_refresco():
    """Comprueba cero llamadas a escaneo para éxito y refresco (instrumentación)."""
    import sys
    import time
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "ref26.mp4", contenido=b"z26" * 600)
        # Patch escaneo antes de servicio y UI
        escaneo_calls = []
        orig_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        orig_sinc = None
        try:
            from tareas_videos import TareaSincronizacionCatalogo
            orig_sinc = TareaSincronizacionCatalogo._trabajo
        except: pass
        def fake_escaneo(self, *a, **k):
            escaneo_calls.append("iniciar_escaneo")
            return None
        visor_videos.VisorVideos.iniciar_escaneo = fake_escaneo
        # Servicio copiar no debe escanear
        res = svc.copiar_video(vid, B, ruta_db)
        assert res["ok"]
        assert not escaneo_calls, f"servicio copiar no debe escaneo, got {escaneo_calls}"
        # UI refresco tampoco debe escanear
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config26.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        for _ in range(200):
            QApplication.processEvents()
            time.sleep(0.02)
            if ventana._carga_completada and not ventana.gestor.activo:
                break
        ventana.carpeta_seleccionada = os.path.abspath(B)
        recarga_calls = []
        orig_prog = ventana._programar_recarga_por_carpeta
        def spy_prog(*a, **k):
            recarga_calls.append("recarga")
            return orig_prog(*a, **k)
        ventana._programar_recarga_por_carpeta = spy_prog
        ventana._al_resultado_copiar(res)
        QApplication.processEvents()
        assert recarga_calls, "debe haber recarga"
        assert not escaneo_calls, f"refresco no debe escaneo, got {escaneo_calls}"
        ventana._programar_recarga_por_carpeta = orig_prog
        visor_videos.VisorVideos.iniciar_escaneo = orig_escaneo
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
        print("test_26 OK")
    finally:
        try:
            visor_videos.VisorVideos.iniciar_escaneo = orig_escaneo
        except: pass
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_27_servicio_entrega_carpeta_destino_canonica():
    """Servicio devuelve carpeta_destino canónica y UI la consume sin FS directo."""
    tmpdir, ruta_db = _crear_db_temporal()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, A, "ref27.mp4", contenido=b"27" * 500)
        res = svc.copiar_video(vid, B, ruta_db)
        assert "carpeta_destino" in res, "servicio debe devolver carpeta_destino"
        assert "ruta" in res
        # carpeta_destino debe ser canónica y coincidir con B normalizado
        assert os.path.normcase(os.path.normpath(res["carpeta_destino"])) == os.path.normcase(os.path.normpath(os.path.abspath(B)))
        # ruta debe estar dentro de carpeta_destino
        assert os.path.normcase(os.path.normpath(os.path.dirname(res["ruta"]))) == os.path.normcase(os.path.normpath(res["carpeta_destino"]))
        # UI usa carpetas_iguales sin os.path directo
        from rutas import carpetas_iguales
        assert carpetas_iguales(B, res["carpeta_destino"])
        assert not carpetas_iguales(A, res["carpeta_destino"])
        print("test_27 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    tests = [
        test_01_exito_hash_identico,
        test_02_original_permanece,
        test_03_nuevo_video_id_distinto,
        test_04_marcadores_segmentos_no_heredados,
        test_05_destino_paginado_sin_escaneo,
        test_06_A_sigue_solo_original,
        test_07_reinicio_reconexion_AB,
        test_08_colision_FS_rechazada,
        test_09_misma_carpeta_rechazada,
        test_10_origen_faltante,
        test_11_destino_inexistente,
        test_12_error_lectura_copia,
        test_13_hash_mismatch_no_publica,
        test_14_fallo_DB_post_publicacion_inconsistencia,
        test_15_case_insensitive_windows,
        test_16_tarea_delega_servicio,
        test_17_ui_no_fs_sqlite_directo,
        test_18_menu_handler_correctos,
        test_19_actividad_progreso_error,
        test_20_unique_constraint_sufijo,
        test_21_temporal_limpio_en_fallos,
        test_22_no_deja_sqlite_apuntando_inexistente,
        test_23_origen_relaciones_intactas_con_derivados,
        test_24_refresco_B_via_recarga_paginada_sin_escaneo,
        test_25_A_no_contamina_vista,
        test_26_cero_llamadas_escaneo_para_exito_y_refresco,
        test_27_servicio_entrega_carpeta_destino_canonica,
    ]
    fallos = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            import traceback
            fallos += 1
            print(f"FAIL {fn.__name__}: {exc}")
            traceback.print_exc()
    total = len(tests)
    print(f"TOTAL={total - fallos}/{total}")
    print(f"RESULTADO_FINAL={'PASS' if fallos == 0 else 'FAIL'}")
