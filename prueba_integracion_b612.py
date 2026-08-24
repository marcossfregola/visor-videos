"""Suite integrada B6.12 — validacion cruzada (filtro/orden/paginacion + resumen + export + lote + secuencia + derivados + migraciones).

Toda DB/video/fixture vive bajo C:\\prueba\\_tmp_b612_integracion y se elimina en finally.
No toca datos reales. Requiere FFmpeg/FFprobe para export real; si no disponible, esos casos hacen skip OK.
Cubre 14 casos:
 1 filtro marcador/color+orden+paginacion
 2 segmento Sin clasificar+orden+paginacion
 3 resumen colapsado batch
 4 export individual real FFmpeg/FFprobe+naming+alta/trazabilidad
 5 lote por color+colisiones+parciales
 6 secuencia ordenada+trazabilidad exacta
 7 cancelacion sin temporales/trazabilidad falsa
 8 derivado fuera de raiz
 9 persistencia/snapshot historico (original eliminado)
10 bloqueo derivado-de-derivado
11 UNIQUE(nombre)/catalog_error
12 migraciones idempotentes+PRAGMA integrity_check
13 filtro texto+color AND + paginacion determinista
14 derivado eliminado fisicamente historica persiste
"""
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
import json

import escanear_videos as ev
import exportar_segmento as exp
import exportar_secuencia as seq
import tareas_videos as tv
import nombres

BASE = r"C:\prueba\_tmp_b612_integracion"

_ARGS_SIN_CONSOLA = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {})

def _ffmpeg_disponible():
    return shutil.which("ffmpeg") is not None

def _hash_archivo(ruta):
    h=hashlib.sha256()
    with open(ruta,"rb") as f:
        for c in iter(lambda: f.read(8192),b""):
            h.update(c)
    return h.hexdigest()

def _ffprobe_json(ruta):
    r=subprocess.run(["ffprobe","-v","error","-print_format","json","-show_format","-show_streams",ruta],capture_output=True,text=True,timeout=10,**_ARGS_SIN_CONSOLA)
    if r.returncode!=0:
        return None
    return json.loads(r.stdout)

def _generar_video(ruta,duracion=4.0,fps=30):
    cmd=["ffmpeg","-y","-f","lavfi","-i",f"testsrc=size=320x240:rate={fps}:duration={duracion}","-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100","-c:v","libx264","-pix_fmt","yuv420p","-preset","veryfast","-crf","23","-c:a","aac","-b:a","64k","-t",str(duracion),ruta]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=20,**_ARGS_SIN_CONSOLA)
    return r.returncode==0 and os.path.isfile(ruta)

def _asegurar_base():
    os.makedirs(BASE,exist_ok=True)

def _crear_db_legacy_solo_videos(db_path,nombre="viejo.mp4",ruta="/tmp/viejo.mp4"):
    conn=sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL UNIQUE,ruta TEXT NOT NULL,extension TEXT NOT NULL,fecha_importacion TEXT NOT NULL)")
    conn.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion) VALUES (?,?,?,?)",(nombre,ruta,".mp4","2020-01-01T00:00:00"))
    conn.commit()
    conn.close()

def _insertar_video_catalogado(db_path,video_ruta,nombre=None):
    conn=ev.conectar_bd(db_path)
    try:
        datos=ev.obtener_datos_ffprobe(video_ruta)
        if datos is None:
            raise RuntimeError("ffprobe fallo")
        st=os.stat(video_ruta)
        if nombre is None:
            nombre=os.path.basename(video_ruta)
        ext=os.path.splitext(nombre)[1].lower()
        registro={"nombre":nombre,"ruta":os.path.abspath(video_ruta),"extension":ext,"fecha_importacion":"2026-01-01T00:00:00","duracion_segundos":float(datos["duracion_segundos"]),"ancho":datos["ancho"],"alto":datos["alto"],"codec_video":datos["codec_video"],"cantidad_miniaturas":0,"tamano_bytes":st.st_size,"mtime_ns":st.st_mtime_ns}
        ev._asegurar_columnas_videos(conn)
        ev._upsert_video(conn,registro)
        conn.commit()
        fila=conn.execute("SELECT id FROM videos WHERE nombre=?",(nombre,)).fetchone()
        return fila[0] if fila else None
    finally:
        conn.close()

def _insertar_segmento(db_path,video_id,inicio,fin,color=None):
    conn=sqlite3.connect(db_path)
    ev._asegurar_tablas_derivados(conn)
    try:
        ev._asegurar_tabla_segmentos(conn)
    except Exception:
        pass
    # asegurar columna color ya existente
    cur=conn.execute("INSERT INTO segmentos_video (video_id,inicio,fin,color) VALUES (?,?,?,?)",(video_id,float(inicio),float(fin),color))
    sid=cur.lastrowid
    conn.commit()
    conn.close()
    return sid

def _insertar_marcador(db_path,video_id,tiempo,color=None):
    return ev.guardar_marcador(video_id,tiempo,db_path,color=color)

