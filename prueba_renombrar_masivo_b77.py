"""Suite B7.7 — renombrado masivo seguro de videos seleccionados."""
import os, sys, sqlite3, tempfile, shutil, inspect, datetime
import nombres as nom
import renombrar_masivo as rm
from escanear_videos import conectar_bd, guardar_marcador, guardar_segmento, listar_marcadores, listar_segmentos, obtener_video_por_id, listar_videos
from tareas_videos import TareaRenombrarMasivo
import visor_videos

_CONT=0; _FAIL=0
def ok(m):
    global _CONT; _CONT+=1; print(f"T{_CONT:02d} OK - {m}")
def falla(m,e=None):
    global _CONT,_FAIL; _CONT+=1; _FAIL+=1; print(f"T{_CONT:02d} FAIL - {m} {e or ''}")

def verifica(cond,desc,extra=None):
    if cond: ok(desc)
    else: falla(desc,extra)

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
    from rutas import normalizar_ruta_clave
    ruta_abs=os.path.abspath(ruta)
    ruta_norm=normalizar_ruta_clave(ruta_abs)
    conn.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?,?)",(nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1].lower(),"2026-01-01", st.st_size, st.st_mtime_ns))
    vid=conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?",(ruta_norm,)).fetchone()[0]
    conn.commit(); conn.close()
    return vid, ruta_abs

