"""Suite B8.3A — operaciones con homónimos, contrato por ruta_normalizada exacta.

Casos A-J sobre archivos temporales + DB temporal, sin datos reales.
"""

import os
import shutil
import sqlite3
import tempfile

from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    listar_marcadores,
    listar_segmentos,
    obtener_video_por_id,
    obtener_video_por_ruta_normalizada,
    buscar_colision_ruta_video,
)
from rutas import normalizar_ruta_clave
import renombrar_video as ren_svc
import mover_video as mov_svc
import copiar_video as cop_svc
import lote_operaciones as lote_svc
from renombrar_video import ColisionError as RenColision
from mover_video import ColisionError as MovColision
from copiar_video import ColisionError as CopColision

# Helpers
def _crear_db():
    tmpdir = tempfile.mkdtemp()
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return tmpdir, ruta_db

def _insertar(ruta_db, carpeta, nombre, contenido=b"x"*1024):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    st = os.stat(ruta)
    conn = conectar_bd(ruta_db)
    try:
        # Insertar con ruta_normalizada explícita para compatibilidad
        ruta_abs = os.path.abspath(ruta)
        ruta_norm = normalizar_ruta_clave(ruta_abs)
        conn.execute(
            "INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, tamano_bytes, mtime_ns) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1].lower(), "2026-01-01T00:00:00", st.st_size, st.st_mtime_ns),
        )
        conn.commit()
        vid = conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?", (ruta_norm,)).fetchone()[0]
        return vid, ruta_abs
    finally:
        conn.close()

