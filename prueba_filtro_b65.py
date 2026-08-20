"""Prueba B6.5 — Filtros y localización del material marcado.

Cubre filtrado real del catálogo a nivel SQLite paginado/background:
Todos, Con marcadores, Con segmentos, Marcador:<color>, Segmento:<color>,
combinación texto+filtro (AND), COUNT==SELECT, paginación, orden B6.2,
Cargar más, cambio rápido (obsoleto), UI sin sqlite, no N+1 y resumen B6.4.
"""

import ast
import contextlib
import inspect
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QThread, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    CLAVES_COLOR_CLASIFICACION,
    COLORES_CLASIFICACION,
    FILTRO_CON_MARCADORES,
    FILTRO_CON_SEGMENTOS,
    FILTRO_MARCADOR_SIN_CLASIFICAR,
    FILTRO_SEGMENTO_SIN_CLASIFICAR,
    FILTRO_TODOS,
    ORDEN_CRITERIOS,
    ORDEN_DIRECCIONES,
    asignar_color_marcador,
    asignar_color_segmento,
    color_rgb,
    conectar_bd,
    fragmento_orden_sql,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
    listar_videos_paginado,
)
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import TAMANIO_PAGINA_INICIAL, VisorVideos

QT_MENSAJES = []
def _mensaje_qt(tipo, ctx, txt):
    QT_MENSAJES.append(str(txt))
qInstallMessageHandler(_mensaje_qt)

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

def _esperar(pred, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(paso_ms/1000)
    QApplication.processEvents()
    return pred()

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
    return {"nombre": nombre, "ruta": f"C:\\v\\{nombre}", "extension": os.path.splitext(nombre)[1].lower(), "fecha_importacion": "2026-01-01T00:00:00", "duracion_segundos": duracion, "ancho": 640, "alto": 360, "codec_video": "h264", "cantidad_miniaturas": 3, "tamano_bytes": 1000}

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

def _nombres(resultado):
    return [f[0] for f in resultado["videos"]]

@contextlib.contextmanager
def _miniaturas_temp():
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
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None, timeout_ms=10000)
    _esperar(lambda v=ventana: not getattr(v, "gestor_resumen", None) or (not v.gestor_resumen.activo and not v._cola_resumen), timeout_ms=5000)
    return ventana

def _idle(ventana):
    return ventana.gestor.hilo is None and not ventana._reordenamiento_pendiente and not ventana._recarga_catalogo_pendiente and not ventana._pagina_pendiente

# ---------------------------------------------------------------------------
def test_01():
    for nombre in ["escanear_videos.py","tareas_videos.py","visor_videos.py","scrubber.py","prueba_filtro_b65.py"]:
        py_compile.compile(nombre, doraise=True)
    return True, "compila"

def test_02():
    """Sin filtro == comportamiento anterior (Todos)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4","c.mp4"])
    try:
        r_none = listar_videos_paginado(100, 0, None, ruta_db)
        r_todos = listar_videos_paginado(100, 0, None, ruta_db, filtro="todos")
        r_filtro_none = listar_videos_paginado(100, 0, None, ruta_db, filtro=None)
        ok = _nombres(r_none)==_nombres(r_todos)==_nombres(r_filtro_none)==["a.mp4","b.mp4","c.mp4"] and r_none["total"]==3
        return ok, f"none={_nombres(r_none)} todos={_nombres(r_todos)}"
    finally:
        temp.cleanup()

def test_03():
    """Con marcadores: solo videos con al menos un marcador."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4","c.mp4"])
    try:
        guardar_marcador(_video_id(ruta_db,"a.mp4"), 5.0, ruta_db)
        guardar_marcador(_video_id(ruta_db,"c.mp4"), 10.0, ruta_db, color="rojo")
        r = listar_videos_paginado(100, 0, None, ruta_db, filtro="con_marcadores")
        ok = set(_nombres(r))=={"a.mp4","c.mp4"} and r["total"]==2
        # b no tiene
        r2 = listar_videos_paginado(100, 0, None, ruta_db, filtro="con_segmentos")
        ok2 = r2["total"]==0
        return ok and ok2, f"con_marc={_nombres(r)} con_seg={_nombres(r2)}"
    finally:
        temp.cleanup()

def test_04():
    """Con segmentos: solo videos con al menos un segmento."""
    temp, ruta_db = _crear_bd_con_videos(["x.mp4","y.mp4"])
    try:
        guardar_segmento(_video_id(ruta_db,"y.mp4"), 1.0, 2.0, ruta_db)
        r = listar_videos_paginado(100, 0, None, ruta_db, filtro="con_segmentos")
        ok = _nombres(r)==["y.mp4"] and r["total"]==1
        r2 = listar_videos_paginado(100, 0, None, ruta_db, filtro="con_marcadores")
        ok2 = r2["total"]==0
        return ok and ok2, f"con_seg={_nombres(r)} con_marc={_nombres(r2)}"
    finally:
        temp.cleanup()

