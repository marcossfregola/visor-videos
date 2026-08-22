"""Regresión B7.7 post-rename — selección preservada por video_id sin escaneo global.

Flujo real GestorTareas -> tarea_resultado -> tarea_finalizada -> recarga SQLite -> selección restaurada.
No invoca handlers de finalización manualmente para fabricar estado.
"""
import os
import sys
import shutil
import sqlite3
import time
import inspect

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop

import visor_videos as vv_mod
import tareas_videos as tv
import escanear_videos as esc_mod
import renombrar_masivo as rm

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

BASE_PRUEBA = os.path.join(os.path.abspath(r"C:\prueba"), "_offscreen_test_b77_fix")
VIDEOS_DIR = os.path.join(BASE_PRUEBA, "videos")

def _limpiar():
    base_abs = os.path.abspath(BASE_PRUEBA)
    prueba_abs = os.path.abspath(r"C:\prueba")
    if not base_abs.startswith(prueba_abs + os.sep):
        print(f"ruta no segura {base_abs}")
        sys.exit(2)
    if os.path.basename(base_abs) != "_offscreen_test_b77_fix":
        print(f"nombre inesperado {base_abs}")
        sys.exit(2)
    if os.path.isdir(base_abs):
        shutil.rmtree(base_abs, ignore_errors=True)

def _esperar(pred, timeout=8000):
    fin = time.monotonic() + timeout/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return pred()

