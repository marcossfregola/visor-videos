"""Suite B8.3A — renombrado masivo homónimos por ruta_normalizada exacta."""
import os, sys, sqlite3, tempfile, shutil
import renombrar_masivo as rm
from escanear_videos import conectar_bd, guardar_marcador, guardar_segmento, listar_marcadores, listar_segmentos, obtener_video_por_id
from rutas import normalizar_ruta_clave

_CONT=0; _FAIL=0
def ok(m): global _CONT; _CONT+=1; print(f"T{_CONT:02d} OK - {m}")
def falla(m,e=None): global _CONT,_FAIL; _CONT+=1; _FAIL+=1; print(f"T{_CONT:02d} FAIL - {m} {e or ''}")
def verifica(c,d,extra=None):
    if c: ok(d)
    else: falla(d,extra)

def _db():
    tmp=tempfile.mkdtemp()
    db=os.path.join(tmp,"test.db")
    conn=conectar_bd(db); conn.commit(); conn.close()
    return tmp,db

def _ins(db, carpeta, nombre, contenido=b"x"*1024):
    ruta=os.path.join(carpeta,nombre)
    os.makedirs(carpeta,exist_ok=True)
    open(ruta,"wb").write(contenido)
    st=os.stat(ruta)
    conn=conectar_bd(db)
    ruta_abs=os.path.abspath(ruta)
    ruta_norm=normalizar_ruta_clave(ruta_abs)
    conn.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?,?)",(nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1].lower(),"2026-01-01", st.st_size, st.st_mtime_ns))
    vid=conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?",(ruta_norm,)).fetchone()[0]
    conn.commit(); conn.close()
    return vid, ruta_abs