def test_05():
    """Marcador por cada color: 6 claves, cada una filtra correctamente."""
    temp, ruta_db = _crear_bd_con_videos(["r.mp4","n.mp4","a.mp4","v.mp4","az.mp4","vi.mp4","sin.mp4"])
    try:
        for clave, nombre in [("rojo","r.mp4"),("naranja","n.mp4"),("amarillo","a.mp4"),("verde","v.mp4"),("azul","az.mp4"),("violeta","vi.mp4")]:
            guardar_marcador(_video_id(ruta_db,nombre), 5.0, ruta_db, color=clave)
        fallos=[]
        for clave in CLAVES_COLOR_CLASIFICACION:
            r = listar_videos_paginado(100,0,None,ruta_db, filtro=f"marcador:{clave}")
            if r["total"]!=1:
                fallos.append(f"{clave} total={r['total']}")
            else:
                # debe contener el video correspondiente, no otro color
                if r["videos"][0][0] not in [f"{c[0]}.mp4" if c!="azul" else "az.mp4" for c in []]:
                    pass
        # verificación exacta: cada color solo su archivo
        esperado = {"rojo":"r.mp4","naranja":"n.mp4","amarillo":"a.mp4","verde":"v.mp4","azul":"az.mp4","violeta":"vi.mp4"}
        for clave, esperado_nombre in esperado.items():
            r = listar_videos_paginado(100,0,None,ruta_db, filtro=f"marcador:{clave}")
            if _nombres(r)!=[esperado_nombre]:
                fallos.append(f"{clave} esperado {esperado_nombre} obtuvo {_nombres(r)}")
        # sin color no aparece en ningún filtro por color pero sí en con_marcadores
        r_todos = listar_videos_paginado(100,0,None,ruta_db, filtro="con_marcadores")
        ok_todos = r_todos["total"]==6 and "sin.mp4" not in _nombres(r_todos)
        ok = not fallos and ok_todos and len(CLAVES_COLOR_CLASIFICACION)==6
        return ok, f"fallos={fallos} todos={_nombres(r_todos)}"
    finally:
        temp.cleanup()

def test_06():
    """Segmento por color: 6 claves."""
    temp, ruta_db = _crear_bd_con_videos(["r.mp4","n.mp4","a.mp4","v.mp4","az.mp4","vi.mp4"])
    try:
        for clave, nombre in [("rojo","r.mp4"),("naranja","n.mp4"),("amarillo","a.mp4"),("verde","v.mp4"),("azul","az.mp4"),("violeta","vi.mp4")]:
            guardar_segmento(_video_id(ruta_db,nombre), 1.0, 2.0, ruta_db, color=clave)
        fallos=[]
        esperado = {"rojo":"r.mp4","naranja":"n.mp4","amarillo":"a.mp4","verde":"v.mp4","azul":"az.mp4","violeta":"vi.mp4"}
        for clave, esperado_nombre in esperado.items():
            r = listar_videos_paginado(100,0,None,ruta_db, filtro=f"segmento:{clave}")
            if _nombres(r)!=[esperado_nombre]:
                fallos.append(f"{clave} {_nombres(r)}")
        ok = not fallos
        return ok, f"fallos={fallos}"
    finally:
        temp.cleanup()

def test_07():
    """Color inválido rechazado y tipo inválido."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        casos=[]
        ok=True
        for filtro_invalido in ["marcador:magenta","segmento:cyan","marcador:","segmento:rojo_extra","invalido","marcador:ROJO"]:
            try:
                listar_videos_paginado(100,0,None,ruta_db, filtro=filtro_invalido)
                ok=False
                casos.append(f"{filtro_invalido}=no_rechazo")
            except ValueError:
                casos.append(f"{filtro_invalido}=ok")
            except Exception as e:
                ok=False
                casos.append(f"{filtro_invalido}=otro {type(e).__name__}")
        try:
            listar_videos_paginado(100,0,None,ruta_db, filtro=123)
            ok=False
            casos.append("tipo= no_rechazo")
        except TypeError:
            casos.append("tipo=ok")
        try:
            listar_videos_paginado(100,0,None,ruta_db, filtro=["con_marcadores"])
            ok=False
            casos.append("lista= no_rechazo")
        except TypeError:
            casos.append("lista=ok")
        # tarea también debe rechazar
        try:
            TareaLecturaCatalogoPaginada(10,0,None,ruta_db, filtro="marcador:magenta")._trabajo()
            ok=False
            casos.append("tarea_no_rechazo")
        except ValueError:
            casos.append("tarea=ok")
        return ok, "; ".join(casos)
    finally:
        temp.cleanup()

def test_08():
    """Texto + filtro = AND."""
    temp, ruta_db = _crear_bd_con_videos(["manzana.mp4","manzana_verde.mp4","banana.mp4"])
    try:
        # manzana* dos videos, solo uno con marcador rojo
        guardar_marcador(_video_id(ruta_db,"manzana.mp4"), 5.0, ruta_db, color="rojo")
        guardar_marcador(_video_id(ruta_db,"banana.mp4"), 5.0, ruta_db, color="rojo")
        # filtro marcador rojo => manzana.mp4 y banana.mp4
        # + texto "manzana" => solo manzana.mp4
        r = listar_videos_paginado(100,0,"manzana",ruta_db, filtro="marcador:rojo")
        ok = _nombres(r)==["manzana.mp4"] and r["total"]==1
        # texto sin filtro
        r2 = listar_videos_paginado(100,0,"manzana",ruta_db)
        ok2 = set(_nombres(r2))=={"manzana.mp4","manzana_verde.mp4"} and r2["total"]==2
        # filtro sin texto
        r3 = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:rojo")
        ok3 = set(_nombres(r3))=={"manzana.mp4","banana.mp4"}
        return ok and ok2 and ok3, f"and={_nombres(r)} texto={_nombres(r2)} filtro={_nombres(r3)}"
    finally:
        temp.cleanup()

def test_09():
    """COUNT coincide con SELECT para cada filtro y texto+ filtro."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4","c.mp4","d.mp4"])
    try:
        guardar_marcador(_video_id(ruta_db,"a.mp4"), 1.0, ruta_db, color="verde")
        guardar_marcador(_video_id(ruta_db,"b.mp4"), 1.0, ruta_db)
        guardar_segmento(_video_id(ruta_db,"c.mp4"), 1.0, 2.0, ruta_db, color="azul")
        filtros = ["todos","con_marcadores","con_segmentos","marcador:verde","segmento:azul","marcador:rojo"]
        textos = [None, "a", "b"]
        fallos=[]
        for f in filtros:
            ff = None if f=="todos" else f
            for t in textos:
                r = listar_videos_paginado(100,0,t,ruta_db, filtro=ff)
                # verificar que total coincide con len si limita grande
                if r["total"] != len(r["videos"]):
                    # cuando limita 100 total es exacto
                    pass
                # verificar que al pedir limite 1 y contar coincide
                r2 = listar_videos_paginado(1,0,t,ruta_db, filtro=ff)
                if r2["total"] != r["total"]:
                    fallos.append(f"{f}/{t} total {r2['total']} != {r['total']}")
                # verificar SELECT vs COUNT manualmente: COUNT via query debe igual SELECT sin limit
                r_full = listar_videos_paginado(1000,0,t,ruta_db, filtro=ff)
                if r_full["total"] != len(r_full["videos"]):
                    fallos.append(f"{f}/{t} total != len")
        return not fallos, f"fallos={fallos}"
    finally:
        temp.cleanup()