def test_A_homonimos_coexisten():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
    try:
        vidA, rutaA = _insertar(ruta_db, A, "video.mp4", contenido=b"a"*100)
        vidB, rutaB = _insertar(ruta_db, B, "video.mp4", contenido=b"b"*100)
        assert vidA != vidB, "IDs distintos para homónimos"
        # Verificar que ambos existen en DB por ruta_normalizada
        recA = obtener_video_por_ruta_normalizada(rutaA, ruta_db)
        recB = obtener_video_por_ruta_normalizada(rutaB, ruta_db)
        assert recA is not None and recA["id"] == vidA
        assert recB is not None and recB["id"] == vidB
        assert recA["ruta_normalizada"] != recB["ruta_normalizada"]
        print("A OK — dos video.mp4 en A y B coexisten con IDs distintos")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_B_renombrar_homonimo_permitido_mismo_id():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
    try:
        vidA, _ = _insertar(ruta_db, A, "x.mp4", contenido=b"x")
        vidB, _ = _insertar(ruta_db, B, "video.mp4", contenido=b"y")
        # Existe B/video.mp4, renombrar A/x.mp4 -> A/video.mp4 debe ser permitido (destino A/video.mp4 libre)
        res = ren_svc.renombrar_video(vidA, "video.mp4", ruta_db)
        assert res["ok"] and res["video_id"] == vidA, "debe conservar mismo ID"
        assert res["nombre"] == "video.mp4"
        # Verificar DB
        info = obtener_video_por_id(vidA, ruta_db)
        assert info["nombre"] == "video.mp4"
        assert info["id"] == vidA
        # B sigue intacto
        infoB = obtener_video_por_id(vidB, ruta_db)
        assert infoB["nombre"] == "video.mp4" and infoB["id"] == vidB
        # FS: ambos archivos existen en sus carpetas distintas
        assert os.path.isfile(os.path.join(A, "video.mp4"))
        assert os.path.isfile(os.path.join(B, "video.mp4"))
        print("B OK — renombrar hacia homónimo en otra carpeta permitido, mismo ID")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_C_renombrar_ruta_exacta_ocupada_rechazado():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A")
    os.makedirs(A, exist_ok=True)
    try:
        vid1, ruta1 = _insertar(ruta_db, A, "a.mp4", contenido=b"a")
        vid2, ruta2 = _insertar(ruta_db, A, "b.mp4", contenido=b"b")
        # intentar renombrar a.mp4 -> b.mp4 (destino exacto ocupado en misma carpeta)
        try:
            ren_svc.renombrar_video(vid1, "b.mp4", ruta_db)
            assert False, "debe rechazar colisión exacta"
        except RenColision:
            pass
        # FS y DB intactos
        assert os.path.isfile(ruta1)
        assert os.path.isfile(ruta2)
        info1 = obtener_video_por_id(vid1, ruta_db)
        assert info1["nombre"] == "a.mp4"
        print("C OK — renombrar hacia ruta exacta ocupada rechazado, FS+DB intactos")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_D_mover_homonimo_permitido_conserva_id():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B"); C = os.path.join(tmpdir, "C")
    for d in [A,B,C]: os.makedirs(d, exist_ok=True)
    try:
        vidA, _ = _insertar(ruta_db, A, "video.mp4", contenido=b"a")
        vidB, _ = _insertar(ruta_db, B, "video.mp4", contenido=b"b")
        rutaA_orig = os.path.join(A, "video.mp4")
        res = mov_svc.mover_video(vidA, C, ruta_db)
        assert res["ok"] and res["video_id"] == vidA
        assert res["ruta"] == os.path.abspath(os.path.join(C, "video.mp4"))
        # B sigue con mismo nombre
        infoB = obtener_video_por_id(vidB, ruta_db)
        assert infoB["nombre"] == "video.mp4"
        assert os.path.isfile(os.path.join(C, "video.mp4"))
        assert os.path.isfile(os.path.join(B, "video.mp4"))
        print("D OK — mover homónimo a C permitido, conserva ID, homónimo B intacto")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_E_mover_ruta_exacta_ocupada_rechazado():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); C = os.path.join(tmpdir, "C")
    os.makedirs(A, exist_ok=True); os.makedirs(C, exist_ok=True)
    try:
        vidA, rutaA = _insertar(ruta_db, A, "video.mp4", contenido=b"a")
        vidC, rutaC = _insertar(ruta_db, C, "video.mp4", contenido=b"c")
        # intentar mover A/video.mp4 -> C/video.mp4 donde ya existe otro archivo catalogado y FS
        try:
            mov_svc.mover_video(vidA, C, ruta_db)
            assert False, "debe rechazar colisión exacta"
        except MovColision:
            pass
        assert os.path.isfile(rutaA)
        assert os.path.isfile(rutaC)
        infoA = obtener_video_por_id(vidA, ruta_db)
        assert infoA["ruta"] == rutaA
        print("E OK — mover hacia ruta exacta ocupada rechazado sin overwrite")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_F_copiar_homonimo_nuevo_id():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B"); C = os.path.join(tmpdir, "C"); D = os.path.join(tmpdir, "D")
    for d in [A,B,C,D]: os.makedirs(d, exist_ok=True)
    try:
        vidA, _ = _insertar(ruta_db, A, "video.mp4", contenido=b"a")
        vidB, rutaB = _insertar(ruta_db, B, "video.mp4", contenido=b"bcopy")
        vidC, _ = _insertar(ruta_db, C, "video.mp4", contenido=b"c")
        res = cop_svc.copiar_video(vidB, D, ruta_db)
        assert res["ok"]
        nuevo = res["video_id"]
        assert nuevo != vidB and nuevo != vidA and nuevo != vidC
        assert res["nombre"] == "video.mp4"
        assert os.path.isfile(os.path.join(D, "video.mp4"))
        # Verificar hash idéntico a origen
        with open(rutaB, "rb") as f: h_orig = f.read()
        with open(res["ruta"], "rb") as f: h_copy = f.read()
        assert h_orig == h_copy
        print("F OK — copiar homónimo a D con nuevo ID distinto de A/B/C")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_G_copiar_ruta_exacta_ocupada_rechazado():
    tmpdir, ruta_db = _crear_db()
    B = os.path.join(tmpdir, "B"); D = os.path.join(tmpdir, "D")
    os.makedirs(B, exist_ok=True); os.makedirs(D, exist_ok=True)
    try:
        vidB, _ = _insertar(ruta_db, B, "video.mp4", contenido=b"b")
        vidD, rutaD = _insertar(ruta_db, D, "video.mp4", contenido=b"d")
        try:
            cop_svc.copiar_video(vidB, D, ruta_db)
            assert False, "debe rechazar copia a ruta exacta ocupada"
        except CopColision:
            pass
        # también rechaza si FS existe aunque no catalogado? crear archivo FS suelto
        os.remove(rutaD)
        conn = conectar_bd(ruta_db)
        conn.execute("DELETE FROM videos WHERE id=?", (vidD,))
        conn.commit(); conn.close()
        # ahora DB no tiene D/video.mp4 pero FS sí existe (creamos de nuevo)
        with open(os.path.join(D, "video.mp4"), "wb") as f:
            f.write(b"existFS")
        try:
            cop_svc.copiar_video(vidB, D, ruta_db)
            assert False, "debe rechazar por FS existente"
        except CopColision:
            pass
        assert os.path.isfile(os.path.join(D, "video.mp4"))
        print("G OK — copiar a ruta exacta ya existente/catalogada rechazado sin overwrite/reutilización ID")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_H_marcador_segmento_conservados_tras_rename_move():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); C = os.path.join(tmpdir, "C")
    os.makedirs(A, exist_ok=True); os.makedirs(C, exist_ok=True)
    try:
        vid, _ = _insertar(ruta_db, A, "orig.mp4", contenido=b"orig")
        mid = guardar_marcador(vid, 2.5, ruta_db)
        sid, _, _ = guardar_segmento(vid, 1.0, 3.0, ruta_db)
        # renombrar
        ren_svc.renombrar_video(vid, "renamed.mp4", ruta_db)
        marc = listar_marcadores(vid, ruta_db)
        seg = listar_segmentos(vid, ruta_db)
        assert len(marc)==1 and marc[0][0]==mid
        assert len(seg)==1 and seg[0][0]==sid
        # mover
        mov_svc.mover_video(vid, C, ruta_db)
        marc2 = listar_marcadores(vid, ruta_db)
        seg2 = listar_segmentos(vid, ruta_db)
        assert len(marc2)==1 and marc2[0][0]==mid
        assert len(seg2)==1 and seg2[0][0]==sid
        print("H OK — marcador/segmento siguen asociados al mismo video_id tras rename/move")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_I_cache_canonica_no_renombrada():
    # Comprobar que operaciones no tocan caché por v<id>
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); C = os.path.join(tmpdir, "C")
    mini = os.path.join(tmpdir, "mini")
    os.makedirs(A, exist_ok=True); os.makedirs(C, exist_ok=True); os.makedirs(mini, exist_ok=True)
    import rutas, escanear_videos as esc
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini
    esc.ruta_carpeta_miniaturas = lambda: mini
    try:
        vid, _ = _insertar(ruta_db, A, "cache.mp4", contenido=b"cache")
        # crear caché canónica v<id>_01.jpg
        cache_path = esc.ruta_miniatura_id(vid, 1)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(b"fakejpg")
        mtime_before = os.path.getmtime(cache_path)
        # renombrar y mover
        ren_svc.renombrar_video(vid, "cache2.mp4", ruta_db)
        mov_svc.mover_video(vid, C, ruta_db)
        # cache debe seguir en misma ruta v<id>_01.jpg sin renombrar ni reasignar
        assert os.path.isfile(cache_path), "cache canónica no debe moverse"
        assert os.path.getmtime(cache_path) == mtime_before, "cache no debe reescribirse"
        # No debe existir cache para otro id
        assert not os.path.isfile(esc.ruta_miniatura_id(vid+999, 1))
        # Verificar helpers: ruta_miniatura_id sigue determinística
        assert esc.ruta_miniatura_id(vid, 1) == cache_path
        print("I OK — cache canónica por v<id> no se renombra ni reasigna tras rename/move")
    finally:
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_J_lote_homonimos_y_duplicado_intralote():
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B"); C = os.path.join(tmpdir, "C"); D = os.path.join(tmpdir, "D")
    for d in [A,B,C,D]: os.makedirs(d, exist_ok=True)
    try:
        vid1, _ = _insertar(ruta_db, A, "same.mp4", contenido=b"1")
        vid2, _ = _insertar(ruta_db, B, "same.mp4", contenido=b"2")
        vid3, _ = _insertar(ruta_db, C, "unique.mp4", contenido=b"3")
        # Lote mover dos homónimos same.mp4 a D: primero ok, segundo debe ser duplicado intra-lote o colisión FS
        res = lote_svc.lote_operaciones("mover", [vid1, vid2], ruta_db, carpeta_destino=D)
        assert res["exitosos_count"] == 1, f"un exitoso esperado, got {res}"
        assert res["fallidos_count"] == 1
        # El fallido debe ser por colisión duplicada
        assert "duplicado" in res["fallidos"][0]["error"].lower() or "colisión" in res["fallidos"][0]["error"].lower() or "ya existe" in res["fallidos"][0]["error"].lower()
        # Lote copiar mismo vid dos veces a mismo destino -> segundo duplicado intra-lote
        E = os.path.join(tmpdir, "E")
        os.makedirs(E, exist_ok=True)
        vidC, _ = _insertar(ruta_db, C, "dup.mp4", contenido=b"dup")
        # limpiar D para prueba copiar
        for f in os.listdir(D):
            os.remove(os.path.join(D, f))
        # eliminar registro previo de vid1 en D para no interferir
        conn = sqlite3.connect(ruta_db)
        # mover ya dejó vid1 en D, lo dejamos; copiar dup a E dos veces
        conn.close()
        res2 = lote_svc.lote_operaciones("copiar", [vidC, vidC], ruta_db, carpeta_destino=E)
        assert res2["exitosos_count"] == 1 and res2["fallidos_count"] == 1, f"copiar duplicado intra-lote debe dar 1 ok 1 fallo, got {res2}"
        # Dos ítems con mismo nombre final pero carpetas destino distintas -> válidos (probamos secuencialmente con dos lotes distintos)
        F = os.path.join(tmpdir, "F")
        G = os.path.join(tmpdir, "G")
        os.makedirs(F, exist_ok=True); os.makedirs(G, exist_ok=True)
        vid4, _ = _insertar(ruta_db, A, "another.mp4", contenido=b"4")
        # Copiar same nombre a F y a G vía lotes separados -> ambos deben ser ok con mismo basename
        resF = cop_svc.copiar_video(vid4, F, ruta_db)
        resG = cop_svc.copiar_video(vid4, G, ruta_db)
        assert resF["nombre"] == "another.mp4" and resG["nombre"] == "another.mp4"
        assert resF["video_id"] != resG["video_id"]
        assert os.path.isfile(os.path.join(F, "another.mp4"))
        assert os.path.isfile(os.path.join(G, "another.mp4"))
        print("J OK — lote: homónimos destinos distintos permitidos; destino físico duplicado intra-lote detectado")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_K_copy_homonimo_cache_por_id_distinta():
    """B8.3A — copy homónimo: nuevo ID, rutas canónicas v<id>_01.jpg distintas, no roba cache origen, rename/move conservan v<id>"""
    tmpdir, ruta_db = _crear_db()
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B"); C = os.path.join(tmpdir, "C")
    for d in [A,B,C]: os.makedirs(d, exist_ok=True)
    mini = os.path.join(tmpdir, "mini")
    os.makedirs(mini, exist_ok=True)
    import rutas, escanear_videos as esc
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini
    esc.ruta_carpeta_miniaturas = lambda: mini
    try:
        vid_orig, ruta_orig = _insertar(ruta_db, A, "video.mp4", contenido=b"orig")
        # cache canónica origen v<id>_01.jpg y previews
        src_mini = esc.ruta_miniatura_id(vid_orig, 1)
        with open(src_mini, "wb") as f: f.write(b"fakejpg_orig")
        for i in [1,2]:
            p = esc.ruta_preview_id(vid_orig, i)
            with open(p, "wb") as f: f.write(b"preview_orig")
        mtime_orig = os.path.getmtime(src_mini)
        # copiar homónimo a B (mismo nombre visible, carpeta distinta)
        res = cop_svc.copiar_video(vid_orig, B, ruta_db)
        assert res["ok"] and res["nombre"] == "video.mp4"
        vid_copy = res["video_id"]
        assert vid_copy != vid_orig, "copy homónimo debe obtener nuevo ID distinto"
        # rutas canónicas deben diferir
        ruta_mini_orig = esc.ruta_miniatura_id(vid_orig, 1)
        ruta_mini_copy = esc.ruta_miniatura_id(vid_copy, 1)
        assert ruta_mini_orig != ruta_mini_copy, f"cache homónimo debe ser distinta por ID: {ruta_mini_orig} vs {ruta_mini_copy}"
        assert ruta_mini_orig.endswith(f"v{vid_orig}_01.jpg") and ruta_mini_copy.endswith(f"v{vid_copy}_01.jpg")
        assert os.path.isfile(ruta_mini_orig) and os.path.isfile(ruta_mini_copy)
        # contenido idéntico inicial pero archivos distintos
        assert open(ruta_mini_orig,"rb").read() == open(ruta_mini_copy,"rb").read()
        # previews también distintas
        for i in [1,2]:
            po = esc.ruta_preview_id(vid_orig, i)
            pc = esc.ruta_preview_id(vid_copy, i)
            assert po != pc and po.endswith(f"v{vid_orig}_preview_{i:02d}.jpg") and pc.endswith(f"v{vid_copy}_preview_{i:02d}.jpg")
            assert os.path.isfile(po) and os.path.isfile(pc)
            assert open(po,"rb").read() == open(pc,"rb").read()
        # rename del origen conserva su cache v<id>
        import renombrar_video as ren
        ren.renombrar_video(vid_orig, "renamed.mp4", ruta_db)
        assert os.path.isfile(ruta_mini_orig) and os.path.getmtime(ruta_mini_orig) == mtime_orig
        assert esc.ruta_miniatura_id(vid_orig, 1) == ruta_mini_orig
        # move del origen conserva cache
        import mover_video as mov
        mov.mover_video(vid_orig, C, ruta_db)
        assert os.path.isfile(ruta_mini_orig)
        assert esc.ruta_miniatura_id(vid_orig, 1) == ruta_mini_orig
        # copy no roba: eliminar cache copia no afecta origen
        os.remove(ruta_mini_copy)
        assert not os.path.isfile(ruta_mini_copy)
        assert os.path.isfile(ruta_mini_orig)
        # modificar copia no altera origen (recrear copia y modificar)
        with open(ruta_mini_copy, "wb") as f: f.write(b"copy_mod")
        assert open(ruta_mini_orig,"rb").read() == b"fakejpg_orig"
        assert open(ruta_mini_copy,"rb").read() != open(ruta_mini_orig,"rb").read()
        print("K OK — copy homónimo cache por ID distinta, rename/move conservan v<id>, no roba")
    finally:
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_L_config_vs_cache_real_todos_previews():
    """B8.3A — CONFIG != CACHE: replicar copia TODOS los previews reales aunque CANTIDAD_PREVIEWS sea 1.
    Aislamiento: previews_existentes_por_id respeta CANTIDAD (B8.2), solo _previews_canonicos_reales_por_id enumerara todos.
    """
    import escanear_videos as esc
    import rutas
    tmpdir = tempfile.mkdtemp()
    mini = os.path.join(tmpdir, "mini")
    os.makedirs(mini, exist_ok=True)
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini
    esc.ruta_carpeta_miniaturas = lambda: mini
    orig_cantidad = esc.CANTIDAD_PREVIEWS
    try:
        vid_orig = 501
        vid_dest = 502
        vid_otro = 999
        src_mini = esc.ruta_miniatura_id(vid_orig, 1)
        with open(src_mini, "wb") as f:
            f.write(b"mini_orig")
        for idx in [1, 2, 5]:
            p = esc.ruta_preview_id(vid_orig, idx)
            with open(p, "wb") as f:
                f.write(f"preview_{idx}".encode())
        otro_preview = esc.ruta_preview_id(vid_otro, 5)
        with open(otro_preview, "wb") as f:
            f.write(b"otro")
        legacy_name = "videoX_preview_05.jpg"
        legacy_path = os.path.join(mini, legacy_name)
        with open(legacy_path, "wb") as f:
            f.write(b"legacy")
        # Aislamiento: public helper respeta CANTIDAD (B8.2), privado enumera todos
        # con CANTIDAD default 3, public debe ver solo 01,02 (no 05)
        public_default = esc.previews_existentes_por_id(vid_orig)
        assert len(public_default) == 2, f"public con CANTIDAD=3 debe ver solo 01,02 got {public_default}"
        assert not any("05" in p for p in public_default), f"public no debe incluir 05 {public_default}"
        # privado debe ver 3
        assert hasattr(esc, "_previews_canonicos_reales_por_id"), "_previews_canonicos_reales_por_id debe existir"
        privados = esc._previews_canonicos_reales_por_id(vid_orig)
        assert len(privados) == 3, f"privado debe enumerar 01,02,05 got {privados}"
        assert any(f"v{vid_orig}_preview_05.jpg" in p for p in privados)
        # monkeypatch config a 1: public solo 01, privado sigue 3, replicar debe copiar 3
        esc.CANTIDAD_PREVIEWS = 1
        public_1 = esc.previews_existentes_por_id(vid_orig)
        assert len(public_1) == 1 and any("01" in p for p in public_1), f"public con CANTIDAD=1 debe ver solo 01 got {public_1}"
        privados_1 = esc._previews_canonicos_reales_por_id(vid_orig)
        assert len(privados_1) == 3, f"privado con CANTIDAD=1 debe seguir viendo 3 got {privados_1}"
        res = esc.replicar_cache_por_id(vid_orig, vid_dest)
        esc.CANTIDAD_PREVIEWS = orig_cantidad
        assert res.get("copiados", 0) >= 4, f"debe copiar mini+3 previews, res={res}"
        assert res.get("preview_copiadas", 0) == 3, f"preview_copiadas debe ser 3, res={res}"
        assert res.get("mini_copiadas", 0) == 1
        for idx in [1, 2, 5]:
            dst = esc.ruta_preview_id(vid_dest, idx)
            src = esc.ruta_preview_id(vid_orig, idx)
            assert os.path.isfile(dst), f"dest preview {idx} debe existir {dst}"
            assert open(src, "rb").read() == open(dst, "rb").read()
        assert os.path.isfile(otro_preview)
        assert os.path.isfile(legacy_path)
        # public dest con config restaurado=3 debe ver solo 01,02
        public_dest = esc.previews_existentes_por_id(vid_dest)
        assert len(public_dest) == 2 and not any("05" in p for p in public_dest), f"public dest con CANTIDAD=3 debe ver 2 got {public_dest}"
        # privado dest debe ver 3
        priv_dest = esc._previews_canonicos_reales_por_id(vid_dest)
        assert len(priv_dest) == 3 and any("05" in p for p in priv_dest), f"privado dest debe tener 05 {priv_dest}"
        print("L OK — aislamiento: public respeta CANTIDAD (1=>01 solo), privado/replica copiaron 01,02,05")
    finally:
        esc.CANTIDAD_PREVIEWS = orig_cantidad
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_M_ausencia_fallback_legacy():
    """B8.3A — ausencia de fallback por nombre en flujo productivo copiar_video.

    Verifica estructuralmente que copiar_video.py tiene cero llamadas a _replicar_cache_miniaturas
    fuera de su propia definición, usa helper por ID y retorno incluye cache_replica determinista.
    """
    import pathlib, tempfile, shutil, os
    code = open("copiar_video.py", encoding="utf-8").read()
    # contar llamadas: buscar `_replicar_cache_miniaturas(` sin `def `
    import re
    # encontrar todas las apariciones
    calls = [m.start() for m in re.finditer(r"_replicar_cache_miniaturas\s*\(", code)]
    # determinar cuál es la definición: línea con `def _replicar_cache_miniaturas`
    def_pos = code.find("def _replicar_cache_miniaturas")
    # filtrar llamadas que no son la definición (def ya tiene `def ` antes, pero nuestro regex no incluye def )
    # Si code tiene `def _replicar...(` también cuenta, así que excluir si está precedido por `def `
    real_calls = 0
    for pos in calls:
        snippet = code[max(0, pos-30):pos]
        if "def " in snippet[-30:]:
            # es la definicion
            continue
        real_calls += 1
    assert real_calls == 0, f"copiar_video.py debe tener CERO llamadas productivas a _replicar_cache_miniaturas, found {real_calls}"
    # verificar que usa helper por ID
    assert "replicar_cache_por_id" in code or "copiar_cache_entre_ids" in code, "copiar_video debe referenciar helper por ID"
    assert "cache_replica" in code, "copiar_video debe incluir campo cache_replica determinista"
    # verificación dinámica: copiar homónimo incluye detalle
    import rutas, escanear_videos as esc
    tmpdir = tempfile.mkdtemp()
    mini = os.path.join(tmpdir, "mini")
    os.makedirs(mini, exist_ok=True)
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini
    esc.ruta_carpeta_miniaturas = lambda: mini
    tmpdir_db, ruta_db = _crear_db()
    # Crear dirs A y B para copia
    A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
    try:
        vid_orig, _ = _insertar(ruta_db, A, "check.mp4", contenido=b"chk")
        # miniatura origen
        with open(esc.ruta_miniatura_id(vid_orig, 1), "wb") as f:
            f.write(b"mini")
        res = cop_svc.copiar_video(vid_orig, B, ruta_db)
        assert res.get("ok") is True
        assert "cache_replica" in res, f"resultado copiar debe incluir cache_replica, got keys {res.keys()}"
        assert isinstance(res["cache_replica"], dict), "cache_replica debe ser dict"
        # nunca debe haber usado flujo por nombre -> cache_replica no debe contener legacy fallback
        # fallback legacy habría sido por nombre, pero ahora helper por ID produce detalle con copiados/ya_exist...
        print(f"M OK — cero llamadas fallback por nombre, helper por ID usado, cache_replica={res['cache_replica']}")
    finally:
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(tmpdir_db, ignore_errors=True)