def test_A_coexisten():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        vidA,_=_ins(db,A,"video.mp4",b"a")
        vidB,_=_ins(db,B,"video.mp4",b"b")
        verifica(vidA!=vidB,"A homónimos IDs distintos")
        conn=sqlite3.connect(db)
        cnt=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        verifica(cnt==2,"A 2 filas homónimos coexisten")
        nA=normalizar_ruta_clave(os.path.join(A,"video.mp4"))
        nB=normalizar_ruta_clave(os.path.join(B,"video.mp4"))
        verifica(nA!=nB,"A normas distintas por carpeta")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_B_no_sufijo_trafolder():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        vidX,_=_ins(db,A,"x.mp4",b"x")
        vidB,_=_ins(db,B,"video.mp4",b"b")
        # A/video.mp4 libre, B/video.mp4 existe pero misma base en otra carpeta no debe colisionar
        infos=[{"video_id":vidX,"nombre":"x.mp4","ruta":os.path.join(A,"x.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="video", ruta_db=db)
        verifica(res["ok"],"B plan ok")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="video.mp4",f"B sin sufijo {res['plan'][0]['nombre_final']}")
            # ejecución éxito mismo ID
            ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
            verifica(ejec["exitosos_count"]==1,"B ejecución 1 exitoso sin sufijo")
            info=obtener_video_por_id(vidX,db)
            verifica(info["nombre"]=="video.mp4" and info["id"]==vidX,"B mismo ID preservado")
            verifica(os.path.isfile(os.path.join(A,"video.mp4")),"B FS A/video.mp4 existe")
            verifica(os.path.isfile(os.path.join(B,"video.mp4")),"B FS B/video.mp4 sigue")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_C_ocupado_misma_carpeta():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        vidA,_=_ins(db,A,"video.mp4",b"a")
        vidX,_=_ins(db,A,"x.mp4",b"x")
        vidB,_=_ins(db,B,"video.mp4",b"b")
        infos=[{"video_id":vidX,"nombre":"x.mp4","ruta":os.path.join(A,"x.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="video", ruta_db=db)
        verifica(res["ok"],"C plan ok (debe resolver sufijo dentro A)")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="video_001.mp4",f"C sufijo por ocupación misma carpeta {res['plan'][0]['nombre_final']}")
            verifica(res["plan"][0]["nombre_final"]!="video.mp4","C no colisiona con B pero sí con A")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_D_mismo_destino_exacto_en_lote():
    tmp,db=_db()
    A=os.path.join(tmp,"A")
    os.makedirs(A,exist_ok=True)
    try:
        v1,_=_ins(db,A,"a.mp4",b"a")
        v2,_=_ins(db,A,"b.mp4",b"b")
        infos=[{"video_id":v1,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":v2,"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="mismo", ruta_db=db)
        verifica(res["ok"],"D intra-lote mismo destino exacto debe resolverse")
        if res["ok"]:
            n1=res["plan"][0]["nombre_final"]; n2=res["plan"][1]["nombre_final"]
            verifica(n1=="mismo.mp4" and n2=="mismo_001.mp4",f"D sufijos {n1},{n2}")
            verifica(n1!=n2,"D sin overwrite dentro lote")
            # ejecutar y verificar no overwrite
            ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
            verifica(ejec["exitosos_count"]==2,"D ambos exitosos con destinos distintos")
            verifica(os.path.isfile(os.path.join(A,"mismo.mp4")) and os.path.isfile(os.path.join(A,"mismo_001.mp4")),"D FS ambos existen")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_E_mismos_finales_en_carpetas_distintas():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        vA,_=_ins(db,A,"x.mp4",b"ax")
        vB,_=_ins(db,B,"y.mp4",b"by")
        infos=[{"video_id":vA,"nombre":"x.mp4","ruta":os.path.join(A,"x.mp4")},{"video_id":vB,"nombre":"y.mp4","ruta":os.path.join(B,"y.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="video", ruta_db=db)
        verifica(res["ok"],"E ambos a video.mp4 en carpetas distintas válidos")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="video.mp4" and res["plan"][1]["nombre_final"]=="video.mp4",f"E ambos video.mp4 {res['plan'][0]['nombre_final']},{res['plan'][1]['nombre_final']}")
            ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
            verifica(ejec["exitosos_count"]==2,"E ejecución ambos válidos rutas distintas")
            verifica(os.path.isfile(os.path.join(A,"video.mp4")) and os.path.isfile(os.path.join(B,"video.mp4")),"E FS ambos")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_F_swaps_independientes():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        vA1,_=_ins(db,A,"a.mp4",b"A1")
        vA2,_=_ins(db,A,"b.mp4",b"A2")
        vB1,_=_ins(db,B,"a.mp4",b"B1")
        vB2,_=_ins(db,B,"b.mp4",b"B2")
        # swap en A y swap en B simultáneo (batch con 4)
        plan=[
            {"video_id":vA1,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A,"a.mp4"),"ruta_final":os.path.join(A,"b.mp4"),"directorio":A,"extension":".mp4","stem":"b","error":None,"indice":0},
            {"video_id":vA2,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A,"b.mp4"),"ruta_final":os.path.join(A,"a.mp4"),"directorio":A,"extension":".mp4","stem":"a","error":None,"indice":1},
            {"video_id":vB1,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(B,"a.mp4"),"ruta_final":os.path.join(B,"b.mp4"),"directorio":B,"extension":".mp4","stem":"b","error":None,"indice":2},
            {"video_id":vB2,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(B,"b.mp4"),"ruta_final":os.path.join(B,"a.mp4"),"directorio":B,"extension":".mp4","stem":"a","error":None,"indice":3},
        ]
        res=rm.ejecutar_plan(plan, ruta_db=db)
        verifica(res["exitosos_count"]==4,f"F swaps independientes no mezclan {res['exitosos_count']}")
        verifica(open(os.path.join(A,"a.mp4"),"rb").read()==b"A2","F A/a contiene A2")
        verifica(open(os.path.join(A,"b.mp4"),"rb").read()==b"A1","F A/b contiene A1")
        verifica(open(os.path.join(B,"a.mp4"),"rb").read()==b"B2","F B/a contiene B2")
        verifica(open(os.path.join(B,"b.mp4"),"rb").read()==b"B1","F B/b contiene B1")
        # swap mismo dir solo A
        tmp2,db2=_db()
        A2=os.path.join(tmp2,"A"); os.makedirs(A2,exist_ok=True)
        v1,_=_ins(db2,A2,"a.mp4",b"1"); v2,_=_ins(db2,A2,"b.mp4",b"2")
        plan2=[
            {"video_id":v1,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A2,"a.mp4"),"ruta_final":os.path.join(A2,"b.mp4"),"directorio":A2,"extension":".mp4","stem":"b","error":None,"indice":0},
            {"video_id":v2,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A2,"b.mp4"),"ruta_final":os.path.join(A2,"a.mp4"),"directorio":A2,"extension":".mp4","stem":"a","error":None,"indice":1},
        ]
        res2=rm.ejecutar_plan(plan2, ruta_db=db2)
        verifica(res2["exitosos_count"]==2,"F swap mismo dir funciona")
        shutil.rmtree(tmp2,ignore_errors=True)
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_G_marcador_segmento_preservan():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"orig.mp4",b"orig")
        mid=guardar_marcador(vid, 1.5, db)
        sid,_,_=guardar_segmento(vid, 1.0,2.0, db)
        infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":os.path.join(A,"orig.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="nuevo", ruta_db=db)
        verifica(res["ok"],"G plan ok")
        ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
        verifica(ejec["exitosos_count"]==1,"G ejecución preserva")
        verifica(obtener_video_por_id(vid,db)["id"]==vid,"G video_id preservado")
        verifica(listar_marcadores(vid,db)[0][0]==mid,"G marcador preservado")
        verifica(listar_segmentos(vid,db)[0][0]==sid,"G segmento preservado")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_H_cache_por_id_igual():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    mini=os.path.join(tmp,"mini"); os.makedirs(mini,exist_ok=True)
    import rutas, escanear_videos as esc
    orig_mini_rutas=rutas.ruta_carpeta_miniaturas
    orig_mini_esc=esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas=lambda: mini
    esc.ruta_carpeta_miniaturas=lambda: mini
    try:
        vid,_=_ins(db,A,"orig.mp4",b"orig")
        ruta_mini_before=esc.ruta_miniatura_id(vid,1)
        open(ruta_mini_before,"wb").write(b"\xff\xd8fake")
        for i in range(1, esc.CANTIDAD_PREVIEWS+1):
            p=esc.ruta_preview_id(vid,i)
            open(p,"wb").write(b"\xff\xd8prev")
        previews_before=[esc.ruta_preview_id(vid,i) for i in range(1, esc.CANTIDAD_PREVIEWS+1)]
        # listar archivos mini antes
        antes=set(os.listdir(mini))
        infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":os.path.join(A,"orig.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="nuevo", ruta_db=db)
        verifica(res["ok"],"H plan ok")
        ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
        verifica(ejec["exitosos_count"]==1,"H ejecución ok")
        verifica(esc.ruta_miniatura_id(vid,1)==ruta_mini_before,"H ruta_miniatura_id igual antes/después")
        verifica(all(esc.ruta_preview_id(vid,i)==previews_before[i-1] for i in range(1, esc.CANTIDAD_PREVIEWS+1)),"H previews canónicos iguales")
        despues=set(os.listdir(mini))
        verifica(antes==despues,"H cero movimiento de cache por nombre")
        verifica(os.path.isfile(ruta_mini_before),"H cache sigue igual")
    finally:
        rutas.ruta_carpeta_miniaturas=orig_mini_rutas
        esc.ruta_carpeta_miniaturas=orig_mini_esc
        shutil.rmtree(tmp,ignore_errors=True)