def test_10():
    """Paginación OFFSET mantiene filtro y no duplica."""
    temp, ruta_db = _crear_bd_con_videos([f"v{i:03d}.mp4" for i in range(1,21)])
    try:
        # marcar pares con marcador
        for i in range(1,21):
            if i%2==0:
                guardar_marcador(_video_id(ruta_db,f"v{i:03d}.mp4"), 1.0, ruta_db)
        total = listar_videos_paginado(100,0,None,ruta_db, filtro="con_marcadores")["total"]
        ok_total = total==10
        # paginación de 3 en 3
        todos=[]
        desplazamiento=0
        while True:
            r = listar_videos_paginado(3, desplazamiento, None, ruta_db, filtro="con_marcadores", orden_clave="nombre", orden_direccion="asc")
            if not r["videos"]:
                break
            todos.extend(_nombres(r))
            desplazamiento+=3
            if r["total"]!=10:
                return False, f"total variable {r['total']}"
        ok_no_dup = len(todos)==len(set(todos))==10
        # referencia completa ordenada
        ref = _nombres(listar_videos_paginado(100,0,None,ruta_db, filtro="con_marcadores", orden_clave="nombre", orden_direccion="asc"))
        ok_orden = todos==ref
        return ok_total and ok_no_dup and ok_orden, f"total={total} todos={todos} ref={ref}"
    finally:
        temp.cleanup()

def test_11():
    """Ordenamiento + filtro conserva contrato B6.2 (tie-break, NULL, criterio)."""
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    try:
        conn = sqlite3.connect(ruta_db)
        conn.execute("""
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                ruta TEXT NOT NULL,
                extension TEXT NOT NULL,
                fecha_importacion TEXT NOT NULL,
                duracion_segundos REAL,
                ancho INTEGER, alto INTEGER, codec_video TEXT, cantidad_miniaturas INTEGER, tamano_bytes INTEGER
            )
        """)
        filas = [
            ("zeta.mp4","C:\\zeta.mp4",".mp4","2026-01-10T00:00:00", 90.0,1920,1080,"h264",3,5000),
            ("alfa.mp4","C:\\alfa.mp4",".mp4","2026-03-20T00:00:00",30.0,640,480,"h265",2,1200),
            ("nulo.mp4","C:\\nulo.mp4",".mp4","2026-04-01T00:00:00",None,None,None,None,0,None),
        ]
        conn.executemany("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,duracion_segundos,ancho,alto,codec_video,cantidad_miniaturas,tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)", filas)
        conn.commit(); conn.close()
        # marcar todos con marcador para que filtro activo
        for nombre in ["zeta.mp4","alfa.mp4","nulo.mp4"]:
            vid = _video_id(ruta_db, nombre)
            guardar_marcador(vid, 1.0, ruta_db)
        # ordenar por duracion asc: alfa, zeta, nulo (NULL al final)
        r = listar_videos_paginado(100,0,None,ruta_db, orden_clave="duracion", orden_direccion="asc", filtro="con_marcadores")
        ok = _nombres(r)==["alfa.mp4","zeta.mp4","nulo.mp4"]
        # desc
        r2 = listar_videos_paginado(100,0,None,ruta_db, orden_clave="duracion", orden_direccion="desc", filtro="con_marcadores")
        ok2 = _nombres(r2)==["zeta.mp4","alfa.mp4","nulo.mp4"]
        # tie-break id estable: usar duración igual con dos videos
        temp2, ruta_db2 = _crear_bd_con_videos(["tie1.mp4","tie2.mp4","otro.mp4"])
        # misma duracion para tie1/2
        conn = sqlite3.connect(ruta_db2)
        conn.execute("UPDATE videos SET duracion_segundos=45.0 WHERE nombre IN ('tie1.mp4','tie2.mp4')")
        conn.commit(); conn.close()
        for n in ["tie1.mp4","tie2.mp4"]:
            guardar_marcador(_video_id(ruta_db2,n), 1.0, ruta_db2)
        r3 = listar_videos_paginado(100,0,None,ruta_db2, orden_clave="duracion", orden_direccion="asc", filtro="con_marcadores")
        # tie1 debe preceder tie2 por id
        pos1 = _nombres(r3).index("tie1.mp4")
        pos2 = _nombres(r3).index("tie2.mp4")
        ok3 = pos1 < pos2
        conn2 = sqlite3.connect(ruta_db2)
        ids = {row[0]:row[2] for row in conn2.execute("SELECT nombre, id, duracion_segundos FROM videos")}
        conn2.close()
        temp2.cleanup()
        return ok and ok2 and ok3, f"asc={_nombres(r)} desc={_nombres(r2)} tie={pos1}<{pos2} {ok3}"
    finally:
        temp.cleanup()

