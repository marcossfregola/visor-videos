"""Prueba B7.4 fix-027 — copia conserva primera miniatura tras reinicio sin escaneo.

Demuestra fallo bloqueante original: copiar A->B perdía miniatura tras cerrar/reabrir
porque copiar_video no replicaba cache derivada (miniatura/previews) al nuevo nombre.
Fija manteniendo identidad nueva y copiando deriva sin regeneración FFmpeg.

Cubre:
A) copiar A->B;
B) nuevo video_id distinto;
C) primera miniatura disponible para copia;
D) cerrar/recrear contexto (nueva lectura desde persistencia equivalente al arranque);
E) copia sigue resolviendo su primera miniatura sin escaneo;
F) original conserva la suya;
G) no se regenera innecesariamente mediante FFmpeg.

Falla con estado defectuoso (antes de fix): copia queda sin miniatura tras reinicio.
Pasa con fix: copia replica cache y persiste.

B8.3A — cache canónica por video_id: v<id>_01.jpg y v<id>_preview_<NN>.jpg
"""
import os
import shutil
import sqlite3
import tempfile
import datetime

import escanear_videos
import visor_videos
import copiar_video as svc
import rutas as rutas_mod
from escanear_videos import conectar_bd, listar_videos_paginado, ruta_miniatura_id, ruta_preview_id, previews_existentes_por_id
from rutas import normalizar_ruta_clave


def _crear_db(tmpdir):
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return ruta_db