def _video_id_por_nombre(db_path,nombre):
    conn=sqlite3.connect(db_path)
    fila=conn.execute("SELECT id FROM videos WHERE nombre=?",(nombre,)).fetchone()
    conn.close()
    return fila[0] if fila else None

# ---------------------------------------------------------------------------
def test_01_filtro_marcador_color_orden_paginacion():
    """Filtro marcador/color+orden+paginacion: marcador:rojo con orden duracion y paginacion sin duplicados."""
    tmp=os.path.join(BASE,"t01_filtro_marcador")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    if os.path.exists(db):
        os.remove(db)
    conn=ev.conectar_bd(db)
    conn.close()
    # crear 6 videos con duraciones distintas
    vdir=os.path.join(tmp,"videos")
    os.makedirs(vdir,exist_ok=True)
    nombres=[]
    for i,name in enumerate(["a.mp4","b.mp4","c.mp4","d.mp4","e.mp4","f.mp4"]):
        ruta=os.path.join(vdir,name)
        if not _generar_video(ruta,duracion=2+i*0.5):
            return False, f"gen {name} fail"
        vid=_insertar_video_catalogado(db,ruta)
        nombres.append((name,vid))
    # marcar: a rojo, b rojo, c azul, resto sin marcador
    _insertar_marcador(db,nombres[0][1],1.0,color="rojo")
    _insertar_marcador(db,nombres[1][1],1.0,color="rojo")
    _insertar_marcador(db,nombres[2][1],1.0,color="azul")
    # filtro marcador:rojo debe dar 2 con orden duracion asc
    r=ev.listar_videos_paginado(100,0,None,db,filtro="marcador:rojo",orden_clave="duracion",orden_direccion="asc")
    if r["total"]!=2:
        return False, f"marcador:rojo total {r['total']} !=2 {r['videos']}"
    got=[x[0] for x in r["videos"]]
    if set(got)!= {"a.mp4","b.mp4"}:
        return False, f"marcador:rojo got {got}"
    # paginacion de 1 en 1 debe mantener orden y sin duplicados
    todos=[]
    disp=0
    while True:
        pg=ev.listar_videos_paginado(1,disp,None,db,filtro="marcador:rojo",orden_clave="duracion",orden_direccion="asc")
        if not pg["videos"]:
            break
        todos.extend([x[0] for x in pg["videos"]])
        disp+=1
        if pg["total"]!=2:
            return False, "total variable en paginacion"
    if len(todos)!=len(set(todos)) or len(todos)!=2:
        return False, f"paginacion duplicados {todos}"
    if todos!=got:
        return False, f"paginacion orden no determinista {todos} vs {got}"
    return True, f"filtro marcador/color+orden+paginacion OK {got} pag {todos}"

def test_02_segmento_sin_clasificar_orden_paginacion():
    """Segmento Sin clasificar+orden+paginacion: color IS NULL con orden nombre asc."""
    tmp=os.path.join(BASE,"t02_sin_clasificar")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    if os.path.exists(db):
        os.remove(db)
    ev.conectar_bd(db).close()
    vdir=os.path.join(tmp,"videos")
    os.makedirs(vdir,exist_ok=True)
    vids=[]
    for name,color in [("seg_null.mp4",None),("seg_rojo.mp4","rojo"),("seg_azul.mp4","azul"),("seg_null2.mp4",None)]:
        ruta=os.path.join(vdir,name)
        if not _generar_video(ruta,duracion=2):
            return False, f"gen {name} fail"
        vid=_insertar_video_catalogado(db,ruta)
        vids.append((name,vid,color))
        _insertar_segmento(db,vid,0.5,1.0,color=color)
    r=ev.listar_videos_paginado(100,0,None,db,filtro="segmento:sin_clasificar",orden_clave="nombre",orden_direccion="asc")
    if r["total"]!=2:
        return False, f"sin_clasificar total {r['total']} !=2 got {[x[0] for x in r['videos']]}"
    got=[x[0] for x in r["videos"]]
    if set(got)!= {"seg_null.mp4","seg_null2.mp4"}:
        return False, f"sin clasificar got {got}"
    # paginacion
    todos=[]
    disp=0
    while True:
        pg=ev.listar_videos_paginado(1,disp,None,db,filtro="segmento:sin_clasificar",orden_clave="nombre",orden_direccion="asc")
        if not pg["videos"]:
            break
        todos.extend([x[0] for x in pg["videos"]])
        disp+=1
    if todos!=sorted(todos):
        return False, f"orden paginacion no asc {todos}"
    if todos!=got:
        return False, f"paginacion vs full {todos} vs {got}"
    return True, f"segmento Sin clasificar+orden+paginacion OK {got}"