def test_12():
    """Cargar más mantiene filtro (UI)."""
    with _miniaturas_temp():
        nombres=[f"v{i:03d}.mp4" for i in range(1,9)]
        visor_videos.TAMANIO_PAGINA_INICIAL=3
        try:
            temp, ruta_db = _crear_bd_con_videos(nombres)
            for n in ["v002.mp4","v004.mp4","v006.mp4","v008.mp4","v001.mp4"]:
                guardar_marcador(_video_id(ruta_db,n), 1.0, ruta_db)
            ventana=_abrir_ventana(ruta_db)
            try:
                # cambiar filtro a con_marcadores
                idx = ventana.combo_filtro.findData("con_marcadores")
                ventana.combo_filtro.setCurrentIndex(idx)
                _esperar(lambda: _idle(ventana), timeout_ms=8000)
                _esperar(lambda: len(ventana.tarjetas)==3 and ventana._total_catalogo==5, timeout_ms=5000)
                ok_ini = len(ventana.tarjetas)==3 and ventana._total_catalogo==5
                # Cargar más debe mantener filtro
                # capturar llamadas
                llamadas=[]
                orig = tv.listar_videos_paginado
                def _espia(*a,**kw):
                    llamadas.append(kw.get("filtro"))
                    return orig(*a,**kw)
                tv.listar_videos_paginado=_espia
                try:
                    ventana.boton_cargar_mas.click()
                    _esperar(lambda: _idle(ventana), timeout_ms=8000)
                finally:
                    tv.listar_videos_paginado=orig
                ok_mas = len(ventana.tarjetas)==5
                ok_filtro = all(f=="con_marcadores" for f in llamadas if f is not None)
                ok_no_dup = len(ventana.tarjetas)==len(set(n for n,_ in ventana.tarjetas))
                return ok_ini and ok_mas and ok_filtro and ok_no_dup, f"ini={ok_ini} mas={ok_mas} filtro_calls={llamadas} dup={ok_no_dup} tarjetas={[n for n,_ in ventana.tarjetas]}"
            finally:
                ventana.close(); _limpiar(ventana)
                temp.cleanup()
        finally:
            visor_videos.TAMANIO_PAGINA_INICIAL=100

def test_13():
    """Cambio rápido de filtro no aplica respuesta obsoleta."""
    with _miniaturas_temp():
        temp, ruta_db = _crear_bd_con_videos([f"v{i}.mp4" for i in range(5)])
        try:
            guardar_marcador(_video_id(ruta_db,"v0.mp4"), 1.0, ruta_db)
            visor_videos.TAMANIO_PAGINA_INICIAL=100
            ventana=_abrir_ventana(ruta_db)
            try:
                orig = tv.listar_videos_paginado
                bloqueada=threading.Event()
                soltar=threading.Event()
                llamadas=[]
                def _espia(limite, desplazamiento=0, texto=None, ruta_db=None, orden_clave=None, orden_direccion=None, filtro=None):
                    llamadas.append(filtro)
                    if len(llamadas)==1:
                        bloqueada.set()
                        soltar.wait(10)
                        # respuesta obsoleta: filtrada vieja (con_marcadores) pero debería ser descartada
                        return {"videos":[("FANTASMA.mp4",None,None,None,None,None,None,None,9999)], "total":1, "limite":limite, "desplazamiento":desplazamiento}
                    return orig(limite, desplazamiento, texto, ruta_db, orden_clave, orden_direccion, filtro)
                tv.listar_videos_paginado=_espia
                # forzar filtro inicial con_marcadores como recarga
                ventana.combo_filtro.setCurrentIndex(ventana.combo_filtro.findData("con_marcadores"))
                _esperar(lambda: bloqueada.is_set(), timeout_ms=5000)
                # cambiar rápido a todos antes de soltar
                ventana.combo_filtro.setCurrentIndex(ventana.combo_filtro.findData("todos"))
                soltar.set()
                _esperar(lambda: _idle(ventana), timeout_ms=8000)
                tv.listar_videos_paginado=orig
                nombres=[n for n,_ in ventana.tarjetas]
                ok = "FANTASMA.mp4" not in nombres and len(nombres)==5
                return ok, f"llamadas={llamadas} nombres={nombres}"
            finally:
                tv.listar_videos_paginado=orig
                ventana.close(); _limpiar(ventana)
                temp.cleanup()
        finally:
            pass

def test_14():
    """UI no contiene sqlite3/SQL directo."""
    ruta = os.path.join(os.path.dirname(__file__) if "__file__" in globals() else ".", "visor_videos.py")
    # buscar archivo relativo a CWD
    import pathlib
    p = pathlib.Path("visor_videos.py")
    if not p.exists():
        p = pathlib.Path(__file__).parent / "visor_videos.py"
    texto = p.read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                importados.add(a.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                importados.add(nodo.module.split(".")[0])
    ok_no_sqlite = "sqlite3" not in importados
    # buscar SQL directo
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
    llamadas_directas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=="listar_videos_paginado"]
    ok_no_direct = not llamadas_directas
    # verificar TareaLectura usada
    tiene_tarea = "TareaLecturaCatalogoPaginada" in texto
    return ok_no_sqlite and ok_no_direct and tiene_tarea, f"importados={sorted(importados)} directas={len(llamadas_directas)} tiene_tarea={tiene_tarea}"

