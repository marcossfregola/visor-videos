import os
import sqlite3
import tempfile
import time
import threading

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor

import escanear_videos as es
import visor_videos
from escanear_videos import configurar_cantidad_previews
from visor_videos import VisorVideos

def _png(ruta):
    img = QImage(40,30, QImage.Format_RGB32)
    img.fill(QColor("green"))
    img.save(ruta, "PNG")

def _fila_db(nombre, dur, carpeta):
    return (nombre, os.path.join(carpeta, nombre), os.path.splitext(nombre)[1].lower(), "2026-08-03T00:00:00", dur, 1920,1080,"h264",1,1024)

def _esperar(pred, timeout_ms=8000):
    fin=time.time()+timeout_ms/1000
    while time.time()<fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    return pred()

def test_01_secuenciacion_diferidos():
    """Secuenciación legacy/previews con bloqueo controlado.
    - Bloquea migración para vid 1, solicita previews 3->5 durante vuelo.
    - Verifica diferida, no inicia preview mientras migra, al liberar arranca exactamente una vez,
      destinos no vacíos, legacy permanece, no tmp huérfano, sin FFmpeg duplicado si legacy ya aporta.
    """
    app = QApplication.instance() or QApplication([])
    mini = tempfile.TemporaryDirectory()
    videos = tempfile.TemporaryDirectory()
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "catalogo.db")
    ruta_config = os.path.join(tmp.name, "config.json")
    # DB con 1 video clip.mp4 + 2 extras para no interferir
    conn = sqlite3.connect(ruta_db)
    conn.execute("""CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, duracion_segundos REAL, ancho INTEGER, alto INTEGER, codec_video TEXT, cantidad_miniaturas INTEGER, tamano_bytes INTEGER)""")
    conn.executemany("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas,tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     [_fila_db("clip.mp4", 100.0, videos.name), _fila_db("extra_00.mp4", 100.0, videos.name)])
    conn.commit(); conn.close()
    # legacy cache: clip con 3 previews (para 3) y extra con 3
    orig_mini_es = es.ruta_carpeta_miniaturas
    orig_mini_vi = visor_videos.ruta_carpeta_miniaturas
    es.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    for i in range(1,4):
        _png(os.path.join(mini.name, f"clip_preview_{i:02d}.jpg"))
        _png(os.path.join(mini.name, f"extra_00_preview_{i:02d}.jpg"))
        _png(os.path.join(mini.name, f"clip_{i:02d}.jpg"))
        _png(os.path.join(mini.name, f"extra_00_{i:02d}.jpg"))
    open(os.path.join(videos.name, "clip.mp4"), "wb").write(b"video")
    open(os.path.join(videos.name, "extra_00.mp4"), "wb").write(b"video")
    #Cantidad inicial 3
    configurar_cantidad_previews(3)
    # Bloquear migración para vid 1
    import tareas_videos as tv
    orig_migrar = es.migrar_cache_legacy_a_id
    orig_migrar_tv = tv.migrar_cache_legacy_a_id
    bloqueo = threading.Event()
    started = threading.Event()
    def migrar_bloqueada(vid, nombre):
        if vid == 1:
            started.set()
            # esperar hasta que test libere (con timeout para no colgar)
            bloqueo.wait(timeout=10)
        return orig_migrar(vid, nombre)
    es.migrar_cache_legacy_a_id = migrar_bloqueada
    tv.migrar_cache_legacy_a_id = migrar_bloqueada
    # Espiar generar_preview para contar FFmpeg
    orig_gen = es.generar_preview
    llamadas = []
    def gen_spy(ruta_video, destino, indice=None, duracion_segundos=None):
        llamadas.append(indice)
        img = QImage(40,30, QImage.Format_RGB32)
        img.fill(QColor("green"))
        img.save(destino, "PNG")
        return True
    es.generar_preview = gen_spy
    # Crear visor
    ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
    ventana.resize(900,600)
    ventana.show()
    try:
        # esperar carga pero migración para vid 1 quedará bloqueada
        _esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None, timeout_ms=5000)
        # esperar que migración haya empezado y esté bloqueada
        ok_started = _esperar(lambda: started.is_set(), timeout_ms=3000)
        if not ok_started:
            print("P01 FALLO - migración no empezó bloqueada")
            return False, "migración no bloqueada"
        # Verificar que vid 1 está en vuelo
        if 1 not in getattr(ventana, "_migracion_ids_en_vuelo", set()):
            print("P01 FALLO - vid 1 no en vuelo")
            return False, "vid 1 no en vuelo"
        # Solicitar previews 3->5 durante migración en vuelo
        configurar_cantidad_previews(5)
        # Simular cambio de combo: ajustar_previews y encolar
        for _, tarjeta in ventana.tarjetas:
            if getattr(tarjeta, "_video_id", None) == 1:
                tarjeta.ajustar_previews(5)
        # Encolar previews para todos (como hace _al_cambiar_cantidad_previews)
        ventana._encolar_previews_por_id([1,2])
        QApplication.processEvents()
        # Verificar diferida: vid 1 debe estar en _previews_diferidas y en _cola_previews, pero no debe haber iniciado preview para vid 1
        diferidas = getattr(ventana, "_previews_diferidas", set())
        cola = getattr(ventana, "_cola_previews", [])
        cola_ids = [c[0] for c in cola]
        if 1 not in diferidas:
            print(f"P01 FALLO - vid 1 no en diferidas {diferidas}")
            return False, f"vid 1 no en diferidas {diferidas}"
        if 1 not in cola_ids:
            print(f"P01 FALLO - vid 1 no en cola {cola_ids}")
            return False, f"vid 1 no en cola {cola_ids}"
        # Verificar que no arrancó preview para vid 1 mientras migra
        # gestor_previews no debe tener tarea activa para vid 1 (si hay tarea, no debe incluir vid 1)
        if ventana.gestor_previews.activo:
            tarea = getattr(ventana, "tarea_previews", None)
            vids_act = getattr(tarea, "_video_ids", []) if tarea else []
            if 1 in vids_act:
                print(f"P01 FALLO - preview para vid 1 arrancó durante migración {vids_act}")
                return False, f"preview arrancó durante migración {vids_act}"
        # Ahora liberar migración
        llamadas.clear()
        bloqueo.set()
        # Esperar que migración termine y previews se generen
        _esperar(lambda: not ventana.gestor_migracion.activo and not ventana._migracion_ids_en_vuelo, timeout_ms=5000)
        # Esperar previews (incluye diferidos)
        _esperar(lambda: not ventana.gestor_previews.activo and not ventana._cola_previews and not getattr(ventana, "_previews_diferidas", set()), timeout_ms=8000)
        # Verificar destinos finales no vacíos
        from escanear_videos import ruta_preview_id, ruta_miniatura_id
        for idx in [4,5]:
            ruta = ruta_preview_id(1, idx)
            if not os.path.isfile(ruta) or os.path.getsize(ruta)==0:
                print(f"P01 FALLO - destino {ruta} vacío")
                return False, f"destino {ruta} vacío"
        # Verificar legacy permanece
        for i in range(1,4):
            leg = os.path.join(mini.name, f"clip_preview_{i:02d}.jpg")
            if not os.path.isfile(leg):
                print(f"P01 FALLO - legacy {leg} no permanece")
                return False, f"legacy {leg} no permanece"
        # Verificar no tmp huérfano
        for name in os.listdir(mini.name):
            if name.startswith("tmp_mig_v1_"):
                print(f"P01 FALLO - tmp huérfano {name}")
                return False, f"tmp huérfano {name}"
        # Verificar que solo se generaron los faltantes (4,5) y no duplicado
        # Como legacy aportaba 3, al pasar a 5 solo 4,5 deben generarse
        # Pero si legacy ya aportaba 3, y migración copió 3, luego preview genera 4,5 => llamadas [4,5]
        # Si hay extra_00, también podría generar, pero extra_00 ya tiene 3 y también necesita 4,5 si cantidad 5
        # Filtrar solo para vid 1: llamadas para vid 1 deberían ser [4,5]
        # Nuestro spy cuenta global, para clip y extra_00 ambos necesitan 4,5 => 4 llamadas
        # Verificar que no se regeneraron 1,2,3
        if sorted([c for c in llamadas if c in [1,2,3]]):
            print(f"P01 FALLO - se regeneraron existentes {llamadas}")
            return False, f"se regeneraron {llamadas}"
        # Verificar que al menos 4,5 están en llamadas (puede haber 4 llamadas para 2 videos)
        if 4 not in llamadas or 5 not in llamadas:
            print(f"P01 FALLO - faltan 4,5 en {llamadas}")
            return False, f"faltan 4,5 en {llamadas}"
        # Verificar que preview se arrancó exactamente una vez para vid 1 (no doble dispatch)
        # Contar cuántas veces se inició tarea con vid 1: ya verificamos que no arrancó durante migración,
        # y después solo una vez. Podemos verificar que no hay duplicados en cola.
        # Si hubiera doble dispatch, llamadas tendría duplicados >2 por video
        # Para clip, llamadas para 4,5 debe ser 1 cada uno, no duplicado
        # Como tenemos 2 videos, cada uno 2 llamadas => total 4, si duplicado sería 8
        if len([c for c in llamadas if c in [4,5]]) > 4:
            print(f"P01 FALLO - doble dispatch {llamadas}")
            return False, f"doble dispatch {llamadas}"
        # Verificar que si legacy ya aporta (caso 3 previews), no hay FFmpeg duplicado innecesario para 1,2,3
        # Ya verificamos que no se regeneraron 1,2,3, y que 4,5 son los únicos
        print("P01 OK - secuenciación diferida correcta")
        return True, "ok"
    finally:
        # liberar bloqueo por si quedó
        bloqueo.set()
        ventana.close()
        ventana.gestor.cerrar()
        if getattr(ventana, "gestor_previews", None):
            ventana.gestor_previews.cerrar()
        if getattr(ventana, "gestor_migracion", None):
            ventana.gestor_migracion.cerrar()
        es.ruta_carpeta_miniaturas = orig_mini_es
        visor_videos.ruta_carpeta_miniaturas = orig_mini_vi
        es.migrar_cache_legacy_a_id = orig_migrar
        try:
            import tareas_videos as tv4
            tv4.migrar_cache_legacy_a_id = orig_migrar_tv
            tv4.escanear_mod.generar_preview = orig_gen
        except Exception:
            pass
        es.generar_preview = orig_gen
        configurar_cantidad_previews(3)
        mini.cleanup()
        videos.cleanup()
        tmp.cleanup()
        QApplication.processEvents()

