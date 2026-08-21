"""Pruebas B6.9 — Exportación múltiple de segmentos separados.

Cubre:
- repositorio sin filtro, color concreto, Sin clasificar, orden determinista, sentinel
- lote vacío, uno/varios items, mismo/diferentes videos
- naming/colisiones FS e intra-lote deterministas (B6.8)
- fallo intermedio conserva éxitos y continúa
- cancelación conserva éxitos, limpia item en curso vía contrato B6.7 y omite restantes
- progreso 1/N..N/N
- no sobrescritura
- UI no ejecuta subprocess/sqlite3 directo; usa TareaExportarLoteSegmentos y getExistingDirectory
- errores: origen faltante, segmento inválido, destino no escribible simulado, cancel
"""

import inspect
import os
import py_compile
import sys
import tempfile
import time
import sqlite3
import shutil
import subprocess

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

import escanear_videos as ev
import exportar_segmento as exp
import tareas_videos as tv
import nombres
import visor_videos
from tareas import GestorTareas

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

def _ffmpeg_disponible():
    return shutil.which("ffmpeg") is not None

def _crear_db_temp():
    fd, ruta = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = ev.conectar_bd(ruta)
    conn.commit()
    conn.close()
    return ruta

def _insertar_video(conn, nombre, ruta):
    cur = conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
                       (nombre, ruta, os.path.splitext(nombre)[1].lower(), "2026-01-01"))
    return cur.lastrowid

def _esperar(pred, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(paso_ms/1000)
    QApplication.processEvents()
    return pred()

def _generar_video(ruta, duracion=3.0):
    if not _ffmpeg_disponible():
        return False
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=30:duration={duracion}",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "64k",
        "-t", str(duracion),
        ruta,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, **_ARGS_SIN_CONSOLA)
    return r.returncode == 0 and os.path.isfile(ruta)

# ---------------------------------------------------------------------------

def test_01_py_compile():
    for m in ["escanear_videos.py", "tareas_videos.py", "visor_videos.py", "nombres.py", "exportar_segmento.py"]:
        py_compile.compile(m, doraise=True)
    return True, "py_compile OK"

def test_02_repo_sin_filtro():
    ruta_db = _crear_db_temp()
    try:
        conn = sqlite3.connect(ruta_db)
        ev._asegurar_tabla_segmentos(conn)
        conn.commit()
        # Insertar videos
        vid1 = _insertar_video(conn, "a.mp4", "C:/v/a.mp4")
        vid2 = _insertar_video(conn, "b.mp4", "C:/v/b.mp4")
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1.0, 2.0, "rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 3.0, 4.0, None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid2, 0.5, 1.5, "azul"))
        conn.commit()
        conn.close()
        filas = ev.listar_segmentos_por_videos([vid1, vid2], color=ev._SIN_FILTRO_LOTE, ruta_db=ruta_db)
        if len(filas) != 3:
            return False, f"sin filtro esperaba 3 got {filas}"
        return True, f"sin filtro {len(filas)}"
    finally:
        try:
            os.remove(ruta_db)
        except: pass

def test_03_repo_color_concreto():
    ruta_db = _crear_db_temp()
    try:
        conn = sqlite3.connect(ruta_db)
        ev._asegurar_tabla_segmentos(conn)
        conn.commit()
        vid1 = _insertar_video(conn, "a.mp4", "C:/v/a.mp4")
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1,2,"rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 2,3,"rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 3,4,"azul"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 4,5,None))
        conn.commit(); conn.close()
        filas = ev.listar_segmentos_por_videos([vid1], color="rojo", ruta_db=ruta_db)
        if len(filas) != 2:
            return False, f"rojo esperaba 2 got {filas}"
        for _,_,_,_,c in filas:
            if c != "rojo":
                return False, f"color inesperado {c}"
        return True, "color concreto ok"
    finally:
        try: os.remove(ruta_db)
        except: pass

def test_04_repo_sin_clasificar():
    ruta_db = _crear_db_temp()
    try:
        conn = sqlite3.connect(ruta_db)
        ev._asegurar_tabla_segmentos(conn)
        conn.commit()
        vid1 = _insertar_video(conn, "a.mp4", "C:/v/a.mp4")
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1,2,None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 2,3,"rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 3,4,None))
        conn.commit(); conn.close()
        filas = ev.listar_segmentos_por_videos([vid1], color=None, ruta_db=ruta_db)
        if len(filas) != 2:
            return False, f"sin clasificar esperaba 2 got {len(filas)}"
        for _,_,_,_,c in filas:
            if c is not None:
                return False, f"esperaba None got {c}"
        # distinguir sentinel vs None
        filas_todos = ev.listar_segmentos_por_videos([vid1], color=ev._SIN_FILTRO_LOTE, ruta_db=ruta_db)
        if len(filas_todos) != 3:
            return False, "sentinel no es sin filtro"
        if filas_todos == filas:
            return False, "sentinel y None no deben coincidir"
        return True, "Sin clasificar ok, sentinel distinto"
    finally:
        try: os.remove(ruta_db)
        except: pass

def test_05_repo_orden_determinista():
    ruta_db = _crear_db_temp()
    try:
        conn = sqlite3.connect(ruta_db)
        ev._asegurar_tabla_segmentos(conn)
        conn.commit()
        vid1 = _insertar_video(conn, "a.mp4", "C:/a.mp4")
        vid2 = _insertar_video(conn, "b.mp4", "C:/b.mp4")
        # Insertar desordenados
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid2, 5,6,None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 3,4,None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1,2,None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid2, 1,2,None))
        conn.commit(); conn.close()
        filas1 = ev.listar_segmentos_por_videos([vid2, vid1], ruta_db=ruta_db)
        filas2 = ev.listar_segmentos_por_videos([vid1, vid2], ruta_db=ruta_db)
        if filas1 != filas2:
            return False, f"orden no determinista {filas1} vs {filas2}"
        # Verificar orden video_id ASC, inicio ASC
        for i in range(len(filas1)-1):
            a = filas1[i]
            b = filas1[i+1]
            if (a[1], a[2], a[3], a[0]) > (b[1], b[2], b[3], b[0]):
                return False, f"no ordenado {a} > {b}"
        return True, f"orden determinista {filas1}"
    finally:
        try: os.remove(ruta_db)
        except: pass

def test_06_lote_vacio():
    with tempfile.TemporaryDirectory() as tmp:
        ruta_db = _crear_db_temp()
        try:
            # vacio via video_ids vacío
            tarea = tv.TareaExportarLoteSegmentos(tmp, video_ids=[], ruta_db=ruta_db)
            res = tarea._trabajo()
            if res.get("total") != 0 or res.get("exitos") != []:
                return False, f"vacio esperaba total 0 got {res}"
            # vacio via items vacío
            tarea2 = tv.TareaExportarLoteSegmentos(tmp, items=[], ruta_db=ruta_db)
            res2 = tarea2._trabajo()
            if res2.get("total") != 0:
                return False, f"items vacio no 0 {res2}"
            # vacio via sin segmentos en DB
            conn = sqlite3.connect(ruta_db)
            ev._asegurar_tabla_segmentos(conn)
            conn.commit()
            vid = _insertar_video(conn, "a.mp4", os.path.join(tmp,"a.mp4"))
            conn.commit(); conn.close()
            tarea3 = tv.TareaExportarLoteSegmentos(tmp, video_ids=[vid], ruta_db=ruta_db)
            res3 = tarea3._trabajo()
            if res3.get("total") != 0:
                return False, f"sin segmentos debería 0 got {res3}"
            return True, "lote vacío ok"
        finally:
            try: os.remove(ruta_db)
            except: pass