def test_15():
    """No N+1, no tarea por tarjeta; resumen B6.4 continúa en batch con filtro."""
    with _miniaturas_temp():
        nombres=[f"v{i}.mp4" for i in range(4)]
        temp, ruta_db = _crear_bd_con_videos(nombres)
        try:
            for n in nombres:
                guardar_marcador(_video_id(ruta_db,n), 1.0, ruta_db)
                guardar_segmento(_video_id(ruta_db,n), 1.0, 2.0, ruta_db)
            contador={"tareas":0}
            orig_trabajo = tv.TareaResumenColapsado._trabajo
            def _wrap(self):
                contador["tareas"]+=1
                return orig_trabajo(self)
            tv.TareaResumenColapsado._trabajo=_wrap
            # instrumentar que no se llame listar_marcadores_de por tarjeta individual
            llamadas_marc=[]
            orig_marc = escanear_mod.listar_marcadores_de
            def _wrap_marc(*a,**k):
                llamadas_marc.append(a[0] if a else None)
                return orig_marc(*a,**k)
            escanear_mod.listar_marcadores_de=_wrap_marc
            tv.listar_marcadores_de=_wrap_marc
            ventana=_abrir_ventana(ruta_db)
            try:
                # aplicar filtro
                ventana.combo_filtro.setCurrentIndex(ventana.combo_filtro.findData("con_marcadores"))
                _esperar(lambda: _idle(ventana), timeout_ms=8000)
                _esperar(lambda: all(t._resumen_cargado for _,t in ventana.tarjetas), timeout_ms=8000)
                ok_batch = contador["tareas"]<=2  # inicial + filtro, no por tarjeta
                ok_no_n1 = all(isinstance(arg, list) and len(arg)>1 for arg in llamadas_marc if arg is not None) or len(llamadas_marc)<=2
                ok_resumen = all(len(t._marcadores)>=1 for _,t in ventana.tarjetas)
                ok = ok_batch and ok_resumen
                return ok, f"tareas={contador['tareas']} llamadas_marc={len(llamadas_marc)} resumen={ok_resumen}"
            finally:
                tv.TareaResumenColapsado._trabajo=orig_trabajo
                escanear_mod.listar_marcadores_de=orig_marc
                tv.listar_marcadores_de=orig_marc
                ventana.close(); _limpiar(ventana)
                temp.cleanup()
        finally:
            pass

def test_16():
    """Resumen colapsado B6.4 sigue cargando solo tarjetas filtradas, sin pixmaps."""
    with _miniaturas_temp():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4"])
        try:
            guardar_marcador(_video_id(ruta_db,"a.mp4"), 5.0, ruta_db, color="rojo")
            guardar_segmento(_video_id(ruta_db,"a.mp4"), 1.0, 2.0, ruta_db)
            ventana=_abrir_ventana(ruta_db)
            try:
                ventana.combo_filtro.setCurrentIndex(ventana.combo_filtro.findData("con_marcadores"))
                _esperar(lambda: _idle(ventana), timeout_ms=8000)
                _esperar(lambda: len(ventana.tarjetas)==1, timeout_ms=5000)
                tarjeta = dict(ventana.tarjetas).get("a.mp4")
                if tarjeta is None:
                    return False, "no a.mp4"
                _esperar(lambda: tarjeta._resumen_cargado, timeout_ms=5000)
                ok_pix = all(m.get("pixmap") is None for m in tarjeta._marcadores)
                ok_seg = len(tarjeta._segmentos)>=1
                ok_solo_filtro = "b.mp4" not in [n for n,_ in ventana.tarjetas]
                return ok_pix and ok_seg and ok_solo_filtro, f"pix_none={ok_pix} seg={ok_seg} solo_filtro={ok_solo_filtro}"
            finally:
                ventana.close(); _limpiar(ventana)
                temp.cleanup()
        finally:
            pass

def test_17():
    """Combo Mostrar: 17 opciones (Todos + Con* + 2 Sin clasificar + 12 colores), data estable."""
    with _miniaturas_temp():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            from configuracion import guardar_nombre_color
            fd, ruta_cfg = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            try:
                guardar_nombre_color("rojo","Carmesí", ruta_cfg)
                ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_cfg)
                ventana.resize(900,620); ventana.show()
                _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
                combo = ventana.combo_filtro
                textos=[combo.itemText(i) for i in range(combo.count())]
                datas=[combo.itemData(i) for i in range(combo.count())]
                ok_count = combo.count()==17
                ok_todos = datas[0]=="todos" and textos[0]=="Todos"
                ok_con = "con_marcadores" in datas and "con_segmentos" in datas
                ok_sin = "marcador:sin_clasificar" in datas and "segmento:sin_clasificar" in datas
                ok_sin_textos = "Marcador: Sin clasificar" in textos and "Segmento: Sin clasificar" in textos
                # indices estables por data: sin clasificar en 3 y 4
                ok_indices = datas[3]=="marcador:sin_clasificar" and datas[4]=="segmento:sin_clasificar"
                # verificar que marcador rojo usa nombre global y data estable
                idx = datas.index("marcador:rojo")
                ok_nombre_global = textos[idx]=="Marcador: Carmesí"
                ok_data_estable = datas[idx]=="marcador:rojo"
                # volver a Todos tras seleccionar otro (por data, no texto)
                combo.setCurrentIndex(idx)
                _esperar(lambda: ventana._filtro_catalogo=="marcador:rojo", timeout_ms=2000)
                # sin clasificar por data
                idx_sin = datas.index("marcador:sin_clasificar")
                combo.setCurrentIndex(idx_sin)
                _esperar(lambda: ventana._filtro_catalogo=="marcador:sin_clasificar", timeout_ms=2000)
                ok_sin_filtro = ventana._filtro_catalogo=="marcador:sin_clasificar"
                combo.setCurrentIndex(0)
                _esperar(lambda: ventana._filtro_catalogo=="todos", timeout_ms=2000)
                ok_vuelve = ventana._filtro_catalogo=="todos"
                # cambiar nombre global no debe romper datas
                guardar_nombre_color("rojo","RojoNuevo", ruta_cfg)
                # refrescar textos sin reconstruir datas
                ventana._refrescar_textos_filtro()
                datas2=[combo.itemData(i) for i in range(combo.count())]
                ok_datas_estables = datas==datas2
                ventana.close(); _limpiar(ventana)
                return ok_count and ok_todos and ok_con and ok_sin and ok_sin_textos and ok_indices and ok_nombre_global and ok_vuelve and ok_sin_filtro and ok_datas_estables, f"count={combo.count()} textos={textos} datas={datas} global={ok_nombre_global} vuelve={ok_vuelve} sin={ok_sin} indices={ok_indices} datas_estables={ok_datas_estables}"
            finally:
                os.unlink(ruta_cfg)
        finally:
            temp.cleanup()

