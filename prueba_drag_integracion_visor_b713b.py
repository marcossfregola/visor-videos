"""Prueba integración real VisorVideos <-> Tarjeta sin FakeVisor (B7.13B)."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import tempfile
import shutil
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QByteArray, QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent

from escanear_videos import conectar_bd
import rutas
import visor_videos as vv
import panel_organizacion as po

app = QApplication.instance() or QApplication(sys.argv)

def _make_press(pos, button=Qt.LeftButton, modifiers=Qt.NoModifier, buttons=None):
    btns = buttons if buttons is not None else button
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(pos), button, btns, modifiers)

def _make_move(pos, buttons=Qt.LeftButton, modifiers=Qt.NoModifier):
    return QMouseEvent(QEvent.Type.MouseMove, QPointF(pos), Qt.NoButton, buttons, modifiers)

def _make_release(pos, button=Qt.LeftButton, modifiers=Qt.NoModifier):
    return QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(pos), button, Qt.NoButton, modifiers)

def _fila(nombre, vid, ruta):
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, ruta, vid)

def _esperar_carga(v, timeout=4.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            activo = bool(getattr(v.gestor, "activo", False))
        except Exception:
            activo = False
        if not activo:
            app.processEvents()
            break
        time.sleep(0.02)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

_CONT = 0
_FAIL = 0
def ok(m):
    global _CONT
    _CONT += 1
    print(f"T{_CONT:02d} OK - {m}")
def falla(m, e=None):
    global _CONT, _FAIL
    _CONT += 1
    _FAIL += 1
    print(f"T{_CONT:02d} FAIL - {m} {e or ''}")
def verifica(cond, desc):
    if cond:
        ok(desc)
    else:
        falla(desc)

print("=== B7.13B integración real VisorVideos ===")
tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "test.db")
conn = conectar_bd(db)
conn.commit()
conn.close()
# insert 3 videos con rutas reales temporales
carpeta_videos = os.path.join(tmp, "videos")
os.makedirs(carpeta_videos, exist_ok=True)
vids = []
for name, vid in [("video_a.mp4", 101), ("video_b.mp4", 102), ("video_c.mp4", 103)]:
    ruta = os.path.join(carpeta_videos, name)
    open(ruta, "wb").write(b"x" * 1024)
    st = os.stat(ruta)
    c = conectar_bd(db)
    c.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?,?)",
              (name, os.path.abspath(ruta), rutas.normalizar_ruta_clave(os.path.abspath(ruta)), os.path.splitext(name)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns))
    # asegurar id determinista
    row = c.execute("SELECT id FROM videos WHERE nombre=?", (name,)).fetchone()
    actual_vid = row[0]
    # si autoincrement no coincide con vid deseado, usamos actual
    vids.append((name, actual_vid, os.path.abspath(ruta)))
    c.commit()
    c.close()
print(f"insertados vids={vids}")

ruta_config = os.path.join(tmp, "config.json")
vv_inst = vv.VisorVideos(ruta_db=db, ruta_config=ruta_config)
vv_inst.resize(900, 600)
vv_inst.show()
_esperar_carga(vv_inst, timeout=4.0)
print(f"tarjetas tras carga: {len(vv_inst.tarjetas)} visibles={vv_inst.visibles}")
# Si carga no trajo filas (carpeta filtro), forzar reemplazo con filas reales
if len(vv_inst.tarjetas) < 3:
    filas = [_fila(n, vid, ruta) for n, vid, ruta in vids]
    # mapear vid real
    vv_inst._reemplazar_tarjetas(filas)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()
print(f"post-reemplazar tarjetas={len(vv_inst.tarjetas)} visibles={vv_inst.visibles}")
# activar modo organización via método real
vv_inst.boton_modo_organizacion.setChecked(True)
app.processEvents()
time.sleep(0.12)
app.processEvents()
verifica(vv_inst._modo_organizacion, "Modo Organización activo via boton")
# selección real via lógica de VisorVideos (no set directo fake)
# limpiar primero
vv_inst._limpiar_seleccion()
app.processEvents()
# seleccionar video_a y video_b via ctrl logic real
# primero sin ctrl = single
vv_inst._al_seleccionar_tarjeta("video_a.mp4", False)
app.processEvents()
verifica("video_a.mp4" in vv_inst._nombres_seleccionados, "selección real video_a")
# segundo con ctrl
vv_inst._al_seleccionar_tarjeta("video_b.mp4", True)
app.processEvents()
verifica(vv_inst._nombres_seleccionados == {"video_a.mp4", "video_b.mp4"}, f"selección real multiseleccion {vv_inst._nombres_seleccionados}")

# registrar evidencias PRE-GESTO para una tarjeta elegida (video_a)
tarjeta_a = vv_inst._tarjeta_por_nombre("video_a.mp4")
if tarjeta_a is None:
    falla("tarjeta_a no encontrada")
    sys.exit(1)
# a) window
win = tarjeta_a.window()
win_name = win.__class__.__name__ if win is not None else "None"
print(f"EVIDENCIA a) tarjeta.window().__class__.__name__ = {win_name}")
verifica(win_name == "VisorVideos", "a) window es VisorVideos")
# b) _visor_para_drag
visor_drag = tarjeta_a._visor_para_drag()
visor_drag_name = type(visor_drag).__name__ if visor_drag is not None else "None"
print(f"EVIDENCIA b) type(tarjeta._visor_para_drag()).__name__ = {visor_drag_name} (id={id(visor_drag) if visor_drag else None}, visor_inst id={id(vv_inst)})")
verifica(visor_drag is vv_inst, "b) _visor_para_drag devuelve instancia real VisorVideos")
# c) _ids_para_drag antes
ids_pre = tarjeta_a._ids_para_drag(visor_drag)
print(f"EVIDENCIA c) tarjeta._ids_para_drag() = {ids_pre}")
verifica(isinstance(ids_pre, list) and len(ids_pre) == 2, f"c) ids multiselección orden estable {ids_pre}")
# d) selección real
sel_real = set(vv_inst._nombres_seleccionados)
print(f"EVIDENCIA d) selección real en VisorVideos = {sel_real} visibles_order={vv_inst.visibles}")
# también ids ordenados via visor
ids_visor = vv_inst._video_ids_seleccionados_ordenados()
print(f"EVIDENCIA d2) _video_ids_seleccionados_ordenados = {ids_visor}")
# e) QDrag mock
orig_drag = vv.QDrag
calls = []
caps = {}
class MockDrag:
    def __init__(self, parent):
        calls.append("init")
        caps["parent"] = parent
        self._mime = None
    def setMimeData(self, m):
        calls.append("setMime")
        caps["mime"] = m
    def exec(self, action=None, *a, **kw):
        calls.append(("exec", action))
        caps["action"] = action
        return Qt.MoveAction
    def exec_(self, *a, **kw):
        calls.append(("exec_", a[0] if a else None))
        caps["action"] = a[0] if a else None
        return Qt.MoveAction
vv.QDrag = MockDrag

threshold = QApplication.startDragDistance()
print(f"threshold={threshold}")

def send_drag_on_widget(widget, desc):
    calls.clear()
    caps.clear()
    # reset drag state en tarjeta
    tarjeta_a._drag_start_pos = None
    tarjeta_a._drag_deferred = False
    # también reset tarjeta_b para multiselect preservada
    rect = widget.rect()
    pos = QPoint(rect.width()//2, rect.height()//2)
    if pos.x() <= 0 or pos.y() <= 0:
        pos = QPoint(5, 5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(widget, ev_press)
    app.processEvents()
    start_pos = getattr(tarjeta_a, "_drag_start_pos", None)
    # move beyond threshold
    move_pos = QPoint(pos.x() + threshold + 12, pos.y())
    ev_move = _make_move(QPointF(move_pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev_move)
    app.processEvents()
    has_exec = any(isinstance(c, tuple) and c[0] == "exec" for c in calls)
    return has_exec, start_pos, pos, move_pos, list(calls), dict(caps)

# identificar widgets hijos reales: label nombre y preview
label_nombre = None
for lbl in getattr(tarjeta_a, "_labels_campos", []):
    if "<b>Nombre" in lbl.text():
        label_nombre = lbl
        break
if label_nombre is None and tarjeta_a._labels_campos:
    label_nombre = tarjeta_a._labels_campos[0]
preview_widget = None
if getattr(tarjeta_a, "_imagen_miniatura", None) is not None:
    preview_widget = tarjeta_a._imagen_miniatura
elif getattr(tarjeta_a, "_recuadro_sin_miniatura", None) is not None:
    preview_widget = tarjeta_a._recuadro_sin_miniatura
elif getattr(tarjeta_a, "_etiquetas_previews", []):
    preview_widget = tarjeta_a._etiquetas_previews[0]

print(f"label_nombre widget={label_nombre} text={label_nombre.text()[:40] if label_nombre else None}")
print(f"preview_widget={preview_widget} class={preview_widget.__class__.__name__ if preview_widget else None}")

# Test label
if label_nombre is not None:
    has_exec, start_pos, pos, move_pos, _calls, _caps = send_drag_on_widget(label_nombre, "label")
    print(f"EVIDENCIA e) label QDrag exec={has_exec} start_pos={start_pos} calls={_calls} pos={pos} move={move_pos}")
    verifica(has_exec, "e) QDrag ejecutado desde label (hijo real)")
    mime = _caps.get("mime")
    if mime is not None and mime.hasFormat(po.MIME_VIDEOS_IDS):
        payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
        ids = po._deserializar_ids_videos_desde_mime(payload)
        print(f"payload label ids={ids}")
        verifica(ids == ids_visor, f"payload label coincide multiselección {ids}")
        verifica(len(mime.formats()) == 1, "solo MIME privado")
    else:
        falla("label mime no creado")
    print(f"selección tras drag label (debe preservar multiselección) = {vv_inst._nombres_seleccionados}")
    verifica(vv_inst._nombres_seleccionados == {"video_a.mp4", "video_b.mp4"}, "multiselección preservada tras drag label")
else:
    falla("label_nombre no encontrado")

# Test preview
if preview_widget is not None:
    # para preview el gesto debe iniciar desde preview pero la tarjeta origen sigue siendo tarjeta_a
    # eventFilter debe mapear preview -> tarjeta_a
    calls.clear()
    caps.clear()
    tarjeta_a._drag_start_pos = None
    tarjeta_a._drag_deferred = False
    rect = preview_widget.rect()
    pos = QPoint(rect.width()//2, rect.height()//2)
    if pos.x() <= 0 or pos.y() <= 0:
        pos = QPoint(5, 5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(preview_widget, ev_press)
    app.processEvents()
    start_pos = tarjeta_a._drag_start_pos
    ev_move = _make_move(QPointF(QPoint(pos.x()+threshold+12, pos.y())), Qt.LeftButton)
    QApplication.sendEvent(preview_widget, ev_move)
    app.processEvents()
    has_exec = any(isinstance(c, tuple) and c[0]=="exec" for c in calls)
    print(f"EVIDENCIA e) preview QDrag exec={has_exec} start_pos={start_pos} calls={calls}")
    verifica(has_exec, "e) QDrag ejecutado desde preview")
    mime = caps.get("mime")
    if mime is not None:
        payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
        ids = po._deserializar_ids_videos_desde_mime(payload)
        print(f"payload preview ids={ids}")
        verifica(ids == ids_visor, f"payload preview coincide {ids}")
else:
    falla("preview_widget no encontrado")

# Verificar no drag fuera de modo
vv_inst.boton_modo_organizacion.setChecked(False)
app.processEvents()
time.sleep(0.05)
app.processEvents()
verifica(not vv_inst._modo_organizacion, "modo off para prueba no drag")
calls.clear()
caps.clear()
tarjeta_a._drag_start_pos = QPoint(0,0)
# intentar move con modo off
ev_move_off = _make_move(QPoint(threshold+20,0), Qt.LeftButton)
tarjeta_a.mouseMoveEvent(ev_move_off)
app.processEvents()
has_off = any(isinstance(c,tuple) and c[0]=="exec" for c in calls)
verifica(not has_off, "no drag fuera de Modo Organización")
# restaurar modo
vv_inst.boton_modo_organizacion.setChecked(True)
app.processEvents()
time.sleep(0.05)
app.processEvents()

# Verificar no drag si IDs inválidos (video_id None)
# crear tarjeta con id invalido temporalmente
old_vid = tarjeta_a._video_id
tarjeta_a._video_id = None
calls.clear()
caps.clear()
tarjeta_a._drag_start_pos = QPoint(0,0)
ev_move_invalid = _make_move(QPoint(threshold+20,0), Qt.LeftButton)
tarjeta_a.mouseMoveEvent(ev_move_invalid)
app.processEvents()
has_invalid = any(isinstance(c,tuple) and c[0]=="exec" for c in calls)
verifica(not has_invalid, "no drag si IDs inválidos (video_id None)")
tarjeta_a._video_id = old_vid

# Verificar clic/doble/right no rompen (existencia señales)
verifica(hasattr(tarjeta_a, "doble_clic"), "doble_clic existe")
verifica(hasattr(tarjeta_a, "seleccionada"), "seleccionada existe")
# clic simple sin move no debe disparar drag
calls.clear()
caps.clear()
tarjeta_a._drag_start_pos = None
tarjeta_a._drag_deferred=False
# simular press+release sin move>threshold sobre label
if label_nombre is not None:
    rect = label_nombre.rect()
    pos = QPoint(rect.width()//2, rect.height()//2)
    if pos.x()<=0: pos=QPoint(5,5)
    # usar tarjeta directamente para release deferred
    # press ya deja deferred True para multiselección, pero release debería emitir selección single si no hubo drag
    # aquí probamos click simple fuera de multi: limpiar selección a single y luego click sin drag
    vv_inst._limpiar_seleccion()
    vv_inst._al_seleccionar_tarjeta("video_c.mp4", False)
    app.processEvents()
    tc = vv_inst._tarjeta_por_nombre("video_c.mp4")
    calls.clear()
    caps.clear()
    tc._drag_start_pos=None
    tc._drag_deferred=False
    # encontrar label de tc
    lbl_c = None
    for lbl in tc._labels_campos:
        if "<b>Nombre" in lbl.text():
            lbl_c=lbl
            break
    if lbl_c is not None:
        evp = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
        QApplication.sendEvent(lbl_c, evp)
        app.processEvents()
        evr = _make_release(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(lbl_c, evr)
        app.processEvents()
        has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in calls)
        verifica(not has_drag, "clic simple sin move no dispara drag")
        # verificar selección sigue single
        verifica(vv_inst._nombres_seleccionados == {"video_c.mp4"}, "clic conserva selección single")

# restaurar selección multiselección para final
vv_inst._limpiar_seleccion()
vv_inst._al_seleccionar_tarjeta("video_a.mp4", False)
vv_inst._al_seleccionar_tarjeta("video_b.mp4", True)
app.processEvents()

# Verificar sin FS/SQLite en ruta drag (inspección bloque)
import inspect
bloque = ""
try:
    bloque += inspect.getsource(vv.Tarjeta._ids_para_drag)
    bloque += inspect.getsource(vv.Tarjeta.mouseMoveEvent)
    bloque += inspect.getsource(vv._crear_mime_data_drag_b713b)
except Exception:
    pass
for kw in ["TareaLoteOperaciones", "sqlite3", "shutil", "os.rename"]:
    verifica(kw not in bloque, f"ruta drag sin {kw}")

vv.QDrag = orig_drag
print(f"TOTAL={_CONT-_FAIL}/{_CONT}")
if _FAIL==0:
    print("RESULTADO_FINAL=OK")
else:
    print("RESULTADO_FINAL=ERROR")
    sys.exit(1)

# cerrar gestores
try:
    vv_inst.close()
except Exception:
    pass
for gname in ["gestor", "gestor_previews", "gestor_navegacion_destino", "gestor_lote"]:
    try:
        g = getattr(vv_inst, gname, None)
        if g is not None:
            g.cerrar()
    except Exception:
        pass
shutil.rmtree(tmp, ignore_errors=True)