def test_03_resumen_colapsado():
    """Resumen colapsado batch: marcadores y segmentos en una sola tarea por lote."""
    tmp=os.path.join(BASE,"t03_resumen")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    vdir=os.path.join(tmp,"videos")
    os.makedirs(vdir,exist_ok=True)
    vids=[]
    for name in ["r1.mp4","r2.mp4","r3.mp4"]:
        ruta=os.path.join(vdir,name)
        if not _generar_video(ruta,duracion=3):
            return False, f"gen {name} fail"
        vid=_insertar_video_catalogado(db,ruta)
        vids.append(vid)
        _insertar_marcador(db,vid,1.0,color=None)
        _insertar_marcador(db,vid,2.0,color="verde")
        _insertar_segmento(db,vid,0.5,1.5,color=None)
        _insertar_segmento(db,vid,2.0,2.5,color="rojo")
    # tarea batch resumen
    tarea=tv.TareaResumenColapsado(vids,ruta_db=db)
    res=tarea._trabajo()
    if len(res["marcadores"])!=6:
        return False, f"marcadores batch {len(res['marcadores'])} !=6"
    if len(res["segmentos"])!=6:
        return False, f"segmentos batch {len(res['segmentos'])} !=6"
    # verificar colores NULL preservados
    nulls_m=sum(1 for m in res["marcadores"] if m[3] is None)
    if nulls_m!=3:
        return False, f"null marcadores {nulls_m} !=3"
    nulls_s=sum(1 for s in res["segmentos"] if s[4] is None)
    if nulls_s!=3:
        return False, f"null segmentos {nulls_s} !=3"
    # debe ser una sola tarea (ya lo es) y sin pixmaps
    for m in res["marcadores"]:
        if len(m)!=4:
            return False, f"marcador con pixmap? {m}"
    return True, f"resumen colapsado batch OK {len(res['marcadores'])} marc {len(res['segmentos'])} seg"