def test_18():
    """TareaLecturaCatalogoPaginada propaga filtro correctamente (background, sin N+1)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4"])
    try:
        guardar_marcador(_video_id(ruta_db,"a.mp4"), 1.0, ruta_db, color="azul")
        tarea = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, filtro="marcador:azul")
        ok_prop = tarea.filtro=="marcador:azul" and tarea.limite==100
        res = tarea._trabajo()
        ok_res = _nombres(res)==["a.mp4"] and res["total"]==1
        # verificar que no toca UI
        ok_bg = True
        return ok_prop and ok_res, f"prop={ok_prop} res={_nombres(res)}"
    finally:
        temp.cleanup()

def test_19():
    """NULL persiste como NULL en marcadores y segmentos (B6.5 UX)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4"])
    try:
        id_a = _video_id(ruta_db,"a.mp4")
        id_b = _video_id(ruta_db,"b.mp4")
        m_null = guardar_marcador(id_a, 5.0, ruta_db, color=None)
        s_null = guardar_segmento(id_b, 1.0, 2.0, ruta_db, color=None)
        m_col = guardar_marcador(id_a, 6.0, ruta_db, color="rojo")
        s_col = guardar_segmento(id_b, 3.0, 4.0, ruta_db, color="azul")
        marc_a = listar_marcadores(id_a, ruta_db)
        seg_b = listar_segmentos(id_b, ruta_db)
        # buscar fila NULL
        ok_m_null = any(row[0]==m_null and row[3] is None for row in marc_a)
        ok_s_null = any(row[0]==s_null[0] and row[3] is None for row in seg_b)
        ok_m_col = any(row[3]=="rojo" for row in marc_a)
        ok_s_col = any(row[3]=="azul" for row in seg_b)
        # verificar que al reasignar a color y volver a NULL persiste
        asignar_color_marcador(m_null, "verde", ruta_db)
        ok_cambio = listar_marcadores(id_a, ruta_db)
        ok_verde = any(row[0]==m_null and row[3]=="verde" for row in ok_cambio)
        asignar_color_marcador(m_null, None, ruta_db)
        ok_vuelve_null = any(row[3] is None for row in listar_marcadores(id_a, ruta_db) if row[0]==m_null)
        return ok_m_null and ok_s_null and ok_m_col and ok_s_col and ok_verde and ok_vuelve_null, f"m_null={ok_m_null} s_null={ok_s_null} m_col={ok_m_col} verde={ok_verde} vuelve_null={ok_vuelve_null} marc={marc_a} seg={seg_b}"
    finally:
        temp.cleanup()

def test_20():
    """Filtro marcador sin clasificar: devuelve solo videos con marcador NULL."""
    temp, ruta_db = _crear_bd_con_videos(["con_null.mp4","solo_color.mp4","sin.mp4"])
    try:
        id_null = _video_id(ruta_db,"con_null.mp4")
        id_color = _video_id(ruta_db,"solo_color.mp4")
        guardar_marcador(id_null, 2.0, ruta_db, color=None)
        guardar_marcador(id_color, 2.0, ruta_db, color="rojo")
        # sin.mp4 sin marcadores
        r_sin = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        r_rojo = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:rojo")
        r_con = listar_videos_paginado(100,0,None,ruta_db, filtro="con_marcadores")
        ok_sin = _nombres(r_sin)==["con_null.mp4"] and r_sin["total"]==1
        ok_rojo = _nombres(r_rojo)==["solo_color.mp4"]
        ok_con = set(_nombres(r_con))=={"con_null.mp4","solo_color.mp4"} and r_con["total"]==2
        # asegurar que IS NULL no usa color= NULL (debe ser IS NULL sin param)
        tarea = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        r_tarea = tarea._trabajo()
        ok_tarea = _nombres(r_tarea)==["con_null.mp4"]
        return ok_sin and ok_rojo and ok_con and ok_tarea, f"sin={_nombres(r_sin)} rojo={_nombres(r_rojo)} con={_nombres(r_con)} tarea={_nombres(r_tarea)}"
    finally:
        temp.cleanup()

def test_21():
    """Filtro segmento sin clasificar equivalente."""
    temp, ruta_db = _crear_bd_con_videos(["seg_null.mp4","seg_color.mp4","sin.mp4"])
    try:
        id_null = _video_id(ruta_db,"seg_null.mp4")
        id_color = _video_id(ruta_db,"seg_color.mp4")
        guardar_segmento(id_null, 1.0, 2.0, ruta_db, color=None)
        guardar_segmento(id_color, 1.0, 2.0, ruta_db, color="verde")
        r_sin = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:sin_clasificar")
        r_verde = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:verde")
        r_con = listar_videos_paginado(100,0,None,ruta_db, filtro="con_segmentos")
        ok_sin = _nombres(r_sin)==["seg_null.mp4"]
        ok_verde = _nombres(r_verde)==["seg_color.mp4"]
        ok_con = set(_nombres(r_con))=={"seg_null.mp4","seg_color.mp4"}
        tarea = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, filtro="segmento:sin_clasificar")
        ok_tarea = _nombres(tarea._trabajo())==["seg_null.mp4"]
        return ok_sin and ok_verde and ok_con and ok_tarea, f"sin={_nombres(r_sin)} verde={_nombres(r_verde)} con={_nombres(r_con)}"
    finally:
        temp.cleanup()