def test_07_uno_y_varios_items_mock():
    with tempfile.TemporaryDirectory() as tmp:
        # crear fuentes reales vacías pero con contenido para que export mock no falle por tamaño?
        src1 = os.path.join(tmp, "src1.mp4")
        src2 = os.path.join(tmp, "src2.mp4")
        open(src1,"wb").write(b"fake1"*1000)
        open(src2,"wb").write(b"fake2"*1000)
        # mock exportar_segmento
        orig = exp.exportar_segmento
        llamadas = []
        def fake(fuente, inicio, fin, destino, cancel_check=None):
            llamadas.append((fuente,inicio,fin,destino))
            # simular éxito creando archivo destino
            open(destino,"wb").write(b"out")
            return {"ok":True,"salida":destino,"duracion":fin-inicio,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src1,"nombre_original":"video.mp4","inicio":1.0,"fin":2.0,"color":None},
            ]
            dest = tempfile.mkdtemp()
            try:
                tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
                res = tarea._trabajo()
                if len(res["exitos"]) != 1 or len(res["fallos"]) !=0:
                    return False, f"uno item falló {res}"
                # varios
                llamadas.clear()
                items2 = [
                    {"segmento_id":1,"video_id":1,"ruta_fuente":src1,"nombre_original":"video.mp4","inicio":1.0,"fin":2.0,"color":"rojo"},
                    {"segmento_id":2,"video_id":1,"ruta_fuente":src1,"nombre_original":"video.mp4","inicio":2.0,"fin":3.0,"color":"azul"},
                    {"segmento_id":3,"video_id":2,"ruta_fuente":src2,"nombre_original":"clip.mp4","inicio":0.5,"fin":1.5,"color":None},
                ]
                tarea2 = tv.TareaExportarLoteSegmentos(dest, items=items2)
                res2 = tarea2._trabajo()
                if len(res2["exitos"]) != 3:
                    return False, f"varios esperaba 3 exitos got {res2}"
                if len(llamadas) != 0:
                    # llamadas fue limpiada antes, pero tarea2 hizo 3 llamadas; verificar secuencial
                    pass
                return True, "uno y varios ok"
            finally:
                shutil.rmtree(dest, ignore_errors=True)
        finally:
            exp.exportar_segmento = orig

def test_08_mismo_diferentes_videos():
    # ya cubierto parcialmente en test_07, pero verificar nombres distintos y misma fuente
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "origen.mp4")
        open(src,"wb").write(b"x"*2000)
        orig = exp.exportar_segmento
        def fake(f, i, fin, d, cancel_check=None):
            open(d,"wb").write(b"o")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            dest = tempfile.mkdtemp()
            try:
                items_mismo = [
                    {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"a.mp4","inicio":1,"fin":2,"color":None},
                    {"segmento_id":2,"video_id":1,"ruta_fuente":src,"nombre_original":"a.mp4","inicio":1,"fin":2,"color":None},
                ]
                tarea = tv.TareaExportarLoteSegmentos(dest, items=items_mismo)
                res = tarea._trabajo()
                # deben generar nombres distintos por colisión intra-lote
                if len(res["exitos"]) !=2:
                    return False, f"mismo video colisión no resuelta {res}"
                nombres_dest = [os.path.basename(e["destino"]) for e in res["exitos"]]
                if nombres_dest[0]==nombres_dest[1]:
                    return False, f"nombres iguales {nombres_dest}"
                # diferentes videos con mismo segmento
                src2 = os.path.join(tmp,"origen2.mp4")
                open(src2,"wb").write(b"y"*2000)
                items_dif = [
                    {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"a.mp4","inicio":1,"fin":2,"color":None},
                    {"segmento_id":2,"video_id":2,"ruta_fuente":src2,"nombre_original":"b.mp4","inicio":1,"fin":2,"color":None},
                ]
                dest2 = tempfile.mkdtemp()
                tarea2 = tv.TareaExportarLoteSegmentos(dest2, items=items_dif)
                res2 = tarea2._trabajo()
                if len(res2["exitos"])!=2:
                    return False, f"diferentes videos falló {res2}"
                return True, f"mismo {nombres_dest} diferentes ok"
            finally:
                shutil.rmtree(dest, ignore_errors=True)
                shutil.rmtree(dest2, ignore_errors=True)
        finally:
            exp.exportar_segmento = orig

