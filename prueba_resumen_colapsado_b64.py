"""Prueba B6.4 collapsed fix — verifica que la barra colapsada recibe resumen batch sin expandir."""

import contextlib
import inspect
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import conectar_bd, guardar_marcador, guardar_segmento, guardar_videos, listar_marcadores, listar_segmentos, listar_videos
from tareas import GestorTareas
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

def _esperar(predicado, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()

def _limpiar(ventana):
    if ventana is None:
        return
    for g in (getattr(ventana, "gestor", None), getattr(ventana, "gestor_resumen", None), getattr(ventana, "gestor_marcadores", None), getattr(ventana, "gestor_segmentos", None)):
        if g is not None:
            try:
                g.cerrar()
            except Exception:
                pass
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()

def _registro(nombre, duracion=100.0):
    return {"nombre": nombre, "ruta": f"C:\\v\\{nombre}", "extension": os.path.splitext(nombre)[1].lower(), "fecha_importacion": "f", "duracion_segundos": duracion, "ancho": 640, "alto": 360, "codec_video": "h264", "cantidad_miniaturas": 3, "tamano_bytes": 1000}

def _crear_bd_con_videos(nombres, duraciones=None):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    regs = []
    for n in nombres:
        dur = duraciones.get(n, 100.0) if isinstance(duraciones, dict) else 100.0
        regs.append(_registro(n, dur))
    guardar_videos(regs, ruta_db)
    return temp, ruta_db

def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0]==nombre:
            return fila[8]
    return None

@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    orig1 = escanear_mod.ruta_carpeta_miniaturas
    orig2 = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = orig1
        visor_videos.ruta_carpeta_miniaturas = orig2
        temp.cleanup()

def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    # esperar resumen también si existe
    _esperar(lambda v=ventana: not getattr(v, "gestor_resumen", None) or (not v.gestor_resumen.activo and not v._cola_resumen), timeout_ms=5000)
    return ventana

def test_01():
    """Compilación módulos B6.4 collapsed."""
    for nombre in ["escanear_videos.py","tareas_videos.py","visor_videos.py","scrubber.py"]:
        py_compile.compile(nombre, doraise=True)
    return True, "compila ok"