def test_04_export_individual_real():
    """Export individual real FFmpeg/FFprobe+naming+alta/trazabilidad."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg no disponible skip"
    tmp=os.path.join(BASE,"t04_individual")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=6):
        return False, "gen orig fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,1.5,3.7,color="rojo")
    # naming via motor
    sugerido=nombres.generar_sugerencia_exportacion(os.path.basename(orig),1.5,3.7,extension=".mp4")
    if sugerido!="orig_segmento_1.50-3.70.mp4":
        return False, f"naming {sugerido!r} != 'orig_segmento_1.50-3.70.mp4'"
    dest=os.path.join(tmp,sugerido)
    res=exp.exportar_segmento(orig,1.5,3.7,dest)
    if not res.get("ok"):
        return False, f"export fail {res.get('error')}"
    if not os.path.isfile(dest):
        return False, "dest no existe"
    info=_ffprobe_json(dest)
    if info is None:
        return False, "ffprobe dest fail"
    dur=float(info["format"]["duration"])
    if abs(dur-2.2) > exp.TOLERANCIA_DURACION_EXPORT+0.05:
        return False, f"dur {dur} vs 2.2"
    # alta trazabilidad
    alta=ev.incorporar_video_derivado_al_catalogo(dest,vid,[{"segmento_id":sid,"inicio":1.5,"fin":3.7}],tipo="individual",ruta_db=db)
    if not alta.get("ok"):
        return False, f"alta fail {alta.get('error')}"
    traza=ev.obtener_derivacion_por_derivado(alta["derivado_video_id"],ruta_db=db)
    if traza is None or traza["derivacion"]["original_video_id"]!=vid:
        return False, f"traza {traza}"
    if len(traza["segmentos"])!=1 or traza["segmentos"][0][2]!=sid:
        return False, f"segmento trazado {traza['segmentos']}"
    tmp_files=[f for f in os.listdir(tmp) if ".tmp" in f]
    if tmp_files:
        return False, f"temporales huerfanos {tmp_files}"
    return True, f"individual FFmpeg/FFprobe+naming+alta OK {sugerido} dur {dur:.2f}"

def test_05_lote_por_color_colisiones_parciales():
    """Lote por color+colisiones+parciales: color rojo, colisiones FS/intra-lote, fallo intermedio conserva exitos."""
    tmp=os.path.join(BASE,"t05_lote")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    vdir=os.path.join(tmp,"videos")
    os.makedirs(vdir,exist_ok=True)
    orig=os.path.join(vdir,"orig.mp4")
    if not _generar_video(orig,duracion=6):
        return False, "gen orig fail"
    vid=_insertar_video_catalogado(db,orig)
    # segmentos: 2 rojos con mismo inicio/fin (colision intra-lote), 1 azul, 1 sin clasificar
    sid1=_insertar_segmento(db,vid,0.5,1.0,color="rojo")
    sid2=_insertar_segmento(db,vid,0.5,1.0,color="rojo")
    sid3=_insertar_segmento(db,vid,1.5,2.0,color="azul")
    sid4=_insertar_segmento(db,vid,2.5,3.0,color=None)
    # lote por color rojo debe dar 2
    filas=ev.listar_segmentos_por_videos([vid],color="rojo",ruta_db=db)
    if len(filas)!=2:
        return False, f"lote rojo filas {len(filas)} !=2"
    dest_dir=os.path.join(tmp,"lote_out")
    os.makedirs(dest_dir,exist_ok=True)
    # crear colision FS: preexistente que colisiona con primer nombre
    # nombre base para orig.mp4 0.5-1.0 => orig_segmento_0.50-1.00.mp4
    col=os.path.join(dest_dir,"orig_segmento_0.50-1.00.mp4")
    open(col,"wb").write(b"exist")
    # construir items: 2 rojos + 1 con origen faltante para parcial
    items=[
        {"segmento_id":sid1,"video_id":vid,"ruta_fuente":orig,"nombre_original":os.path.basename(orig),"inicio":0.5,"fin":1.0,"color":"rojo"},
        {"segmento_id":sid2,"video_id":vid,"ruta_fuente":orig,"nombre_original":os.path.basename(orig),"inicio":0.5,"fin":1.0,"color":"rojo"},
        {"segmento_id":9999,"video_id":vid,"ruta_fuente":os.path.join(tmp,"no_existe.mp4"),"nombre_original":os.path.basename(orig),"inicio":2.5,"fin":3.0,"color":None},
    ]
    tarea=tv.TareaExportarLoteSegmentos(dest_dir,items=items,ruta_db=db)
    res=tarea._trabajo()
    if len(res["exitos"])!=2:
        return False, f"lote exitos {len(res['exitos'])} !=2 {res}"
    nombres_dest=sorted([os.path.basename(e["destino"]) for e in res["exitos"]])
    if "orig_segmento_0.50-1.00.mp4" in nombres_dest:
        return False, f"colision FS no resuelta {nombres_dest}"
    if nombres_dest[0]==nombres_dest[1]:
        return False, f"colision intra-lote no resuelta {nombres_dest}"
    if len(res["fallos"])!=1:
        return False, f"fallos parcial {len(res['fallos'])} !=1"
    for e in res["exitos"]:
        if not os.path.isfile(e["destino"]):
            return False, f"exito borrado {e['destino']}"
        if _ffprobe_json(e["destino"]) is None:
            return False, f"ffprobe lote {e['destino']} fail"
        if e.get("alta_catalogo") is None or not e["alta_catalogo"].get("ok"):
            return False, f"alta lote faltante {e}"
    if open(col,"rb").read()!=b"exist":
        return False, "colision FS sobrescrita"
    return True, f"lote por color+colisiones+parciales OK {nombres_dest} fallos {len(res['fallos'])}"

def test_06_secuencia_ordenada_trazabilidad():
    """Secuencia ordenada+trazabilidad exacta: orden explicito preservado en DB."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t06_secuencia")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=8):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid1=_insertar_segmento(db,vid,0.5,1.5)
    sid2=_insertar_segmento(db,vid,3.0,4.0)
    sid3=_insertar_segmento(db,vid,5.0,6.0)
    segs=[(3.0,4.0),(0.5,1.5),(5.0,6.0)]
    info_orden=[{"segmento_id":sid2,"inicio":3.0,"fin":4.0},{"segmento_id":sid1,"inicio":0.5,"fin":1.5},{"segmento_id":sid3,"inicio":5.0,"fin":6.0}]
    dst=os.path.join(tmp,"seq.mp4")
    tarea=tv.TareaExportarSecuencia(orig,segs,dst,original_video_id=vid,segmentos_info_orden=info_orden,ruta_db=db)
    res=tarea._trabajo()
    if not res.get("ok"):
        return False, f"seq fail {res.get('error')}"
    if not os.path.isfile(dst):
        return False, "dst no existe"
    info=_ffprobe_json(dst)
    if info is None:
        return False, "ffprobe seq fail"
    dur=float(info["format"]["duration"])
    esperado=sum(b-a for a,b in segs)
    if abs(dur-esperado) > seq.TOLERANCIA_DURACION_EXPORT+0.1:
        return False, f"dur {dur} vs {esperado}"
    alta=res.get("alta_catalogo")
    if not alta or not alta.get("ok"):
        return False, f"alta seq fail {alta}"
    traza=ev.obtener_derivacion_por_derivado(alta["derivado_video_id"],ruta_db=db)
    if len(traza["segmentos"])!=3:
        return False, f"segs len {len(traza['segmentos'])}"
    for idx,(exp_sid,exp_ini,exp_fin) in enumerate([(sid2,3.0,4.0),(sid1,0.5,1.5),(sid3,5.0,6.0)]):
        row=traza["segmentos"][idx]
        if row[2]!=exp_sid or row[3]!=idx or abs(row[4]-exp_ini)>1e-6 or abs(row[5]-exp_fin)>1e-6:
            return False, f"orden mismatch idx {idx} row {row} vs exp {(exp_sid,idx,exp_ini,exp_fin)}"
    tmp_files=[f for f in os.listdir(tmp) if ".tmp" in f]
    if tmp_files:
        return False, f"temporales {tmp_files}"
    return True, f"secuencia ordenada+trazabilidad OK dur {dur:.2f}"

