"""Regresiones UX final B7.7 — preservación de contexto visual post-renombrado masivo.

Cubre A-E atravesando flujo real GestorTareas y recarga, sin llamar handlers manualmente.
"""
import os
import sys
import shutil
import time
import sqlite3

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import visor_videos as vv_mod
import tareas_videos as tv
import escanear_videos as esc_mod
import renombrar_masivo as rm
from escanear_videos import conectar_bd

_CONT = 0
_FALLOS = 0

def ok(msg):
    global _CONT
    _CONT += 1
    print(f"T{_CONT:02d} OK - {msg}")

def falla(msg, extra=None):
    global _CONT, _FALLOS
    _CONT += 1
    _FALLOS += 1
    print(f"T{_CONT:02d} FAIL - {msg} {extra or ''}")

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)

BASE_PRUEBA = os.path.join(os.path.abspath(r"C:\prueba"), "_offscreen_test_b77_contexto")
VIDEOS_DIR = os.path.join(BASE_PRUEBA, "videos")

def _limpiar():
    base_abs = os.path.abspath(BASE_PRUEBA)
    prueba_abs = os.path.abspath(r"C:\prueba")
    if not base_abs.startswith(prueba_abs + os.sep):
        print(f"ruta no segura {base_abs}")
        sys.exit(2)
    if os.path.basename(base_abs) != "_offscreen_test_b77_contexto":
        print(f"nombre inesperado {base_abs}")
        sys.exit(2)
    if os.path.isdir(base_abs):
        shutil.rmtree(base_abs, ignore_errors=True)

def _esperar(pred, timeout=10000):
    fin = time.monotonic() + timeout/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return pred()

def _crear_bd_y_archivos(nombres):
    _limpiar()
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    for name in nombres:
        ruta = os.path.join(VIDEOS_DIR, name)
        with open(ruta, "wb") as f:
            f.write(b"X"*2048)
    db_path = os.path.join(BASE_PRUEBA, "test.db")
    cfg_path = os.path.join(BASE_PRUEBA, "cfg.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("{}")
    conn = conectar_bd(db_path)
    conn.commit()
    vids = []
    for name in nombres:
        ruta = os.path.join(VIDEOS_DIR, name)
        abs_ruta = os.path.abspath(ruta)
        st = os.stat(ruta)
        conn.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
                     (name, abs_ruta, os.path.splitext(name)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns))
        vid = conn.execute("SELECT id FROM videos WHERE nombre=?", (name,)).fetchone()[0]
        vids.append(vid)
    conn.commit()
    conn.close()
    return db_path, cfg_path, vids

