"""B9.4 modalidad Reducida — cantidad reducida sin scroll."""
import os, sys, tempfile, sqlite3, gc, time, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QScrollArea
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QEvent

import visor_videos
from visor_videos import Tarjeta, VisorVideos, PreviewTiraTemporal, MODO_TIRA_DINAMICA, MODO_TIRA, MODO_REDUCIDA, REDUCIDA_MAX_PREVIEWS, dimensiones_miniatura, _seleccionar_ms_reducida, _cantidad_reducida_que_cabe, _ms_tira_densidad_ordenada
from exploracion_temporal import tiempos_objetivo
from exploracion_cache import objetivo_total_densidad
import exploracion_cache

CONFIG_TMP = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(CONFIG_TMP.name, "configuracion.json")
app = QApplication.instance() or QApplication(sys.argv)

def _pix(color="#aabbcc"):
    pm = QPixmap(320,180)
    pm.fill(QColor(color))
    return pm

def _filas(nombres, durs, carpeta="C:\\tmp_b94"):
    filas=[]
    for i,(n,d) in enumerate(zip(nombres,durs), start=1):
        filas.append((n,float(d),1920,1080,"h264",3,12345,os.path.join(carpeta,n),i))
    return filas

def _crear_bd(filas):
    t=tempfile.TemporaryDirectory()
    ruta=os.path.join(t.name,"catalogo.db")
    conn=sqlite3.connect(ruta)
    try:
        conn.execute("""CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, duracion_segundos REAL, ancho INTEGER, alto INTEGER, codec_video TEXT, cantidad_miniaturas INTEGER, tamano_bytes INTEGER)""")
        for f in filas:
            nombre,dur,w,h,codec,mini,tam,ruta_v,vid=f
            conn.execute("INSERT INTO videos (id,nombre,ruta,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas) VALUES (?,?,?,?,?,?,?,?,?,?)",(vid,nombre,ruta_v,os.path.splitext(nombre)[1],"2026-08-03T00:00:00",dur,w,h,codec,mini))
        conn.commit()
    finally:
        conn.close()
    return t,ruta

def _crear_bd_homonimos(filas):
    t=tempfile.TemporaryDirectory()
    ruta=os.path.join(t.name,"catalogo.db")
    conn=sqlite3.connect(ruta)
    try:
        conn.execute("""CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, ruta TEXT NOT NULL, ruta_normalizada TEXT, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, duracion_segundos REAL, ancho INTEGER, alto INTEGER, codec_video TEXT, cantidad_miniaturas INTEGER, tamano_bytes INTEGER, UNIQUE(ruta_normalizada))""")
        for f in filas:
            nombre,dur,w,h,codec,mini,tam,ruta_v,vid=f
            ruta_norm=os.path.normcase(os.path.normpath(os.path.abspath(ruta_v)))
            conn.execute("INSERT INTO videos (id,nombre,ruta,ruta_normalizada,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(vid,nombre,ruta_v,ruta_norm,os.path.splitext(nombre)[1],"2026-08-03T00:00:00",dur,w,h,codec,mini))
        conn.commit()
    finally:
        conn.close()
    return t,ruta

def _densos(dur, cant):
    mss=tiempos_objetivo(dur,cant)
    return [{"instante": ms/1000.0, "pixmap": _pix("#ccbbaa")} for ms in mss]

def _a_modo(t, modo):
    idx=t._selector_modo_tira.findData(modo)
    if idx>=0:
        t._selector_modo_tira.setCurrentIndex(idx)
        QApplication.processEvents()

def _a_modo_tira(t): _a_modo(t, MODO_TIRA)
def _a_modo_din(t): _a_modo(t, MODO_TIRA_DINAMICA)
def _a_modo_red(t): _a_modo(t, MODO_REDUCIDA)

def _cleanup(v):
    if v is None: return
    for n in ("gestor","gestor_previews","gestor_operaciones","gestor_marcadores","gestor_segmentos","gestor_reproduccion","gestor_exploracion","gestor_resumen","gestor_migracion","gestor_export","gestor_preparacion_lote","gestor_preparacion_secuencia","gestor_renombrado","gestor_mover","gestor_crear_carpeta","gestor_copiar","gestor_eliminar","gestor_lote","gestor_renombrar_masivo","gestor_navegacion_destino","gestor_prevalidacion_drop","gestor_previews_visuales"):
        g=getattr(v,n,None)
        if g is not None:
            try:
                if getattr(g,"hilo",None) is not None: g.cerrar()
                else: g.cerrar()
            except: pass
    fin=time.monotonic()+3
    while time.monotonic()<fin:
        QApplication.processEvents()
        vivos=0
        for n in ("gestor","gestor_previews","gestor_operaciones","gestor_marcadores","gestor_segmentos","gestor_reproduccion","gestor_exploracion","gestor_resumen","gestor_migracion","gestor_export","gestor_preparacion_lote","gestor_preparacion_secuencia","gestor_renombrado","gestor_mover","gestor_crear_carpeta","gestor_copiar","gestor_eliminar","gestor_lote","gestor_renombrar_masivo","gestor_navegacion_destino","gestor_prevalidacion_drop","gestor_previews_visuales"):
            g=getattr(v,n,None)
            if g and getattr(g,"hilo",None) and g.hilo.isRunning(): vivos+=1
        if vivos==0: break
        time.sleep(0.02)
    try: v.close()
    except: pass
    try: v.deleteLater()
    except: pass
    for _ in range(5): QApplication.processEvents()
    time.sleep(0.1); QApplication.processEvents()
    try: QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except: pass
    for _ in range(3): QApplication.processEvents()
    gc.collect(); QApplication.processEvents()

# 1 default sigue Dinámica; combo tiene exactamente 4 en orden (B9.5 añade Ajustada)
def test_01_default_combo():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); QApplication.processEvents()
    ok = t._modo_tira_b93 == MODO_TIRA_DINAMICA
    ok = ok and t._selector_modo_tira.count()==4
    ok = ok and t._selector_modo_tira.itemText(0)=="Dinámica"
    ok = ok and t._selector_modo_tira.itemText(1)=="Tira"
    ok = ok and t._selector_modo_tira.itemText(2)=="Reducida"
    ok = ok and t._selector_modo_tira.itemText(3)=="Ajustada"
    ok = ok and t._selector_modo_tira.currentData()==MODO_TIRA_DINAMICA
    ok = ok and not t._tira_scroll.isVisible()
    ok = ok and not t._reducida_contenedor.isVisible()
    ok = ok and not t._ajustada_grid.isVisible()
    ok = ok and len(t._tira_previews_widgets)==0 and len(t._reducida_previews_widgets)==0 and len(t._ajustada_grid._logical_ms)==0
    t.deleteLater(); QApplication.processEvents()
    return ok, f"combo 4 ok={ok}"