def test_copia_preserva_miniatura_tras_reinicio_sin_escaneo():
    tmp = tempfile.mkdtemp()
    # aislar miniaturas via monkeypatch rutas
    mini_real = rutas_mod.ruta_carpeta_miniaturas
    mini_escan_real = escanear_videos.ruta_carpeta_miniaturas
    mini_visor_real = visor_videos.ruta_carpeta_miniaturas
    mini = os.path.join(tmp, "miniaturas")
    os.makedirs(mini, exist_ok=True)
    def fake_mini():
        return mini
    rutas_mod.ruta_carpeta_miniaturas = fake_mini
    escanear_videos.ruta_carpeta_miniaturas = fake_mini
    visor_videos.ruta_carpeta_miniaturas = fake_mini

    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A); os.makedirs(B)

    ruta_db = _crear_db(tmp)

    # instrumentar FFmpeg: no debe llamarse para replicar miniatura
    ffmpeg_calls = []
    orig_gen_mini = escanear_videos.generar_miniatura
    orig_gen_preview = escanear_videos.generar_preview
    orig_asegurar = escanear_videos.asegurar_miniatura
    orig_asegurar_miniaturas = escanear_videos.asegurar_miniaturas
    def spy_gen_mini(*a, **k):
        ffmpeg_calls.append("generar_miniatura")
        return orig_gen_mini(*a, **k)
    def spy_gen_preview(*a, **k):
        ffmpeg_calls.append("generar_preview")
        return orig_gen_preview(*a, **k)
    def spy_asegurar(*a, **k):
        ffmpeg_calls.append("asegurar_miniatura")
        return orig_asegurar(*a, **k)
    def spy_asegurar_miniaturas(*a, **k):
        ffmpeg_calls.append("asegurar_miniaturas")
        return orig_asegurar_miniaturas(*a, **k)
    escanear_videos.generar_miniatura = spy_gen_mini
    escanear_videos.generar_preview = spy_gen_preview
    escanear_videos.asegurar_miniatura = spy_asegurar
    escanear_videos.asegurar_miniaturas = spy_asegurar_miniaturas

    # espiar escaneo: no debe requerirse
    escaneo_calls = []
    orig_iniciar_escaneo = visor_videos.VisorVideos.iniciar_escaneo
    def fake_escaneo(self, *a, **k):
        escaneo_calls.append("iniciar_escaneo")
        return None
    visor_videos.VisorVideos.iniciar_escaneo = fake_escaneo

    try:
        # A) crear original en A con miniatura existente
        nombre_orig = "videoX.mp4"
        ruta_orig = os.path.join(A, nombre_orig)
        with open(ruta_orig, "wb") as f:
            f.write(b"fakevideo" * 800)
        st = os.stat(ruta_orig)
        conn = conectar_bd(ruta_db)
        ruta_abs = os.path.abspath(ruta_orig)
        ruta_norm = normalizar_ruta_clave(ruta_abs)
        conn.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns,cantidad_miniaturas) VALUES (?,?,?,?,?,?,?,?)",
                     (nombre_orig, ruta_abs, ruta_norm, ".mp4", datetime.datetime.now().isoformat(), st.st_size, st.st_mtime_ns, 1))
        vid_orig = conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?", (ruta_norm,)).fetchone()[0]
        conn.commit(); conn.close()

        # simular miniatura y previews canónicas por ID para original (como si pipeline B8.2 ya generó)
        mini_orig = ruta_miniatura_id(vid_orig, 1)
        with open(mini_orig, "wb") as f:
            f.write(b"fakejpg")
        # asegurar mtime mini >= video para vigencia
        import time
        time.sleep(0.01)
        # previews canónicos por ID
        for i in range(1, 4):
            p = ruta_preview_id(vid_orig, i)
            with open(p, "wb") as f:
                f.write(b"preview")

        # verificar F) original conserva miniatura canónica antes de copia
        assert os.path.isfile(ruta_miniatura_id(vid_orig, 1)), "original debe tener miniatura canónica por ID antes"
        assert len(previews_existentes_por_id(vid_orig)) >= 1

        # A) copiar A->B via servicio (fuera UI) — homónimo conserva mismo nombre visible
        ffmpeg_calls.clear()
        res = svc.copiar_video(vid_orig, B, ruta_db)
        assert res.get("ok"), f"copia debe ok: {res}"
        vid_copy = res["video_id"]
        nombre_copy = res["nombre"]
        ruta_copy = res["ruta"]

        # B) nuevo video_id distinto aunque mismo nombre homónimo
        assert vid_copy != vid_orig, "nuevo video_id distinto del original"
        assert res["video_id_original"] == vid_orig
        assert nombre_copy == nombre_orig, "homónimo conserva mismo nombre visible"

        # C) primera miniatura disponible para la copia inmediatamente (sin escaneo, sin regeneración) — ruta canónica por ID distinta
        mini_copy_path = ruta_miniatura_id(vid_copy, 1)
        mini_orig_path = ruta_miniatura_id(vid_orig, 1)
        assert mini_copy_path != mini_orig_path, f"rutas canónicas deben diferir por ID: {mini_copy_path} vs {mini_orig_path}"
        assert mini_copy_path.endswith(f"v{vid_copy}_01.jpg") and mini_orig_path.endswith(f"v{vid_orig}_01.jpg"), f"esquema canónico v<id>_01.jpg esperado {mini_copy_path} {mini_orig_path}"
        assert os.path.isfile(mini_copy_path), f"archivo miniatura copia debe existir: {mini_copy_path}, lista {os.listdir(mini)}"
        assert os.path.isfile(mini_orig_path), f"origen conserva miniatura: {mini_orig_path}"
        # previews también replicados por ID con rutas distintas
        previews_copy = previews_existentes_por_id(vid_copy)
        previews_orig = previews_existentes_por_id(vid_orig)
        assert len(previews_copy) >= 1, f"copia debe tener previews replicados por ID, got {previews_copy}"
        assert len(previews_orig) >= 1
        for idx in range(1, 4):
            pc = ruta_preview_id(vid_copy, idx)
            po = ruta_preview_id(vid_orig, idx)
            assert pc != po, f"previews canónicas deben diferir por ID idx {idx}: {pc} vs {po}"
            assert pc.endswith(f"v{vid_copy}_preview_{idx:02d}.jpg")
        # contenido idéntico inicial (copia bit-identical)
        with open(mini_orig_path, "rb") as f: data_orig_init = f.read()
        with open(mini_copy_path, "rb") as f: data_copy_init = f.read()
        assert data_orig_init == data_copy_init, "miniatura copia debe ser copia idéntica del original, no regenerada"

        # G) no se regenera innecesariamente mediante FFmpeg
        assert not any(c in ("generar_miniatura", "generar_preview", "asegurar_miniatura", "asegurar_miniaturas") for c in ffmpeg_calls), f"no debe regenerar FFmpeg, calls={ffmpeg_calls}"
        assert not escaneo_calls, f"no debe escaneo, calls={escaneo_calls}"

        # D) cerrar/recrear contexto: simular reinicio con nueva lectura desde persistencia
        pagA = listar_videos_paginado(100, 0, None, ruta_db, carpeta=A, incluir_subcarpetas=False)
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        idsA = [r[8] for r in pagA["videos"]]
        idsB = [r[8] for r in pagB["videos"]]
        assert vid_orig in idsA and vid_copy not in idsA, f"A debe contener solo original: {idsA}"
        assert vid_copy in idsB and vid_orig not in idsB, f"B debe contener copia: {idsB}"

        # E) copia sigue resolviendo su primera miniatura sin escaneo tras reinicio — rutas por ID distintas
        ffmpeg_calls.clear(); escaneo_calls.clear()
        mini_orig_reload = ruta_miniatura_id(vid_orig, 1)
        mini_copy_reload = ruta_miniatura_id(vid_copy, 1)
        assert mini_orig_reload is not None and os.path.isfile(mini_orig_reload), "original conserva miniatura tras reinicio"
        assert mini_copy_reload is not None and os.path.isfile(mini_copy_reload), f"copia debe conservar miniatura tras reinicio, got {mini_copy_reload}, mini dir {os.listdir(mini)}"
        assert mini_orig_reload != mini_copy_reload, "rutas de miniatura deben ser distintas SIEMPRE para IDs distintos (B8.3A estricto, homónimo no comparte archivo)"
        assert mini_orig_reload.endswith(f"v{vid_orig}_01.jpg") and mini_copy_reload.endswith(f"v{vid_copy}_01.jpg")
        with open(mini_orig_reload, "rb") as f: data_orig = f.read()
        with open(mini_copy_reload, "rb") as f: data_copy = f.read()
        assert data_orig == data_copy, "miniatura copia debe ser copia idéntica del original, no regenerada"
        # previews reload también distintas
        assert ruta_preview_id(vid_orig, 1) != ruta_preview_id(vid_copy, 1)
        assert os.path.isfile(ruta_preview_id(vid_orig, 1)) and os.path.isfile(ruta_preview_id(vid_copy, 1))

        # F) original conserva la suya y no se comparte estado mutable — modificar/eliminar copia no altera origen
        # modificar copia
        with open(mini_copy_reload, "wb") as f:
            f.write(b"modificado_copy_distinto")
        with open(mini_orig_reload, "rb") as f: data_orig_after = f.read()
        with open(mini_copy_reload, "rb") as f: data_copy_after = f.read()
        assert data_orig_after == data_orig, "modificar cache copia NO debe alterar origen"
        assert data_copy_after != data_orig_after, "copia modificada debe diferir de origen"
        # restaurar copia para siguiente check y probar eliminación no afecta origen
        with open(mini_copy_reload, "wb") as f:
            f.write(data_orig)
        # eliminar copia temporalmente
        os.remove(mini_copy_reload)
        assert not os.path.isfile(mini_copy_reload), "copia eliminada"
        assert os.path.isfile(mini_orig_reload), "origen intacto tras eliminar cache copia"
        # restaurar
        with open(mini_copy_reload, "wb") as f:
            f.write(data_orig)
        assert os.path.isfile(mini_copy_reload) and os.path.isfile(mini_orig_reload)
        assert open(mini_orig_reload,"rb").read() == open(mini_copy_reload,"rb").read()

        # verificar copia no heredó marcadores/segmentos
        conn2 = sqlite3.connect(ruta_db)
        c_orig = conn2.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=?", (vid_orig,)).fetchone()[0]
        c_copy = conn2.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=?", (vid_copy,)).fetchone()[0]
        conn2.close()
        assert c_copy == 0, "copia no debe heredar marcadores"

        # Recreación real de VisorVideos (cierre/recreación)
        import sys
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmp, "config_test.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        for _ in range(100):
            QApplication.processEvents()
            time.sleep(0.02)
            if getattr(ventana, "_carga_completada", False) and not ventana.gestor.activo:
                break
        # verificar que tras recreación, copia y original siguen con miniatura por ID
        assert os.path.isfile(ruta_miniatura_id(vid_copy, 1))
        assert os.path.isfile(ruta_miniatura_id(vid_orig, 1))
        assert not escaneo_calls, f"recreación Visor no debe escaneo para miniatura, got {escaneo_calls}"
        ventana.close()
        try: ventana.gestor.cerrar()
        except: pass
        try: ventana.gestor_copiar.cerrar()
        except: pass

        print("test_copia_preserva_miniatura_tras_reinicio_sin_escaneo OK")
    finally:
        visor_videos.VisorVideos.iniciar_escaneo = orig_iniciar_escaneo
        escanear_videos.generar_miniatura = orig_gen_mini
        escanear_videos.generar_preview = orig_gen_preview
        escanear_videos.asegurar_miniatura = orig_asegurar
        escanear_videos.asegurar_miniaturas = orig_asegurar_miniaturas
        rutas_mod.ruta_carpeta_miniaturas = mini_real
        escanear_videos.ruta_carpeta_miniaturas = mini_escan_real
        visor_videos.ruta_carpeta_miniaturas = mini_visor_real
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_copia_preserva_miniatura_tras_reinicio_sin_escaneo()
    print("TOTAL=1/1 RESULTADO_FINAL=PASS")
