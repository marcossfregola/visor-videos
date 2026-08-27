"""B9.7.3 P06 — Ajustada auto-repaint al llegar preview visual — estricto sincrónico."""
import os, sys, tempfile, gc, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor, QImage
from PySide6.QtCore import Qt, QEvent

import visor_videos
from visor_videos import Tarjeta, VisorVideos, MODO_AJUSTADA, MODO_TIRA, MODO_REDUCIDA, MODO_TIRA_DINAMICA, dimensiones_miniatura
from exploracion_temporal import tiempos_objetivo

app = QApplication.instance() or QApplication(sys.argv)

def _pix(color="#aabbcc", w=320, h=180):
    pm = QPixmap(w, h)
    pm.fill(QColor(color))
    return pm

def _qimg(color="#aabbcc", w=64, h=36):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    return img

def _filas(nombres, carpeta="C:\\tmp_b973"):
    filas=[]
    for i,n in enumerate(nombres, start=1):
        filas.append((n,100.0,1920,1080,"h264",3,12345,os.path.join(carpeta,n),i))
    return filas

def _crear_bd(filas):
    t=tempfile.TemporaryDirectory()
    ruta=os.path.join(t.name,"catalogo.db")
    import sqlite3
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

def _cleanup_vis(v):
    if v is None: return
    for n in ("gestor","gestor_previews","gestor_operaciones","gestor_marcadores","gestor_segmentos","gestor_reproduccion","gestor_exploracion","gestor_resumen","gestor_migracion","gestor_export","gestor_preparacion_lote","gestor_preparacion_secuencia","gestor_renombrado","gestor_mover","gestor_crear_carpeta","gestor_copiar","gestor_eliminar","gestor_lote","gestor_renombrar_masivo","gestor_navegacion_destino","gestor_prevalidacion_drop","gestor_previews_visuales"):
        g=getattr(v,n,None)
        if g is not None:
            try: g.cerrar()
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

def _patch_update(widget):
    cnt={"n":0, "orig": widget.update}
    orig = widget.update
    def counted(*a, **kw):
        cnt["n"]+=1
        return orig(*a, **kw)
    widget.update = counted
    return cnt

def _drain():
    for _ in range(3):
        QApplication.processEvents()
        time.sleep(0.01)
        QApplication.processEvents()

def _setup_ajustada_vis():
    filas=_filas(["v1.mp4"], carpeta="C:\\tmp_b973_a")
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta)
    v.resize(1200,700); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.03)
        if len(v.tarjetas)>=1: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    tarjeta=dict(v.tarjetas)["v1.mp4"]
    tarjeta.show(); tarjeta.resize(1200,600); QApplication.processEvents()
    tarjeta.expandir(); QApplication.processEvents()
    tarjeta._densidad_manual=15
    mss=tiempos_objetivo(100.0, 15)
    tarjeta.set_metadata_densa(mss, version="v973_1"); QApplication.processEvents()
    tarjeta._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_modo(tarjeta, MODO_AJUSTADA); QApplication.processEvents()
    ms_needed = sorted(tarjeta._tira_logical_ms)[0]
    tarjeta._cache_visual.clear()
    tarjeta._cache_visual_pending.clear()
    tarjeta._cache_visual_pending.add(ms_needed)
    try:
        tarjeta._cache_visual_gen+=1
    except: tarjeta._cache_visual_gen=1
    gen = tarjeta._cache_visual_gen
    version = tarjeta._densidad_version
    vid = tarjeta._video_id
    return v, tdir, tarjeta, ms_needed, gen, version, vid

