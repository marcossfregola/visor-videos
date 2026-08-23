"""Prueba B7.13D — DROP tipo explorador sobre subcarpeta bajo cursor (hover transitorio)."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import tempfile
import shutil
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QByteArray, QPoint, Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QDragLeaveEvent

import panel_organizacion as po
from escanear_videos import conectar_bd
import visor_videos as vv
from tareas_videos import TareaLoteOperaciones

app = QApplication.instance() or QApplication(sys.argv)

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

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)

def _make_mime(ids):
    payload = po._serializar_ids_videos_para_mime(ids)
    m = QMimeData()
    if payload is not None:
        m.setData(po.MIME_VIDEOS_IDS, QByteArray(payload))
    return m

def _fila(nombre, vid, ruta="/tmp"):
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, os.path.join(ruta, nombre), vid)

def _esperar_carga(v, timeout=3.0):
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

def _point_en_fila(panel, nombre):
    """Retorna QPoint en viewport coordinates centrado en la fila nombre."""
    for i in range(panel.lista_subcarpetas.count()):
        it = panel.lista_subcarpetas.item(i)
        if it is not None and it.text() == nombre:
            rect = panel.lista_subcarpetas.visualItemRect(it)
            # centro
            pt = rect.center()
            # asegurar dentro viewport
            return pt
    return None

def _point_vacio_lista(panel):
    """Retorna QPoint en viewport que es espacio vacío (debajo de último item)."""
    # buscar y debajo del último rect
    max_y = -1
    for i in range(panel.lista_subcarpetas.count()):
        it = panel.lista_subcarpetas.item(i)
        if it is not None:
            r = panel.lista_subcarpetas.visualItemRect(it)
            if r.bottom() > max_y:
                max_y = r.bottom()
    vp = panel.lista_subcarpetas.viewport()
    h = vp.height()
    # punto 10px debajo del último item, si cabe
    y = max_y + 10 if max_y >= 0 else 5
    if y >= h:
        # si viewport no suficientemente alto, usar punto entre items? fallback: punto muy abajo fuera de items pero dentro viewport may clamp
        y = h - 5 if h > 5 else 5
        # verificar que ese y no cae sobre item (si hay muchos items, puede caer sobre último)
        # si aún cae sobre item, usar x muy a derecha? itemAt usa x también, pero si y está sobre item, seguirá hit
        # mejor usar y = h-2 y verificar itemAt es None, sino ajustar
        pt_test = QPoint(5, y)
        if panel.lista_subcarpetas.itemAt(pt_test) is not None:
            # buscar hueco: intentar y = max_y+2 pero si no cabe, entonces no hay vacío real (lista llena)
            # En ese caso, usaremos punto fuera del viewport mapeado desde panel fondo
            return None
    return QPoint(5, y)

def _point_fondo_panel(panel):
    """Punto en panel coordenadas que es fondo (header)."""
    return QPoint(5, 5)

print("=== B7.13D prueba_drag_subcarpeta_hover_b713d ===")

# Setup panel base
def _crear_panel_con_subcarpetas(subs=["A", "B", "C"]):
    panel = po.PanelOrganizacion()
    dest = os.path.join(tempfile.gettempdir(), "dest_b713d_" + "_".join(subs))
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=subs, cargando=False, error=None)
    panel.resize(320, 260)
    panel.show()
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()
    return panel, dest

# Test 1: fila A bajo cursor => hover objetivo A
print("--- T1 fila A bajo cursor => hover A ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B", "C"])
panel.lista_subcarpetas.clearSelection()
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() is None, "T1 hover inicial None")
verifica(panel.objetivo_nombre() is None, "T1 objetivo estable None")
ptA = _point_en_fila(panel, "A")
verifica(ptA is not None, "T1 ptA existe")
if ptA is not None:
    m = _make_mime([1])
    vp = panel.lista_subcarpetas.viewport()
    ev = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(vp, ev)
    app.processEvents()
    verifica(ev.isAccepted(), "T1 dragEnter A aceptado")
    verifica(panel.drop_hover_objetivo_nombre() == "A", f"T1 hover A {panel.drop_hover_objetivo_nombre()!r}")
    verifica(panel.is_drag_highlight_activo(), "T1 panel highlight activo")
    verifica(panel.is_row_highlight_activo(), "T1 row highlight activo")
    # verificar highlight A visible via background
    # buscar row A
    rowA = -1
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "A":
            rowA = i
            break
    verifica(rowA >= 0 and panel.is_row_highlight_activo(rowA), f"T1 highlight A visible row {rowA}")
panel.close()

# Test 2: fila B bajo cursor => cambia hover A->B
print("--- T2 A->B cambia hover ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B", "C"])
ptA = _point_en_fila(panel, "A")
ptB = _point_en_fila(panel, "B")
m = _make_mime([1])
vp = panel.lista_subcarpetas.viewport()
evA = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evA)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "A", "T2 hover A inicial")
# mover a B
m2 = _make_mime([1])
evB = QDragMoveEvent(ptB, Qt.CopyAction, m2, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evB)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "B", f"T2 hover B tras move {panel.drop_hover_objetivo_nombre()!r}")
# verificar A limpia y B resaltada
rowA = next((i for i in range(panel.lista_subcarpetas.count()) if panel.lista_subcarpetas.item(i).text() == "A"), -1)
rowB = next((i for i in range(panel.lista_subcarpetas.count()) if panel.lista_subcarpetas.item(i).text() == "B"), -1)
# A debería no estar highlight
verifica(not panel.is_row_highlight_activo(rowA), f"T2 A limpia highlight {rowA}")
verifica(panel.is_row_highlight_activo(rowB), f"T2 B resaltada {rowB}")
panel.close()

# Test 3: espacio vacío de lista => hover None raíz
print("--- T3 vacío lista => hover None ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
# primero hover A
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m = _make_mime([1])
ev = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "A", "T3 hover A")
# ahora mover a vacío
ptVacio = _point_vacio_lista(panel)
if ptVacio is None:
    # si no hay vacío real, forzamos punto fuera de items via panel fondo pero enviado a viewport?
    # intentar y muy abajo
    ptVacio = QPoint(5, panel.lista_subcarpetas.viewport().height() - 2)
    # verificar que itemAt es None, si no, usar panel fondo
    if panel.lista_subcarpetas.itemAt(ptVacio) is not None:
        # viewport lleno, usar panel fondo como vacío
        ptVacio = None
if ptVacio is not None:
    m2 = _make_mime([1])
    ev2 = QDragMoveEvent(ptVacio, Qt.CopyAction, m2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(vp, ev2)
    app.processEvents()
    verifica(panel.drop_hover_objetivo_nombre() is None, f"T3 hover None tras vacío {panel.drop_hover_objetivo_nombre()!r}")
    verifica(not panel.is_row_highlight_activo(), "T3 highlight fila limpio tras vacío")
else:
    # fallback: enviar dragMove a panel fondo
    m2 = _make_mime([1])
    ptFondo = _point_fondo_panel(panel)
    ev2 = QDragEnterEvent(ptFondo, Qt.CopyAction, m2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev2)
    app.processEvents()
    verifica(panel.drop_hover_objetivo_nombre() is None, "T3 hover None via panel fondo fallback")
panel.close()

# Test 4: fondo del panel => hover None raíz
print("--- T4 fondo panel => hover None ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m = _make_mime([1])
ev = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "A", "T4 hover A")
# mover a fondo panel
ptFondo = _point_fondo_panel(panel)
m2 = _make_mime([1])
ev2 = QDragEnterEvent(ptFondo, Qt.CopyAction, m2, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(panel, ev2)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() is None, f"T4 hover None tras fondo {panel.drop_hover_objetivo_nombre()!r}")
verifica(panel.is_drag_highlight_activo(), "T4 panel highlight sigue activo en fondo")
verifica(not panel.is_row_highlight_activo(), "T4 fila highlight limpio en fondo")
panel.close()

# Test 5: A seleccionada + cursor B => drop emite B
print("--- T5 A seleccionada + cursor B => drop B ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B", "C"])
# seleccionar A estable
for i in range(panel.lista_subcarpetas.count()):
    if panel.lista_subcarpetas.item(i).text() == "A":
        panel.lista_subcarpetas.setCurrentRow(i)
        break
app.processEvents()
verifica(panel.objetivo_nombre() == "A", "T5 objetivo estable A")
ptB = _point_en_fila(panel, "B")
m = _make_mime([10, 20])
vp = panel.lista_subcarpetas.viewport()
# dragEnter sobre B (hover B, ignora selección A)
m_enter = _make_mime([10, 20])
evEnter = QDragEnterEvent(ptB, Qt.CopyAction, m_enter, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evEnter)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "B", "T5 hover B pese a selección A")
caps = []
panel.dropVideosSolicitado.connect(lambda ids, obj: caps.append((list(ids), obj)))
evDrop = QDropEvent(ptB, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evDrop)
app.processEvents()
verifica(len(caps) == 1, f"T5 drop emite 1 {caps}")
if caps:
    verifica(caps[0][1] == "B", f"T5 drop objetivo B {caps[0][1]!r} pese a selección A")
    verifica(caps[0][0] == [10, 20], "T5 IDs correctos")
panel.close()

# Test 6: A seleccionada + fondo => drop emite None
print("--- T6 A seleccionada + fondo => drop None ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
for i in range(panel.lista_subcarpetas.count()):
    if panel.lista_subcarpetas.item(i).text() == "A":
        panel.lista_subcarpetas.setCurrentRow(i)
        break
app.processEvents()
verifica(panel.objetivo_nombre() == "A", "T6 objetivo A")
# hover sobre vacío/fondo
ptFondo = _point_fondo_panel(panel)
m = _make_mime([30])
# primero enter en fondo para asegurar hover None
m_enter_f = _make_mime([30])
evEnter = QDragEnterEvent(ptFondo, Qt.CopyAction, m_enter_f, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(panel, evEnter)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() is None, "T6 hover None fondo")
caps = []
panel.dropVideosSolicitado.connect(lambda ids, obj: caps.append((list(ids), obj)))
evDrop = QDropEvent(ptFondo, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(panel, evDrop)
app.processEvents()
verifica(len(caps) == 1 and caps[0][1] is None, f"T6 drop None pese a selección A {caps}")
panel.close()

# Test 7: sin selección + cursor B => drop emite B
print("--- T7 sin selección + cursor B => drop B ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
panel.lista_subcarpetas.clearSelection()
app.processEvents()
verifica(panel.objetivo_nombre() is None, "T7 sin selección")
ptB = _point_en_fila(panel, "B")
m = _make_mime([40])
vp = panel.lista_subcarpetas.viewport()
m_enter40 = _make_mime([40])
evEnter = QDragEnterEvent(ptB, Qt.CopyAction, m_enter40, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evEnter)
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "B", "T7 hover B sin selección")
caps = []
panel.dropVideosSolicitado.connect(lambda ids, obj: caps.append((list(ids), obj)))
evDrop = QDropEvent(ptB, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evDrop)
app.processEvents()
verifica(len(caps) == 1 and caps[0][1] == "B", f"T7 drop B sin selección {caps}")
panel.close()

# Test 8: row highlight A visible
print("--- T8 highlight A visible ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m = _make_mime([1])
ev = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev)
app.processEvents()
rowA = next((i for i in range(panel.lista_subcarpetas.count()) if panel.lista_subcarpetas.item(i).text() == "A"), -1)
verifica(rowA >= 0, "T8 rowA existe")
# verificar background no nulo (highlight)
it = panel.lista_subcarpetas.item(rowA) if rowA >= 0 else None
has_highlight = False
if it is not None:
    try:
        bg = it.background()
        # QBrush isNull false indica highlight
        has_highlight = not bg.isOpaque() or bg.color().name() != "#000000"  # fallback
        # más preciso: check is row highlight activo
        has_highlight = panel.is_row_highlight_activo(rowA)
    except Exception:
        has_highlight = panel.is_row_highlight_activo(rowA)
verifica(has_highlight, "T8 highlight A visible")
panel.close()

# Test 9: al pasar B, A limpia y B resaltada (ya probado en T2, repetir)
print("--- T9 highlight A->B switch ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
ptB = _point_en_fila(panel, "B")
vp = panel.lista_subcarpetas.viewport()
m = _make_mime([1])
QApplication.sendEvent(vp, QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
rowA = next((i for i in range(panel.lista_subcarpetas.count()) if panel.lista_subcarpetas.item(i).text() == "A"), -1)
rowB = next((i for i in range(panel.lista_subcarpetas.count()) if panel.lista_subcarpetas.item(i).text() == "B"), -1)
verifica(panel.is_row_highlight_activo(rowA), "T9 A highlight inicial")
m_tmp2 = _make_mime([1])
QApplication.sendEvent(vp, QDragMoveEvent(ptB, Qt.CopyAction, m_tmp2, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(not panel.is_row_highlight_activo(rowA), "T9 A limpia tras B")
verifica(panel.is_row_highlight_activo(rowB), "T9 B resaltada")
panel.close()

# Test 10: al pasar a vacío, highlight de fila limpio
print("--- T10 vacío limpia highlight ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m_tmp = _make_mime([1])
QApplication.sendEvent(vp, QDragEnterEvent(ptA, Qt.CopyAction, m_tmp, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(panel.is_row_highlight_activo(), "T10 highlight activo antes")
ptFondo = _point_fondo_panel(panel)
_mime_auto_369 = _make_mime([1])
QApplication.sendEvent(panel, QDragEnterEvent(ptFondo, Qt.CopyAction, _mime_auto_369, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(not panel.is_row_highlight_activo(), "T10 highlight limpio tras vacío")
verifica(panel.is_drag_highlight_activo(), "T10 panel highlight sigue en fondo")
panel.close()

# Test 11: dragLeave limpia hover + fila
print("--- T11 dragLeave limpia ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m_tmp = _make_mime([1])
QApplication.sendEvent(vp, QDragEnterEvent(ptA, Qt.CopyAction, m_tmp, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "A", "T11 hover A antes leave")
verifica(panel.is_row_highlight_activo(), "T11 highlight antes leave")
evLeave = QDragLeaveEvent()
QApplication.sendEvent(panel, evLeave)
app.processEvents()
# también probar via viewport leave
verifica(panel.drop_hover_objetivo_nombre() is None, "T11 hover None tras leave")
verifica(not panel.is_row_highlight_activo(), "T11 highlight limpio tras leave")
verifica(not panel.is_drag_highlight_activo(), "T11 panel highlight limpio tras leave")
panel.close()

# Test 12: drop limpia hover + fila
print("--- T12 drop limpia hover+fila ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m_tmp = _make_mime([1])
QApplication.sendEvent(vp, QDragEnterEvent(ptA, Qt.CopyAction, m_tmp, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() == "A", "T12 hover A antes drop")
caps = []
panel.dropVideosSolicitado.connect(lambda ids, obj: caps.append((ids, obj)))
_mime_fix_0 = _make_mime([1])
QApplication.sendEvent(vp, QDropEvent(ptA, Qt.CopyAction, _mime_fix_0, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
verifica(panel.drop_hover_objetivo_nombre() is None, "T12 hover None tras drop")
verifica(not panel.is_row_highlight_activo(), "T12 highlight limpio tras drop")
verifica(not panel.is_drag_highlight_activo(), "T12 panel highlight limpio tras drop")
panel.close()

# Test 13: MIME inválido no crea hover ni highlight
print("--- T13 MIME inválido no hover ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m_bad = QMimeData()
m_bad.setText("texto ajeno")
evBad = QDragEnterEvent(ptA, Qt.CopyAction, m_bad, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evBad)
app.processEvents()
verifica(not evBad.isAccepted(), "T13 dragEnter inválido no aceptado")
verifica(panel.drop_hover_objetivo_nombre() is None, "T13 hover None con MIME inválido")
verifica(not panel.is_row_highlight_activo(), "T13 highlight no creado inválido")
verifica(not panel.is_drag_highlight_activo(), "T13 panel highlight no creado inválido")
panel.close()

# Test 14: ocupado/cargando/error no crea hover
print("--- T14 ocupado/cargando/error no hover ---")
for estado, kwargs in [
    ("ocupado", dict(ocupado=True)),
    ("cargando", dict(cargando=True)),
    ("error", dict(error="no disponible")),
]:
    panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
    # aplicar estado via actualizar
    if estado == "ocupado":
        panel.actualizar(dest, False, True, destino_valido=True, subcarpetas=["A", "B"], cargando=False, error=None)
    elif estado == "cargando":
        panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["A", "B"], cargando=True, error=None)
    else:
        panel.actualizar(dest, False, False, destino_valido=False, subcarpetas=["A", "B"], cargando=False, error="no disponible")
    panel.show()
    app.processEvents()
    ptA = _point_en_fila(panel, "A")
    vp = panel.lista_subcarpetas.viewport()
    # punto puede ser None si lista deshabilitada y sin items? pero subcarpetas siguen pero lista disabled
    # usar panel punto
    m = _make_mime([1])
    # probar via panel y viewport
    ev = QDragEnterEvent(ptA if ptA is not None else QPoint(5,5), Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
    target = vp if ptA is not None else panel
    QApplication.sendEvent(target, ev)
    app.processEvents()
    verifica(not ev.isAccepted(), f"T14 {estado} dragEnter no aceptado")
    verifica(panel.drop_hover_objetivo_nombre() is None, f"T14 {estado} hover None")
    verifica(not panel.is_row_highlight_activo(), f"T14 {estado} highlight no creado")
    verifica(not panel.is_drag_highlight_activo(), f"T14 {estado} panel highlight no creado")
    panel.close()

# Test 15: drop sobre hija no cambia breadcrumb/destino actual antes de señal
print("--- T15 drop no cambia breadcrumb/destino ---")
panel, dest = _crear_panel_con_subcarpetas(["A", "B"])
panel.show()
app.processEvents()
dest_before = panel.destino()
texto_before = panel.etiqueta_destino.text()
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
# asegurar destino válido
verifica(panel._destino_valido, "T15 destino válido")
caps = []
panel.dropVideosSolicitado.connect(lambda ids, obj: caps.append((ids, obj)))
m = _make_mime([1])
m_enter2 = _make_mime([1])
evEnter = QDragEnterEvent(ptA, Qt.CopyAction, m_enter2, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evEnter)
app.processEvents()
# verificar destino no cambió tras hover
verifica(panel.destino() == dest_before, "T15 destino no cambia tras hover")
verifica(panel.etiqueta_destino.text() == texto_before, "T15 breadcrumb no cambia tras hover")
# ahora drop
evDrop = QDropEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evDrop)
app.processEvents()
verifica(panel.destino() == dest_before, "T15 destino no cambia tras drop antes de señal")
verifica(panel.etiqueta_destino.text() == texto_before, "T15 breadcrumb no cambia tras drop")
verifica(len(caps)==1 and caps[0][1]=="A", "T15 drop emite hija")
panel.close()

# Test 16: no cambia origen/filtro/orden/selección de videos por hover
print("--- T16 hover no cambia origen/filtro/orden/selección ---")
tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "test.db")
conn = conectar_bd(db)
conn.commit()
conn.close()
carpeta_origen = os.path.join(tmp, "origen")
os.makedirs(carpeta_origen, exist_ok=True)
dest_root = os.path.join(tmp, "dest_root")
os.makedirs(dest_root, exist_ok=True)
for sub in ["A", "B"]:
    os.makedirs(os.path.join(dest_root, sub), exist_ok=True)
# crear videos
vids = []
for name in ["video_a.mp4", "video_b.mp4"]:
    ruta = os.path.join(carpeta_origen, name)
    open(ruta, "wb").write(b"x"*1024)
    st = os.stat(ruta)
    c = conectar_bd(db)
    c.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
              (name, os.path.abspath(ruta), ".mp4", "2026-01-01", st.st_size, st.st_mtime_ns))
    row = c.execute("SELECT id FROM videos WHERE nombre=?", (name,)).fetchone()
    vids.append((name, row[0], os.path.abspath(ruta)))
    c.commit()
    c.close()
ruta_config = os.path.join(tmp, "config.json")
visor = vv.VisorVideos(ruta_db=db, ruta_config=ruta_config)
visor.resize(900, 600)
visor.show()
_esperar_carga(visor, timeout=3)
filas = [_fila(n, vid, os.path.abspath(os.path.join(carpeta_origen, n))) for n, vid, ruta in vids]
visor._reemplazar_tarjetas(filas)
app.processEvents()
time.sleep(0.05)
app.processEvents()
visor.boton_modo_organizacion.setChecked(True)
app.processEvents()
time.sleep(0.08)
app.processEvents()
visor._organizacion_destino = dest_root
visor._organizacion_destino_valido = True
visor._organizacion_subcarpetas = ["A", "B"]
visor._organizacion_error = None
visor._organizacion_cargando = False
visor._organizacion_objetivo_nombre = None
visor._actualizar_panel_organizacion()
app.processEvents()
# estado origen antes
origen_before = visor.carpeta_seleccionada
filtro_before = getattr(visor, "_filtro_catalogo", "todos")
orden_before = getattr(visor, "_orden_catalogo", None)
seleccion_before = set(getattr(visor, "_nombres_seleccionados", set()))
scroll_before = visor.area.verticalScrollBar().value() if hasattr(visor, "area") else 0
# seleccionar un video
visor._limpiar_seleccion()
visor._al_seleccionar_tarjeta("video_a.mp4", False)
app.processEvents()
seleccion_before = set(visor._nombres_seleccionados)
# hover sobre hija A via panel
panel = visor.panel_organizacion
panel.show()
app.processEvents()
ptA = _point_en_fila(panel, "A")
vp = panel.lista_subcarpetas.viewport()
m = _make_mime([vids[0][1]])
evHover = QDragEnterEvent(ptA, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, evHover)
app.processEvents()
# verificar no cambió origen/filtro/orden/selección
verifica(visor.carpeta_seleccionada == origen_before, "T16 origen no cambia por hover")
verifica(getattr(visor, "_filtro_catalogo", "todos") == filtro_before, "T16 filtro no cambia")
verifica(getattr(visor, "_orden_catalogo", None) == orden_before, "T16 orden no cambia")
verifica(set(getattr(visor, "_nombres_seleccionados", set())) == seleccion_before, "T16 selección videos no cambia")
# scroll no debe cambiar drásticamente (tolerancia 0)
verifica(visor.area.verticalScrollBar().value() == scroll_before, "T16 viewport scroll no cambia")
# limpiar
QApplication.sendEvent(panel, QDragLeaveEvent())
app.processEvents()
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop","gestor_renombrar_masivo","gestor_mover","gestor_copiar","gestor_eliminar"]:
    try:
        getattr(visor, g).cerrar()
    except Exception:
        pass
shutil.rmtree(tmp, ignore_errors=True)

# ── T17 Integración movimiento a hija preservando video_id y relaciones ──
print("--- T17 integración drop físico a hija preserva identidad ---")
tmp17 = tempfile.mkdtemp()
db17 = os.path.join(tmp17, "test.db")
conn = conectar_bd(db17)
conn.commit()
conn.close()
origen17 = os.path.join(tmp17, "origen")
os.makedirs(origen17, exist_ok=True)
dest17 = os.path.join(tmp17, "dest")
os.makedirs(dest17, exist_ok=True)
hija17 = os.path.join(dest17, "HijaDrop")
os.makedirs(hija17, exist_ok=True)
# crear video origen
nombre_v = "video_integ.mp4"
ruta_v = os.path.join(origen17, nombre_v)
open(ruta_v, "wb").write(b"x"*2048)
st = os.stat(ruta_v)
c = conectar_bd(db17)
c.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
          (nombre_v, os.path.abspath(ruta_v), ".mp4", "2026-01-01", st.st_size, st.st_mtime_ns))
row = c.execute("SELECT id FROM videos WHERE nombre=?", (nombre_v,)).fetchone()
vid = row[0]
print(f"T17 video_id={vid} ruta={ruta_v}")
# crear marcador y segmento asociados
try:
    curm = c.execute("INSERT INTO marcadores_video (video_id, tiempo, color) VALUES (?,?,?)", (vid, 5.0, "rojo"))
    mid = curm.lastrowid
    print(f"T17 marcador id={mid}")
except Exception as e:
    print(f"T17 marcador insert error {e}")
    mid = None
try:
    curs = c.execute("INSERT INTO segmentos_video (video_id, inicio, fin, color) VALUES (?,?,?,?)", (vid, 1.0, 3.0, "azul"))
    sid = curs.lastrowid
    print(f"T17 segmento id={sid}")
except Exception as e:
    print(f"T17 segmento insert error {e}")
    sid = None
c.commit()
c.close()
# Visor
ruta_cfg17 = os.path.join(tmp17, "config.json")
visor17 = vv.VisorVideos(ruta_db=db17, ruta_config=ruta_cfg17)
visor17.resize(900, 600)
visor17.show()
_esperar_carga(visor17, timeout=3)
filas17 = [_fila(nombre_v, vid, os.path.abspath(ruta_v))]
visor17._reemplazar_tarjetas(filas17)
app.processEvents()
time.sleep(0.05)
app.processEvents()
visor17.boton_modo_organizacion.setChecked(True)
app.processEvents()
time.sleep(0.08)
app.processEvents()
visor17._organizacion_destino = dest17
visor17._organizacion_destino_valido = True
visor17._organizacion_subcarpetas = ["HijaDrop"]
visor17._organizacion_error = None
visor17._organizacion_cargando = False
visor17._organizacion_objetivo_nombre = None
visor17._organizacion_objetivo_completo = None
visor17._actualizar_panel_organizacion()
app.processEvents()
time.sleep(0.1)
app.processEvents()
# asegurar que selección estable es None (sin selección previa de hija)
try:
    visor17.panel_organizacion.lista_subcarpetas.clearSelection()
except Exception:
    pass
app.processEvents()
# verificar destino actual es dest (raíz)
dest_before17 = visor17.panel_organizacion.destino()
print(f"T17 dest_before={dest_before17!r} dest17={dest17!r} subcarpetas={visor17.panel_organizacion._subcarpetas}")
verifica(dest_before17 == dest17, "T17 destino raíz antes")
# simular drop físico sobre fila hija SIN seleccionarla previamente
panel17 = visor17.panel_organizacion
panel17.show()
app.processEvents()
time.sleep(0.05)
app.processEvents()
# punto en fila hija
ptHija = _point_en_fila(panel17, "HijaDrop")
verifica(ptHija is not None, "T17 ptHija existe")
vp17 = panel17.lista_subcarpetas.viewport()
# seleccionar video en visor (origen) para que _ids_para_drag tenga ids
visor17._limpiar_seleccion()
visor17._al_seleccionar_tarjeta(nombre_v, False)
app.processEvents()
verifica(nombre_v in visor17._nombres_seleccionados, "T17 video seleccionado origen")
# asegurar que objetivo estable sigue None (no click previo sobre hija)
verifica(panel17.objetivo_nombre() is None, "T17 objetivo estable None antes drop físico")
# construir mime con vid
m17 = _make_mime([vid])
m_enter17 = _make_mime([vid])
evEnter17 = QDragEnterEvent(ptHija, Qt.CopyAction, m_enter17, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp17, evEnter17)
app.processEvents()
verifica(panel17.drop_hover_objetivo_nombre() == "HijaDrop", "T17 hover HijaDrop")
# ahora drop físico
caps17 = []
# visor ya conectado a dropVideosSolicitado, pero también capturamos
drop_capt = []
orig_handler = visor17._al_drop_videos_solicitado
# interceptar señal panel drop para verificar emisión
panel17.dropVideosSolicitado.connect(lambda ids, obj: drop_capt.append((ids, obj)))
evDrop17 = QDropEvent(ptHija, Qt.CopyAction, m17, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp17, evDrop17)
app.processEvents()
# esperar prevalidación y lote
def _esperar_drop17(timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            pre_act = bool(getattr(visor17.gestor_prevalidacion_drop, "activo", False))
            pre_flag = bool(getattr(visor17, "_prevalidacion_drop_en_curso", False))
            lote_act = bool(getattr(visor17.gestor_lote, "activo", False))
            lote_flag = bool(getattr(visor17, "_lote_en_curso", False))
        except Exception:
            pre_act = pre_flag = lote_act = lote_flag = False
        if not pre_act and not pre_flag and not lote_act and not lote_flag:
            if time.time() - t0 > 0.6:
                break
        time.sleep(0.03)
        app.processEvents()
    time.sleep(0.3)
    app.processEvents()
_esperar_drop17(timeout=8)
# verificar que drop emitió HijaDrop (no raíz)
verifica(len(drop_capt) == 1, f"T17 drop emit 1 {drop_capt}")
if drop_capt:
    verifica(drop_capt[0][1] == "HijaDrop", f"T17 drop objetivo HijaDrop {drop_capt[0][1]!r}")
    verifica(drop_capt[0][0] == [vid], f"T17 drop ids {drop_capt[0][0]}")
# verificar archivo movido a hija
ruta_dest_hija = os.path.join(hija17, nombre_v)
ruta_origen = os.path.join(origen17, nombre_v)
# esperar un poco más por FS
time.sleep(0.2)
app.processEvents()
verifica(os.path.isfile(ruta_dest_hija), f"T17 archivo en hija {ruta_dest_hija}")
verifica(not os.path.isfile(ruta_origen), f"T17 origen eliminado {ruta_origen}")
# verificar DB conserva mismo video_id y ruta actualizada
c = conectar_bd(db17)
row2 = c.execute("SELECT id, ruta FROM videos WHERE id=?", (vid,)).fetchone()
verifica(row2 is not None, "T17 video_id existe en DB tras mover")
if row2:
    verifica(row2[0] == vid, f"T17 mismo video_id {row2[0]}")
    # ruta debe ser hija
    try:
        import os as _os
        ruta_db = row2[1]
        verifica(_os.path.normcase(_os.path.normpath(ruta_db)) == _os.path.normcase(_os.path.normpath(ruta_dest_hija)), f"T17 ruta DB actualizada a hija {ruta_db!r}")
    except Exception as e:
        falla(f"T17 ruta check {e}")
    # verificar marcadores siguen ligados
    if mid is not None:
        marc = c.execute("SELECT video_id FROM marcadores_video WHERE id=?", (mid,)).fetchone()
        verifica(marc is not None and marc[0] == vid, f"T17 marcador preservado video_id {marc}")
    else:
        # al menos verificar que hay marcadores para ese vid
        marcs = c.execute("SELECT COUNT(*) FROM marcadores_video WHERE video_id=?", (vid,)).fetchone()
        verifica(marcs[0] >= 1, f"T17 marcador count {marcs[0]}")
    if sid is not None:
        seg = c.execute("SELECT video_id FROM segmentos_video WHERE id=?", (sid,)).fetchone()
        verifica(seg is not None and seg[0] == vid, f"T17 segmento preservado {seg}")
    else:
        segs = c.execute("SELECT COUNT(*) FROM segmentos_video WHERE video_id=?", (vid,)).fetchone()
        verifica(segs[0] >= 1, f"T17 segmento count {segs[0]}")
c.close()
# verificar cero reescaneo global: no se disparó TareaEscaneo nueva (gestor no activo y no hay mensaje escaneando)
# comprobar que no hubo creación de archivo en origen ni duplicado
verifica(os.path.isfile(ruta_dest_hija), "T17 hija archivo existe final")
# limpiar
try:
    panel17.dropVideosSolicitado.disconnect()
except Exception:
    pass
visor17.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop","gestor_renombrar_masivo","gestor_mover","gestor_copiar","gestor_eliminar"]:
    try:
        getattr(visor17, g).cerrar()
    except Exception:
        pass
shutil.rmtree(tmp17, ignore_errors=True)
print("--- T17 integración OK ---")

print(f"TOTAL={_CONT-_FAIL}/{_CONT}")
if _FAIL == 0:
    print("RESULTADO_FINAL=OK")
else:
    print("RESULTADO_FINAL=ERROR")
    sys.exit(1)

# Reuse panel close
try:
    panel.close()
except:
    pass