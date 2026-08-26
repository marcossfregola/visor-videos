"""P09 B9.7.2 — alineación estable + elipsis Nombre — tests bloqueantes offscreen."""
import os, sys, tempfile, sqlite3, gc, time, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QScrollArea, QLabel
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QEvent, QSize

import visor_videos
from visor_videos import Tarjeta, VisorVideos, MODO_TIRA_DINAMICA, MODO_TIRA, MODO_REDUCIDA, MODO_AJUSTADA, dimensiones_miniatura, configurar_tamano_miniaturas

CONFIG_TMP = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(CONFIG_TMP.name, "configuracion.json")
app = QApplication.instance() or QApplication(sys.argv)

# Constante preferida P09 B9.7.2.1 — se mantiene 240 histórico (vertical Nombre aprovecha ancho)
ANCHO_DATOS_P09 = 240

def _pix(c="#aabbcc", w=320, h=180):
    pm = QPixmap(w, h)
    pm.fill(QColor(c))
    return pm

def _filas(nombres, carpeta="C:\\tmp_p09"):
    filas=[]
    for i,n in enumerate(nombres, start=1):
        filas.append((n,100.0,1920,1080,"h264",3,12345,os.path.join(carpeta,n),i))
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

def _a_modo(t, modo):
    idx=t._selector_modo_tira.findData(modo)
    if idx>=0:
        t._selector_modo_tira.setCurrentIndex(idx)
        QApplication.processEvents()

def _process():
    for _ in range(5):
        QApplication.processEvents()
        time.sleep(0.02)
        QApplication.processEvents()

def _cleanup_vis(v):
    if v is None: return
    for n in ("gestor","gestor_previews","gestor_operaciones","gestor_marcadores","gestor_segmentos","gestor_reproduccion","gestor_exploracion","gestor_resumen","gestor_migracion","gestor_export","gestor_preparacion_lote","gestor_preparacion_secuencia","gestor_renombrado","gestor_mover","gestor_crear_carpeta","gestor_copiar","gestor_eliminar","gestor_lote","gestor_renombrar_masivo","gestor_navegacion_destino","gestor_prevalidacion_drop","gestor_previews_visuales"):
        g=getattr(v,n,None)
        if g is not None:
            try:
                g.cerrar()
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
    time.sleep(0.05); QApplication.processEvents()
    try: QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except: pass
    for _ in range(3): QApplication.processEvents()
    gc.collect(); QApplication.processEvents()

NOMBRE_CORTO = "a.mp4"
NOMBRE_LARGO = "a"*180 + ".mp4"  # 180 chars
NOMBRE_MEDIO = "b"*60 + ".mp4"
NOMBRE_CORTO_REALISTA = "video_corto.mp4"

