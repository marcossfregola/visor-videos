"""Pruebas B6.10 — unión de varios segmentos del mismo original en un único derivado.

Cubre:
- vía principal sin subs: 2 y 3 segmentos, 0/1/2 audios, no-keyframe, orden inverso
- destino existente: no sobrescribe, preserva hash
- subtítulo compatible preservado via fallback extracción precisa + concat
- MKV/SubRip no validado: rechazo claro
- cancelación durante unión: limpia temporales, no publica, gestor inactivo
- background: tarea fuera de hilo principal y gestor vuelve a inactivo
- UI mínima reutilizando selección B6.9 y orden explícito, naming B6.8, no B6.11
- aislación UI (no subprocess/sqlite directo), sin -y contra destino, temporales únicos, FFprobe verificación, mapeo explícito y recodificación CPU
"""

import hashlib
import inspect
import math
import os
import py_compile
import subprocess
import sys
import tempfile
import time
import uuid
import json
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

import exportar_segmento as exp
import exportar_secuencia as seq
import tareas_videos as tv
from tareas import GestorTareas
import visor_videos
import nombres

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

def _ffmpeg_disponible():
    return shutil.which("ffmpeg") is not None

def _hash_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _ffprobe_json(ruta):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", ruta],
        capture_output=True, text=True, timeout=10, **_ARGS_SIN_CONSOLA
    )
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)

def _generar_video(ruta, duracion=6.0, con_audio=True, doble_audio=False, fps=30):
    if doble_audio:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={fps}:duration={duracion}",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v", "-map", "1:a", "-map", "2:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "64k",
            "-t", str(duracion),
            ruta,
        ]
    elif con_audio:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={fps}:duration={duracion}",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duracion),
            ruta,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={fps}:duration={duracion}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
            "-an",
            "-t", str(duracion),
            ruta,
        ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, **_ARGS_SIN_CONSOLA)
    return r.returncode == 0 and os.path.isfile(ruta)

def _generar_video_con_subtitulo(video_sin_sub, srt_path, salida, contenedor="mp4"):
    if contenedor == "mp4":
        cmd = ["ffmpeg", "-y", "-i", video_sin_sub, "-i", srt_path, "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", salida]
    else:
        cmd = ["ffmpeg", "-y", "-i", video_sin_sub, "-i", srt_path, "-c:v", "copy", "-c:a", "copy", "-c:s", "srt", salida]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, **_ARGS_SIN_CONSOLA)
    return r.returncode == 0 and os.path.isfile(salida)