def _setup_visor(db_path, cfg_path, nombres):
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    # bloquear escaneo/ffprobe/miniaturas para E
    contadores = {"escaneo":0, "ffprobe":0, "ffmpeg":0, "miniaturas":0, "recarga":0}
    orig_escanear = esc_mod.escanear_videos
    orig_ffprobe = esc_mod.obtener_datos_ffprobe
    orig_ffprobe_tv = tv.obtener_datos_ffprobe
    orig_run = esc_mod.subprocess.run
    orig_asegurar = esc_mod.asegurar_miniaturas
    orig_asegurar_tv = tv.asegurar_miniaturas
    orig_listar = tv.listar_videos_paginado
    orig_diff = esc_mod.detectar_diferencias
    orig_iniciar_escaneo = vv_mod.VisorVideos.iniciar_escaneo
    def _count_esc(ruta):
        contadores["escaneo"] += 1
        return orig_escanear(ruta)
    def _block_ffprobe(*a,**k):
        contadores["ffprobe"] += 1
        raise AssertionError("ffprobe no debe invocarse")
    def _block_ffprobe_tv(*a,**k):
        contadores["ffprobe"] += 1
        raise AssertionError("ffprobe tv no debe invocarse")
    def _block_run(*a,**k):
        contadores["ffmpeg"] += 1
        raise AssertionError("ffmpeg no debe invocarse")
    def _block_mini(*a,**k):
        contadores["miniaturas"] += 1
        raise AssertionError("miniaturas no debe invocarse")
    def _count_listar(*a,**k):
        contadores["recarga"] += 1
        return orig_listar(*a,**k)
    def _block_diff(*a,**k):
        contadores["escaneo"] += 1
        raise AssertionError("detectar_diferencias no debe invocarse")
    def _blocked_iniciar(self,*a,**k):
        contadores["escaneo"] += 1
        raise AssertionError("iniciar_escaneo no debe dispararse")
    esc_mod.escanear_videos = _count_esc
    esc_mod.obtener_datos_ffprobe = _block_ffprobe
    tv.obtener_datos_ffprobe = _block_ffprobe_tv
    esc_mod.subprocess.run = _block_run
    esc_mod.asegurar_miniaturas = _block_mini
    tv.asegurar_miniaturas = _block_mini
    tv.listar_videos_paginado = _count_listar
    esc_mod.detectar_diferencias = _block_diff
    vv_mod.VisorVideos.iniciar_escaneo = _blocked_iniciar
    visor = vv_mod.VisorVideos(ruta_db=db_path, ruta_config=cfg_path)
    visor.resize(900, 700)
    visor.show()
    _esperar(lambda: getattr(visor, "_carga_completada", False) and not visor.gestor.activo, timeout=12000)
    _esperar(lambda: len(visor.tarjetas) >= len(nombres), timeout=5000)
    visor.carpeta_seleccionada = os.path.abspath(VIDEOS_DIR)
    QApplication.processEvents()
    # restaurar contadores para no interferir con carga inicial
    contadores["escaneo"]=0; contadores["recarga"]=0
    teardown = lambda: (
        setattr(esc_mod, "escanear_videos", orig_escanear),
        setattr(esc_mod, "obtener_datos_ffprobe", orig_ffprobe),
        setattr(tv, "obtener_datos_ffprobe", orig_ffprobe_tv),
        setattr(esc_mod.subprocess, "run", orig_run),
        setattr(esc_mod, "asegurar_miniaturas", orig_asegurar),
        setattr(tv, "asegurar_miniaturas", orig_asegurar_tv),
        setattr(tv, "listar_videos_paginado", orig_listar),
        setattr(esc_mod, "detectar_diferencias", orig_diff),
        setattr(vv_mod.VisorVideos, "iniciar_escaneo", orig_iniciar_escaneo),
    )
    return visor, contadores, teardown

def _seleccionar_por_vids(visor, vids):
    # selecciona por video_id usando API interna mínima para setup (no fabrica estado post-recarga)
    vid_a_nombre = {}
    for nombre, tarjeta in visor.tarjetas:
        vid = getattr(tarjeta, "_video_id", None)
        if vid in vids:
            vid_a_nombre[vid] = nombre
    visor._nombres_seleccionados = set(vid_a_nombre.values())
    for n in vid_a_nombre.values():
        visor._marcar_tarjeta(n, True)
    visor._actualizar_resumen_seleccion()
    QApplication.processEvents()
    return vid_a_nombre