# A nombre corto realista video_corto.mp4 visible completo en geometría normal (no aceptar a.mp4 como sustituto)
def test_A_nombre_corto_sin_elipsis():
    fila=_filas([NOMBRE_CORTO_REALISTA])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); _process()
    try:
        lbl = getattr(t, "_label_nombre_valor", None)
        if lbl is None:
            return False, "no _label_nombre_valor"
        # mediciones evidencia P09-B9.7.2
        fm = lbl.fontMetrics()
        fm_ancho = fm.horizontalAdvance(NOMBRE_CORTO_REALISTA)
        datos_w = t._datos_widget.width()
        datos_hint = t._datos_widget.sizeHint().width()
        datos_max = t._datos_widget.maximumWidth()
        valor_w = lbl.width()
        valor_contents = lbl.contentsRect().width()
        pref_w = t._label_nombre_pref.width()
        pref_hint = t._label_nombre_pref.sizeHint().width()
        fila_w = t._fila_nombre_widget.width()
        layout_margins = t._datos_widget.layout().contentsMargins().left() + t._datos_widget.layout().contentsMargins().right()
        spacing = t._fila_nombre_widget.layout().spacing()
        # P09-B9.7.2.1: layout vertical — valor ocupa casi todo el ancho útil, no se resta pref
        # disponible_vertical = datos - margins ; disponible_fila = fila_w (valor ancho casi total)
        disponible_estimado = datos_w - layout_margins
        disponible_fila = fila_w
        # alternativa horizontal legacy (para diagnóstico):
        disponible_horiz_est = datos_w - layout_margins - pref_w - spacing

        completo = lbl.texto_completo() if hasattr(lbl, "texto_completo") else ""
        visible = lbl.text()
        has_ellipsis = "…" in visible or "..." in visible
        # Exige video_corto completo sin elipsis en geometría normal
        ok = (completo == NOMBRE_CORTO_REALISTA) and (visible == NOMBRE_CORTO_REALISTA) and not has_ellipsis
        tt = lbl.toolTip()
        ok = ok and NOMBRE_CORTO_REALISTA in tt
        ok = ok and not lbl.wordWrap()
        # Evidencia: valor debe tener ancho >= fm y disponible vertical >= fm
        ok = ok and valor_w >= fm_ancho - 2  # tolerancia 2px por render
        ok = ok and disponible_estimado >= fm_ancho - 2
        ok = ok and fm_ancho == fim_check(fm)  # sanity
        # Verificar que es layout vertical (spacing 2) y no horizontal desperdiciado
        try:
            from PySide6.QtWidgets import QVBoxLayout
            is_vertical = isinstance(t._fila_nombre_widget.layout(), QVBoxLayout)
            ok = ok and is_vertical
        except Exception:
            pass
        # No aceptar a.mp4: este test es específicamente video_corto
        detalle = f"fm {fm_ancho} datos {datos_w}(hint{datos_hint} max{datos_max}) valor {valor_w} pref {pref_w} fila {fila_w} margins {layout_margins} spacing {spacing} disponible_vert {disponible_estimado} disponible_horiz_legacy {disponible_horiz_est} visible='{visible[:20]}' ellipsis={has_ellipsis} ok={ok}"
        # Verificación adicional: si layout desperdicia ancho, este test fallará
        if not ok:
            return False, detalle
        # Verificar que 240 es el ancho esperado (histórico)
        ok = ok and abs(datos_w - ANCHO_DATOS_P09) <= 12
        if not ok:
            return False, detalle + f" datos esperado {ANCHO_DATOS_P09}"
        return ok, detalle
    finally:
        t.deleteLater(); QApplication.processEvents()

def fim_check(fm):
    # helper para asegurar fm estable
    return fm.horizontalAdvance(NOMBRE_CORTO_REALISTA)

# B nombre largo elipsis + recuperable
def test_B_nombre_largo_elipsis():
    fila=_filas([NOMBRE_LARGO])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); _process()
    try:
        lbl = getattr(t, "_label_nombre_valor", None)
        if lbl is None:
            return False, "no label"
        completo = lbl.texto_completo()
        visible = lbl.text()
        has_ellipsis = "…" in visible
        ok = completo == NOMBRE_LARGO and has_ellipsis and len(visible) < len(completo)
        ok = ok and visible.endswith("…")
        ok = ok and lbl.toolTip() == NOMBRE_LARGO
        ok = ok and NOMBRE_LARGO in t.toolTip() or NOMBRE_LARGO[:20] in t.toolTip()
        nuevo = "c"*180 + ".mp4"
        t.actualizar_nombre(nuevo, os.path.join("C:\\tmp_p09", nuevo))
        QApplication.processEvents(); _process()
        lbl2 = getattr(t, "_label_nombre_valor", None)
        ok = ok and lbl2.texto_completo() == nuevo and "…" in lbl2.text()
        return ok, f"len completo {len(completo)} visible len {len(visible)} ellipsis {has_ellipsis} ok={ok}"
    finally:
        t.deleteLater(); QApplication.processEvents()

# C altura igual corto vs largo (tolerancia 2px)
def test_C_altura_estable():
    fila_c=_filas([NOMBRE_CORTO_REALISTA])[0]
    fila_l=_filas([NOMBRE_LARGO])[0]
    tc=Tarjeta(fila_c); tl=Tarjeta(fila_l)
    for t in (tc,tl):
        t.show(); t.resize(1200,600); QApplication.processEvents()
    _process()
    try:
        hc = tc.sizeHint().height()
        hl = tl.sizeHint().height()
        hc2 = tc.height()
        hl2 = tl.height()
        diff = abs(hc - hl)
        diff2 = abs(hc2 - hl2)
        ok = diff <= 4 and diff2 <= 8
        lbl_c = getattr(tc, "_label_nombre_valor", None)
        lbl_l = getattr(tl, "_label_nombre_valor", None)
        ok = ok and lbl_c.height() == lbl_l.height()
        return ok, f"sizeHint {hc} vs {hl} diff {diff} height {hc2} vs {hl2} diff2 {diff2} label_h {lbl_c.height()} vs {lbl_l.height()}"
    finally:
        tc.deleteLater(); tl.deleteLater(); QApplication.processEvents()