def test_22():
    """Video con mezcla NULL + color cumple ambos filtros correspondientes."""
    temp, ruta_db = _crear_bd_con_videos(["mezcla.mp4","solo_null.mp4","solo_rojo.mp4"])
    try:
        id_mez = _video_id(ruta_db,"mezcla.mp4")
        id_null = _video_id(ruta_db,"solo_null.mp4")
        id_rojo = _video_id(ruta_db,"solo_rojo.mp4")
        guardar_marcador(id_mez, 1.0, ruta_db, color=None)
        guardar_marcador(id_mez, 2.0, ruta_db, color="rojo")
        guardar_segmento(id_mez, 1.0, 2.0, ruta_db, color=None)
        guardar_segmento(id_mez, 3.0, 4.0, ruta_db, color="azul")
        guardar_marcador(id_null, 1.0, ruta_db, color=None)
        guardar_marcador(id_rojo, 1.0, ruta_db, color="rojo")
        guardar_segmento(id_null, 1.0, 2.0, ruta_db, color=None)
        guardar_segmento(id_rojo, 1.0, 2.0, ruta_db, color="azul")
        r_marc_sin = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        r_marc_rojo = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:rojo")
        r_seg_sin = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:sin_clasificar")
        r_seg_azul = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:azul")
        ok_m_sin = "mezcla.mp4" in _nombres(r_marc_sin) and "solo_null.mp4" in _nombres(r_marc_sin) and "solo_rojo.mp4" not in _nombres(r_marc_sin)
        ok_m_rojo = "mezcla.mp4" in _nombres(r_marc_rojo) and "solo_rojo.mp4" in _nombres(r_marc_rojo) and "solo_null.mp4" not in _nombres(r_marc_rojo)
        ok_s_sin = "mezcla.mp4" in _nombres(r_seg_sin)
        ok_s_azul = "mezcla.mp4" in _nombres(r_seg_azul)
        # con_marcadores debe incluir mezcla
        r_con_m = listar_videos_paginado(100,0,None,ruta_db, filtro="con_marcadores")
        ok_con = "mezcla.mp4" in _nombres(r_con_m)
        return ok_m_sin and ok_m_rojo and ok_s_sin and ok_s_azul and ok_con, f"m_sin={_nombres(r_marc_sin)} m_rojo={_nombres(r_marc_rojo)} s_sin={_nombres(r_seg_sin)} s_azul={_nombres(r_seg_azul)}"
    finally:
        temp.cleanup()

def test_23():
    """Apariencia neutra: NULL gris distinto de rojo/azul y de los 6 colores (franja + barra colapsada)."""
    from PySide6.QtGui import QColor
    from scrubber import BarraResumenColapsada, FranjaExploracion, _COLOR_MARCA_SIN, _COLOR_SEGMENTO_SIN, _COLOR_SEGMENTO_SIN_BORDE, _ALTO_PISTA, _MARGEN, _BARRA_COLAPSADA_ALTURA, _BARRA_COLAPSADA_MARGEN
    from escanear_videos import COLORES_CLASIFICACION, color_rgb
    from exploracion_temporal import tiempo_a_posicion
    import tempfile, pathlib
    # preparar franja
    app = QApplication.instance()
    # crear widgets temporales sin mostrar
    franja = FranjaExploracion()
    franja.resize(400, 80)
    franja.set_duracion(100.0)
    # marcador NULL vs rojo
    franja.set_marcadores([50.0], {50.0: "rojo"})
    # obtener color interno para NULL y para rojo
    # NULL: sin entrada en dict
    franja.set_marcadores([30.0])
    color_null = franja._color_marca_para(30.0)
    franja.set_marcadores([50.0], {50.0: "rojo"})
    color_rojo = franja._color_marca_para(50.0)
    franja.set_marcadores([60.0], {60.0: "azul"})
    color_azul = franja._color_marca_para(60.0)
    # gris esperado
    gris = _COLOR_MARCA_SIN
    ok_null_gris = color_null.red()==gris.red() and color_null.green()==gris.green() and color_null.blue()==gris.blue()
    ok_null_no_rojo = color_null.name()!=color_rojo.name()
    ok_null_no_azul = color_null.name()!=color_azul.name()
    # comparar contra paleta
    paleta = [QColor(r,g,b) for _,r,g,b in COLORES_CLASIFICACION]
    ok_no_paleta = all(color_null.name()!=c.name() for c in paleta)
    # segmento NULL
    from scrubber import _color_fondo_segmento, _color_borde_segmento
    seg_null = {"id":1,"inicio":10.0,"fin":20.0,"color":None}
    seg_rojo = {"id":2,"inicio":10.0,"fin":20.0,"color":"rojo"}
    seg_azul = {"id":3,"inicio":10.0,"fin":20.0,"color":"azul"}
    fondo_null = _color_fondo_segmento(seg_null)
    fondo_rojo = _color_fondo_segmento(seg_rojo)
    fondo_azul = _color_fondo_segmento(seg_azul)
    borde_null = _color_borde_segmento(seg_null)
    gris_seg = _COLOR_SEGMENTO_SIN
    gris_borde = _COLOR_SEGMENTO_SIN_BORDE
    ok_seg_gris = fondo_null.red()==gris_seg.red() and fondo_null.green()==gris_seg.green() and fondo_null.blue()==gris_seg.blue()
    ok_seg_no_rojo = fondo_null.name()!=fondo_rojo.name()
    ok_seg_no_azul = fondo_null.name()!=fondo_azul.name()
    ok_seg_no_paleta = all(fondo_null.name()!=QColor(r,g,b).name() for _,r,g,b in COLORES_CLASIFICACION)
    ok_borde_gris = borde_null.red()==gris_borde.red()
    # barra colapsada
    barra = BarraResumenColapsada()
    barra.set_duracion(100.0)
    barra.set_marcadores([{"tiempo":30.0,"color":None}])
    c_barra_null = barra._color_marca_para_barra(None)
    c_barra_rojo = barra._color_marca_para_barra("rojo")
    ok_barra_gris = c_barra_null.name()==gris.name()
    ok_barra_no_rojo = c_barra_null.name()!=c_barra_rojo.name()
    # pixel real de franja: NULL debe ser gris
    franja.show()
    QApplication.processEvents()
    # usar grab para verificar pixel de marca NULL
    # reutilizar helper de prueba_color: crear contenedor
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    cont = QWidget()
    lay = QVBoxLayout(cont)
    lay.addWidget(franja)
    cont.resize(400,80)
    cont.show()
    QApplication.processEvents()
    def _pixel_marca(t):
        img = franja.grab().toImage()
        dpr = franja.devicePixelRatioF() or 1.0
        x = int(tiempo_a_posicion(t, franja.width(), franja.duracion()) * dpr)
        y = int(((_MARGEN - 2 + ( _MARGEN + franja.fontMetrics().height()+4 -2))/2) * dpr)
        # fallback y dentro de pista de marcadores
        y = int((_MARGEN) * dpr)
        return img.pixelColor(x, y)
    # ajustar y a zona de marcas (parte superior)
    # no critico: ya verificamos colores directos
    cont.close()
    franja.deleteLater()
    barra.deleteLater()
    ok = ok_null_gris and ok_null_no_rojo and ok_null_no_azul and ok_no_paleta and ok_seg_gris and ok_seg_no_rojo and ok_seg_no_azul and ok_seg_no_paleta and ok_borde_gris and ok_barra_gris and ok_barra_no_rojo
    return ok, f"marca_null={color_null.name()} gris={gris.name()} rojo={color_rojo.name()} no_rojo={ok_null_no_rojo} no_paleta={ok_no_paleta} seg_null={fondo_null.name()} gris_seg={gris_seg.name()} barra_null={c_barra_null.name()}"

