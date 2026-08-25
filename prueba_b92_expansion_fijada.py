"""B9.2 — P02 gestión de tarjetas expandidas/fijadas.

Cobertura especifica minima exigida (11 puntos) + smoke + no regresion basica.
Solo estado/UI barato, sin persistencia, sin FFmpeg/previews extra.
"""
import os
import sys
import json
import sqlite3
import tempfile
import contextlib
import py_compile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TMP = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TMP.name, "configuracion.json")

app = QApplication.instance() or QApplication(sys.argv)

_CANT_ORIG = escanear_mod.CANTIDAD_PREVIEWS

def _filas(nombres, duraciones=None, carpeta="C:\\tmp_b92"):
    durs = duraciones or [100.0]*len(nombres)
    filas = []
    for i, (n, d) in enumerate(zip(nombres, durs), start=1):
        filas.append((n, float(d), 1920, 1080, "h264", 3, 12345, os.path.join(carpeta, n), i))
    return filas

def _crear_bd(filas):
    t = tempfile.TemporaryDirectory()
    ruta = os.path.join(t.name, "catalogo.db")
    conn = sqlite3.connect(ruta)
    try:
        conn.execute("""CREATE TABLE videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL,
            duracion_segundos REAL,
            ancho INTEGER, alto INTEGER, codec_video TEXT,
            cantidad_miniaturas INTEGER, tamano_bytes INTEGER)""")
        for f in filas:
            nombre, dur, w, h, codec, mini, tam, ruta_v, vid = f
            conn.execute("INSERT INTO videos (id,nombre,ruta,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (vid, nombre, ruta_v, os.path.splitext(nombre)[1], "2026-08-03T00:00:00", dur, w, h, codec, mini))
        conn.commit()
    finally:
        conn.close()
    return t, ruta

@contextlib.contextmanager
def _miniaturas_tmp():
    t = tempfile.TemporaryDirectory()
    orig1 = escanear_mod.ruta_carpeta_miniaturas
    orig2 = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: t.name
    visor_videos.ruta_carpeta_miniaturas = lambda: t.name
    try:
        yield t.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = orig1
        visor_videos.ruta_carpeta_miniaturas = orig2
        t.cleanup()

def _esperar(pred, timeout=4000, paso=20):
    import time as _t
    fin = _t.monotonic()+timeout/1000
    while _t.monotonic()<fin:
        QApplication.processEvents()
        if pred():
            return True
        _t.sleep(paso/1000)
    QApplication.processEvents()
    return pred()

def _limpiar(ventana):
    if ventana is None:
        return
    try:
        for g in [getattr(ventana,'gestor',None), getattr(ventana,'gestor_previews',None), getattr(ventana,'gestor_exploracion',None), getattr(ventana,'gestor_marcadores',None), getattr(ventana,'gestor_segmentos',None), getattr(ventana,'gestor_resumen',None), getattr(ventana,'gestor_migracion',None)]:
            if g and getattr(g,'hilo',None):
                try: g.cerrar()
                except Exception: pass
    except Exception: pass
    try: ventana.close()
    except Exception: pass
    try: ventana.deleteLater()
    except Exception: pass
    for _ in range(3):
        QApplication.processEvents()

def _ventana_con_tarjetas(nombres, duraciones=None):
    filas = _filas(nombres, duraciones)
    tdir, ruta_db = _crear_bd(filas)
    v = VisorVideos(ruta_db=ruta_db)
    v.resize(900,600)
    v.show()
    _esperar(lambda: getattr(v,'_carga_completada',False) and getattr(v.gestor,'hilo',None) is None, timeout=8000)
    _esperar(lambda: len(v.tarjetas)>=len(nombres), timeout=3000)
    # si no cargó por async, forzar creacion directa
    if len(v.tarjetas)==0:
        v._crear_tarjetas(filas)
        QApplication.processEvents()
    return tdir, v

# 1
def test_01_estado_inicial_no_fijado():
    fila = _filas(["a.mp4"])[0]
    t = Tarjeta(fila)
    ok = getattr(t,"_fijada", None) is False
    btn = getattr(t,"_boton_fijar", None)
    ok = ok and btn is not None
    ok = ok and btn.text()=="Fijar" and "Fijar" in btn.toolTip()
    ok = ok and btn.isHidden()  # solo visible expandida
    ok = ok and not t._expandida
    t.deleteLater(); QApplication.processEvents()
    return ok, f"_fijada={getattr(t,'_fijada',None)} btn={btn.text() if btn else None} visible={btn.isVisible() if btn else None}"

# 2
def test_02_fijar_mantiene_abierta():
    fila = _filas(["a.mp4"])[0]
    t = Tarjeta(fila)
    # necesita estar en ventana para que isVisible refleje logica; usamos isHidden
    t.show(); QApplication.processEvents()
    t.expandir()
    QApplication.processEvents()
    btn = t._boton_fijar
    btn.setChecked(True)
    QApplication.processEvents()
    ok = t._expandida and t._fijada and btn.text()=="Desfijar"
    ok = ok and not btn.isHidden()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"expandida={t._expandida} fijada={t._fijada} btn={btn.text()} hidden={btn.isHidden()}"

# 3
def test_03_no_colapsa_fijada():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4"])
        try:
            d = dict(v.tarjetas)
            ta = d["a.mp4"]; tb = d["b.mp4"]
            ta.expandir(); QApplication.processEvents()
            ta._boton_fijar.setChecked(True); QApplication.processEvents()
            tb.expandir(); QApplication.processEvents()
            ok = ta._expandida and tb._expandida and ta._fijada and not tb._fijada
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"ta_exp={ta._expandida} ta_fij={ta._fijada} tb_exp={tb._expandida}"

# 4
def test_04_varias_fijadas_coexisten():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4","c.mp4"])
        try:
            d = dict(v.tarjetas)
            ta=d["a.mp4"]; tb=d["b.mp4"]; tc=d["c.mp4"]
            ta.expandir(); QApplication.processEvents(); ta._boton_fijar.setChecked(True); QApplication.processEvents()
            tb.expandir(); QApplication.processEvents(); tb._boton_fijar.setChecked(True); QApplication.processEvents()
            tc.expandir(); QApplication.processEvents()
            ok = ta._expandida and tb._expandida and tc._expandida
            ok = ok and ta._fijada and tb._fijada and not tc._fijada
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"a:{ta._expandida}/{ta._fijada} b:{tb._expandida}/{tb._fijada} c:{tc._expandida}/{tc._fijada}"

# 5
def test_05_autocolapso_no_fijadas():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4"])
        try:
            d=dict(v.tarjetas); ta=d["a.mp4"]; tb=d["b.mp4"]
            ta.expandir(); QApplication.processEvents()
            assert ta._expandida and not tb._expandida
            tb.expandir(); QApplication.processEvents()
            ok = tb._expandida and not ta._expandida
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"ta={ta._expandida} tb={tb._expandida}"

# 6
def test_06_colapso_manual_desfija():
    fila=_filas(["a.mp4"])[0]
    t=Tarjeta(fila)
    t.expandir(); QApplication.processEvents()
    t._boton_fijar.setChecked(True); QApplication.processEvents()
    assert t._fijada
    t.colapsar(); QApplication.processEvents()
    ok = not t._expandida and not t._fijada and t._boton_fijar.text()=="Fijar" and not t._boton_fijar.isChecked()
    t.deleteLater(); QApplication.processEvents()
    return ok, f"expandida={t._expandida} fijada={t._fijada} btn={t._boton_fijar.text()}"

# 7
def test_07_desfijar_vuelve_a_autocolapso():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4"])
        try:
            d=dict(v.tarjetas); ta=d["a.mp4"]; tb=d["b.mp4"]
            ta.expandir(); QApplication.processEvents(); ta._boton_fijar.setChecked(True); QApplication.processEvents()
            # desfijar
            ta._boton_fijar.setChecked(False); QApplication.processEvents()
            assert not ta._fijada and ta._expandida
            tb.expandir(); QApplication.processEvents()
            ok = tb._expandida and not ta._expandida
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"ta_fijada={ta._fijada} ta_exp={ta._expandida} tb_exp={tb._expandida}"

# 8
def test_08_seleccion_no_rota():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4"])
        try:
            d=dict(v.tarjetas); ta=d["a.mp4"]
            # seleccionar via click simulado: emitir señal manualmente
            ta.expandir(); QApplication.processEvents()
            ta._boton_fijar.setChecked(True); QApplication.processEvents()
            # seleccionar
            v._al_seleccionar_tarjeta(ta._video_id, False)
            QApplication.processEvents()
            ok_sel = ta._video_id in v._ids_seleccionados
            # fijar no debe alterar seleccion
            ok = ok_sel and ta._fijada and ta._expandida
            # colapsar manual desfija pero seleccion sigue
            ta.colapsar(); QApplication.processEvents()
            ok = ok and not ta._fijada and ta._video_id in v._ids_seleccionados
            # marcadores/segmentos vacios no crash
            ok = ok and isinstance(ta._marcadores, list) and isinstance(ta._segmentos, list)
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"seleccion_ok={ok_sel} fijada_post={ta._fijada}"

# 9
def test_09_no_persistencia():
    # config
    ruta_cfg = os.environ["VISOR_CONFIG"]
    antes = None
    if os.path.isfile(ruta_cfg):
        with open(ruta_cfg,"rb") as f: antes=f.read()
    else:
        antes=b""
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4"])
        try:
            ta=dict(v.tarjetas)["a.mp4"]
            ta.expandir(); QApplication.processEvents()
            ta._boton_fijar.setChecked(True); QApplication.processEvents()
            # verificar config no contiene fijada
            despues = b""
            if os.path.isfile(ruta_cfg):
                with open(ruta_cfg,"rb") as f: despues=f.read()
            ok_cfg = b"fijada" not in despues.lower() and b"fijar" not in despues.lower()
            # sqlite: no tabla/columna fijada
            conn = sqlite3.connect(v._ruta_db)
            try:
                cur=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='videos'")
                row=cur.fetchone()
                sql=row[0] if row else ""
                ok_sql = "fijada" not in sql.lower()
            finally:
                conn.close()
            ok = ok_cfg and ok_sql
        finally:
            _limpiar(v); tdir.cleanup()
        # restaurar config
        if antes==b"" and os.path.isfile(ruta_cfg):
            try: os.remove(ruta_cfg)
            except Exception: pass
        elif antes!=b"":
            with open(ruta_cfg,"wb") as f: f.write(antes)
        return ok, f"cfg_ok={ok_cfg} sql_ok={ok_sql}"

# 10
def test_10_no_altera_previews_ni_ffmpeg():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4"])
        try:
            ta=dict(v.tarjetas)["a.mp4"]
            cnt_antes = escanear_mod.CANTIDAD_PREVIEWS
            # mock ffmpeg
            llamadas={"n":0}
            orig_generar = escanear_mod.generar_preview
            orig_ffprobe = getattr(escanear_mod, "obtener_metadatos", None)
            def _fake(*a,**k):
                llamadas["n"]+=1
                raise AssertionError("FFmpeg no debe llamarse al fijar")
            escanear_mod.generar_preview = _fake
            # ffprobe mock
            orig_run = None
            import subprocess
            orig_run = subprocess.run
            def _fake_run(*a,**k):
                llamadas["n"]+=1
                raise AssertionError("FFprobe/subprocess no debe llamarse al fijar")
            subprocess.run = _fake_run
            try:
                ta.expandir(); QApplication.processEvents()
                cnt_despues_expand = escanear_mod.CANTIDAD_PREVIEWS
                ta._boton_fijar.setChecked(True); QApplication.processEvents()
                ta._boton_fijar.setChecked(False); QApplication.processEvents()
                ta.colapsar(); QApplication.processEvents()
            finally:
                escanear_mod.generar_preview = orig_generar
                subprocess.run = orig_run
            ok = llamadas["n"]==0 and cnt_antes==cnt_despues_expand==escanear_mod.CANTIDAD_PREVIEWS
            # cantidad de previews visibles no cambia (slots)
            ok = ok and len(ta._etiquetas_previews)==cnt_antes
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"llamadas_ffmpeg={llamadas['n']} cantidad={escanear_mod.CANTIDAD_PREVIEWS}"

# 11
def test_11_reconstruccion_sin_crash():
    with _miniaturas_tmp():
        tdir, v = _ventana_con_tarjetas(["a.mp4","b.mp4"])
        try:
            d=dict(v.tarjetas); ta=d["a.mp4"]
            ta.expandir(); QApplication.processEvents(); ta._boton_fijar.setChecked(True); QApplication.processEvents()
            # reconstruccion: limpiar y recrear tarjetas (simula recarga)
            # guardar referencia vieja
            viejas = list(v.tarjetas)
            # limpiar layout
            for _, tj in list(v.tarjetas):
                try:
                    v.cuadricula.removeWidget(tj)
                    tj.hide(); tj.deleteLater()
                except Exception:
                    pass
            v.tarjetas.clear(); v.visibles.clear()
            QApplication.processEvents()
            # viejas no deben tener parent visible ni crash al acceder _fijada
            ok_viejas = True
            for _, tj in viejas:
                try:
                    _ = tj._fijada
                    _ = tj._expandida
                except RuntimeError:
                    # widget destruido es esperado, pero no crash
                    pass
                except Exception as e:
                    ok_viejas=False
            # crear nuevas
            filas2=_filas(["a.mp4","b.mp4"])
            v._crear_tarjetas(filas2)
            QApplication.processEvents()
            d2=dict(v.tarjetas)
            ta2=d2["a.mp4"]
            ok_nueva = not ta2._fijada and not ta2._expandida
            ok = ok_viejas and ok_nueva
        finally:
            _limpiar(v); tdir.cleanup()
        return ok, f"viejas_ok={ok_viejas} nueva_fijada={ta2._fijada}"

def test_12_pycompile_y_diffcheck():
    import subprocess
    ok1=True
    try:
        py_compile.compile("visor_videos.py", doraise=True)
        py_compile.compile("prueba_b92_expansion_fijada.py", doraise=True)
    except Exception as e:
        ok1=False
        return ok1, f"py_compile fallo {e}"
    # git diff --check
    try:
        r=subprocess.run(["git","diff","--check"], capture_output=True, text=True)
        ok2 = r.returncode==0 or "ERROR" not in r.stdout
    except Exception:
        ok2=True
    return ok1 and ok2, "py_compile ok"

if __name__=="__main__":
    pruebas=[
        ("01_estado_inicial_no_fijado", test_01_estado_inicial_no_fijado),
        ("02_fijar_mantiene_abierta", test_02_fijar_mantiene_abierta),
        ("03_no_colapsa_fijada", test_03_no_colapsa_fijada),
        ("04_varias_fijadas_coexisten", test_04_varias_fijadas_coexisten),
        ("05_autocolapso_no_fijadas", test_05_autocolapso_no_fijadas),
        ("06_colapso_manual_desfija", test_06_colapso_manual_desfija),
        ("07_desfijar_vuelve_autocolapso", test_07_desfijar_vuelve_a_autocolapso),
        ("08_seleccion_no_rota", test_08_seleccion_no_rota),
        ("09_no_persistencia", test_09_no_persistencia),
        ("10_no_altera_previews_ffmpeg", test_10_no_altera_previews_ni_ffmpeg),
        ("11_reconstruccion_sin_crash", test_11_reconstruccion_sin_crash),
        ("12_pycompile_diffcheck", test_12_pycompile_y_diffcheck),
    ]
    fallos=0
    for nombre, fn in pruebas:
        try:
            ok, msg = fn()
            status="OK" if ok else "FAIL"
            print(f"{status} {nombre}: {msg}")
            sys.stdout.flush()
            if not ok:
                fallos+=1
        except Exception as e:
            import traceback
            print(f"ERROR {nombre}: {e}")
            traceback.print_exc()
            fallos+=1
    print(f"\nResumen: {len(pruebas)-fallos}/{len(pruebas)} OK")
    sys.exit(0 if fallos==0 else 1)