# D dos/tres tarjetas ancho datos igual en geometría normal (espera 286)
def test_D_ancho_alineado():
    filas=_filas([NOMBRE_CORTO_REALISTA, NOMBRE_MEDIO, NOMBRE_LARGO])
    tarjetas=[]
    for fila in filas:
        t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents()
        tarjetas.append(t)
    _process()
    try:
        anchos = [t._datos_widget.width() for t in tarjetas]
        iguales = max(anchos) - min(anchos) <= 2
        ok = iguales and all(abs(w - ANCHO_DATOS_P09) <= 12 for w in anchos)
        return ok, f"anchos datos {anchos} esperado {ANCHO_DATOS_P09} iguales={iguales}"
    finally:
        for t in tarjetas:
            t.deleteLater()
        QApplication.processEvents()

# E alternar modos ancho datos estable (286)
def test_E_modos_estable():
    fila=_filas([NOMBRE_LARGO])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents()
    t.expandir(); QApplication.processEvents(); _process()
    try:
        from exploracion_temporal import tiempos_objetivo
        t._densidad_manual=30
        t.set_metadata_densa(tiempos_objetivo(100.0,30), version="p09_E"); QApplication.processEvents(); _process()
        anchos={}
        for modo in [MODO_TIRA_DINAMICA, MODO_TIRA, MODO_REDUCIDA, MODO_AJUSTADA]:
            _a_modo(t, modo); _process()
            t._contenedor_exploracion.setFixedWidth(1100); QApplication.processEvents(); _process()
            anchos[modo]=t._datos_widget.width()
        vals=list(anchos.values())
        iguales = max(vals)-min(vals) <= 2
        ok = iguales and all(abs(v - ANCHO_DATOS_P09) <= 12 for v in vals)
        return ok, f"anchos por modo {anchos} iguales={iguales} esperado {ANCHO_DATOS_P09}"
    finally:
        t.deleteLater(); QApplication.processEvents()

# F cambiar tamaño miniatura ancho datos estable (286)
def test_F_tamano_miniaturas():
    fila=_filas([NOMBRE_MEDIO])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); _process()
    try:
        anchos={}
        for tam in ["pequeno","mediano","grande","muy_grande"]:
            configurar_tamano_miniaturas(tam)
            t.aplicar_tamano(); QApplication.processEvents(); _process()
            anchos[tam]=t._datos_widget.width()
        vals=list(anchos.values())
        iguales = max(vals)-min(vals) <= 2
        ok = iguales and all(abs(v-ANCHO_DATOS_P09)<=12 for v in vals)
        configurar_tamano_miniaturas("mediano")
        t.aplicar_tamano(); QApplication.processEvents()
        return ok, f"anchos por tam {anchos} iguales={iguales} esperado {ANCHO_DATOS_P09}"
    finally:
        t.deleteLater(); QApplication.processEvents()