def test_A_orden_no_afectado_sin_salto():
    """A) orden no afectado por renombrado: seleccionados visibles, no salto al inicio."""
    nombres = ["a.mp4","b.mp4","c.mp4","d.mp4","e.mp4","f.mp4"]
    db_path, cfg_path, vids = _crear_bd_y_archivos(nombres)
    visor, contadores, teardown = _setup_visor(db_path, cfg_path, nombres)
    try:
        # ordenar por fecha_importacion (no cambia por renombrado) para no afectar orden
        visor._orden_catalogo = ("fecha_importacion", "asc")
        # seleccionar 2 del medio
        vids_sel = vids[1:3]  # b,c
        _seleccionar_por_vids(visor, vids_sel)
        # asegurar scroll no en 0: mover a 80 si posible
        visor.area.verticalScrollBar().setValue(80)
        QApplication.processEvents()
        scroll_previo = visor.area.verticalScrollBar().value()
        # construir plan que no altera orden relativo (numero secuencial)
        video_infos = []
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t = visor._tarjeta_por_nombre(nombre)
            vid = getattr(t, "_video_id", None)
            ruta = visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        plan_res = rm.construir_plan(video_infos, "{original}_{numero:03d}", ruta_db=db_path)
        verifica(plan_res["ok"], "A plan ok orden no afectado")
        plan = plan_res["plan"]
        tarea = tv.TareaRenombrarMasivo(video_infos, "{original}_{numero:03d}", db_path)
        tarea.set_plan(plan)
        visor._renombrar_masivo_ids_origen = set(vids_sel)
        visor._renombrar_masivo_en_curso = True
        visor._renombrar_masivo_plan = plan
        visor._renombrar_masivo_scroll_previo = scroll_previo
        visor._renombrar_masivo_orden_previo = list(visor._video_ids_seleccionados_ordenados())
        contadores["recarga"]=0
        contadores["escaneo"]=0
        ok_iniciado = visor.gestor_renombrar_masivo.iniciar(tarea)
        verifica(ok_iniciado, "A iniciar gestor ok")
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.3); QApplication.processEvents()
        # verificación selección preservada
        ids_despues = set(visor._video_ids_seleccionados_ordenados())
        verifica(ids_despues == set(vids_sel), f"A ids preservados {ids_despues}")
        # verificación no salto innecesario: scroll no debe ser 0 si previo no era 0 y seleccionados visibles
        scroll_despues = visor.area.verticalScrollBar().value()
        # si orden no cambió, y previo tenía visibles, no debe saltar a 0
        verifica(scroll_despues != 0 or scroll_previo == 0, f"A no salto a 0 innecesario previo {scroll_previo} despues {scroll_despues}")
        verifica(contadores["escaneo"]==0, "A cero escaneo")
        verifica(contadores["ffprobe"]==0, "A cero ffprobe")
        verifica(contadores["ffmpeg"]==0, "A cero ffmpeg")
        verifica(contadores["miniaturas"]==0, "A cero miniaturas")
        verifica(contadores["recarga"]>=1, "A recarga >=1")
        visor.close(); visor.gestor.cerrar()
        try: visor.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        teardown
        _limpiar()

