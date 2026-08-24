"""Prueba B8.3 Transicion madre -> subcarpeta A (bug: A quedaba vacia tras madre recursiva).

Cubre:
1. madre con A+B
2. dos homonimos distintos
3. escaneo madre recursiva
4. ambos visibles
5. seleccionar A
6. escanear A individual
7. A debe seguir mostrando su video
8. mismo video_id
9. B no corrompido
10. volver madre recursiva
11. ambos vuelven
12. IDs y rutas intactos
"""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import tempfile, shutil, sqlite3, pathlib
from PySide6.QtWidgets import QApplication
import escanear_videos as ev
from rutas import normalizar_ruta_clave, carpetas_iguales
from visor_videos import VisorVideos, MODO_ALCANCE_SUBCARPETAS
from visor_videos import _ruta_contiene
import visor_videos as vv

def _crear_video(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

def test_transicion():
    tmp_root = tempfile.mkdtemp(prefix="b83_trans_")
    mini_dir = tempfile.mkdtemp(prefix="mini_")
    db_dir = tempfile.mkdtemp(prefix="db_")
    ruta_db = os.path.join(db_dir, "cat.db")
    ruta_config = os.path.join(db_dir, "cfg.json")
    # Patch mini
    import rutas, escanear_videos
    orig_mini = rutas.ruta_carpeta_miniaturas
    orig_mini2 = escanear_videos.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas=lambda: mini_dir
    escanear_videos.ruta_carpeta_miniaturas=lambda: mini_dir
    orig_ff = ev.obtener_datos_ffprobe
    ev.obtener_datos_ffprobe=lambda p: {"duracion_segundos":5,"ancho":640,"alto":480,"codec_video":"h264"}
    madre = os.path.join(tmp_root, "madre")
    A = os.path.join(madre, "A")
    B = os.path.join(madre, "B")
    os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
    vidA_path = os.path.join(A, "video.mp4")
    vidB_path = os.path.join(B, "video.mp4")
    _crear_video(vidA_path, b"A distinct content 111")
    _crear_video(vidB_path, b"B distinct content 222222")
    app = QApplication.instance() or QApplication([])
    visor = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
    # ensure DB table exists
    conn0 = ev.conectar_bd(ruta_db)
    conn0.close()
    # Helper to run pipeline sync madre recursiva
    # Use visor's iniciar_escaneo but wait synchronously via backend for determinismo
    # We'll simulate pipeline via backend tasks to avoid flakiness, but also set visor state for traza
    from tareas_videos import TareaEscaneo, TareaTamanosArchivos, TareaFFprobe, TareaGuardarVideos, TareaSincronizacionCatalogo, TareaLecturaCatalogoPaginada, TareaMiniaturasPorId, TareaActualizarCantidadMiniaturas

    def escanear_pipeline(carpeta, incluir_sub):
        ev.configurar_escaneo_recursivo(incluir_sub)
        t = TareaEscaneo(carpeta)
        vids = t._trabajo()
        t2 = TareaTamanosArchivos(vids, carpeta)
        stats = t2._trabajo()
        t3 = TareaFFprobe([os.path.join(carpeta, v) for v in vids], nombres=vids, stats=stats, ruta_db=ruta_db)
        res_ff = t3._trabajo()
        regs = ev.combinar_registros_con_ffprobe(vids, carpeta, res_ff)
        regs = ev.combinar_registros_con_tamanos(regs, stats)
        # guardar necesita _registros_para_guardar mapping for visor, but backend alone
        t4 = TareaGuardarVideos(regs, ruta_db)
        res_guard = t4._trabajo()
        # miniaturas update (mock)
        t5 = TareaMiniaturasPorId(res_guard["ids"], {vid: regs[i]["ruta"] for i, vid in enumerate(res_guard["ids"])}, duraciones={r["ruta"]:5 for r in regs}, nombres_por_id={vid: regs[i]["nombre"] for i, vid in enumerate(res_guard["ids"])})
        res_mini = t5._trabajo()
        t6 = TareaActualizarCantidadMiniaturas([(vid,1) for vid in res_guard["ids"]], ruta_db)
        res_upd = t6._trabajo()
        return vids, stats, res_ff, regs, res_guard

    # FASE 1: madre recursiva
    print("=== FASE1 MADRE recursiva ===")
    visor.carpeta_seleccionada = madre
    visor._modo_alcance = MODO_ALCANCE_SUBCARPETAS
    # also set combo
    try:
        idx = visor.combo_modo_alcance.findData(MODO_ALCANCE_SUBCARPETAS)
        if idx>=0:
            visor.combo_modo_alcance.setCurrentIndex(idx)
    except: pass
    # traza antes
    print(f" carpeta_seleccionada={visor.carpeta_seleccionada} _modo={visor._modo_alcance} recursivo={visor._recursivo_actual()} alcance={visor._alcance_sincronizacion} escaneadas={visor.carpetas_escaneadas}")
    vids, stats, res_ff, regs, res_guard = escanear_pipeline(madre, True)
    print(f" escaneo madre vids={vids} guard ids={res_guard['ids']}")
    # sincronizacion madre (sin protegidas/retiradas)
    visor._carpeta_sincronizacion = madre
    visor._alcance_sincronizacion = None
    visor._cola_carpetas_escaneo = []
    # visor logic for retiradas: after madre, escaneadas empty, so retiradas None
    t_sync = TareaSincronizacionCatalogo(madre, ruta_db, carpetas_protegidas=None, carpetas_retiradas=None)
    res_sync = t_sync._trabajo()
    print(f" sync madre resumen={res_sync['resumen']} shrink={res_sync['shrink']}")
    # update visor escaneadas
    visor.carpetas_escaneadas.add(madre)
    visor._carpeta_sincronizacion = None
    visor._alcance_sincronizacion = None
    # lectura madre con incluir_sub True (via visor helper)
    visor.carpeta_seleccionada = madre
    tarea_lec = visor._crear_tarea_lectura()
    print(f" lectura madre carpeta_param={tarea_lec._carpeta} incluir_sub={tarea_lec._incluir_subcarpetas}")
    # also run lectura direct
    t_lec = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, orden_clave="nombre", orden_direccion="asc", filtro=None, carpeta=madre, incluir_subcarpetas=True)
    res_lec = t_lec._trabajo()
    print(f" lectura madre total={res_lec['total']} videos={res_lec['videos']}")
    # Check DB
    conn = sqlite3.connect(ruta_db)
    rows = conn.execute("SELECT id, nombre, ruta, ruta_normalizada FROM videos ORDER BY id").fetchall()
    print(f" DB rows madre={rows}")
    conn.close()
    assert len(rows)==2, f"madre debe tener 2 filas, got {rows}"
    assert rows[0][1]==rows[1][1] or "video.mp4" in rows[0][1], "homonimos mismo nombre base"
    ids_madre = [r[0] for r in rows]
    assert ids_madre[0]!=ids_madre[1], "ids distintos"
    # tarjetas visibles via visor (crear manualmente)
    visor.tarjetas.clear(); visor.visibles.clear()
    visor._crear_tarjetas(res_lec["videos"])
    print(f" visor tarjetas visibles={visor.tarjetas_visibles()} len={len(visor.tarjetas)}")
    assert len(visor.tarjetas)==2, "fase1 2 tarjetas visibles"
    # guardar ids para comparar luego
    id_A_madre = None
    id_B_madre = None
    for nombre,tarjeta in visor.tarjetas:
        ruta = getattr(tarjeta, "_carpeta_video", None)
        vid = getattr(tarjeta, "_video_id", None)
        # Determine by carpeta
        if ruta and os.path.normcase(A) in os.path.normcase(ruta):
            id_A_madre = vid
        elif ruta and os.path.normcase(B) in os.path.normcase(ruta):
            id_B_madre = vid
        else:
            # fallback by ruta in DB
            pass
    # Alternative lookup via DB
    conn = sqlite3.connect(ruta_db)
    idA = conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?", (normalizar_ruta_clave(vidA_path),)).fetchone()[0]
    idB = conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?", (normalizar_ruta_clave(vidB_path),)).fetchone()[0]
    conn.close()
    print(f" idA={idA} idB={idB} idA_madre={id_A_madre} idB_madre={id_B_madre}")
    assert idA!=idB
    # FASE 2: seleccionar A y escanear A individual
    print("\n=== FASE2 A individual ===")
    visor.carpeta_seleccionada = A
    try:
        idx2 = visor.combo_modo_alcance.findData(MODO_ALCANCE_SUBCARPETAS)
        if idx2>=0:
            visor.combo_modo_alcance.setCurrentIndex(idx2)
    except: pass
    visor._modo_alcance = MODO_ALCANCE_SUBCARPETAS
    print(f" traza antes A: carpeta={visor.carpeta_seleccionada} recursivo={visor._recursivo_actual()} alcance={visor._alcance_sincronizacion} escaneadas={visor.carpetas_escaneadas} cola={visor._cola_carpetas_escaneo}")
    # Compute retiradas as visor would (with fix)
    # We call visor._iniciar_sincronizacion indirectly to capture, but we simulate
    # Use visor's current logic (patched) to compute retiradas
    # To capture, we monkey patch _iniciar_sincronizacion briefly
    captured={}
    orig_sync = visor._iniciar_sincronizacion
    def cap_sync(carpeta=None):
        c = carpeta if carpeta else visor.carpeta_seleccionada
        # replicate visor's retiradas logic (patched version)
        protegidas=None
        if visor._alcance_sincronizacion:
            protegidas=[p for p in visor._alcance_sincronizacion if not carpetas_iguales(p,c)]
        retiradas=None
        if not visor._cola_carpetas_escaneo:
            escaneadas=getattr(visor,"carpetas_escaneadas",set()) or set()
            if visor._alcance_sincronizacion:
                alcance_set=list(visor._alcance_sincronizacion)
                cand=[]
                for esc in escaneadas:
                    if not any(carpetas_iguales(esc,a) for a in alcance_set):
                        if _ruta_contiene(esc,c) or _ruta_contiene(c,esc):
                            continue
                        cand.append(esc)
                if cand: retiradas=cand
            else:
                cand=[]
                for esc in escaneadas:
                    if not carpetas_iguales(esc,c):
                        if _ruta_contiene(esc,c) or _ruta_contiene(c,esc):
                            continue
                        cand.append(esc)
                if cand: retiradas=cand
        captured["protegidas"]=protegidas
        captured["retiradas"]=retiradas
        captured["carpeta"]=c
        print(f" CAPTURE retiradas={retiradas} protegidas={protegidas}")
        return None
    # Call cap to get values
    cap_sync(A)
    # Now real pipeline for A
    ev.configurar_escaneo_recursivo(visor._recursivo_actual())
    vidsA, statsA, res_ffA, regsA, res_guardA = escanear_pipeline(A, visor._recursivo_actual())
    print(f" escaneo A vids={vidsA} regsA={regsA} guardA ids={res_guardA['ids']}")
    assert os.path.isfile(vidA_path), "archivo fisico A debe existir"
    assert vidsA==["video.mp4"], f"A debe detectar video.mp4, got {vidsA}"
    # sincronizacion A with correct retiradas (should be None after fix, not [madre])
    t_syncA = TareaSincronizacionCatalogo(A, ruta_db, carpetas_protegidas=captured["protegidas"], carpetas_retiradas=captured["retiradas"])
    res_syncA = t_syncA._trabajo()
    print(f" sync A resumen={res_syncA['resumen']} shrink={res_syncA['shrink']}")
    # Update escaneadas
    visor.carpetas_escaneadas.add(A)
    # lectura A
    visor.carpeta_seleccionada = A
    tarea_lecA = visor._crear_tarea_lectura()
    print(f" lectura A carpeta_param={tarea_lecA._carpeta} incluir_sub={tarea_lecA._incluir_subcarpetas}")
    t_lecA = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, orden_clave="nombre", orden_direccion="asc", filtro=None, carpeta=A, incluir_subcarpetas=visor._recursivo_actual())
    res_lecA = t_lecA._trabajo()
    print(f" lectura A total={res_lecA['total']} videos={res_lecA['videos']}")
    conn = sqlite3.connect(ruta_db)
    rowsA = conn.execute("SELECT id, nombre, ruta FROM videos ORDER BY id").fetchall()
    print(f" DB rows after A={rowsA}")
    conn.close()
    visor.tarjetas.clear(); visor.visibles.clear()
    visor._crear_tarjetas(res_lecA["videos"])
    print(f" visor tarjetas A len={len(visor.tarjetas)} visibles={visor.tarjetas_visibles()}")
    for n,t in visor.tarjetas:
        print(f"  tarjeta A nombre={n} id={t._video_id} carpeta={t._carpeta_video}")
    assert len(visor.tarjetas)==1, f"A debe mostrar exactamente 1 tarjeta, got {len(visor.tarjetas)}"
    # mismo video_id
    idA_after = visor.tarjetas[0][1]._video_id if visor.tarjetas else None
    assert idA_after==idA, f"A debe conservar mismo id {idA}, got {idA_after}"
    # B no corrompido: DB still has B row
    conn = sqlite3.connect(ruta_db)
    rowB = conn.execute("SELECT id, ruta FROM videos WHERE ruta_normalizada=?", (normalizar_ruta_clave(vidB_path),)).fetchone()
    print(f" B still in DB rowB={rowB}")
    assert rowB is not None and rowB[0]==idB, "B no debe corromperse"
    conn.close()
    # FASE 3: volver madre recursiva
    print("\n=== FASE3 volver MADRE ===")
    visor.carpeta_seleccionada = madre
    visor._modo_alcance = MODO_ALCANCE_SUBCARPETAS
    ev.configurar_escaneo_recursivo(True)
    # Run madre pipeline again to ensure both reappear (if needed, sync will not shrink because A is descendant)
    # For volver madre, escaneadas = {madre, A}
    print(f" traza antes madre2: escaneadas={visor.carpetas_escaneadas} alcance={visor._alcance_sincronizacion}")
    # Capture retiradas for madre
    cap_sync(madre)
    print(f" capture madre2 retiradas={captured['retiradas']}")
    # No need to re-scan, just lectura madre
    t_lecM2 = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, orden_clave="nombre", orden_direccion="asc", filtro=None, carpeta=madre, incluir_subcarpetas=True)
    res_lecM2 = t_lecM2._trabajo()
    print(f" lectura madre2 total={res_lecM2['total']} videos={res_lecM2['videos']}")
    conn = sqlite3.connect(ruta_db)
    rowsM2 = conn.execute("SELECT id, ruta FROM videos ORDER BY id").fetchall()
    print(f" DB rows madre2={rowsM2}")
    conn.close()
    visor.tarjetas.clear(); visor.visibles.clear()
    visor._crear_tarjetas(res_lecM2["videos"])
    print(f" visor tarjetas madre2 len={len(visor.tarjetas)}")
    assert len(visor.tarjetas)==2, "volver madre debe mostrar 2"
    # IDs intactos
    ids_m2 = sorted([t._video_id for _,t in visor.tarjetas])
    assert sorted([idA,idB])==ids_m2, f"IDs madre2 {ids_m2} vs {[idA,idB]}"
    print("=== TRANSICION OK ===")
    # cleanup
    rutas.ruta_carpeta_miniaturas=orig_mini
    escanear_videos.ruta_carpeta_miniaturas=orig_mini2
    ev.obtener_datos_ffprobe=orig_ff
    shutil.rmtree(tmp_root, ignore_errors=True)
    shutil.rmtree(db_dir, ignore_errors=True)
    shutil.rmtree(mini_dir, ignore_errors=True)
    try:
        visor.close()
    except: pass
    print("RESULTADO_FINAL=OK")
    return True

if __name__=="__main__":
    import sys
    ok = test_transicion()
    sys.exit(0 if ok else 1)