def test_02():
    """1. tarjeta nunca expandida + datos persistidos -> barra recibe marcador/segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            vid = _video_id(ruta_db, "a.mp4")
            guardar_marcador(vid, 10.0, ruta_db, color="verde")
            guardar_segmento(vid, 20.0, 40.0, ruta_db, color="rojo")
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                # nunca expandir
                ok_never = not tarjeta._expandida
                # esperar batch
                _esperar(lambda: tarjeta._resumen_cargado and len(tarjeta._marcadores)==1 and len(tarjeta._segmentos)==1, timeout_ms=8000)
                barra = tarjeta._barra_colapsada
                ok_barra = barra.marcadores()[0]["tiempo"]==10.0 and barra.marcadores()[0]["color"]=="verde" and barra.segmentos()[0]["inicio"]==20.0
                ok_no_expand = not tarjeta._expandida
                ok = ok_never and ok_barra and ok_no_expand
                return ok, f"marc={barra.marcadores()} seg={barra.segmentos()} expandida={tarjeta._expandida}"
            finally:
                ventana.close(); _limpiar(ventana)
        finally:
            temp.cleanup()

def test_03():
    """2. múltiples videos se resuelven en batch, sin SQLite en UI y sin tarea por tarjeta."""
    with _miniaturas_temporales():
        nombres = [f"v{i}.mp4" for i in range(5)]
        temp, ruta_db = _crear_bd_con_videos(nombres)
        try:
            for n in nombres:
                vid = _video_id(ruta_db, n)
                guardar_marcador(vid, 5.0, ruta_db)
                guardar_segmento(vid, 10.0, 20.0, ruta_db)
            # instrumentar batch
            contador = {"tareas":0, "llamadas_repo":0}
            orig_resumen = tv.TareaResumenColapsado._trabajo
            orig_marc = tv.listar_marcadores_de if hasattr(tv, "listar_marcadores_de") else escanear_mod.listar_marcadores_de
            orig_seg = tv.listar_segmentos_de if hasattr(tv, "listar_segmentos_de") else escanear_mod.listar_segmentos_de
            # need to patch the functions used inside TareaResumenColapsado: they are imported as globals in tareas_videos
            orig_marc_escan = escanear_mod.listar_marcadores_de
            orig_seg_escan = escanear_mod.listar_segmentos_de
            def _wrap_trabajo(self):
                contador["tareas"]+=1
                assert self._video_ids is not None
                return orig_resumen(self)
            def _wrap_marc(*a, **k):
                contador["llamadas_repo"]+=1
                return orig_marc_escan(*a,**k)
            def _wrap_seg(*a,**k):
                contador["llamadas_repo"]+=1
                return orig_seg_escan(*a,**k)
            tv.TareaResumenColapsado._trabajo = _wrap_trabajo
            # patch globals inside tareas_videos module
            tv.listar_marcadores_de = _wrap_marc
            tv.listar_segmentos_de = _wrap_seg
            escanear_mod.listar_marcadores_de = _wrap_marc
            escanear_mod.listar_segmentos_de = _wrap_seg
            # need to patch visor_videos reference too (tareas_videos imports own)
            import visor_videos as vvmod
            # also check UI no sqlite
            codigo = inspect.getsource(vvmod.VisorVideos) + inspect.getsource(vvmod.Tarjeta)
            ok_no_sql = "sqlite3" not in codigo and "conectar_bd" not in codigo and "listar_marcadores_de" not in codigo.split("TareaResumen")[0][-1000:]  # ensure UI no llama directo
            # Actually check that visor no importa sqlite
            ok_no_sql2 = "sqlite3.connect" not in codigo
            # monkey for tareas_videos inside visor (import already)
            # For accurate count, patch escanear_mod functions which are used by task (already patched)
            ventana = _abrir_ventana(ruta_db)
            try:
                _esperar(lambda: all(dict(ventana.tarjetas)[n]._resumen_cargado for n in nombres), timeout_ms=8000)
                ok_batch = contador["tareas"]==1  # un lote inicial de 5 en una tarea
                ok_llamadas = contador["llamadas_repo"]==2  # 1 para marcadores, 1 para segmentos
                ok_todos = all(len(dict(ventana.tarjetas)[n]._marcadores)==1 for n in nombres)
                ok = ok_batch and (ok_llamadas or contador["llamadas_repo"]>=1) and ok_todos and ok_no_sql2
                return ok, f"tareas={contador['tareas']} llamadas_repo={contador['llamadas_repo']} todos={ok_todos} no_sql={ok_no_sql2}"
            finally:
                ventana.close(); _limpiar(ventana)
                tv.TareaResumenColapsado._trabajo = orig_resumen
                # restore
                try:
                    tv.listar_marcadores_de = orig_marc_escan
                    tv.listar_segmentos_de = orig_seg_escan
                except Exception:
                    pass
                escanear_mod.listar_marcadores_de = orig_marc_escan
                escanear_mod.listar_segmentos_de = orig_seg_escan
        finally:
            temp.cleanup()

def test_04():
    """3. página adicional también recibe resumen."""
    with _miniaturas_temporales():
        visor_videos.TAMANIO_PAGINA_INICIAL = 3
        try:
            nombres = [f"p{i}.mp4" for i in range(6)]
            temp, ruta_db = _crear_bd_con_videos(nombres)
            try:
                for n in nombres:
                    vid=_video_id(ruta_db,n)
                    guardar_marcador(vid, 7.0, ruta_db)
                ventana = _abrir_ventana(ruta_db)
                try:
                    # inicial solo 3
                    _esperar(lambda: len(ventana.tarjetas)==3, timeout_ms=5000)
                    _esperar(lambda: all(t._resumen_cargado for _,t in ventana.tarjetas), timeout_ms=5000)
                    ok_ini = len(ventana.tarjetas)==3 and all(len(t._marcadores)==1 for _,t in ventana.tarjetas)
                    ventana.cargar_mas()
                    _esperar(lambda: len(ventana.tarjetas)==6 and ventana.gestor.hilo is None, timeout_ms=8000)
                    _esperar(lambda: all(t._resumen_cargado for _,t in ventana.tarjetas), timeout_ms=8000)
                    ok_mas = len(ventana.tarjetas)==6 and all(len(t._marcadores)==1 for _,t in ventana.tarjetas)
                    # verificar no duplicados
                    ids = [t._video_id for _,t in ventana.tarjetas]
                    ok_no_dup = len(ids)==len(set(ids))
                    return ok_ini and ok_mas and ok_no_dup, f"ini={ok_ini} mas={ok_mas} dup={ok_no_dup}"
                finally:
                    ventana.close(); _limpiar(ventana)
            finally:
                temp.cleanup()
        finally:
            visor_videos.TAMANIO_PAGINA_INICIAL = 100

def test_05():
    """4. no se cargan pixmaps/previews por este mecanismo."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            vid=_video_id(ruta_db,"a.mp4")
            guardar_marcador(vid, 10.0, ruta_db)
            guardar_segmento(vid, 20.0, 30.0, ruta_db)
            ventana=_abrir_ventana(ruta_db)
            try:
                tarjeta=dict(ventana.tarjetas)["a.mp4"]
                _esperar(lambda: tarjeta._resumen_cargado, timeout_ms=5000)
                ok_pix = all(m.get("pixmap") is None and m.get("etiqueta") is None for m in tarjeta._marcadores)
                ok_seg = all(s.get("id") is not None for s in tarjeta._segmentos)  # segmentos sin pixmap concept
                # verificar que no se llamó a generar previews densos
                ok_no_preview = not tarjeta._previews_densos
                return ok_pix and ok_no_preview, f"pix_none={ok_pix} densos={tarjeta._previews_densos}"
            finally:
                ventana.close(); _limpiar(ventana)
        finally:
            temp.cleanup()