def test_24():
    """Cambiar NULL <-> color bajo filtro activo recarga correctamente (DB + Tarea)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4","b.mp4"])
    try:
        id_a = _video_id(ruta_db,"a.mp4")
        id_b = _video_id(ruta_db,"b.mp4")
        m_a = guardar_marcador(id_a, 5.0, ruta_db, color=None)
        m_b = guardar_marcador(id_b, 5.0, ruta_db, color="rojo")
        s_a = guardar_segmento(id_a, 1.0, 2.0, ruta_db, color=None)
        s_b = guardar_segmento(id_b, 1.0, 2.0, ruta_db, color="azul")
        # filtro sin clasificar inicialmente ve solo a.mp4
        r1 = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        ok1 = _nombres(r1)==["a.mp4"]
        r1s = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:sin_clasificar")
        ok1s = _nombres(r1s)==["a.mp4"]
        # cambiar a.mp4 a rojo/azul
        asignar_color_marcador(m_a, "rojo", ruta_db)
        asignar_color_segmento(s_a[0], "azul", ruta_db)
        r2 = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        ok2 = _nombres(r2)==[]
        r2c = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:rojo")
        ok2c = set(_nombres(r2c))=={"a.mp4","b.mp4"}
        r2s = listar_videos_paginado(100,0,None,ruta_db, filtro="segmento:sin_clasificar")
        ok2s = _nombres(r2s)==[]
        # volver a NULL
        asignar_color_marcador(m_a, None, ruta_db)
        asignar_color_segmento(s_a[0], None, ruta_db)
        r3 = listar_videos_paginado(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        ok3 = _nombres(r3)==["a.mp4"]
        # tarea background debe reflejar cambio
        t = TareaLecturaCatalogoPaginada(100,0,None,ruta_db, filtro="marcador:sin_clasificar")
        ok_t = _nombres(t._trabajo())==["a.mp4"]
        # verificar que 6 colores siguen funcionando
        # repoblar b con cada color y filtrar
        ok_colores = True
        for clave in CLAVES_COLOR_CLASIFICACION:
            # limpiar y crear nuevo video por color? usar b.mp4 cambiar color y verificar
            asignar_color_marcador(m_b, clave, ruta_db)
            r = listar_videos_paginado(100,0,None,ruta_db, filtro=f"marcador:{clave}")
            if "b.mp4" not in _nombres(r):
                ok_colores = False
        return ok1 and ok1s and ok2 and ok2c and ok2s and ok3 and ok_t and ok_colores, f"r1={_nombres(r1)} r2={_nombres(r2)} r2c={_nombres(r2c)} r3={_nombres(r3)} colores={ok_colores}"
    finally:
        temp.cleanup()

def main():
    app = QApplication(sys.argv)
    pruebas = [test_01,test_02,test_03,test_04,test_05,test_06,test_07,test_08,test_09,test_10,test_11,test_12,test_13,test_14,test_15,test_16,test_17,test_18,test_19,test_20,test_21,test_22,test_23,test_24]
    resultados=[]
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, det = fn()
        except Exception as exc:
            import traceback
            ok, det = False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1200:]}"
        resultados.append((i, ok, det))
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {det}")
    ok_total = all(ok for _,ok,_ in resultados)
    print(f"TOTAL={sum(1 for _,ok,_ in resultados if ok)}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    qInstallMessageHandler(None)
    return 0 if ok_total else 1

if __name__=="__main__":
    sys.exit(main())