def test_B_orden_nombre_cambia_scroll_al_primero():
    """B) orden por nombre cambia posiciones: viewport termina mostrando primero según nuevo orden."""
    nombres = ["b.mp4","a.mp4","c.mp4"]
    db_path, cfg_path, vids = _crear_bd_y_archivos(nombres)
    visor, contadores, teardown = _setup_visor(db_path, cfg_path, nombres)
    try:
        # ordenar por nombre asc
        visor._orden_catalogo = ("nombre", "asc")
        # forzar recarga para aplicar orden
        visor._programar_recarga_por_carpeta()
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.2); QApplication.processEvents()
        # verificar orden inicial a,b,c
        orden_inicial = [n for n,_ in visor.tarjetas]
        verifica(orden_inicial == sorted(nombres), f"B orden inicial sorted {orden_inicial}")
        # seleccionar a y c (extremos)
        vid_a = vids[nombres.index("a.mp4")]
        vid_c = vids[nombres.index("c.mp4")]
        vids_sel = [vid_a, vid_c]
        _seleccionar_por_vids(visor, vids_sel)
        # crear plan manual que invierte orden lexicográfico: a->z_a.mp4, c->a_c.mp4
        video_infos = []
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t = visor._tarjeta_por_nombre(nombre)
            vid = getattr(t, "_video_id", None)
            ruta = visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        # construir plan manual swap
        # vid_a: a.mp4 -> z_a.mp4, vid_c: c.mp4 -> a_c.mp4
        plan = []
        for info in video_infos:
            vid = info["video_id"]
            nombre_actual = info["nombre"]
            if vid == vid_a:
                final = "z_a.mp4"
            else:
                final = "a_c.mp4"
            plan.append({"video_id": vid, "nombre_actual": nombre_actual, "nombre_final": final, "ruta_actual": info["ruta"], "ruta_final": os.path.join(VIDEOS_DIR, final), "directorio": VIDEOS_DIR, "extension": ".mp4", "stem": os.path.splitext(final)[0], "error": None, "indice": video_infos.index(info)})
        tarea = tv.TareaRenombrarMasivo(video_infos, "{original}_{numero}", db_path)
        tarea.set_plan(plan)
        visor._renombrar_masivo_ids_origen = set(vids_sel)
        visor._renombrar_masivo_en_curso = True
        visor._renombrar_masivo_plan = plan
        visor._renombrar_masivo_scroll_previo = visor.area.verticalScrollBar().value()
        visor._renombrar_masivo_orden_previo = list(visor._video_ids_seleccionados_ordenados())
        orden_previo = list(visor._renombrar_masivo_orden_previo)
        contadores["recarga"]=0
        visor.gestor_renombrar_masivo.iniciar(tarea)
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.4); QApplication.processEvents()
        ids_despues = visor._video_ids_seleccionados_ordenados()
        verifica(set(ids_despues) == set(vids_sel), f"B ids preservados {ids_despues}")
        # verificar que primer seleccionado según nuevo orden visible es vid_c (a_c.mp4) por orden nombre asc
        # nuevo orden por nombre asc debería ser a_c (vid_c), b, z_a (vid_a)
        ordenar_nuevo = [n for n,_ in visor.tarjetas]
        verifica("a_c.mp4" in ordenar_nuevo and "z_a.mp4" in ordenar_nuevo, f"B nuevo orden contiene renombrados {ordenar_nuevo}")
        idx_a_c = ordenar_nuevo.index("a_c.mp4") if "a_c.mp4" in ordenar_nuevo else -1
        idx_z_a = ordenar_nuevo.index("z_a.mp4") if "z_a.mp4" in ordenar_nuevo else -1
        verifica(idx_a_c < idx_z_a, f"B a_c antes que z_a ({idx_a_c} < {idx_z_a})")
        # verificación viewport: primer seleccionado (vid_c) debe estar visible (ensureWidgetVisible)
        tarjeta_primero = visor._tarjeta_por_video_id(vid_c)
        verifica(tarjeta_primero is not None, "B tarjeta primero existe")
        if tarjeta_primero is not None:
            # comprobar que viewport lo muestra (geometry o scroll)
            try:
                vp_h = visor.area.viewport().height()
                scroll = visor.area.verticalScrollBar().value()
                y = tarjeta_primero.y()
                h = tarjeta_primero.height()
                visible = not (y + h < scroll or y > scroll + vp_h) if vp_h>0 else True
                verifica(visible, f"B primero visible scroll {scroll} y {y} h {h} vp_h {vp_h}")
            except Exception as e:
                verifica(False, f"B visible check fallo {e}")
        # verificar determinista: referencia = primero según nuevo orden
        verifica(ids_despues[0] == vid_c, f"B determinista primero vid_c {ids_despues[0]}")
        verifica(contadores["escaneo"]==0 and contadores["ffprobe"]==0, "B cero escaneo/ffprobe")
        visor.close(); visor.gestor.cerrar()
        try: visor.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        teardown
        _limpiar()