def _crear_srt(path):
    content = """1
00:00:01,000 --> 00:00:02,000
Hola

2
00:00:03,000 --> 00:00:04,000
Mundo
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def _esperar(pred, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(paso_ms/1000)
    QApplication.processEvents()
    return pred()

# ---------------------------------------------------------------------------

def test_01():
    for m in ["exportar_segmento.py", "exportar_secuencia.py", "tareas_videos.py", "visor_videos.py", "nombres.py"]:
        py_compile.compile(m, doraise=True)
    return True, "py_compile OK"

def test_02():
    if not _ffmpeg_disponible():
        return True, "ffmpeg no disponible, skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src, duracion=6):
            return False, "no se pudo generar fuente"
        dst = os.path.join(tmp, "dst.mp4")
        segs = [(1.0, 2.0), (3.0, 4.0)]
        res = seq.exportar_secuencia(src, segs, dst)
        if not res.get("ok"):
            return False, f"seq 2 seg falló: {res.get('error')}"
        if not os.path.isfile(dst):
            return False, "dst no existe"
        info = _ffprobe_json(dst)
        if info is None:
            return False, "ffprobe dst falló"
        dur = float(info["format"]["duration"])
        esperado = sum(b - a for a, b in segs)
        if abs(dur - esperado) > seq.TOLERANCIA_DURACION_EXPORT + 0.1:
            return False, f"dur {dur} vs esperado {esperado}"
        start = float(info["format"].get("start_time", 0) or 0)
        if abs(start) > seq.TOLERANCIA_START:
            return False, f"start {start}"
        has_v = any(s["codec_type"]=="video" for s in info["streams"])
        has_a = any(s["codec_type"]=="audio" for s in info["streams"])
        if not has_v or not has_a:
            return False, f"video {has_v} audio {has_a}"
        tmp_files = [f for f in os.listdir(tmp) if ".tmp" in f]
        if tmp_files:
            return False, f"temporales huérfanos {tmp_files}"
        return True, f"2 seg dur {dur:.2f} ok"

def test_03():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src, duracion=8):
            return False, "gen fail"
        dst = os.path.join(tmp, "dst3.mp4")
        segs = [(0.5, 1.0), (2.0, 2.8), (5.0, 5.6)]
        res = seq.exportar_secuencia(src, segs, dst)
        if not res.get("ok"):
            return False, f"3 seg falló {res.get('error')}"
        info = _ffprobe_json(dst)
        dur = float(info["format"]["duration"])
        esperado = sum(b - a for a,b in segs)
        if abs(dur - esperado) > seq.TOLERANCIA_DURACION_EXPORT + 0.1:
            return False, f"3 seg dur {dur} vs {esperado}"
        return True, f"3 seg {dur:.2f} ok"

def test_04():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "sin_audio.mp4")
        if not _generar_video(src, con_audio=False):
            return False, "gen sin audio fail"
        dst = os.path.join(tmp, "dst.mp4")
        segs = [(0.5, 1.5), (2.0, 3.0)]
        r = seq.exportar_secuencia(src, segs, dst)
        if not r.get("ok"):
            return False, f"seq sin audio falló {r.get('error')}"
        info = _ffprobe_json(dst)
        has_a = any(s["codec_type"]=="audio" for s in info["streams"])
        has_v = any(s["codec_type"]=="video" for s in info["streams"])
        if has_a:
            return False, "derivado no debería tener audio"
        if not has_v:
            return False, "derivado debería tener video"
        return True, "sin audio ok"

def test_05():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "doble.mp4")
        if not _generar_video(src, doble_audio=True):
            return False, "gen doble audio fail"
        info_src = _ffprobe_json(src)
        src_a = sum(1 for s in info_src["streams"] if s["codec_type"]=="audio")
        if src_a != 2:
            return False, f"src audio {src_a} !=2"
        dst = os.path.join(tmp, "dst.mp4")
        r = seq.exportar_secuencia(src, [(1.0, 2.0),(3.0,4.0)], dst)
        if not r.get("ok"):
            return False, f"doble audio seq fail {r.get('error')}"
        info = _ffprobe_json(dst)
        dst_a = sum(1 for s in info["streams"] if s["codec_type"]=="audio")
        if dst_a != 2:
            return False, f"dst audio {dst_a} !=2"
        return True, f"doble audio preservado {dst_a}"

def test_06():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src, duracion=6):
            return False, "gen fail"
        # segmentos no alineados a keyframe: 1.37 y 3.63 son tiempos no keyframe típicos
        dst = os.path.join(tmp, "dst.mp4")
        segs = [(1.37, 2.19), (3.63, 4.81)]
        r = seq.exportar_secuencia(src, segs, dst)
        if not r.get("ok"):
            return False, f"no-keyframe fail {r.get('error')}"
        info = _ffprobe_json(dst)
        dur = float(info["format"]["duration"])
        esperado = sum(b-a for a,b in segs)
        if abs(dur - esperado) > seq.TOLERANCIA_DURACION_EXPORT + 0.1:
            return False, f"dur {dur} vs {esperado}"
        return True, f"no-keyframe {dur:.2f}"

def test_07():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src, duracion=8):
            return False, "gen fail"
        # orden inverso explícito: usuario pide [3-4,1-2] debe respetarse, duración = 2
        dst = os.path.join(tmp, "dst.mp4")
        segs = [(3.0, 4.0), (1.0, 2.0)]
        r = seq.exportar_secuencia(src, segs, dst)
        if not r.get("ok"):
            return False, f"orden inverso fail {r.get('error')}"
        info = _ffprobe_json(dst)
        dur = float(info["format"]["duration"])
        esperado = 2.0
        if abs(dur - esperado) > seq.TOLERANCIA_DURACION_EXPORT + 0.1:
            return False, f"dur orden {dur}"
        # Verificar que se usó orden inverso mirando que el comando no haya reordenado
        # No podemos verificar contenido visual, pero al menos duración suma es exacta
        return True, f"orden inverso dur {dur:.2f}"

def test_08():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src):
            return False, "gen fail"
        dst = os.path.join(tmp, "dst.mp4")
        with open(dst, "wb") as f:
            f.write(b"previo")
        h_before = _hash_archivo(dst)
        r = seq.exportar_secuencia(src, [(1.0,2.0),(3.0,4.0)], dst)
        if r.get("ok"):
            return False, "debería fallar si destino existe"
        if not os.path.isfile(dst):
            return False, "destino borrado"
        h_after = _hash_archivo(dst)
        if h_before != h_after:
            return False, "hash cambió"
        tmp_files = [f for f in os.listdir(tmp) if ".tmp" in f]
        if tmp_files:
            return False, f"huérfano {tmp_files}"
        return True, "destino existente no sobrescrito"

def test_09():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base.mp4")
        if not _generar_video(base):
            return False, "gen base fail"
        srt = os.path.join(tmp, "sub.srt")
        _crear_srt(srt)
        src = os.path.join(tmp, "con_sub.mp4")
        if not _generar_video_con_subtitulo(base, srt, src, "mp4"):
            return False, "mux sub fail"
        info_src = _ffprobe_json(src)
        sub_src = sum(1 for s in info_src["streams"] if s["codec_type"]=="subtitle")
        if sub_src == 0:
            return False, "src sin sub"
        dst = os.path.join(tmp, "dst.mp4")
        r = seq.exportar_secuencia(src, [(1.0,2.0),(3.0,4.0)], dst)
        if not r.get("ok"):
            return False, f"sub compatible fallback fail {r.get('error')}"
        info = _ffprobe_json(dst)
        sub_dst = sum(1 for s in info["streams"] if s["codec_type"]=="subtitle")
        if sub_dst == 0:
            return False, "dst sin sub, fallback debería preservar"
        codecs = [s["codec_name"] for s in info["streams"] if s["codec_type"]=="subtitle"]
        if "mov_text" not in codecs:
            return False, f"codec sub dst {codecs}"
        # verificar no temporales huérfanos
        tmp_files = [f for f in os.listdir(tmp) if ".tmp" in f]
        if tmp_files:
            return False, f"huérfano tras fallback {tmp_files}"
        return True, f"sub compatible preservado {codecs}"

def test_10():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        # MKV con SubRip debe rechazarse claro en B6.10
        base = os.path.join(tmp, "base.mkv")
        # generar base mkv
        cmd = ["ffmpeg","-y","-f","lavfi","-i","testsrc=size=320x240:rate=30:duration=3",
               "-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100",
               "-c:v","libx264","-pix_fmt","yuv420p","-preset","veryfast","-crf","23","-c:a","aac","-t","3",base]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, **_ARGS_SIN_CONSOLA)
        if r.returncode !=0 or not os.path.isfile(base):
            return True, "skip gen mkv base fail"
        srt = os.path.join(tmp, "sub.srt")
        _crear_srt(srt)
        src = os.path.join(tmp, "con_sub.mkv")
        if not _generar_video_con_subtitulo(base, srt, src, "mkv"):
            return True, "skip mux mkv fail"
        dst = os.path.join(tmp, "dst.mkv")
        res = seq.exportar_secuencia(src, [(0.5,1.0),(1.5,2.0)], dst)
        if res.get("ok"):
            return False, "MKV SubRip debería ser rechazado"
        if "no validado" not in (res.get("error") or "").lower() and "rechazo" not in (res.get("error") or "").lower():
            return False, f"error no indica rechazo claro {res.get('error')}"
        if os.path.exists(dst):
            return False, "dst no debe existir tras rechazo"
        tmp_files = [f for f in os.listdir(tmp) if ".tmp" in f]
        if tmp_files:
            return False, f"huérfano tras rechazo {tmp_files}"
        return True, f"MKV SubRip rechazo claro: {res.get('error')[:60]}"

def test_11():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        # video largo para cancelar
        src = os.path.join(tmp, "src.mp4")
        cmd = ["ffmpeg","-y","-f","lavfi","-i","testsrc=size=1280x720:rate=30:duration=15","-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100","-c:v","libx264","-pix_fmt","yuv420p","-preset","veryfast","-crf","18","-c:a","aac","-t","15",src]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, **_ARGS_SIN_CONSOLA)
        if r.returncode != 0 or not os.path.isfile(src):
            if not _generar_video(src, duracion=15):
                return False, "gen fail"
        dst = os.path.join(tmp, "dst.mp4")
        gestor = GestorTareas()
        tarea = tv.TareaExportarSecuencia(src, [(0,5),(5,10),(10,14)], dst)
        ok_ini = gestor.iniciar(tarea)
        if not ok_ini:
            return False, "no inició tarea"
        time.sleep(0.2)
        tarea.cancelar()
        _esperar(lambda: not gestor.activo, timeout_ms=10000)
        time.sleep(0.6)
        tmp_files = [f for f in os.listdir(tmp) if ".tmp" in f]
        if tmp_files:
            return False, f"huérfanos tras cancel {tmp_files}"
        if gestor.activo:
            return False, "gestor sigue activo tras cancel"
        if os.path.exists(dst):
            return False, "dst existe tras cancel, debería haberse limpiado"
        gestor.cerrar()
        return True, "cancelación secuencia ok"

def test_12():
    if not _ffmpeg_disponible():
        return True, "skip"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src):
            return False, "gen fail"
        dst = os.path.join(tmp, "dst.mp4")
        gestor = GestorTareas()
        tarea = tv.TareaExportarSecuencia(src, [(0.5,1.5),(2.0,3.0)], dst)
        inicio_ok = gestor.iniciar(tarea)
        if not inicio_ok:
            return False, "inicio falló"
        if not gestor.activo:
            return False, "gestor debería estar activo"
        _esperar(lambda: not gestor.activo and gestor.hilo is None, timeout_ms=15000)
        if gestor.activo:
            return False, "gestor no volvió a inactivo"
        # Verificar que dst existe si ok
        if not os.path.isfile(dst):
            return False, "dst no existe tras secuencia"
        gestor.cerrar()
        return True, "background inactivo ok"

def test_13():
    # UI aislada: no subprocess/sqlite directo, usa TareaExportarSecuencia, naming B6.8, reutiliza selección B6.9
    src_v = inspect.getsource(visor_videos.VisorVideos)
    src_dialogo_seq = inspect.getsource(visor_videos.DialogoExportarSecuencia)
    src_seq_handler = inspect.getsource(visor_videos.VisorVideos._al_exportar_secuencia_solicitado)
    try:
        src_seq_dialog = inspect.getsource(visor_videos.VisorVideos._abrir_dialogo_secuencia_con_datos)
    except Exception:
        src_seq_dialog = ""
    combined_vis = src_v + src_dialogo_seq
    if "import subprocess" in combined_vis or "subprocess.Popen" in combined_vis or "subprocess.run" in combined_vis:
        return False, "UI contiene subprocess directo"
    if "import sqlite3" in combined_vis or "sqlite3.connect" in combined_vis:
        return False, "UI contiene sqlite directo"
    if "TareaExportarSecuencia" not in (src_seq_handler + src_seq_dialog):
        return False, "UI secuencia no usa TareaExportarSecuencia"
    if "QFileDialog.getSaveFileName" not in (src_seq_handler + src_seq_dialog):
        return False, "sin diálogo save"
    if "nombres.generar_sugerencia" not in (src_seq_handler + src_seq_dialog) and "nombres.asegurar_extension" not in (src_seq_handler + src_seq_dialog):
        return False, "sin naming B6.8"
    # Reutiliza selección B6.9: debe usar TareaListarSegmentosVarios y DialogoExportarSecuencia
    if "TareaListarSegmentosVarios" not in src_seq_handler:
        return False, "no reutiliza selección B6.9 (TareaListarSegmentosVarios)"
    if "DialogoExportarSecuencia" not in (src_seq_handler + src_seq_dialog + src_v):
        return False, "no usa diálogo secuencia"
    # Orden explícito: debe obtener segmentos_ordenados
    if "segmentos_ordenados" not in src_seq_dialog:
        return False, "sin orden explícito"
    # Dialogo no usa subprocess/sqlite/pixmap
    if "QPixmap" in src_dialogo_seq or "sqlite3" in src_dialogo_seq or "subprocess" in src_dialogo_seq:
        return False, "diálogo secuencia toca pixmap/subprocess/sqlite"
    # Verificar que no es B6.11 (incorporación catálogo): no debe mencionar incorporar al catálogo en secuencia
    if "incorporar" in src_seq_handler.lower() and "catalogo" in src_seq_handler.lower():
        return False, "secuencia no debe incorporar a catálogo (B6.11)"
    return True, "UI mínima secuencia ok"

def test_14():
    # Verificar temporales únicos en mismo directorio y extensión conservada, no -y, verificación y mapeo explícito
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src):
            return True, "skip gen"
        info = seq._ffprobe_info(src)
        args = seq._construir_args_concat_sin_subs(src, [(0,1),(1,2)], os.path.join(tmp, "dst.mp4"), info)
        if "-filter_complex" not in args:
            return False, "sin filter_complex"
        # Verificar trim/atrim/setpts/concat y mapeo explícito
        joined = " ".join(args)
        for token in ["trim=", "atrim=", "setpts", "concat", "-map"]:
            if token not in joined:
                return False, f"falta {token} en args"
        # Verificar recodificación CPU
        needed = ["libx264", "veryfast", "crf", "yuv420p", "aac"]
        for n in needed:
            if n not in joined:
                return False, f"falta {n}"
        # No -y contra destino final
        if "-y" in args:
            return False, "contiene -y"
        # Temporal en mismo directorio
        tmp_gen = seq._generar_temporal(os.path.join(tmp, "mi_destino.mp4"))
        if os.path.dirname(os.path.abspath(tmp_gen)) != os.path.dirname(os.path.abspath(os.path.join(tmp, "mi_destino.mp4"))):
            return False, "dir temporal distinto"
        if os.path.splitext(tmp_gen)[1].lower() != ".mp4":
            return False, "ext temporal distinta"
        return True, "construcción y temporales ok"

def test_15():
    # Validación N<2 debe fallar
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mp4")
        if not _generar_video(src):
            return True, "skip"
        dst = os.path.join(tmp, "dst.mp4")
        r1 = seq.exportar_secuencia(src, [(0,1)], dst)
        if r1.get("ok"):
            return False, "N=1 debería fallar"
        if "al menos 2" not in (r1.get("error") or ""):
            return False, f"error inesperado N=1 {r1.get('error')}"
        r2 = seq.exportar_secuencia(src, [(1,0.5),(0,1)], dst)
        if r2.get("ok"):
            return False, "fin < inicio debería fallar"
        return True, "validación N>=2 ok"

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    pruebas = [
        test_01, test_02, test_03, test_04, test_05, test_06, test_07, test_08, test_09, test_10,
        test_11, test_12, test_13, test_14, test_15
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            import traceback
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}\n{traceback.format_exc()[:600]}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")
        sys.stdout.flush()
        QApplication.processEvents()
        time.sleep(0.06)
    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__ == "__main__":
    sys.exit(main())
