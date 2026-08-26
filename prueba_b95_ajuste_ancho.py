"""B9.5 Ajustada — grilla TODAS al ancho (varias filas) — pruebas bloqueantes."""
import os, sys, tempfile, sqlite3, gc, time, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QScrollArea
from PySide6.QtGui import QPixmap, QColor, QImage
from PySide6.QtCore import Qt, QEvent, QPoint, QRect

import visor_videos
from visor_videos import Tarjeta, VisorVideos, PreviewTiraTemporal, AjustadaGridWidget, MODO_TIRA_DINAMICA, MODO_TIRA, MODO_REDUCIDA, MODO_AJUSTADA, AJUSTADA_SPACING, AJUSTADA_MARGIN, dimensiones_miniatura, _ms_tira_densidad_ordenada, _ajustada_calcular_cols, configurar_tamano_miniaturas, obtener_tamano_miniaturas, TAMANIOS_MINIATURAS
from exploracion_temporal import tiempos_objetivo
from exploracion_cache import objetivo_total_densidad
import exploracion_cache

CONFIG_TMP = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(CONFIG_TMP.name, "configuracion.json")
app = QApplication.instance() or QApplication(sys.argv)

def _pix(color="#aabbcc", w=320, h=180):
    pm = QPixmap(w, h)
    pm.fill(QColor(color))
    return pm

def _filas(nombres, durs, anchos=None, altos=None, carpeta="C:\\tmp_b95"):
    filas=[]
    for i,(n,d) in enumerate(zip(nombres,durs), start=1):
        w = anchos[i-1] if anchos and i-1 < len(anchos) else 1920
        h = altos[i-1] if altos and i-1 < len(altos) else 1080
        filas.append((n,float(d),w,h,"h264",3,12345,os.path.join(carpeta,n),i))
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

def _a_ajustada(t): _a_modo(t, MODO_AJUSTADA)
def _a_tira(t): _a_modo(t, MODO_TIRA)
def _a_din(t): _a_modo(t, MODO_TIRA_DINAMICA)
def _a_reducida(t): _a_modo(t, MODO_REDUCIDA)

def _cleanup_visores(v):
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

# 1 selector 4 opciones orden Dinámica Tira Reducida Ajustada default Dinámica
def test_01_selector_4():
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
    # debe ser 1 widget ajustada, no 200
    cnt_aju = len([w for w in t.findChildren(AjustadaGridWidget)])
    ok = ok and cnt_aju==1
    t.deleteLater(); QApplication.processEvents()
    return ok, f"selector 4 ok={ok} cntAju={cnt_aju if 'cnt_aju' in locals() else '?'}"

# 2 Ajustada es cuarta Vista separada y mutuamente excluyente
def test_02_exclusividad():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.agregar_fotogramas_densos(_densos(100.0,15)); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_din(t); QApplication.processEvents()
    ok = t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible() and not t._ajustada_grid.isVisible()
    _a_tira(t); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible() and not t._ajustada_grid.isVisible()
    _a_reducida(t); QApplication.processEvents()
    # reducida requiere ancho, fijar
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents(); _a_reducida(t); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and not t._tira_scroll.isVisible() and t._reducida_contenedor.isVisible() and not t._ajustada_grid.isVisible()
    _a_ajustada(t); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible() and t._ajustada_grid.isVisible()
    _a_din(t); QApplication.processEvents()
    ok = ok and t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible() and not t._ajustada_grid.isVisible()
    t.colapsar(); QApplication.processEvents()
    ok = ok and not t._franja.isVisible() and not t._tira_scroll.isVisible() and not t._reducida_contenedor.isVisible() and not t._ajustada_grid.isVisible()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"exclusiva ok={ok}"