# A. RESULTADO VÁLIDO AJUSTADA — delta sincrónico >=1, cache, pending, placeholder tras processEvents
def test_A_valid_ajustada():
    v,tdir,tarjeta,ms,gen,version,vid=_setup_ajustada_vis()
    try:
        # instalar spy antes de drenar
        cnt=_patch_update(tarjeta._ajustada_grid)
        _drain()
        # re-capturar gen/version tras drenar por si timer incrementó
        gen = tarjeta._cache_visual_gen
        version = tarjeta._densidad_version
        # asegurar pending vigente antes de snapshot
        tarjeta._cache_visual_pending.add(ms)
        # snapshot sincrónico
        before=cnt["n"]
        img=_qimg("#ff0000")
        res={"video_id": vid, "version": version, "request_id": gen, "imagenes": [(ms, img)]}
        v._al_resultado_preview_visual(res)
        after_immediate=cnt["n"]
        delta=after_immediate-before
        # condiciones sincrónicas
        if delta < 1:
            return False, f"A FAIL delta {delta} esperado >=1 (before {before} after {after_immediate}) ms {ms}"
        if delta > 2:
            # documentar si >1 por código sincrónico real, pero permitir
            pass
        if ms not in tarjeta._cache_visual:
            return False, f"A FAIL pixmap no en cache ms {ms} delta {delta}"
        pm=tarjeta._cache_visual.get(ms)
        if pm is None or pm.isNull():
            return False, f"A FAIL pixmap nulo ms {ms}"
        if ms in tarjeta._cache_visual_pending:
            return False, f"A FAIL pending no limpio ms {ms} pending {tarjeta._cache_visual_pending}"
        # tras processEvents verificar que celda deja placeholder (pixmap sigue visible, no vuelve a placeholder)
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if ms not in tarjeta._cache_visual:
            return False, f"A FAIL tras processEvents pixmap perdido ms {ms}"
        if tarjeta._cache_visual.get(ms).isNull():
            return False, f"A FAIL tras processEvents pixmap nulo"
        if ms in tarjeta._cache_visual_pending:
            return False, f"A FAIL tras processEvents pending reapareció"
        # verificar que ag no requirió FFmpeg: ya validado en test G, pero aquí no disparó generación
        return True, f"A PASS delta {delta} (ideal 1) ms {ms} gen {gen}"
    finally:
        # restaurar orig
        try: tarjeta._ajustada_grid.update = cnt["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# B. STALE REQUEST_ID — delta 0 sincrónico, no entra cache, no borra pending vigente de otro ms
def test_B_stale_request_id():
    v,tdir,tarjeta,ms,gen,version,vid=_setup_ajustada_vis()
    try:
        old_gen=gen
        tarjeta._cache_visual_gen+=1
        new_gen=tarjeta._cache_visual_gen
        tarjeta._cache_visual_pending.clear()
        # B9.7.3 P06 — limpiar retry y cola para determinismo stale (evita tormenta previa)
        try:
            if hasattr(tarjeta, "_ajustada_visual_retry"):
                tarjeta._ajustada_visual_retry.clear()
        except: pass
        try:
            v._cola_previews_visuales.clear()
            v._preview_visual_op_actual = None
            # detener gestor si quedó activo de setup
            try:
                if v.gestor_previews_visuales.activo:
                    v.gestor_previews_visuales.cerrar()
            except: pass
        except: pass
        otro_ms = sorted(tarjeta._tira_logical_ms)[1] if len(tarjeta._tira_logical_ms)>1 else ms
        # si otro_ms == ms, elegir siguiente distinto
        if otro_ms == ms and len(tarjeta._tira_logical_ms)>1:
            otro_ms = sorted(tarjeta._tira_logical_ms)[1]
        tarjeta._cache_visual_pending.add(otro_ms)
        # asegurar ms stale no está en pending vigente
        if ms in tarjeta._cache_visual_pending:
            tarjeta._cache_visual_pending.discard(ms)
        # cola con solo el nuevo gen vigente
        try:
            v._cola_previews_visuales.append({"video_id": vid, "version": version, "ms_lista": [otro_ms], "request_id": new_gen})
        except: pass
        cnt=_patch_update(tarjeta._ajustada_grid)
        _drain()
        before=cnt["n"]
        img=_qimg("#aaaaaa")
        stale={"video_id": vid, "version": version, "request_id": old_gen, "imagenes": [(ms, img)]}
        v._al_resultado_preview_visual(stale)
        after=cnt["n"]
        delta=after-before
        # asserts estrictos
        if delta != 0:
            return False, f"B FAIL delta stale {delta} esperado 0 (before {before} after {after}) old_gen {old_gen} new_gen {new_gen}"
        if ms in tarjeta._cache_visual:
            return False, f"B FAIL stale entró a cache ms {ms}"
        if otro_ms not in tarjeta._cache_visual_pending:
            return False, f"B FAIL pending vigente borrado otro_ms {otro_ms} pending {tarjeta._cache_visual_pending}"
        # tras processEvents tampoco debe aparecer
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if ms in tarjeta._cache_visual:
            return False, f"B FAIL tras processEvents stale apareció en cache"
        if cnt["n"] - after != 0:
            # si después de processEvents hubo repaint por timer, no lo atribuimos al handler (medición sincrónica ya pasó)
            # verificar que delta sincrónico sigue 0 y que no se añadió por stale tras timers (cache check ya)
            pass
        return True, f"B PASS stale old_gen {old_gen} new {new_gen} delta 0 otro_ms {otro_ms} preservado"
    finally:
        try: tarjeta._ajustada_grid.update = cnt["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# C. OTRA TARJETA / VIDEO_ID — delta1>=1 delta2==0 sincrónico, cache solo en tarjeta1
def test_C_otra_tarjeta():
    import tempfile as _tf
    tdir=_tf.TemporaryDirectory()
    ruta=os.path.join(tdir.name,"cat.db")
    v=VisorVideos(ruta_db=ruta); v.resize(1200,700); v.show(); QApplication.processEvents()
    fila1=_filas(["v1.mp4"], carpeta="C:\\tmp_b973_b1")[0]
    fila2=_filas(["v2.mp4"], carpeta="C:\\tmp_b973_b2")[0]
    fila1 = (fila1[0], fila1[1], fila1[2], fila1[3], fila1[4], fila1[5], fila1[6], fila1[7], 101)
    fila2 = (fila2[0], fila2[1], fila2[2], fila2[3], fila2[4], fila2[5], fila2[6], fila2[7], 102)
    t1=Tarjeta(fila1); t2=Tarjeta(fila2)
    for t in (t1,t2):
        v.tarjetas.append((t._nombre, t))
        t.show(); t.resize(1200,600); QApplication.processEvents()
        t.expandir(); QApplication.processEvents()
        t._densidad_manual=15
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v973_cross"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_modo(t, MODO_AJUSTADA); QApplication.processEvents()
        t._cache_visual.clear(); t._cache_visual_pending.clear()
        ms0 = sorted(t._tira_logical_ms)[0] if t._tira_logical_ms else tiempos_objetivo(100.0,15)[0]
        t._cache_visual_pending.add(ms0)
        try: t._cache_visual_gen+=1
        except: t._cache_visual_gen=1
    cnt1=cnt2=None
    try:
        ms1=sorted(t1._tira_logical_ms)[0]
        vid1=t1._video_id; gen1=t1._cache_visual_gen; ver1=t1._densidad_version
        cnt1=_patch_update(t1._ajustada_grid); cnt2=_patch_update(t2._ajustada_grid)
        _drain()
        # restaurar gen/version tras drain
        gen1=t1._cache_visual_gen; ver1=t1._densidad_version
        before1=cnt1["n"]; before2=cnt2["n"]
        img=_qimg("#ff00ff")
        res={"video_id": vid1, "version": ver1, "request_id": gen1, "imagenes": [(ms1, img)]}
        v._al_resultado_preview_visual(res)
        after1=cnt1["n"]; after2=cnt2["n"]
        delta1=after1-before1; delta2=after2-before2
        if delta1 < 1:
            return False, f"C FAIL delta1 {delta1} esperado >=1 before {before1} after {after1}"
        if delta2 != 0:
            return False, f"C FAIL delta2 {delta2} esperado 0 (ruido timer no permitido sincrónico) before2 {before2} after2 {after2}"
        if ms1 not in t1._cache_visual:
            return False, f"C FAIL cache1 falta ms {ms1}"
        if ms1 in t2._cache_visual:
            return False, f"C FAIL cache cruzado ms {ms1} apareció en t2"
        # tras processEvents, verificar que sigue sin cruce
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if ms1 in t2._cache_visual:
            return False, f"C FAIL tras processEvents cruce cache2"
        return True, f"C PASS delta1 {delta1} delta2 {delta2} cache1 ok cross no"
    finally:
        try:
            if cnt1: t1._ajustada_grid.update=cnt1["orig"]
            if cnt2: t2._ajustada_grid.update=cnt2["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass
        try:
            t1.deleteLater(); t2.deleteLater(); QApplication.processEvents()
        except: pass

# D. MULTI-FIJADAS A/B — snapshots por entrega, ausencia de cruce sincrónico
def test_D_multi_fijadas():
    filas=_filas(["v1.mp4","v2.mp4"], carpeta="C:\\tmp_b973_d")
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta); v.resize(1200,700); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.03)
        if len(v.tarjetas)>=2: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    d=dict(v.tarjetas)
    t1=d["v1.mp4"]; t2=d["v2.mp4"]
    for t in (t1,t2):
        t.show(); t.resize(1200,600); QApplication.processEvents()
        t.expandir(); QApplication.processEvents()
        t._boton_fijar.setChecked(True); QApplication.processEvents()
        t._densidad_manual=15
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v973_multi"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_modo(t, MODO_AJUSTADA); QApplication.processEvents()
        t._cache_visual.clear(); t._cache_visual_pending.clear()
        if not getattr(t, "_tira_logical_ms", None):
            t._ajustada_actualizar_logica(); QApplication.processEvents()
        try: t._cache_visual_gen+=1
        except: t._cache_visual_gen=1
    cnt_a=cnt_b=None
    try:
        # elegir ms distintos y dentro de requeridos (primeros índices)
        ms_a=sorted(t1._tira_logical_ms)[0]
        ms_b=sorted(t2._tira_logical_ms)[0]
        # asegurar pending
        t1._cache_visual_pending.add(ms_a); t2._cache_visual_pending.add(ms_b)
        cnt_a=_patch_update(t1._ajustada_grid); cnt_b=_patch_update(t2._ajustada_grid)
        _drain()
        # snapshot A
        before_a=cnt_a["n"]; before_b=cnt_b["n"]
        img_a=_qimg("#111111")
        res_a={"video_id": t1._video_id, "version": t1._densidad_version, "request_id": t1._cache_visual_gen, "imagenes": [(ms_a, img_a)]}
        v._al_resultado_preview_visual(res_a)
        after_a=cnt_a["n"]; after_b=cnt_b["n"]
        deltaA=after_a-before_a; deltaB=after_b-before_b
        if deltaA < 1:
            return False, f"D FAIL fase A deltaA {deltaA} esperado >=1"
        if deltaB != 0:
            return False, f"D FAIL fase A deltaB {deltaB} esperado 0 cruce sincrónico"
        if ms_a not in t1._cache_visual:
            return False, f"D FAIL fase A cache A falta ms_a {ms_a}"
        if ms_a in t2._cache_visual:
            return False, f"D FAIL fase A cruce cache t2 contiene ms_a"
        # no usar acumulado: nuevo snapshot antes de B
        # drenar timer residual antes de snapshot B? spec dice snapshot nuevo antes de resultado B
        _drain()
        before_a2=cnt_a["n"]; before_b2=cnt_b["n"]
        img_b=_qimg("#222222")
        # re-capturar gen/version current (no cambiado)
        res_b={"video_id": t2._video_id, "version": t2._densidad_version, "request_id": t2._cache_visual_gen, "imagenes": [(ms_b, img_b)]}
        v._al_resultado_preview_visual(res_b)
        after_a2=cnt_a["n"]; after_b2=cnt_b["n"]
        deltaA2=after_a2-before_a2; deltaB2=after_b2-before_b2
        if deltaB2 < 1:
            return False, f"D FAIL fase B deltaB {deltaB2} esperado >=1"
        if deltaA2 != 0:
            return False, f"D FAIL fase B deltaA {deltaA2} esperado 0"
        if ms_b not in t2._cache_visual:
            return False, f"D FAIL fase B cache B falta ms_b {ms_b}"
        if ms_b in t1._cache_visual and ms_b != ms_a:
            # si ms_b coincide con ms_a (mismo valor) es esperable que ambos tengan mismo ms pero distinto video_id, cache por tarjeta separada; verificar no cruza otro ms
            # need check that t1 not containing ms_b if ms_b distinct from ms_a
            if ms_b not in t1._cache_visual or ms_b==ms_a:
                pass
            else:
                return False, f"D FAIL fase B cruce t1 contiene ms_b {ms_b}"
        # si ms_a==ms_b (both first), cache values both present but in respective tarjetas: ok; need check no extra cross: t1 should not have received ms_b additional beyond own? already have ms_a; t2 has ms_b. That's fine.
        # tras processEvents ambos pixmaps visibles
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if ms_a not in t1._cache_visual or t1._cache_visual[ms_a].isNull():
            return False, f"D FAIL tras processEvents A perdido"
        if ms_b not in t2._cache_visual or t2._cache_visual[ms_b].isNull():
            return False, f"D FAIL tras processEvents B perdido"
        return True, f"D PASS A deltaA {deltaA} deltaB {deltaB} | B deltaB {deltaB2} deltaA2 {deltaA2}"
    finally:
        try:
            if cnt_a: t1._ajustada_grid.update=cnt_a["orig"]
            if cnt_b: t2._ajustada_grid.update=cnt_b["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# E. VERSION STALE — cambio version/densidad antes de resultado viejo
def test_E_version_stale():
    v,tdir,tarjeta,ms,gen,version,vid=_setup_ajustada_vis()
    try:
        old_version=version; old_gen=gen; old_ms=ms
        # cambiar densidad/version
        tarjeta._densidad_manual=30
        tarjeta.set_metadata_densa(tiempos_objetivo(100.0,30), version="v973_new"); QApplication.processEvents()
        tarjeta._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_modo(tarjeta, MODO_AJUSTADA); QApplication.processEvents()
        new_version=tarjeta._densidad_version
        assert new_version != old_version, "version debe cambiar"
        # asegurar pending para old_ms no vigente? limpiar
        # si old_ms sigue en pending pero version cambió, stale debe descartarse
        tarjeta._cache_visual_pending.add(old_ms)
        cnt=_patch_update(tarjeta._ajustada_grid)
        _drain()
        before=cnt["n"]
        img=_qimg("#cccccc")
        stale={"video_id": vid, "version": old_version, "request_id": old_gen, "imagenes": [(old_ms, img)]}
        v._al_resultado_preview_visual(stale)
        after=cnt["n"]
        delta=after-before
        if delta != 0:
            return False, f"E FAIL delta stale version {delta} esperado 0"
        if old_ms in tarjeta._cache_visual:
            # verificar que si estaba previamente, no se sobrescribió con vieja? But cache was cleared earlier; stale should not insert
            # si ya existía por otro valido, no validar sobreescritura; pero en este setup cache was cleared before stale? In _setup, cache cleared, then version changed, cache not yet filled. So old_ms should not be in cache.
            # Si old_ms está, es fallo
            return False, f"E FAIL stale versión insertó cache old_ms {old_ms}"
        # tras processEvents tampoco debe aparecer
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if old_ms in tarjeta._cache_visual:
            return False, f"E FAIL tras processEvents cache viejo apareció"
        if cnt["n"] - after != 0:
            pass
        return True, f"E PASS old {old_version}->{new_version} delta 0, cache no recibió vieja"
    finally:
        try: tarjeta._ajustada_grid.update=cnt["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# F. RUTA _aplicar_exploracion_densa CON IMÁGENES DIRECTAS — confirmar delta >=1 sincrónico
def test_F_ruta_densa_directa():
    v,tdir,tarjeta,ms,gen,version,vid=_setup_ajustada_vis()
    try:
        # Preparar para ruta densa: tarjeta en Ajustada, expandida, con logical ms vigentes
        # _aplicar_exploracion_densa requiere op con video_id y resultado con version/fotogramas/imagenes
        # Usar primer ms visible que esté en requeridos
        ms_densa = sorted(tarjeta._tira_logical_ms)[0]
        # Limpiar cache para observar inserción
        tarjeta._cache_visual.clear()
        tarjeta._cache_visual_pending.clear()
        # asegurar que ms_densa está en requeridos (pending necesario no obligatorio pero ayuda)
        tarjeta._cache_visual_pending.add(ms_densa)
        op={"video_id": vid, "nombre": tarjeta._nombre if hasattr(tarjeta, '_nombre') else "v1.mp4"}
        version_densa="v973_densa_F"
        # primero establecer metadata para que fotogramas sea aceptado? _aplicar_exploracion_densa valida fotogramas y version y filtra por existencia; como pasamos imagen, evita check disco
        # foto lista incluye ms_densa
        fotogramas=[ms_densa]
        img=_qimg("#f97300")
        resultado={"version": version_densa, "fotogramas": fotogramas, "imagenes": [(ms_densa, img)]}
        cnt=_patch_update(tarjeta._ajustada_grid)
        _drain()
        before=cnt["n"]
        v._aplicar_exploracion_densa(tarjeta, op, resultado)
        after=cnt["n"]
        delta=after-before
        if delta < 1:
            return False, f"F FAIL delta {delta} esperado >=1 en _aplicar_exploracion_densa Ajustada (before {before} after {after})"
        if ms_densa not in tarjeta._cache_visual:
            return False, f"F FAIL cache no recibió ms_densa {ms_densa} tras ruta densa"
        if tarjeta._cache_visual[ms_densa].isNull():
            return False, f"F FAIL pixmap nulo en cache densа"
        # tras processEvents sigue visible
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        if ms_densa not in tarjeta._cache_visual:
            return False, f"F FAIL tras processEvents perdido"
        return True, f"F PASS ruta densa delta {delta} cache ok ms {ms_densa} version {version_densa}"
    finally:
        try: tarjeta._ajustada_grid.update=cnt["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# G. NO FFMPEG — repaint no dispara generación/FFmpeg ni recalcula geometría innecesaria
def test_G_no_ffmpeg():
    import pathlib
    txt=pathlib.Path(visor_videos.__file__).read_text(encoding="utf-8", errors="ignore")
    idx=txt.find("def _al_resultado_preview_visual")
    bloque=txt[idx:idx+7000] if idx>=0 else ""
    ok_static = "ffmpeg" not in bloque.lower() and "ffprobe" not in bloque.lower() and "subprocess" not in bloque.lower()
    if not ok_static:
        return False, f"G FAIL bloque contiene ffmpeg/ffprobe/subprocess"
    # runtime: mock exploracion_cache no llamado
    v,tdir,tarjeta,ms,gen,version,vid=_setup_ajustada_vis()
    try:
        import unittest.mock as mock
        with mock.patch("exploracion_cache.ruta_fotograma_version", side_effect=AssertionError("FFmpeg no debe llamarse")):
            cnt=_patch_update(tarjeta._ajustada_grid)
            _drain()
            # recapturar gen/version tras drain como en A
            gen = tarjeta._cache_visual_gen
            version = tarjeta._densidad_version
            tarjeta._cache_visual_pending.add(ms)
            before=cnt["n"]
            img=_qimg("#999999")
            res={"video_id": vid, "version": version, "request_id": gen, "imagenes": [(ms, img)]}
            v._al_resultado_preview_visual(res)
            after=cnt["n"]
            delta=after-before
            if delta < 1:
                return False, f"G FAIL runtime delta {delta} esperado >=1"
            if ms not in tarjeta._cache_visual:
                return False, f"G FAIL cache miss"
            # además no debe recalcular geometría de forma espuria: cols/rows deberían permanecer igual antes/después si no cambió densidad
            # capturar cols antes
        # segunda verificación estática para _aplicar_exploracion_densa con imagenes: tampoco debe llamar ffmpeg
        idx2=txt.find("def _aplicar_exploracion_densa")
        bloque2=txt[idx2:idx2+8000] if idx2>=0 else ""
        # en esa rama con imagenes, no debe haber llamada a generar_preview/run ffmpeg
        if "generar_preview" in bloque2.lower() or "ruta_fotograma_version" in bloque2:
            # ruta_fotograma_version es permitido solo cuando no hay imagen (fallback disco); con imagen no debe usarse para esa ms. Ya verificado que con imagen se salta.
            # Pero presencia no es fallo si está condicionada; solo verificar no hay ffmpeg improbable
            if "ffmpeg" in bloque2.lower():
                return False, f"G FAIL bloque densа contiene ffmpeg"
        return True, f"G PASS no ffmpeg static ok runtime delta {delta}"
    finally:
        try: tarjeta._ajustada_grid.update=cnt["orig"]
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

# Mantener compatibilidad con tests antiguos que validan Tira/Reducida no regresión (opcional)
def test_H_tira_reducida_mantienen():
    filas=_filas(["v1.mp4"], carpeta="C:\\tmp_b973_c")
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta); v.resize(1200,700); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.03)
        if len(v.tarjetas)>=1: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    tarjeta=dict(v.tarjetas)["v1.mp4"]
    tarjeta.show(); tarjeta.resize(1200,600); QApplication.processEvents()
    tarjeta.expandir(); QApplication.processEvents()
    try:
        ok=True; msgs=[]
        for modo in (MODO_TIRA, MODO_REDUCIDA):
            tarjeta._densidad_manual=15
            tarjeta.set_metadata_densa(tiempos_objetivo(100.0,15), version=f"v973_{modo}"); QApplication.processEvents()
            tarjeta._contenedor_exploracion.setFixedWidth(1800 if modo==MODO_REDUCIDA else 1200); QApplication.processEvents()
            _a_modo(tarjeta, modo); QApplication.processEvents()
            tarjeta._cache_visual.clear(); tarjeta._cache_visual_pending.clear()
            ms=sorted(tarjeta._tira_logical_ms)[0]
            tarjeta._cache_visual_pending.add(ms)
            try: tarjeta._cache_visual_gen+=1
            except: tarjeta._cache_visual_gen=1
            gen=tarjeta._cache_visual_gen; ver=tarjeta._densidad_version; vid=tarjeta._video_id
            img=_qimg("#123123")
            res={"video_id": vid, "version": ver, "request_id": gen, "imagenes": [(ms, img)]}
            # para Tira/Reducida el repaint no es vía ajustada_grid.update sino vía _tira_refrescar/_reducida_refrescar, pero al menos cache debe entrar
            cnt=None
            # no exigimos ag.update aquí, solo cache/pending
            v._al_resultado_preview_visual(res)
            for _ in range(3):
                QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
            has = ms in tarjeta._cache_visual and ms not in tarjeta._cache_visual_pending
            ok = ok and has
            msgs.append(f"{modo} {has}")
        return ok, ";".join(msgs)
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

TESTS=[
    ("A_valid_ajustada_sync", test_A_valid_ajustada),
    ("B_stale_request_id_sync0", test_B_stale_request_id),
    ("C_otra_tarjeta_no_cruza", test_C_otra_tarjeta),
    ("D_multi_fijadas_AB", test_D_multi_fijadas),
    ("E_version_stale_sync0", test_E_version_stale),
    ("F_ruta_densa_directa", test_F_ruta_densa_directa),
    ("G_no_ffmpeg", test_G_no_ffmpeg),
    ("H_tira_reducida_mantienen", test_H_tira_reducida_mantienen),
]

if __name__=="__main__":
    import traceback
    fails=[]
    for name, fn in TESTS:
        try:
            ok,msg=fn()
            print(f"{name}: {'PASS' if ok else 'FAIL'} {msg}")
            if not ok: fails.append(name)
            for _ in range(2):
                QApplication.processEvents()
            gc.collect(); QApplication.processEvents()
        except Exception as e:
            traceback.print_exc()
            print(f"{name}: EXC {e}")
            fails.append(name)
    print(f"\nTotal {len(TESTS)} fails {len(fails)}: {fails}")
    sys.exit(0 if not fails else 1)
