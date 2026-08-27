"""B9.7.3 P06 — DIAGNOSTICO BLANCOS RESIDUALES Ajustada — pipeline completo, pending huerfano, partial batch, stale, multi-fijadas."""
import os, sys, tempfile, gc, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor, QImage
from PySide6.QtCore import Qt, QEvent, QTimer, QRect

import visor_videos
from visor_videos import Tarjeta, VisorVideos, MODO_AJUSTADA, dimensiones_miniatura
from exploracion_temporal import tiempos_objetivo

app = QApplication.instance() or QApplication(sys.argv)

def _pix(color="#aabbcc", w=64, h=36):
    pm = QPixmap(w, h)
    pm.fill(QColor(color))
    return pm

def _qimg(color="#aabbcc", w=64, h=36):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    return img

def _qimg_null():
    return QImage()  # null

def _filas(nombres, carpeta="C:\\tmp_b973_diag"):
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

def _drain():
    for _ in range(3):
        QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()

def _setup_ajustada_con_N(N=15, duracion=100.0, version="v973_diag", nombre="v1.mp4"):
    filas=_filas([nombre], carpeta="C:\\tmp_b973_diag_setup")
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta)
    v.resize(1200,800); v.show()
    for _ in range(30):
        QApplication.processEvents(); time.sleep(0.03)
        if len(v.tarjetas)>=1: break
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas); QApplication.processEvents()
    tarjeta=dict(v.tarjetas)[nombre]
    tarjeta.show(); tarjeta.resize(1200,700); QApplication.processEvents()
    tarjeta.expandir(); QApplication.processEvents()
    tarjeta._densidad_manual=N
    mss=tiempos_objetivo(duracion, N)
    tarjeta.set_metadata_densa(mss, version=version); QApplication.processEvents()
    tarjeta._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
    _a_modo(tarjeta, MODO_AJUSTADA); QApplication.processEvents()
    # forzar geometria visible
    try:
        tarjeta._ajustada_actualizar_logica(); QApplication.processEvents()
    except: pass
    _drain()
    tarjeta._cache_visual.clear()
    tarjeta._cache_visual_pending.clear()
    # reset gen
    try: tarjeta._cache_visual_gen +=1
    except: tarjeta._cache_visual_gen=1
    return v, tdir, tarjeta

def _metricas(tarjeta, v=None):
    logical = list(getattr(tarjeta, "_tira_logical_ms", []))
    requeridos = tarjeta._ajustada_ms_visuales_necesarios() if hasattr(tarjeta,"_ajustada_ms_visuales_necesarios") else set()
    cache = set(tarjeta._cache_visual.keys())
    pending = set(tarjeta._cache_visual_pending)
    # visibles = requeridos (top viewport + exposed)
    visibles = requeridos
    sin_cache_sin_pending = [ms for ms in visibles if ms not in cache and ms not in pending]
    en_pending_sin_tarea = []
    # pending pero sin tarea activa/cola
    if v is not None:
        cola_ms=set()
        for op in getattr(v,"_cola_previews_visuales",[]):
            if op.get("video_id")==tarjeta._video_id:
                cola_ms.update(op.get("ms_lista") or [])
        activa_ms=set()
        try:
            op_act=getattr(v,"_preview_visual_op_actual",None)
            if op_act and op_act.get("video_id")==tarjeta._video_id:
                activa_ms.update(op_act.get("ms_lista") or [])
        except: pass
        for ms in pending:
            if ms in visibles and ms not in cola_ms and ms not in activa_ms and v.gestor_previews_visuales.activo==False:
                # pending pero sin tarea activa ni cola -> huerfano
                # but if gestor activo para otro video, not count
                en_pending_sin_tarea.append(ms)
        # more general: pending sin cola ni activa
        # also count pending that is visible but not in cola/activa
    blancos = [ms for ms in visibles if ms not in cache]
    return {
        "N": len(logical),
        "visibles": len(visibles),
        "cache": len(cache),
        "pending": len(pending),
        "sin_cache_sin_pending": len(sin_cache_sin_pending),
        "en_pending_sin_tarea": len(en_pending_sin_tarea),
        "blancos": len(blancos),
        "visibles_set": visibles,
        "cache_set": cache,
        "pending_set": pending,
        "blancos_set": set(blancos),
        "sin_cache_sin_pending_set": set(sin_cache_sin_pending),
        "huerfanos_set": set(en_pending_sin_tarea),
    }

# TESTS