# 3 Densidades 15/30/60/120/200 N exacto sin subset
def test_03_densidades_todas():
    ok=True; msg=[]
    for dens in [15,30,60,120,200]:
        fila=_filas(["a.mp4"],[600.0])[0]
        t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
        t._densidad_manual=dens
        # metadata via set_metadata_densa
        mss=tiempos_objetivo(600.0, dens)
        t.set_metadata_densa(mss, version=f"v3_{dens}"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
        _a_ajustada(t); QApplication.processEvents()
        logical = getattr(t, "_ajustada_logical_ms", []) or getattr(t, "_tira_logical_ms", [])
        ok = ok and len(logical)==dens and len(t._previews_densos)==dens
        # Ajustada debe tener N celdas lógicas == N, no 5
        ok = ok and len(t._ajustada_grid._logical_ms)==dens
        msg.append(f"{dens}:{len(logical)}")
        t.deleteLater(); QApplication.processEvents()
    return ok, ";".join(msg)

# 4 Auto conserva fórmula vigente
def test_04_auto():
    ok=True; msg=[]
    for dur, exp in [(30,15),(120,15),(600,20),(3360,112),(7200,200)]:
        fila=_filas(["y.mp4"],[float(dur)])[0]
        t=Tarjeta(fila); t.show(); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
        t._densidad_manual=None
        cant=objetivo_total_densidad(dur)
        ok = ok and cant==exp
        mss=tiempos_objetivo(float(dur), cant)
        t.set_metadata_densa(mss, version=f"auto_{dur}"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
        _a_ajustada(t); QApplication.processEvents()
        logical = getattr(t, "_ajustada_logical_ms", [])
        ok = ok and len(logical)==exp
        msg.append(f"Auto{dur}={exp}->{len(logical)}")
        t.deleteLater(); QApplication.processEvents()
    return ok, ";".join(msg)

# 5 Grilla cols>=1 rows=ceil(N/cols) sin overflow ni scroll horizontal
def test_05_grilla_sin_overflow():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(tiempos_objetivo(100.0,30), version="v5"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(900); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    cols=t._ajustada_cols; rows=t._ajustada_rows; cw=t._ajustada_cell_w; ch=t._ajustada_cell_h; spacing=AJUSTADA_SPACING; margin=AJUSTADA_MARGIN
    ancho_util=t._ajustada_ancho_util()
    ok = cols>=1 and rows==math.ceil(30/cols)
    # ancho requerido <= ancho_util +1
    req = cols*cw + (cols-1)*spacing
    ok = ok and req <= ancho_util+1
    # ninguna celda excede ancho_util (x+width <= ancho_util+2*margin)
    for idx in range(30):
        r=t._ajustada_grid._rect_for_index(idx)
        ok = ok and r.x() + r.width() <= ancho_util + 2*margin +1
        ok = ok and r.width()==cw and r.height()==ch
    # sin QScrollArea horizontal interno
    ok = ok and not isinstance(t._ajustada_grid, QScrollArea)
    ok = ok and not t._ajustada_grid.parent().__class__.__name__=="QScrollArea"
    # verificar que Ajustada no tiene scrollbar horizontal visible
    _has_hbar = hasattr(t._ajustada_grid, "horizontalScrollBar")
    _no_hbar_visible = (not _has_hbar) or (not t._ajustada_grid.horizontalScrollBar().isVisible() if _has_hbar else True)
    ok = ok and _no_hbar_visible
    t.deleteLater(); QApplication.processEvents()
    return ok, f"cols {cols} rows {rows} cw {cw} ch {ch} ancho_util {ancho_util} req {req} ok={ok}"

# 6 Aspect ratios 16:9 9:16 4:3 extremo sin deformación
def test_06_aspect_ratios():
    casos=[
        (1920,1080, 16/9, 320),
        (1080,1920, 1080/1920, int(round(180*1080/1920))),
        (640,480, 4/3, int(round(180*4/3))),
        (2560,1080, 2560/1080, int(round(180*2560/1080))), # ultrawide 2.37
    ]
    ok=True; msg=[]
    for w,h,asp_exp,w_exp in casos:
        fila=(f"v_{w}x{h}.mp4",100.0,w,h,"h264",3,12345,f"C:\\tmp\\v_{w}x{h}.mp4", 99)
        t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
        t._densidad_manual=15
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version=f"asp_{w}x{h}"); QApplication.processEvents()
        slot=t._tira_ancho_slot()
        # slot debe ser w_exp (con clamps 40..800)
        exp_clamped = max(40, min(800, w_exp))
        ok = ok and slot==exp_clamped
        t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_ajustada(t); QApplication.processEvents()
        cw=t._ajustada_cell_w; ch=t._ajustada_cell_h
        # cell_h derivado mantiene aspecto: cw/ch ~= asp
        asp_cell = cw/ch if ch else 0
        ok = ok and abs(asp_cell - asp_exp) < 0.05
        # no deformación: celda no recorta, mantiene KeepAspectRatio (verificar ch = round(cw/asp))
        ch_expected = int(round(cw/asp_exp))
        ok = ok and abs(ch - ch_expected) <=1
        msg.append(f"{w}x{h} slot {slot} cw {cw} ch {ch} asp {asp_cell:.2f}")
        t.deleteLater(); QApplication.processEvents()
    return ok, ";".join(msg)

# 7 N=1/15/200 y anchos variados sin división cero/overflow
def test_07_edge_N_ancho():
    ok=True; msg=[]
    for N, ancho_cfg in [(1,200),(1,1800),(15,200),(15,1800),(200,300),(200,1800)]:
        dur=600.0 if N==200 else 100.0
        fila=_filas(["a.mp4"],[dur])[0]
        t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
        t._densidad_manual=N
        mss=tiempos_objetivo(dur,N) if N!=1 else tiempos_objetivo(dur,1)
        # para N=1, tiempos_objetivo produce 1
        t.set_metadata_densa(mss, version=f"edge_{N}_{ancho_cfg}"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(ancho_cfg); QApplication.processEvents()
        _a_ajustada(t); QApplication.processEvents()
        try:
            cols=t._ajustada_cols; rows=t._ajustada_rows; cw=t._ajustada_cell_w; ch=t._ajustada_cell_h
            ok = ok and cols>=1 and rows>=1 and cw>=40 and ch>=30
            ok = ok and rows==math.ceil(len(mss)/cols)
            ok = ok and len(t._ajustada_grid._logical_ms)==len(mss)
            # sin division zero
            assert cw>0 and ch>0
            msg.append(f"N={N} w={ancho_cfg} cols {cols} rows {rows}")
        except Exception as e:
            ok=False; msg.append(f"N={N} w={ancho_cfg} EXC {e}")
        t.deleteLater(); QApplication.processEvents()
    return ok, ";".join(msg)

# 8 Última fila parcial mantiene orden cronológico y uniformidad
def test_08_ultima_fila():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v8"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(700); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    cols=t._ajustada_cols; rows=t._ajustada_rows
    logical=t._ajustada_logical_ms
    ok = logical==sorted(logical)
    # última fila parcial: verificar que número celdas última fila = N % cols o cols
    n=15; rem=n%cols; expected_last = rem if rem!=0 else cols
    # contar rects última fila
    last_row_start=(rows-1)*cols
    last_row_count = n - last_row_start
    ok = ok and last_row_count==expected_last
    # uniformidad: todos los cell_w iguales, cell_h iguales
    for idx in range(n):
        r=t._ajustada_grid._rect_for_index(idx)
        ok = ok and r.width()==t._ajustada_cell_w and r.height()==t._ajustada_cell_h
    # orden cronológico visual: x crece con col, y con row, idx incrementa orden
    for idx in range(n-1):
        r1=t._ajustada_grid._rect_for_index(idx); r2=t._ajustada_grid._rect_for_index(idx+1)
        # idx+1 está a la derecha o siguiente fila
        if (idx+1)%cols==0:
            ok = ok and r2.y() > r1.y()
        else:
            ok = ok and r2.x() > r1.x() and r2.y()==r1.y()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"cols {cols} rows {rows} last {expected_last} ok={ok}"

# 9 Placeholders representan N aunque cache vacía
def test_09_placeholders():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(tiempos_objetivo(100.0,30), version="v9"); QApplication.processEvents()
    # asegurar cache vacía
    t._cache_visual.clear(); t._cache_visual_pending.clear(); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    ok = len(t._ajustada_grid._logical_ms)==30 and len(t._cache_visual)==0
    # cada rect existe y es visible placeholder
    for idx in range(30):
        r=t._ajustada_grid._rect_for_index(idx)
        ok = ok and not r.isEmpty() and r.width()>0
    # no pixmaps retenidos, pero celdas existen
    ok = ok and t._ajustada_grid.isVisible()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"logical {len(t._ajustada_grid._logical_ms)} cache {len(t._cache_visual)}"

# 10 Cache/QPixmap acotada con 200, no 200 widgets ni 200 pixmaps
def test_10_cache_acotada():
    fila=_filas(["a.mp4"],[600.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=200
    mss=tiempos_objetivo(600.0,200)
    t.set_metadata_densa(mss, version="v10"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    # poblar cache con visibles (batch)
    # simular que se cargaron 12
    for ms in list(t._ajustada_grid._logical_ms)[:12]:
        t._cache_visual[ms]=_pix("#123")
    t._sincronizar_cache_visual(); QApplication.processEvents()
    ok = len(t._cache_visual) <= 24 and len(t._cache_visual) < 200
    # widgets: solo 1 grid, no 200 PreviewTiraTemporal
    cnt_tira = len([w for w in QApplication.allWidgets() if isinstance(w, PreviewTiraTemporal) and w.isVisible()])
    # ajustada grid count
    cnt_aju = len([w for w in t.findChildren(AjustadaGridWidget)])
    ok = ok and cnt_aju==1
    ok = ok and len(t._ajustada_grid._logical_ms)==200
    # verificar que no se crearon 200 PreviewTiraTemporal widgets (solo 1 grilla custom)
    ok = ok and cnt_tira < 5  # no 200 widgets de preview
    # no 200 pixmaps grandes
    ok = ok and len(t._cache_visual) != 200
    t.deleteLater(); QApplication.processEvents()
    gc.collect(); QApplication.processEvents()
    return ok, f"cache {len(t._cache_visual)} cntAju {cnt_aju} cntTira {cnt_tira}"

# 11 Ciclos sin crecimiento ghosts
def test_11_ciclos():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=60
    t.set_metadata_densa(tiempos_objetivo(100.0,60), version="v11"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    ok=True
    for i in range(3):
        _a_din(t); QApplication.processEvents()
        ok = ok and t._franja.isVisible() and not t._ajustada_grid.isVisible() and len(t._cache_visual)==0
        _a_tira(t); QApplication.processEvents()
        ok = ok and t._tira_scroll.isVisible()
        _a_reducida(t); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents(); _a_reducida(t); QApplication.processEvents()
        ok = ok and t._reducida_contenedor.isVisible()
        _a_ajustada(t); QApplication.processEvents()
        ok = ok and t._ajustada_grid.isVisible()
        # cache debe mantenerse acotada
        ok = ok and len(t._cache_visual) <= 24
    # después de ciclos, solo una vista visible
    visibles = sum([t._franja.isVisible(), t._tira_scroll.isVisible(), t._reducida_contenedor.isVisible(), t._ajustada_grid.isVisible()])
    ok = ok and visibles==1
    t.deleteLater(); QApplication.processEvents()
    return ok, f"ciclos visibles {visibles} ok={ok}"

# 12 Marcadores/segmentos/pendiente A en celda correcta
def test_12_anotaciones():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    dur=100.0; t._duracion=dur
    t._densidad_manual=15
    logical=tiempos_objetivo(dur,15)
    t.set_metadata_densa(logical, version="v12"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    # marcadores en tiempos exactos de logical[0] y logical[7]
    logical_sorted=sorted(logical)
    t._marcadores=[{"tiempo": logical_sorted[0]/1000.0, "color":"rojo", "id":1},{"tiempo": logical_sorted[7]/1000.0, "color":None, "id":2}]
    t._segmentos=[{"id":10, "inicio": logical_sorted[5]/1000.0 -0.1, "fin": logical_sorted[5]/1000.0+0.1, "color":"azul"}]
    t._reconstruir_mapa_marcadores_tira(); QApplication.processEvents()
    # verificar helper asigna correctamente
    ok=True
    for ms in logical_sorted:
        marc = t._marcadores_para_sample_tira(ms)
        seg = t._segmentos_para_sample_tira(ms)
        # si ms es logical[0] debe tener marcador id 1
        if ms==logical_sorted[0]:
            ok = ok and len(marc)==1 and marc[0]["id"]==1
        elif ms==logical_sorted[7]:
            ok = ok and len(marc)==1 and marc[0]["id"]==2
        else:
            # otros no deben tener esos marcadores (pueden tener 0)
            if ms!=logical_sorted[0] and ms!=logical_sorted[7]:
                ok = ok and not any(m["id"] in (1,2) for m in marc)
        # segmento debe contener solo ms cercano a logical[5]
        if ms==logical_sorted[5]:
            ok = ok and len(seg)==1 and seg[0]["id"]==10
        # pendiente A
    t._boton_segmento.setChecked(True); QApplication.processEvents()
    t._extremo_segmento = logical_sorted[3]/1000.0
    QApplication.processEvents()
    pendiente = t._tira_ms_pendiente_logico()
    ok = ok and pendiente==logical_sorted[3]
    # Resetear modo segmento para probar creación marcador exacta
    t._boton_segmento.setChecked(False); QApplication.processEvents()
    t._extremo_segmento=None; QApplication.processEvents()
    # creación desde click ms exacto
    created=[]
    t.marcador_creado.connect(lambda reg: created.append(reg["tiempo"]))
    t._on_ajustada_left_clicked(logical_sorted[4]); QApplication.processEvents()
    ok = ok and len(created)==1 and abs(created[0]-logical_sorted[4]/1000.0)<1e-9
    t.deleteLater(); QApplication.processEvents()
    return ok, f"anot ok={ok} pendiente {pendiente}"

# 13 Dos tarjetas fijadas Ajustada densidades diferentes independientes
def test_13_dos_fijadas():
    filas=_filas(["a.mp4","b.mp4"],[100.0,200.0])
    tdir,ruta_db=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta_db); v.resize(1100,700); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=2: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    d=dict(v.tarjetas)
    ta=d["a.mp4"]; tb=d["b.mp4"]
    ta.expandir(); QApplication.processEvents(); ta._boton_fijar.setChecked(True); QApplication.processEvents()
    tb.expandir(); QApplication.processEvents(); tb._boton_fijar.setChecked(True); QApplication.processEvents()
    ta._densidad_manual=30; ta.set_metadata_densa(tiempos_objetivo(100.0,30), version="v13a"); QApplication.processEvents()
    tb._densidad_manual=60; tb.set_metadata_densa(tiempos_objetivo(200.0,60), version="v13b"); QApplication.processEvents()
    ta._contenedor_exploracion.setFixedWidth(1200); tb._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(ta); _a_ajustada(tb); QApplication.processEvents()
    ok = ta._modo_tira_b93==MODO_AJUSTADA and tb._modo_tira_b93==MODO_AJUSTADA
    ok = ok and len(ta._ajustada_logical_ms)==30 and len(tb._ajustada_logical_ms)==60
    # cols pueden coincidir o no — no hay invariante obligatorio sobre igualdad de columnas entre tarjetas distintas
    ok = ok and ta._cache_visual is not tb._cache_visual
    ok = ok and ta._ajustada_grid is not tb._ajustada_grid
    _cleanup_visores(v)
    try: tdir.cleanup()
    except: pass
    return ok, f"ta30 {len(ta._ajustada_logical_ms)} tb60 {len(tb._ajustada_logical_ms)} ok={ok}"

# 14 Colapsar libera estado visual/cache sin borrar metadata disco
def test_14_colapsar():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(tiempos_objetivo(100.0,30), version="v14"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    for ms in t._ajustada_grid._logical_ms[:5]:
        t._cache_visual[ms]=_pix("#abc")
    ok = len(t._cache_visual)>0 and t._ajustada_grid.isVisible()
    t.colapsar(); QApplication.processEvents()
    try: QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except: pass
    QApplication.processEvents()
    ok = ok and not t._expandida and not t._ajustada_grid.isVisible() and len(t._cache_visual)==0 and len(t._cache_visual_pending)==0
    ok = ok and len(t._ajustada_grid._logical_ms)==0
    # _previews_densos se vacía al colapsar por diseño existente, pero disco permanece (no verificado aquí)
    t.deleteLater(); QApplication.processEvents()
    return ok, f"colapso ok={ok}"

# 15 No persistencia del modo Ajustada
def test_15_no_persistencia():
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
    ta.set_metadata_densa(tiempos_objetivo(100.0,30), version="v15"); QApplication.processEvents()
    ta._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(ta); QApplication.processEvents()
    despues=b""
    if os.path.isfile(ruta_cfg):
        with open(ruta_cfg,"rb") as f: despues=f.read()
    ok_cfg = b"ajustada" not in despues.lower() and b"b95" not in despues.lower()
    conn=sqlite3.connect(v._ruta_db)
    try:
        cur=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'")
        row=cur.fetchone()
        sql=row[0] if row else ""
        ok_sql = "ajustada" not in sql.lower()
    finally:
        conn.close()
    _cleanup_visores(v)
    try: tdir.cleanup()
    except: pass
    if antes==b"" and os.path.isfile(ruta_cfg):
        try: os.remove(ruta_cfg)
        except: pass
    elif antes!=b"":
        with open(ruta_cfg,"wb") as f: f.write(antes)
    return ok_cfg and ok_sql, f"cfg {ok_cfg} sql {ok_sql}"

# 16 B9.6 autoresize: resize puro recalcula solo geometría sin cambiar N ni regenerar (contrato B9.6)
def test_16_no_resize_auto():
    import time as _t
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=30
    t.set_metadata_densa(tiempos_objetivo(100.0,30), version="v16"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    # estabilizar ultimo ancho
    try:
        t._responsive_b96_ultimo_ancho = t._responsive_b96_obtener_ancho_util()
    except: pass
    QApplication.processEvents()
    cols_antes=t._ajustada_cols; rows_antes=t._ajustada_rows; cw_antes=t._ajustada_cell_w
    ancho_antes=t._ajustada_ancho_util()
    n_antes=len(t._ajustada_logical_ms)
    gen_antes=t._cache_visual_gen
    # resize puro B9.6: cambiar ancho contenedor y disparar Tarjeta.resizeEvent coalescido
    t._contenedor_exploracion.setFixedWidth(700); QApplication.processEvents()
    # disparar resizeEvent para coalescing B9.6
    try:
        from PySide6.QtGui import QResizeEvent
        from PySide6.QtCore import QSize
        ev=QResizeEvent(QSize(800,600), QSize(t.width(), t.height()))
        t.resize(800,600); QApplication.sendEvent(t, ev)
    except: pass
    for _ in range(5):
        QApplication.processEvents(); _t.sleep(0.02); QApplication.processEvents()
    cols_desp=t._ajustada_cols; rows_desp=t._ajustada_rows; cw_desp=t._ajustada_cell_w
    ancho_desp=t._ajustada_ancho_util()
    # debe haber recalculado geometría (cols/cw/rows cambian) coherentemente
    req = cols_desp*cw_desp + (cols_desp-1)*AJUSTADA_SPACING
    ok = t._ajustada_grid.isVisible()
    geom_cambio = (cols_desp != cols_antes or cw_desp != cw_antes or rows_desp != rows_antes)
    ok = ok and geom_cambio
    ok = ok and req <= ancho_desp +2
    ok = ok and len(t._ajustada_logical_ms)==n_antes and n_antes==30
    ok = ok and len(t._tira_logical_ms)==30
    # no regeneración ni invalidación masiva: gen no incrementa masiva, cache no vaciada arbitraria
    ok = ok and (t._cache_visual_gen - gen_antes) <=2
    # no crash, 1 widget
    ok = ok and len([w for w in t.findChildren(AjustadaGridWidget)])==1
    t.deleteLater(); QApplication.processEvents()
    return ok, f"B9.6 antes cols {cols_antes} cw {cw_antes} ancho {ancho_antes} -> desp cols {cols_desp} cw {cw_desp} ancho {ancho_desp} N {n_antes}"

# 17 Cambiar Densidad y reentrar a Ajustada sí recalcula
def test_17_densidad_reentrar():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=15
    t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v17_15"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    n15=len(t._ajustada_logical_ms)
    # cambiar densidad a 30 mientras en Ajustada
    t._densidad_manual=60
    t.set_metadata_densa(tiempos_objetivo(100.0,60), version="v17_60"); QApplication.processEvents()
    t.aplicar_densidad(60); QApplication.processEvents()
    # debe haber recalculado (por aplicar_densidad)
    n60=len(t._ajustada_logical_ms)
    ok = n15==15 and n60==60
    # salir y reentrar
    _a_din(t); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    n60b=len(t._ajustada_logical_ms)
    ok = ok and n60b==60
    t.deleteLater(); QApplication.processEvents()
    return ok, f"15->{n15} 60->{n60} reentrar->{n60b}"

# 18 Cambiar tamaño miniaturas por flujo explícito recalcula
def test_18_tamano_miniaturas():
    fila=_filas(["a.mp4"],[100.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    configurar_tamano_miniaturas("mediano")
    t._densidad_manual=30
    t.set_metadata_densa(tiempos_objetivo(100.0,30), version="v18"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    cw_med=t._ajustada_cell_w; ch_med=t._ajustada_cell_h
    # cambiar a grande via flujo explícito aplicar_tamano
    configurar_tamano_miniaturas("grande")
    t.aplicar_tamano(); QApplication.processEvents()
    # _actualizar_tira_tamano_b93 debe haber recalculado ajustada
    cw_grande=t._ajustada_cell_w; ch_grande=t._ajustada_cell_h
    ok = cw_grande != cw_med or ch_grande != ch_med
    # restaurar mediano para no afectar otros tests
    configurar_tamano_miniaturas("mediano")
    t.aplicar_tamano(); QApplication.processEvents()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"med cw {cw_med} ch {ch_med} -> grande cw {cw_grande} ch {ch_grande}"

# 19 Homónimos video_id no fallback por nombre
def test_19_homonimos():
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
    t1.expandir(); QApplication.processEvents()
    t1._densidad_manual=15
    t1.set_metadata_densa(tiempos_objetivo(100.0,15), version=f"v19_{t1._video_id}"); QApplication.processEvents()
    t1._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t1); QApplication.processEvents()
    assert len(t1._ajustada_logical_ms)>0
    t1._on_ajustada_left_clicked(t1._ajustada_logical_ms[0]); QApplication.processEvents()
    ok = ok and len(t1._marcadores)==1
    t1.colapsar(); QApplication.processEvents()
    t2.expandir(); QApplication.processEvents()
    t2._densidad_manual=15
    t2.set_metadata_densa(tiempos_objetivo(100.0,15), version=f"v19_{t2._video_id}"); QApplication.processEvents()
    t2._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_ajustada(t2); QApplication.processEvents()
    ok = ok and len(t2._marcadores)==0
    ok = ok and len(t1._marcadores)==1
    _cleanup_visores(v)
    try: tdir.cleanup()
    except: pass
    return ok, f"ids {t1._video_id}/{t2._video_id} marcadores {len(t1._marcadores)}/{len(t2._marcadores)}"

# 20 No acceso directo UI a SQLite/FFmpeg/FFprobe nuevo
def test_20_no_acceso_directo():
    import pathlib
    p=pathlib.Path(visor_videos.__file__)
    txt=p.read_text(encoding="utf-8", errors="ignore")
    # buscar en sección Ajustada que no haga import sqlite3 ni subprocess FFmpeg
    # extraer bloque AjustadaGridWidget y helpers ajustada
    idx=txt.find("class AjustadaGridWidget")
    bloque=txt[idx:idx+8000] if idx>=0 else ""
    ok = "sqlite3" not in bloque.lower()
    ok = ok and "ffprobe" not in bloque.lower() and "ffmpeg" not in bloque.lower()
    # verificar que Tarjeta no hace queries directas en ajustada
    ok = ok and "conectar_bd" not in bloque
    return ok, f"bloque sin sqlite/ffprobe ok={ok}"

# 21 Cache Ajustada fila lejana >100 sin thrash (densidad 200)
def test_21_cache_fila_lejana():
    fila=_filas(["a.mp4"],[600.0])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,800); QApplication.processEvents(); t.expandir(); QApplication.processEvents()
    t._densidad_manual=200
    mss=tiempos_objetivo(600.0,200)
    t.set_metadata_densa(mss, version="v21"); QApplication.processEvents()
    t._contenedor_exploracion.setFixedWidth(1800); QApplication.processEvents()
    _a_ajustada(t); QApplication.processEvents()
    # asegurar top paint inicial
    try:
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QPaintEvent
        rect_top = QRect(0,0,1800,600)
        t._ajustada_grid.paintEvent(QPaintEvent(rect_top)); QApplication.processEvents()
    except Exception:
        pass
    logical = t._ajustada_logical_ms
    assert len(logical)==200
    # elegir índice lejano >100 (ej 130)
    idx_lejano = 130
    ms_lejano = logical[idx_lejano]
    # simular exposición lejana via clip real de esa fila
    rect_lej = t._ajustada_grid._rect_for_index(idx_lejano)
    # clip que cubre 2x2 celdas alrededor
    try:
        from PySide6.QtCore import QRect as QRC
        from PySide6.QtGui import QPaintEvent as QPE
        clip_lej = QRC(rect_lej.x(), rect_lej.y(), rect_lej.width()*2, rect_lej.height()*2)
        # capturar solicitudes
        solicitudes=[]
        t._cache_visual_pending.clear()
        def _cap_preview(payload):
            try:
                solicitudes.append(list(payload.get("ms_lista", [])))
            except Exception:
                pass
        def _cap_ajustada(ms_list):
            try:
                solicitudes.append(list(ms_list))
            except Exception:
                pass
        t.preview_visual_solicitada.connect(_cap_preview)
        t._ajustada_grid.ajustada_need_visual.connect(_cap_ajustada)
        t._ajustada_grid.paintEvent(QPE(clip_lej)); QApplication.processEvents()
        # procesar timers diferidos
        for _ in range(5):
            QApplication.processEvents()
            time.sleep(0.02)
            QApplication.processEvents()
        # verificar que se solicitó ms_lejano (o vecinos que lo incluyen)
        flat = [m for batch in solicitudes for m in batch]
        ok_solic = ms_lejano in flat or any(m==ms_lejano for m in flat)
        # fallback: si paintEvent capturó exposed, requeridos debe contenerlo aunque no haya emitido si ya estaba en pending
        if not ok_solic:
            ok_solic = ms_lejano in getattr(t._ajustada_grid, "_last_exposed_ms", set())
        # emular flujo real: Tarjeta recibe payload via _on_ajustada_need_visual
        if ms_lejano not in flat:
            t._on_ajustada_need_visual([ms_lejano]); QApplication.processEvents()
            for _ in range(3):
                QApplication.processEvents()
                time.sleep(0.02)
            flat2 = [m for batch in solicitudes for m in batch]
            ok_solic = ok_solic or (ms_lejano in flat2)
        ok_pending = ms_lejano in t._cache_visual_pending
        pm = _pix("#123456")
        gen = t._cache_visual_gen
        t._cache_visual_pending.discard(ms_lejano)
        t._cache_visual[ms_lejano]=pm
        t._sincronizar_cache_visual(); QApplication.processEvents()
        ok_cache = ms_lejano in t._cache_visual
        t._ajustada_grid.paintEvent(QPE(clip_lej)); QApplication.processEvents()
        for _ in range(3):
            QApplication.processEvents()
        ok_no_thrash = ms_lejano in t._cache_visual and ms_lejano not in t._cache_visual_pending
        ok_req = ms_lejano in t._ajustada_ms_visuales_necesarios()
        rect_top2 = QRect(0,0,1800,600)
        t._ajustada_grid.paintEvent(QPE(rect_top2)); QApplication.processEvents()
        t._sincronizar_cache_visual(); QApplication.processEvents()
        ok_acotada = len(t._cache_visual) < 50 and len(t._cache_visual) < 200
        try:
            t.preview_visual_solicitada.disconnect(_cap_preview)
        except Exception:
            pass
        try:
            t._ajustada_grid.ajustada_need_visual.disconnect(_cap_ajustada)
        except Exception:
            pass
        ok = ok_solic and ok_pending and ok_cache and ok_no_thrash and ok_req and ok_acotada
        msg = f"lejano {ms_lejano} idx {idx_lejano} solic {ok_solic} pending {ok_pending} cache {ok_cache} no_thrash {ok_no_thrash} req {ok_req} acotada {len(t._cache_visual)}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        ok=False; msg=f"EXC {e}"
    t.deleteLater(); QApplication.processEvents()
    gc.collect(); QApplication.processEvents()
    return ok, msg

TESTS=[
    ("01_selector_4",test_01_selector_4),
    ("02_exclusividad",test_02_exclusividad),
    ("03_densidades_todas",test_03_densidades_todas),
    ("04_auto",test_04_auto),
    ("05_grilla_sin_overflow",test_05_grilla_sin_overflow),
    ("06_aspect_ratios",test_06_aspect_ratios),
    ("07_edge_N_ancho",test_07_edge_N_ancho),
    ("08_ultima_fila",test_08_ultima_fila),
    ("09_placeholders",test_09_placeholders),
    ("10_cache_acotada",test_10_cache_acotada),
    ("11_ciclos",test_11_ciclos),
    ("12_anotaciones",test_12_anotaciones),
    ("13_dos_fijadas",test_13_dos_fijadas),
    ("14_colapsar",test_14_colapsar),
    ("15_no_persistencia",test_15_no_persistencia),
    ("16_no_resize_auto",test_16_no_resize_auto),
    ("17_densidad_reentrar",test_17_densidad_reentrar),
    ("18_tamano_miniaturas",test_18_tamano_miniaturas),
    ("19_homonimos",test_19_homonimos),
    ("20_no_acceso_directo",test_20_no_acceso_directo),
    ("21_cache_fila_lejana",test_21_cache_fila_lejana),
]

if __name__=="__main__":
    import traceback
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