def test_02_tres_a_cinco_a_siete():
    """3->5 y luego 5->7 mientras migra debe generar faltantes vigentes (no fijada a vieja)."""
    app = QApplication.instance() or QApplication([])
    mini = tempfile.TemporaryDirectory()
    videos = tempfile.TemporaryDirectory()
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "catalogo.db")
    ruta_config = os.path.join(tmp.name, "config.json")
    conn = sqlite3.connect(ruta_db)
    conn.execute("""CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, ruta TEXT NOT NULL, extension TEXT NOT NULL, fecha_importacion TEXT NOT NULL, duracion_segundos REAL, ancho INTEGER, alto INTEGER, codec_video TEXT, cantidad_miniaturas INTEGER, tamano_bytes INTEGER)""")
    conn.executemany("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas,tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     [_fila_db("clip.mp4", 100.0, videos.name)])
    conn.commit(); conn.close()
    orig_mini_es = es.ruta_carpeta_miniaturas
    orig_mini_vi = visor_videos.ruta_carpeta_miniaturas
    es.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    for i in range(1,4):
        _png(os.path.join(mini.name, f"clip_preview_{i:02d}.jpg"))
    open(os.path.join(videos.name, "clip.mp4"), "wb").write(b"video")
    configurar_cantidad_previews(3)
    import tareas_videos as tv2
    orig_migrar = es.migrar_cache_legacy_a_id
    orig_migrar_tv2 = tv2.migrar_cache_legacy_a_id
    bloqueo = threading.Event()
    started = threading.Event()
    def migrar_bloqueada(vid, nombre):
        if vid == 1:
            started.set()
            bloqueo.wait(timeout=10)
        return orig_migrar(vid, nombre)
    es.migrar_cache_legacy_a_id = migrar_bloqueada
    tv2.migrar_cache_legacy_a_id = migrar_bloqueada
    orig_gen = es.generar_preview
    llamadas = []
    def gen_spy(ruta_video, destino, indice=None, duracion_segundos=None):
        llamadas.append(indice)
        img = QImage(40,30, QImage.Format_RGB32)
        img.fill(QColor("green"))
        img.save(destino, "PNG")
        return True
    es.generar_preview = gen_spy
    try:
        tv2.escanear_mod.generar_preview = gen_spy
    except Exception:
        pass
    ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
    ventana.resize(900,600)
    ventana.show()
    try:
        _esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None, timeout_ms=5000)
        _esperar(lambda: started.is_set(), timeout_ms=3000)
        # 3->5
        configurar_cantidad_previews(5)
        for _, t in ventana.tarjetas:
            if getattr(t, "_video_id", None)==1:
                t.ajustar_previews(5)
        ventana._encolar_previews_por_id([1])
        # inmediatamente 5->7
        configurar_cantidad_previews(7)
        for _, t in ventana.tarjetas:
            if getattr(t, "_video_id", None)==1:
                t.ajustar_previews(7)
        ventana._encolar_previews_por_id([1])
        QApplication.processEvents()
        # verificar que sigue diferida y solo una entrada (deduplicada)
        diferidas = getattr(ventana, "_previews_diferidas", set())
        if 1 not in diferidas:
            print("P02 FALLO - vid 1 no en diferidas tras 3->5->7")
            return False, "no diferida"
        # liberar
        llamadas.clear()
        bloqueo.set()
        _esperar(lambda: not ventana.gestor_migracion.activo and not ventana._migracion_ids_en_vuelo, timeout_ms=5000)
        _esperar(lambda: not ventana.gestor_previews.activo and not ventana._cola_previews and not getattr(ventana, "_previews_diferidas", set()), timeout_ms=8000)
        # debe haber generado 4,5,6,7 (faltantes vigentes para 7, ya que 3->5->7)
        # Como 3 ya existían via legacy, faltan 4,5,6,7
        if sorted(llamadas) != [4,5,6,7]:
            print(f"P02 FALLO - llamadas {sorted(llamadas)} esperado [4,5,6,7]")
            return False, f"llamadas {sorted(llamadas)}"
        print("P02 OK - 3->5->7 genera faltantes vigentes")
        return True, "ok"
    finally:
        bloqueo.set()
        ventana.close()
        ventana.gestor.cerrar()
        if getattr(ventana, "gestor_previews", None):
            ventana.gestor_previews.cerrar()
        if getattr(ventana, "gestor_migracion", None):
            ventana.gestor_migracion.cerrar()
        es.ruta_carpeta_miniaturas = orig_mini_es
        visor_videos.ruta_carpeta_miniaturas = orig_mini_vi
        es.migrar_cache_legacy_a_id = orig_migrar
        try:
            import tareas_videos as tv3
            tv3.migrar_cache_legacy_a_id = orig_migrar_tv2
            tv3.escanear_mod.generar_preview = orig_gen
        except Exception:
            pass
        es.generar_preview = orig_gen
        configurar_cantidad_previews(3)
        mini.cleanup()
        videos.cleanup()
        tmp.cleanup()
        QApplication.processEvents()

def main():
    app = QApplication.instance() or QApplication([])
    resultados=[]
    for fn in [test_01_secuenciacion_diferidos, test_02_tres_a_cinco_a_siete]:
        try:
            ok, detalle = fn()
        except Exception as exc:
            import traceback
            ok, detalle = False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        resultados.append(ok)
        print(f"{'OK' if ok else 'FALLO'} - {detalle}")
    total = sum(resultados)
    print(f"TOTAL={total}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total==len(resultados) else 'FALLO'}")
    return 0 if total==len(resultados) else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