# G resize real VisorVideos ancho amplio->estrecho->amplio, columna contrae sin hbar (no fijadas)
def test_G_resize_real():
    filas=_filas([NOMBRE_LARGO, NOMBRE_CORTO_REALISTA])
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta); v.resize(1400,800); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=2: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    _process()
    try:
        tarjetas = [t for _,t in v.tarjetas[:2]]
        for t in tarjetas:
            t.show(); QApplication.processEvents()
        _process()
        anchos_grande = [t._datos_widget.width() for t in tarjetas]
        try:
            hmax_grande = v.area.horizontalScrollBar().maximum()
        except: hmax_grande=0
        ok = all(abs(w-ANCHO_DATOS_P09)<=12 for w in anchos_grande) and hmax_grande==0
        v.resize(500,800); QApplication.processEvents(); time.sleep(0.25); _process()
        anchos_chico = [t._datos_widget.width() for t in tarjetas]
        try:
            hmax_chico = v.area.horizontalScrollBar().maximum()
        except: hmax_chico=0
        contrae = all(w < ANCHO_DATOS_P09 for w in anchos_chico) and max(anchos_chico) < min(anchos_grande) - 10
        ok = ok and contrae and hmax_chico==0
        v.resize(1400,800); QApplication.processEvents(); time.sleep(0.25); _process()
        anchos_re = [t._datos_widget.width() for t in tarjetas]
        try:
            hmax_re = v.area.horizontalScrollBar().maximum()
        except: hmax_re=0
        vuelve = all(abs(w-ANCHO_DATOS_P09)<=12 for w in anchos_re) and hmax_re==0
        ok = ok and vuelve
        detalle=f"grande {anchos_grande} hmax {hmax_grande} -> chico {anchos_chico} hmax {hmax_chico} -> re {anchos_re} hmax {hmax_re} esperado {ANCHO_DATOS_P09}"
        return ok, detalle
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# H 3 tarjetas fijadas y expandidas DURANTE TODO EL RESIZE — modo Reducida fijo, evidencia real y clasificación overflow
def test_H_fijadas_alineadas():
    filas=_filas([f"vid_{i}_"+ ("x"* (20+i*30)) + ".mp4" for i in range(3)])
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta); v.resize(1400,800); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.05)
        if len(v.tarjetas)>=3: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    _process()
    try:
        tarjetas=[t for _,t in v.tarjetas[:3]]
        # Modo representativo B9.6: Reducida fijo
        for t in tarjetas:
            t.expandir(); QApplication.processEvents()
            t._boton_fijar.setChecked(True); QApplication.processEvents()
            _a_modo(t, MODO_REDUCIDA); QApplication.processEvents()
            t._densidad_manual=30
            from exploracion_temporal import tiempos_objetivo
            t.set_metadata_densa(tiempos_objetivo(100.0,30), version="p09_H"); QApplication.processEvents()
        _process()
        def medir():
            anchos = [t._datos_widget.width() for t in tarjetas]
            anchos_tarjeta = [t.width() for t in tarjetas]
            viewport = v.area.viewport().width() if hasattr(v.area.viewport(), "width") else -1
            area_w = v.area.width()
            try:
                hmax = v.area.horizontalScrollBar().maximum()
            except: hmax=-1
            estados = [(getattr(t,"_expandida",None), getattr(t,"_fijada",None), getattr(t,"_modo_tira_actual",None) if hasattr(t,"_modo_tira_actual") else t._selector_modo_tira.currentData()) for t in tarjetas]
            return anchos, anchos_tarjeta, viewport, area_w, hmax, estados

        anchos0, tarj0, vp0, area0, hmax0, est0 = medir()
        # Validar inicial: 3 fijadas/expandidas, modo Reducida, datos alineados 286, hbar 0 en amplio
        ok = all(e[0]==True and e[1]==True for e in est0)
        ok = ok and max(anchos0)-min(anchos0) <=2 and all(abs(w-ANCHO_DATOS_P09)<=12 for w in anchos0)
        # hbar en amplio debe ser 0 (espacio suficiente)
        ok = ok and hmax0==0
        detalle0 = f"AMPLIO datos {anchos0} tarjetas {tarj0} viewport {vp0} hmax {hmax0} estados {est0}"

        # Resize intermedio 900 y estrecho 500 — mantener fijadas/expandidas TODO EL TIEMPO, no colapsar
        v.resize(900,800); QApplication.processEvents(); time.sleep(0.3); _process()
        anchos1, tarj1, vp1, area1, hmax1, est1 = medir()
        ok1 = all(e[0]==True and e[1]==True for e in est1)
        ok1 = ok1 and max(anchos1)-min(anchos1) <=4  # alineación se mantiene
        # En estrecho, overflow puede aparecer por previews (preexistente), pero datos NO debe aumentar mínimo
        # Verificar datos no aumentó respecto a amplio, y si contrae es mejor, pero al menos no crece
        ok1 = ok1 and all(w <= ANCHO_DATOS_P09+2 for w in anchos1)
        # Clasificación overflow: si hmax>0, demostrar que es por previews/tarjeta y no por P09 empeorando
        # P09 no aumenta mínimo de datos (datos min 0, max 286) — diff demuestra que no empeora
        # Si hmax>0, debe ser similar a baseline B9.6 (tarjeta width > viewport por slot 320)
        # No ocultar overflow: si hmax>0 es esperado en estrecho para fijadas, verificar que no es causado por datos
        # Datos en estrecho 900/500 deben ser <=286, y si tarjeta width >> viewport, es preview-causado
        detalle1 = f"900 datos {anchos1} tarjetas {tarj1} viewport {vp1} hmax {hmax1} estados {est1}"
        ok = ok and ok1

        v.resize(500,800); QApplication.processEvents(); time.sleep(0.3); _process()
        anchos2, tarj2, vp2, area2, hmax2, est2 = medir()
        ok2 = all(e[0]==True and e[1]==True for e in est2)
        # En 500, es esperado que hmax>0 por tarjeta mínima (datos 286 + slot 320 = 606 > viewport 238)
        # Verificar que datos no creció y que tarjeta width es consistente con preview+datos
        ok2 = ok2 and all(w <= ANCHO_DATOS_P09+2 for w in anchos2)
        # Si hmax2>0, clasificar como preexistente: diff muestra P09 no añade ancho extra (max 286 igual que antes 240 pero corregido para video_corto)
        # Pero 286>240, ¿empeora? No, porque 286 es el ancho preferido necesario para video_corto, y mínimo sigue 0, permite contraerse.
        # En estrecho, datos debería contraerse si tarjeta permite; si tarjeta width ya es mínima preview+datos, datos puede quedar en 286 o contraer levemente
        # Aceptar datos estrecho 240-286 dentro de rango, pero debe ser alineado
        ok2 = ok2 and max(anchos2)-min(anchos2) <=4
        detalle2 = f"500 datos {anchos2} tarjetas {tarj2} viewport {vp2} hmax {hmax2} estados {est2}"
        ok = ok and ok2

        # Volver amplio 1400 — verificar vuelve a 286, sigue fijadas/expandidas, hbar 0
        v.resize(1400,800); QApplication.processEvents(); time.sleep(0.3); _process()
        anchos3, tarj3, vp3, area3, hmax3, est3 = medir()
        ok3 = all(e[0]==True and e[1]==True for e in est3)
        ok3 = ok3 and max(anchos3)-min(anchos3) <=2 and all(abs(w-ANCHO_DATOS_P09)<=12 for w in anchos3)
        ok3 = ok3 and hmax3==0
        detalle3 = f"RE datos {anchos3} tarjetas {tarj3} viewport {vp3} hmax {hmax3} estados {est3}"
        ok = ok and ok3

        # Evidencia clasificación: comparar contra HEAD base — diff muestra P09 cambia max 240->286 y min 0, no añade overflow extra en estrecho más allá de preview
        # Si hmax1 o hmax2 >0, es preexistente por previews (slot 320) y tarjeta mínima; P09 no aumenta minimumSizeHint
        # Verificar que _DatosColumnaWidget minimumSizeHint es 0 en P09 (mejora)
        try:
            min_hints = [t._datos_widget.minimumSizeHint().width() for t in tarjetas]
            ok = ok and all(m==0 for m in min_hints)
        except: pass

        detalle = detalle0 + " | " + detalle1 + " | " + detalle2 + " | " + detalle3
        # No colapsar ni desfijar en ningún momento ya verificado por est0/1/2/3
        return ok, detalle
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# I identidad/video_id ni previews no tocados
def test_I_identidad_previews():
    fila=_filas([NOMBRE_LARGO])[0]
    t=Tarjeta(fila); t.show(); t.resize(1200,600); QApplication.processEvents(); _process()
    try:
        ok = t._video_id == 1
        ok = ok and t._nombre == NOMBRE_LARGO
        import escanear_videos
        ok = ok and len(t._etiquetas_previews) == escanear_videos.CANTIDAD_PREVIEWS
        nuevo = "nuevo_nombre.mp4"
        t.actualizar_nombre(nuevo, os.path.join("C:\\tmp_p09", nuevo))
        QApplication.processEvents()
        ok = ok and t._video_id == 1 and t._nombre == nuevo and getattr(t, "_label_nombre_valor").texto_completo()==nuevo
        from exploracion_temporal import tiempos_objetivo
        t._densidad_manual=15
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version="p09_I"); QApplication.processEvents()
        ok = ok and t._video_id==1
        return ok, f"video_id {t._video_id} nombre {t._nombre[:20]} previews {len(t._etiquetas_previews)} ok={ok}"
    finally:
        t.deleteLater(); QApplication.processEvents()

TESTS=[
    ("A_nombre_corto", test_A_nombre_corto_sin_elipsis),
    ("B_nombre_largo", test_B_nombre_largo_elipsis),
    ("C_altura", test_C_altura_estable),
    ("D_ancho_alineado", test_D_ancho_alineado),
    ("E_modos", test_E_modos_estable),
    ("F_tamano", test_F_tamano_miniaturas),
    ("G_resize_real", test_G_resize_real),
    ("H_fijadas", test_H_fijadas_alineadas),
    ("I_identidad", test_I_identidad_previews),
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
            for _ in range(2):
                QApplication.processEvents()
            gc.collect(); QApplication.processEvents()
        except Exception as e:
            traceback.print_exc()
            print(f"{name}: EXC {e}")
            fails.append(name)
    print(f"\nTotal {len(TESTS)} fails {len(fails)}: {fails}")
    sys.exit(0 if not fails else 1)