def test_partial_batch_menos_imagenes_que_solicitados():
    """Batch 12 solicita, worker devuelve 10 (2 faltantes por archivo ausente). Pending de faltantes debe limpiarse para permitir reintento."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=30, version="v973_partial")
    try:
        logical=sorted(tarjeta._tira_logical_ms)
        requeridos=tarjeta._ajustada_ms_visuales_necesarios()
        # elegir 12 primeros requeridos
        batch=list(sorted(requeridos))[:12]
        if len(batch)<4:
            batch=logical[:12]
        # simular emision real: pending + gen + cola op
        for m in batch:
            tarjeta._cache_visual_pending.add(m)
        try: tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        gen=tarjeta._cache_visual_gen
        version=tarjeta._densidad_version
        vid=tarjeta._video_id
        # registrar op activa simulada como lo hace _procesar_siguiente
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batch), "request_id": gen}
        # worker devuelve solo 10 de 12 (faltan 2 intermedios)
        faltantes=batch[5:7]  # 2 ms que fallan
        entregados=[ms for ms in batch if ms not in faltantes]
        imagenes=[(ms,_qimg("#ff0000")) for ms in entregados]
        res={"video_id": vid, "version": version, "request_id": gen, "imagenes": imagenes}
        v._al_resultado_preview_visual(res)
        # limpiar op activa como haria finalizada
        v._preview_visual_op_actual=None
        # metricas
        met=_metricas(tarjeta, v)
        # Verificar: faltantes NO deben quedar en pending (fix), cache no tiene faltantes, blancos = faltantes
        pending=tarjeta._cache_visual_pending
        cache=tarjeta._cache_visual
        # pre-fix: pending contiene faltantes => blancos huérfanos
        # post-fix: pending no contiene faltantes => reintentable (sin_cache_sin_pending)
        if faltantes[0] in pending or faltantes[1] in pending:
            return False, f"PARTIAL FAIL pending huérfano queda {faltantes} pending {sorted(pending)[:6]} cache {len(cache)} -> blanco permanente (blancos {met['blancos']})"
        # ahora debe aparecer como sin_cache_sin_pending para permitir reintento via paintEvent
        if faltantes[0] not in met["sin_cache_sin_pending_set"] or faltantes[1] not in met["sin_cache_sin_pending_set"]:
            # after sincronizar, si requeridos aún incluye faltantes, deben estar como sin pending sin cache
            return False, f"PARTIAL FAIL faltantes no quedaron como reintentables: {faltantes} sin_cache_sin_pending {met['sin_cache_sin_pending_set']} pending {pending} requeridos {sorted(requeridos)[:8]}"
        # blancos deben ser exactamente faltantes (2)
        if met["blancos"] != len(faltantes):
            # si blancos !=2, hay otro error
            pass
        # Simular repaint que re-solicitara: paintEvent detectaría need para faltantes si pending no existe
        # verificamos que agendado pending tras un paint simulado se limpiaría? No necesario aquí, solo que pending huérfano no existe
        return True, f"PARTIAL PASS batch {len(batch)} entregados {len(entregados)} faltantes {faltantes} pending {len(pending)} blancos {met['blancos']} sin_cache_sin_pending {met['sin_cache_sin_pending']}"
    finally:
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_stale_no_limpia_pending_vigente():
    """Resultado stale (viejo gen) no debe borrar pending de nueva generación vigente."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=20, version="v973_stale")
    try:
        logical=sorted(tarjeta._tira_logical_ms)
        # old gen
        for m in logical[:4]:
            tarjeta._cache_visual_pending.add(m)
        try: tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        old_gen=tarjeta._cache_visual_gen
        old_version=tarjeta._densidad_version
        vid=tarjeta._video_id
        # new gen: cambiar pending a nuevo batch
        tarjeta._cache_visual_gen+=1
        new_gen=tarjeta._cache_visual_gen
        # nuevo pending para otro ms (el segundo)
        nuevo_ms=logical[5]
        tarjeta._cache_visual_pending.clear()
        tarjeta._cache_visual_pending.add(nuevo_ms)
        # también encolar op para nuevo gen (simular cola)
        v._cola_previews_visuales.append({"video_id": vid, "version": old_version, "ms_lista": [nuevo_ms], "request_id": new_gen})
        # stale llega con old_gen, con imagen para old ms
        stale_ms=logical[1]
        res_stale={"video_id": vid, "version": old_version, "request_id": old_gen, "imagenes": [(stale_ms,_qimg("#aaaaaa"))]}
        v._al_resultado_preview_visual(res_stale)
        pending=tarjeta._cache_visual_pending
        cache=tarjeta._cache_visual
        # checks: stale no debe insertar en cache
        if stale_ms in cache:
            return False, f"STALE FAIL stale insertó cache {stale_ms}"
        # pending vigente debe preservarse
        if nuevo_ms not in pending:
            return False, f"STALE FAIL pending vigente borrado {nuevo_ms} pending {pending}"
        # stale ms no debe quitar pending vigente ni crear hueco
        return True, f"STALE PASS old_gen {old_gen} new_gen {new_gen} nuevo_ms {nuevo_ms} preservado stale_ms {stale_ms} no insertado"
    finally:
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_qimage_invalido_null():
    """Worker devuelve QImage nulo/invalido: pending debe limpiarse y cache no insertada, permitiendo reintento."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=15, version="v973_qnull")
    try:
        _drain()
        tarjeta._cache_visual.clear()
        tarjeta._cache_visual_pending.clear()
        QApplication.processEvents()
        logical=sorted(tarjeta._tira_logical_ms)
        ms=logical[0]
        tarjeta._cache_visual_pending.add(ms)
        try: tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        gen=tarjeta._cache_visual_gen; version=tarjeta._densidad_version; vid=tarjeta._video_id
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": [ms], "request_id": gen}
        res={"video_id": vid, "version": version, "request_id": gen, "imagenes": [(ms, _qimg_null())]}
        v._al_resultado_preview_visual(res)
        v._preview_visual_op_actual=None
        pending=tarjeta._cache_visual_pending
        cache=tarjeta._cache_visual
        if ms in cache:
            return False, f"QNULL FAIL cache insertó ms con imagen nula"
        # pending puede re-agregarse inmediatamente via hover/_refrescar (6250 vecinos) — no es huérfano si hay cola o reintento
        # verificar que ms no queda como blanco permanente sin reintento: debe estar en pending (re-solicitado) o en sin_cache_sin_pending
        met=_metricas(tarjeta, v)
        if ms not in pending and ms not in met["sin_cache_sin_pending_set"]:
            return False, f"QNULL FAIL ms {ms} ni en pending ni reintentable pending {pending} sin_cache {met['sin_cache_sin_pending_set']}"
        return True, f"QNULL PASS ms {ms} cache no insert pending {len(pending)} reintentable"
    finally:
        try: tarjeta._ajustada_grid.blockSignals(False)
        except: pass
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_error_lectura_jpeg_individual_no_bloquea():
    """Simular error de lectura de un JPEG: payload vacío para ese ms (batch parcial). pending debe limpiarse."""
    # reutiliza partial logic pero con 1 faltante por error
    v,tdir,tarjeta=_setup_ajustada_con_N(N=25, version="v973_errjpeg")
    try:
        logical=sorted(tarjeta._tira_logical_ms)
        batch=list(sorted(tarjeta._ajustada_ms_visuales_necesarios()))[:6]
        if len(batch)<6: batch=logical[:6]
        for m in batch: tarjeta._cache_visual_pending.add(m)
        try: tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        gen=tarjeta._cache_visual_gen; version=tarjeta._densidad_version; vid=tarjeta._video_id
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batch), "request_id": gen}
        # simular error: un ms falla lectura, no incluido en imagenes
        ms_error=batch[2]
        entregados=[ms for ms in batch if ms!=ms_error]
        res={"video_id": vid, "version": version, "request_id": gen, "imagenes": [(ms,_qimg("#00ff00")) for ms in entregados]}
        v._al_resultado_preview_visual(res)
        v._preview_visual_op_actual=None
        pending=tarjeta._cache_visual_pending
        if ms_error in pending:
            return False, f"ERRJPEG FAIL pending huérfano ms_error {ms_error} pending {sorted(pending)}"
        met=_metricas(tarjeta, v)
        if ms_error not in met["sin_cache_sin_pending_set"]:
            return False, f"ERRJPEG FAIL no reintentable {ms_error}"
        return True, f"ERRJPEG PASS ms_error {ms_error} pending limpio entregados {len(entregados)} blancos {met['blancos']}"
    finally:
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_batch_fuera_de_orden():
    """Dos batches A y B, B llega primero. No debe dejar huérfanos ni sobrescribir."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=30, version="v973_ooo")
    try:
        logical=sorted(tarjeta._tira_logical_ms)
        # batch A = primeros 6, batch B = siguientes 6
        batchA=logical[:6]
        batchB=logical[6:12]
        # emitir A
        for m in batchA: tarjeta._cache_visual_pending.add(m)
        try: tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        genA=tarjeta._cache_visual_gen; version=tarjeta._densidad_version; vid=tarjeta._video_id
        # cola simula: A encolado, B encolado subsiguiente con gen incrementado?
        # en pipeline real, cada solicitud incrementa gen. Simulamos genB > genA
        tarjeta._cache_visual_gen+=1
        genB=tarjeta._cache_visual_gen
        for m in batchB: tarjeta._cache_visual_pending.add(m)
        # op activa A, cola B
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batchA), "request_id": genA}
        v._cola_previews_visuales=[{"video_id": vid, "version": version, "ms_lista": list(batchB), "request_id": genB}]
        # B llega primero pero genB > genA, no es stale? Actually B es newer gen, A es older. Si B llega primero, A será stale al llegar después.
        # Primero entregar B (genB) -> debe insertarse
        resB={"video_id": vid, "version": version, "request_id": genB, "imagenes": [(ms,_qimg("#111111")) for ms in batchB]}
        # Pero _al_resultado espera que gen coincida con tarjeta._cache_visual_gen == genB. Actualmente tarjeta gen es genB, so B es vigente, A será stale
        # Entregar B out of order: como genB == current gen, debe aceptarse aunque A aún activa con genA. Simular que B llegó antes que A: actualizar op_activa a B temporalmente?
        # Para test out-of-order, simulamos que cola se adelanta: procesar B antes que A terminase -> gen check falla para B si activa sigue A
        # Más simple: no simular activa, directamente entregar B con genB vigente, luego A con genA stale
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batchB), "request_id": genB}
        v._al_resultado_preview_visual(resB)
        v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batchA), "request_id": genA}
        # ahora A llega stale
        resA={"video_id": vid, "version": version, "request_id": genA, "imagenes": [(ms,_qimg("#222222")) for ms in batchA]}
        v._al_resultado_preview_visual(resA)
        v._preview_visual_op_actual=None
        v._cola_previews_visuales=[]
        # checks: batchB debe estar en cache, batchA stale no debe insertar (si gen check descarta) -> pre-fix stale descarta pero también descarta pending solo si no queued
        # Después de B aceptado, gen sigue genB, so A stale debe descartarse
        cache=set(tarjeta._cache_visual.keys())
        pending=tarjeta._cache_visual_pending
        # batchB should be cached
        faltanB=[ms for ms in batchB if ms not in cache]
        if faltanB:
            return False, f"OOO FAIL batchB no cache {faltanB} cache {sorted(cache)}"
        # batchA stale no debe haber sido insertado (except if gen check preserved? but gen mismatch should discard)
        # Actually if batchA stale, it should NOT be inserted
        intersectA=[ms for ms in batchA if ms in cache]
        if intersectA:
            return False, f"OOO FAIL stale batchA insertado {intersectA}"
        # pending for batchA stale should have been limpiado si no queued; pending for batchB should be limpio
        if any(ms in pending for ms in batchB):
            return False, f"OOO FAIL pending B huérfano {pending}"
        # pending A debería haber sido limpiado (o preservado si queued, pero no queued)
        # como A stale, pending A debería estar limpio
        if any(ms in pending for ms in batchA):
            # stale handler discards pending for ms in imagenes if not queued -> should be limpio
            # if still pending, es huérfano
            return False, f"OOO FAIL pending A stale huérfano {pending}"
        return True, f"OOO PASS B cache {len(batchB)} A stale descartado pending {len(pending)}"
    finally:
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_multi_fijadas_no_cruce():
    """Dos tarjetas fijadas en Ajustada: batch parcial en una no afecta otra, pending independiente."""
    filas=_filas(["v1.mp4","v2.mp4"], carpeta="C:\\tmp_b973_multi_diag")
    tdir,ruta=_crear_bd(filas)
    v=VisorVideos(ruta_db=ruta); v.resize(1200,800); v.show()
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
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v973_multi2"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_modo(t, MODO_AJUSTADA); QApplication.processEvents()
        t._cache_visual.clear(); t._cache_visual_pending.clear()
        try: t._cache_visual_gen+=1
        except: t._cache_visual_gen=1
    try:
        # limpiar cola global para determinismo
        try: v._cola_previews_visuales.clear(); v._preview_visual_op_actual=None
        except: pass
        # t1 solicita batch con faltante
        batch1=list(sorted(t1._ajustada_ms_visuales_necesarios()))[:6]
        if len(batch1)<6: batch1=sorted(t1._tira_logical_ms)[:6]
        for m in batch1: t1._cache_visual_pending.add(m)
        try: t1._cache_visual_gen+=1
        except: t1._cache_visual_gen=1
        gen1=t1._cache_visual_gen; vid1=t1._video_id; ver1=t1._densidad_version
        v._preview_visual_op_actual={"video_id": vid1, "version": ver1, "ms_lista": list(batch1), "request_id": gen1}
        ms_fail=batch1[2]
        entregados=[ms for ms in batch1 if ms!=ms_fail]
        res1={"video_id": vid1, "version": ver1, "request_id": gen1, "imagenes": [(ms,_qimg("#ff0000")) for ms in entregados]}
        v._al_resultado_preview_visual(res1)
        v._preview_visual_op_actual=None
        QApplication.processEvents()
        # t2 batch completo
        batch2=list(sorted(t2._ajustada_ms_visuales_necesarios()))[:6]
        if len(batch2)<6: batch2=sorted(t2._tira_logical_ms)[:6]
        for m in batch2: t2._cache_visual_pending.add(m)
        try: t2._cache_visual_gen+=1
        except: t2._cache_visual_gen=1
        gen2=t2._cache_visual_gen; vid2=t2._video_id; ver2=t2._densidad_version
        v._preview_visual_op_actual={"video_id": vid2, "version": ver2, "ms_lista": list(batch2), "request_id": gen2}
        res2={"video_id": vid2, "version": ver2, "request_id": gen2, "imagenes": [(ms,_qimg("#00ff00")) for ms in batch2]}
        v._al_resultado_preview_visual(res2)
        v._preview_visual_op_actual=None
        # verificar que pending huérfano t1 fue limpiado (o re-encolado con retry <3, pero no huérfano bloqueante)
        # con retry acotado, tras faltante pending se libera y luego paint puede re-encolar si retry<3. Verificar que no queda huérfano bloqueado (retry debe ser 1 y pending puede estar re-agregado)
        retry_t1 = getattr(t1, "_ajustada_visual_retry", {}).get(ms_fail, 0)
        if ms_fail in t1._cache_visual_pending and retry_t1 >= 3:
            return False, f"MULTI FAIL t1 pending huérfano post-retry {ms_fail} pending {t1._cache_visual_pending} retry {retry_t1}"
        if ms_fail not in t1._cache_visual_pending and ms_fail not in t1._cache_visual and retry_t1 != 1:
            # debe estar retry 1 y ser reintentable (pending o sin_cache)
            # verificar reintentable
            try:
                is_pending = ms_fail in t1._cache_visual_pending
                is_sin = ms_fail in (t1._ajustada_ms_visuales_necesarios() - set(t1._cache_visual.keys()) - t1._cache_visual_pending)
                if not is_pending and not is_sin:
                    return False, f"MULTI FAIL t1 no reintentable {ms_fail} pending {t1._cache_visual_pending} retry {retry_t1}"
            except: pass
        # también asegurar que no está en cache (fail no insertó)
        # nota: ms_fail numérico puede coincidir en t2 por misma lógica densidad; no es cruce. Solo verificar pending huérfano t2 no relacionado
        # verificar que t2 no tenga pending huérfano para su propio batch
        # cruce real sería video_id equivocado, no valor ms idéntico
        # t2 debe tener cache completo
        if any(ms not in t2._cache_visual for ms in batch2):
            return False, f"MULTI FAIL t2 cache incompleta {batch2} cache {list(t2._cache_visual.keys())[:6]}"
        # t1 cache debe tener entregados pero no fail
        if ms_fail in t1._cache_visual:
            return False, f"MULTI FAIL t1 cache contiene fail"
        if any(ms not in t1._cache_visual for ms in entregados):
            return False, f"MULTI FAIL t1 cache faltantes entregados"
        return True, f"MULTI PASS t1 fail {ms_fail} limpio t2 ok {len(batch2)}"
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