# 2 helper subset: 15→5 con extremos y equiespaciado
def test_02_helper_15_5():
    logical = sorted(tiempos_objetivo(100.0,15))
    subset = _seleccionar_ms_reducida(logical,5)
    ok = len(subset)==5
    ok = ok and subset[0]==logical[0] and subset[-1]==logical[-1]
    ok = ok and subset==sorted(subset) and len(set(subset))==5
    # distribución razonablemente equiespaciada: diferencias ~ 3-4
    # verificar que cada paso sea 3 o 4 (para 15->5 ratio 3.5)
    idxs=[logical.index(ms) for ms in subset]
    diffs=[idxs[i+1]-idxs[i] for i in range(4)]
    ok = ok and all(d in (3,4) for d in diffs)
    # también incluir primero y último
    return ok, f"subset {subset} idx {idxs} diffs {diffs}"

# 3 helper cantidad 1 => central, universo <=N => todos
def test_03_helper_1_y_todos():
    logical = sorted(tiempos_objetivo(100.0,15))
    # 1 central
    subset1=_seleccionar_ms_reducida(logical,1)
    mid_idx=len(logical)//2
    ok = subset1==[logical[mid_idx]]
    # universo <=N
    small=[1000,2000,3000]
    subset_small=_seleccionar_ms_reducida(small,5)
    ok = ok and subset_small==sorted(small) and len(subset_small)==3
    # exact 5 -> todos
    exact=[100,200,300,400,500]
    ok = ok and _seleccionar_ms_reducida(exact,5)==exact
    # k=2 incluye extremos
    subset2=_seleccionar_ms_reducida(logical,2)
    ok = ok and subset2==[logical[0], logical[-1]]
    return ok, f"1central={subset1} mid={mid_idx} small={subset_small} 2={subset2}"

