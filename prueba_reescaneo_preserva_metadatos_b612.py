"""
Prueba regresion B6.12 reescaneo preserva marcadores/segmentos e IDs.

Usa APIs productivas exactas: conectar_bd, preparar_registros_basicos,
combinar_registros_con_ffprobe/_miniaturas/_tamanos, guardar_videos,
guardar_marcador/segmento, listar_*, detectar_diferencias,
preparar_plan_sincronizacion, aplicar_incorporaciones, eliminar_candidatos,
integrity_check. No FFmpeg real necesario: registros sinteticos que representan
resultado del escaneo.

Base: C:\\prueba\\_tmp_b612_reescaneo\\biblioteca_test.db + carpeta videos temporal.
"""
import os
import sys
import shutil
import sqlite3
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_ROOT = os.path.join(BASE_DIR, "_tmp_b612_reescaneo")
DB_PATH = os.path.join(TMP_ROOT, "biblioteca_test.db")
VIDEOS_DIR = os.path.join(TMP_ROOT, "videos")

# Asegurar imports productivos
sys.path.insert(0, BASE_DIR)
import escanear_videos as ev

def _limpiar():
    if os.path.exists(TMP_ROOT):
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)

def _crear_archivo(nombre, size=1024):
    ruta = os.path.join(VIDEOS_DIR, nombre)
    # crear archivo dummy para que stat funcione
    with open(ruta, "wb") as f:
        f.write(b"\x00" * size)
    return ruta