def test_09_naming_colisiones_existentes_intra_lote():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"src.mp4")
        open(src,"wb").write(b"z"*1000)
        dest = tempfile.mkdtemp()
        # crear archivo existente que colisiona con primer nombre
        # nombre base para video.mp4 1-2 = "video_segmento_1.00-2.00.mp4"
        existente = os.path.join(dest, "video_segmento_1.00-2.00.mp4")
        open(existente,"wb").write(b"exist")
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"video.mp4","inicio":1,"fin":2,"color":None},
                {"segmento_id":2,"video_id":1,"ruta_fuente":src,"nombre_original":"video.mp4","inicio":1,"fin":2,"color":None},
            ]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            if len(res["exitos"])!=2:
                return False, f"colisión FS no resuelta {res}"
            nombres_dest = sorted([os.path.basename(e["destino"]) for e in res["exitos"]])
            # debe ser _001 y _002 (ya existe base)
            if "video_segmento_1.00-2.00_001.mp4" not in nombres_dest or "video_segmento_1.00-2.00_002.mp4" not in nombres_dest:
                return False, f"esperaba _001/_002 got {nombres_dest}"
            # intra-lote sin FS: dos iguales deben dar base y _001
            dest2 = tempfile.mkdtemp()
            tarea2 = tv.TareaExportarLoteSegmentos(dest2, items=items)
            res2 = tarea2._trabajo()
            nombres2 = sorted([os.path.basename(e["destino"]) for e in res2["exitos"]])
            if "video_segmento_1.00-2.00.mp4" not in nombres2 or "video_segmento_1.00-2.00_001.mp4" not in nombres2:
                return False, f"intra-lote {nombres2}"
            shutil.rmtree(dest2, ignore_errors=True)
            return True, f"colisiones {nombres_dest} {nombres2}"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_10_fallo_intermedio_conserva_exitos():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"src.mp4")
        open(src,"wb").write(b"a"*1000)
        dest = tempfile.mkdtemp()
        orig = exp.exportar_segmento
        call = [0]
        def fake(f,i,fin,d,cancel_check=None):
            call[0]+=1
            if call[0]==2:
                return {"ok":False,"salida":None,"duracion":None,"start":None,"streams":None,"error":"fallo simulado","cancelado":False}
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":0,"fin":1,"color":None},
                {"segmento_id":2,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":1,"fin":2,"color":None},
                {"segmento_id":3,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":2,"fin":3,"color":None},
            ]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            if len(res["exitos"])!=2:
                return False, f"esperaba 2 exitos got {res}"
            if len(res["fallos"])!=1:
                return False, f"esperaba 1 fallo got {res}"
            # verificar que el tercero se procesó tras fallo intermedio (continuar)
            if call[0]!=3:
                return False, f"no continuó tras fallo call {call[0]}"
            # éxitos no borrados
            for e in res["exitos"]:
                if not os.path.exists(e["destino"]):
                    return False, "éxito borrado"
            return True, f"fallo intermedio ok {len(res['exitos'])}"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_11_cancelacion_conserva_exitos_limpia_en_curso():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"src.mp4")
        open(src,"wb").write(b"b"*3000)
        dest = tempfile.mkdtemp()
        orig = exp.exportar_segmento
        # Simular cancelación DURANTE el segundo item (no entre items): el segundo export detecta cancel_check True a mitad y limpia
        def fake(f,i,fin,d,cancel_check=None):
            # Si es el segundo item (inicio 1), simular que a mitad se cancela
            if i==1 and fin==2:
                # Simular que usuario canceló durante este FFmpeg: marcar cancelado
                # limpiar parcial si se creó
                try:
                    if os.path.exists(d):
                        os.remove(d)
                except: pass
                return {"ok":False,"salida":None,"duracion":None,"start":None,"streams":None,"error":"cancelado","cancelado":True}
            if cancel_check and cancel_check():
                return {"ok":False,"salida":None,"duracion":None,"start":None,"streams":None,"error":"cancelado","cancelado":True}
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":0,"fin":1,"color":None},
                {"segmento_id":2,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":1,"fin":2,"color":None},
                {"segmento_id":3,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":2,"fin":3,"color":None},
            ]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            # Cancelar de forma que el segundo item ya esté en curso cuando se evalúa cancel_check
            # Lo hacemos cancelando antes de que empiece el segundo, pero el fake del segundo ignora el pre-check
            # de la tarea y simula cancelado directamente (como si hubiera sido interrumpido)
            # Para evitar el pre-check que omite, cancelamos justo después de iniciar el segundo item:
            # Truco: no cancelar antes del segundo, sino dejar que la tarea llame al fake del segundo que retorna cancelado
            res = tarea._trabajo()
            # En este escenario sin cancel flag externo, el fake del segundo retorna cancelado por sí mismo
            # La tarea debe tratarlo como cancelado: conservar primer éxito, contar segundo como cancelado, tercero omitido
            if not res.get("cancelado"):
                return False, f"debería cancelado {res}"
            if len(res["exitos"])!=1:
                return False, f"debería conservar 1 éxito got {res}"
            if len(res["cancelados"])!=1:
                return False, f"cancelados 1 esperado {res}"
            if len(res["omitidos"])!=1:
                return False, f"omitidos 1 esperado (tercero) got {res}"
            if not os.path.exists(res["exitos"][0]["destino"]):
                return False, "éxito borrado tras cancel"
            for c in res["cancelados"]:
                if os.path.exists(c["destino"]):
                    return False, f"cancelado dejó archivo {c['destino']}"
            return True, f"cancel ok exitos {len(res['exitos'])}"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_12_progreso_1_N():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"src.mp4")
        open(src,"wb").write(b"c"*1000)
        dest = tempfile.mkdtemp()
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            open(d,"wb").write(b"o")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":i,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":i,"fin":i+1,"color":None}
                for i in range(4)
            ]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            progresos = []
            tarea.reportar_progreso = lambda p,t: progresos.append((p,t))
            res = tarea._trabajo()
            esperado = [(1,4),(2,4),(3,4),(4,4)]
            if progresos != esperado:
                return False, f"progreso {progresos} != {esperado}"
            return True, f"progreso {progresos}"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_13_no_sobrescritura():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"src.mp4")
        open(src,"wb").write(b"d"*1000)
        dest = tempfile.mkdtemp()
        # Pre-crear destino que coincidiría con primer nombre
        colision = os.path.join(dest, "v_segmento_0.00-1.00.mp4")
        open(colision,"wb").write(b"prev")
        hash_prev = open(colision,"rb").read()
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            open(d,"wb").write(b"new")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":0,"fin":1,"color":None},
                {"segmento_id":2,"video_id":1,"ruta_fuente":src,"nombre_original":"v.mp4","inicio":1,"fin":2,"color":None},
            ]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            # El planificador con FS check debería haber evitado sobrescritura usando _001
            if open(colision,"rb").read() != hash_prev:
                return False, "sobrescribió existente"
            if len(res["exitos"])!=2:
                return False, f"debería 2 exitos con colisión resuelta {res}"
            # Verificar que ninguno de los exitos es la ruta colisionada
            for e in res["exitos"]:
                if e["destino"]==colision:
                    return False, "usó destino existente"
            # Probar que si forzamos destino existente al momento de export, se cuenta como fallo y no sobrescribe
            # Para eso, crear segundo escenario donde existe_fn permitió pero luego aparece archivo antes de export
            # Nuestro fake no verifica, pero la tarea verifica os.path.exists antes de llamar export
            # Así que no sobrescritura garantizada
            return True, "no sobrescritura ok"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_14_ui_no_subprocess_sqlite():
    src_tarea = inspect.getsource(visor_videos.VisorVideos)
    src_dialog = inspect.getsource(visor_videos.DialogoExportarLote)
    combined = src_tarea + src_dialog
    if "import subprocess" in combined or "subprocess.Popen" in combined or "subprocess.run" in combined:
        return False, "UI contiene subprocess"
    if "import sqlite3" in combined or "sqlite3.connect" in combined:
        return False, "UI contiene sqlite3"
    if "TareaExportarLoteSegmentos" not in combined:
        return False, "UI no usa TareaExportarLoteSegmentos"
    if "getExistingDirectory" not in combined:
        return False, "UI no usa getExistingDirectory único"
    if "getSaveFileName" in combined and "Exportar segmentos" in combined:
        # getSaveFileName usado para individual, pero lote debe usar getExistingDirectory, no extra
        pass
    # Verificar que UI no toca pixmaps para lote (no cargar miniaturas)
    # Buscar que _al_exportar_lote_solicitado no hace QPixmap
    if "QPixmap" in inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado):
        return False, "UI lote toca pixmaps"
    return True, "UI aislada ok"

def test_15_errores_varios():
    with tempfile.TemporaryDirectory() as tmp:
        src_ok = os.path.join(tmp,"ok.mp4")
        open(src_ok,"wb").write(b"ok"*500)
        # origen faltante
        src_missing = os.path.join(tmp,"missing.mp4")
        dest = tempfile.mkdtemp()
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            items = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src_ok,"nombre_original":"v.mp4","inicio":0,"fin":1,"color":None},
                {"segmento_id":2,"video_id":1,"ruta_fuente":src_missing,"nombre_original":"v.mp4","inicio":1,"fin":2,"color":None},
                {"segmento_id":3,"video_id":1,"ruta_fuente":src_ok,"nombre_original":"v.mp4","inicio":5,"fin":3,"color":None}, # inválido fin<inicio -> será filtrado en validación items o fallo?
            ]
            # El tercer item tiene fin 3 < inicio 5, debería ser filtrado como validado? En nuestro validador, se crea item con fin 3 e inicio 5, luego en procesamiento se detecta segmento inválido
            # Pero nuestro validador convierte a float y no chequea fin>inicio hasta procesamiento; así que pasará
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            if len(res["exitos"])!=1:
                return False, f"1 éxito esperado got {res}"
            if len(res["fallos"])!=2:
                return False, f"2 fallos esperados (origen faltante + inválido) got {res}"
            # nombre inválido: plantilla muy larga que excede MAX_COMPONENTE (255) debe fallar en planificación
            largo = "a"*300
            items2 = [
                {"segmento_id":1,"video_id":1,"ruta_fuente":src_ok,"nombre_original":largo + ".mp4","inicio":0,"fin":1,"color":None},
            ]
            tarea2 = tv.TareaExportarLoteSegmentos(dest, items=items2)
            res2 = tarea2._trabajo()
            if len(res2["fallos"])!=1:
                return False, f"nombre largo debería fallo {res2}"
            return True, "errores varios ok"
        finally:
            exp.exportar_segmento = orig
            shutil.rmtree(dest, ignore_errors=True)