def test_N_120_200_metrics():
    """Métricas N=120 y N=200 top viewport: verificar acotado y blancos sin pending huérfano."""
    results=[]
    for N in (120,200):
        v,tdir,tarjeta=_setup_ajustada_con_N(N=N, version=f"v973_N{N}")
        try:
            # simular carga completa top viewport: solicitar y entregar todos requeridos
            requeridos=tarjeta._ajustada_ms_visuales_necesarios()
            batch=list(sorted(requeridos))[:12]
            # si requeridos <12, usar logical slice
            if len(batch)<12:
                batch=sorted(tarjeta._tira_logical_ms)[:12]
            for m in batch: tarjeta._cache_visual_pending.add(m)
            try: tarjeta._cache_visual_gen+=1
            except: tarjeta._cache_visual_gen=1
            gen=tarjeta._cache_visual_gen; version=tarjeta._densidad_version; vid=tarjeta._video_id
            v._preview_visual_op_actual={"video_id": vid, "version": version, "ms_lista": list(batch), "request_id": gen}
            # entregar con 1 faltante para simular 5% ≈ 1/20
            faltante=batch[3] if len(batch)>3 else batch[0]
            entregados=[ms for ms in batch if ms!=faltante]
            res={"video_id": vid, "version": version, "request_id": gen, "imagenes": [(ms,_qimg("#123456")) for ms in entregados]}
            v._al_resultado_preview_visual(res)
            v._preview_visual_op_actual=None
            met=_metricas(tarjeta, v)
            # verificar no huérfano
            if faltante in tarjeta._cache_visual_pending:
                results.append((N, False, f"N={N} huérfano {faltante} pending {met['pending']} blancos {met['blancos']}"))
            else:
                # debe quedar como reintentable
                if faltante not in met["sin_cache_sin_pending_set"]:
                    results.append((N, False, f"N={N} no reintentable faltante {faltante}"))
                else:
                    results.append((N, True, f"N={N} visibles {met['visibles']} cache {met['cache']} pending {met['pending']} blancos {met['blancos']} sin_cache_sin_pending {met['sin_cache_sin_pending']}"))
            # verificar cache acotada <200 y <48 para Ajustada
            if met["cache"]>48:
                results.append((N, False, f"N={N} cache no acotada {met['cache']}"))
        finally:
            _cleanup_vis(v);
            try: tdir.cleanup()
            except: pass
        _drain()
    fails=[r for r in results if not r[1]]
    ok=len(fails)==0
    msg="; ".join([r[2] for r in results])
    return ok, msg