def test_07_cancelacion_sin_temporales():
    """Cancelacion sin temporales/trazabilidad falsa: FFmpeg terminado, sin archivo ni relacion."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t07_cancel")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    # video grande 720p 15s para ventana cancelacion
    cmd=["ffmpeg","-y","-f","lavfi","-i","testsrc=size=1280x720:rate=30:duration=15","-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100","-c:v","libx264","-pix_fmt","yuv420p","-preset","veryfast","-crf","18","-c:a","aac","-t","15",orig]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=20,**_ARGS_SIN_CONSOLA)
    if r.returncode!=0 or not os.path.isfile(orig):
        if not _generar_video(orig,duracion=15):
            return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0,14)
    from tareas import GestorTareas
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication(sys.argv)
    dst=os.path.join(tmp,"cancel.mp4")
    tarea=tv.TareaExportarSegmento(orig,0,14,dst,original_video_id=vid,segmento_id=sid,ruta_db=db)
    gestor=GestorTareas()
    if not gestor.iniciar(tarea):
        return False, "no inicio"
    time.sleep(0.2)
    tarea.cancelar()
    fin=time.monotonic()+10
    while time.monotonic()<fin:
        app.processEvents()
        if not gestor.activo:
            break
        time.sleep(0.02)
    time.sleep(0.5)
    if gestor.activo:
        return False, "gestor sigue activo"
    if os.path.exists(dst):
        return False, "dst existe tras cancel"
    tmp_h=[f for f in os.listdir(tmp) if ".tmp" in f]
    if tmp_h:
        return False, f"temporales huerfanos {tmp_h}"
    # sin trazabilidad falsa
    conn=sqlite3.connect(db)
    fila=conn.execute("SELECT id FROM videos WHERE nombre=?",(os.path.basename(dst),)).fetchone()
    conn.close()
    if fila is not None:
        return False, "video sin relacion tras cancel"
    # contar derivaciones debe ser 0
    conn2=sqlite3.connect(db)
    try:
        c=conn2.execute("SELECT COUNT(*) FROM videos_derivados").fetchone()[0]
    except:
        c=0
    conn2.close()
    if c!=0:
        return False, f"derivaciones {c} !=0 tras cancel"
    gestor.cerrar()
    return True, "cancelacion sin temporales/trazabilidad falsa OK"

def test_08_derivado_fuera_raiz():
    """Derivado fuera de raiz: export a directorio distinto al original y alta incremental."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t08_fuera")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig_dir=os.path.join(tmp,"originales")
    fuera_dir=os.path.join(tmp,"fuera_raiz")
    os.makedirs(orig_dir,exist_ok=True)
    os.makedirs(fuera_dir,exist_ok=True)
    orig=os.path.join(orig_dir,"base.mp4")
    if not _generar_video(orig,duracion=4):
        return False, "gen orig fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0.5,1.5)
    derivado=os.path.join(fuera_dir,"derivado_fuera.mp4")
    res=exp.exportar_segmento(orig,0.5,1.5,derivado)
    if not res.get("ok") or not os.path.isfile(derivado):
        return False, f"export fail {res.get('error')}"
    info=_ffprobe_json(derivado)
    if info is None:
        return False, "ffprobe fuera fail"
    alta=ev.incorporar_video_derivado_al_catalogo(derivado,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if not alta.get("ok"):
        return False, f"alta fuera fail {alta.get('error')}"
    traza=ev.obtener_derivacion_por_derivado(alta["derivado_video_id"],ruta_db=db)
    if traza is None or traza["derivacion"]["original_video_id"]!=vid:
        return False, f"traza fuera {traza}"
    if not os.path.isfile(derivado):
        return False, "derivado borrado"
    return True, f"derivado fuera de raiz OK {alta['derivado_video_id']} FFprobe {info['streams'][0]['codec_name']}"

def test_09_persistencia_snapshot():
    """Persistencia/snapshot historico: original eliminado, trazabilidad conserva nombre/ruta y segmentos."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t09_snapshot")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=4):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0.5,1.5)
    conn=sqlite3.connect(db)
    orig_row=conn.execute("SELECT nombre,ruta FROM videos WHERE id=?",(vid,)).fetchone()
    conn.close()
    der=os.path.join(tmp,"der.mp4")
    res=exp.exportar_segmento(orig,0.5,1.5,der)
    if not res.get("ok"):
        return False, f"export fail {res.get('error')}"
    alta=ev.incorporar_video_derivado_al_catalogo(der,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if not alta.get("ok"):
        return False, f"alta fail {alta.get('error')}"
    der_vid=alta["derivado_video_id"]
    deriv_id=alta["derivacion_id"]
    conn=sqlite3.connect(db)
    conn.execute("DELETE FROM videos WHERE id=?",(vid,))
    conn.commit()
    conn.close()
    traza=ev.obtener_derivacion_por_derivado(der_vid,ruta_db=db)
    if traza is None:
        return False, "traza perdida"
    if traza["derivacion"]["original_nombre"]!=orig_row[0] or traza["derivacion"]["original_ruta"]!=os.path.abspath(orig):
        return False, f"snapshot perdido {traza['derivacion']} vs {orig_row}"
    if traza["derivacion"]["id"]!=deriv_id:
        return False, "derivacion_id cambio"
    if len(traza["segmentos"])!=1 or traza["segmentos"][0][2]!=sid:
        return False, f"segmentos perdidos {traza['segmentos']}"
    listado=ev.listar_derivaciones_por_original(vid,ruta_db=db)
    if len(listado)!=1:
        return False, f"listado tras borrar {listado}"
    return True, f"persistencia/snapshot OK {orig_row}"

def test_10_bloqueo_derivado_de_derivado():
    """Bloqueo derivado-de-derivado: original que ya es derivado no puede ser padre."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t10_derder")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=4):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0.5,1.0)
    der1=os.path.join(tmp,"der1.mp4")
    res=exp.exportar_segmento(orig,0.5,1.0,der1)
    if not res.get("ok"):
        return False, f"export fail {res.get('error')}"
    alta1=ev.incorporar_video_derivado_al_catalogo(der1,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.0}],tipo="individual",ruta_db=db)
    if not alta1.get("ok"):
        return False, f"alta1 fail {alta1.get('error')}"
    der_vid=alta1["derivado_video_id"]
    sid_der=_insertar_segmento(db,der_vid,0.2,0.6)
    der2=os.path.join(tmp,"der2.mp4")
    if not _generar_video(der2,duracion=2):
        return False, "gen der2 fail"
    alta2=ev.incorporar_video_derivado_al_catalogo(der2,der_vid,[{"segmento_id":sid_der,"inicio":0.2,"fin":0.6}],tipo="individual",ruta_db=db)
    if alta2.get("ok"):
        return False, "derivado-de-derivado deberia bloqueado"
    if "derivado-de-derivado" not in (alta2.get("error") or "").lower() and "bloqueado" not in (alta2.get("error") or "").lower():
        return False, f"error no indica bloqueo {alta2.get('error')}"
    if not os.path.isfile(der2):
        return False, "der2 borrado"
    conn=sqlite3.connect(db)
    try:
        c=conn.execute("SELECT COUNT(*) FROM videos_derivados").fetchone()[0]
    except:
        c=0
    conn.close()
    if c!=1:
        return False, f"derivaciones {c} !=1"
    return True, "bloqueo derivado-de-derivado OK"