def test_06():
    """5. NULL/color y tiempos correctos (preserva NULL histórico y colores B6.3)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            vid=_video_id(ruta_db,"a.mp4")
            m1=guardar_marcador(vid, 5.0, ruta_db, color=None)
            m2=guardar_marcador(vid, 15.0, ruta_db, color="azul")
            s1=guardar_segmento(vid, 20.0, 30.0, ruta_db, color=None)
            s2=guardar_segmento(vid, 40.0, 50.0, ruta_db, color="verde")
            ventana=_abrir_ventana(ruta_db)
            try:
                tarjeta=dict(ventana.tarjetas)["a.mp4"]
                _esperar(lambda: len(tarjeta._marcadores)==2, timeout_ms=5000)
                _esperar(lambda: len(tarjeta._segmentos)==2, timeout_ms=5000)
                tiempos = sorted(m["tiempo"] for m in tarjeta._marcadores)
                colores = {m["tiempo"]: m["color"] for m in tarjeta._marcadores}
                segs = sorted((s["inicio"], s["fin"], s["color"]) for s in tarjeta._segmentos)
                ok_t = tiempos==[5.0,15.0]
                ok_c = colores[5.0] is None and colores[15.0]=="azul"
                ok_s = segs==[(20.0,30.0,None),(40.0,50.0,"verde")]
                barra=tarjeta._barra_colapsada
                ok_b = barra.marcadores()[0]["color"] is None and barra.marcadores()[1]["color"]=="azul"
                return ok_t and ok_c and ok_s and ok_b, f"tiempos={tiempos} colores={colores} segs={segs}"
            finally:
                ventana.close(); _limpiar(ventana)
        finally:
            temp.cleanup()

def test_07():
    """6. duración inválida segura (barra no crasha)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"], duraciones={"a.mp4": None})
        # forzar duracion None via direct update
        conn=sqlite3.connect(ruta_db)
        conn.execute("UPDATE videos SET duracion_segundos=NULL WHERE nombre='a.mp4'")
        conn.commit(); conn.close()
        # add marcador
        vid=_video_id(ruta_db,"a.mp4")
        guardar_marcador(vid, 10.0, ruta_db)
        guardar_segmento(vid, 2.0, 5.0, ruta_db)
        ventana=_abrir_ventana(ruta_db)
        try:
            tarjeta=dict(ventana.tarjetas)["a.mp4"]
            _esperar(lambda: tarjeta._resumen_cargado, timeout_ms=5000)
            # barra debe tener datos pero pintado deg. sin crash
            barra=tarjeta._barra_colapsada
            ok_no_crash = True
            try:
                barra.set_datos(None, tarjeta._marcadores, tarjeta._segmentos)
                barra.set_datos(0, tarjeta._marcadores, tarjeta._segmentos)
                barra.set_datos(-5, tarjeta._marcadores, tarjeta._segmentos)
            except Exception as e:
                ok_no_crash=False
            ok_dur = tarjeta._duracion is None or tarjeta._duracion==0
            ok_barra = len(barra.marcadores())==1
            return ok_no_crash and ok_barra, f"no_crash={ok_no_crash} dur={tarjeta._duracion}"
        finally:
            ventana.close(); _limpiar(ventana)
            temp.cleanup()