def _ids_por_nombre(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        filas = conn.execute("SELECT id, nombre FROM videos ORDER BY nombre").fetchall()
        return {nombre: vid for vid, nombre in filas}
    finally:
        conn.close()

def _dump_videos(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT id, nombre, ruta, tamano_bytes, mtime_ns FROM videos ORDER BY nombre").fetchall()
    finally:
        conn.close()

def _dump_marcadores(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT id, video_id, tiempo, color FROM marcadores_video ORDER BY video_id, tiempo, id").fetchall()
    finally:
        conn.close()

def _dump_segmentos(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute("SELECT id, video_id, inicio, fin, color FROM segmentos_video ORDER BY video_id, inicio, id").fetchall()
    finally:
        conn.close()

def _integrity(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def _crear_esquema():
    # API productiva
    conn = ev.conectar_bd(DB_PATH)
    conn.commit()
    conn.close()
    assert os.path.isfile(DB_PATH), "No se creo DB"

def test_base():
    print("=== ESCENARIO BASE: reescaneo preserva IDs y marcadores/segmentos ===")
    _limpiar()
    _crear_esquema()
    # Crear archivos fisicos A,B,C
    for n in ["A.mp4","B.mp4","C.mp4"]:
        _crear_archivo(n, size=1024)

    # 2) guardar A,B,C con APIs productivas (mismo orden que _iniciar_guardado)
    vids = ["A.mp4","B.mp4","C.mp4"]
    res_tam = ev.obtener_tamanos_archivos(vids, VIDEOS_DIR)
    registros = ev.combinar_registros_con_ffprobe(vids, VIDEOS_DIR, {"resultados":[]})
    registros = ev.combinar_registros_con_miniaturas(registros, {"resultados":[]})
    registros = ev.combinar_registros_con_tamanos(registros, res_tam)
    res_guardado = ev.guardar_videos(registros, DB_PATH)
    assert res_guardado["guardados"] == 3, f"guardados {res_guardado}"
    ids_antes = _ids_por_nombre(DB_PATH)
    idA, idB, idC = ids_antes["A.mp4"], ids_antes["B.mp4"], ids_antes["C.mp4"]
    print(f"IDs iniciales: A={idA} B={idB} C={idC}")
    print(f"videos antes: {_dump_videos(DB_PATH)}")

    # 3) crear marcadores y segmentos repartidos A/B con colores
    m1 = ev.guardar_marcador(idA, 10.5, DB_PATH, color="rojo")
    m2 = ev.guardar_marcador(idA, 20.0, DB_PATH, color="azul")
    m3 = ev.guardar_marcador(idB, 5.0, DB_PATH, color="verde")
    # necesitamos al menos 2 marcadores y 2 segmentos repartidos en A/B incluyendo colores
    # Ya tenemos 3 marcadores; para cumplir minimo 2 marcados vamos bien
    s1 = ev.guardar_segmento(idA, 1.0, 2.5, DB_PATH, color="amarillo")
    s2 = ev.guardar_segmento(idB, 3.0, 7.0, DB_PATH, color="violeta")
    marc_antes = _dump_marcadores(DB_PATH)
    seg_antes = _dump_segmentos(DB_PATH)
    print(f"marcadores antes: {marc_antes}")
    print(f"segmentos antes: {seg_antes}")
    assert len(marc_antes) >= 2, "faltan marcadores"
    assert len(seg_antes) >= 2, "faltan segmentos"

    # Capturar filas exactas e IDs
    videos_antes = _dump_videos(DB_PATH)

    # 5) simular segundo escaneo donde A/B/C siguen y aparece D nuevo
    _crear_archivo("D.mp4", size=2048)
    # El pipeline productivo guarda TODOS los detectados (A,B,C,D) via guardar_videos
    # y luego sincroniza. Verificamos ambas vias.

    # Via 1: guardar_videos con todos (como hace _iniciar_guardado)
    vids2 = ["A.mp4","B.mp4","C.mp4","D.mp4"]
    res_tam2 = ev.obtener_tamanos_archivos(vids2, VIDEOS_DIR)
    registros2 = ev.combinar_registros_con_ffprobe(vids2, VIDEOS_DIR, {"resultados":[]})
    registros2 = ev.combinar_registros_con_miniaturas(registros2, {"resultados":[]})
    registros2 = ev.combinar_registros_con_tamanos(registros2, res_tam2)
    ev.guardar_videos(registros2, DB_PATH)

    # Via 2: plan/sincronizacion productiva (detectar -> preparar -> aplicar -> eliminar)
    diferencias = ev.detectar_diferencias(VIDEOS_DIR, DB_PATH)
    print(f"diferencias tras guardar todos: {diferencias}")
    plan = ev.preparar_plan_sincronizacion(diferencias)
    inc = ev.aplicar_incorporaciones(plan, DB_PATH)
    eli = ev.eliminar_candidatos(plan, DB_PATH)
    print(f"plan a_incorporar: {[r['nombre'] for r in plan['a_incorporar']]}")
    print(f"incorporaciones: {inc} eliminaciones: {eli}")

    # 7) afirmar D agregado y A/B/C mantienen EXACTAMENTE IDs
    ids_despues = _ids_por_nombre(DB_PATH)
    print(f"IDs despues: {ids_despues}")
    print(f"videos despues: {_dump_videos(DB_PATH)}")
    assert "D.mp4" in ids_despues, "D no agregado"
    for nombre in ["A.mp4","B.mp4","C.mp4"]:
        assert ids_despues[nombre] == ids_antes[nombre], f"ID cambio para {nombre}: antes {ids_antes[nombre]} despues {ids_despues[nombre]}"
    print("IDs preservados OK base")

    marc_despues = _dump_marcadores(DB_PATH)
    seg_despues = _dump_segmentos(DB_PATH)
    print(f"marcadores despues: {marc_despues}")
    print(f"segmentos despues: {seg_despues}")
    assert marc_antes == marc_despues, f"marcadores cambiaron: antes {marc_antes} despues {marc_despues}"
    assert seg_antes == seg_despues, f"segmentos cambiaron: antes {seg_antes} despues {seg_despues}"
    # verificar video_id y colores
    for mid, vid, t, col in marc_despues:
        assert vid in (idA, idB), f"marcador video_id invalido {vid}"
    for sid, vid, ini, fin, col in seg_despues:
        assert vid in (idA, idB), f"segmento video_id invalido {vid}"
    # colores especificos
    colores_marc = {c for _,_,_,c in marc_despues}
    colores_seg = {c for _,_,_,_,c in seg_despues}
    assert "rojo" in colores_marc and "azul" in colores_marc, f"colores marcadores perdidos {colores_marc}"
    assert "amarillo" in colores_seg and "violeta" in colores_seg, f"colores segmentos perdidos {colores_seg}"
    print("marcadores/segmentos preservados OK base")

    # 8) repetir reescaneo idempotente
    vids3 = ["A.mp4","B.mp4","C.mp4","D.mp4"]
    res_tam3 = ev.obtener_tamanos_archivos(vids3, VIDEOS_DIR)
    registros3 = ev.combinar_registros_con_ffprobe(vids3, VIDEOS_DIR, {"resultados":[]})
    registros3 = ev.combinar_registros_con_miniaturas(registros3, {"resultados":[]})
    registros3 = ev.combinar_registros_con_tamanos(registros3, res_tam3)
    ev.guardar_videos(registros3, DB_PATH)
    diferencias2 = ev.detectar_diferencias(VIDEOS_DIR, DB_PATH)
    plan2 = ev.preparar_plan_sincronizacion(diferencias2)
    ev.aplicar_incorporaciones(plan2, DB_PATH)
    ev.eliminar_candidatos(plan2, DB_PATH)
    ids_idem = _ids_por_nombre(DB_PATH)
    assert ids_idem == ids_despues, f"idempotencia fallo: {ids_idem} vs {ids_despues}"
    assert _dump_marcadores(DB_PATH) == marc_despues, "marcadores idempotencia fallo"
    assert _dump_segmentos(DB_PATH) == seg_despues, "segmentos idempotencia fallo"
    print("idempotencia OK")

    # 9) integrity_check
    ic = _integrity(DB_PATH)
    print(f"integrity_check: {ic}")
    assert ic == "ok", f"integrity {ic}"
    print("=== BASE PASS ===")
    return {"ids_antes": ids_antes, "ids_despues": ids_despues, "marc_antes": marc_antes, "seg_antes": seg_antes}

def test_modificado():
    print("\n=== ESCENARIO MODIFICADO: video existente considerado modificado ===")
    # Reusar DB existente con A,B,C,D y marcadores
    # Simular que A.mp4 cambia mtime/tamaño/metadata (ej: tamano 4096, mtime nuevo, duracion 120, 1920x1080)
    ids = _ids_por_nombre(DB_PATH)
    idA = ids["A.mp4"]
    marc_antes = _dump_marcadores(DB_PATH)
    seg_antes = _dump_segmentos(DB_PATH)
    videos_antes = _dump_videos(DB_PATH)
    print(f"videos antes modificado: {videos_antes}")
    # Modificar archivo fisico para cambiar mtime/tamano
    rutaA = os.path.join(VIDEOS_DIR, "A.mp4")
    with open(rutaA, "wb") as f:
        f.write(b"\x00" * 4096)
    # Ahora preparar registros como haria el pipeline al detectar modificado: nuevos tamaños + ffprobe metadata
    vids_mod = ["A.mp4","B.mp4","C.mp4","D.mp4"]
    res_tam = ev.obtener_tamanos_archivos(vids_mod, VIDEOS_DIR)
    ff_res = {"resultados": [{"ruta": rutaA, "datos": {"duracion_segundos": 120.5, "ancho": 1920, "alto": 1080, "codec_video": "h264"}}]}
    registros = ev.combinar_registros_con_ffprobe(vids_mod, VIDEOS_DIR, ff_res)
    registros = ev.combinar_registros_con_miniaturas(registros, {"resultados":[]})
    registros = ev.combinar_registros_con_tamanos(registros, res_tam)
    print(f"registro A modificado a guardar: {[r for r in registros if r['nombre']=='A.mp4'][0]}")
    # localizar el registro de A y verificar que contiene nueva metadata
    regA = [r for r in registros if r["nombre"]=="A.mp4"][0]
    assert regA["tamano_bytes"] == 4096, "tamano no propagado"
    assert regA["duracion_segundos"] == 120.5, "duracion no propagada"
    # Guardar via upsert productivo (mismo que pipeline)
    ev.guardar_videos(registros, DB_PATH)
    ids_despues = _ids_por_nombre(DB_PATH)
    print(f"IDs despues modificado: {ids_despues}")
    assert ids_despues["A.mp4"] == idA, f"ID A cambio tras modificado: antes {idA} despues {ids_despues['A.mp4']}"
    # Verificar que B,C,D tambien preservan ID
    for n in ["B.mp4","C.mp4","D.mp4"]:
        assert ids_despues[n] == ids[n], f"ID {n} cambio inesperado"
    marc_despues = _dump_marcadores(DB_PATH)
    seg_despues = _dump_segmentos(DB_PATH)
    print(f"marcadores despues modificado: {marc_despues}")
    print(f"segmentos despues modificado: {seg_despues}")
    assert marc_despues == marc_antes, f"marcadores perdidos tras modificado: antes {marc_antes} despues {marc_despues}"
    assert seg_despues == seg_antes, f"segmentos perdidos tras modificado"
    # Verificar colores intactos
    for _,_,_,col in marc_despues:
        assert col in (None,"rojo","azul","verde"), f"color marcador alterado {col}"
    for _,_,_,_,col in seg_despues:
        assert col in (None,"amarillo","violeta"), f"color segmento alterado {col}"
    # Verificar que metadata de A si se actualizo en videos
    conn = sqlite3.connect(DB_PATH)
    filaA = conn.execute("SELECT duracion_segundos, ancho, alto, codec_video, tamano_bytes FROM videos WHERE nombre='A.mp4'").fetchone()
    conn.close()
    print(f"fila A tras modificado: {filaA}")
    assert filaA[0] == 120.5 and filaA[1]==1920 and filaA[2]==1080 and filaA[3]=="h264" and filaA[4]==4096, f"metadata A no actualizada correctamente {filaA}"
    ic = _integrity(DB_PATH)
    assert ic == "ok", f"integrity tras modificado {ic}"
    print("=== MODIFICADO PASS ===")

def test_plan_completo():
    print("\n=== ESCENARIO PLAN COMPLETO: altas + modificados ===")
    # Agregar E nuevo y modificar B a la vez, usando el plan completo + guardar
    _crear_archivo("E.mp4", size=512)
    # Modificar B fisico
    rutaB = os.path.join(VIDEOS_DIR, "B.mp4")
    with open(rutaB, "wb") as f:
        f.write(b"\x01" * 3000)
    ids_antes = _ids_por_nombre(DB_PATH)
    marc_antes = _dump_marcadores(DB_PATH)
    seg_antes = _dump_segmentos(DB_PATH)
    print(f"ids antes plan completo: {ids_antes}")
    # Pipeline completo: detectar diferencias -> guardar todos (como pipeline) -> sync
    # Primero guardar_todos via guardar_videos (simula _iniciar_guardado que guarda detectados)
    vids5 = ["A.mp4","B.mp4","C.mp4","D.mp4","E.mp4"]
    res_tam = ev.obtener_tamanos_archivos(vids5, VIDEOS_DIR)
    ff_res = {"resultados": [
        {"ruta": os.path.join(VIDEOS_DIR,"B.mp4"), "datos": {"duracion_segundos": 60.0, "ancho":1280, "alto":720, "codec_video":"hevc"}},
    ]}
    registros = ev.combinar_registros_con_ffprobe(vids5, VIDEOS_DIR, ff_res)
    registros = ev.combinar_registros_con_miniaturas(registros, {"resultados":[]})
    registros = ev.combinar_registros_con_tamanos(registros, res_tam)
    ev.guardar_videos(registros, DB_PATH)
    # Luego sincronizacion plan (aunque ya guardado, deberia ser no-op salvo E ya incorporado)
    diferencias = ev.detectar_diferencias(VIDEOS_DIR, DB_PATH)
    print(f"diferencias plan completo: {diferencias}")
    plan = ev.preparar_plan_sincronizacion(diferencias)
    print(f"plan a_incorporar: {[r['nombre'] for r in plan['a_incorporar']]} ya_sinc: {plan['ya_sincronizados']} candidatos: {plan['candidatos_a_eliminar']}")
    inc = ev.aplicar_incorporaciones(plan, DB_PATH)
    eli = ev.eliminar_candidatos(plan, DB_PATH)
    print(f"inc {inc} eli {eli}")
    ids_despues = _ids_por_nombre(DB_PATH)
    print(f"ids despues plan completo: {ids_despues}")
    # E debe existir, A-D preservan ID
    assert "E.mp4" in ids_despues, "E no agregado"
    for n in ["A.mp4","B.mp4","C.mp4","D.mp4"]:
        assert ids_despues[n]==ids_antes[n], f"ID {n} cambio en plan completo"
    marc_despues = _dump_marcadores(DB_PATH)
    seg_despues = _dump_segmentos(DB_PATH)
    assert marc_despues==marc_antes, f"marcadores perdidos plan completo"
    assert seg_despues==seg_antes, f"segmentos perdidos plan completo"
    ic = _integrity(DB_PATH)
    assert ic=="ok", f"integrity plan completo {ic}"
    # Verificar metadata B actualizada
    conn = sqlite3.connect(DB_PATH)
    filaB = conn.execute("SELECT duracion_segundos, tamano_bytes FROM videos WHERE nombre='B.mp4'").fetchone()
    conn.close()
    print(f"fila B tras plan completo: {filaB}")
    assert filaB[0]==60.0 and filaB[1]==3000, f"B metadata no actualizada {filaB}"
    print("=== PLAN COMPLETO PASS ===")

def main():
    try:
        test_base()
        test_modificado()
        test_plan_completo()
        print("\n*** TODOS LOS ESCENARIOS PASS - NO REPRODUCIDO ***")
        print("Evidencia: IDs y marcadores/segmentos preservados en base, modificado y plan completo.")
        ic = _integrity(DB_PATH)
        print(f"integrity_check final: {ic}")
        return 0
    except AssertionError as e:
        print("\n*** FALLO REPRODUCIDO ***")
        import traceback
        traceback.print_exc()
        print("\nEvidencia antes/después ya impresa arriba.")
        # Localizar funcion sospechosa
        print("\nSospecha prioritaria: buscar INSERT OR REPLACE / REPLACE / DELETE+INSERT en escanear_videos.py")
        with open(os.path.join(BASE_DIR,"escanear_videos.py"), encoding="utf-8") as f:
            txt = f.read()
            for i, line in enumerate(txt.splitlines(),1):
                if "REPLACE" in line or "INSERT OR" in line:
                    print(f"  linea {i}: {line.strip()}")
            if "REPLACE" not in txt:
                print("  No se encontro REPLACE directo; verificar _upsert_video ON CONFLICT.")
        ic = _integrity(DB_PATH)
        print(f"integrity_check: {ic}")
        return 1
    except Exception as e:
        print("\n*** ERROR INESPERADO ***")
        import traceback
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    sys.exit(main())
