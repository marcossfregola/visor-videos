"""Suite B7.8 — optimización segura de consistencia post-operaciones.

Verifica política mínima: decisión explícita 'recarga necesaria' vs 'actualización local suficiente',
sin perseguir cero lecturas SQLite, preservando veracidad del catálogo.

Instrumenta _programar_recarga_por_carpeta para demostrar recargas necesarias exactas y no duplicadas.
"""

import os
import sys
import tempfile
import shutil
import inspect

from escanear_videos import conectar_bd
import visor_videos
from rutas import carpetas_iguales

_CONT = 0
_FAIL = 0

def ok(m):
    global _CONT
    _CONT += 1
    print(f"T{_CONT:02d} OK - {m}")

def falla(m, e=None):
    global _CONT, _FAIL
    _CONT += 1
    _FAIL += 1
    print(f"T{_CONT:02d} FAIL - {m} {e or ''}")

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)

def _db():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    conn = conectar_bd(db)
    conn.commit()
    conn.close()
    return tmp, db

def _ins(db, carpeta, nombre, contenido=b"x" * 1024):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    st = os.stat(ruta)
    conn = conectar_bd(db)
    conn.execute(
        "INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
        (nombre, os.path.abspath(ruta), os.path.splitext(nombre)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns),
    )
    vid = conn.execute("SELECT id FROM videos WHERE nombre=?", (nombre,)).fetchone()[0]
    conn.commit()
    conn.close()
    return vid, os.path.abspath(ruta)

def _crear_visor(tmp, db):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    ruta_config = os.path.join(tmp, "cfg_b78.json")
    ventana = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
    ventana.resize(720, 540)
    ventana.show()
    # esperar carga mínima
    import time
    for _ in range(60):
        QApplication.processEvents()
        time.sleep(0.02)
        if getattr(ventana, "_carga_completada", False) and not getattr(ventana.gestor, "activo", False):
            break
    return ventana, app