def test_scroll_zona_media_y_final():
    """Simular scroll a zona media/final: requeridos debe incluir expuestos y no dejar blancos por evicción agresiva."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=60, version="v973_scroll")
    try:
        logical=sorted(tarjeta._tira_logical_ms)
        # top viewport ya cargado
        requeridos_top=tarjeta._ajustada_ms_visuales_necesarios()
        # simular scroll medio: set last_exposed a índices 20..35
        cols=getattr(tarjeta,"_ajustada_cols",4)
        # forzar exposed indices media
        mid_indices=set(range(20, min(35, len(logical))))
        mid_ms=[logical[i] for i in mid_indices if i < len(logical)]
        tarjeta._ajustada_grid._last_exposed_ms=set(mid_ms)
        tarjeta._ajustada_grid._last_exposed_indices=set(mid_indices)
        requeridos_mid=tarjeta._ajustada_ms_visuales_necesarios()
        # verificar que requeridos_mid incluye mid_ms
        faltanMid=[ms for ms in mid_ms if ms not in requeridos_mid]
        if faltanMid:
            return False, f"SCROLL MID FAIL requeridos no incluye expuestos medios faltan {faltanMid[:4]} requeridos {len(requeridos_mid)}"
        # cargar cache para mid
        for ms in mid_ms:
            tarjeta._cache_visual[ms]=_pix("#aaaaaa")
        # ahora sincronizar y verificar que no evicta mid_ms aunque estén lejos de top
        tarjeta._sincronizar_cache_visual()
        evictados=[ms for ms in mid_ms if ms not in tarjeta._cache_visual]
        if evictados:
            return False, f"SCROLL MID FAIL cache evictada agresiva {evictados[:4]} cache {len(tarjeta._cache_visual)} requeridos {len(requeridos_mid)}"
        # zona final
        final_indices=set(range(max(0,len(logical)-15), len(logical)))
        final_ms=[logical[i] for i in final_indices]
        tarjeta._ajustada_grid._last_exposed_ms=set(final_ms)
        tarjeta._ajustada_grid._last_exposed_indices=set(final_indices)
        requeridos_final=tarjeta._ajustada_ms_visuales_necesarios()
        faltanFinal=[ms for ms in final_ms if ms not in requeridos_final]
        if faltanFinal:
            return False, f"SCROLL FINAL FAIL faltan {faltanFinal[:4]}"
        for ms in final_ms:
            tarjeta._cache_visual[ms]=_pix("#bbbbbb")
        tarjeta._sincronizar_cache_visual()
        evictadosF=[ms for ms in final_ms if ms not in tarjeta._cache_visual]
        if evictadosF:
            return False, f"SCROLL FINAL FAIL evictados {evictadosF[:4]}"
        return True, f"SCROLL PASS mid {len(mid_ms)} final {len(final_ms)} requeridos mid {len(requeridos_mid)} final {len(requeridos_final)} cache {len(tarjeta._cache_visual)}"
    finally:
        _cleanup_vis(v);
        try: tdir.cleanup()
        except: pass

def test_A_transitorio_converge_solo():
    """Parte A — transitorio converge en 2 intentos sin interacción, vía ag.update() paintEvent."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=15, version="v973_A_trans")
    try:
        _drain()
        tarjeta._cache_visual.clear()
        tarjeta._cache_visual_pending.clear()
        try:
            tarjeta._ajustada_visual_retry.clear()
        except: pass
        try:
            v._cola_previews_visuales.clear()
            v._preview_visual_op_actual=None
        except: pass
        # elegir ms visible (primero en logical)
        ms = sorted(tarjeta._tira_logical_ms)[0]
        # asegurar requeridos incluye ms
        requeridos = tarjeta._ajustada_ms_visuales_necesarios()
        if ms not in requeridos:
            ms = sorted(requeridos)[0] if requeridos else ms
        # aislar requeridos a solo ms para evitar gen drift por otros visibles
        _orig_req = tarjeta._ajustada_ms_visuales_necesarios
        tarjeta._ajustada_ms_visuales_necesarios = lambda: {ms}
        # métricas
        requests = []
        def _cap(payload):
            try:
                if payload.get("video_id")==tarjeta._video_id:
                    requests.append(list(payload.get("ms_lista") or []))
            except: pass
        tarjeta.preview_visual_solicitada.connect(_cap)
        # también contar updates de grid
        cnt_grid = {"n":0, "orig": tarjeta._ajustada_grid.update}
        orig_up = tarjeta._ajustada_grid.update
        def _cnt(*a,**kw):
            cnt_grid["n"]+=1
            return orig_up(*a,**kw)
        tarjeta._ajustada_grid.update = _cnt
        # 1) primera solicitud: simular celda visible -> request directo (evitar paintEvent extra)
        ver = tarjeta._densidad_version
        vid = tarjeta._video_id
        # limpiar estado previo y cancelar singleShot pendiente
        try:
            v._cola_previews_visuales.clear()
            v._preview_visual_op_actual=None
            if v.gestor_previews_visuales.activo:
                v.gestor_previews_visuales.cerrar()
            try:
                tarjeta._ajustada_grid._pending_need_emitted = False
            except: pass
            for _ in range(2):
                QApplication.processEvents()
        except: pass
        # asegurar cola limpia antes de emitir
        try:
            v._cola_previews_visuales.clear()
        except: pass
        tarjeta._cache_visual_pending.add(ms)
        try:
            tarjeta._cache_visual_gen+=1
        except: tarjeta._cache_visual_gen=1
        gen1 = tarjeta._cache_visual_gen
        payload = {"video_id": vid, "version": ver, "ms_lista": [ms], "request_id": gen1, "gen": gen1}
        # emitir via signal para que sea capturado y vaya por Visor
        tarjeta.preview_visual_solicitada.emit(payload)
        QApplication.processEvents()
        try:
            v._cola_previews_visuales.clear()
        except: pass
        # verificar que al menos un request contiene ms (puede ser batch con otros)
        reqs_with_ms = [r for r in requests if ms in r]
        if len(reqs_with_ms)==0:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL 1er request no contiene ms {ms} got {requests} gen {gen1} pending {tarjeta._cache_visual_pending}"
        req1 = reqs_with_ms[0]
        try:
            if getattr(v, "_preview_visual_op_actual", None) is None:
                v._preview_visual_op_actual={"video_id": vid, "version": ver, "ms_lista": list(req1), "request_id": gen1}
        except: pass
        # 2) primera carga devuelve batch parcial SIN ese ms (faltante transitorio)
        res1 = {"video_id": vid, "version": ver, "request_id": gen1, "imagenes": []}  # vacío => faltante
        before_up = cnt_grid["n"]
        v._al_resultado_preview_visual(res1)
        v._preview_visual_op_actual=None
        retry_after1 = dict(getattr(tarjeta, "_ajustada_visual_retry", {}))
        pending_immediate = set(tarjeta._cache_visual_pending)
        # verificar que retry se incrementó y ms no está en cache
        if retry_after1.get(ms,0)!=1:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL retry no incrementado a 1 tras 1er fallo {retry_after1} pending {pending_immediate}"
        if ms in tarjeta._cache_visual:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL ms en cache tras fallo"
        QApplication.processEvents()
        after_up = cnt_grid["n"]
        pending_after1 = set(tarjeta._cache_visual_pending)
        if after_up - before_up <1:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL ag.update no llamado tras faltante delta {after_up-before_up}"
        # 3) sin interacción, el propio flujo de repintado debe permitir nueva solicitud
        # ag.update ya disparó paintEvent -> _on_ajustada_need_visual diferido via singleShot(0)
        # procesar eventos para que singleShot se ejecute
        for _ in range(5):
            QApplication.processEvents()
            time.sleep(0.02)
            QApplication.processEvents()
        # debe haber 2da solicitud automática (pending se re-agrega via paintEvent, es esperado)
        if len(requests) <2:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL no converge: solo {len(requests)} requests tras faltante, esperado 2 (requests {requests}) retry {retry_after1} pending {pending_after1}"
        req2 = requests[1]
        if ms not in req2:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
            return False, f"A FAIL 2da request no contiene ms {ms} got {req2} all {requests}"
        # 4) antes del segundo intento, hacer que JPEG aparezca: segunda carga devuelve QImage válido
        try:
            # limpiar cola waiting que contenga ms para no bloquear descarte de faltantes del segundo batch
            try:
                v._cola_previews_visuales.clear()
            except: pass
            gen2 = tarjeta._cache_visual_gen
            v._preview_visual_op_actual={"video_id": vid, "version": ver, "ms_lista": list(req2), "request_id": gen2}
        except: pass
        img_ok = _qimg("#00ff00")
        res2 = {"video_id": vid, "version": ver, "request_id": gen2, "imagenes": [(ms, img_ok)]}
        before_up2 = cnt_grid["n"]
        v._al_resultado_preview_visual(res2)
        v._preview_visual_op_actual=None
        for _ in range(3):
            QApplication.processEvents(); time.sleep(0.01); QApplication.processEvents()
        pending_final = set(tarjeta._cache_visual_pending)
        cache_final = set(tarjeta._cache_visual.keys())
        retry_final = dict(getattr(tarjeta, "_ajustada_visual_retry", {}))
        updates = cnt_grid["n"]
        tarjeta.preview_visual_solicitada.disconnect(_cap)
        tarjeta._ajustada_grid.update = cnt_grid["orig"]
        if ms not in cache_final:
            return False, f"A FAIL no converge a cache ms {ms} cache {cache_final} pending {pending_final} requests {len(requests)} updates {updates}"
        if ms in pending_final:
            return False, f"A FAIL pending no limpio tras éxito {pending_final}"
        if retry_final.get(ms,0)!=0:
            return False, f"A FAIL retry no reseteado tras éxito {retry_final}"
        cnt_ms = len([r for r in requests if ms in r])
        if cnt_ms <2:
            return False, f"A FAIL requests con ms {cnt_ms} esperado >=2 (transitorio ideal) got {requests} updates {updates}"
        if cnt_ms >4:
            return False, f"A FAIL requests con ms {cnt_ms} >4 (tormenta) got {requests} updates {updates}"
        return True, f"A PASS converge {cnt_ms} intentos (ideal 2) total {len(requests)} updates {updates} retry {retry_after1}->{retry_final} cache {len(cache_final)}"
    finally:
        try:
            tarjeta._ajustada_ms_visuales_necesarios = _orig_req
        except: pass
        try:
            tarjeta._ajustada_grid.update = cnt_grid["orig"]
        except: pass
        try:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

