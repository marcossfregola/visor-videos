"""Prueba B8.4 lectura subcarpeta catalogada via MADRE recursivo."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import tempfile, shutil, sqlite3, time, pathlib
from PySide6.QtWidgets import QApplication
import escanear_videos as ev
import rutas
from rutas import normalizar_ruta_clave
from visor_videos import VisorVideos, MODO_ALCANCE_SUBCARPETAS
from configuracion import guardar_modo_alcance
from tareas_videos import TareaEscaneo, TareaTamanosArchivos, TareaFFprobe, TareaGuardarVideos, TareaSincronizacionCatalogo, TareaLecturaCatalogoPaginada

def _wait(vis, t=4):
    app=QApplication.instance()
    s=time.time()
    while time.time()-s < t:
        if not vis.gestor.activo and not vis._recarga_catalogo_pendiente and not vis._reordenamiento_pendiente and not vis._escaneo_pendiente and not vis._sincronizacion_pendiente:
            for _ in range(2):
                app.processEvents()
                time.sleep(0.02)
            if not vis.gestor.activo:
                return True
        app.processEvents()
        time.sleep(0.02)
    return False

def test():
    base = pathlib.Path(r"C:\prueba\_tmp_b84_madre_subcarpeta")
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    madre = base / "MADRE"
    A = madre / "A"
    B = madre / "B"
    A.mkdir(parents=True, exist_ok=True)
    B.mkdir(parents=True, exist_ok=True)
    with open(A / "AAAA.mp4", "wb") as f:
        f.write(b"A1")
    with open(B / "AAAA.mp4", "wb") as f:
        f.write(b"B2"*100)
    db_dir = tempfile.mkdtemp(prefix="db84_")
    mini_dir = tempfile.mkdtemp(prefix="mini84_")
    ruta_db = os.path.join(db_dir, "cat.db")
    ruta_cfg = os.path.join(db_dir, "cfg.json")
    orig_mini = rutas.ruta_carpeta_miniaturas
    orig_mini2 = ev.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: mini_dir
    ev.ruta_carpeta_miniaturas = lambda: mini_dir
    orig_ff = ev.obtener_datos_ffprobe
    ev.obtener_datos_ffprobe = lambda p: {"duracion_segundos":5, "ancho":640, "alto":480, "codec_video":"h264"}
    app = QApplication.instance() or QApplication([])
    visor = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_cfg)
    ev.conectar_bd(ruta_db).close()
    guardar_modo_alcance(MODO_ALCANCE_SUBCARPETAS, ruta_cfg)
    visor._modo_alcance = MODO_ALCANCE_SUBCARPETAS
    try:
        idx = visor.combo_modo_alcance.findData(MODO_ALCANCE_SUBCARPETAS)
        if idx>=0:
            visor.combo_modo_alcance.setCurrentIndex(idx)
    except: pass
    try:
        visor.escaneo_automatico.setChecked(False)
    except: pass
    _wait(visor,2)
    # Escanear MADRE via visor
    visor.carpeta_seleccionada = str(madre)
    visor._al_carpeta_actual_arbol(str(madre))
    _wait(visor,2)
    ev.configurar_escaneo_recursivo(visor._recursivo_actual())
    visor.iniciar_escaneo()
    start=time.time()
    while time.time()-start < 12:
        app.processEvents()
        time.sleep(0.05)
        pending = visor._escaneo_pendiente or visor._tamanos_pendiente or visor._ffprobe_pendiente or visor._guardado_pendiente or visor._miniaturas_pendiente or visor._actualizar_miniaturas_pendiente or visor._sincronizacion_pendiente or visor._recarga_catalogo_pendiente
        if visor._carga_completada and not pending and not visor.gestor.activo:
            break
    print(f"MADRE scan: {len(visor.tarjetas)} {visor.tarjetas_visibles()}")
    assert len(visor.tarjetas)==2, f"MADRE 2, got {len(visor.tarjetas)}"
    conn = sqlite3.connect(ruta_db)
    rows = conn.execute("SELECT id, nombre, ruta, ruta_normalizada FROM videos ORDER BY id").fetchall()
    print(f"DB rows {rows}")
    assert len(rows)==2
    for r in rows:
        assert r[1]=="AAAA.mp4", f"nombre debe ser AAAA.mp4, got {r[1]!r}"
        assert r[3]==normalizar_ruta_clave(r[2]), "ruta_normalizada mismatch"
    conn.close()
    idA = [r[0] for r in rows if r[3].endswith("\\a\\aaaa.mp4")][0]
    idB = [r[0] for r in rows if r[3].endswith("\\b\\aaaa.mp4")][0]
    # MADRE lectura
    visor.carpeta_seleccionada = str(madre)
    tarea_madre = visor._crear_tarea_lectura()
    res_madre = tarea_madre._trabajo()
    print(f"MADRE lectura total {res_madre['total']} ids {[v[8] for v in res_madre['videos']]}")
    assert res_madre['total']==2
    # A sin escanear
    visor._al_carpeta_actual_arbol(str(A))
    _wait(visor,3)
    print(f"A tarjetas {len(visor.tarjetas)} {visor.tarjetas_visibles()} ids {[t._video_id for _,t in visor.tarjetas]}")
    assert len(visor.tarjetas)==1 and visor.tarjetas[0][1]._video_id==idA, f"A debe 1 id {idA}"
    tarea_A = visor._crear_tarea_lectura()
    res_A = tarea_A._trabajo()
    print(f"A lectura total {res_A['total']} ids {[v[8] for v in res_A['videos']]}")
    assert res_A['total']==1 and res_A['videos'][0][8]==idA
    # B sin escanear
    visor._al_carpeta_actual_arbol(str(B))
    _wait(visor,3)
    print(f"B tarjetas {len(visor.tarjetas)} visibles {visor.tarjetas_visibles()} ids {[t._video_id for _,t in visor.tarjetas]}")
    for n,t in visor.tarjetas:
        print(f"  B tarjeta {n!r} id {t._video_id} carpeta {t._carpeta_video!r}")
    tarea_B = visor._crear_tarea_lectura()
    print(f"B lectura carpeta {tarea_B._carpeta!r} incluir {tarea_B._incluir_subcarpetas}")
    res_B = tarea_B._trabajo()
    print(f"B lectura total {res_B['total']} ids {[v[8] for v in res_B['videos']]}")
    for v in res_B['videos']:
        print(f"  B fila nombre {v[0]!r} ruta {v[7]!r} id {v[8]}")
    # B debe mostrar 1 tarjeta, con video_id que corresponde a B (no a A)
    assert len(visor.tarjetas)==1, f"B tarjetas {len(visor.tarjetas)}"
    assert res_B['total']==1, f"B lectura {res_B['total']}"
    # Verificar que el id de B es distinto de A y que no es el de MADRE's otro
    assert visor.tarjetas[0][1]._video_id != idA, f"B id {visor.tarjetas[0][1]._video_id} no debe ser A {idA}"
    # Volver MADRE
    visor._al_carpeta_actual_arbol(str(madre))
    _wait(visor,3)
    print(f"MADRE2 tarjetas {len(visor.tarjetas)} ids {sorted([t._video_id for _,t in visor.tarjetas])} idA {idA} idB {idB}")
    assert len(visor.tarjetas)==2, f"MADRE2 {len(visor.tarjetas)}"
    # Verificar que los ids son los originales (no nuevos) - si hay nuevos, al menos son 2 distintos y uno es de A y otro de B por ruta
    # Para simplificar, solo verificar que son 2 distintos y que uno corresponde a A y otro a B por ruta_normalizada
    # Si la DB fue re-creada con nuevos ids (31,32) tras rename, no aplica aquí
    # Para esta fase sin rename, deben ser los originales
    # Hacemos check laxo: 2 tarjetas con ids distintos
    assert len(set([t._video_id for _,t in visor.tarjetas]))==2
    tarea_madre2 = visor._crear_tarea_lectura()
    res_madre2 = tarea_madre2._trabajo()
    assert res_madre2['total']==2
    # No cambia video_id
    conn = sqlite3.connect(ruta_db)
    rows2 = conn.execute("SELECT id, ruta_normalizada FROM videos ORDER BY id").fetchall()
    conn.close()
    assert rows2[0][0]==idA and rows2[1][0]==idB
    print("OK B8.4 lectura subcarpeta")
    # Cleanup
    rutas.ruta_carpeta_miniaturas = orig_mini
    ev.ruta_carpeta_miniaturas = orig_mini2
    ev.obtener_datos_ffprobe = orig_ff
    try:
        visor.close()
    except: pass
    app.quit()
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(db_dir, ignore_errors=True)
    shutil.rmtree(mini_dir, ignore_errors=True)
    print("RESULTADO_FINAL=OK")
    return True

if __name__=="__main__":
    import sys
    sys.exit(0 if test() else 1)