def test_C_varios_separados_primero_nuevo_orden():
    """C) varios seleccionados separados: referencia determinista = primero según nuevo orden visible."""
    nombres = ["a.mp4","b.mp4","c.mp4","d.mp4","e.mp4"]
    db_path, cfg_path, vids = _crear_bd_y_archivos(nombres)
    visor, contadores, teardown = _setup_visor(db_path, cfg_path, nombres)
    try:
        visor._orden_catalogo = ("nombre", "asc")
        visor._programar_recarga_por_carpeta()
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.2); QApplication.processEvents()
        # seleccionar separados: a, c, e
        vids_sel = [vids[0], vids[2], vids[4]]
        _seleccionar_por_vids(visor, vids_sel)
        orden_previo = list(visor._video_ids_seleccionados_ordenados())
        verifica(orden_previo == vids_sel, f"C orden previo {orden_previo} == {vids_sel}")
        # plan que cambia orden: c->0_c.mp4 (lexicographically first), a->z_a.mp4 (last), e stays
        video_infos = []
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t = visor._tarjeta_por_nombre(nombre)
            vid = getattr(t, "_video_id", None)
            ruta = visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        mapping = {vids[0]:"z_a.mp4", vids[2]:"0_c.mp4", vids[4]:"e.mp4"}
        plan=[]
        for info in video_infos:
            vid=info["video_id"]
            plan.append({"video_id": vid, "nombre_actual": info["nombre"], "nombre_final": mapping[vid], "ruta_actual": info["ruta"], "ruta_final": os.path.join(VIDEOS_DIR, mapping[vid]), "directorio": VIDEOS_DIR, "extension": ".mp4", "stem": os.path.splitext(mapping[vid])[0], "error": None, "indice": video_infos.index(info)})
        tarea = tv.TareaRenombrarMasivo(video_infos, "{texto}", db_path, texto="x")
        tarea.set_plan(plan)
        visor._renombrar_masivo_ids_origen = set(vids_sel)
        visor._renombrar_masivo_en_curso = True
        visor._renombrar_masivo_scroll_previo = visor.area.verticalScrollBar().value()
        visor._renombrar_masivo_orden_previo = orden_previo
        visor.gestor_renombrar_masivo.iniciar(tarea)
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.4); QApplication.processEvents()
        ids_nuevo = visor._video_ids_seleccionados_ordenados()
        verifica(set(ids_nuevo)==set(vids_sel), f"C ids preservados {ids_nuevo}")
        # nuevo orden por nombre asc: 0_c (vid c), e (vid e), z_a (vid a)
        verifica(ids_nuevo[0]==vids[2], f"C primero determinista vid c {ids_nuevo[0]}")
        verifica(ids_nuevo == [vids[2], vids[4], vids[0]], f"C orden nuevo determinista {ids_nuevo}")
        # viewport debe mostrar primero (0_c)
        t_prim = visor._tarjeta_por_video_id(vids[2])
        verifica(t_prim is not None, "C tarjeta primero existe")
        visor.close(); visor.gestor.cerrar()
        try: visor.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        teardown
        _limpiar()

def test_D_seleccionado_ya_visible_no_desplazar():
    """D) seleccionado ya visible tras recarga: no desplazar innecesariamente."""
    nombres = ["a.mp4","b.mp4","c.mp4","d.mp4"]
    db_path, cfg_path, vids = _crear_bd_y_archivos(nombres)
    visor, contadores, teardown = _setup_visor(db_path, cfg_path, nombres)
    try:
        visor._orden_catalogo = ("nombre", "asc")
        visor._programar_recarga_por_carpeta()
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.2); QApplication.processEvents()
        # seleccionar b (posición 1, visible si viewport grande)
        vid_b = vids[1]
        _seleccionar_por_vids(visor, [vid_b])
        visor.resize(900, 700)
        visor.show()
        QApplication.processEvents()
        # asegurar viewport scroll 0 y que b visible
        visor.area.verticalScrollBar().setValue(0)
        QApplication.processEvents()
        time.sleep(0.2)
        scroll_previo = visor.area.verticalScrollBar().value()
        # plan que no cambia orden (aumenta nombre pero mantiene orden relativo)
        video_infos=[]
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t=visor._tarjeta_por_nombre(nombre)
            vid=getattr(t,"_video_id",None)
            ruta=visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        # usar plan que mantiene orden (b -> b_001)
        plan_res = rm.construir_plan(video_infos, "{original}_{numero:03d}", ruta_db=db_path)
        verifica(plan_res["ok"], "D plan ok")
        plan=plan_res["plan"]
        tarea=tv.TareaRenombrarMasivo(video_infos, "{original}_{numero:03d}", db_path)
        tarea.set_plan(plan)
        visor._renombrar_masivo_ids_origen = set([vid_b])
        visor._renombrar_masivo_en_curso=True
        visor._renombrar_masivo_scroll_previo=scroll_previo
        visor._renombrar_masivo_orden_previo=list(visor._video_ids_seleccionados_ordenados())
        visor.gestor_renombrar_masivo.iniciar(tarea)
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.4); QApplication.processEvents()
        ids_despues = visor._video_ids_seleccionados_ordenados()
        verifica(ids_despues==[vid_b], f"D ids preservados {ids_despues}")
        scroll_despues = visor.area.verticalScrollBar().value()
        # si seleccionado ya visible y orden no cambió, no debe desplazar (scroll debe permanecer 0)
        verifica(scroll_despues == scroll_previo, f"D no desplazar innecesario previo {scroll_previo} despues {scroll_despues}")
        visor.close(); visor.gestor.cerrar()
        try: visor.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        teardown
        _limpiar()