def test_B_permanente_acotado():
    """Parte B — permanente no tormenta: max 3 reintentos, luego estable sin loop."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=15, version="v973_B_perm")
    try:
        _drain()
        tarjeta._cache_visual.clear()
        tarjeta._cache_visual_pending.clear()
        try: tarjeta._ajustada_visual_retry.clear()
        except: pass
        try: v._cola_previews_visuales.clear(); v._preview_visual_op_actual=None
        except: pass
        ms = sorted(tarjeta._tira_logical_ms)[0]
        _orig_req = tarjeta._ajustada_ms_visuales_necesarios
        tarjeta._ajustada_ms_visuales_necesarios = lambda: {ms}
        ver=tarjeta._densidad_version; vid=tarjeta._video_id
        # forzar 3 fallos directos sin depender de paintEvent batch
        for _ in range(3):
            try: v._cola_previews_visuales.clear()
            except: pass
            tarjeta._cache_visual_pending.discard(ms)
            try: tarjeta._cache_visual_gen+=1
            except: tarjeta._cache_visual_gen=1
            gen=tarjeta._cache_visual_gen
            v._preview_visual_op_actual={"video_id": vid, "version": ver, "ms_lista": [ms], "request_id": gen}
            v._al_resultado_preview_visual({"video_id": vid, "version": ver, "request_id": gen, "imagenes": []})
            v._preview_visual_op_actual=None
            QApplication.processEvents()
        retry_mid=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if retry_mid.get(ms,0)!=3:
            return False, f"B FAIL setup retry {retry_mid}"
        # ahora intentar nueva solicitud (debe ser bloqueada) — solo contar single ms
        requests_ms=[]
        def _cap(payload):
            try:
                lst=list(payload.get("ms_lista") or [])
                if lst == [ms]:
                    requests_ms.append(lst)
            except: pass
        tarjeta.preview_visual_solicitada.connect(_cap)
        cnt_grid={"n":0, "orig": tarjeta._ajustada_grid.update}
        orig_up=tarjeta._ajustada_grid.update
        def _cnt(*a,**kw):
            cnt_grid["n"]+=1
            return orig_up(*a,**kw)
        tarjeta._ajustada_grid.update=_cnt
        before=len(requests_ms)
        tarjeta._on_ajustada_need_visual([ms])
        QApplication.processEvents()
        after=len(requests_ms)
        # también probar via ag.update
        tarjeta._ajustada_grid.update()
        for _ in range(5):
            QApplication.processEvents(); time.sleep(0.02); QApplication.processEvents()
        after2=len(requests_ms)
        extra = (after - before) + (after2 - after)
        pending_final=set(tarjeta._cache_visual_pending)
        retry_final=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        cola_len=len(v._cola_previews_visuales)
        try: tarjeta.preview_visual_solicitada.disconnect(_cap)
        except: pass
        tarjeta._ajustada_grid.update=cnt_grid["orig"]
        if extra !=0:
            return False, f"B FAIL tras agotar emite extra {extra} requests_ms {requests_ms} retry {retry_final}"
        if retry_final.get(ms,0)!=3:
            return False, f"B FAIL retry no 3 {retry_final}"
        return True, f"B PASS acotado retry {retry_final.get(ms)} extra {extra} pending {len(pending_final)} cola {cola_len} updates {cnt_grid['n']}"
    finally:
        try: tarjeta._ajustada_ms_visuales_necesarios = _orig_req
        except: pass
        try: tarjeta._ajustada_grid.update=cnt_grid["orig"]
        except: pass
        try: tarjeta.preview_visual_solicitada.disconnect(_cap)
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

def test_C_generacion_tardia_reactiva():
    """Parte C — generación tardía reactiva celda agotada via _aplicar_exploracion_densa."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=15, version="v973_C_gen")
    try:
        _drain()
        tarjeta._cache_visual.clear()
        tarjeta._cache_visual_pending.clear()
        try: tarjeta._ajustada_visual_retry.clear()
        except: pass
        try: v._cola_previews_visuales.clear(); v._preview_visual_op_actual=None
        except: pass
        ms = sorted(tarjeta._tira_logical_ms)[0]
        # agotar retry a 3 de forma determinista (evitar gen drift por paint)
        ver=tarjeta._densidad_version; vid=tarjeta._video_id
        try:
            tarjeta._ajustada_visual_retry[ms]=3
        except: pass
        # opcional: simular 3 incrementos reales sin depender de gen
        # for _ in range(3):
        #     tarjeta._cache_visual_pending.discard(ms)
        #     try:
        #         tarjeta._cache_visual_gen+=1
        #         gen=tarjeta._cache_visual_gen
        #         v._preview_visual_op_actual={"video_id": vid, "version": ver, "ms_lista": [ms], "request_id": gen}
        #         res={"video_id": vid, "version": ver, "request_id": gen, "imagenes": []}
        #         v._al_resultado_preview_visual(res)
        #         v._preview_visual_op_actual=None
        #         QApplication.processEvents()
        #     except: pass
        retry_antes=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if retry_antes.get(ms,0)!=3:
            return False, f"C FAIL no agotado antes {retry_antes}"
        # verificar que nuevo request ya no emite (agotado)
        reqs=[]
        def _cap(payload):
            if payload.get("video_id")==vid:
                reqs.append(list(payload.get("ms_lista") or []))
        tarjeta.preview_visual_solicitada.connect(_cap)
        tarjeta._on_ajustada_need_visual([ms])
        QApplication.processEvents()
        if reqs:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            return False, f"C FAIL agotado aún emite {reqs} retry {retry_antes}"
        # ahora generación tardía: TareaExploracionDensa parcial/final para ese ms
        # simular _aplicar_exploracion_densa con imagen válida (FFmpeg generó JPEG)
        img=_qimg("#123456")
        op={"video_id": vid, "nombre": tarjeta._nombre if hasattr(tarjeta,'_nombre') else "v1.mp4"}
        # mockear ruta_fotograma_version para que exista
        import exploracion_cache, unittest.mock as mock
        with mock.patch("exploracion_cache.ruta_fotograma_version", return_value="/tmp/fake.jpg"):
            with mock.patch("os.path.isfile", return_value=True):
                # versión misma (no cambia) pero fotogramas incluye ms -> debe reset retry
                v._aplicar_exploracion_densa(tarjeta, op, {"version": ver, "fotogramas": [ms], "imagenes": [(ms, img)]})
                QApplication.processEvents()
        retry_despues=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        cache_has= ms in tarjeta._cache_visual
        # también probar que tras reset, nueva solicitud sí emite si aún no en cache (limpiar cache para test)
        if not cache_has:
            # si cache no se llenó porque requeridos filtra, forzar cache manual para verificar reset
            pass
        # si cache se llenó, ya converge; si no, verificar que retry se reseteó y permite nuevo intento
        if retry_despues.get(ms,0)!=0 and not cache_has:
            tarjeta.preview_visual_solicitada.disconnect(_cap)
            return False, f"C FAIL retry no reseteado tras generación {retry_despues} cache {cache_has}"
        # si cache tiene, ya terminado sin necesidad de nuevo request
        # si cache no tiene, verificar que ahora sí permite request
        if not cache_has:
            reqs2=[]
            def _cap2(p):
                if p.get("video_id")==vid:
                    reqs2.append(p.get("ms_lista"))
            tarjeta.preview_visual_solicitada.connect(_cap2)
            tarjeta._on_ajustada_need_visual([ms])
            QApplication.processEvents()
            try: tarjeta.preview_visual_solicitada.disconnect(_cap2)
            except: pass
            if not reqs2:
                tarjeta.preview_visual_solicitada.disconnect(_cap)
                return False, f"C FAIL tras generación no permite reintento {retry_despues}"
        tarjeta.preview_visual_solicitada.disconnect(_cap)
        return True, f"C PASS agotado {retry_antes.get(ms)} -> reset {retry_despues.get(ms,0)} cache {cache_has} reqs {len(reqs)}"
    finally:
        try: tarjeta.preview_visual_solicitada.disconnect(_cap)
        except: pass
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

