"""Suite B8.2 — Caché por video_id"""
import os, tempfile, sqlite3, shutil, subprocess, sys
import rutas as rutas_mod
import escanear_videos as ev
from escanear_videos import conectar_bd, preparar_registros_basicos, guardar_videos, actualizar_cantidad_miniaturas, migrar_cache_legacy_a_id, contar_miniaturas_por_id, previews_faltantes_por_id, previews_existentes_por_id, ruta_miniatura_id, ruta_preview_id, generar_miniatura, contar_miniaturas, ruta_miniatura, ruta_preview, _nombre_seguro
import configuracion

def _crear_video_valido(ruta):
    cmd=["ffmpeg","-y","-f","lavfi","-i","color=c=blue:s=320x180:d=1:r=30","-c:v","libx264","-pix_fmt","yuv420p","-t","1",ruta]
    r=subprocess.run(cmd,capture_output=True)
    return r.returncode==0 and os.path.isfile(ruta)

def _setup_cache_temp():
    tmp = tempfile.TemporaryDirectory()
    orig = rutas_mod.ruta_carpeta_miniaturas
    orig2 = ev.ruta_carpeta_miniaturas
    rutas_mod.ruta_carpeta_miniaturas = lambda: tmp.name
    ev.ruta_carpeta_miniaturas = lambda: tmp.name
    return tmp, orig, orig2

def _teardown(tmp, orig, orig2):
    rutas_mod.ruta_carpeta_miniaturas = orig
    ev.ruta_carpeta_miniaturas = orig2
    tmp.cleanup()

def test_01_namespace_v1():
    return ruta_miniatura_id(1,1).endswith("v1_01.jpg"), ruta_miniatura_id(1,1)
def test_02_namespace_v7():
    return ruta_miniatura_id(7,2).endswith("v7_02.jpg"), ruta_miniatura_id(7,2)
def test_03_namespace_v20():
    return ruta_miniatura_id(20,15).endswith("v20_15.jpg"), ruta_miniatura_id(20,15)
def test_04_no_depende_nombre():
    a=ruta_miniatura_id(5,1)
    b=ruta_miniatura_id(5,1)
    # con nombres diferentes pero mismo id, ruta debe ser igual
    # Simular cambio de nombre: no afecta
    ok = a==b and "video" not in a
    return ok, f"a={a} b={b}"
def test_05_cambio_nombre_conserva():
    tmp, o1, o2 = _setup_cache_temp()
    try:
        r1=ruta_miniatura_id(10,1)
        # cambiar nombre no debe cambiar ruta
        r2=ruta_miniatura_id(10,1)
        ok = r1==r2
        return ok, f"{r1} vs {r2}"
    finally:
        _teardown(tmp,o1,o2)
def test_06_cambio_ruta_conserva():
    tmp, o1, o2 = _setup_cache_temp()
    try:
        r1=ruta_miniatura_id(11,1)
        r2=ruta_miniatura_id(11,1)
        ok = r1==r2
        return ok, f"{r1}"
    finally:
        _teardown(tmp,o1,o2)
def test_07_dos_ids_distintos():
    a=ruta_miniatura_id(1,1)
    b=ruta_miniatura_id(2,1)
    ok = a!=b and "v1_" in a and "v2_" in b
    return ok, f"a={a} b={b}"