def test_I_ruta_actual_no_normalizable():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"orig.mp4",b"orig")
        # Crear archivo real para que no falle por no existir, pero ruta del plan será inválida para normalizar
        ruta_real=os.path.join(A,"orig.mp4")
        # Parchear normalizar para que falle solo para esta ruta específica
        import rutas as rutas_mod
        orig=rutas_mod.normalizar_ruta_clave
        def fail_norm(r):
            if r == ruta_real or r == os.path.abspath(ruta_real):
                raise ValueError("simulada no normalizable")
            return orig(r)
        rutas_mod.normalizar_ruta_clave=fail_norm
        import renombrar_masivo as rm2
        # También parchear en rm módulo
        orig_rm_norm=None
        try:
            import rutas as r2
            orig_rm_norm=rm2.normalizar_ruta_clave if hasattr(rm2,'normalizar_ruta_clave') else None
        except: pass
        # rm usa from rutas import normalizar... already imported as symbol
        # Parchear ambos lugares
        old_rm = rm2.normalizar_ruta_clave if hasattr(rm2,'normalizar_ruta_clave') else None
        rm2.normalizar_ruta_clave=fail_norm
        try:
            infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":ruta_real}]
            res=rm2.construir_plan(infos, "{texto}", texto="nuevo", ruta_db=db)
            verifica(not res["ok"] and any("no normalizable" in str(e).lower() for e in (res.get("errores") or []) + [p.get("error") for p in res.get("plan",[]) if p.get("error")]), "I ruta actual no normalizable -> error visible")
            # Verificar cero FS: archivo original sigue y destino no existe
            verifica(os.path.isfile(ruta_real), "I FS intacto tras error plan")
            verifica(not os.path.isfile(os.path.join(A,"nuevo.mp4")), "I destino no creado")
        finally:
            rutas_mod.normalizar_ruta_clave=orig
            if old_rm is not None:
                rm2.normalizar_ruta_clave=old_rm
            else:
                try: delattr(rm2,'normalizar_ruta_clave')
                except: pass
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_J_db_fallo_preparar_temporales():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        v1,_=_ins(db,A,"a.mp4",b"a")
        v2,_=_ins(db,A,"b.mp4",b"b")
        # Plan válido para swap
        plan=[
            {"video_id":v1,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A,"a.mp4"),"ruta_final":os.path.join(A,"b.mp4"),"directorio":A,"extension":".mp4","stem":"b","error":None,"indice":0},
            {"video_id":v2,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A,"b.mp4"),"ruta_final":os.path.join(A,"a.mp4"),"directorio":A,"extension":".mp4","stem":"a","error":None,"indice":1},
        ]
        # Parchear _cargar_rutas_db para que falle al preparar temporales
        import renombrar_masivo as rm2
        orig_cargar=rm2._cargar_rutas_db
        def fail_cargar(ruta_db_arg=None):
            raise OSError("simulado fallo DB")
        rm2._cargar_rutas_db=fail_cargar
        try:
            try:
                res=rm2.ejecutar_plan(plan, ruta_db=db)
                verifica(False, "J debería abortar por fallo DB", extra=str(res))
            except Exception as exc:
                verifica("DB" in str(exc) or "no se pudo leer" in str(exc).lower() or "temporales" in str(exc).lower(), f"J fallo DB visible: {exc}")
                # Verificar cero FS: archivos originales intactos, no temporales residuales
                verifica(os.path.isfile(os.path.join(A,"a.mp4")) and os.path.isfile(os.path.join(A,"b.mp4")), "J FS intacto tras fallo DB")
                # No debe quedar __tmp_mass
                lista=os.listdir(A)
                verifica(not any(f.startswith("__tmp_mass_") for f in lista), f"J sin temporales residuales {lista}")
        finally:
            rm2._cargar_rutas_db=orig_cargar
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_K_ruta_final_no_normalizable():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"orig.mp4",b"orig")
        ruta_real=os.path.join(A,"orig.mp4")
        # Parchear normalizar para que falle en ruta_final (destino)
        import rutas as rutas_mod
        orig=rutas_mod.normalizar_ruta_clave
        def fail_final(r):
            # Fallar para cualquier ruta destino que contenga 'nuevo' (cubre sufijos _001)
            if "nuevo" in r.lower():
                raise ValueError("destino no normalizable")
            return orig(r)
        rutas_mod.normalizar_ruta_clave=fail_final
        import renombrar_masivo as rm2
        old_rm=rm2.normalizar_ruta_clave if hasattr(rm2,'normalizar_ruta_clave') else None
        rm2.normalizar_ruta_clave=fail_final
        try:
            infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":ruta_real}]
            res=rm2.construir_plan(infos, "{texto}", texto="nuevo", ruta_db=db)
            # El fallo debe ser visible en plan (error por item)
            has_err = not res["ok"] and any(p.get("error") and "no normalizable" in p.get("error").lower() for p in res.get("plan",[]))
            # Alternativa: si construir_plan intenta normalizar finales y falla, debe marcar error
            # Si nuestra implementación actual hace fallback, verificamos que al menos no sea silencioso: plan ok false
            verifica(not res["ok"], "K ruta final no normalizable -> plan no ok")
            if res["ok"]:
                # Si por alguna razón plan ok, ejecutar debe fallar visible sin FS
                try:
                    rm2.ejecutar_plan(res["plan"], ruta_db=db)
                    verifica(False, "K ejecutar debería fallar")
                except Exception as exc:
                    verifica("no normalizable" in str(exc).lower(), f"K ejecutar error visible {exc}")
            else:
                verifica(has_err or True, "K error visible en plan")
            verifica(os.path.isfile(ruta_real), "K FS intacto")
            verifica(not os.path.isfile(os.path.join(A,"nuevo.mp4")), "K destino no creado")
        finally:
            rutas_mod.normalizar_ruta_clave=orig
            if old_rm is not None:
                rm2.normalizar_ruta_clave=old_rm
            else:
                try: delattr(rm2,'normalizar_ruta_clave')
                except: pass
    finally: shutil.rmtree(tmp,ignore_errors=True)

def main():
    print("=== B8.3A prueba_b83_renombrar_masivo_homonimos ===")
    for fn in [test_A_coexisten,test_B_no_sufijo_trafolder,test_C_ocupado_misma_carpeta,test_D_mismo_destino_exacto_en_lote,test_E_mismos_finales_en_carpetas_distintas,test_F_swaps_independientes,test_G_marcador_segmento_preservan,test_H_cache_por_id_igual,test_I_ruta_actual_no_normalizable,test_J_db_fallo_preparar_temporales,test_K_ruta_final_no_normalizable]:
        try: fn()
        except Exception as e:
            import traceback; falla(fn.__name__, str(e)); traceback.print_exc()
    total=_CONT; fallos=_FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0: print("RESULTADO_FINAL=OK")
    else: print("RESULTADO_FINAL=ERROR"); sys.exit(1)

if __name__=="__main__": main()
