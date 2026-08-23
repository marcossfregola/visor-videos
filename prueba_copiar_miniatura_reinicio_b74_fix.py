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
from escanear_videos import conectar_bd, listar_videos_paginado


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
        conn.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns,cantidad_miniaturas) VALUES (?,?,?,?,?,?,?)",
                     (nombre_orig, os.path.abspath(ruta_orig), ".mp4", datetime.datetime.now().isoformat(), st.st_size, st.st_mtime_ns, 1))
        vid_orig = conn.execute("SELECT id FROM videos WHERE nombre=?", (nombre_orig,)).fetchone()[0]
        conn.commit(); conn.close()

        # simular miniatura y previews existentes para original (como si pipeline ya generó)
        mini_orig = os.path.join(mini, "videoX_01.jpg")
        with open(mini_orig, "wb") as f:
            f.write(b"fakejpg")
        # asegurar mtime mini >= video para vigencia
        import time
        time.sleep(0.01)
        # previews
        for i in range(1, 4):
            p = os.path.join(mini, f"videoX_preview_{i:02d}.jpg")
            with open(p, "wb") as f:
                f.write(b"preview")

        # verificar F) original conserva miniatura antes de copia
        assert visor_videos.miniatura_principal(nombre_orig) is not None, "original debe tener miniatura antes"
        assert os.path.isfile(visor_videos.miniatura_principal(nombre_orig))

        # A) copiar A->B via servicio (fuera UI)
        ffmpeg_calls.clear()
        res = svc.copiar_video(vid_orig, B, ruta_db)
        assert res.get("ok"), f"copia debe ok: {res}"
        vid_copy = res["video_id"]
        nombre_copy = res["nombre"]
        ruta_copy = res["ruta"]

        # B) nuevo video_id distinto
        assert vid_copy != vid_orig, "nuevo video_id distinto del original"
        assert res["video_id_original"] == vid_orig

        # C) primera miniatura disponible para la copia inmediatamente (sin escaneo, sin regeneración)
        mini_copy_path = visor_videos.miniatura_principal(nombre_copy)
        assert mini_copy_path is not None, f"copia debe tener miniatura inmediata, got {mini_copy_path}, lista {os.listdir(mini)}"
        assert os.path.isfile(mini_copy_path), f"archivo miniatura copia debe existir: {mini_copy_path}"
        # previews también replicados
        previews_copy = visor_videos.previews_de(nombre_copy)
        assert len(previews_copy) >= 1, f"copia debe tener previews replicados, got {previews_copy}"

        # G) no se regenera innecesariamente mediante FFmpeg
        assert not any(c in ("generar_miniatura", "generar_preview", "asegurar_miniatura", "asegurar_miniaturas") for c in ffmpeg_calls), f"no debe regenerar FFmpeg, calls={ffmpeg_calls}"
        assert not escaneo_calls, f"no debe escaneo, calls={escaneo_calls}"

        # D) cerrar/recrear contexto: simular reinicio con nueva lectura desde persistencia
        # cerrar conexiones y reabrir via paginado + miniatura lookup (equivalente arranque)
        # también recrear VisorVideos con mismo ruta_db / ruta_config temporal

        # nueva lectura paginada sin escaneo para ambas carpetas
        pagA = listar_videos_paginado(100, 0, None, ruta_db, carpeta=A, incluir_subcarpetas=False)
        pagB = listar_videos_paginado(100, 0, None, ruta_db, carpeta=B, incluir_subcarpetas=False)
        idsA = [r[8] for r in pagA["videos"]]
        idsB = [r[8] for r in pagB["videos"]]
        assert vid_orig in idsA and vid_copy not in idsA, f"A debe contener solo original: {idsA}"
        assert vid_copy in idsB and vid_orig not in idsB, f"B debe contener copia: {idsB}"

        # E) copia sigue resolviendo su primera miniatura sin escaneo tras reinicio
        ffmpeg_calls.clear(); escaneo_calls.clear()
        # re-evaluar miniatura tras 'reinicio' (nueva resolución FS)
        mini_orig_reload = visor_videos.miniatura_principal(nombre_orig)
        mini_copy_reload = visor_videos.miniatura_principal(nombre_copy)
        assert mini_orig_reload is not None and os.path.isfile(mini_orig_reload), "original conserva miniatura tras reinicio"
        assert mini_copy_reload is not None and os.path.isfile(mini_copy_reload), f"copia debe conservar miniatura tras reinicio, got {mini_copy_reload}, mini dir {os.listdir(mini)}"
        # contenido idéntico al original (copia bit-identical de cache)
        with open(mini_orig_reload, "rb") as f: data_orig = f.read()
        with open(mini_copy_reload, "rb") as f: data_copy = f.read()
        assert data_orig == data_copy, "miniatura copia debe ser copia idéntica del original, no regenerada"

        # F) original conserva la suya (ya verificado) y no se comparte estado mutable
        assert mini_orig_reload != mini_copy_reload, "rutas de miniatura deben ser distintas (identidad nueva, no compartir archivo)"
        # verificar copia no heredó marcadores/segmentos sería por svc, pero aquí no creamos, al menos verificar DB
        conn2 = sqlite3.connect(ruta_db)
        c_orig = conn2.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=?", (vid_orig,)).fetchone()[0]
        c_copy = conn2.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=?", (vid_copy,)).fetchone()[0]
        conn2.close()
        # ambos 0 en este test, pero copy no debe compartir si hubiera
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
        # esperar carga inicial sin escaneo
        for _ in range(100):
            QApplication.processEvents()
            time.sleep(0.02)
            if getattr(ventana, "_carga_completada", False) and not ventana.gestor.activo:
                break
        # verificar que tras recreación, copia y original siguen con miniatura (via helper)
        assert visor_videos.miniatura_principal(nombre_copy) is not None
        assert visor_videos.miniatura_principal(nombre_orig) is not None
        # no se debe haber disparado escaneo durante recreación para resolver miniatura
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