def test_D_multi_retry_isolated():
    """D — multi-fijadas no comparten contadores."""
    filas=_filas(["v1.mp4","v2.mp4"], carpeta="C:\\tmp_b973_multi_D")
    tdir,ruta=_crear_bd(filas)
    v=visor_videos.VisorVideos(ruta_db=ruta); v.resize(1200,800); v.show()
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
        t.set_metadata_densa(tiempos_objetivo(100.0,15), version="v973_multiD"); QApplication.processEvents()
        t._contenedor_exploracion.setFixedWidth(1200); QApplication.processEvents()
        _a_modo(t, MODO_AJUSTADA); QApplication.processEvents()
        t._cache_visual.clear(); t._cache_visual_pending.clear()
        try: t._ajustada_visual_retry.clear()
        except: pass
        try: t._cache_visual_gen+=1
        except: t._cache_visual_gen=1
    try:
        ms1=sorted(t1._tira_logical_ms)[0]
        ms2=sorted(t2._tira_logical_ms)[0]
        # agotar t1 a 3
        ver1=t1._densidad_version; vid1=t1._video_id
        for _ in range(3):
            try:
                t1._cache_visual_gen+=1; gen=t1._cache_visual_gen
                v._preview_visual_op_actual={"video_id": vid1, "version": ver1, "ms_lista": [ms1], "request_id": gen}
                v._al_resultado_preview_visual({"video_id": vid1, "version": ver1, "request_id": gen, "imagenes": []})
                v._preview_visual_op_actual=None; QApplication.processEvents()
            except: pass
        retry1=dict(getattr(t1,"_ajustada_visual_retry",{}))
        retry2=dict(getattr(t2,"_ajustada_visual_retry",{}))
        if retry1.get(ms1,0)!=3:
            return False, f"D FAIL t1 no agotado {retry1}"
        if retry2.get(ms2,0)!=0:
            return False, f"D FAIL t2 contaminado {retry2} retry1 {retry1}"
        # t2 debe aún permitir request
        reqs=[]
        def _cap(p):
            if p.get("video_id")==t2._video_id:
                reqs.append(p.get("ms_lista"))
        t2.preview_visual_solicitada.connect(_cap)
        t2._on_ajustada_need_visual([ms2]); QApplication.processEvents()
        try: t2.preview_visual_solicitada.disconnect(_cap)
        except: pass
        if not reqs:
            return False, f"D FAIL t2 bloqueado injustamente retry2 {retry2} retry1 {retry1}"
        # t1 debe estar bloqueado
        reqs1=[]
        def _cap1(p):
            if p.get("video_id")==vid1:
                reqs1.append(p.get("ms_lista"))
        t1.preview_visual_solicitada.connect(_cap1)
        t1._on_ajustada_need_visual([ms1]); QApplication.processEvents()
        try: t1.preview_visual_solicitada.disconnect(_cap1)
        except: pass
        if reqs1:
            return False, f"D FAIL t1 no bloqueado tras agotar {reqs1}"
        return True, f"D PASS t1 {retry1.get(ms1)} t2 {retry2.get(ms2,0)} aislados"
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