# 4 ancho suficiente => máximo 5 jamás >5
def test_04_ancho_suficiente_max5():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(2000,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.agregar_fotogramas_densos(_densos(100.0,15)); QApplication.processEvents()
    # forzar ancho grande
    t._contenedor_exploracion.setFixedWidth(2000); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    ok = len(subset)==5 and len(subset)<=5
    ok = ok and len(t._reducida_previews_widgets)==5
    ok = ok and len(t._reducida_previews_widgets)<=5
    # verificar no se crean 6
    t.deleteLater(); QApplication.processEvents()
    return ok, f"subset {len(subset)} pool {len(t._reducida_previews_widgets)}"

# 5 ancho estrecho => 1/2/3 según fórmula y requerido <= útil sin scrollbar
def test_05_ancho_estrecho():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(800,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.agregar_fotogramas_densos(_densos(100.0,15)); QApplication.processEvents()
    # helper puro
    slot=t._tira_ancho_slot()  # 320 para 16:9
    spacing=2
    # calcula para ancho_util estrecho: solo 1 debe caber si ancho=300
    cabe1=_cantidad_reducida_que_cabe(300, slot, spacing)
    cabe2=_cantidad_reducida_que_cabe(650, slot, spacing)
    cabe3=_cantidad_reducida_que_cabe(1000, slot, spacing)
    ok = cabe1==0 and cabe2==2 and cabe3==3
    # integración: forzar ancho_util pequeño via contenedor
    t._contenedor_exploracion.setFixedWidth(400); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    # 400 ancho_util ~ 400-4=396, slot 320 => cabe 1
    ok = ok and len(subset)==1
    # comprobar requerido <= útil
    req = len(subset)*slot + max(0,len(subset)-1)*spacing + 4
    util = t._reducida_ancho_util()
    ok = ok and req <= util + 1
    # verificar no QScrollArea
    ok = ok and not isinstance(t._reducida_contenedor, QScrollArea)
    # verificar que no tiene scrollbars — corrección precedencia: variable booleana inequívoca
    has_hbar = hasattr(t._reducida_contenedor, 'horizontalScrollBar')
    if has_hbar:
        try:
            condicion_no_hbar = not t._reducida_contenedor.horizontalScrollBar().isVisible()
        except Exception:
            condicion_no_hbar = True
    else:
        condicion_no_hbar = True
    ok = ok and condicion_no_hbar
    # en realidad QWidget no tiene scrollbar, asegurar que layout es QHBoxLayout
    ok = ok and isinstance(t._reducida_contenedor.layout(), QHBoxLayout)
    t.deleteLater(); QApplication.processEvents()
    return ok, f"cabe 300->{cabe1} 650->{cabe2} 1000->{cabe3} subset1={len(subset)} req {req} util {util}"

# 6 aspecto horizontal y vertical usan ancho_slot real B9.3 vertical puede permitir más pero cap 5
def test_06_aspecto():
    # horizontal 1920x1080 => slot 320
    fila_h=('hor.mp4', 100.0, 1920,1080,'h264',3,12345,r'C:\tmp\hor.mp4', 10)
    t=Tarjeta(fila_h); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.agregar_fotogramas_densos(_densos(100.0,30)); QApplication.processEvents()
    slot_h=t._tira_ancho_slot()
    ok = slot_h==320
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    ok = ok and len(t._reducida_previews_widgets)<=5
    for w in t._reducida_previews_widgets:
        ok = ok and w.width()==slot_h
    t.deleteLater(); QApplication.processEvents()
    # vertical 1080x1920 => slot ~101
    fila_v=('vert.mp4',100.0,1080,1920,'h264',3,12345,r'C:\tmp\vert.mp4', 11)
    tv=Tarjeta(fila_v); tv.show(); tv.resize(1200,600); QApplication.processEvents(); tv.expandir(); QApplication.processEvents()
    tv._densidad_manual=30
    tv.agregar_fotogramas_densos(_densos(100.0,30)); QApplication.processEvents()
    slot_v=tv._tira_ancho_slot()
    ok = ok and slot_v < 150 and slot_v==int(round(180*1080/1920))
    tv._contenedor_exploracion.setFixedWidth(800); QApplication.processEvents()
    _a_modo_red(tv); QApplication.processEvents()
    cabe_v=_cantidad_reducida_que_cabe(tv._reducida_ancho_util(), slot_v, 2)
    # con 800 ancho, cabe para vertical debiera ser >3
    ok = ok and cabe_v >=3
    ok = ok and len(tv._reducida_previews_widgets)<=5 and len(tv._reducida_previews_widgets)==min(5,cabe_v,30)
    for w in tv._reducida_previews_widgets:
        ok = ok and w.width()==slot_v
    tv.deleteLater(); QApplication.processEvents()
    return ok, f"h slot {slot_h} v slot {slot_v} cabe_v {cabe_v}"

# 7 exclusividad Dinámica/Tira/Reducida
def test_07_exclusividad():
    fila=_filas(["x.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.agregar_fotogramas_densos(_densos(100.0,15)); QApplication.processEvents()
    # Dinámica
    _a_modo_din(t); QApplication.processEvents()
    ok = t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible()
    # Tira
    _a_modo_tira(t); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible()
    # Reducida
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and not t._tira_scroll.isVisible() and t._reducida_contenedor.isVisible()
    # volver Dinámica
    _a_modo_din(t); QApplication.processEvents()
    ok = ok and t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible()
    # colapsada todas ocultas
    t.colapsar(); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"exclusiva ok={ok}"

# 8 Densidad 15/30/60/120/200 conserva logical total y subset <=5
def test_08_densidad_logical():
    ok=True; msg=[]
    for dens in [15,30,60,120,200]:
        fila=_filas(["a.mp4"],[600.0])[0]
        t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
        t._densidad_manual=dens
        t.agregar_fotogramas_densos(_densos(600.0,dens)); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(2000); QApplication.processEvents()
        _a_modo_red(t); QApplication.processEvents()
        logical = getattr(t,"_tira_logical_ms",[])
        subset = getattr(t,"_reducida_ms_subset",[])
        ok = ok and len(logical)==dens and len(t._previews_densos)==dens
        ok = ok and len(subset)<=5 and len(subset)>=1
        msg.append(f"{dens}:{len(logical)}->{len(subset)}")
        t.deleteLater(); QApplication.processEvents()
    return ok, ";".join(msg)

# 9 Reducida solicita/cachea solo subset no universo
def test_09_cache_acotado():
    fila=_filas(["a.mp4"],[600.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=200
    mss=tiempos_objetivo(600.0,200)
    t.set_metadata_densa(mss, version="v9"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    requeridos=t._ms_visuales_necesarios()
    ok = len(requeridos)==len(subset) and requeridos==set(subset)
    ok = ok and len(requeridos)<=5
    # simular carga de cache para subset
    for ms in list(requeridos)[:3]:
        t._cache_visual[ms]=_pix("#123")
    t._sincronizar_cache_visual()
    ok = ok and len(t._cache_visual)<=5 and len(t._cache_visual)<=len(subset)
    # verificar que universo 200 no está en cache
    ok = ok and len(t._cache_visual) < 200
    t.deleteLater(); QApplication.processEvents()
    return ok, f"subset {len(subset)} req {len(requeridos)} cache {len(t._cache_visual)}"

# 10 Tira->Reducida libera pool Tira; Reducida->Tira vuelve
def test_10_tira_reducida_switch():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=60
    t.agregar_fotogramas_densos(_densos(100.0,60)); QApplication.processEvents()
    # a tira
    _a_modo_tira(t); QApplication.processEvents()
    pool_tira=len(t._tira_previews_widgets)
    ok = pool_tira>0
    # a reducida
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    ok = ok and len(t._tira_previews_widgets)==0 and len(t._reducida_previews_widgets)>0 and len(t._reducida_previews_widgets)<=5
    ok = ok and len(t._previews_densos)==60  # metadata no perdida
    # volver a tira
    _a_modo_tira(t); QApplication.processEvents()
    ok = ok and len(t._reducida_previews_widgets)==0 and len(t._tira_previews_widgets)>0
    t.deleteLater(); QApplication.processEvents()
    return ok, f"tira {pool_tira} ->red {len(t._reducida_previews_widgets)} ->tira {ok}"

# 11 colapso libera widgets/cache reducida y desfija
def test_11_colapso():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._boton_fijar.setChecked(True); QApplication.processEvents()
    t._densidad_manual=30
    t.agregar_fotogramas_densos(_densos(100.0,30)); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    ok = len(t._reducida_previews_widgets)>0 and t._fijada
    t.colapsar(); QApplication.processEvents()
    try: QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except: pass
    QApplication.processEvents()
    ok = ok and not t._expandida and not t._fijada and len(t._reducida_previews_widgets)==0
    ok = ok and len(t._cache_visual)==0 and len(getattr(t,"_reducida_ms_subset",[]))==0
    t.deleteLater(); QApplication.processEvents()
    return ok, f"colapso ok={ok}"

# 12 dos fijadas una Tira y otra Reducida independientes
def test_12_dos_fijadas_independientes():
    filas=_filas(["a.mp4","b.mp4"],[100.0,100.0])
    tdir,ruta_db=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta_db); v.resize(1100,700); v.show()
    # esperar tarjetas
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=2: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    d=dict(v.tarjetas)
    ta=d["a.mp4"]; tb=d["b.mp4"]
    ta.expandir(); QApplication.processEvents(); ta._boton_fijar.setChecked(True); QApplication.processEvents()
    tb.expandir(); QApplication.processEvents(); tb._boton_fijar.setChecked(True); QApplication.processEvents()
    ta._densidad_manual=30; ta.agregar_fotogramas_densos(_densos(100.0,30)); QApplication.processEvents()
    tb._densidad_manual=60; tb.agregar_fotogramas_densos(_densos(100.0,60)); QApplication.processEvents()
    ta._contenedor_exploracion.setFixedWidth(1800); tb._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_tira(ta); _a_modo_red(tb); QApplication.processEvents()
    ok = ta._modo_tira_b93==MODO_TIRA and tb._modo_tira_b93==MODO_REDUCIDA
    ok = ok and len(ta._tira_logical_ms)==30 and len(tb._tira_logical_ms)==60
    ok = ok and len(ta._tira_previews_widgets)>0 and len(tb._reducida_previews_widgets)>0
    ok = ok and len(tb._reducida_previews_widgets)<=5
    # cache independiente
    ok = ok and ta._cache_visual is not tb._cache_visual
    _cleanup(v)
    try: tdir.cleanup()
    except: pass
    return ok, f"ta {ta._modo_tira_b93} {len(ta._tira_logical_ms)} tb {tb._modo_tira_b93} {len(tb._tira_logical_ms)}"

# 13 marcador creación exacta en Reducida
def test_13_marcador_reducida():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    dur=100.0
    t._duracion=dur
    t._densidad_manual=15
    logical=_ms_tira_densidad_ordenada(dur,15)
    t.set_metadata_densa(logical, version="v13"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    assert len(subset)>0
    # interceptar marcador
    created=[]
    t.marcador_creado.connect(lambda reg: created.append((reg["tiempo"], getattr(t,"_video_id", None))))
    # click en primer preview reducida
    ms=subset[0]
    t_inst=ms/1000.0
    # usar handler directo como haría click
    t._on_tira_left_clicked(ms)
    QApplication.processEvents()
    ok = len(created)==1 and abs(created[0][0]-t_inst)<1e-9
    ok = ok and created[0][1]==t._video_id
    # verificar que marcador agregado tiene tiempo exacto
    ok = ok and len(t._marcadores)==1 and abs(t._marcadores[0]["tiempo"]-t_inst)<1e-9
    t.deleteLater(); QApplication.processEvents()
    return ok, f"created {created} marcador {t._marcadores[0] if t._marcadores else None}"

# 14 segmento A/B exacto + A pendiente/cancelacion en Reducida
def test_14_segmento_reducida():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    dur=200.0; t._duracion=dur
    t._densidad_manual=30
    logical=_ms_tira_densidad_ordenada(dur,30)
    t.set_metadata_densa(logical, version="v14"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(2000); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    assert len(subset)>=2
    t._boton_segmento.setChecked(True); QApplication.processEvents()
    msA=subset[0]; msB=subset[-1]
    tA=msA/1000.0; tB=msB/1000.0
    # primer click A
    t._on_tira_left_clicked(msA); QApplication.processEvents()
    ok = t._extremo_segmento is not None and abs(t._extremo_segmento - tA)<1e-9
    # verificar que algún widget muestra pendiente
    pendientes=[w for w in t._reducida_previews_widgets if getattr(w,"_pendiente_tira",False)]
    ok = ok and len(pendientes)==1
    # segundo click B crea segmento
    created=[]
    t.segmento_creado.connect(lambda reg: created.append(reg))
    t._on_tira_left_clicked(msB); QApplication.processEvents()
    ok = ok and len(created)==1
    seg=created[0]
    ok = ok and abs(min(seg["inicio"], seg["fin"]) - min(tA,tB))<1e-9 and abs(max(seg["inicio"], seg["fin"]) - max(tA,tB))<1e-9
    ok = ok and t._extremo_segmento is None
    # A pendiente cancelación: crear nuevo A y toggle off
    t._on_tira_left_clicked(msA); QApplication.processEvents()
    ok = ok and t._extremo_segmento is not None
    t._boton_segmento.setChecked(False); QApplication.processEvents()
    ok = ok and t._extremo_segmento is None and not any(getattr(w,"_pendiente_tira",False) for w in t._reducida_previews_widgets)
    t.deleteLater(); QApplication.processEvents()
    return ok, f"seg {seg if created else None}"

# 15 marcadores/segmentos existentes decoran solo previews pertinentes sin ghosts
def test_15_decoraciones():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    dur=100.0; t._duracion=dur
    logical=_ms_tira_densidad_ordenada(dur,15)
    t.set_metadata_densa(logical, version="v15"); QApplication.processEvents()
    # crear marcadores en tiempos específicos (uno debe mapear a subset, otro quizás no pero verificamos no ghost en no pertinente)
    # con densidad 15, logical son 15 muestras; reducida 5 elige idx 0,4,7,11,14 (dependiendo round)
    t._marcadores=[{"tiempo": logical[0]/1000.0, "color": "rojo", "id":1},{"tiempo": logical[7]/1000.0, "color": None, "id":2}]
    t._segmentos=[{"id":10, "inicio": logical[11]/1000.0 -0.1, "fin": logical[11]/1000.0+0.1, "color":"azul"}]
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    # verificar que cada widget tiene marcadores solo si ms está mapeado
    ok=True
    for w in t._reducida_previews_widgets:
        ms=w._logical_ms
        marc=w._marcadores_tira
        seg=w._segmentos_tira
        # si marcador tiempo corresponde a ms, debe aparecer
        exp_marc=[m for m in t._marcadores if t._marcadores_para_sample_tira(ms) and any(m["id"]==x["id"] for x in marc)]
        # verificar que marcadores list coincide con helper
        ok = ok and marc==t._marcadores_para_sample_tira(ms)
        ok = ok and seg==t._segmentos_para_sample_tira(ms)
        # no ghost: if helper returns [], widget must have []
        if not t._marcadores_para_sample_tira(ms):
            ok = ok and len(marc)==0
        if not t._segmentos_para_sample_tira(ms):
            ok = ok and len(seg)==0
    t.deleteLater(); QApplication.processEvents()
    return ok, f"subset {subset}  decor ok={ok}"

# 16 click derecho una sola emision y menu actua sobre registro real
def test_16_click_derecho():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    dur=100.0; t._duracion=dur
    logical=_ms_tira_densidad_ordenada(dur,15)
    t.set_metadata_densa(logical, version="v16"); QApplication.processEvents()
    # marcador exacto asociado al primer subset ms
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    subset=getattr(t,"_reducida_ms_subset",[])
    ms0=subset[0]
    tiempo0=ms0/1000.0
    t._marcadores=[{"tiempo": tiempo0, "color":"rojo", "id":42}]
    # recompute map and refresh decor
    t._reducida_actualizar_decoraciones(); QApplication.processEvents()
    emisiones=[]
    def on_right(ms, gp):
        emisiones.append(ms)
    # conectar extra listener a widgets (ellos ya conectan al handler interno)
    for w in t._reducida_previews_widgets:
        if w._logical_ms==ms0:
            # conectar además para contar
            w.tira_right_clicked.connect(on_right)
            # simular right click
            from PySide6.QtCore import QPoint
            w.tira_right_clicked.emit(ms0, QPoint(0,0))
            QApplication.processEvents()
            break
    ok = len(emisiones)==1 and emisiones[0]==ms0
    # verificar que handler interno crea menu para registro real (no duplicado)
    # después de emisión, _menu_marcador_actual debe existir y corresponder a marcador id 42
    ok = ok and t._menu_marcador_actual is not None
    t.deleteLater(); QApplication.processEvents()
    return ok, f"emisiones {emisiones} menu {t._menu_marcador_actual is not None}"

# 17 homonimos mismo nombre distintos video_id aislados
def test_17_homonimos():
    filas=[("same.mp4",100.0,1920,1080,"h264",3,12345,r"C:\a\same.mp4",1), ("same.mp4",100.0,1920,1080,"h264",3,12345,r"C:\b\same.mp4",2)]
    tdir,ruta_db=_crear_bd_homonimos(filas)
    v=VisorVideos(ruta_db=ruta_db); v.resize(1100,700); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=2: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    d={}
    for nombre, tarjeta in v.tarjetas:
        d.setdefault(nombre, []).append(tarjeta)
    t1=d["same.mp4"][0]; t2=d["same.mp4"][1]
    ok = t1._video_id!=t2._video_id
    # expandir y probar t1 aislado (fijar para no colapsar al expandir t2 luego, pero test secuencial es suficiente)
    t1.expandir(); QApplication.processEvents()
    t1._densidad_manual=15
    t1.set_metadata_densa(_ms_tira_densidad_ordenada(100.0,15), version=f"v17_{t1._video_id}"); QApplication.processEvents()
    t1._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t1); QApplication.processEvents()
    assert len(t1._reducida_ms_subset)>0, "t1 subset vacío"
    t1._on_tira_left_clicked(t1._reducida_ms_subset[0]); QApplication.processEvents()
    ok = ok and len(t1._marcadores)==1
    # colapsar t1 antes de probar t2 para evitar autocolapso
    t1.colapsar(); QApplication.processEvents()
    t2.expandir(); QApplication.processEvents()
    t2._densidad_manual=15
    t2.set_metadata_densa(_ms_tira_densidad_ordenada(100.0,15), version=f"v17_{t2._video_id}"); QApplication.processEvents()
    t2._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t2); QApplication.processEvents()
    ok = ok and len(t2._marcadores)==0
    # t1 sigue con su marcador pero no debe haber contaminado t2
    ok = ok and len(t1._marcadores)==1
    ok = ok and t1._reducida_ms_subset is not t2._reducida_ms_subset
    _cleanup(v)
    try: tdir.cleanup()
    except: pass
    return ok, f"ids {t1._video_id}/{t2._video_id} marcadores {len(t1._marcadores)}/{len(t2._marcadores)}"

# 18 no persistencia
def test_18_no_persistencia():
    ruta_cfg=os.environ["VISOR_CONFIG"]
    antes=b""
    if os.path.isfile(ruta_cfg):
        with open(ruta_cfg,"rb") as f: antes=f.read()
    filas=_filas(["a.mp4"],[100.0])
    tdir,ruta_db=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta_db); v.show()
    for _ in range(20):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=1: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    ta=dict(v.tarjetas)["a.mp4"]
    ta.expandir(); QApplication.processEvents()
    ta._densidad_manual=30
    ta.set_metadata_densa(_ms_tira_densidad_ordenada(100.0,30), version="v18"); QApplication.processEvents()
    ta._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(ta); QApplication.processEvents()
    despues=b""
    if os.path.isfile(ruta_cfg):
        with open(ruta_cfg,"rb") as f: despues=f.read()
    ok_cfg = b"reducida" not in despues.lower() and b"b94" not in despues.lower()
    conn=sqlite3.connect(v._ruta_db)
    try:
        cur=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'")
        row=cur.fetchone()
        sql=row[0] if row else ""
        ok_sql = "reducida" not in sql.lower()
    finally:
        conn.close()
    _cleanup(v)
    try: tdir.cleanup()
    except: pass
    if antes==b"" and os.path.isfile(ruta_cfg):
        try: os.remove(ruta_cfg)
        except: pass
    elif antes!=b"":
        with open(ruta_cfg,"wb") as f: f.write(antes)
    return ok_cfg and ok_sql, f"cfg {ok_cfg} sql {ok_sql}"

# 19 no widgets/QPixmap masivos densidad200 reducida <=5
def test_19_no_masivo():
    # asegurar limpieza previa
    for _ in range(5): QApplication.processEvents(); gc.collect()
    fila=_filas(["a.mp4"],[600.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=200
    mss=tiempos_objetivo(600.0,200)
    t.set_metadata_densa(mss, version="v19"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(2000); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    ok = len(t._reducida_previews_widgets)<=5 and len(t._reducida_previews_widgets)<=REDUCIDA_MAX_PREVIEWS
    ok = ok and len(t._previews_densos)==200
    # cache visual acotado
    for ms in list(t._ms_visuales_necesarios())[:5]:
        t._cache_visual[ms]=_pix("#abc")
    t._sincronizar_cache_visual()
    ok = ok and len(t._cache_visual)<=5 and len(t._cache_visual)<=REDUCIDA_MAX_PREVIEWS
    # pool de esta tarjeta <=5, global puede tener residuos de otros tests no limpiados totalmente; verificar pool específico
    ok = ok and len(t._reducida_previews_widgets)<=5
    # también verificar que no se crearon 200 widgets en esta tarjeta
    ok = ok and len(t._reducida_previews_widgets) != 200
    t.deleteLater()
    for _ in range(5): QApplication.processEvents()
    try: QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except: pass
    QApplication.processEvents(); gc.collect()
    return ok, f"pool {len(t._reducida_previews_widgets)} cache {len(t._cache_visual)} logical 200"

# 20 no auto-fit widths coinciden con ancho natural B9.3 no se reducen para hacer entrar 5
def test_20_no_autofit():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(800,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(_ms_tira_densidad_ordenada(100.0,30), version="v20"); QApplication.processEvents()
    # ancho estrecho donde 5 no caben: solo 2 caben
    t._contenedor_exploracion.setFixedWidth(700); QApplication.processEvents()
    slot=t._tira_ancho_slot()
    _a_modo_red(t); QApplication.processEvents()
    ok = len(t._reducida_previews_widgets) <5  # no forzar 5
    for w in t._reducida_previews_widgets:
        ok = ok and w.width()==slot
    # verificar que no se redujo para hacer entrar 5
    ok = ok and slot == t._tira_ancho_slot()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"pool {len(t._reducida_previews_widgets)} slot {slot}"

# 21 B9.6 autoresize Reducida: tras resize debe recalcular cabe automáticamente max5 sin overflow
def test_21_no_autoresize():
    import time as _t
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(_ms_tira_densidad_ordenada(100.0,30), version="v21"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_modo_red(t); QApplication.processEvents()
    try:
        t._responsive_b96_ultimo_ancho = t._responsive_b96_obtener_ancho_util()
    except: pass
    subset_antes=list(getattr(t,"_reducida_ms_subset",[]))
    pool_antes=len(t._reducida_previews_widgets)
    slot=t._tira_ancho_slot()
    # cambiar ancho manualmente y disparar resize B9.6
    t._contenedor_exploracion.setFixedWidth(400); QApplication.processEvents()
    try:
        from PySide6.QtGui import QResizeEvent
        from PySide6.QtCore import QSize
        ev=QResizeEvent(QSize(600,600), QSize(t.width(), t.height()))
        t.resize(600,600); QApplication.sendEvent(t, ev)
    except: pass
    for _ in range(5):
        QApplication.processEvents(); _t.sleep(0.02); QApplication.processEvents()
    subset_desp=list(getattr(t,"_reducida_ms_subset",[]))
    pool_desp=len(t._reducida_previews_widgets)
    ok=True
    # debe haber recalculado: cabe 400 -> 1, no 5
    geom_cambio = (pool_desp != pool_antes or subset_desp != subset_antes)
    ok = ok and geom_cambio
    ok = ok and 1 <= pool_desp <=5 and pool_desp==len(subset_desp) <=5
    ok = ok and not isinstance(t._reducida_contenedor, QScrollArea)
    ok = ok and t._reducida_contenedor.isVisible()
    # previews normales no se encogen
    for w in t._reducida_previews_widgets:
        ok = ok and w.width()==slot
    # logical N sigue 30
    ok = ok and len(getattr(t,"_tira_logical_ms",[]))==30
    # sin crash
    ok = ok and isinstance(subset_desp, list)
    t.deleteLater(); QApplication.processEvents()
    return ok, f"B9.6 antes {pool_antes} {len(subset_antes)} -> desp {pool_desp} {len(subset_desp)} slot {slot} ok={ok}"

# runner
import traceback
TESTS=[
    ("01_default_combo",test_01_default_combo),
    ("02_helper_15_5",test_02_helper_15_5),
    ("03_helper_1_y_todos",test_03_helper_1_y_todos),
    ("04_ancho_suficiente_max5",test_04_ancho_suficiente_max5),
    ("05_ancho_estrecho",test_05_ancho_estrecho),
    ("06_aspecto",test_06_aspecto),
    ("07_exclusividad",test_07_exclusividad),
    ("08_densidad_logical",test_08_densidad_logical),
    ("09_cache_acotado",test_09_cache_acotado),
    ("10_tira_reducida_switch",test_10_tira_reducida_switch),
    ("11_colapso",test_11_colapso),
    ("12_dos_fijadas_independientes",test_12_dos_fijadas_independientes),
    ("13_marcador_reducida",test_13_marcador_reducida),
    ("14_segmento_reducida",test_14_segmento_reducida),
    ("15_decoraciones",test_15_decoraciones),
    ("16_click_derecho",test_16_click_derecho),
    ("17_homonimos",test_17_homonimos),
    ("18_no_persistencia",test_18_no_persistencia),
    ("19_no_masivo",test_19_no_masivo),
    ("20_no_autofit",test_20_no_autofit),
    ("21_no_autoresize",test_21_no_autoresize),
]

if __name__=="__main__":
    fails=[]
    for name,fn in TESTS:
        try:
            ok,msg=fn()
            print(f"{name}: {'PASS' if ok else 'FAIL'} {msg}")
            if not ok:
                fails.append(name)
            for _ in range(3):
                QApplication.processEvents()
            gc.collect()
            QApplication.processEvents()
        except Exception as e:
            traceback.print_exc()
            print(f"{name}: EXC {e}")
            fails.append(name)
    print(f"\nTotal {len(TESTS)} fails {len(fails)}: {fails}")
    sys.exit(0 if not fails else 1)