def test_11_unique_catalog_error():
    """B8.3 UNIQUE(ruta_normalizada): misma ruta rechaza con catalog_error, distinta ruta mismo nombre ahora PERMITIDO (homónimo)."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t11_unique")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=4):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0.5,1.5)
    der1=os.path.join(tmp,"dup.mp4")
    res1=exp.exportar_segmento(orig,0.5,1.5,der1)
    if not res1.get("ok"):
        return False, f"export1 fail {res1.get('error')}"
    alta1=ev.incorporar_video_derivado_al_catalogo(der1,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if not alta1.get("ok"):
        return False, f"alta1 fail {alta1.get('error')}"
    # misma ruta debe fallar
    alta2=ev.incorporar_video_derivado_al_catalogo(der1,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if alta2.get("ok"):
        return False, "misma ruta deberia fallar"
    if not alta2.get("catalog_error"):
        return False, f"catalog_error false misma ruta {alta2}"
    if not os.path.isfile(der1):
        return False, "der1 borrado"
    # distinta ruta mismo nombre B8.3: debe PERMITIRSE (homónimo) — antes fallaba con UNIQUE(nombre)
    otro_dir=os.path.join(tmp,"otro")
    os.makedirs(otro_dir,exist_ok=True)
    der2=os.path.join(otro_dir,"dup.mp4")
    if not _generar_video(der2,duracion=2):
        return False, "gen der2 fail"
    alta3=ev.incorporar_video_derivado_al_catalogo(der2,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if not alta3.get("ok"):
        return False, f"B8.3 homónimo distinta ruta mismo nombre debería permitir, got {alta3}"
    if alta3.get("catalog_error"):
        return False, f"catalog_error inesperado para homónimo permitido {alta3}"
    if not os.path.isfile(der2):
        return False, "der2 borrado"
    # verificar que ambos homónimos coexisten con ids distintos
    if alta1["derivado_video_id"] == alta3["derivado_video_id"]:
        return False, "ids homónimos no deben colisionar"
    return True, "B8.3 homónimo permitido, misma ruta rechaza OK"

def test_12_migraciones_idempotentes_integrity():
    """Migraciones idempotentes+PRAGMA integrity_check: 3 aperturas, datos intactos, integrity ok."""
    tmp=os.path.join(BASE,"t12_mig")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"idem.db")
    if os.path.exists(db):
        os.remove(db)
    # legacy solo videos
    _crear_db_legacy_solo_videos(db,nombre="viejo.mp4",ruta=r"C:\prueba\videos\viejo.mp4")
    # 1ra migracion via conectar_bd
    conn1=ev.conectar_bd(db)
    conn1.close()
    # insertar via catalogado tras migracion
    vdir=os.path.join(tmp,"src")
    os.makedirs(vdir,exist_ok=True)
    src=os.path.join(vdir,"orig.mp4")
    if not _generar_video(src,duracion=2):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,src)
    if not vid:
        return False, "insert fail"
    # 2da y 3ra migracion
    conn2=ev.conectar_bd(db)
    c=conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    if c!=2:  # viejo + orig
        conn2.close()
        return False, f"count tras 2da mig {c} !=2"
    tablas=[r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "videos_derivados" not in tablas or "videos_derivados_segmentos" not in tablas:
        conn2.close()
        return False, f"tablas faltan {tablas}"
    conn2.close()
    conn3=ev.conectar_bd(db)
    conn3.close()
    # integrity_check
    conn=sqlite3.connect(db)
    fila=conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    if fila is None or fila[0]!="ok":
        return False, f"integrity_check {fila}"
    # reabrir y verificar datos intactos
    conn4=sqlite3.connect(db)
    fila_viejo=conn4.execute("SELECT nombre FROM videos WHERE nombre='viejo.mp4'").fetchone()
    conn4.close()
    if fila_viejo is None or fila_viejo[0]!="viejo.mp4":
        return False, "viejo perdido tras idempotente"
    return True, "migraciones idempotentes+PRAGMA integrity_check OK"

def test_13_texto_color_and():
    """Filtro texto+color AND con paginacion determinista."""
    tmp=os.path.join(BASE,"t13_texto_color")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    vdir=os.path.join(tmp,"videos")
    os.makedirs(vdir,exist_ok=True)
    # crear 4 videos: manzana.mp4, manzana_verde.mp4, banana.mp4, manzana_roja.mp4
    for name in ["manzana.mp4","manzana_verde.mp4","banana.mp4","manzana_roja.mp4"]:
        ruta=os.path.join(vdir,name)
        if not _generar_video(ruta,duracion=2):
            return False, f"gen {name} fail"
        vid=_insertar_video_catalogado(db,ruta)
        # marcar: manzana y banana con rojo, manzana_verde sin marcador, manzana_roja rojo
        if name in ["manzana.mp4","banana.mp4","manzana_roja.mp4"]:
            _insertar_marcador(db,vid,1.0,color="rojo")
    r=ev.listar_videos_paginado(100,0,"manzana",db,filtro="marcador:rojo",orden_clave="nombre",orden_direccion="asc")
    got=[x[0] for x in r["videos"]]
    if set(got)!= {"manzana.mp4","manzana_roja.mp4"} or r["total"]!=2:
        return False, f"texto+color AND got {got} total {r['total']}"
    # paginacion 1+1 mantiene AND
    pg1=ev.listar_videos_paginado(1,0,"manzana",db,filtro="marcador:rojo",orden_clave="nombre",orden_direccion="asc")
    pg2=ev.listar_videos_paginado(1,1,"manzana",db,filtro="marcador:rojo",orden_clave="nombre",orden_direccion="asc")
    if pg1["total"]!=2 or pg2["total"]!=2:
        return False, "total paginacion AND variable"
    if [pg1["videos"][0][0],pg2["videos"][0][0]]!=got:
        return False, f"paginacion AND orden {pg1} {pg2} vs {got}"
    return True, f"filtro texto+color AND OK {got}"

def test_14_derivado_eliminado_historica():
    """Derivado eliminado fisicamente historica persiste y derivado fuera de raiz ya cubierto."""
    if not _ffmpeg_disponible():
        return True, "ffmpeg skip"
    tmp=os.path.join(BASE,"t14_der_del")
    os.makedirs(tmp,exist_ok=True)
    db=os.path.join(tmp,"db.db")
    ev.conectar_bd(db).close()
    orig=os.path.join(tmp,"orig.mp4")
    if not _generar_video(orig,duracion=4):
        return False, "gen fail"
    vid=_insertar_video_catalogado(db,orig)
    sid=_insertar_segmento(db,vid,0.5,1.5)
    der=os.path.join(tmp,"der.mp4")
    res=exp.exportar_segmento(orig,0.5,1.5,der)
    if not res.get("ok"):
        return False, f"export fail {res.get('error')}"
    alta=ev.incorporar_video_derivado_al_catalogo(der,vid,[{"segmento_id":sid,"inicio":0.5,"fin":1.5}],tipo="individual",ruta_db=db)
    if not alta.get("ok"):
        return False, f"alta fail {alta.get('error')}"
    der_vid=alta["derivado_video_id"]
    os.remove(der)
    conn=sqlite3.connect(db)
    conn.execute("DELETE FROM videos WHERE id=?",(der_vid,))
    conn.commit()
    conn.close()
    traza=ev.obtener_derivacion_por_derivado(der_vid,ruta_db=db)
    if traza is None:
        return False, "historica perdida"
    if traza["derivacion"]["derivado_video_id"]!=der_vid:
        return False, "derivado_vid mismatch"
    if not ev.es_video_derivado(der_vid,ruta_db=db):
        return False, "es_video_derivado false tras borrado"
    return True, "derivado eliminado historica persiste OK"

def main():
    _asegurar_base()
    pruebas=[
        ("filtro marcador/color+orden+paginacion",test_01_filtro_marcador_color_orden_paginacion),
        ("segmento Sin clasificar+orden+paginacion",test_02_segmento_sin_clasificar_orden_paginacion),
        ("resumen colapsado",test_03_resumen_colapsado),
        ("export individual real FFmpeg/FFprobe+naming+alta/trazabilidad",test_04_export_individual_real),
        ("lote por color+colisiones+parciales",test_05_lote_por_color_colisiones_parciales),
        ("secuencia ordenada+trazabilidad exacta",test_06_secuencia_ordenada_trazabilidad),
        ("cancelacion sin temporales/trazabilidad falsa",test_07_cancelacion_sin_temporales),
        ("derivado fuera de raiz",test_08_derivado_fuera_raiz),
        ("persistencia/snapshot historico",test_09_persistencia_snapshot),
        ("bloqueo derivado-de-derivado",test_10_bloqueo_derivado_de_derivado),
        ("UNIQUE(nombre)/catalog_error",test_11_unique_catalog_error),
        ("migraciones idempotentes+PRAGMA integrity_check",test_12_migraciones_idempotentes_integrity),
        ("filtro texto+color AND+paginacion",test_13_texto_color_and),
        ("derivado eliminado historica",test_14_derivado_eliminado_historica),
    ]
    # QApplication para tareas cancelacion
    app=None
    try:
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication(sys.argv)
    except Exception:
        app=None
    resultados=[]
    try:
        for idx,(nombre,fn) in enumerate(pruebas,start=1):
            try:
                ok,detalle=fn()
            except Exception as exc:
                import traceback
                ok,detalle=False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()[:800]}"
            resultados.append((idx,nombre,ok,detalle))
            print(f"P{idx:02d} {'PASS' if ok else 'FAIL'} - {nombre}: {detalle}")
            sys.stdout.flush()
            if app:
                app.processEvents()
            time.sleep(0.05)
        ok_total=all(ok for _,_,ok,_ in resultados)
        aprobadas=sum(1 for _,_,ok,_ in resultados if ok)
        print(f"TOTAL={aprobadas}/{len(pruebas)}")
        print(f"RESULTADO_FINAL={'PASS' if ok_total else 'FAIL'}")
        # evidencia FFmpeg
        try:
            r=subprocess.run(["ffmpeg","-version"],capture_output=True,text=True,timeout=5,**_ARGS_SIN_CONSOLA)
            print(f"FFMPEG={'OK' if r.returncode==0 else 'FAIL'} {r.stdout.splitlines()[0] if r.stdout else ''}")
        except Exception as e:
            print(f"FFMPEG=ERROR {e}")
        try:
            r=subprocess.run(["ffprobe","-version"],capture_output=True,text=True,timeout=5,**_ARGS_SIN_CONSOLA)
            print(f"FFPROBE={'OK' if r.returncode==0 else 'FAIL'} {r.stdout.splitlines()[0] if r.stdout else ''}")
        except Exception as e:
            print(f"FFPROBE=ERROR {e}")
        # integrity_check sobre ultima DB si existe
        try:
            # usar una DB temporal de prueba final
            tmp=os.path.join(BASE,"_final_check")
            os.makedirs(tmp,exist_ok=True)
            db_check=os.path.join(tmp,"check.db")
            conn=ev.conectar_bd(db_check)
            conn.close()
            conn2=sqlite3.connect(db_check)
            fila=conn2.execute("PRAGMA integrity_check").fetchone()
            print(f"INTEGRITY_CHECK={fila[0] if fila else 'UNKNOWN'}")
            conn2.close()
        except Exception as e:
            print(f"INTEGRITY_CHECK=ERROR {e}")
        return 0 if ok_total else 1
    finally:
        try:
            if os.path.isdir(BASE):
                shutil.rmtree(BASE,ignore_errors=True)
            if not os.path.exists(BASE):
                print(f"LIMPIEZA_TMP=OK {BASE} eliminado")
            else:
                print(f"LIMPIEZA_TMP=FAIL {BASE} persiste")
                shutil.rmtree(BASE,ignore_errors=True)
        except Exception as exc:
            print(f"LIMPIEZA_TMP=ERROR {exc}")
        if app:
            try:
                app.processEvents()
            except Exception:
                pass

if __name__=="__main__":
    sys.exit(main())