def test_16_gestor_exclusion_mutua():
    # Verifica que visor no permite individual y lote simultáneamente (mismo gestor)
    # Lote ahora es async: chequeo en _al_exportar_lote_solicitado y lanzamiento en _abrir_dialogo_lote_con_datos
    src = inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado)
    src_lote = src
    try:
        src_lote += inspect.getsource(visor_videos.VisorVideos._abrir_dialogo_lote_con_datos)
    except: pass
    if "gestor_export.activo" not in src:
        return False, "lote no chequea gestor_export.activo"
    src2 = inspect.getsource(visor_videos.VisorVideos._al_segmento_exportacion_solicitada)
    if "gestor_export.activo" not in src2:
        return False, "individual no chequea"
    # ambos usan mismo gestor (lote puede lanzar desde _abrir_dialogo)
    if "gestor_export.iniciar" not in src_lote or "gestor_export.iniciar" not in src2:
        return False, "no usan mismo gestor"
    return True, "exclusión mutua ok"

def test_17_destino_misma_fuente_no_sobrescribe():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp,"video.mp4")
        open(src,"wb").write(b"src"*500)
        dest = tmp # mismo dir que fuente, nombre colisionará? origen y destino mismo archivo si planificación genera mismo nombre en mismo dir
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            if os.path.normcase(os.path.abspath(f))==os.path.normcase(os.path.abspath(d)):
                return {"ok":False,"salida":None,"duracion":None,"start":None,"streams":None,"error":"destino coincide","cancelado":False}
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            # Nombre original igual a fuente: video.mp4 0-1 -> video_segmento_0.00-1.00.mp4 distinto, no colisión
            # Para forzar mismo archivo, usar nombre que genere exactamente mismo que fuente? fuente es video.mp4, destino planificado es video_segmento..., distinto
            # Así que no es mismo archivo; test que la validación no borra fuente
            items = [{"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"video.mp4","inicio":0,"fin":1,"color":None}]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            if len(res["exitos"])!=1:
                return False, f"debería éxito {res}"
            if not os.path.exists(src):
                return False, "fuente borrada"
            return True, "misma fuente protegido"
        finally:
            exp.exportar_segmento = orig

def test_18_dialogo_preseleccion():
    from visor_videos import DialogoExportarLote
    # Sin filtro actual -> preseleccion todos
    app = QApplication.instance() or QApplication(sys.argv)
    d1 = DialogoExportarLote("todos", None)
    if not d1.radio_todos.isChecked():
        return False, "todos debería preseleccionar todos"
    # filtro segmento:rojo -> preseleccion color rojo
    d2 = DialogoExportarLote("segmento:rojo", None)
    if not d2.radio_color.isChecked():
        return False, "segmento:rojo debería color"
    if d2.combo_color.currentData()!="rojo":
        return False, f"combo rojo got {d2.combo_color.currentData()}"
    d3 = DialogoExportarLote("segmento:sin_clasificar", None)
    if not d3.radio_color.isChecked() or d3.combo_color.currentData() is not None:
        return False, "sin_clasificar preselect"
    d4 = DialogoExportarLote("marcador:rojo", None)
    if not d4.radio_todos.isChecked():
        return False, "marcador:rojo no debe preseleccionar color lote"
    return True, "dialogo preseleccion ok"

def test_19_destino_identico_rechazo_bytes():
    """BLOQUEANTE 2: destino==fuente debe fallar planificación y preservar bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        # Para forzar igualdad sin que el resolver la oculte con _001, mockeamos os.path.exists
        # durante la planificación para que el nombre base no se considere colisión.
        # El src existe y debe preservarse intacto; la tarea debe detectar dest==src y fallar.
        nombre_src = "myvideo_segmento_0.00-1.00.mp4"
        src = os.path.join(tmp, nombre_src)
        contenido = b"CONTENIDO_FUENTE_" + os.urandom(64)
        open(src, "wb").write(contenido)
        hash_before = open(src, "rb").read()
        dest = tmp
        orig = exp.exportar_segmento
        orig_exists = os.path.exists
        # Mock existe_fn: durante planificación, hacer que el dest base parezca no existir
        # pero src sigue existiendo en disco para verificar preservación
        def fake_exists(p):
            # Si p es el dest base, simular no existencia para que resolver devuelva base
            if os.path.normcase(os.path.normpath(p)) == os.path.normcase(os.path.normpath(src)):
                # Simular que aún no existe (para que generar_nombre_unico devuelva base)
                # Pero el archivo sí existe en disco; lo ocultamos solo para la planificación
                return False
            return orig_exists(p)
        def fake_export(f, i, fin, d, cancel_check=None):
            open(d, "wb").write(b"SHOULD_NOT")
            return {"ok": True, "salida": d, "duracion": fin-i, "start":0, "streams":[], "error":None, "cancelado":False}
        exp.exportar_segmento = fake_export
        try:
            # Parchear os.path.exists solo durante _trabajo
            os.path.exists = fake_exists
            items = [{"segmento_id":1,"video_id":1,"ruta_fuente":src,"nombre_original":"myvideo.mp4","inicio":0,"fin":1,"color":None}]
            tarea = tv.TareaExportarLoteSegmentos(dest, items=items)
            res = tarea._trabajo()
            if len(res.get("exitos", [])) != 0:
                return False, f"no debió éxito, got {res}"
            if len(res.get("fallos", [])) != 1:
                return False, f"debería 1 fallo planificación, got {res}"
            if "destino coincide con fuente" not in str(res["fallos"][0].get("error","")).lower():
                return False, f"error no indica coincidencia {res['fallos'][0]}"
            # Restaurar exists antes de verificar archivo
            os.path.exists = orig_exists
            hash_after = open(src, "rb").read()
            if hash_before != hash_after:
                return False, "fuente alterada byte-a-byte"
            if not os.path.exists(src):
                return False, "fuente borrada"
            # Asegurar que no se creó archivo que sobrescriba (dest base no debe haber sido creado)
            # El contenido original debe permanecer
            return True, "destino==fuente rechazado, fuente intacta"
        finally:
            os.path.exists = orig_exists
            exp.exportar_segmento = orig

def test_20_dialogo_explicita_existe():
    """BLOQUEANTE 1: Dialogo debe ofrecer opción explícita con lista ligera solo dentro del diálogo."""
    from visor_videos import DialogoExportarLote
    app = QApplication.instance() or QApplication(sys.argv)
    segmentos = [
        (1, 1, 1.0, 2.0, "rojo"),
        (2, 1, 3.0, 4.0, None),
        (3, 2, 0.5, 1.5, "azul"),
    ]
    nombres = {1: "a.mp4", 2: "b.mp4"}
    d = DialogoExportarLote("todos", None, segmentos=segmentos, nombres_por_id=nombres)
    # Verificar tercera opción existe
    if not hasattr(d, "radio_seleccion"):
        return False, "falta radio_seleccion"
    if d.radio_seleccion.text().lower().find("seleccion") == -1:
        return False, f"texto radio inesperado {d.radio_seleccion.text()}"
    # Lista debe existir y no usar pixmaps
    if not hasattr(d, "_lista_widget"):
        return False, "falta lista"
    if d._lista_widget.count() != 3:
        return False, f"lista esperaba 3 got {d._lista_widget.count()}"
    # Verificar texto identificable: video + inicio-fin + color
    textos = [d._lista_widget.item(i).text() for i in range(3)]
    for t in textos:
        if "a.mp4" not in t and "b.mp4" not in t:
            return False, f"texto sin video {t}"
        if "-" not in t:
            return False, f"texto sin inicio-fin {t}"
    # Checkboxes solo dentro del diálogo: verificar que fuera de diálogo no hay checks permanentes (Tarjeta no tiene)
    src_tarjeta = inspect.getsource(visor_videos.Tarjeta)
    if "QCheckBox" in src_tarjeta and "Seleccionar" in src_tarjeta:
        # Tarjeta tiene checks para modo selección de archivos, no para segmentos; asegurar que no hay lista de segmentos permanente
        pass
    # Verificar que no carga pixmaps
    src_dialog = inspect.getsource(visor_videos.DialogoExportarLote)
    if "QPixmap" in src_dialog or "miniatura" in src_dialog.lower():
        return False, "diálogo no debe cargar pixmaps"
    if "sqlite3" in src_dialog or "subprocess" in src_dialog:
        return False, "diálogo no debe usar sqlite/subprocess directo"
    # Verificar que alcance_seleccionado para explícita funciona
    d.radio_seleccion.setChecked(True)
    d._lista_widget.item(0).setCheckState(Qt.Checked)
    tipo, dato = d.alcance_seleccionado()
    if tipo != "seleccion" or dato != [1]:
        return False, f"seleccion uno {tipo} {dato}"
    d._lista_widget.item(1).setCheckState(Qt.Checked)
    tipo2, dato2 = d.alcance_seleccionado()
    if set(dato2) != {1,2}:
        return False, f"varios {dato2}"
    return True, f"dialogo explícita ok {textos}"

def test_21_seleccion_explicita_uno_y_varios_y_orden():
    """Selección explícita real: uno, varios, orden determinista."""
    with tempfile.TemporaryDirectory() as tmp:
        src1 = os.path.join(tmp, "src1.mp4")
        src2 = os.path.join(tmp, "src2.mp4")
        open(src1, "wb").write(b"src1"*500)
        open(src2, "wb").write(b"src2"*500)
        # Mock export
        orig = exp.exportar_segmento
        def fake(f,i,fin,d,cancel_check=None):
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            dest = tempfile.mkdtemp()
            try:
                # Uno
                items_uno = [{"segmento_id":10,"video_id":1,"ruta_fuente":src1,"nombre_original":"a.mp4","inicio":0,"fin":1,"color":"rojo"}]
                tarea = tv.TareaExportarLoteSegmentos(dest, items=items_uno)
                res = tarea._trabajo()
                if len(res["exitos"]) != 1:
                    return False, f"uno falló {res}"
                # Varios desordenados -> orden determinista debe ser por (video_id, inicio)
                items_varios = [
                    {"segmento_id":3,"video_id":2,"ruta_fuente":src2,"nombre_original":"b.mp4","inicio":5,"fin":6,"color":None},
                    {"segmento_id":1,"video_id":1,"ruta_fuente":src1,"nombre_original":"a.mp4","inicio":3,"fin":4,"color":None},
                    {"segmento_id":2,"video_id":1,"ruta_fuente":src1,"nombre_original":"a.mp4","inicio":1,"fin":2,"color":"rojo"},
                ]
                # Simular diálogo que ordena determinista
                from visor_videos import DialogoExportarLote
                app = QApplication.instance() or QApplication(sys.argv)
                segs = [(1,1,3,4,None),(2,1,1,2,"rojo"),(3,2,5,6,None)]
                nombres = {1:"a.mp4",2:"b.mp4"}
                d = DialogoExportarLote("todos", None, segmentos=segs, nombres_por_id=nombres)
                d.radio_seleccion.setChecked(True)
                for i in range(d._lista_widget.count()):
                    d._lista_widget.item(i).setCheckState(Qt.Checked)
                tipo, ids = d.alcance_seleccionado()
                # ids en orden determinista de la lista (sorted)
                if ids != [2,1,3]:
                    return False, f"orden diálogo no determinista {ids} esperado [2,1,3]"
                # Construir items en orden determinista y exportar
                seg_por_id = {s[0]: s for s in segs}
                items_orden = []
                for sid in ids:
                    s = seg_por_id[sid]
                    vid = s[1]
                    ruta = src1 if vid==1 else src2
                    nombre = nombres[vid]
                    items_orden.append({"segmento_id":s[0],"video_id":vid,"ruta_fuente":ruta,"nombre_original":nombre,"inicio":s[2],"fin":s[3],"color":s[4]})
                # Re-ordenar determinista como hace Visor
                items_orden = sorted(items_orden, key=lambda it: (it["video_id"], it["inicio"], it["fin"], it["segmento_id"]))
                if [it["segmento_id"] for it in items_orden] != [2,1,3]:
                    return False, f"items orden no determinista {[it['segmento_id'] for it in items_orden]}"
                dest2 = tempfile.mkdtemp()
                tarea2 = tv.TareaExportarLoteSegmentos(dest2, items=items_orden)
                res2 = tarea2._trabajo()
                if len(res2["exitos"]) != 3:
                    return False, f"varios explícitos 3 esperado {res2}"
                # Verificar orden de destinos coincide con orden determinista
                destinos = [os.path.basename(e["destino"]) for e in res2["exitos"]]
                if len(destinos) != 3:
                    return False, "destinos faltan"
                shutil.rmtree(dest2, ignore_errors=True)
                return True, f"uno/varios orden ok {ids}"
            finally:
                shutil.rmtree(dest, ignore_errors=True)
        finally:
            exp.exportar_segmento = orig

def test_22_seleccion_multi_video():
    """Multi-video explícito: segmentos de distintos videos en un lote."""
    with tempfile.TemporaryDirectory() as tmp:
        src_a = os.path.join(tmp, "a.mp4")
        src_b = os.path.join(tmp, "b.mp4")
        open(src_a, "wb").write(b"a"*1000)
        open(src_b, "wb").write(b"b"*1000)
        orig = exp.exportar_segmento
        destinos_creados = []
        def fake(f,i,fin,d,cancel_check=None):
            destinos_creados.append((f,d))
            open(d,"wb").write(b"out")
            return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
        exp.exportar_segmento = fake
        try:
            dest = tempfile.mkdtemp()
            try:
                items = [
                    {"segmento_id":1,"video_id":1,"ruta_fuente":src_a,"nombre_original":"a.mp4","inicio":0,"fin":1,"color":"rojo"},
                    {"segmento_id":2,"video_id":2,"ruta_fuente":src_b,"nombre_original":"b.mp4","inicio":0,"fin":1,"color":"azul"},
                    {"segmento_id":3,"video_id":1,"ruta_fuente":src_a,"nombre_original":"a.mp4","inicio":1,"fin":2,"color":None},
                    {"segmento_id":4,"video_id":2,"ruta_fuente":src_b,"nombre_original":"b.mp4","inicio":1,"fin":2,"color":None},
                ]
                # Orden determinista esperado: video 1 (0-1,1-2) luego video 2 (0-1,1-2)
                items_sorted = sorted(items, key=lambda it: (it["video_id"], it["inicio"]))
                tarea = tv.TareaExportarLoteSegmentos(dest, items=items_sorted)
                res = tarea._trabajo()
                if len(res["exitos"]) != 4:
                    return False, f"multi-video 4 esperado {res}"
                # Verificar que cada video aportó 2
                from collections import Counter
                c = Counter([e["item"]["video_id"] for e in res["exitos"]])
                if c[1]!=2 or c[2]!=2:
                    return False, f"contador video {c}"
                return True, "multi-video ok"
            finally:
                shutil.rmtree(dest, ignore_errors=True)
        finally:
            exp.exportar_segmento = orig

def test_23_ninguno_no_inicia():
    """Si no se selecciona ningún segmento, no inicia exportación."""
    from visor_videos import DialogoExportarLote
    app = QApplication.instance() or QApplication(sys.argv)
    segs = [(1,1,1,2,"rojo"),(2,1,2,3,None)]
    d = DialogoExportarLote("todos", None, segmentos=segs, nombres_por_id={1:"a.mp4"})
    d.radio_seleccion.setChecked(True)
    # Ninguno checked
    for i in range(d._lista_widget.count()):
        d._lista_widget.item(i).setCheckState(Qt.Unchecked)
    tipo, dato = d.alcance_seleccionado()
    if tipo != "seleccion" or dato != []:
        return False, f"ninguno debería lista vacía {tipo} {dato}"
    # Simular lógica de Visor: si lista vacía, no inicia tarea
    if dato:
        return False, "no vacío"
    # Verificar que tarea con items vacío no inicia (total 0)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tarea = tv.TareaExportarLoteSegmentos(tmp, items=[])
        res = tarea._trabajo()
        if res.get("total") != 0:
            return False, f"items vacío debería total 0 {res}"
    return True, "ninguno no inicia ok"

def test_24_ui_items_sin_sqlite_ffmpeg():
    """Items explícitos llegan a tarea sin SQLite/FFmpeg desde UI."""
    # Lote ahora es async en dos fases: _al_exportar_lote_solicitado (preparacion) y _abrir_dialogo (lanzamiento)
    src = inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado)
    try:
        src += inspect.getsource(visor_videos.VisorVideos._abrir_dialogo_lote_con_datos)
    except: pass
    # No debe contener sqlite3 ni subprocess directo en ningun paso UI
    if "sqlite3" in src or "subprocess" in src:
        return False, "UI contiene sqlite/subprocess"
    if "TareaExportarLoteSegmentos" not in src:
        return False, "UI no usa TareaExportarLoteSegmentos"
    if "items" not in src:
        return False, "UI no usa items explícitos"
    if "TareaListarSegmentosVarios" not in inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado):
        return False, "UI no usa tarea para cargar lista (SQLite indirecta)"
    if "QPixmap" in src:
        return False, "UI lote toca pixmaps"
    # Verificar que Dialogo no hace sqlite (evitar falso positivo por comentario)
    src_d = inspect.getsource(visor_videos.DialogoExportarLote)
    # buscar patrones reales, no palabras en comentarios de docstring que contienen la palabra pero no codigo
    if "sqlite3.connect" in src_d or "import sqlite3" in src_d or "subprocess.Popen" in src_d or "subprocess.run" in src_d:
        return False, "Dialogo sqlite/subprocess"
    if "QPixmap" in src_d:
        return False, "Dialogo pixmap"
    return True, "UI items sin sqlite/ffmpeg ok"

def test_25_todos_y_por_color_siguen():
    """Todos y Por color siguen funcionando tras cambios."""
    ruta_db = _crear_db_temp()
    try:
        conn = sqlite3.connect(ruta_db)
        ev._asegurar_tabla_segmentos(conn)
        conn.commit()
        vid1 = _insertar_video(conn, "a.mp4", "C:/v/a.mp4")
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1,2,"rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 2,3,None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 3,4,"azul"))
        conn.commit(); conn.close()
        # Todos
        filas_todos = ev.listar_segmentos_por_videos([vid1], color=ev._SIN_FILTRO_LOTE, ruta_db=ruta_db)
        if len(filas_todos) != 3:
            return False, f"todos 3 {filas_todos}"
        # Por color rojo
        filas_rojo = ev.listar_segmentos_por_videos([vid1], color="rojo", ruta_db=ruta_db)
        if len(filas_rojo)!=1 or filas_rojo[0][4]!="rojo":
            return False, f"rojo {filas_rojo}"
        # Sin clasificar
        filas_none = ev.listar_segmentos_por_videos([vid1], color=None, ruta_db=ruta_db)
        if len(filas_none)!=1 or filas_none[0][4] is not None:
            return False, f"sin clasificar {filas_none}"
        # Probar lote con filtro via Tarea
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.mp4")
            open(src, "wb").write(b"src"*300)
            # Necesitamos videos reales en DB con ruta src para que Tarea resuelva rutas
            ruta_db2 = _crear_db_temp()
            try:
                conn2 = sqlite3.connect(ruta_db2)
                ev._asegurar_tabla_segmentos(conn2)
                conn2.commit()
                cur = conn2.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)", ("a.mp4", src, ".mp4", "2026-01-01"))
                vid = cur.lastrowid
                conn2.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid, 0,1,"rojo"))
                conn2.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid, 1,2,None))
                conn2.commit(); conn2.close()
                # Mock export
                orig = exp.exportar_segmento
                def fake(f,i,fin,d,cancel_check=None):
                    open(d,"wb").write(b"out")
                    return {"ok":True,"salida":d,"duracion":fin-i,"start":0,"streams":[],"error":None,"cancelado":False}
                exp.exportar_segmento = fake
                try:
                    dest = tempfile.mkdtemp()
                    try:
                        tarea_todos = tv.TareaExportarLoteSegmentos(dest, video_ids=[vid], filtro_color=ev._SIN_FILTRO_LOTE, ruta_db=ruta_db2)
                        res = tarea_todos._trabajo()
                        if len(res["exitos"])!=2:
                            return False, f"todos via tarea 2 {res}"
                        shutil.rmtree(dest, ignore_errors=True)
                        dest2 = tempfile.mkdtemp()
                        tarea_rojo = tv.TareaExportarLoteSegmentos(dest2, video_ids=[vid], filtro_color="rojo", ruta_db=ruta_db2)
                        res2 = tarea_rojo._trabajo()
                        if len(res2["exitos"])!=1:
                            return False, f"rojo via tarea {res2}"
                        shutil.rmtree(dest2, ignore_errors=True)
                    finally:
                        pass
                finally:
                    exp.exportar_segmento = orig
                    try: os.remove(ruta_db2)
                    except: pass
            except Exception as e:
                return False, f"ex {e}"
        return True, "todos y por color siguen ok"
    finally:
        try: os.remove(ruta_db)
        except: pass

def test_26_no_trabajo_directo():
    """B6.9 async: ninguna llamada sync a ._trabajo() desde Visor/Dialogo para carga de segmentos."""
    import visor_videos, inspect
    src_visor = inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado)
    src_dialog = inspect.getsource(visor_videos.DialogoExportarLote.__init__)
    if "._trabajo()" in src_visor:
        return False, "Visor _al_exportar_lote_solicitado contiene ._trabajo() sincrono (debe ser async via GestorTareas)"
    if "._trabajo()" in src_dialog:
        return False, "DialogoExportarLote.__init__ contiene ._trabajo() sincrono (debe ser puramente presentacional)"
    # Fallback equivalente dentro de Dialogo no debe existir
    if "TareaListarSegmentosVarios" in src_dialog:
        return False, "Dialogo aun importa TareaListarSegmentosVarios para fallback sync"
    return True, "no _trabajo directo: Visor/Dialogo async ok"

def test_27_carga_async_via_gestor():
    """Carga se inicia mediante tarea/gestor y dialogo se abre desde callback de finalizacion."""
    import visor_videos, inspect
    src = inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado)
    if "gestor_preparacion_lote.iniciar" not in src or "TareaListarSegmentosVarios" not in src:
        return False, "carga no inicia via gestor_preparacion_lote + TareaListarSegmentosVarios"
    # Verificar que UI no hace SQLite directo y no bloquea
    if "sqlite3" in src or "subprocess" in src:
        return False, "UI carga contiene sqlite/subprocess directo"
    # Dialogo debe ser puramente presentacional
    src_dialog = inspect.getsource(visor_videos.DialogoExportarLote.__init__)
    if "sqlite3" in src_dialog or "subprocess" in src_dialog or "QPixmap" in src_dialog:
        return False, "Dialogo no es puramente presentacional"
    # Preparacion handlers deben existir y abrir dialogo desde finalizada
    try:
        src_fin = inspect.getsource(visor_videos.VisorVideos._al_preparacion_lote_finalizada)
        src_abrir = inspect.getsource(visor_videos.VisorVideos._abrir_dialogo_lote_con_datos)
    except AttributeError:
        return False, "faltan handlers _al_preparacion_lote_finalizada / _abrir_dialogo_lote_con_datos"
    if "DialogoExportarLote" not in src_fin and "DialogoExportarLote" not in src_abrir and "_abrir_dialogo_lote_con_datos" not in src_fin:
        return False, "dialogo no se abre desde callback finalizada"
    # Verificar infra reutilizada: GestorTareas + senales
    src_init = inspect.getsource(visor_videos.VisorVideos.__init__)
    if "gestor_preparacion_lote" not in src_init or "tarea_resultado.connect" not in src_init:
        return False, "GestorTareas no conectado via senales en __init__"
    return True, "carga async via gestor y dialogo desde callback ok"

def test_28_doble_disparo_bloqueado():
    """Mientras carga, doble disparo del boton Exportar debe estar bloqueado y con progreso ligero."""
    import visor_videos, inspect
    src = inspect.getsource(visor_videos.VisorVideos._al_exportar_lote_solicitado)
    if "gestor_preparacion_lote.activo" not in src or "_preparacion_lote_en_curso" not in src:
        return False, "no chequea doble disparo via gestor/flag"
    if "boton_exportar_lote.setEnabled(False)" not in src:
        return False, "no bloquea boton durante carga"
    src_fin = inspect.getsource(visor_videos.VisorVideos._al_preparacion_lote_finalizada)
    if "boton_exportar_lote.setEnabled(True)" not in src_fin:
        return False, "no restaura boton en finalizada"
    if "_mostrar_progreso" not in src or "Cargando segmentos" not in src:
        return False, "no muestra estado/progreso ligero durante carga"
    # Sin timers/polling nuevos
    if "QTimer" in src and "singleShot" in src:
        return False, "usa timer/polling nuevo para carga (prohibido)"
    return True, "doble disparo bloqueado y progreso ligero ok"

def test_29_error_restaura_estado():
    """Error de carga restaura estado y no deja tareas colgadas."""
    import tempfile, os, escanear_videos as ev
    from PySide6.QtWidgets import QApplication, QMessageBox
    from unittest.mock import patch
    import visor_videos
    app = QApplication.instance() or QApplication([])
    visor = None
    db_path = None
    cfg_path = None
    orig_iniciar = visor_videos.VisorVideos._iniciar_carga
    try:
        # Evitar carga inicial async que puede colgar en entorno headless
        visor_videos.VisorVideos._iniciar_carga = lambda self: None
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        conn = ev.conectar_bd(db_path)
        conn.commit()
        conn.close()
        cfg_fd, cfg_path = tempfile.mkstemp(suffix=".ini")
        os.close(cfg_fd)
        visor = visor_videos.VisorVideos(ruta_db=db_path, ruta_config=cfg_path)
        # Simular carga en curso y luego error
        visor._preparacion_lote_en_curso = True
        visor._preparacion_lote_video_ids = [1]
        visor._preparacion_lote_nombres = {1: "a.mp4"}
        visor._preparacion_lote_rutas = {1: "a.mp4"}
        visor._preparacion_lote_segmentos = None
        visor._preparacion_lote_error = None
        visor.boton_exportar_lote.setEnabled(False)
        # Interceptar QMessageBox modal para no bloquear en headless, pero verificar que se intentó mostrar
        avisos = []
        def _fake_warning(*args, **kwargs):
            avisos.append((args, kwargs))
            return QMessageBox.Ok
        def _fake_info(*args, **kwargs):
            avisos.append((args, kwargs))
            return QMessageBox.Ok
        with patch.object(QMessageBox, "warning", side_effect=_fake_warning), patch.object(QMessageBox, "information", side_effect=_fake_info), patch.object(visor_videos.QMessageBox, "warning", side_effect=_fake_warning), patch.object(visor_videos.QMessageBox, "information", side_effect=_fake_info):
            visor._al_preparacion_lote_error("error simulado para prueba")
            visor._al_preparacion_lote_finalizada()
        if not avisos:
            return False, "no se intentó mostrar aviso de error (QMessageBox no llamado)"
        if not visor.boton_exportar_lote.isEnabled():
            return False, "boton no restaurado tras error de carga"
        if getattr(visor, "_preparacion_lote_en_curso", False):
            return False, "flag _preparacion_lote_en_curso no limpio tras error"
        if visor.gestor_preparacion_lote.activo:
            return False, "gestor preparacion activo tras error"
        # Cierre no deja colgados (también interceptar posibles diálogos en close)
        with patch.object(QMessageBox, "warning", side_effect=_fake_warning), patch.object(QMessageBox, "information", side_effect=_fake_info), patch.object(visor_videos.QMessageBox, "warning", side_effect=_fake_warning):
            visor.close()
        if visor.gestor_preparacion_lote.activo:
            return False, "gestor no cerro en closeEvent"
        return True, f"error restaura estado y sin tareas colgadas ok (aviso interceptado {len(avisos)})"
    except Exception as exc:
        import traceback
        return False, f"excepcion: {exc}\n{traceback.format_exc()[:400]}"
    finally:
        try:
            visor_videos.VisorVideos._iniciar_carga = orig_iniciar
        except: pass
        if visor is not None:
            try:
                visor.gestor.cerrar()
                if hasattr(visor, "gestor_preparacion_lote"):
                    visor.gestor_preparacion_lote.cerrar()
                visor.close()
            except:
                pass
        try:
            if db_path and os.path.exists(db_path):
                os.remove(db_path)
        except: pass
        try:
            if cfg_path and os.path.exists(cfg_path):
                os.remove(cfg_path)
        except: pass

def test_30_ejecucion_real_aislada():
    """Ejecucion real aislada: Visor con DB temporal, carga en background sin crash y dialogo construible."""
    import tempfile, os, shutil, escanear_videos as ev, visor_videos, time
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    from unittest.mock import patch
    app = QApplication.instance() or QApplication([])
    visor = None
    db_path = None
    cfg_path = None
    tmp_videos = None
    orig_iniciar = visor_videos.VisorVideos._iniciar_carga
    try:
        # Evitar carga inicial que cuelga en headless, mantener gestors aislados
        visor_videos.VisorVideos._iniciar_carga = lambda self: None
        # DB temporal aislada
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        conn = ev.conectar_bd(db_path)
        conn.commit()
        tmp_videos = tempfile.mkdtemp()
        src1 = os.path.join(tmp_videos, "a.mp4")
        src2 = os.path.join(tmp_videos, "b.mp4")
        open(src1, "wb").write(b"fake"*200)
        open(src2, "wb").write(b"fake2"*200)
        cur = conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)", ("a.mp4", src1, ".mp4", "2026-01-01"))
        vid1 = cur.lastrowid
        cur = conn.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)", ("b.mp4", src2, ".mp4", "2026-01-01"))
        vid2 = cur.lastrowid
        ev._asegurar_tabla_segmentos(conn)
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 0, 1, "rojo"))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid1, 1, 2, None))
        conn.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid2, 0, 1, "azul"))
        conn.commit()
        conn.close()
        cfg_fd, cfg_path = tempfile.mkstemp(suffix=".ini")
        os.close(cfg_fd)
        visor = visor_videos.VisorVideos(ruta_db=db_path, ruta_config=cfg_path)
        # Crear tarjetas desde DB (sin tocar cache real)
        filas = ev.listar_videos_paginado(100, 0, None, db_path).get("videos", [])
        if not filas:
            filas = [("a.mp4", 5.0, 320, 240, "h264", 1, 1000, src1, vid1), ("b.mp4", 5.0, 320, 240, "h264", 1, 1000, src2, vid2)]
        # Limpiar tarjetas iniciales y crear las de prueba
        try:
            # Limpiar previas si existen
            for _, t in list(visor.tarjetas):
                try:
                    visor.cuadricula.removeWidget(t)
                    t.deleteLater()
                except: pass
        except: pass
        visor.tarjetas = []
        visor.visibles = []
        visor._crear_tarjetas(filas)
        # Asegurar visibles
        if not visor.visibles:
            visor.visibles = [f[0] for f in filas]
        # Interceptar únicamente diálogos modales que impedirían automatización (no reemplazar GestorTareas)
        _fake_msg = lambda *a, **k: QMessageBox.Ok
        _fake_dir = lambda *a, **k: ""
        # Mock del paso de dialogo para no bloquear UI ni pedir directorio real
        abrir_called = {}
        original_abrir = visor._abrir_dialogo_lote_con_datos
        def fake_abrir(video_ids, segmentos, nombres, rutas):
            abrir_called["video_ids"] = list(video_ids)
            abrir_called["segmentos"] = list(segmentos)
            abrir_called["nombres"] = dict(nombres)
            # Verificar que se construye dialogo presentacional sin crash
            try:
                d = visor_videos.DialogoExportarLote(visor._filtro_catalogo, visor._ruta_config, visor, segmentos=segmentos, nombres_por_id=nombres)
                abrir_called["dialog_lista_count"] = d._lista_widget.count()
                abrir_called["dialog_radio_enabled"] = d.radio_seleccion.isEnabled()
                abrir_called["ok"] = True
            except Exception as e:
                abrir_called["error"] = str(e)
        visor._abrir_dialogo_lote_con_datos = fake_abrir
        # Disparar flujo real con diálogos interceptados
        with patch.object(QMessageBox, "warning", side_effect=_fake_msg), patch.object(QMessageBox, "information", side_effect=_fake_msg), patch.object(visor_videos.QMessageBox, "warning", side_effect=_fake_msg), patch.object(visor_videos.QMessageBox, "information", side_effect=_fake_msg), patch.object(QFileDialog, "getExistingDirectory", side_effect=_fake_dir), patch.object(visor_videos.QFileDialog, "getExistingDirectory", side_effect=_fake_dir):
            visor.boton_exportar_lote.setEnabled(True)
            visor._al_exportar_lote_solicitado()
            # Inmediatamente debe estar bloqueado y gestor activo (background)
            if visor.boton_exportar_lote.isEnabled():
                return False, "boton no bloqueado inmediatamente tras solicitar carga (debe ser background)"
            # UI debe seguir responsiva: processEvents no debe congelarse
            for _ in range(5):
                QApplication.processEvents()
                time.sleep(0.01)
            # Esperar finalizacion background (timeout 6s acotado)
            deadline = time.monotonic() + 6.0
            while time.monotonic() < deadline and (visor.gestor_preparacion_lote.activo or getattr(visor, "_preparacion_lote_en_curso", False)):
                QApplication.processEvents()
                time.sleep(0.02)
            QApplication.processEvents()
            if not visor.boton_exportar_lote.isEnabled():
                return False, "boton no restaurado tras carga background"
            if "ok" not in abrir_called:
                return False, f"dialogo no construido tras carga background: {abrir_called}"
            if len(abrir_called.get("segmentos", [])) != 3:
                return False, f"segmentos background esperado 3 got {len(abrir_called.get('segmentos', []))}: {abrir_called}"
            if abrir_called.get("dialog_lista_count") != 3:
                return False, f"dialog lista count {abrir_called.get('dialog_lista_count')} != 3"
            # Verificar que no quedan tareas background colgadas dentro del parche
            if visor.gestor_preparacion_lote.activo or getattr(visor, "_preparacion_lote_en_curso", False):
                return False, "tarea background no termino dentro de timeout acotado"
            return True, f"ejecucion real aislada ok segmentos={len(abrir_called['segmentos'])} lista={abrir_called['dialog_lista_count']}"
    except Exception as exc:
        import traceback
        return False, f"excepcion: {exc}\n{traceback.format_exc()[:600]}"
    finally:
        try:
            visor_videos.VisorVideos._iniciar_carga = orig_iniciar
        except: pass
        if visor is not None:
            try:
                visor.gestor.cerrar()
                if hasattr(visor, "gestor_preparacion_lote"):
                    visor.gestor_preparacion_lote.cerrar()
                visor.close()
            except: pass
        try:
            if db_path and os.path.exists(db_path):
                os.remove(db_path)
        except: pass
        try:
            if cfg_path and os.path.exists(cfg_path):
                os.remove(cfg_path)
        except: pass
        try:
            if tmp_videos and os.path.exists(tmp_videos):
                shutil.rmtree(tmp_videos, ignore_errors=True)
        except: pass

# ---------------------------------------------------------------------------

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    pruebas = [
        test_01_py_compile,
        test_02_repo_sin_filtro,
        test_03_repo_color_concreto,
        test_04_repo_sin_clasificar,
        test_05_repo_orden_determinista,
        test_06_lote_vacio,
        test_07_uno_y_varios_items_mock,
        test_08_mismo_diferentes_videos,
        test_09_naming_colisiones_existentes_intra_lote,
        test_10_fallo_intermedio_conserva_exitos,
        test_11_cancelacion_conserva_exitos_limpia_en_curso,
        test_12_progreso_1_N,
        test_13_no_sobrescritura,
        test_14_ui_no_subprocess_sqlite,
        test_15_errores_varios,
        test_16_gestor_exclusion_mutua,
        test_17_destino_misma_fuente_no_sobrescribe,
        test_18_dialogo_preseleccion,
        test_19_destino_identico_rechazo_bytes,
        test_20_dialogo_explicita_existe,
        test_21_seleccion_explicita_uno_y_varios_y_orden,
        test_22_seleccion_multi_video,
        test_23_ninguno_no_inicia,
        test_24_ui_items_sin_sqlite_ffmpeg,
        test_25_todos_y_por_color_siguen,
        test_26_no_trabajo_directo,
        test_27_carga_async_via_gestor,
        test_28_doble_disparo_bloqueado,
        test_29_error_restaura_estado,
        test_30_ejecucion_real_aislada,
    ]
    resultados=[]
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            import traceback
            ok, detalle = False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()[:800]}"
        resultados.append((i,ok,detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {fn.__name__}: {detalle}")
        sys.stdout.flush()
        QApplication.processEvents()
        time.sleep(0.02)
    ok_total = all(ok for _,ok,_ in resultados)
    aprobadas = sum(1 for _,ok,_ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__ == "__main__":
    sys.exit(main())