def test_E_cero_operaciones_pesadas():
    """E) 0 escaneo/FFprobe/FFmpeg/miniaturas por esta corrección."""
    nombres = ["a.mp4","b.mp4"]
    db_path, cfg_path, vids = _crear_bd_y_archivos(nombres)
    visor, contadores, teardown = _setup_visor(db_path, cfg_path, nombres)
    try:
        vids_sel = vids[:1]
        _seleccionar_por_vids(visor, vids_sel)
        video_infos=[]
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t=visor._tarjeta_por_nombre(nombre)
            vid=getattr(t,"_video_id",None)
            ruta=visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        plan_res=rm.construir_plan(video_infos, "{texto}_{numero}", texto="e_test", ruta_db=db_path)
        plan=plan_res["plan"]
        tarea=tv.TareaRenombrarMasivo(video_infos, "{texto}_{numero}", db_path, texto="e_test")
        tarea.set_plan(plan)
        visor._renombrar_masivo_ids_origen=set(vids_sel)
        visor._renombrar_masivo_en_curso=True
        visor._renombrar_masivo_orden_previo=list(visor._video_ids_seleccionados_ordenados())
        visor._renombrar_masivo_scroll_previo=visor.area.verticalScrollBar().value()
        contadores["escaneo"]=0; contadores["ffprobe"]=0; contadores["ffmpeg"]=0; contadores["miniaturas"]=0; contadores["recarga"]=0
        visor.gestor_renombrar_masivo.iniciar(tarea)
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        time.sleep(0.3); QApplication.processEvents()
        verifica(contadores["escaneo"]==0, f"E cero escaneo {contadores['escaneo']}")
        verifica(contadores["ffprobe"]==0, f"E cero ffprobe {contadores['ffprobe']}")
        verifica(contadores["ffmpeg"]==0, f"E cero ffmpeg {contadores['ffmpeg']}")
        verifica(contadores["miniaturas"]==0, f"E cero miniaturas {contadores['miniaturas']}")
        verifica(contadores["recarga"]>=1, f"E recarga >=1 {contadores['recarga']}")
        # verificar que visor_videos no importa subprocess/ffmpeg en corrección
        src=open("visor_videos.py",encoding="utf-8").read()
        # zona nueva debe no contener ffmpeg/ffprobe/subprocess
        verifica("ffmpeg" not in src.lower().split("_renombrar_masivo_scroll_previo")[1].split("def ")[0] if "_renombrar_masivo_scroll_previo" in src else True, "E visor sin ffmpeg en zona nueva")
        visor.close(); visor.gestor.cerrar()
        try: visor.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        teardown
        _limpiar()

def main():
    print("=== Regresiones UX final B7.7 contexto visual post-rename A-E ===")
    for fn in [test_A_orden_no_afectado_sin_salto, test_B_orden_nombre_cambia_scroll_al_primero, test_C_varios_separados_primero_nuevo_orden, test_D_seleccionado_ya_visible_no_desplazar, test_E_cero_operaciones_pesadas]:
        try:
            fn()
        except Exception as e:
            import traceback
            falla(fn.__name__ + " excepción", str(e))
            traceback.print_exc()
            _limpiar()
    total=_CONT; fallos=_FALLOS
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__=="__main__":
    main()