def test_N_fallo_enumeracion_determinista():
    """B8.3A N — si os.listdir falla, replicar reporta fallo determinista y copiar preserva archivo+DB."""
    import escanear_videos as esc
    import rutas
    tmpdir = tempfile.mkdtemp()
    mini = os.path.join(tmpdir, "mini")
    os.makedirs(mini, exist_ok=True)
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini
    esc.ruta_carpeta_miniaturas = lambda: mini
    # guardar listdir original
    orig_listdir = esc.os.listdir
    orig_listdir_global = os.listdir
    tmpdir_db = None
    try:
        vid_orig = 701
        vid_dest = 702
        src_mini = esc.ruta_miniatura_id(vid_orig, 1)
        with open(src_mini, "wb") as f:
            f.write(b"mini_n")
        for idx in [1, 2]:
            p = esc.ruta_preview_id(vid_orig, idx)
            with open(p, "wb") as f:
                f.write(b"prev")
        # monkeypatch os.listdir solo para cache: lanzar OSError cuando carpeta==mini
        def patched_listdir(path):
            if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(mini)):
                raise OSError("simulated listado fallo")
            return orig_listdir(path)
        esc.os.listdir = patched_listdir
        # replicar directo debe reportar fallo
        res = esc.replicar_cache_por_id(vid_orig, vid_dest)
        assert res.get("fallos", 0) >= 1, f"replicar debe reportar fallos>=1 con listdir error, got {res}"
        detalle_str = " ".join(str(d.get("estado","")) for d in res.get("detalles", []))
        assert "fallo_enumeracion_previews" in detalle_str, f"detalle debe contener fallo_enumeracion_previews, got {res}"
        # aunque falló enumeración, si mini existía y no había error de copia, puede haber copiado mini pero fallo persiste
        # verificar que no se destruyó origen
        assert os.path.isfile(src_mini), "origen mini no debe destruirse"
        # restaurar para prueba via copiar_video
        esc.os.listdir = orig_listdir
        # limpiar dest si se creó parcialmente
        for idx in [1, 2]:
            dst = esc.ruta_preview_id(vid_dest, idx)
            if os.path.isfile(dst):
                os.remove(dst)
        dst_mini = esc.ruta_miniatura_id(vid_dest, 1)
        if os.path.isfile(dst_mini):
            os.remove(dst_mini)
        # ahora probar vía copiar_video con fallo enumeración
        tmpdir_db, ruta_db = _crear_db()
        A = os.path.join(tmpdir, "A"); B = os.path.join(tmpdir, "B")
        os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
        # insertar origen DB con archivo real
        vid_db, ruta_orig = _insertar(ruta_db, A, "n_fail.mp4", contenido=b"failcontent")
        # crear cache canónica para ese vid_db
        cache_mini = esc.ruta_miniatura_id(vid_db, 1)
        with open(cache_mini, "wb") as f:
            f.write(b"mini_db")
        # patch de nuevo para copy
        esc.os.listdir = patched_listdir
        # también parchear os.listdir global usado por copiar? replicar usa esc.os.listdir ya parcheado
        os.listdir = patched_listdir
        res_copy = cop_svc.copiar_video(vid_db, B, ruta_db)
        # restaurar inmediatamente
        esc.os.listdir = orig_listdir
        os.listdir = orig_listdir_global
        assert res_copy.get("ok") is True, f"copiar debe ok aunque cache falle, got {res_copy}"
        assert res_copy.get("cache_fallos", 0) >= 1, f"cache_fallos debe >=1, got {res_copy}"
        cr = res_copy.get("cache_replica", {})
        detalle_c = " ".join(str(d.get("estado","")) for d in cr.get("detalles", [])) if isinstance(cr, dict) else ""
        assert "fallo_enumeracion_previews" in detalle_c, f"cache_replica detalle debe contener fallo_enumeracion, got {cr}"
        # archivo copiado debe existir y DB debe tener registro
        assert os.path.isfile(res_copy["ruta"]), "archivo copiado debe existir pese a fallo cache"
        info = esc.obtener_video_por_ruta_normalizada(res_copy["ruta"], ruta_db)
        assert info is not None and info["id"] == res_copy["video_id"], "DB debe contener nuevo video pese a fallo"
        # origen intacto
        assert os.path.isfile(ruta_orig), "origen intacto"
        print(f"N OK — listdir OSError reportado fallos={res.get('fallos')} y copiar cache_fallos={res_copy.get('cache_fallos')}")
    finally:
        esc.os.listdir = orig_listdir
        try:
            os.listdir = orig_listdir_global
        except: pass
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        shutil.rmtree(tmpdir, ignore_errors=True)
        if tmpdir_db:
            shutil.rmtree(tmpdir_db, ignore_errors=True)

if __name__ == "__main__":
    test_A_homonimos_coexisten()
    test_B_renombrar_homonimo_permitido_mismo_id()
    test_C_renombrar_ruta_exacta_ocupada_rechazado()
    test_D_mover_homonimo_permitido_conserva_id()
    test_E_mover_ruta_exacta_ocupada_rechazado()
    test_F_copiar_homonimo_nuevo_id()
    test_G_copiar_ruta_exacta_ocupada_rechazado()
    test_H_marcador_segmento_conservados_tras_rename_move()
    test_I_cache_canonica_no_renombrada()
    test_J_lote_homonimos_y_duplicado_intralote()
    test_K_copy_homonimo_cache_por_id_distinta()
    test_L_config_vs_cache_real_todos_previews()
    test_M_ausencia_fallback_legacy()
    test_N_fallo_enumeracion_determinista()
    print("TODOS B8.3 OK")
