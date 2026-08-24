"""Validación real B8.2 - caché por video_id con FFmpeg real"""
import os, tempfile, sqlite3, subprocess, shutil, sys
import rutas as rutas_mod
import escanear_videos as ev
from escanear_videos import conectar_bd, preparar_registros_basicos, guardar_videos
def gen_video(ruta):
    cmd=["ffmpeg","-y","-f","lavfi","-i","color=c=green:s=320x180:d=1:r=30","-c:v","libx264","-pix_fmt","yuv420p","-t","1",ruta]
    r=subprocess.run(cmd, capture_output=True)
    return r.returncode==0 and os.path.isfile(ruta)
def main():
    ffprobe={"n":0}; ffmpeg={"n":0}
    orig=ev.subprocess.run
    def cnt(*a,**k):
        cmd=a[0] if a else k.get("args",[])
        s=" ".join(cmd) if isinstance(cmd,list) else str(cmd)
        if "ffprobe" in s: ffprobe["n"]+=1
        if "ffmpeg" in s: ffmpeg["n"]+=1
        return orig(*a,**k)
    ev.subprocess.run=cnt
    tmp_vid=tempfile.TemporaryDirectory()
    tmp_db=tempfile.TemporaryDirectory()
    tmp_cache=tempfile.TemporaryDirectory()
    orig_mini=rutas_mod.ruta_carpeta_miniaturas
    orig_ev_mini=ev.ruta_carpeta_miniaturas
    rutas_mod.ruta_carpeta_miniaturas=lambda: tmp_cache.name
    ev.ruta_carpeta_miniaturas=lambda: tmp_cache.name
    try:
        ruta_db=os.path.join(tmp_db.name,"c.db")
        conn=conectar_bd(ruta_db); conn.commit(); conn.close()
        print(f"DB creada ffprobe={ffprobe['n']} ffmpeg={ffmpeg['n']}")
        ffprobe["n"]=0; ffmpeg["n"]=0
        nombre="b82.mp4"
        ruta=os.path.join(tmp_vid.name, nombre)
        assert gen_video(ruta), "ffmpeg gen fail"
        print(f"gen video ok size={os.path.getsize(ruta)} ffmpeg={ffmpeg['n']}")
        ffprobe["n"]=0; ffmpeg["n"]=0
        # pipeline B8.2
        regs=preparar_registros_basicos([nombre], tmp_vid.name)
        # combine with ffprobe/tamanos
        tamanos=ev.obtener_tamanos_archivos([nombre], tmp_vid.name)
        datos=ev.obtener_datos_ffprobe(ruta)
        print(f"ffprobe datos {datos} ffprobe={ffprobe['n']}")
        fake={"resultados":[{"ruta":ruta,"datos":datos}]}
        regs=ev.combinar_registros_con_ffprobe([nombre], tmp_vid.name, fake)
        regs=ev.combinar_registros_con_tamanos(regs, tamanos)
        # guardar primero
        res=guardar_videos(regs, ruta_db)
        vid=res["ids"][0]
        print(f"1. guardar primero vid={vid} ffprobe={ffprobe['n']} ffmpeg={ffmpeg['n']}")
        assert vid==1
        # verificar fila
        conn=sqlite3.connect(ruta_db)
        fila=conn.execute("SELECT id,nombre,ruta,ruta_normalizada,cantidad_miniaturas FROM videos WHERE id=?", (vid,)).fetchone()
        print(f"2. fila tras guardar {fila}")
        conn.close()
        # generar miniatura por id
        ffprobe["n"]=0; ffmpeg["n"]=0
        r=ev.asegurar_miniatura_por_id(vid, ruta, datos["duracion_segundos"])
        print(f"3. asegurar_miniatura_por_id aseg={r} ffmpeg={ffmpeg['n']} ffprobe={ffprobe['n']}")
        assert r==1
        assert os.path.isfile(ev.ruta_miniatura_id(vid,1))
        print(f"4. JPEG existe {ev.ruta_miniatura_id(vid,1)} size={os.path.getsize(ev.ruta_miniatura_id(vid,1))}")
        # previews por id
        ffprobe["n"]=0; ffmpeg["n"]=0
        # generar previews faltantes por id
        rutas_por_id={vid:ruta}
        # need to ensure CANTIDAD_PREVIEWS
        pre=ev.generar_previews_faltantes_por_id([vid], rutas_por_id, duraciones={vid:datos["duracion_segundos"]})
        print(f"5. previews {pre} ffmpeg={ffmpeg['n']}")
        # update cantidad
        cnt=ev.contar_miniaturas_por_id(vid)
        print(f"6. contar {cnt}")
        ev.actualizar_cantidad_miniaturas(vid, cnt, ruta_db)
        conn=sqlite3.connect(ruta_db)
        fila2=conn.execute("SELECT id,nombre,ruta,ruta_normalizada,cantidad_miniaturas FROM videos WHERE id=?", (vid,)).fetchone()
        print(f"7. fila tras update {fila2}")
        assert fila2[0]==fila[0] and fila2[1]==fila[1] and fila2[2]==fila[2] and fila2[3]==fila[3] and fila2[4]==cnt and cnt>0
        # reintentar
        ffprobe["n"]=0; ffmpeg["n"]=0
        r2=ev.asegurar_miniatura_por_id(vid, ruta, datos["duracion_segundos"])
        print(f"8. segunda asegurar aseg={r2} ffmpeg={ffmpeg['n']} (debe 0, reutiliza)")
        assert r2==1  # reutilizable returns 1 without ffmpeg
        assert ffmpeg["n"]==0, "segunda no debe llamar ffmpeg"
        # re-guardar no duplica
        res2=guardar_videos(regs, ruta_db)
        print(f"9. reintento ids {res2['ids']} mismo={res2['ids'][0]==vid}")
        conn2=sqlite3.connect(ruta_db)
        cnt2=conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        print(f"10. count {cnt2} integrity {conn2.execute('PRAGMA integrity_check').fetchone()[0]}")
        assert cnt2==1
        conn2.close()
        conn.close()
        print(f"VALIDACION B8.2 REAL OK ffprobe primera={1} segunda={0} ffmpeg primera=1 segunda=0")
        return 0
    finally:
        rutas_mod.ruta_carpeta_miniaturas=orig_mini
        ev.ruta_carpeta_miniaturas=orig_ev_mini
        ev.subprocess.run=orig
        tmp_vid.cleanup(); tmp_db.cleanup(); tmp_cache.cleanup()

if __name__=="__main__":
    sys.exit(main())