def _crear_bd_y_archivos():
    _limpiar()
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    for name, content in [("a.mp4", b"A"*2048), ("b.mp4", b"B"*2048), ("c.mp4", b"C"*2048)]:
        ruta = os.path.join(VIDEOS_DIR, name)
        with open(ruta, "wb") as f:
            f.write(content)
    db_path = os.path.join(BASE_PRUEBA, "test.db")
    cfg_path = os.path.join(BASE_PRUEBA, "cfg.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("{}")
    from escanear_videos import conectar_bd
    conn = conectar_bd(db_path)
    conn.commit()
    vids = []
    for name in ["a.mp4", "b.mp4", "c.mp4"]:
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

def test_seleccion_preservada_exitoso():
    """3 videos -> GestorTareas real TareaRenombrarMasivo -> recarga catalog -> mismos 3 video_id seleccionados."""
    db_path, cfg_path, vids = _crear_bd_y_archivos()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    contadores = {"escaneo":0, "ffprobe":0, "ffmpeg":0, "miniaturas":0, "recarga":0}
    orig_escanear = esc_mod.escanear_videos
    orig_ffprobe = esc_mod.obtener_datos_ffprobe
    orig_ffprobe_tv = tv.obtener_datos_ffprobe
    orig_run = esc_mod.subprocess.run
    orig_asegurar = esc_mod.asegurar_miniaturas
    orig_asegurar_tv = tv.asegurar_miniaturas
    orig_listar = tv.listar_videos_paginado
    orig_diff = esc_mod.detectar_diferencias
    try:
        def _count_esc(ruta):
            contadores["escaneo"] += 1
            return orig_escanear(ruta)
        def _count_ffprobe(ruta):
            contadores["ffprobe"] += 1
            raise AssertionError("ffprobe no debe invocarse en post-rename recarga")
        def _count_ffprobe_tv(*a,**k):
            contadores["ffprobe"] += 1
            raise AssertionError("ffprobe tv no debe invocarse")
        def _count_run(*a,**k):
            contadores["ffmpeg"] += 1
            raise AssertionError("ffmpeg no debe invocarse")
        def _count_mini(*a,**k):
            contadores["miniaturas"] += 1
            raise AssertionError("miniaturas no debe invocarse en recarga")
        def _count_listar(*a,**k):
            contadores["recarga"] += 1
            return orig_listar(*a,**k)
        def _count_diff(*a,**k):
            contadores["escaneo"] += 1
            raise AssertionError("detectar_diferencias no debe invocarse")
        esc_mod.escanear_videos = _count_esc
        esc_mod.obtener_datos_ffprobe = _count_ffprobe
        tv.obtener_datos_ffprobe = _count_ffprobe_tv
        esc_mod.subprocess.run = _count_run
        esc_mod.asegurar_miniaturas = _count_mini
        tv.asegurar_miniaturas = _count_mini
        tv.listar_videos_paginado = _count_listar
        esc_mod.detectar_diferencias = _count_diff

        orig_iniciar_escaneo = vv_mod.VisorVideos.iniciar_escaneo
        def _blocked_iniciar(self, *a, **k):
            contadores["escaneo"] += 1
            raise AssertionError("iniciar_escaneo no debe dispararse tras renombrado masivo")
        vv_mod.VisorVideos.iniciar_escaneo = _blocked_iniciar

        visor = vv_mod.VisorVideos(ruta_db=db_path, ruta_config=cfg_path)
        visor.resize(720,540)
        visor.show()
        _esperar(lambda: getattr(visor, "_carga_completada", False) and not visor.gestor.activo, timeout=10000)
        _esperar(lambda: len(visor.tarjetas) >= 3, timeout=5000)
        verifica(len(visor.tarjetas) >= 3, f"tarjetas cargadas {len(visor.tarjetas)} >=3")
        verifica(not visor.gestor.activo, "gestor principal inactivo tras carga inicial")
        verifica(getattr(visor, "_carga_completada", False), "carga_completada True tras carga")
        visor.carpeta_seleccionada = os.path.abspath(VIDEOS_DIR)
        QApplication.processEvents()
        vid_a_nombre = {}
        for nombre, tarjeta in visor.tarjetas:
            vid = getattr(tarjeta, "_video_id", None)
            if vid in vids:
                vid_a_nombre[vid] = nombre
        verifica(len(vid_a_nombre)==3, f"mapeo vid->nombre 3 {vid_a_nombre}")
        verifica(set(vid_a_nombre.keys())==set(vids), "mapeo cubre todos los vids")
        visor._nombres_seleccionados = set(vid_a_nombre.values())
        for n in vid_a_nombre.values():
            visor._marcar_tarjeta(n, True)
        visor._actualizar_resumen_seleccion()
        QApplication.processEvents()
        verifica(visor.boton_renombrar_masivo.isEnabled(), "botón Renombrar habilitado con 3")
        verifica(len(visor._nombres_seleccionados)==3, "3 seleccionados antes")
        ids_antes = set(visor._video_ids_seleccionados_ordenados())
        verifica(ids_antes == set(vids), f"ids antes {ids_antes} == {set(vids)}")
        verifica(visor.resumen_seleccion.text().startswith("3 de"), "resumen 3 de ... antes")
        video_infos = []
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t = visor._tarjeta_por_nombre(nombre)
            vid = getattr(t, "_video_id", None)
            ruta = visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        verifica(len(video_infos)==3, "video_infos 3 en orden visible")
        verifica(all(isinstance(x["video_id"], int) and x["video_id"]>0 for x in video_infos), "video_infos tipos válidos")
        plan_res = rm.construir_plan(video_infos, "{texto}_{numero}", texto="renom", ruta_db=db_path)
        verifica(plan_res["ok"], "plan ok {texto}_{numero}")
        verifica(len(plan_res["plan"])==3, "plan 3 items")
        verifica(all(p.get("nombre_final") for p in plan_res["plan"]), "plan nombres_final no vacíos")
        verifica(all(p.get("error") is None for p in plan_res["plan"]), "plan sin errores por item")
        plan = plan_res["plan"]
        src_handler = inspect.getsource(vv_mod.VisorVideos._al_resultado_renombrar_masivo)
        verifica("iniciar_escaneo" not in src_handler and "TareaEscaneo" not in src_handler, "handler cero Escanear carpeta")
        verifica("_programar_recarga_por_carpeta" in src_handler, "handler usa _programar_recarga_por_carpeta")
        # verificar que visor_videos no contiene ExceptHandler solo-pass en código nuevo ni fallback silencioso
        src_visor = open("visor_videos.py", encoding="utf-8").read()
        # el fix no debe introducir 'except Exception:' seguido de pass en zona renombrar ni reemplazar
        verifica("self._renombrar_masivo_ids_origen = {int(v[\"video_id\"])" not in src_visor or "diagnostico_ids" in src_visor, "fix ids_origen valida explícitamente sin fallback silencioso")
        # Preparar secuencia real GestorTareas
        secuencia = []
        def _seq_resultado(val):
            secuencia.append("tarea_resultado")
        def _seq_finalizada():
            secuencia.append("tarea_finalizada")
        def _seq_recarga_res(val):
            secuencia.append("recarga_resultado")
        # Conectar capturas adicionales (no reemplazan handlers originales)
        visor.gestor_renombrar_masivo.tarea_resultado.connect(_seq_resultado)
        visor.gestor_renombrar_masivo.tarea_finalizada.connect(_seq_finalizada)
        # Capturar recarga del gestor principal
        # Guardar original _al_resultado_recarga para detectar orden
        orig_al_recarga = visor._al_resultado_recarga
        def _wrapped_recarga(res):
            secuencia.append("recarga_resultado_wrapped")
            return orig_al_recarga(res)
        visor._al_resultado_recarga = _wrapped_recarga
        # Patch del gestor principal tarea_resultado para detectar recarga via señal
        def _seq_gestor_resultado(val):
            # solo si es recarga (identificable por contener 'videos' y 'total')
            if isinstance(val, dict) and "videos" in val and "total" in val:
                if "recarga_gestor_resultado" not in secuencia:
                    secuencia.append("recarga_gestor_resultado")
        visor.gestor.tarea_resultado.connect(_seq_gestor_resultado)
        # Crear TareaRenombrarMasivo real y lanzar via GestorTareas (sin llamar handlers manualmente)
        from tareas_videos import TareaRenombrarMasivo
        tarea = TareaRenombrarMasivo(video_infos, "{texto}_{numero}", db_path, texto="renom")
        tarea.set_plan(plan)
        # Preservar ids_origen como hace _iniciar_renombrar_masivo pero con validación explícita (no genérica)
        ids_origen_check = set()
        diag = None
        for idx, info in enumerate(video_infos):
            if not isinstance(info, dict):
                diag = f"idx {idx} no dict"
                break
            v = info.get("video_id")
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                diag = f"vid inválido {v!r}"
                break
            ids_origen_check.add(int(v))
        verifica(diag is None, f"validación explícita ids_origen sin excepción genérica ({diag})")
        visor._renombrar_masivo_ids_origen = ids_origen_check
        visor._renombrar_masivo_en_curso = True
        visor._renombrar_masivo_plan = plan
        contadores["recarga"] = 0
        contadores["escaneo"] = 0
        secuencia.clear()
        ok_iniciado = visor.gestor_renombrar_masivo.iniciar(tarea)
        verifica(ok_iniciado, "gestor_renombrar_masivo.iniciar OK")
        verifica(visor.gestor_renombrar_masivo.activo, "gestor renombrar activo tras iniciar")
        verifica(visor._renombrar_masivo_en_curso, "_renombrar_masivo_en_curso True tras iniciar")
        verifica(visor.boton_cancelar_renombrar_masivo.isVisible(), "botón cancelar renombrar visible tras iniciar")
        # Esperar flujo real: tarea_resultado -> tarea_finalizada -> recarga catalog -> gestor inactivo y selección restaurada
        # El visor programa recarga tras tarea_resultado; tarea_finalizada limpia _en_curso
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        verifica(not visor.gestor_renombrar_masivo.activo, "gestor renombrar inactivo tras tarea_finalizada (señal real)")
        verifica("tarea_resultado" in secuencia, f"secuencia contiene tarea_resultado {secuencia}")
        verifica("tarea_finalizada" in secuencia, f"secuencia contiene tarea_finalizada {secuencia}")
        verifica(secuencia.index("tarea_resultado") < secuencia.index("tarea_finalizada"), f"orden resultado antes de finalizada {secuencia}")
        # Esperar recarga SQLite terminada (gestor principal)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        # Dar tiempo a _reemplazar_tarjetas (corre en hilo UI tras resultado recarga) - sin forzar refrescos manuales
        QApplication.processEvents()
        time.sleep(0.25)
        QApplication.processEvents()
        QApplication.processEvents()
        verifica(not visor.gestor.activo, "gestor principal inactivo tras recarga")
        verifica(not visor._recarga_catalogo_pendiente, "recarga_catalogo no pendiente tras recarga")
        verifica(not visor._renombrar_masivo_en_curso, "_renombrar_masivo_en_curso False tras tarea_finalizada real (no llamada manual)")
        verifica(visor._renombrar_masivo_ids_a_restaurar is None, "ids_a_restaurar consumido tras _reemplazar_tarjetas")
        verifica(visor._renombrar_masivo_ids_origen is None, "ids_origen consumido tras recarga")
        # Verificar selección por video_id preservada solo después de flujo completo
        ids_despues = set(visor._video_ids_seleccionados_ordenados())
        verifica(ids_despues == set(vids), f"ids después {ids_despues} == {set(vids)} (preservados por video_id)")
        verifica(len(visor._nombres_seleccionados)==3, f"3 seleccionados después {visor._nombres_seleccionados}")
        verifica(visor.resumen_seleccion.text().startswith("3 de"), "resumen 3 de ... después")
        for vid in vids:
            t = visor._tarjeta_por_video_id(vid)
            verifica(t is not None, f"tarjeta vid {vid} existe tras rename")
            if t is not None:
                verifica(t._seleccionada, f"vid {vid} marcada seleccionada")
                verifica(t._check.isChecked(), f"vid {vid} check marcado")
                verifica(t._nombre != vid_a_nombre.get(vid), f"vid {vid} nombre cambió {t._nombre} != {vid_a_nombre.get(vid)}")
                verifica(t._nombre.startswith("renom_"), f"vid {vid} nombre final con prefijo renom_ {t._nombre}")
        verifica(visor.boton_renombrar_masivo.isEnabled(), "botón renombrar habilitado tras preservación")
        verifica(visor.boton_mover_seleccionados.isEnabled(), "mover habilitado coherente tras recarga")
        verifica(visor.boton_copiar_seleccionados.isEnabled(), "copiar habilitado tras recarga")
        verifica(visor.boton_eliminar_seleccionados.isEnabled(), "eliminar habilitado tras recarga")
        verifica(not visor.boton_cancelar_renombrar_masivo.isVisible(), "botón cancelar renombrar no visible tras finalizada real")
        verifica(contadores["escaneo"]==0, f"cero Escanear carpeta ({contadores['escaneo']})")
        verifica(contadores["ffprobe"]==0, f"cero FFprobe ({contadores['ffprobe']})")
        verifica(contadores["ffmpeg"]==0, f"cero FFmpeg ({contadores['ffmpeg']})")
        verifica(contadores["miniaturas"]==0, f"cero miniaturas ({contadores['miniaturas']})")
        verifica(contadores["recarga"]>=1, f"al menos 1 recarga SQLite ({contadores['recarga']})")
        verifica("recarga_gestor_resultado" in secuencia or "recarga_resultado_wrapped" in secuencia, f"secuencia recarga observada {secuencia}")
        temporales = [f for f in os.listdir(VIDEOS_DIR) if f.startswith("__tmp_mass_")]
        verifica(len(temporales)==0, f"no temporales residuales {temporales}")
        verifica(not visor.gestor_renombrar_masivo.activo and not visor.gestor.activo, "ambos gestores inactivos al final")
        visor.close()
        visor.gestor.cerrar()
        try:
            visor.gestor_renombrar_masivo.cerrar()
        except Exception:
            pass
        print("TEST exitoso gestortareas real finalizado")
    finally:
        esc_mod.escanear_videos = orig_escanear
        esc_mod.obtener_datos_ffprobe = orig_ffprobe
        tv.obtener_datos_ffprobe = orig_ffprobe_tv
        esc_mod.subprocess.run = orig_run
        esc_mod.asegurar_miniaturas = orig_asegurar
        tv.asegurar_miniaturas = orig_asegurar_tv
        tv.listar_videos_paginado = orig_listar
        esc_mod.detectar_diferencias = orig_diff
        vv_mod.VisorVideos.iniciar_escaneo = orig_iniciar_escaneo
        _limpiar()

def test_parcial():
    """Resultado parcial via GestorTareas real: 3 videos, 1 archivo faltante -> 2 ok 1 fallido, preservar 3 ids (recreado)."""
    db_path, cfg_path, vids = _crear_bd_y_archivos()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    orig_listar = tv.listar_videos_paginado
    contadores = {"recarga":0, "escaneo":0}
    try:
        def _count_listar(*a,**k):
            contadores["recarga"] += 1
            return orig_listar(*a,**k)
        tv.listar_videos_paginado = _count_listar
        orig_iniciar = vv_mod.VisorVideos.iniciar_escaneo
        def _blocked(self,*a,**k):
            contadores["escaneo"] += 1
            raise AssertionError("no escaneo en parcial")
        vv_mod.VisorVideos.iniciar_escaneo = _blocked

        visor = vv_mod.VisorVideos(ruta_db=db_path, ruta_config=cfg_path)
        visor.resize(720,540)
        visor.show()
        _esperar(lambda: getattr(visor, "_carga_completada", False) and not visor.gestor.activo, timeout=10000)
        _esperar(lambda: len(visor.tarjetas) >=3, timeout=5000)
        visor.carpeta_seleccionada = os.path.abspath(VIDEOS_DIR)
        QApplication.processEvents()
        vid_a_nombre = {}
        for nombre, t in visor.tarjetas:
            vid = getattr(t, "_video_id", None)
            if vid in vids:
                vid_a_nombre[vid] = nombre
        visor._nombres_seleccionados = set(vid_a_nombre.values())
        for n in vid_a_nombre.values():
            visor._marcar_tarjeta(n, True)
        QApplication.processEvents()
        video_infos = []
        for nombre in visor.tarjetas_visibles():
            if nombre not in visor._nombres_seleccionados:
                continue
            t = visor._tarjeta_por_nombre(nombre)
            vid = getattr(t, "_video_id", None)
            ruta = visor._ruta_video_de(t) or os.path.join(VIDEOS_DIR, nombre)
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        # provocar fallo en uno: eliminar archivo c.mp4 antes de ejecutar tarea
        os.remove(os.path.join(VIDEOS_DIR, "c.mp4"))
        plan_res = rm.construir_plan(video_infos, "{texto}_{numero}", texto="parcial", ruta_db=db_path)
        verifica(plan_res["ok"], "plan parcial ok")
        verifica(len(plan_res["plan"])==3, "plan parcial 3")
        plan = plan_res["plan"]
        from tareas_videos import TareaRenombrarMasivo
        tarea = TareaRenombrarMasivo(video_infos, "{texto}_{numero}", db_path, texto="parcial")
        tarea.set_plan(plan)
        secuencia = []
        visor.gestor_renombrar_masivo.tarea_resultado.connect(lambda v: secuencia.append("tarea_resultado_parcial"))
        visor.gestor_renombrar_masivo.tarea_finalizada.connect(lambda: secuencia.append("tarea_finalizada_parcial"))
        visor._renombrar_masivo_ids_origen = set(vids)
        visor._renombrar_masivo_en_curso = True
        visor._renombrar_masivo_plan = plan
        ok_ini = visor.gestor_renombrar_masivo.iniciar(tarea)
        verifica(ok_ini, "gestor parcial iniciar OK")
        _esperar(lambda: not visor.gestor_renombrar_masivo.activo, timeout=10000)
        verifica(not visor.gestor_renombrar_masivo.activo, "gestor parcial inactivo tras finalizada")
        verifica("tarea_resultado_parcial" in secuencia, "secuencia parcial resultado real")
        verifica("tarea_finalizada_parcial" in secuencia, "secuencia parcial finalizada real")
        # recuperar archivo para que recarga no afecte pertenencia
        open(os.path.join(VIDEOS_DIR, "c.mp4"), "wb").write(b"C"*2048)
        _esperar(lambda: not visor.gestor.activo and not visor._recarga_catalogo_pendiente, timeout=10000)
        QApplication.processEvents()
        time.sleep(0.25)
        QApplication.processEvents()
        QApplication.processEvents()
        verifica(not visor._renombrar_masivo_en_curso, "parcial _en_curso False tras señal real")
        ids_despues = set(visor._video_ids_seleccionados_ordenados())
        verifica(ids_despues == set(vids), f"parcial ids después {ids_despues} == {set(vids)}")
        verifica(len(visor._nombres_seleccionados)==3, f"parcial 3 checks {visor._nombres_seleccionados}")
        verifica(contadores["escaneo"]==0, "parcial cero escaneo")
        verifica(contadores["recarga"]>=1, f"parcial recarga >=1 ({contadores['recarga']})")
        verifica(not visor.boton_cancelar_renombrar_masivo.isVisible(), "parcial cancelar no visible tras finalizada")
        visor.close()
        visor.gestor.cerrar()
        try:
            visor.gestor_renombrar_masivo.cerrar()
        except Exception:
            pass
    finally:
        tv.listar_videos_paginado = orig_listar
        vv_mod.VisorVideos.iniciar_escaneo = orig_iniciar
        _limpiar()

def main():
    print("=== Regresión B7.7 post-rename selección por video_id (GestorTareas real) ===")
    src = open("renombrar_masivo.py", encoding="utf-8").read()
    verifica("TareaEscaneo" not in src, "renombrar_masivo.py cero TareaEscaneo")
    src_v = inspect.getsource(vv_mod.VisorVideos._al_resultado_renombrar_masivo)
    verifica("iniciar_escaneo" not in src_v and "TareaEscaneo" not in src_v, "UI handler cero Escanear carpeta")
    for kw in ["ffmpeg","ffprobe","subprocess"]:
        verifica(kw.lower() not in src.lower() or "import subprocess" not in src.lower(), f"renombrar_masivo cero {kw}")
    # AST check: el fix no introduce fallback silencioso ni ExceptHandler solo-Pass en zona nueva
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    # 1) fallback genérico antiguo ya eliminado: debe contener diagnostico_ids y no el patrón try genérico
    verifica("diagnostico_ids" in src_visor, "fix contiene diagnostico_ids explícito")
    verifica("self._renombrar_masivo_ids_origen = {int(v[\"video_id\"])" not in src_visor, "fallback genérico antiguo eliminado")
    # 2) el bloque _reemplazar_tarjetas no debe tener 'except Exception: pass' alrededor de _actualizar_resumen
    verifica("try:\n                self._actualizar_resumen_seleccion()\n            except Exception:\n                pass" not in src_visor, "sin ExceptHandler solo-Pass en _reemplazar_tarjetas")
    try:
        test_seleccion_preservada_exitoso()
    except Exception as e:
        import traceback
        falla("test_seleccion_preservada_exitoso excepción", str(e))
        traceback.print_exc()
    try:
        test_parcial()
    except Exception as e:
        import traceback
        falla("test_parcial excepción", str(e))
        traceback.print_exc()
    total = _CONT
    fallos = _FALLOS
    print(f"TOTAL={total - fallos}/{total}")
    if fallos == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