def test_E_stale_no_consume_retry():
    """E — stale/version vieja no consume ni reinicia contador vigente."""
    v,tdir,tarjeta=_setup_ajustada_con_N(N=15, version="v973_E_stale")
    try:
        _drain()
        tarjeta._cache_visual.clear(); tarjeta._cache_visual_pending.clear()
        try: tarjeta._ajustada_visual_retry.clear()
        except: pass
        try: v._cola_previews_visuales.clear(); v._preview_visual_op_actual=None
        except: pass
        ms = sorted(tarjeta._tira_logical_ms)[0]
        ver_old=tarjeta._densidad_version; vid=tarjeta._video_id
        # 1 fallo vigente para ms
        try:
            tarjeta._cache_visual_gen+=1; gen1=tarjeta._cache_visual_gen
            v._preview_visual_op_actual={"video_id": vid, "version": ver_old, "ms_lista": [ms], "request_id": gen1}
            v._al_resultado_preview_visual({"video_id": vid, "version": ver_old, "request_id": gen1, "imagenes": []})
            v._preview_visual_op_actual=None; QApplication.processEvents()
        except: pass
        retry1=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if retry1.get(ms,0)!=1:
            return False, f"E FAIL retry1 no 1 {retry1}"
        # cambiar versión (densidad) -> retry debe resetear
        tarjeta._densidad_manual=30
        tarjeta.set_metadata_densa(tiempos_objetivo(100.0,30), version="v973_E_new"); QApplication.processEvents()
        retry_after_ver=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if retry_after_ver.get(ms,0)!=0:
            return False, f"E FAIL retry no reseteado tras versión {retry_after_ver}"
        # volver a fallar 1 con nueva versión
        ver_new=tarjeta._densidad_version
        try:
            tarjeta._cache_visual_gen+=1; gen2=tarjeta._cache_visual_gen
            v._preview_visual_op_actual={"video_id": vid, "version": ver_new, "ms_lista": [ms], "request_id": gen2}
            v._al_resultado_preview_visual({"video_id": vid, "version": ver_new, "request_id": gen2, "imagenes": []})
            v._preview_visual_op_actual=None; QApplication.processEvents()
        except: pass
        retry2=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if retry2.get(ms,0)!=1:
            return False, f"E FAIL retry2 no 1 tras nueva ver {retry2}"
        # ahora llega stale de vieja versión/gen
        stale={"video_id": vid, "version": ver_old, "request_id": gen1, "imagenes": [(ms, _qimg("#aaaaaa"))]}
        # stale no debe insertar cache ni modificar retry vigente
        before_retry=dict(retry2)
        v._al_resultado_preview_visual(stale)
        QApplication.processEvents()
        retry_after_stale=dict(getattr(tarjeta,"_ajustada_visual_retry",{}))
        if ms in tarjeta._cache_visual:
            return False, f"E FAIL stale insertó cache"
        if retry_after_stale.get(ms,0)!=1:
            return False, f"E FAIL stale modificó retry vigente {before_retry} -> {retry_after_stale}"
        return True, f"E PASS stale no consume retry {retry1}->{retry_after_ver}->{retry2}->{retry_after_stale}"
    finally:
        _cleanup_vis(v)
        try: tdir.cleanup()
        except: pass

TESTS=[
    ("partial_batch_menos_imagenes", test_partial_batch_menos_imagenes_que_solicitados),
    ("stale_no_limpia_vigente", test_stale_no_limpia_pending_vigente),
    ("qimage_null", test_qimage_invalido_null),
    ("error_jpeg_individual", test_error_lectura_jpeg_individual_no_bloquea),
    ("batch_fuera_de_orden", test_batch_fuera_de_orden),
    ("multi_fijadas", test_multi_fijadas_no_cruce),
    ("N_120_200_metrics", test_N_120_200_metrics),
    ("scroll_media_final", test_scroll_zona_media_y_final),
    ("A_transitorio_converge", test_A_transitorio_converge_solo),
    ("B_permanente_acotado", test_B_permanente_acotado),
    ("C_generacion_tardia", test_C_generacion_tardia_reactiva),
    ("D_multi_retry_isolated", test_D_multi_retry_isolated),
    ("E_stale_no_consume", test_E_stale_no_consume_retry),
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
    # métricas finales detalladas para N=120/200
    if not fails:
        print("DIAG COMPLETO: sin huérfanos, pending limpio, reintentable")
    sys.exit(0 if not fails else 1)
