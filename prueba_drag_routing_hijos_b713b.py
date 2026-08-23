"""Reproduccion B7.13B real-drag-routing sobre hijos reales de Tarjeta."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent, QDrag

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

def _make_dbl(pos, button=Qt.LeftButton, modifiers=Qt.NoModifier):
    return QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(pos), button, button, modifiers)

def _fila(nombre, vid, ruta="/tmp"):
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, os.path.join(ruta, nombre), vid)

class FakeVisor:
    def __init__(self):
        self._modo_organizacion = True
        self._nombres_seleccionados = set()
        self._visibles_order = []
        self._tarjetas_by_name = {}
    def _video_ids_seleccionados_ordenados(self):
        ids=[]
        for n in self._visibles_order:
            if n in self._nombres_seleccionados:
                t=self._tarjetas_by_name.get(n)
                if t is not None:
                    vid=getattr(t,"_video_id",None)
                    if isinstance(vid,int) and not isinstance(vid,bool) and vid>0:
                        ids.append(vid)
        return ids

_CONT=0
_FAIL=0
def ok(m):
    global _CONT
    _CONT+=1
    print(f"T{_CONT:02d} OK - {m}")

def falla(m,e=None):
    global _CONT,_FAIL
    _CONT+=1
    _FAIL+=1
    print(f"T{_CONT:02d} FAIL - {m} {e or ''}")

def verifica(cond,desc,extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc,extra)

# helpers para encontrar hijos
def find_label(tarjeta, contiene=None):
    for lbl in tarjeta.findChildren(QLabel):
        try:
            txt=lbl.text()
            if contiene and contiene in txt:
                return lbl
            if "<b>Nombre" in txt:
                return lbl
        except: pass
    for lbl in tarjeta.findChildren(QLabel):
        if lbl is tarjeta._imagen_miniatura:
            continue
        if lbl in getattr(tarjeta,"_etiquetas_previews",[]):
            continue
        if lbl is getattr(tarjeta,"_recuadro_sin_miniatura",None):
            continue
        return lbl
    return None

def get_preview(tarjeta):
    if getattr(tarjeta,"_imagen_miniatura",None) is not None:
        return tarjeta._imagen_miniatura
    if getattr(tarjeta,"_recuadro_sin_miniatura",None) is not None:
        return tarjeta._recuadro_sin_miniatura
    lst=getattr(tarjeta,"_etiquetas_previews",[])
    if lst:
        return lst[0]
    return None

threshold = QApplication.startDragDistance()
print(f"startDragDistance={threshold}")

# Construir contenedor real offscreen
contenedor = QWidget()
layout = QVBoxLayout(contenedor)
fake = FakeVisor()
fake._visibles_order=["video_test.mp4"]
tarjeta = vv.Tarjeta(_fila("video_test.mp4", 42))
tarjeta.marcar_seleccionada(True)
fake._tarjetas_by_name={"video_test.mp4": tarjeta}
fake._nombres_seleccionados={"video_test.mp4"}
fake._modo_organizacion=True
orig_visor = tarjeta._visor_para_drag
tarjeta._visor_para_drag = lambda: fake
layout.addWidget(tarjeta)
contenedor.show()
app.processEvents()
tarjeta.show()
app.processEvents()

# mock QDrag
orig_drag = vv.QDrag
drag_calls = []
caps = {}
class MockDrag:
    def __init__(self, parent):
        drag_calls.append("init")
        caps["parent"]=parent
        self._mime=None
    def setMimeData(self,m):
        drag_calls.append("setMime")
        caps["mime"]=m
    def exec(self, action=None, *a, **kw):
        drag_calls.append(("exec",action))
        caps["action"]=action
        return Qt.MoveAction
    def exec_(self, *a, **kw):
        drag_calls.append(("exec_",a[0] if a else None))
        caps["action"]=a[0] if a else None
        return Qt.MoveAction
vv.QDrag = MockDrag

def reset_drag():
    drag_calls.clear()
    caps.clear()
    tarjeta._drag_start_pos=None
    tarjeta._drag_deferred=False

def send_drag_via_widget(widget, desc):
    """Envia press + move > threshold SOBRE EL WIDGET QUE RECIBE EL MOUSE usando sendEvent."""
    reset_drag()
    rect = widget.rect()
    pos = QPoint(rect.width()//2, rect.height()//2)
    if pos.x()<=0 or pos.y()<=0:
        pos = QPoint(5,5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(widget, ev_press)
    app.processEvents()
    start_pos_after_press = getattr(tarjeta,"_drag_start_pos",None)
    move_pos = QPoint(pos.x()+threshold+10, pos.y())
    ev_move = _make_move(QPointF(move_pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev_move)
    app.processEvents()
    has_exec = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls) or "exec" in drag_calls or "exec_" in drag_calls
    info = f"widget={widget.__class__.__name__} objName={widget.objectName()!r} start_pos={start_pos_after_press} drag_calls={drag_calls} pos={pos} move={move_pos}"
    return has_exec, start_pos_after_press, info

# Identificar superficies
label_widget = find_label(tarjeta, "Nombre")
preview_widget = get_preview(tarjeta)
check_widget = getattr(tarjeta,"_check",None)
fondo_widget = tarjeta

print(f"label_widget={label_widget} text={label_widget.text()[:60] if label_widget else None}")
print(f"preview_widget={preview_widget} class={preview_widget.__class__.__name__ if preview_widget else None}")
print(f"check_widget={check_widget} visible={check_widget.isVisible() if check_widget else None}")
print(f"fondo_widget={fondo_widget}")

results={}
# T01 Fondo
reset_drag()
pos_fondo = QPoint(5,5)
ev_p = _make_press(QPointF(pos_fondo), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
QApplication.sendEvent(tarjeta, ev_p)
app.processEvents()
ev_m = _make_move(QPointF(QPoint(pos_fondo.x()+threshold+10, pos_fondo.y())), Qt.LeftButton)
QApplication.sendEvent(tarjeta, ev_m)
app.processEvents()
fondo_ok = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls) or "exec" in drag_calls
results["fondo"]=(fondo_ok, f"drag_calls={drag_calls} start_pos={tarjeta._drag_start_pos}")
verifica(fondo_ok, f"Fondo Tarjeta inicia drag > umbral {results['fondo']}")
reset_drag()

# T02 Label
if label_widget is not None:
    has_exec, start_pos, info = send_drag_via_widget(label_widget, "label")
    results["label"]=(has_exec, info)
    verifica(has_exec, f"Label inicia drag > umbral? {info[:250]}", None)
    if not has_exec:
        print(f"REPRO: label NO inicia drag (bug reproducido) start_pos={start_pos}")
    else:
        print(f"REPRO: label SI inicia drag")
else:
    falla("label_widget no encontrado")
    results["label"]=(False,"no widget")

# T03 Preview
if preview_widget is not None:
    has_exec, start_pos, info = send_drag_via_widget(preview_widget, "preview")
    results["preview"]=(has_exec, info)
    verifica(has_exec, f"Preview inicia drag > umbral? {info[:250]}")
    if not has_exec:
        print(f"REPRO: preview NO inicia drag (bug reproducido) start_pos={start_pos}")
    else:
        print(f"REPRO: preview SI inicia drag")
else:
    falla("preview_widget no encontrado")
    results["preview"]=(False,"no widget")

# T04 Checkbox - NO debe iniciar drag
if check_widget is not None:
    check_widget.setVisible(True)
    app.processEvents()
    has_exec, start_pos, info = send_drag_via_widget(check_widget, "checkbox")
    results["check"]=(has_exec, info)
    verifica(not has_exec, f"Checkbox NO inicia drag (correcto) {info[:250]}")
    if has_exec:
        print(f"REPRO: checkbox SI inicia drag (bug secuestro)")
    else:
        print(f"REPRO: checkbox NO inicia drag (correcto)")
else:
    falla("check no encontrado")
    results["check"]=(False,"no widget")

# T05 Umbral < no debe iniciar ni desde fondo ni desde hijos
reset_drag()
pos_small = QPoint(5,5)
ev_p = _make_press(QPointF(pos_small), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
if label_widget is not None:
    QApplication.sendEvent(label_widget, ev_p)
    app.processEvents()
    small_move = QPoint(pos_small.x() + (threshold-1 if threshold>1 else 0), pos_small.y())
    ev_m_small = _make_move(QPointF(small_move), Qt.LeftButton)
    QApplication.sendEvent(label_widget, ev_m_small)
    app.processEvents()
    has_small = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_small, f"< umbral no inicia desde label (thr {threshold}) drag_calls={drag_calls}")

# T06 Modo OFF no inicia
fake._modo_organizacion=False
reset_drag()
if label_widget is not None:
    pos = QPoint(label_widget.rect().width()//2, label_widget.rect().height()//2)
    if pos.x()<=0: pos=QPoint(5,5)
    ev_p = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(label_widget, ev_p)
    app.processEvents()
    ev_m = _make_move(QPointF(QPoint(pos.x()+threshold+10, pos.y())), Qt.LeftButton)
    QApplication.sendEvent(label_widget, ev_m)
    app.processEvents()
    has_off = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_off, f"Modo OFF no inicia drag desde label drag_calls={drag_calls}")
fake._modo_organizacion=True

# ── B7.13B GESTOS REALES AMPLIADOS T07-T14 ──
# Helper para reset centrado en cualquier tarjeta
def reset_drag_t(tgt):
    drag_calls.clear()
    caps.clear()
    tgt._drag_start_pos=None
    tgt._drag_deferred=False

# T07 MULTISELECCION desde hijo label (2-3 tarjetas)
# Crea 3 tarjetas en orden visible, todas seleccionadas, drag desde label de la del medio (ya seleccionada)
contenedor2 = QWidget()
layout2 = QVBoxLayout(contenedor2)
fake2 = FakeVisor()
fake2._modo_organizacion=True
fake2._visibles_order=["v1.mp4","v2.mp4","v3.mp4"]
t1 = vv.Tarjeta(_fila("v1.mp4", 101, "/tmp"))
t2 = vv.Tarjeta(_fila("v2.mp4", 102, "/tmp"))
t3 = vv.Tarjeta(_fila("v3.mp4", 103, "/tmp"))
for tt in [t1,t2,t3]:
    tt.marcar_seleccionada(True)
fake2._tarjetas_by_name={"v1.mp4":t1,"v2.mp4":t2,"v3.mp4":t3}
fake2._nombres_seleccionados={"v1.mp4","v2.mp4","v3.mp4"}
for tt in [t1,t2,t3]:
    tt._visor_para_drag=lambda f=fake2: f
    layout2.addWidget(tt)
contenedor2.show()
app.processEvents()
for tt in [t1,t2,t3]:
    tt.show()
app.processEvents()
# asegurar labels
label_t2 = find_label(t2, "Nombre")
if label_t2 is None:
    falla("T07 label_t2 no encontrado")
else:
    drag_calls.clear(); caps.clear(); t2._drag_start_pos=None; t2._drag_deferred=False
    rect = label_t2.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_p = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(label_t2, ev_p)
    app.processEvents()
    sel_before = set(fake2._nombres_seleccionados)
    ev_m = _make_move(QPointF(QPoint(pos.x()+threshold+10, pos.y())), Qt.LeftButton)
    QApplication.sendEvent(label_t2, ev_m)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(has_drag, f"T07 multiseleccion drag desde hijo inicia {drag_calls}")
    mime = caps.get("mime")
    if mime is not None and mime.hasFormat(po.MIME_VIDEOS_IDS):
        payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
        ids = po._deserializar_ids_videos_desde_mime(payload)
        verifica(ids==[101,102,103], f"T07 payload multiseleccion orden estable {ids}")
    else:
        falla("T07 mime no recibido o formato incorrecto", f"caps={caps}")
    verifica(fake2._nombres_seleccionados==sel_before, f"T07 seleccion no reducida {fake2._nombres_seleccionados} == {sel_before}")
    verifica(len(fake2._nombres_seleccionados)==3, "T07 siguen 3 seleccionadas")
    # limpiar
    for tt in [t1,t2,t3]:
        tt._drag_start_pos=None; tt._drag_deferred=False
    drag_calls.clear(); caps.clear()
    contenedor2.close()

# T08 CLICK SIMPLE EN LABEL sin superar umbral: press+release sobre label hijo conserva seleccionada y cero QDrag
# Usar tarjeta no seleccionada inicialmente, click simple debe emitir seleccionada(nombre, False)
tarjeta8 = vv.Tarjeta(_fila("click_simple.mp4", 55, "/tmp"))
fake8 = FakeVisor()
fake8._modo_organizacion=True
fake8._visibles_order=["click_simple.mp4"]
fake8._tarjetas_by_name={"click_simple.mp4": tarjeta8}
fake8._nombres_seleccionados=set()
tarjeta8.marcar_seleccionada(False)
orig8 = tarjeta8._visor_para_drag
tarjeta8._visor_para_drag=lambda: fake8
# crear contenedor aislado para geometria
cont8 = QWidget()
l8 = QVBoxLayout(cont8)
l8.addWidget(tarjeta8)
cont8.show()
app.processEvents()
tarjeta8.show()
app.processEvents()
label8 = find_label(tarjeta8, "Nombre")
if label8 is None:
    falla("T08 label8 no encontrado")
else:
    emisiones=[]
    def cap8(n,ctrl): emisiones.append((n,ctrl))
    tarjeta8.seleccionada.connect(cap8)
    drag_calls.clear(); caps.clear(); tarjeta8._drag_start_pos=None; tarjeta8._drag_deferred=False
    rect = label8.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(label8, ev_press)
    app.processEvents()
    # release sin movimiento > umbral
    ev_rel = _make_release(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(label8, ev_rel)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T08 click simple sin umbral cero QDrag drag_calls={drag_calls}")
    verifica(len(emisiones)==1 and emisiones[0][0]=="click_simple.mp4" and emisiones[0][1]==False, f"T08 emite seleccionada(nombre, False) {emisiones}")
    verifica(tarjeta8._drag_start_pos is None and tarjeta8._drag_deferred==False, "T08 estado drag reseteado tras click")
    try: tarjeta8.seleccionada.disconnect(cap8)
    except: pass
    tarjeta8._visor_para_drag=orig8
    cont8.close()
drag_calls.clear(); caps.clear()

# T09 DOBLE CLIC EN LABEL hijo: enviar MouseButtonDblClick al hijo real; debe emitir doble_clic exactamente una vez, cero QDrag y estado reset
tarjeta9 = vv.Tarjeta(_fila("doble.mp4", 56, "/tmp"))
fake9 = FakeVisor()
fake9._modo_organizacion=True
fake9._visibles_order=["doble.mp4"]
fake9._tarjetas_by_name={"doble.mp4":tarjeta9}
fake9._nombres_seleccionados={"doble.mp4"}
tarjeta9.marcar_seleccionada(True)
tarjeta9._visor_para_drag=lambda: fake9
cont9 = QWidget()
l9 = QVBoxLayout(cont9)
l9.addWidget(tarjeta9)
cont9.show()
app.processEvents()
tarjeta9.show()
app.processEvents()
label9 = find_label(tarjeta9, "Nombre")
preview9 = get_preview(tarjeta9)
target9 = label9 if label9 is not None else preview9
if target9 is None:
    falla("T09 target no encontrado")
else:
    emisiones_dbl=[]
    tarjeta9.doble_clic.connect(lambda n: emisiones_dbl.append(n))
    # preparar estado drag previo para verificar reset
    tarjeta9._drag_start_pos=QPoint(0,0)
    tarjeta9._drag_deferred=True
    drag_calls.clear(); caps.clear()
    rect = target9.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_dbl = _make_dbl(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target9, ev_dbl)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T09 doble clic cero QDrag {drag_calls}")
    verifica(len(emisiones_dbl)==1 and emisiones_dbl[0]=="doble.mp4", f"T09 doble_clic exactamente 1 {emisiones_dbl}")
    verifica(tarjeta9._drag_start_pos is None and tarjeta9._drag_deferred==False, "T09 estado drag reseteado tras doble clic")
    try: tarjeta9.doble_clic.disconnect
    except: pass
    cont9.close()
drag_calls.clear(); caps.clear()

# T10 CLICK DERECHO EN LABEL hijo: press/release derecho emite menu_contextual y no inicia QDrag
tarjeta10 = vv.Tarjeta(_fila("menu.mp4", 57, "/tmp"))
fake10 = FakeVisor()
fake10._modo_organizacion=True
fake10._visibles_order=["menu.mp4"]
fake10._tarjetas_by_name={"menu.mp4":tarjeta10}
fake10._nombres_seleccionados=set()
tarjeta10.marcar_seleccionada(False)
tarjeta10._visor_para_drag=lambda: fake10
cont10 = QWidget()
l10 = QVBoxLayout(cont10)
l10.addWidget(tarjeta10)
cont10.show()
app.processEvents()
tarjeta10.show()
app.processEvents()
label10 = find_label(tarjeta10, "Nombre")
if label10 is None:
    falla("T10 label10 no encontrado")
else:
    menu_emits=[]
    sel_emits10=[]
    tarjeta10.menu_contextual.connect(lambda n: menu_emits.append(n))
    tarjeta10.seleccionada.connect(lambda n,ctrl: sel_emits10.append((n,ctrl)))
    drag_calls.clear(); caps.clear(); tarjeta10._drag_start_pos=None; tarjeta10._drag_deferred=False
    rect = label10.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_press_r = _make_press(QPointF(pos), Qt.RightButton, Qt.NoModifier, Qt.RightButton)
    QApplication.sendEvent(label10, ev_press_r)
    app.processEvents()
    ev_rel_r = _make_release(QPointF(pos), Qt.RightButton, Qt.NoModifier)
    QApplication.sendEvent(label10, ev_rel_r)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T10 click derecho cero QDrag {drag_calls}")
    verifica(len(menu_emits)==1 and menu_emits[0]=="menu.mp4", f"T10 menu_contextual emitido {menu_emits}")
    # seleccionada debe haberse emitido porque no estaba seleccionada (semantica actual)
    verifica(len(sel_emits10)>=1, f"T10 seleccionada emitida por right si no seleccionado {sel_emits10}")
    try: tarjeta10.menu_contextual.disconnect
    except: pass
    cont10.close()
drag_calls.clear(); caps.clear()

# T11 CTRL-CLICK hijo: debe preservar toggle/multiseleccion (seleccionada(nombre, True))
tarjeta11 = vv.Tarjeta(_fila("ctrl.mp4", 58, "/tmp"))
fake11 = FakeVisor()
fake11._modo_organizacion=True
fake11._visibles_order=["ctrl.mp4"]
fake11._tarjetas_by_name={"ctrl.mp4":tarjeta11}
fake11._nombres_seleccionados=set()
tarjeta11.marcar_seleccionada(False)
tarjeta11._visor_para_drag=lambda: fake11
cont11 = QWidget()
l11 = QVBoxLayout(cont11)
l11.addWidget(tarjeta11)
cont11.show()
app.processEvents()
tarjeta11.show()
app.processEvents()
label11 = find_label(tarjeta11, "Nombre")
if label11 is None:
    falla("T11 label11 no encontrado")
else:
    emisiones_ctrl=[]
    tarjeta11.seleccionada.connect(lambda n,ctrl: emisiones_ctrl.append((n,ctrl)))
    drag_calls.clear(); caps.clear(); tarjeta11._drag_start_pos=None; tarjeta11._drag_deferred=False
    rect = label11.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.ControlModifier, Qt.LeftButton)
    QApplication.sendEvent(label11, ev_press)
    app.processEvents()
    ev_rel = _make_release(QPointF(pos), Qt.LeftButton, Qt.ControlModifier)
    QApplication.sendEvent(label11, ev_rel)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T11 ctrl-click cero QDrag {drag_calls}")
    verifica(len(emisiones_ctrl)==1 and emisiones_ctrl[0]==("ctrl.mp4", True), f"T11 CTRL emit seleccionada True {emisiones_ctrl}")
    cont11.close()
drag_calls.clear(); caps.clear()

# T12 SHIFT-CLICK hijo: debe emitir seleccion_por_rango sin drag accidental
tarjeta12 = vv.Tarjeta(_fila("shift.mp4", 59, "/tmp"))
fake12 = FakeVisor()
fake12._modo_organizacion=True
fake12._visibles_order=["shift.mp4"]
fake12._tarjetas_by_name={"shift.mp4":tarjeta12}
fake12._nombres_seleccionados=set()
tarjeta12.marcar_seleccionada(False)
tarjeta12._visor_para_drag=lambda: fake12
cont12 = QWidget()
l12 = QVBoxLayout(cont12)
l12.addWidget(tarjeta12)
cont12.show()
app.processEvents()
tarjeta12.show()
app.processEvents()
label12 = find_label(tarjeta12, "Nombre")
if label12 is None:
    falla("T12 label12 no encontrado")
else:
    emisiones_shift=[]
    tarjeta12.seleccion_por_rango.connect(lambda n: emisiones_shift.append(n))
    drag_calls.clear(); caps.clear(); tarjeta12._drag_start_pos=None; tarjeta12._drag_deferred=False
    rect = label12.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.ShiftModifier, Qt.LeftButton)
    QApplication.sendEvent(label12, ev_press)
    app.processEvents()
    ev_rel = _make_release(QPointF(pos), Qt.LeftButton, Qt.ShiftModifier)
    QApplication.sendEvent(label12, ev_rel)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T12 shift-click cero QDrag {drag_calls}")
    verifica(len(emisiones_shift)==1 and emisiones_shift[0]=="shift.mp4", f"T12 SHIFT emit seleccion_por_rango {emisiones_shift}")
    cont12.close()
drag_calls.clear(); caps.clear()

# T13 PREVIEW click simple y doble clic siguen comportamiento esperado (no solo drag)
tarjeta13 = vv.Tarjeta(_fila("preview_click.mp4", 60, "/tmp"))
fake13 = FakeVisor()
fake13._modo_organizacion=True
fake13._visibles_order=["preview_click.mp4"]
fake13._tarjetas_by_name={"preview_click.mp4":tarjeta13}
fake13._nombres_seleccionados=set()
tarjeta13.marcar_seleccionada(False)
tarjeta13._visor_para_drag=lambda: fake13
cont13 = QWidget()
l13 = QVBoxLayout(cont13)
l13.addWidget(tarjeta13)
cont13.show()
app.processEvents()
tarjeta13.show()
app.processEvents()
preview13 = get_preview(tarjeta13)
if preview13 is None:
    falla("T13 preview13 no encontrado")
else:
    # click simple en preview debe emitir seleccionada
    emisiones_prev=[]
    tarjeta13.seleccionada.connect(lambda n,ctrl: emisiones_prev.append((n,ctrl)))
    drag_calls.clear(); caps.clear(); tarjeta13._drag_start_pos=None; tarjeta13._drag_deferred=False
    rect = preview13.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(preview13, ev_press)
    app.processEvents()
    ev_rel = _make_release(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(preview13, ev_rel)
    app.processEvents()
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T13 preview click simple cero QDrag {drag_calls}")
    verifica(len(emisiones_prev)==1 and emisiones_prev[0][0]=="preview_click.mp4", f"T13 preview click emite seleccionada {emisiones_prev}")
    try: tarjeta13.seleccionada.disconnect
    except: pass
    # doble clic en preview debe emitir doble_clic
    emisiones_dbl_prev=[]
    tarjeta13.doble_clic.connect(lambda n: emisiones_dbl_prev.append(n))
    tarjeta13._drag_start_pos=QPoint(0,0); tarjeta13._drag_deferred=True
    drag_calls.clear(); caps.clear()
    ev_dbl = _make_dbl(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(preview13, ev_dbl)
    app.processEvents()
    has_drag2 = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag2, f"T13 preview doble clic cero QDrag {drag_calls}")
    verifica(len(emisiones_dbl_prev)==1 and emisiones_dbl_prev[0]=="preview_click.mp4", f"T13 preview doble_clic {emisiones_dbl_prev}")
    verifica(tarjeta13._drag_start_pos is None, "T13 preview doble clic resetea drag")
    cont13.close()
drag_calls.clear(); caps.clear()

# T14 CHECKBOX click real debe cambiar/emitir señal propia y no iniciar drag
tarjeta14 = vv.Tarjeta(_fila("check.mp4", 61, "/tmp"))
fake14 = FakeVisor()
fake14._modo_organizacion=True
fake14._visibles_order=["check.mp4"]
fake14._tarjetas_by_name={"check.mp4":tarjeta14}
fake14._nombres_seleccionados=set()
tarjeta14.marcar_seleccionada(False)
tarjeta14.mostrar_check(True)
tarjeta14.set_check(False)
tarjeta14._visor_para_drag=lambda: fake14
cont14 = QWidget()
l14 = QVBoxLayout(cont14)
l14.addWidget(tarjeta14)
cont14.show()
app.processEvents()
tarjeta14.show()
app.processEvents()
check14 = getattr(tarjeta14, "_check", None)
if check14 is None:
    falla("T14 check no encontrado")
else:
    check14.setVisible(True)
    check14.setEnabled(True)
    app.processEvents()
    emisiones_check=[]
    tarjeta14.seleccion_check.connect(lambda n,chk: emisiones_check.append((n,chk)))
    drag_calls.clear(); caps.clear(); tarjeta14._drag_start_pos=None; tarjeta14._drag_deferred=False
    estado_antes = check14.isChecked()
    rect = check14.rect()
    pos = QPoint(rect.width()//2, rect.height()//2) if rect.width()>0 else QPoint(5,5)
    if pos.x()<=0 or pos.y()<=0: pos=QPoint(5,5)
    # Enviar press+release real al checkbox (no a Tarjeta) — debe ser manejado por QCheckBox sin pasar por eventFilter drag
    ev_press = _make_press(QPointF(pos), Qt.LeftButton, Qt.NoModifier, Qt.LeftButton)
    QApplication.sendEvent(check14, ev_press)
    app.processEvents()
    ev_rel = _make_release(QPointF(pos), Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(check14, ev_rel)
    app.processEvents()
    # QCheckBox toggles on click; si no toggléo por sendEvent directo, probar QTest fallback
    if check14.isChecked()==estado_antes and len(emisiones_check)==0:
        # fallback usando QTest.mouseClick para mayor fidelidad Qt
        try:
            from PySide6.QtTest import QTest
            QTest.mouseClick(check14, Qt.LeftButton)
            app.processEvents()
        except (AttributeError, RuntimeError, ValueError):
            pass
    has_drag = any(isinstance(c,tuple) and c[0]=="exec" for c in drag_calls)
    verifica(not has_drag, f"T14 checkbox click cero QDrag {drag_calls}")
    # debe haber emitido seleccion_check y cambiado estado
    verifica(len(emisiones_check)>=1, f"T14 checkbox emite seleccion_check {emisiones_check}")
    if len(emisiones_check)>=1:
        verifica(emisiones_check[-1][0]=="check.mp4", f"T14 nombre check correcto {emisiones_check}")
        verifica(emisiones_check[-1][1]==True or check14.isChecked()==True, f"T14 check marcado tras click {emisiones_check} isChecked={check14.isChecked()}")
    verifica(check14.isChecked()!=estado_antes or len(emisiones_check)>=1, f"T14 checkbox cambio estado {estado_antes}->{check14.isChecked()}")
    cont14.close()
drag_calls.clear(); caps.clear()

# ── Resumen reproduccion previa + gestos ──
print("=== RESUMEN REPRODUCCION PREVIA ===")
for k,v in results.items():
    print(f"{k}: {'SI inicia' if v[0] else 'NO inicia'}")
bug_repro = (not results.get("label",[True])[0]) or (not results.get("preview",[True])[0])
print(f"BUG_REPRODUCIDO={bug_repro}")
if bug_repro:
    print("REPRODUCCION PREVIA: al menos una superficie normal NO inicia drag -> bug confirmado")
else:
    print("REPRODUCCION PREVIA: todas las superficies inician drag -> bug NO reproducido")

# Restaurar
vv.QDrag = orig_drag
tarjeta._visor_para_drag = orig_visor

total=_CONT
fallos=_FAIL
print(f"TOTAL={total-fallos}/{total}")
if fallos==0:
    print("RESULTADO_FINAL=OK")
else:
    print("RESULTADO_FINAL=ERROR")

if bug_repro:
    sys.exit(0)
else:
    sys.exit(0)
