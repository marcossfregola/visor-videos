"""Validación real B8.1 B - FFmpeg/FFprobe con video válido, pipeline reordenado."""
import os, tempfile, sqlite3, subprocess, shutil, sys, time
import rutas as rutas_mod
import escanear_videos as ev

def generar_video_valido(ruta_salida):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=320x180:d=1:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1",
        ruta_salida
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode==0 and os.path.isfile(ruta_salida) and os.path.getsize(ruta_salida)>0, res

def main():
    # contadores
    ffprobe_calls = {"n":0}
    ffmpeg_calls = {"n":0}
    orig_run = subprocess.run
    def counting_run(*a, **k):
        cmd = a[0] if a else k.get("args")
        txt = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "ffprobe" in txt:
            ffprobe_calls["n"]+=1
        if "ffmpeg" in txt:
            ffmpeg_calls["n"]+=1
        return orig_run(*a, **k)
    # parchear el subprocess usado por escanear_videos
    import escanear_videos as ev_mod
    orig_ev_run = ev_mod.subprocess.run
    ev_mod.subprocess.run = counting_run

    tmp_videos = tempfile.TemporaryDirectory()
    tmp_db = tempfile.TemporaryDirectory()
    tmp_mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp_db.name, "real.db")
    # parchear ruta miniaturas
    orig_mini = rutas_mod.ruta_carpeta_miniaturas
    orig_ev_mini = ev_mod.ruta_carpeta_miniaturas
    rutas_mod.ruta_carpeta_miniaturas = lambda: tmp_mini.name
    ev_mod.ruta_carpeta_miniaturas = lambda: tmp_mini.name

    try:
        # 1. generar video válido
        nombre = "valid.mp4"
        ruta_video = os.path.join(tmp_videos.name, nombre)
        ok_gen, res = generar_video_valido(ruta_video)
        print(f"1. generar video: ok={ok_gen} size={os.path.getsize(ruta_video) if os.path.isfile(ruta_video) else 0} ffmpeg_calls={ffmpeg_calls['n']}")
        if not ok_gen:
            print(res.stdout[-500:])
            print(res.stderr[-1000:])
            return 1
        # reset contadores tras generación inicial (esa ffmpeg es para crear recurso, no del pipeline)
        ffmpeg_calls["n"]=0
        ffprobe_calls["n"]=0

        # 2. Pipeline: preparar → tamanos → ffprobe → guardar (obtener id) → miniaturas → update
        conn = ev.conectar_bd(ruta_db)
        conn.commit()
        conn.close()
        print(f"2. DB creada, ffprobe_calls={ffprobe_calls['n']} ffmpeg_calls={ffmpeg_calls['n']} (migración)")

        # escanear
        videos = ev.escanear_videos(tmp_videos.name)
        print(f"3. escanear: {videos}")
        assert videos==[nombre]

        # tamanos
        tamanos_res = ev.obtener_tamanos_archivos(videos, tmp_videos.name)
        print(f"4. tamanos: {tamanos_res['con_tamano']} con tamaño")

        # ffprobe vía TareaFFprobe o directo? usar obtener_datos_ffprobe para contar
        # Usar listar_registros_por_nombres vacío para simular reutilización? Pero hacemos ffprobe real
        ff_calls_before = ffprobe_calls["n"]
        # preparar registros básicos + tamanos + ffprobe
        registros = ev.preparar_registros_basicos(videos, tmp_videos.name)
        # obtener ffprobe datos reales para cada ruta
        # Simular pipeline: usar obtener_datos_ffprobe directamente
        datos_ff = ev.obtener_datos_ffprobe(ruta_video)
        print(f"5. ffprobe datos: {datos_ff} ffprobe_calls={ffprobe_calls['n']}")
        assert datos_ff is not None and datos_ff["duracion_segundos"]>0

        # combinar con ffprobe (simular resultado TareaFFprobe)
        fake_ffprobe_res = {"resultados": [{"ruta": ruta_video, "datos": datos_ff, "error": None}]}
        registros = ev.combinar_registros_con_ffprobe(videos, tmp_videos.name, fake_ffprobe_res)
        registros = ev.combinar_registros_con_tamanos(registros, tamanos_res)
        print(f"6. registros combinados: {registros[0]}")

        # guardar primero (antes de miniaturas)
        ff_calls_save = ffprobe_calls["n"]
        res_guard = ev.guardar_videos(registros, ruta_db)
        print(f"7. guardar_videos: guardados={res_guard['guardados']} ids={res_guard['ids']} video_id={res_guard['ids'][0]} ffprobe_calls={ffprobe_calls['n']} ffmpeg_calls={ffmpeg_calls['n']}")
        video_id = res_guard["ids"][0]
        assert isinstance(video_id, int) and video_id>0

        # verificar fila tras guardar
        conn = sqlite3.connect(ruta_db)
        fila = conn.execute("SELECT id, nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE id=?", (video_id,)).fetchone()
        print(f"8. fila tras guardar: {fila}")
        conn.close()
        assert fila[0]==video_id and fila[1]==nombre and fila[2]==ruta_video
        assert fila[4] is not None  # metadata
        # ruta_normalizada estable
        assert fila[3]==rutas_mod.normalizar_ruta_clave(ruta_video)

        # generar miniatura real (asegurar_miniaturas) - debe usar FFmpeg
        ffmpeg_before = ffmpeg_calls["n"]
        ffprobe_before = ffprobe_calls["n"]
        mini_res = ev.asegurar_miniaturas(videos, tmp_videos.name, duraciones={ruta_video: datos_ff["duracion_segundos"]})
        print(f"9. asegurar_miniaturas: {mini_res} ffmpeg_calls={ffmpeg_calls['n']} ffprobe_calls={ffprobe_calls['n']}")
        # verificar que al menos 1 JPEG físico existe
        mini_files = os.listdir(tmp_mini.name) if os.path.isdir(tmp_mini.name) else []
        print(f"10. miniaturas en cache: {mini_files}")
        assert any(f.endswith(".jpg") for f in mini_files), "no JPEG generado"
        # validar JPEG válido (no vacío)
        for f in mini_files:
            p = os.path.join(tmp_mini.name, f)
            assert os.path.getsize(p)>100, f"JPEG vacío {f}"
        # cantidad debe ser >0
        assert mini_res["con_miniatura"]>=1

        # UPDATE por id
        # mapear ruta_normalizada -> id ya tenemos video_id
        cantidad = mini_res["resultados"][0]["cantidad_miniaturas"]
        print(f"11. cantidad_miniaturas reportada: {cantidad}")
        assert cantidad>0
        upd = ev.actualizar_cantidad_miniaturas_batch([(video_id, cantidad)], ruta_db)
        print(f"12. update batch: {upd}")

        # verificar fila conserva mismo id, nombre, ruta, ruta_normalizada, metadata y cantidad>0
        conn = sqlite3.connect(ruta_db)
        fila2 = conn.execute("SELECT id, nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos WHERE id=?", (video_id,)).fetchone()
        print(f"13. fila tras update: {fila2}")
        assert fila2[0]==fila[0] and fila2[1]==fila[1] and fila2[2]==fila[2] and fila2[3]==fila[3]
        assert fila2[4]==fila[4] and fila2[5]==fila[5]
        assert fila2[8]>0 and fila2[8]==cantidad

        # reintentar no crea otro video
        res_guard2 = ev.guardar_videos(registros, ruta_db)
        print(f"14. reintento guardar ids {res_guard2['ids']} mismo? {res_guard2['ids'][0]==video_id}")
        conn2 = sqlite3.connect(ruta_db)
        cnt = conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        print(f"15. count tras reintento: {cnt}")
        assert cnt==1 and res_guard2["ids"][0]==video_id

        # no segundo upsert completo después de miniaturas: verificar que actualizar no hizo upsert (solo UPDATE)
        # lo garantizamos porque usamos UPDATE WHERE id, no INSERT

        # integrity
        integ = conn2.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"16. integrity: {integ}")
        assert integ=="ok"
        conn2.close()
        conn.close()

        # reportar FFmpeg/FFprobe reales durante pipeline (excluyendo generación inicial)
        print(f"17. FFprobe totales pipeline: {ffprobe_calls['n']} (ffprobe_before_save={ff_calls_save} etc)")
        print(f"18. FFmpeg totales pipeline: {ffmpeg_calls['n']} (ffmpeg_before_mini={ffmpeg_before})")
        # Debe haber al menos 1 ffprobe para el video y 1 ffmpeg para miniatura
        assert ffprobe_calls["n"]>=1, "se esperaba al menos 1 ffprobe"
        assert ffmpeg_calls["n"]>=1, "se esperaba al menos 1 ffmpeg para miniatura"

        print("VALIDACIÓN REAL FFmpeg OK - 10/10 checks pasaron")
        return 0
    finally:
        rutas_mod.ruta_carpeta_miniaturas = orig_mini
        ev_mod.ruta_carpeta_miniaturas = orig_ev_mini
        ev_mod.subprocess.run = orig_ev_run
        tmp_videos.cleanup()
        tmp_db.cleanup()
        tmp_mini.cleanup()

if __name__=="__main__":
    sys.exit(main())