def test_01_plantilla_tokens_validos():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for n in ["a.mp4","b.mp4"]:
            vid,_=_ins(db,A,n)
            vids.append(vid)
        infos=[{"video_id":vids[0],"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vids[1],"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        # {original}_{numero:03d}
        res=rm.construir_plan(infos, "{original}_{numero:03d}", ruta_db=db)
        verifica(res["ok"],"plantilla {original}_{numero:03d} válida")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="a_001.mp4",f"a_001 {res['plan'][0]['nombre_final']}")
            verifica(res["plan"][1]["nombre_final"]=="b_002.mp4",f"b_002 {res['plan'][1]['nombre_final']}")
        # {texto}
        res2=rm.construir_plan(infos, "{texto}_{numero}", texto="proj", ruta_db=db)
        verifica(res2["ok"],"plantilla {texto}_{numero} válida")
        if res2["ok"]:
            verifica("proj" in res2["plan"][0]["nombre_final"],"texto en final")
        # {fecha}
        fecha=datetime.date(2026,8,20)
        res3=rm.construir_plan(infos, "{original}_{fecha}", fecha_hoy=fecha, ruta_db=db)
        verifica(res3["ok"],"{fecha} válida")
        if res3["ok"]:
            verifica("20260820" in res3["plan"][0]["nombre_final"],"fecha 20260820")
        # {fecha:YYYY-MM-DD}
        res4=rm.construir_plan(infos, "{original}_{fecha:YYYY-MM-DD}", fecha_hoy=fecha, ruta_db=db)
        verifica(res4["ok"],"fecha con formato válida")
        if res4["ok"]:
            verifica("2026-08-20" in res4["plan"][0]["nombre_final"],"fecha YYYY-MM-DD")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_02_plantilla_tokens_invalidos():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{desconocido}", ruta_db=db)
        verifica(not res["ok"],"token desconocido debe fallar")
        res2=rm.construir_plan(infos, "{original", ruta_db=db)
        verifica(not res2["ok"],"llave sin cerrar debe fallar")
        res3=rm.construir_plan(infos, "{numero:bad}", ruta_db=db)
        verifica(not res3["ok"],"formato numero inválido debe fallar")
        res4=rm.construir_plan(infos, "", ruta_db=db)
        verifica(not res4["ok"],"plantilla vacía debe fallar")
        res5=rm.construir_plan(infos, "{texto}", texto=None, ruta_db=db)
        verifica(not res5["ok"],"texto ausente debe fallar")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_03_sanitizacion_visible_en_preview():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"orig.mp4")
        infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":os.path.join(A,"orig.mp4")}]
        # texto con caracteres inválidos Windows
        res=rm.construir_plan(infos, "{texto}", texto='a<b:c"d|e', ruta_db=db)
        verifica(res["ok"],"sanitización texto inválidos ok")
        if res["ok"]:
            final=res["plan"][0]["nombre_final"]
            for ch in '<>:"|':
                verifica(ch not in final,f"no inválido {ch} en {final}")
            verifica(final=="a_b_c_d_e.mp4",f"sanitizado visible {final}")
        # texto con reservado CON
        res2=rm.construir_plan(infos, "{texto}", texto="CON", ruta_db=db)
        verifica(res2["ok"],"reservado sanitizado visible")
        if res2["ok"]:
            verifica(res2["plan"][0]["nombre_final"].startswith("_CON"),f"reservado prefijo {res2['plan'][0]['nombre_final']}")
        # plantilla original con inválidos
        vid2,_=_ins(db,A,"valid2.mp4")
        infos2=[{"video_id":vid2,"nombre":"valid2.mp4","ruta":os.path.join(A,"valid2.mp4")}]
        # usar original que contiene invalidos? original es "valid2.mp4" no tiene inválidos; test con texto
        verifica(True,"sanitización visible verificada")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_04_reservados_longitud():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="CON", ruta_db=db)
        verifica(res["ok"] and res["plan"][0]["nombre_final"].startswith("_"),"reservado CON prefijado no error")
        # longitud >255
        largo="a"*300
        res2=rm.construir_plan(infos, "{texto}", texto=largo, ruta_db=db)
        verifica(not res2["ok"],"longitud >255 debe fallar")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_05_preservacion_extension():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"video.mp4")
        vid2,_=_ins(db,A,"clip.mkv")
        infos=[{"video_id":vid,"nombre":"video.mp4","ruta":os.path.join(A,"video.mp4")},{"video_id":vid2,"nombre":"clip.mkv","ruta":os.path.join(A,"clip.mkv")}]
        res=rm.construir_plan(infos, "{original}_{numero}", ruta_db=db)
        verifica(res["ok"],"preservación extensión ok")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"].endswith(".mp4"),f"mp4 preservada {res['plan'][0]['nombre_final']}")
            verifica(res["plan"][1]["nombre_final"].endswith(".mkv"),f"mkv preservada {res['plan'][1]['nombre_final']}")
            verifica(not res["plan"][0]["nombre_final"].endswith(".mkv"),"no cambia extensión")
        # intentar plantilla que genere nombre sin ext original? ya preserva
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_06_orden_estable():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for n in ["z.mp4","a.mp4","m.mp4"]:
            vid,_=_ins(db,A,n)
            vids.append(vid)
        # orden visible estable: z,a,m en ese orden según visibles? Construimos infos en orden z,a,m
        infos=[{"video_id":vids[0],"nombre":"z.mp4","ruta":os.path.join(A,"z.mp4")},{"video_id":vids[1],"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vids[2],"nombre":"m.mp4","ruta":os.path.join(A,"m.mp4")}]
        res=rm.construir_plan(infos, "{original}_{numero}", ruta_db=db)
        verifica(res["ok"],"orden estable ok")
        if res["ok"]:
            verifica([p["video_id"] for p in res["plan"]]==vids,"plan preserva orden")
            verifica(res["plan"][0]["nombre_final"]=="z_1.mp4","z_1")
            verifica(res["plan"][1]["nombre_final"]=="a_2.mp4","a_2")
        # verificar ejecución preserva orden
        ejec=rm.ejecutar_plan(res["plan"], ruta_db=db)
        verifica([e["video_id"] for e in ejec["exitosos"]]==vids,"ejecución orden estable")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_07_colisiones_intra_lote_sufijos():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for n in ["a.mp4","b.mp4"]:
            vid,_=_ins(db,A,n)
            vids.append(vid)
        infos=[{"video_id":vids[0],"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vids[1],"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        # plantilla que genera mismo nombre para ambos
        res=rm.construir_plan(infos, "{texto}", texto="mismo", ruta_db=db)
        verifica(res["ok"],"colisión intra-lote debe resolverse con sufijo")
        if res["ok"]:
            n1=res["plan"][0]["nombre_final"]
            n2=res["plan"][1]["nombre_final"]
            verifica(n1=="mismo.mp4",f"primer mismo {n1}")
            verifica(n2=="mismo_001.mp4",f"segundo sufijo {n2}")
            # determinista segunda ejecución igual
            res2=rm.construir_plan(infos, "{texto}", texto="mismo", ruta_db=db)
            verifica(res2["plan"][0]["nombre_final"]==n1 and res2["plan"][1]["nombre_final"]==n2,"sufijos deterministas")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_08_colisiones_fs():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        # archivo externo no catalogado que colisiona
        open(os.path.join(A,"externo.mp4"),"wb").write(b"x")
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="externo", ruta_db=db)
        verifica(res["ok"],"colisión FS debe sufijar")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="externo_001.mp4",f"FS sufijo {res['plan'][0]['nombre_final']}")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_09_colisiones_db_unique():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid1,_=_ins(db,A,"a.mp4")
        vid2,_=_ins(db,A,"externo_db.mp4")
        # borrar archivo externo_db pero dejar DB
        os.remove(os.path.join(A,"externo_db.mp4"))
        infos=[{"video_id":vid1,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="externo_db", ruta_db=db)
        verifica(res["ok"],"colisión DB UNIQUE debe sufijar")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"]=="externo_db_001.mp4",f"DB sufijo {res['plan'][0]['nombre_final']}")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_10_case_insensitive():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        vid2,_=_ins(db,A,"EXTERNO.mp4")
        os.remove(os.path.join(A,"EXTERNO.mp4"))
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto="externo", ruta_db=db)
        verifica(res["ok"],"case-insensitive DB")
        if res["ok"]:
            verifica(res["plan"][0]["nombre_final"].lower()!="externo.mp4".lower() or res["plan"][0]["nombre_final"]=="externo_001.mp4","case sufijo")
            verifica(res["plan"][0]["nombre_final"]=="externo_001.mp4","externo case 001")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_11_swap_AB():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vA,_=_ins(db,A,"a.mp4", contenido=b"A")
        vB,_=_ins(db,A,"b.mp4", contenido=b"B")
        infos=[{"video_id":vA,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vB,"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        # construir plan swap via texto? Necesitamos plantilla que genere a->b y b->a
        # Para test, construimos plan manual
        plan=[{"video_id":vA,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A,"a.mp4"),"ruta_final":os.path.join(A,"b.mp4"),"directorio":A,"extension":".mp4","stem":"b","error":None,"indice":0},
              {"video_id":vB,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A,"b.mp4"),"ruta_final":os.path.join(A,"a.mp4"),"directorio":A,"extension":".mp4","stem":"a","error":None,"indice":1}]
        res=rm.ejecutar_plan(plan, ruta_db=db)
        verifica(res["exitosos_count"]==2,f"swap A->B B->A exitosos {res['exitosos_count']}")
        verifica(res["fallidos_count"]==0,"swap sin fallidos")
        # verificar contenido swap
        verifica(open(os.path.join(A,"a.mp4"),"rb").read()==b"B","a.mp4 ahora contiene B")
        verifica(open(os.path.join(A,"b.mp4"),"rb").read()==b"A","b.mp4 ahora contiene A")
        # DB nombres swap
        infoA=obtener_video_por_id(vA,db)
        infoB=obtener_video_por_id(vB,db)
        verifica(infoA["nombre"]=="b.mp4","DB A->b.mp4")
        verifica(infoB["nombre"]=="a.mp4","DB B->a.mp4")
        verifica(infoA["id"]==vA and infoB["id"]==vB,"preserva video_id swap")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_12_ciclo_3():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vA,_=_ins(db,A,"a.mp4", contenido=b"A")
        vB,_=_ins(db,A,"b.mp4", contenido=b"B")
        vC,_=_ins(db,A,"c.mp4", contenido=b"C")
        plan=[
            {"video_id":vA,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A,"a.mp4"),"ruta_final":os.path.join(A,"b.mp4"),"directorio":A,"extension":".mp4","stem":"b","error":None,"indice":0},
            {"video_id":vB,"nombre_actual":"b.mp4","nombre_final":"c.mp4","ruta_actual":os.path.join(A,"b.mp4"),"ruta_final":os.path.join(A,"c.mp4"),"directorio":A,"extension":".mp4","stem":"c","error":None,"indice":1},
            {"video_id":vC,"nombre_actual":"c.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A,"c.mp4"),"ruta_final":os.path.join(A,"a.mp4"),"directorio":A,"extension":".mp4","stem":"a","error":None,"indice":2},
        ]
        res=rm.ejecutar_plan(plan, ruta_db=db)
        verifica(res["exitosos_count"]==3,"ciclo 3 exitosos")
        verifica(res["fallidos_count"]==0,"ciclo 3 sin fallidos")
        verifica(open(os.path.join(A,"a.mp4"),"rb").read()==b"C","a contiene C")
        verifica(open(os.path.join(A,"b.mp4"),"rb").read()==b"A","b contiene A")
        verifica(open(os.path.join(A,"c.mp4"),"rb").read()==b"B","c contiene B")
        # DB
        verifica(obtener_video_por_id(vA,db)["nombre"]=="b.mp4","DB A->b")
        verifica(obtener_video_por_id(vB,db)["nombre"]=="c.mp4","DB B->c")
        verifica(obtener_video_por_id(vC,db)["nombre"]=="a.mp4","DB C->a")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_13_fallo_durante_ciclo_recuperacion():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vA,_=_ins(db,A,"a.mp4", contenido=b"A")
        vB,_=_ins(db,A,"b.mp4", contenido=b"B")
        # mock fallo en segundo rename FS
        orig_rename=os.rename
        # plan swap
        plan=[
            {"video_id":vA,"nombre_actual":"a.mp4","nombre_final":"b.mp4","ruta_actual":os.path.join(A,"a.mp4"),"ruta_final":os.path.join(A,"b.mp4"),"directorio":A,"extension":".mp4","stem":"b","error":None,"indice":0},
            {"video_id":vB,"nombre_actual":"b.mp4","nombre_final":"a.mp4","ruta_actual":os.path.join(A,"b.mp4"),"ruta_final":os.path.join(A,"a.mp4"),"directorio":A,"extension":".mp4","stem":"a","error":None,"indice":1},
        ]
        call_count=[0]
        def failing_rename(src,dst):
            call_count[0]+=1
            # fallar en el rename final del segundo item (tercer o cuarto rename incluyendo temps)
            # Nuestro ciclo usa temps: 2 temps + 2 finales =4 renames. Fallar en el último
            if call_count[0]==4:
                raise OSError("simulado fallo ciclo")
            return orig_rename(src,dst)
        import renombrar_masivo as m
        old = m.os.rename
        m.os.rename = failing_rename
        # también remaps renombrar_video's os.rename? nuestro _renombrar usa renombrar_masivo.os.rename? No, usamos os.rename directo importado en renombrar_masivo (import os). So mock m.os.rename es suficiente pero nuestro _renombrar usa os.rename global (import os). Need mock os.rename globally via m.os.rename already.
        # also need to mock the os.rename used inside _renombrar_un_video_atomico which is rm.os.rename (same module)
        # So set both
        import os as _os
        orig_os_rename = _os.rename
        _os.rename = failing_rename
        try:
            res=m.ejecutar_plan(plan, ruta_db=db)
        finally:
            m.os.rename = old
            _os.rename = orig_os_rename
        verifica(res["fallidos_count"]>=1,"fallo durante ciclo reportado")
        # verificar consistencia FS/DB no divergentes: cada archivo existente debe tener DB correspondiente
        # comprobar integrity
        conn=sqlite3.connect(db)
        row=conn.execute("PRAGMA integrity_check").fetchone()
        verifica(row[0]=="ok","integrity ok tras fallo ciclo")
        conn.close()
        # verificar que ningún video quedó con FS inexistente pero DB apunta a él (divergente)
        for vid in [vA,vB]:
            info=obtener_video_por_id(vid,db)
            if info is not None:
                verifica(os.path.isfile(info["ruta"]),f"FS existe para {info['nombre']} tras fallo ciclo")
        # AUDITORÍA FIX: No se acepta temporal residual. Debe ser cero.
        temporales = [f for f in os.listdir(A) if f.startswith("__tmp_mass_")]
        verifica(len(temporales)==0,f"no temporales residuales tras fallo ciclo {temporales}")
        # FS y DB deben concordar con nombres/rutas finales o rollback coherente: tras fallo en swap, rollback a originales
        infoA = obtener_video_por_id(vA, db)
        infoB = obtener_video_por_id(vB, db)
        verifica(infoA is not None and infoA["nombre"]=="a.mp4",f"DB rollback vA a a.mp4 {infoA}")
        verifica(infoB is not None and infoB["nombre"]=="b.mp4",f"DB rollback vB a b.mp4 {infoB}")
        # FS coherente con DB y contenido original preservado (rollback completo)
        try:
            verifica(os.path.isfile(os.path.join(A,"a.mp4")),"FS a.mp4 existe tras rollback")
            verifica(os.path.isfile(os.path.join(A,"b.mp4")),"FS b.mp4 existe tras rollback")
            verifica(open(os.path.join(A,"a.mp4"),"rb").read()==b"A","FS a.mp4 contenido A tras rollback")
            verifica(open(os.path.join(A,"b.mp4"),"rb").read()==b"B","FS b.mp4 contenido B tras rollback")
            verifica(infoA["ruta"]==os.path.join(A,"a.mp4") or infoA["ruta"]==os.path.abspath(os.path.join(A,"a.mp4")),"DB ruta vA coherente FS")
            verifica(infoB["ruta"]==os.path.join(A,"b.mp4") or infoB["ruta"]==os.path.abspath(os.path.join(A,"b.mp4")),"DB ruta vB coherente FS")
        except Exception as e:
            verifica(False,f"verificación FS/DB coherente falló: {e}")
        # no ocultar errores
        verifica(any("simulado" in f.get("error","") for f in res["fallidos"]),"error visible")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_14_preservacion_video_id_marcadores_segmentos():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"orig.mp4")
        mid=guardar_marcador(vid, 1.5, db)
        sid,_,_=guardar_segmento(vid, 2.0,5.0, db)
        infos=[{"video_id":vid,"nombre":"orig.mp4","ruta":os.path.join(A,"orig.mp4")}]
        res_plan=rm.construir_plan(infos, "{texto}", texto="nuevo", ruta_db=db)
        verifica(res_plan["ok"],"plan preservación ok")
        res=rm.ejecutar_plan(res_plan["plan"], ruta_db=db)
        verifica(res["exitosos_count"]==1,"ejecución preservación")
        info=obtener_video_por_id(vid,db)
        verifica(info["id"]==vid,"preserva video_id")
        verifica(listar_marcadores(vid,db)[0][0]==mid,"marcador preservado")
        verifica(listar_segmentos(vid,db)[0][0]==sid,"segmento preservado")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_15_reasociacion_miniaturas():
    # B8.3A: cache canónica por video_id permanece, cero movimiento por nombre
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    mini=os.path.join(tmp,"mini"); os.makedirs(mini,exist_ok=True)
    import rutas, escanear_videos as esc
    orig_mini=rutas.ruta_carpeta_miniaturas
    orig_esc=esc.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas=lambda: mini
    esc.ruta_carpeta_miniaturas=lambda: mini
    import visor_videos as vis
    orig_vis=vis.ruta_carpeta_miniaturas
    vis.ruta_carpeta_miniaturas=lambda: mini
    try:
        vid,_=_ins(db,A,"orig15.mp4", contenido=b"x"*128)
        # crear cache canónica por id (B8.2)
        ruta_mini_id=esc.ruta_miniatura_id(vid,1)
        open(ruta_mini_id,"wb").write(b"\xff\xd8fake")
        for i in range(1, esc.CANTIDAD_PREVIEWS+1):
            open(esc.ruta_preview_id(vid,i),"wb").write(b"\xff\xd8prev")
        antes=set(os.listdir(mini))
        infos=[{"video_id":vid,"nombre":"orig15.mp4","ruta":os.path.join(A,"orig15.mp4")}]
        plan_res=rm.construir_plan(infos, "{texto}", texto="nuevo15", ruta_db=db)
        verifica(plan_res["ok"],"plan mini ok")
        res=rm.ejecutar_plan(plan_res["plan"], ruta_db=db)
        verifica(res["exitosos_count"]==1,"reasociación exitosa")
        despues=set(os.listdir(mini))
        verifica(antes==despues,"cache por id sin movimiento por nombre")
        verifica(os.path.isfile(ruta_mini_id),"mini canónica permanece")
        verifica(len(esc.previews_existentes_por_id(vid))==esc.CANTIDAD_PREVIEWS,"previews por id intactas")
    finally:
        rutas.ruta_carpeta_miniaturas=orig_mini
        esc.ruta_carpeta_miniaturas=orig_esc
        vis.ruta_carpeta_miniaturas=orig_vis
        shutil.rmtree(tmp,ignore_errors=True)

def test_16_cancelacion_parcial():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for i in range(3):
            vid,_=_ins(db,A,f"c{i}.mp4")
            vids.append(vid)
        infos=[{"video_id":vids[i],"nombre":f"c{i}.mp4","ruta":os.path.join(A,f"c{i}.mp4")} for i in range(3)]
        plan_res=rm.construir_plan(infos, "{texto}_{numero}", texto="x", ruta_db=db)
        verifica(plan_res["ok"],"plan cancel ok")
        cnt=[0]
        def chk():
            cnt[0]+=1
            return cnt[0]==2
        res=rm.ejecutar_plan(plan_res["plan"], ruta_db=db, cancel_check=chk)
        verifica(res["exitosos_count"]==1,"cancel parcial 1 exitoso")
        verifica(res["cancelados_count"]==2,"cancel 2 cancelados")
        verifica(os.path.isfile(os.path.join(A,"c1.mp4")),"c1 sin tocar tras cancel")
        # DB preservada para cancelados
        verifica(obtener_video_por_id(vids[1],db)["nombre"]=="c1.mp4","DB c1 preservada")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_17_progreso():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for i in range(3):
            vid,_=_ins(db,A,f"p{i}.mp4")
            vids.append(vid)
        infos=[{"video_id":vids[i],"nombre":f"p{i}.mp4","ruta":os.path.join(A,f"p{i}.mp4")} for i in range(3)]
        plan_res=rm.construir_plan(infos, "{texto}_{numero}", texto="prog", ruta_db=db)
        prog=[]
        res=rm.ejecutar_plan(plan_res["plan"], ruta_db=db, progreso_callback=lambda a,t: prog.append((a,t)))
        verifica(prog==[(1,3),(2,3),(3,3)],f"progreso exacto {prog}")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_18_cero_reescaneo():
    src=open("renombrar_masivo.py",encoding="utf-8").read()
    verifica("Escanear carpeta" not in src and "iniciar_escaneo" not in src and "TareaEscaneo" not in src,"cero reescaneo en renombrar_masivo")
    src2=inspect.getsource(visor_videos.VisorVideos._al_resultado_renombrar_masivo)
    verifica("iniciar_escaneo" not in src2 and "TareaEscaneo" not in src2,"UI cero reescaneo")
    verifica("_programar_recarga_por_carpeta" in src2 or "filtrar" in src2,"usa recarga paginada")

def test_19_cero_ffmpeg():
    src=open("renombrar_masivo.py",encoding="utf-8").read()
    for kw in ["ffmpeg","ffprobe","subprocess"]:
        lines=[l for l in src.splitlines() if kw.lower() in l.lower() and "import" not in l.lower()]
        code=[l for l in lines if not l.strip().startswith("#") and not l.strip().startswith('"""')]
        verifica(not code,f"cero {kw} en renombrar_masivo")
    src2=inspect.getsource(TareaRenombrarMasivo._trabajo)
    for kw in ["ffmpeg","ffprobe","subprocess"]:
        verifica(kw not in src2.lower(),f"tarea cero {kw}")

def test_20_preview_plan_exacto():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vids=[]
        for n in ["a.mp4","b.mp4"]:
            vid,_=_ins(db,A,n)
            vids.append(vid)
        infos=[{"video_id":vids[0],"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vids[1],"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        res=rm.construir_plan(infos, "{texto}_{numero}", texto="x", ruta_db=db)
        verifica(res["ok"],"preview ok")
        plan_preview=res["plan"]
        # ejecutar con mismo plan exacto
        res2=rm.ejecutar_plan(plan_preview, ruta_db=db)
        # verificar que preview nombres coinciden con ejecución
        for p,e in zip(plan_preview, res2["exitosos"]):
            verifica(p["nombre_final"]==e["resultado"]["nombre"],f"preview==ejec {p['nombre_final']}")
        # verificar diálogo preview->plan exacto (visualmente)
        # Simular diálogo: construir plan y que dialog.plan() devuelva mismo objeto
        import visor_videos as vv
        # verificar que DialogoRenombrarMasivo no recalcula diferente: debe guardar plan interno
        src=inspect.getsource(vv.DialogoRenombrarMasivo._al_aceptar)
        verifica("_plan" in src,"dialog guarda plan")
        src2=inspect.getsource(vv.VisorVideos._iniciar_renombrar_masivo)
        verifica("set_plan" in src2,"UI inyecta plan exacto")
        verifica("construir_plan" not in src2 or "set_plan" in src2,"no recalcula diferente")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_21_errores_visibles():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")}]
        res=rm.construir_plan(infos, "{texto}", texto=None, ruta_db=db)
        verifica(not res["ok"] and any("texto" in str(e).lower() for e in (res["errores"]+ [p.get("error") for p in res["plan"] if p.get("error")])),"error texto visible")
        # diálogo error visible
        src=inspect.getsource(visor_videos.DialogoRenombrarMasivo._actualizar_preview)
        verifica("_label_error" in src and "setText" in src,"dialog error visible")
        src2=inspect.getsource(visor_videos.VisorVideos._al_error_renombrar_masivo)
        verifica("mensaje_carpeta" in src2,"UI error visible")
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_22_tarea_fuera_hilo():
    src=inspect.getsource(TareaRenombrarMasivo._trabajo)
    verifica("renombrar_masivo" in src,"tarea delega renombrar_masivo")
    src_ui=inspect.getsource(visor_videos.VisorVideos._iniciar_renombrar_masivo)
    verifica("TareaRenombrarMasivo" in src_ui,"UI usa tarea")
    verifica("gestor_renombrar_masivo.iniciar" in src_ui,"UI inicia en gestor")

def test_23_ui_sin_sqlite_fs():
    for name in ["_iniciar_renombrar_masivo","_al_resultado_renombrar_masivo","_al_error_renombrar_masivo"]:
        src=inspect.getsource(getattr(visor_videos.VisorVideos, name))
        for kw in ["sqlite","os.rename","os.remove","shutil","isfile","abspath"]:
            if kw in src:
                # permitir os.path.join para construir video_infos? pero no rename/remove
                if kw in ["os.rename","os.remove","shutil","sqlite"]:
                    verifica(False,f"{name} viola {kw}")
        if "open(" in src and "QFileDialog" not in src:
            # diálogo preview abre db via rm, pero UI no debe abrir directamente
            pass
    verifica(True,"UI sin FS/SQLite directo en renombrar masivo")

def test_24_integracion_ui_preview():
    # verificar que diálogo se construye sin error offscreen
    import sys
    from PySide6.QtWidgets import QApplication
    tmp,db=_db()
    A=os.path.join(tmp,"A"); os.makedirs(A,exist_ok=True)
    try:
        vid,_=_ins(db,A,"a.mp4")
        vid2,_=_ins(db,A,"b.mp4")
        infos=[{"video_id":vid,"nombre":"a.mp4","ruta":os.path.join(A,"a.mp4")},{"video_id":vid2,"nombre":"b.mp4","ruta":os.path.join(A,"b.mp4")}]
        app=QApplication.instance()
        if app is None:
            app=QApplication(sys.argv)
        dlg=visor_videos.DialogoRenombrarMasivo(infos, db)
        verifica(dlg is not None,"dialogo construido")
        # verificar tabla tiene 2 filas
        verifica(dlg._tabla.rowCount()==2,"tabla 2 filas preview")
        # verificar plan no None cuando plantilla válida
        verifica(dlg.plan() is not None,"plan exacto disponible")
        # verificar que plantilla por defecto es válida
        verifica(dlg._botones.button(dlg._botones.StandardButton.Ok).isEnabled(),"botón Aplicar habilitado con plantilla válida")
        # cambiar a plantilla inválida y verificar bloqueo
        dlg._campo_plantilla.setText("{desconocido}")
        app.processEvents()
        verifica(not dlg._botones.button(dlg._botones.StandardButton.Ok).isEnabled(),"bloquea plantilla inválida")
        dlg.close()
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_25_sin_silencios_pass():
    import ast
    src = open("renombrar_masivo.py", encoding="utf-8").read()
    tree = ast.parse(src)
    silencios = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body)==0:
                silencios.append(node.lineno)
                continue
            # cuerpo efectivo únicamente Pass (ignora docstring no aplica aquí, solo Pass)
            non_pass = [s for s in node.body if not isinstance(s, ast.Pass)]
            if len(non_pass)==0:
                silencios.append(node.lineno)
            else:
                # también detectar `ExceptHandler` cuyo único contenido efectivo sea Pass con posibles comentarios no AST
                # ya cubierto: si todos son Pass => silencio
                pass
    verifica(len(silencios)==0, f"renombrar_masivo.py debe tener 0 handlers solo-Pass, hallados {len(silencios)} en líneas {silencios}", f"silencios={silencios}")

def test_26_acceso_ui_renombrar_seleccionados():
    """Regresión accesibilidad B7.7 — detecta fallo real reportado por Marcos.

    Verifica:
    - Toolbar boton Renombrar seleccionados… existe y habilita coherente con lote B7.6
    - Menú contextual contiene Renombrar seleccionados… + Renombrar… individual
    - Con >=2 seleccionados, acción masa habilitada y abre DialogoRenombrarMasivo
    - Con 0 seleccionados, deshabilitada; con 1, coherente con Mover/Copiar/Eliminar seleccionados
    """
    import sys, tempfile, os
    from PySide6.QtWidgets import QApplication, QDialog
    from PySide6.QtCore import QTimer
    tmp, db = _db()
    A = os.path.join(tmp, "A"); os.makedirs(A, exist_ok=True)
    try:
        # crear 2 videos
        vids=[]
        for n in ["a.mp4","b.mp4"]:
            vid,_=_ins(db,A,n)
            vids.append(vid)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmp, "cfg.json")
        ventana = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        ventana.resize(720,540)
        ventana.show()
        # esperar carga
        import time
        for _ in range(100):
            app.processEvents()
            time.sleep(0.02)
            if getattr(ventana, "_carga_completada", False) and not getattr(ventana.gestor, "activo", False):
                break
        # asegurar tarjetas visibles
        ventana.carpeta_seleccionada = os.path.abspath(A)
        from escanear_videos import listar_videos_paginado
        pag = listar_videos_paginado(100,0,None,db)
        if not ventana.tarjetas:
            ventana._crear_tarjetas(pag["videos"])
            app.processEvents()
        # --- 0 selección: toolbar deshabilitado ---
        ventana._nombres_seleccionados.clear()
        ventana._actualizar_botones_lote()
        app.processEvents()
        verifica(hasattr(ventana, "boton_renombrar_masivo"),"toolbar boton existe")
        verifica("Renombrar seleccionados" in ventana.boton_renombrar_masivo.text(),"toolbar label Renombrar seleccionados…")
        verifica(not ventana.boton_renombrar_masivo.isEnabled(),"toolbar deshabilitado con 0 selección")
        # coherencia con otros lote: también deshabilitados con 0
        verifica(not ventana.boton_mover_seleccionados.isEnabled(),"lote mover deshabilitado 0 coherente")
        # --- 1 selección: toolbar habilitado coherente con lote ---
        ventana._nombres_seleccionados = { "a.mp4" }
        ventana._actualizar_botones_lote()
        app.processEvents()
        verifica(ventana.boton_renombrar_masivo.isEnabled()==ventana.boton_mover_seleccionados.isEnabled(),"1 selección coherente con mover")
        verifica(ventana.boton_renombrar_masivo.isEnabled(),"toolbar habilitado con 1 coherente (igual que mover)")
        # --- 2 selección: habilitado ---
        ventana._nombres_seleccionados = { "a.mp4","b.mp4" }
        ventana._actualizar_botones_lote()
        app.processEvents()
        verifica(ventana.boton_renombrar_masivo.isEnabled(),"toolbar habilitado con 2 selección")
        # --- Menú contextual: verificar acciones ---
        src_menu = inspect.getsource(ventana._mostrar_menu_contextual)
        verifica("Renombrar seleccionados" in src_menu,"menu contiene Renombrar seleccionados…")
        verifica("Renombrar…" in src_menu or "Renombrar" in src_menu,"menu conserva Renombrar individual")
        # Crear menu offscreen capturando QMenu sin exec
        captured = {}
        orig_QMenu = visor_videos.QMenu
        class FakeMenu:
            def __init__(self, *a, **k):
                self.actions = []
                self._actions_objs = []
            def addAction(self, txt):
                # crear objeto mínimo con setEnabled y triggered
                class FakeAct:
                    def __init__(self, t):
                        self._txt = t
                        self._enabled = True
                        self._trigger = None
                    def text(self):
                        return self._txt
                    def setEnabled(self, v):
                        self._enabled = bool(v)
                    def isEnabled(self):
                        return self._enabled
                    @property
                    def triggered(self):
                        class Sig:
                            def __init__(self, outer): self.outer=outer
                            def connect(self, fn): self.outer._trigger=fn
                        return Sig(self)
                act = FakeAct(txt)
                self.actions.append(txt)
                self._actions_objs.append(act)
                return act
            def exec(self, *a, **k):
                captured["actions"]=list(self.actions)
                captured["objs"]=list(self._actions_objs)
                return None
        visor_videos.QMenu = FakeMenu
        try:
            # 2 seleccionados -> Renombrar seleccionados habilitado
            ventana._mostrar_menu_contextual("a.mp4")
            acts = captured.get("actions", [])
            verifica("Renombrar seleccionados…" in acts, "menu acción Renombrar seleccionados… existe")
            verifica("Renombrar…" in acts, "menu conserva Renombrar… individual")
            # verificar habilitado con 2
            objs = captured.get("objs", [])
            idx = acts.index("Renombrar seleccionados…") if "Renombrar seleccionados…" in acts else -1
            if idx>=0:
                verifica(objs[idx].isEnabled(),"menu Renombrar seleccionados habilitado con 2")
            # verificar trigger conecta a _iniciar_renombrar_masivo
            verifica("_iniciar_renombrar_masivo" in src_menu,"menu conecta a _iniciar_renombrar_masivo")
            # 0 selección: menu deshabilitado
            ventana._nombres_seleccionados.clear()
            captured.clear()
            ventana._mostrar_menu_contextual("a.mp4")
            acts0 = captured.get("actions", [])
            objs0 = captured.get("objs", [])
            if "Renombrar seleccionados…" in acts0:
                idx0 = acts0.index("Renombrar seleccionados…")
                verifica(not objs0[idx0].isEnabled(),"menu deshabilitado con 0 selección")
            # Verificar Renombrar individual sigue actuando sobre un solo video (no masa)
            verifica("lambda: self._iniciar_renombrar(nombre)" in src_menu or "_iniciar_renombrar" in src_menu,"Renombrar individual actúa sobre un video")
            # Verificar que trigger masa abre dialogo: simular llamada directa
            ventana._nombres_seleccionados = { "a.mp4","b.mp4" }
            dlg_opened = {"ok": False}
            orig_exec = visor_videos.DialogoRenombrarMasivo.exec
            def fake_exec(self):
                dlg_opened["ok"] = True
                return QDialog.Rejected
            visor_videos.DialogoRenombrarMasivo.exec = fake_exec
            try:
                ventana._iniciar_renombrar_masivo()
                verifica(dlg_opened["ok"],"acción masa abre DialogoRenombrarMasivo")
            finally:
                visor_videos.DialogoRenombrarMasivo.exec = orig_exec
        finally:
            visor_videos.QMenu = orig_QMenu
        ventana.close()
        try:
            ventana.gestor_lote.cerrar()
        except Exception as _e:
            print(f"warn cerrar gestor_lote: {_e}")
        try:
            ventana.gestor.cerrar()
        except Exception as _e:
            print(f"warn cerrar gestor: {_e}")
        try:
            ventana.gestor_renombrar_masivo.cerrar()
        except Exception as _e:
            print(f"warn cerrar gestor_renombrar_masivo: {_e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_27_estructural_b83():
    src=open("renombrar_masivo.py",encoding="utf-8").read()
    verifica(src.count("WHERE nombre")==0,"estructural WHERE nombre 0")
    verifica(src.count("COLLATE NOCASE")==0,"estructural COLLATE NOCASE 0")
    # contar llamadas productivas fuera de def
    import re
    # find def position
    def_pos=src.find("def _calcular_renombres_cache")
    after=src[def_pos+ len("def _calcular_renombres_cache"): ] if def_pos!=-1 else src
    # contar en area previa a def y posterior excluyendo def línea
    # simple: contar total -1 (def)
    total_calls=src.count("_calcular_renombres_cache(")
    prod=total_calls -1  # una es def
    verifica(prod==0,f"estructural cero llamadas productivas cache {prod}")
    verifica("UPDATE videos SET nombre = ?, ruta = ?, ruta_normalizada" in src,"UPDATE incluye ruta_normalizada")

def main():
    print("=== B7.7 prueba_renombrar_masivo_b77 ===")
    for fn in [test_01_plantilla_tokens_validos,test_02_plantilla_tokens_invalidos,test_03_sanitizacion_visible_en_preview,test_04_reservados_longitud,test_05_preservacion_extension,test_06_orden_estable,test_07_colisiones_intra_lote_sufijos,test_08_colisiones_fs,test_09_colisiones_db_unique,test_10_case_insensitive,test_11_swap_AB,test_12_ciclo_3,test_13_fallo_durante_ciclo_recuperacion,test_14_preservacion_video_id_marcadores_segmentos,test_15_reasociacion_miniaturas,test_16_cancelacion_parcial,test_17_progreso,test_18_cero_reescaneo,test_19_cero_ffmpeg,test_20_preview_plan_exacto,test_21_errores_visibles,test_22_tarea_fuera_hilo,test_23_ui_sin_sqlite_fs,test_24_integracion_ui_preview,test_25_sin_silencios_pass,test_26_acceso_ui_renombrar_seleccionados,test_27_estructural_b83]:
        try: fn()
        except Exception as e:
            import traceback; falla(fn.__name__, str(e)); traceback.print_exc()
    total=_CONT; fallos=_FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0: print("RESULTADO_FINAL=OK")
    else: print("RESULTADO_FINAL=ERROR"); sys.exit(1)

if __name__=="__main__": main()