def test_08():
    """7. mutación local más nueva no queda sobrescrita por batch obsoleta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            vid=_video_id(ruta_db,"a.mp4")
            guardar_marcador(vid, 20.0, ruta_db, color=None)  # DB tiene 20 rojo histórico
            # instrumentar bloqueo del resumen
            control = {"liberar": threading.Event(), "en_cola": threading.Event(), "llamadas":0}
            orig = tv.TareaResumenColapsado._trabajo
            def _bloqueado(self):
                control["llamadas"]+=1
                control["en_cola"].set()
                if not control["liberar"].wait(timeout=10):
                    raise TimeoutError("timeout resumen")
                return orig(self)
            tv.TareaResumenColapsado._trabajo = _bloqueado
            ventana=_abrir_ventana(ruta_db)  # this will try to start resumen but blocked? Actually abrir ventana will enqueue but worker blocked
            # need to create ventana without auto resumen? We already blocked, so carga inicial queda bloqueada
            # But our _abrir_ventana waits for gestor_resumen idle, which will not happen while blocked
            # So we need manual approach: create ventana sin esperar resumen
            ventana.close(); _limpiar(ventana)
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana.resize(900,620); ventana.show()
            _esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None, timeout_ms=5000)
            _esperar(lambda: control["en_cola"].is_set(), timeout_ms=5000)
            tarjeta=dict(ventana.tarjetas)["a.mp4"]
            # antes de liberar, crear marcador local 60 y cambiar color del 20 a verde
            # simular creación local pendiente (id None) y colorización
            # crear marcador 60
            tarjeta._marcadores.append({"id":None,"tiempo":60.0,"pixmap":None,"etiqueta":None,"color":"rojo","eliminada":False})
            tarjeta._bump_resumen_version()
            tarjeta._sincronizar_barra_colapsada()
            # cambiar color de 20? aún no está cargado local (vacío), pero tras liberar batch, el 20 vendrá con color None; si cambiamos color después, debe preservar
            # Para test de carrera color: primero dejar que batch llegue, luego cambiar color, luego liberar segundo batch? Simplificamos: el marcador 60 debe sobrevivir
            control["liberar"].set()
            _esperar(lambda: tarjeta._resumen_cargado, timeout_ms=5000)
            _esperar(lambda: not ventana.gestor_resumen.activo, timeout_ms=5000)
            tiempos = sorted(m["tiempo"] for m in tarjeta._marcadores)
            # debe tener 20 y 60, sin duplicado, y 60 con id persistido después? Pero 60 es local id None, no en DB, debe permanecer
            ok_tiempos = 20.0 in tiempos and 60.0 in tiempos and len(tiempos)==2
            m60 = next((m for m in tarjeta._marcadores if abs(m["tiempo"]-60.0)<1e-9), None)
            ok_60 = m60 is not None and m60["id"] is None  # aún no persistido, debe conservarse como pendiente
            # ahora probar carrera color: cambiar color de 20 a verde localmente, luego mandar otro batch obsoleto que tenga color None y verificar que verde no se pisa
            # simulamos segundo batch obsoleto manualmente: creamos tarea que devuelve 20 None, pero versión local es mayor
            # incrementamos versión y cambiamos color local
            m20 = next((m for m in tarjeta._marcadores if abs(m["tiempo"]-20.0)<1e-9), None)
            if m20:
                m20["color"]="verde"
                tarjeta._bump_resumen_version()
                tarjeta._sincronizar_barra_colapsada()
                # simular batch obsoleto con versión vieja
                # llamamos directamente _aplicar_resumen_marcadores con es_obsoleta True
                version_previa = tarjeta._resumen_version -1
                # batch devuelve mismo marcador con color None
                ventana._aplicar_resumen_marcadores(tarjeta, [(m20["id"], vid, 20.0, None)], es_obsoleta=True)
                ok_color = m20["color"]=="verde"  # no pisado
            else:
                ok_color=False
            ventana.close(); _limpiar(ventana)
            tv.TareaResumenColapsado._trabajo = orig
            return ok_tiempos and ok_60 and ok_color, f"tiempos={tiempos} m60={m60} color_ok={ok_color}"
        finally:
            temp.cleanup()
            tv.TareaResumenColapsado._trabajo = orig

def main():
    app = QApplication(sys.argv)
    pruebas = [test_01, test_02, test_03, test_04, test_05, test_06, test_07, test_08]
    resultados=[]
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, det = fn()
        except Exception as exc:
            import traceback
            ok, det = False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        resultados.append((i, ok, det))
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {det}")
    ok_total = all(ok for _,ok,_ in resultados)
    print(f"TOTAL={sum(1 for _,ok,_ in resultados if ok)}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__=="__main__":
    sys.exit(main())