def test_01_copia_individual_destino_distinto_0_recargas():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        vid, _ = _ins(db, A, "vid01.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        # resultado copia a B estando en A
        res = {"ok": True, "nombre": "vid01_001.mp4", "ruta": os.path.join(B, "vid01_001.mp4"), "carpeta_destino": os.path.abspath(B), "video_id": 999}
        # asegurar que helper dice no recargar
        verifica(not ventana._b78_copia_debe_recargar(os.path.abspath(B)), "helper copia distinta no recarga")
        ventana._al_resultado_copiar(res)
        app.processEvents()
        verifica(len(recargas) == 0, f"copia destino distinto => 0 recargas (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_02_copia_individual_destino_visible_1_recarga_no_duplicada():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        vid, _ = _ins(db, A, "vid02.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"ok": True, "nombre": "vid02_001.mp4", "ruta": os.path.join(A, "vid02_001.mp4"), "carpeta_destino": os.path.abspath(A), "video_id": 999}
        verifica(ventana._b78_copia_debe_recargar(os.path.abspath(A)), "helper copia misma carpeta recarga")
        ventana._al_resultado_copiar(res)
        app.processEvents()
        # puede haber sido diferida via gestor activo -> en ese caso _reordenamiento_pendiente True cuenta como programada
        # pero spy debe haber sido llamado exactamente 1 vez
        verifica(len(recargas) == 1, f"copia destino visible => exactamente 1 recarga (got {len(recargas)})")
        # segunda llamada inmediata no debe duplicar si ya hay pendiente (gestor.activo dedup interno, pero spy contaría 2 si bug)
        # verificamos que no haya segunda recarga por filtrar u otro path
        # ya verificamos 1, si hubiera duplicado por fallback filtrar fallido sería 2
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_03_lote_mover_con_exitos_recarga_segura():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "m1.mp4")
        v2, _ = _ins(db, A, "m2.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "mover"
        ventana._lote_carpeta_destino = os.path.abspath(B)
        # helper
        verifica(ventana._b78_lote_debe_recargar("mover", [{"video_id": v1}], B), "helper mover con exitos recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "mover", "exitosos": [{"video_id": v1}, {"video_id": v2}], "fallidos": [], "cancelados": [], "total": 2}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) >= 1, f"lote mover con exitos => recarga segura (got {len(recargas)})")
        verifica(len(recargas) == 1, f"lote mover recarga exactamente 1 no duplicada (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_04_lote_eliminar_con_exitos_recarga_segura():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "e1.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "eliminar"
        ventana._lote_carpeta_destino = None
        verifica(ventana._b78_lote_debe_recargar("eliminar", [{"video_id": v1}]), "helper eliminar recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "eliminar", "exitosos": [{"video_id": v1}], "fallidos": [], "cancelados": [], "total": 1}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) == 1, f"lote eliminar con exitos => 1 recarga (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_05_lote_copiar_a_otra_carpeta_0_recargas():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "c1.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "copiar"
        ventana._lote_carpeta_destino = os.path.abspath(B)
        verifica(not ventana._b78_lote_debe_recargar("copiar", [{"video_id": v1}], os.path.abspath(B)), "helper copiar a otra carpeta no recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "copiar", "exitosos": [{"video_id": v1}], "fallidos": [], "cancelados": [], "total": 1}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) == 0, f"lote copiar a otra carpeta => 0 recargas vista actual (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_06_lote_copiar_a_vista_1_recarga():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "c2.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "copiar"
        ventana._lote_carpeta_destino = os.path.abspath(A)
        verifica(ventana._b78_lote_debe_recargar("copiar", [{"video_id": v1}], os.path.abspath(A)), "helper copiar a vista recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "copiar", "exitosos": [{"video_id": v1}], "fallidos": [], "cancelados": [], "total": 1}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) == 1, f"lote copiar a vista => 1 recarga (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_07_lote_sin_exitos_0_recargas():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "s1.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "mover"
        ventana._lote_carpeta_destino = os.path.abspath(B)
        verifica(not ventana._b78_lote_debe_recargar("mover", []), "helper lote sin exitos no recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "mover", "exitosos": [], "fallidos": [{"video_id": v1, "error": "colision"}], "cancelados": [], "total": 1}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) == 0, f"lote sin exitos => 0 recargas normal (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_08_renombrado_masivo_con_exitos_recarga_conservadora():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "r1.mp4")
        v2, _ = _ins(db, A, "r2.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._renombrar_masivo_ids_origen = {v1, v2}
        # política conservadora: con exitos siempre recarga, sin distinguir orden/filtro
        verifica(ventana._b78_renombrado_masivo_debe_recargar([{"video_id": v1}]), "helper renombrado con exitos recarga")
        verifica(not ventana._b78_renombrado_masivo_debe_recargar([]), "helper renombrado sin exitos no recarga")
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"exitosos": [{"video_id": v1, "resultado": {"nombre": "r1_x.mp4"}}], "fallidos": [], "cancelados": [], "total": 1}
        ventana._al_resultado_renombrar_masivo(res)
        app.processEvents()
        verifica(len(recargas) == 1, f"renombrado masivo con exitos => recarga conservadora 1 (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_09_renombrado_masivo_sin_exitos_0_recargas():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "r9.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._renombrar_masivo_ids_origen = {v1}
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"exitosos": [], "fallidos": [{"video_id": v1, "error": "colision"}], "cancelados": [], "total": 1}
        ventana._al_resultado_renombrar_masivo(res)
        app.processEvents()
        verifica(len(recargas) == 0, f"renombrado masivo sin exitos => 0 recargas (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_10_inconsistencia_lote_recarga_fallback():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        # resultado inválido no dict
        ventana._al_resultado_lote(None)
        app.processEvents()
        verifica(len(recargas) >= 1, f"inconsistencia lote dict inválido => fallback recarga (got {len(recargas)})")
        recargas.clear()
        # exitosos no lista
        ventana._al_resultado_lote({"operacion": "mover", "exitosos": "no lista", "fallidos": [], "cancelados": [], "total": 1})
        app.processEvents()
        verifica(len(recargas) >= 1, f"inconsistencia exitosos no lista => fallback recarga (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_11_inconsistencia_renombrado_recarga_fallback():
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        ventana._al_resultado_renombrar_masivo(None)
        app.processEvents()
        verifica(len(recargas) >= 1, f"renombrado inconsistencia None => fallback recarga (got {len(recargas)})")
        recargas.clear()
        ventana._al_resultado_renombrar_masivo({"exitosos": "no lista", "fallidos": []})
        app.processEvents()
        verifica(len(recargas) >= 1, f"renombrado exitosos no lista => fallback recarga (got {len(recargas)})")
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_12_no_duplicada_filtrar_fallo():
    """Lote mover con exitos + filtrar que falla debe seguir exactamente 1 recarga (no duplicada)."""
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        v1, _ = _ins(db, A, "dup12.mp4")
        ventana, app = _crear_visor(tmp, db)
        from PySide6.QtWidgets import QApplication
        ventana.carpeta_seleccionada = os.path.abspath(A)
        ventana._lote_operacion = "mover"
        ventana._lote_carpeta_destino = os.path.abspath(B)
        # hacer filtrar que falle
        orig_filtrar = ventana.filtrar
        def failing_filtrar(*a, **k):
            raise RuntimeError("falla filtrar simulada")
        ventana.filtrar = failing_filtrar
        recargas = []
        orig = ventana._programar_recarga_por_carpeta
        def spy(*a, **k):
            recargas.append(1)
            return orig(*a, **k)
        ventana._programar_recarga_por_carpeta = spy
        res = {"operacion": "mover", "exitosos": [{"video_id": v1}], "fallidos": [], "cancelados": [], "total": 1}
        ventana._al_resultado_lote(res)
        app.processEvents()
        verifica(len(recargas) == 1, f"lote mover con filtrar fallido => 1 recarga no duplicada (got {len(recargas)})")
        ventana.filtrar = orig_filtrar
        ventana._programar_recarga_por_carpeta = orig
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_13_helpers_politica_expuestos():
    # verificar helpers existen y son testeables
    tmp, db = _db()
    try:
        ventana, app = _crear_visor(tmp, db)
        verifica(hasattr(ventana, "_b78_copia_debe_recargar"), "helper _b78_copia_debe_recargar expuesto")
        verifica(hasattr(ventana, "_b78_lote_debe_recargar"), "helper _b78_lote_debe_recargar expuesto")
        verifica(hasattr(ventana, "_b78_renombrado_masivo_debe_recargar"), "helper _b78_renombrado_masivo_debe_recargar expuesto")
        # verificar que no usan FS/re-scan: inspeccionar fuente no toca os.* ni TareaEscaneo
        for name in ["_b78_copia_debe_recargar", "_b78_lote_debe_recargar", "_b78_renombrado_masivo_debe_recargar", "_al_resultado_copiar", "_al_resultado_lote", "_al_resultado_renombrar_masivo"]:
            src = inspect.getsource(getattr(ventana, name))
            # B7.8 no debe introducir reescaneo, ffprobe, ffmpeg, nueva consulta sqlite directa
            verifica("TareaEscaneo" not in src, f"{name} sin TareaEscaneo")
            # ffprobe/ffmpeg en comentario 'no disparar' es inocuo; filtrar comentarios
            code_lines = [l for l in src.splitlines() if not l.strip().startswith("#")]
            code_txt = "\n".join(code_lines).lower()
            # permitir mención en comentario de fijación B7.7 que dice 'no disparar ffprobe', no es código
            has_ff = ("ffprobe" in code_txt and "no disparar" not in code_txt) or ("ffmpeg" in code_txt and "no disparar" not in code_txt)
            # simplificado: si contiene ffprobe fuera de comentario 'no disparar', fallar
            if "ffprobe" in code_txt or "ffmpeg" in code_txt:
                # si la única aparición es en línea con 'no disparar', ignorar
                ff_lines = [l for l in code_lines if "ffprobe" in l.lower() or "ffmpeg" in l.lower()]
                ff_lines_significativas = [l for l in ff_lines if "no disparar" not in l.lower()]
                verifica(not ff_lines_significativas, f"{name} sin ffprobe/ffmpeg (significativo)")
            else:
                verifica(True, f"{name} sin ffprobe/ffmpeg")
        # verificar que copia usa helper centralizado
        src_copiar = inspect.getsource(ventana._al_resultado_copiar)
        verifica("_b78_copia_debe_recargar" in src_copiar, "_al_resultado_copiar usa policy B7.8")
        src_lote = inspect.getsource(ventana._al_resultado_lote)
        verifica("_b78_lote_debe_recargar" in src_lote, "_al_resultado_lote usa policy B7.8")
        src_ren = inspect.getsource(ventana._al_resultado_renombrar_masivo)
        verifica("_b78_renombrado_masivo_debe_recargar" in src_ren, "_al_resultado_renombrar_masivo usa policy B7.8")
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_lote.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass
        try: ventana.gestor_renombrar_masivo.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    print("=== B7.8 prueba_consistencia_postoperaciones_b78 ===")
    for fn in [
        test_01_copia_individual_destino_distinto_0_recargas,
        test_02_copia_individual_destino_visible_1_recarga_no_duplicada,
        test_03_lote_mover_con_exitos_recarga_segura,
        test_04_lote_eliminar_con_exitos_recarga_segura,
        test_05_lote_copiar_a_otra_carpeta_0_recargas,
        test_06_lote_copiar_a_vista_1_recarga,
        test_07_lote_sin_exitos_0_recargas,
        test_08_renombrado_masivo_con_exitos_recarga_conservadora,
        test_09_renombrado_masivo_sin_exitos_0_recargas,
        test_10_inconsistencia_lote_recarga_fallback,
        test_11_inconsistencia_renombrado_recarga_fallback,
        test_12_no_duplicada_filtrar_fallo,
        test_13_helpers_politica_expuestos,
    ]:
        try:
            fn()
        except Exception as e:
            import traceback
            falla(fn.__name__, str(e))
            traceback.print_exc()
    total = _CONT
    fallos = _FAIL
    print(f"TOTAL={total - fallos}/{total}")
    if fallos == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