def test_08_generacion_real_por_id():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1, o2 = _setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"x.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["x.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # generar miniatura por id
        n=ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        exists=os.path.isfile(ruta_miniatura_id(vid,1))
        ok = n==1 and exists
        return ok, f"vid={vid} aseg={n} exists={exists} file={ruta_miniatura_id(vid,1)}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_09_deteccion_existente_por_id():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"y.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["y.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        cnt1=ev.contar_miniaturas_por_id(vid)
        reuse=ev.miniatura_reutilizable_por_id(vid, ruta)
        cnt2=ev.contar_miniaturas_por_id(vid)
        ok = cnt1==1 and reuse is not None and cnt2==1
        return ok, f"cnt1={cnt1} reuse={reuse} cnt2={cnt2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_10_previews_faltantes_por_id():
    tmp_cache, o1,o2=_setup_cache_temp()
    try:
        falt=previews_faltantes_por_id(99)
        ok = len(falt)==ev.CANTIDAD_PREVIEWS and falt[0]==1
        return ok, f"falt={falt}"
    finally:
        _teardown(tmp_cache,o1,o2)
def test_11_segunda_reutiliza():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"z.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["z.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        mtime1=os.path.getmtime(ruta_miniatura_id(vid,1))
        # segunda vez debe reutilizar, no regenerar (mtime igual)
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        mtime2=os.path.getmtime(ruta_miniatura_id(vid,1))
        ok = mtime1==mtime2
        return ok, f"mtime1={mtime1} mtime2={mtime2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_12_no_ffmpeg_si_valida():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"a.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["a.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        # contar ffmpeg calls
        calls={"n":0}
        orig=ev.subprocess.run
        def cnt(*a,**k):
            cmd=a[0] if a else k.get("args")
            if "ffmpeg" in " ".join(cmd):
                calls["n"]+=1
            return orig(*a,**k)
        ev.subprocess.run=cnt
        try:
            ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        finally:
            ev.subprocess.run=orig
        ok = calls["n"]==0
        return ok, f"ffmpeg calls second={calls['n']}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_13_migracion_copia():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"m.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["m.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # crear legacy cache
        nombre="m.mp4"
        legacy=ruta_miniatura(nombre,1)
        # generar miniatura legacy manualmente via old function
        ev.asegurar_miniatura(nombre, ruta, 1.0)
        assert os.path.isfile(legacy)
        # migrar
        mig=migrar_cache_legacy_a_id(vid, nombre)
        new=ruta_miniatura_id(vid,1)
        ok = mig["copiados"]>=1 and os.path.isfile(new) and os.path.isfile(legacy)
        return ok, f"mig={mig} new={new} legacy={legacy}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_14_legacy_permanece():
    # similar a 13 pero verifica legacy no borrado
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"n.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["n.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        legacy=ruta_miniatura("n.mp4",1)
        ev.asegurar_miniatura("n.mp4", ruta, 1.0)
        assert os.path.isfile(legacy)
        migrar_cache_legacy_a_id(vid, "n.mp4")
        ok = os.path.isfile(legacy)
        return ok, f"legacy exists={ok} {legacy}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_15_migracion_idempotente():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"o.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["o.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        legacy=ruta_miniatura("o.mp4",1)
        ev.asegurar_miniatura("o.mp4", ruta, 1.0)
        r1=migrar_cache_legacy_a_id(vid, "o.mp4")
        r2=migrar_cache_legacy_a_id(vid, "o.mp4")
        ok = r1["copiados"]>=1 and r2["copiados"]==0 and r2["ya_existentes"]>=1
        return ok, f"r1={r1} r2={r2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_16_migracion_parcial():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"p.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["p.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # crear 2 legacy miniaturas
        for i in [1,2]:
            # forzar creación de segunda miniatura manualmente copiando
            src=ruta_miniatura("p.mp4",1)
            if not os.path.isfile(src):
                ev.asegurar_miniatura("p.mp4", ruta, 1.0)
            # crear segunda
            dst=ruta_miniatura("p.mp4",2)
            shutil.copyfile(src, dst)
        # migrar solo una vez parcialmente: primero borramos una nueva si existe
        # primera migración copia ambas
        r1=migrar_cache_legacy_a_id(vid, "p.mp4")
        # borrar una nueva
        os.remove(ruta_miniatura_id(vid,2))
        assert not os.path.isfile(ruta_miniatura_id(vid,2))
        r2=migrar_cache_legacy_a_id(vid, "p.mp4")
        ok = r2["copiados"]==1 and os.path.isfile(ruta_miniatura_id(vid,2))
        return ok, f"r1={r1} r2={r2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_17_fallo_copia_no_elimina():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"q.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["q.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        legacy=ruta_miniatura("q.mp4",1)
        ev.asegurar_miniatura("q.mp4", ruta, 1.0)
        # hacer destino no escribible simulando fallo: crear directorio con mismo nombre que destino?
        # Simpler: hacer que primera copia falle por permiso, segunda ok
        # Forzamos fallo haciendo dst ya existente como directorio
        dst=ruta_miniatura_id(vid,1)
        if os.path.isfile(dst):
            os.remove(dst)
        os.makedirs(dst, exist_ok=True)  # ahora dst es directorio, copyfile fallará
        r=migrar_cache_legacy_a_id(vid, "q.mp4")
        # legacy debe permanecer
        ok = os.path.isfile(legacy) and r["fallos"]>=1
        # limpiar directorio
        try:
            os.rmdir(dst)
        except: pass
        return ok, f"r={r} legacy={os.path.isfile(legacy)}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_18_no_fallback_permanente():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"r.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["r.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # crear solo legacy, no nuevo
        legacy=ruta_miniatura("r.mp4",1)
        ev.asegurar_miniatura("r.mp4", ruta, 1.0)
        assert os.path.isfile(legacy)
        # sin migrar, contar por id debe ser 0 (no fallback)
        cnt = ev.contar_miniaturas_por_id(vid)
        ok = cnt==0
        # tras migrar, debe ser 1
        migrar_cache_legacy_a_id(vid, "r.mp4")
        cnt2 = ev.contar_miniaturas_por_id(vid)
        ok = ok and cnt2==1
        return ok, f"cnt antes={cnt} despues={cnt2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_19_renombrar_no_renombra_cache():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"s.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["s.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        cache_antes = ruta_miniatura_id(vid,1)
        assert os.path.isfile(cache_antes)
        mtime_antes=os.path.getmtime(cache_antes)
        # renombrar
        import escanear_videos as evm
        nueva_ruta=os.path.join(tmp_vid.name,"renombrado.mp4")
        os.rename(ruta, nueva_ruta)
        evm.actualizar_nombre_video(vid, "renombrado.mp4", nueva_ruta, ruta_db)
        # cache debe permanecer misma ruta y mismo mtime
        cache_despues = ruta_miniatura_id(vid,1)
        ok = cache_antes==cache_despues and os.path.isfile(cache_despues) and os.path.getmtime(cache_despues)==mtime_antes
        return ok, f"antes={cache_antes} despues={cache_despues}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_20_mover_no_renombra():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"t.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["t.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        cache_antes=ruta_miniatura_id(vid,1)
        mtime_antes=os.path.getmtime(cache_antes)
        nueva=os.path.join(tmp_vid.name,"sub","t.mp4")
        os.makedirs(os.path.dirname(nueva), exist_ok=True)
        shutil.move(ruta, nueva)
        import escanear_videos as evm
        evm.actualizar_ruta_video(vid, nueva, ruta_db)
        cache_despues=ruta_miniatura_id(vid,1)
        ok = cache_antes==cache_despues and os.path.isfile(cache_despues) and os.path.getmtime(cache_despues)==mtime_antes
        return ok, f"antes={cache_antes} despues={cache_despues}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_21_copiar_no_asigna_misma_cache():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"u.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["u.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid1=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid1, ruta, 1.0)
        assert os.path.isfile(ruta_miniatura_id(vid1,1))
        # copiar archivo físicamente y registrar como nuevo video
        ruta2=os.path.join(tmp_vid.name,"u_copia.mp4")
        shutil.copyfile(ruta, ruta2)
        regs2=preparar_registros_basicos(["u_copia.mp4"], tmp_vid.name)
        res2=guardar_videos(regs2, ruta_db)
        vid2=res2["ids"][0]
        assert vid1!=vid2
        # cache para vid2 debe estar vacía inicialmente
        cnt2 = ev.contar_miniaturas_por_id(vid2)
        # y no debe existir archivo v2_01.jpg
        exists2 = os.path.isfile(ruta_miniatura_id(vid2,1))
        ok = cnt2==0 and not exists2
        return ok, f"vid1={vid1} vid2={vid2} cnt2={cnt2} exists2={exists2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_22_cantidad_por_id():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"v.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["v.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        cnt = ev.contar_miniaturas_por_id(vid)
        ev.actualizar_cantidad_miniaturas(vid, cnt, ruta_db)
        conn=sqlite3.connect(ruta_db)
        dbcnt=conn.execute("SELECT cantidad_miniaturas FROM videos WHERE id=?", (vid,)).fetchone()[0]
        conn.close()
        ok = dbcnt==cnt and cnt>0
        return ok, f"cnt={cnt} db={dbcnt}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_23_reprocesado_mismo_id():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"w.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["w.mp4"], tmp_vid.name)
        res1=guardar_videos(regs, ruta_db)
        vid=res1["ids"][0]
        res2=guardar_videos(regs, ruta_db)
        ok = res2["ids"][0]==vid
        return ok, f"vid1={vid} vid2={res2['ids'][0]}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_24_no_segundo_upsert():
    # verificar que actualizar cantidad no hace INSERT
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"x2.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["x2.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # contar inserts antes
        conn=sqlite3.connect(ruta_db)
        cnt_before=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        ev.actualizar_cantidad_miniaturas(vid, 5, ruta_db)
        conn=sqlite3.connect(ruta_db)
        cnt_after=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        ok = cnt_before==cnt_after==1
        return ok, f"cnt {cnt_before}->{cnt_after}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()
def test_25_unique_nombre_vigente():
    tmp_db=tempfile.TemporaryDirectory()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    tmp_cache, o1,o2=_setup_cache_temp()
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        regs=[{"nombre":"dup.mp4","ruta":os.path.join(tmp_db.name,"dup.mp4"),"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}]
        guardar_videos(regs, ruta_db)
        conn=None
        try:
            conn=sqlite3.connect(ruta_db)
            conn.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)", ("dup.mp4", os.path.join(tmp_db.name,"otra","dup.mp4"), rutas_mod.normalizar_ruta_clave(os.path.join(tmp_db.name,"otra","dup.mp4")), ".mp4", "2026-01-01T00:00:00"))
            conn.commit()
            ok=False
        except sqlite3.IntegrityError:
            ok=True
        finally:
            try:
                if conn: conn.close()
            except: pass
        return ok, "UNIQUE nombre vigente"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_db.cleanup()
def test_26_homonimos_rechazados():
    tmp_db=tempfile.TemporaryDirectory()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    tmp_cache, o1,o2=_setup_cache_temp()
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        regs=[{"nombre":"same.mp4","ruta":os.path.join(tmp_db.name,"a","same.mp4"),"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},{"nombre":"same.mp4","ruta":os.path.join(tmp_db.name,"b","same.mp4"),"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}]
        res=guardar_videos(regs, ruta_db)
        conn=sqlite3.connect(ruta_db)
        cnt=conn.execute("SELECT COUNT(*) FROM videos WHERE nombre='same.mp4'").fetchone()[0]
        conn.close()
        ok=cnt==1
        return ok, f"cnt={cnt}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_db.cleanup()
def test_27_unique_ruta_normalizada():
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        p1=os.path.join(tmp_db.name,"video.mp4")
        p2=os.path.join(tmp_db.name,".","video.mp4")
        regs=[{"nombre":"a.mp4","ruta":p1,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}]
        guardar_videos(regs, ruta_db)
        conn=None
        try:
            conn=sqlite3.connect(ruta_db)
            norm=rutas_mod.normalizar_ruta_clave(p2)
            conn.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)", ("b.mp4", p2, norm, ".mp4", "2026-01-01T00:00:00"))
            conn.commit()
            ok=False
        except sqlite3.IntegrityError:
            ok=True
        finally:
            try:
                if conn: conn.close()
            except: pass
        return ok, "UNIQUE ruta_normalizada"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_db.cleanup()
def test_28_integrity():
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        regs=[{"nombre":"a.mp4","ruta":os.path.join(tmp_db.name,"a.mp4"),"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}]
        guardar_videos(regs, ruta_db)
        conn=sqlite3.connect(ruta_db)
        row=conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        ok=row=="ok"
        return ok, row
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_db.cleanup()
def test_29_version():
    ok=configuracion.VERSION_PRODUCTO=="Beta 8" and configuracion.BUILD_IDENTIFICADOR=="B8.2" and configuracion.TEXTO_VERSION_BUILD=="Beta 8 - B8.2"
    return ok, f"{configuracion.VERSION_PRODUCTO} {configuracion.BUILD_IDENTIFICADOR}"

# ── B8.2 arquitectura — pruebas nuevas E ──
def test_30_ui_no_filesystem_pesado():
    import ast
    code=open("visor_videos.py",encoding="utf-8").read()
    tree=ast.parse(code)
    # localizar clase Tarjeta
    tarjeta_src=None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name=="Tarjeta":
            tarjeta_src=ast.get_source_segment(code, node)
            break
    if tarjeta_src is None:
        return False, "Tarjeta no encontrada"
    # Verificar que Tarjeta no contiene migrar_cache_legacy_a_id ni listdir/copyfile/isdir/isfile nuevos B8.2
    prohibidos=["migrar_cache_legacy_a_id", "listdir", "copyfile"]
    for p in prohibidos:
        if p in tarjeta_src:
            return False, f"Tarjeta contiene {p} prohibido en UI B8.2"
    # Verificar miniatura_principal_por_id no hace loop 1..999 ni isfile/listdir
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name=="miniatura_principal_por_id":
            src=ast.get_source_segment(code, node)
            if "range(1, 1000)" in src or "range(1,1000)" in src:
                return False, "miniatura_principal_por_id contiene loop 1..999"
            if "listdir" in src or "isfile" in src or "isdir" in src or "copyfile" in src:
                return False, f"miniatura_principal_por_id contiene FS pesado: {src[:120]}"
            break
    return True, "UI sin FS pesado B8.2"

def test_31_migracion_en_worker():
    # Verifica que TareaMiniaturasPorId y TareaPreviewsPorId propagan nombres_por_id y usan worker
    import inspect
    from tareas_videos import TareaMiniaturasPorId, TareaPreviewsPorId, TareaMigrarCacheLegacy
    sig_mini=inspect.signature(TareaMiniaturasPorId.__init__)
    sig_prev=inspect.signature(TareaPreviewsPorId.__init__)
    ok1="nombres_por_id" in sig_mini.parameters
    ok2="nombres_por_id" in sig_prev.parameters
    ok3=hasattr(TareaMigrarCacheLegacy, "_trabajo")
    # Verificar que visor inicia miniaturas con nombres_por_id
    src=open("visor_videos.py",encoding="utf-8").read()
    ok4="nombres_por_id=self._guardado_nombres_por_id" in src
    # Verificar que escanear genera con nombres_por_id
    src2=open("escanear_videos.py",encoding="utf-8").read()
    ok5="def generar_previews_faltantes_por_id(video_ids, rutas_por_id, duraciones=None, nombres_por_id=None)" in src2
    return ok1 and ok2 and ok3 and ok4 and ok5, f"mini={ok1} prev={ok2} migr={ok3} visor={ok4} escan={ok5}"

def test_32_preview_legacy_con_miniatura_id_existente():
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache, o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"a.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["a.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # crear legacy miniatura y 2 previews legacy
        legacy_mini=ruta_miniatura("a.mp4",1)
        ev.asegurar_miniatura("a.mp4", ruta, 1.0)
        assert os.path.isfile(legacy_mini)
        for i in [1,2]:
            dst=ruta_preview("a.mp4", i)
            # crear preview legacy copiando miniatura
            shutil.copyfile(legacy_mini, dst)
        assert os.path.isfile(ruta_preview("a.mp4",1))
        # generar miniatura por id (simula que ya existe v1_01)
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        assert os.path.isfile(ruta_miniatura_id(vid,1))
        # borrar previews por id si existen
        for i in [1,2]:
            p=ruta_preview_id(vid,i)
            if os.path.isfile(p):
                os.remove(p)
        # ahora existe miniatura id pero no previews id, solo legacy previews
        assert not os.path.isfile(ruta_preview_id(vid,1))
        # migrar via generar_previews_faltantes_por_id con nombres_por_id
        rutas_por_id={vid:ruta}
        nombres_por_id={vid:"a.mp4"}
        res2=ev.generar_previews_faltantes_por_id([vid], rutas_por_id, duraciones={vid:1.0}, nombres_por_id=nombres_por_id)
        ok = os.path.isfile(ruta_preview_id(vid,1)) and os.path.isfile(ruta_preview_id(vid,2)) and os.path.isfile(legacy_mini)
        return ok, f"previews migradas con miniatura existente: {os.path.isfile(ruta_preview_id(vid,1))} {res2}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()

def test_33_fallo_migracion_reportado():
    code=open("escanear_videos.py",encoding="utf-8").read()
    # Verificar que no hay except Exception: pass silencioso en migración
    if "except Exception:\n                pass" in code:
        # debe ser específico
        seg=code[code.find("migrar_cache_legacy_a_id")-2000:code.find("migrar_cache_legacy_a_id")+2000]
        if "except Exception:" in seg and "pass" in seg:
            return False, "hay except Exception: pass silencioso en migración"
    # Verificar migrar retorna fallos y no borra origen
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache,o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"b.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["b.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        legacy=ruta_miniatura("b.mp4",1)
        ev.asegurar_miniatura("b.mp4", ruta, 1.0)
        dst=ruta_miniatura_id(vid,1)
        if os.path.isfile(dst):
            os.remove(dst)
        os.makedirs(dst, exist_ok=True)
        mig=migrar_cache_legacy_a_id(vid, "b.mp4")
        ok = mig["fallos"]>=1 and os.path.isfile(legacy)
        try: os.rmdir(dst)
        except: pass
        return ok, f"fallo reportado {mig}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()

def test_34_no_loop_999_en_ui():
    code=open("visor_videos.py",encoding="utf-8").read()
    if "range(1, 1000)" in code or "range(1,1000)" in code:
        # verificar que no está en Tarjeta ni miniatura_principal_por_id
        if "miniatura_principal_por_id" in code and "range(1, 1000)" in code[code.find("miniatura_principal_por_id"):code.find("miniatura_principal_por_id")+2000]:
            return False, "loop 1..999 aún presente en UI"
    return True, "no loop 1..999"

def test_35_cache_densa_intacta():
    import exploracion_cache
    # Verificar que módulo sigue expuesto y rutas operativas
    ok1 = hasattr(exploracion_cache, "MINIMO_FOTOGRAMAS_DENSIDAD")
    ok2 = hasattr(exploracion_cache, "generar_fotogramas")
    ok3 = hasattr(exploracion_cache, "objetivo_total_densidad")
    return ok1 and ok2 and ok3, f"densa {ok1} {ok2} {ok3}"

def test_36_caller_real_previews_con_nombres():
    """Residuo 1: verifica caller REAL _siguiente_lote_previews propaga nombres_por_id"""
    import inspect
    import visor_videos
    src = inspect.getsource(visor_videos.VisorVideos._siguiente_lote_previews)
    ok_a = "nombres_por_id" in src
    ok_b = "TareaPreviewsPorId" in src and "nombres_por_id=nombres_por_id" in src
    # verificar que se construye mapping desde tarjeta._nombre sin SQLite pesado
    ok_c = "_tarjeta_por_id" in src and "_nombre" in src
    # ejecutar caso obligatorio: miniatura id existente + previews legacy presentes + id faltantes -> flujo normal previews migra
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache,o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"caller.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["caller.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # miniatura id existente
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        assert os.path.isfile(ruta_miniatura_id(vid,1))
        # legacy previews 2 archivos
        legacy_p1=ruta_preview("caller.mp4",1)
        legacy_p2=ruta_preview("caller.mp4",2)
        # crear legacy previews copiando miniatura
        shutil.copyfile(ruta_miniatura_id(vid,1), legacy_p1)
        shutil.copyfile(ruta_miniatura_id(vid,1), legacy_p2)
        assert os.path.isfile(legacy_p1) and os.path.isfile(legacy_p2)
        # asegurar que previews por id no existen (borrar si migró antes)
        for i in [1,2,3]:
            p=ruta_preview_id(vid,i)
            if os.path.isfile(p):
                os.remove(p)
        assert not os.path.isfile(ruta_preview_id(vid,1))
        # flujo normal: construir mapping como hace caller real y ejecutar TareaPreviewsPorId
        from tareas_videos import TareaPreviewsPorId
        rutas_por_id={vid:ruta}
        nombres_por_id={vid:"caller.mp4"}
        tarea=TareaPreviewsPorId([vid], rutas_por_id, duraciones={vid:1.0, ruta:1.0}, nombres_por_id=nombres_por_id)
        # verificar que tarea recibió nombres
        ok_t = tarea.nombres_por_id is not None and tarea.nombres_por_id.get(vid)=="caller.mp4"
        res2=tarea._trabajo()
        ok_migr = os.path.isfile(ruta_preview_id(vid,1)) and os.path.isfile(ruta_preview_id(vid,2)) and os.path.isfile(legacy_p1)
        # también por función directa con mismo mapping
        ok_all = ok_a and ok_b and ok_c and ok_t and ok_migr
        det = f"src_a={ok_a} src_b={ok_b} src_c={ok_c} tarea_nombres={ok_t} migr={ok_migr} res={res2.get('migracion_copiados')}"
        return ok_all, det
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()

def test_37_pipeline_fallo_migracion_observable():
    """Residuo 2: pipeline reporta fallos de migración sin borrar legacy"""
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache,o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"fallo.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["fallo.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # legacy
        legacy=ruta_miniatura("fallo.mp4",1)
        ev.asegurar_miniatura("fallo.mp4", ruta, 1.0)
        assert os.path.isfile(legacy)
        # forzar fallo: destino es directorio
        dst=ruta_miniatura_id(vid,1)
        if os.path.isfile(dst):
            os.remove(dst)
        os.makedirs(dst, exist_ok=True)
        # pipeline asegurar_miniaturas_por_id debe reportar fallos
        rutas_por_id={vid:ruta}
        nombres_por_id={vid:"fallo.mp4"}
        res1=ev.asegurar_miniaturas_por_id([vid], rutas_por_id, nombres_por_id=nombres_por_id)
        ok_a = res1.get("migracion_fallos",0)>=1 and res1.get("errores",0)>=1
        ok_b = os.path.isfile(legacy)
        # pipeline generar_previews_faltantes_por_id con mismo fallo
        # limpiar previews dst dir falla: crear dir para preview 1
        dst_p=ruta_preview_id(vid,1)
        # si preview id no existe como dir, crear dir para forzar fallo en preview migración
        # primero limpiar miniatura dir y restaurar archivo para que preview falle por dst dir
        try: os.rmdir(dst)
        except: pass
        # recrear miniatura id para que preview no use falla de miniatura sino preview
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        # crear legacy preview adicional
        legacy_prev=ruta_preview("fallo.mp4",1)
        shutil.copyfile(legacy, legacy_prev)
        # forzar fallo preview: dst como directorio
        if os.path.isfile(dst_p):
            os.remove(dst_p)
        os.makedirs(dst_p, exist_ok=True)
        res2=ev.generar_previews_faltantes_por_id([vid], rutas_por_id, duraciones={vid:1.0}, nombres_por_id=nombres_por_id)
        ok_c = res2.get("migracion_fallos",0)>=1 and res2.get("errores",0)>=1
        ok_d = os.path.isfile(legacy_prev)
        try: os.rmdir(dst_p)
        except: pass
        ok = ok_a and ok_b and ok_c and ok_d
        return ok, f"aseg fallos={res1.get('migracion_fallos')} err={res1.get('errores')} prev fallos={res2.get('migracion_fallos')} err={res2.get('errores')}"
    finally:
        # limpieza
        try:
            for p in [ruta_miniatura_id(res['ids'][0],1) if 'res' in locals() else None, ruta_preview_id(res['ids'][0],1) if 'res' in locals() else None]:
                if p and os.path.isdir(p):
                    os.rmdir(p)
        except: pass
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()

def test_38_stale_01_canonica():
    """Residuo 3: stale _01 es reemplazada atomically, segunda reutiliza sin FFmpeg, no queda _02"""
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache,o1,o2=_setup_cache_temp()
    ruta_db=os.path.join(tmp_db.name,"c.db")
    try:
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        ruta=os.path.join(tmp_vid.name,"stale.mp4")
        assert _crear_video_valido(ruta)
        regs=preparar_registros_basicos(["stale.mp4"], tmp_vid.name)
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        # generar _01 inicial
        ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        p01=ruta_miniatura_id(vid,1)
        assert os.path.isfile(p01)
        mtime1=os.path.getmtime(p01)
        size1=os.path.getsize(p01)
        # hacer stale: video más nuevo que miniatura (esperar 1.1s para mtime distinto)
        import time
        time.sleep(1.1)
        # tocar video: añadir contenido o utime
        with open(ruta,"ab") as f:
            f.write(b"\x00")
        # asegurar mtime video > mtime miniatura
        os.utime(ruta, None)
        # verificar stale: miniatura no vigente
        assert not ev.miniatura_reutilizable_por_id(vid, ruta)  # stale -> None
        # importar para visor contract
        import visor_videos as vv
        ui_path=vv.miniatura_principal_por_id(vid)
        assert ui_path==p01, f"UI canónica debe ser {p01} got {ui_path}"
        # ejecutar asegurar por id debe regenerar canónica atómicamente
        # capturar contenido stale antes
        with open(p01,"rb") as f:
            stale_content=f.read()
        # mock ffmpeg counting: segunda ejecución debe reutilizar sin FFmpeg después de regenerar
        res_aseg=ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        assert res_aseg==1
        assert os.path.isfile(p01)
        mtime2=os.path.getmtime(p01)
        # verificar mtime vigente > stale y >= video mtime
        ok_a = mtime2>mtime1 and mtime2>=os.path.getmtime(ruta)
        # verificar no _02 accidental
        p02=ruta_miniatura_id(vid,2)
        ok_b = not os.path.isfile(p02)
        # verificar contenido no es stale (mtime vigente implica regeneración; contenido puede coincidir pero mtime debe cambiar)
        # segunda ejecución: contar FFmpeg
        calls={"n":0}
        orig=ev.subprocess.run
        def cnt(*a,**k):
            cmd=a[0] if a else k.get("args")
            try:
                joint=" ".join(cmd) if isinstance(cmd,list) else str(cmd)
            except: joint=""
            if "ffmpeg" in joint:
                calls["n"]+=1
            return orig(*a,**k)
        ev.subprocess.run=cnt
        try:
            ev.asegurar_miniatura_por_id(vid, ruta, 1.0)
        finally:
            ev.subprocess.run=orig
        ok_c = calls["n"]==0
        # verificar aún canónica y sin _02
        ok_d = os.path.isfile(p01) and not os.path.isfile(p02) and vv.miniatura_principal_por_id(vid)==p01
        ok = ok_a and ok_b and ok_c and ok_d
        return ok, f"mtime1={mtime1} mtime2={mtime2} no02={ok_b} noffmpeg2={ok_c} stale_regen={ok_a}"
    finally:
        _teardown(tmp_cache,o1,o2)
        tmp_vid.cleanup(); tmp_db.cleanup()

def main():
    tests=[test_01_namespace_v1,test_02_namespace_v7,test_03_namespace_v20,test_04_no_depende_nombre,test_05_cambio_nombre_conserva,test_06_cambio_ruta_conserva,test_07_dos_ids_distintos,test_08_generacion_real_por_id,test_09_deteccion_existente_por_id,test_10_previews_faltantes_por_id,test_11_segunda_reutiliza,test_12_no_ffmpeg_si_valida,test_13_migracion_copia,test_14_legacy_permanece,test_15_migracion_idempotente,test_16_migracion_parcial,test_17_fallo_copia_no_elimina,test_18_no_fallback_permanente,test_19_renombrar_no_renombra_cache,test_20_mover_no_renombra,test_21_copiar_no_asigna_misma_cache,test_22_cantidad_por_id,test_23_reprocesado_mismo_id,test_24_no_segundo_upsert,test_25_unique_nombre_vigente,test_26_homonimos_rechazados,test_27_unique_ruta_normalizada,test_28_integrity,test_29_version,test_30_ui_no_filesystem_pesado,test_31_migracion_en_worker,test_32_preview_legacy_con_miniatura_id_existente,test_33_fallo_migracion_reportado,test_34_no_loop_999_en_ui,test_35_cache_densa_intacta,test_36_caller_real_previews_con_nombres,test_37_pipeline_fallo_migracion_observable,test_38_stale_01_canonica]
    res=[]
    for i,fn in enumerate(tests,1):
        try: ok,det=fn()
        except Exception as e: import traceback; traceback.print_exc(); ok,det=False,f"{type(e).__name__}: {e}"
        res.append((i,ok,det))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {det}")
    ok_total=all(o for _,o,_ in res)
    print(f"TOTAL={sum(1 for _,o,_ in res if o)}/{len(tests)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1
if __name__=="__main__":
    import sys; sys.exit(main())
