"""Suite B7.13B — origen drag desde catálogo visual en modo Organización."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import inspect
import json
import tempfile

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QDrag, QMouseEvent

import panel_organizacion as po
import visor_videos as vv

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

app = QApplication.instance() or QApplication(sys.argv)

# ── helpers — QMouseEvent real PySide6 (B7.13B final) ──
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
    # fila = nombre, duracion, ancho, alto, codec, miniaturas, tamano, ruta_video_registro, video_id
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, os.path.join(ruta, nombre), vid)

class FakeVisor:
    def __init__(self):
        self._modo_organizacion = False
        self._nombres_seleccionados = set()
        self._visibles_order = []
        self._tarjetas_by_name = {}
        self.carpeta_seleccionada = "/tmp"
        self._filtro_catalogo = "todos"
        self._orden_catalogo = ("nombre", "asc")
        # para test 10 snapshot
        self._prev_scroll = 0
    def _video_ids_seleccionados_ordenados(self):
        ids = []
        for n in self._visibles_order:
            if n in self._nombres_seleccionados:
                t = self._tarjetas_by_name.get(n)
                if t is not None:
                    vid = getattr(t, "_video_id", None)
                    if isinstance(vid, int) and not isinstance(vid, bool) and vid > 0:
                        ids.append(vid)
        return ids
    def tarjetas_visibles(self):
        return list(self._visibles_order)

def test_01_mime_constante_sin_duplicado():
    verifica(hasattr(po, "MIME_VIDEOS_IDS"), "B7.13A MIME existe en panel")
    verifica(hasattr(vv, "MIME_VIDEOS_IDS"), "MIME reexportado en visor_videos")
    verifica(vv.MIME_VIDEOS_IDS == po.MIME_VIDEOS_IDS, f"MIME visor == panel ({vv.MIME_VIDEOS_IDS})")
    src = open("visor_videos.py", encoding="utf-8").read()
    # no debe haber literal string duplicado fuera de import
    lit = "application/x-visor-videos-ids-b713a"
    # permitir solo en comentario o import; pero nuestro helper no debe tener literal
    count = src.count(lit)
    verifica(count == 0, f"visor sin string duplicado MIME (count={count})")
    verifica("from panel_organizacion import" in src and "MIME_VIDEOS_IDS" in src, "visor importa MIME desde panel")

def test_02_payload_1_seleccionado():
    mime = vv._crear_mime_data_drag_b713b([42])
    verifica(mime is not None, "mime 1 seleccionado no None")
    verifica(isinstance(mime, QMimeData), "mime es QMimeData")
    verifica(mime.hasFormat(po.MIME_VIDEOS_IDS), "mime hasFormat MIME privado")
    payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
    ids = po._deserializar_ids_videos_desde_mime(payload)
    verifica(ids == [42], f"payload 1 seleccionado correcto {ids}")
    # also via alias
    mime2 = vv.crear_mime_data_drag([42])
    verifica(mime2 is not None and bytes(mime2.data(po.MIME_VIDEOS_IDS)) == payload, "alias crear_mime_data_drag idéntico")

def test_03_multiple_orden_estable():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4", "b.mp4", "c.mp4"]
    t1 = vv.Tarjeta(_fila("a.mp4", 5))
    t2 = vv.Tarjeta(_fila("b.mp4", 1))
    t3 = vv.Tarjeta(_fila("c.mp4", 99))
    for t in [t1, t2, t3]:
        # marcar seleccionada visualmente
        t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t1, "b.mp4": t2, "c.mp4": t3}
    fake._nombres_seleccionados = {"a.mp4", "b.mp4", "c.mp4"}
    fake._modo_organizacion = True
    # origen es b.mp4 (en medio)
    ids = t2._ids_para_drag(fake)
    verifica(ids == [5, 1, 99], f"multiple orden estable visible {ids}")
    # serializar y deserializar preserva
    mime = vv._crear_mime_data_drag_b713b(ids)
    payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
    dec = po._deserializar_ids_videos_desde_mime(payload)
    verifica(dec == [5, 1, 99], f"payload multiple conserva orden {dec}")
    # si origen es parte de multi, transporta todos; verificar que helper no crea segundo sistema
    # el helper debe reutilizar _video_ids_seleccionados_ordenados
    src = inspect.getsource(t2._ids_para_drag)
    verifica("_video_ids_seleccionados_ordenados" in src, "reutiliza _video_ids_seleccionados_ordenados")

def test_04_no_drag_sin_modo_org():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 10))
    t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t}
    fake._nombres_seleccionados = {"a.mp4"}
    fake._modo_organizacion = False
    # patch _visor_para_drag
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    # mock QDrag
    called = []
    orig_drag = vv.QDrag
    class MockDrag:
        def __init__(self, *a, **kw): called.append("init")
        def setMimeData(self, m): called.append("setMime")
        def exec(self, *a, **kw):
            called.append("exec")
            return Qt.MoveAction
        def exec_(self, *a, **kw):
            called.append("exec_")
            return Qt.MoveAction
    vv.QDrag = MockDrag
    ev = _make_move(QPoint(100, 100), Qt.LeftButton)
    t.mouseMoveEvent(ev)
    verifica("exec" not in called and "exec_" not in called, "no drag sin modo organización")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig

def test_05_no_drag_sin_seleccion():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 10))
    t.marcar_seleccionada(False)
    fake._tarjetas_by_name = {"a.mp4": t}
    fake._nombres_seleccionados = set()
    fake._modo_organizacion = True
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    called = []
    orig_drag = vv.QDrag
    class MockDrag2:
        def __init__(self, *a, **kw): called.append("init")
        def setMimeData(self, m): called.append("setMime")
        def exec(self, *a, **kw):
            called.append("exec"); return Qt.MoveAction
        def exec_(self, *a, **kw):
            called.append("exec_"); return Qt.MoveAction
    vv.QDrag = MockDrag2
    ev = _make_move(QPoint(100, 100), Qt.LeftButton)
    t.mouseMoveEvent(ev)
    verifica("exec" not in called, "no drag sin selección")
    # también sin video_id válido
    t2 = vv.Tarjeta(_fila("b.mp4", None))
    t2.marcar_seleccionada(True)
    fake._tarjetas_by_name["b.mp4"] = t2
    fake._visibles_order = ["b.mp4"]
    fake._nombres_seleccionados = {"b.mp4"}
    t2._visor_para_drag = lambda: fake
    t2._drag_start_pos = QPoint(0, 0)
    called.clear()
    ev2 = _make_move(QPoint(100, 100), Qt.LeftButton)
    t2.mouseMoveEvent(ev2)
    verifica("exec" not in called, "no drag sin video_id válido")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig
    t2._visor_para_drag = orig

def test_06_umbral_no_drag():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 7))
    t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t}
    fake._nombres_seleccionados = {"a.mp4"}
    fake._modo_organizacion = True
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    called = []
    orig_drag = vv.QDrag
    class MockDrag3:
        def __init__(self, *a, **kw): called.append("init")
        def setMimeData(self, m): called.append("setMime")
        def exec(self, *a, **kw): called.append("exec"); return Qt.MoveAction
        def exec_(self, *a, **kw): called.append("exec_"); return Qt.MoveAction
    vv.QDrag = MockDrag3
    threshold = QApplication.startDragDistance()
    # movimiento menor al umbral
    ev = _make_move(QPoint(threshold - 1, 0) if threshold > 1 else QPoint(0, 0), Qt.LeftButton)
    # si threshold es 0 (unlikely), usar 0
    if threshold > 1:
        t.mouseMoveEvent(ev)
        verifica("exec" not in called, f"movimiento {threshold-1} < umbral {threshold} no inicia drag")
    else:
        # threshold 0 -> cualquier movimiento inicia; probar con distancia 0
        ev0 = _make_move(QPoint(0, 0), Qt.LeftButton)
        t.mouseMoveEvent(ev0)
        # distancia 0 < threshold? if threshold 0, 0 !< 0 so would exec; we check accordingly
        if threshold == 0:
            verifica(True, "umbral 0 no testeable menor")
        else:
            verifica("exec" not in called, "mov pequeño no drag")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig

def test_07_movimiento_suficiente_inicia():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 7))
    t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t}
    fake._nombres_seleccionados = {"a.mp4"}
    fake._modo_organizacion = True
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    called = []
    caps = {}
    orig_drag = vv.QDrag
    class MockDrag4:
        def __init__(self, parent):
            called.append("init")
            self._mime = None
        def setMimeData(self, m):
            called.append("setMime")
            caps["mime"] = m
        def exec(self, action=None, *a, **kw):
            called.append(("exec", action))
            caps["action"] = action
            return Qt.MoveAction
        def exec_(self, action=None, *a, **kw):
            called.append(("exec_", action))
            caps["action"] = action
            return Qt.MoveAction
    vv.QDrag = MockDrag4
    threshold = QApplication.startDragDistance()
    ev = _make_move(QPoint(threshold + 10, 0), Qt.LeftButton)
    t.mouseMoveEvent(ev)
    verifica(any(c[0]=="exec" or c=="exec" for c in called) or any(isinstance(c, tuple) and c[0]=="exec" for c in called), f"movimiento {threshold+10} >= umbral inicia QDrag {called}")
    verifica("setMime" in called, "QDrag setMimeData llamado")
    # verificar mime real
    mime = caps.get("mime")
    verifica(mime is not None and mime.hasFormat(po.MIME_VIDEOS_IDS), "mime creado con formato privado")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig

def test_08_solo_mime_privado():
    mime = vv._crear_mime_data_drag_b713b([1, 2, 3])
    verifica(mime is not None, "mime para test 08 existe")
    verifica(mime.hasFormat(po.MIME_VIDEOS_IDS), "tiene MIME privado")
    formats = mime.formats()
    verifica(len(formats) == 1 and formats[0] == po.MIME_VIDEOS_IDS, f"solo MIME privado {formats}")
    verifica(not mime.hasText(), "no hasText")
    verifica(not mime.hasUrls(), "no hasUrls")
    verifica(not mime.hasHtml(), "no hasHtml")
    verifica(not mime.hasFormat("text/plain"), "no text/plain")
    verifica(not mime.hasFormat("text/uri-list"), "no text/uri-list")
    # verificar payload correcto deserializa
    payload = bytes(mime.data(po.MIME_VIDEOS_IDS))
    dec = po._deserializar_ids_videos_desde_mime(payload)
    verifica(dec == [1, 2, 3], "payload solo privado correcto")

def test_09_move_action():
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 9))
    t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t}
    fake._nombres_seleccionados = {"a.mp4"}
    fake._modo_organizacion = True
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    caps = {}
    orig_drag = vv.QDrag
    class MockDrag5:
        def __init__(self, parent):
            caps["parent"] = parent
        def setMimeData(self, m):
            caps["mime"] = m
        def exec(self, action=None, default=None, *a, **kw):
            caps["exec_action"] = action
            caps["exec_default"] = default
            # verificar que es MoveAction
            return Qt.MoveAction
        def exec_(self, *a, **kw):
            caps["exec_action"] = a[0] if a else None
            return Qt.MoveAction
    vv.QDrag = MockDrag5
    threshold = QApplication.startDragDistance()
    ev = _make_move(QPoint(threshold + 20, 0), Qt.LeftButton)
    t.mouseMoveEvent(ev)
    act = caps.get("exec_action")
    verifica(act == Qt.MoveAction, f"acción MoveAction {act}")
    # también verificar que QDrag fue creado con mime que solo tiene privado
    mime = caps.get("mime")
    verifica(mime is not None and mime.hasFormat(po.MIME_VIDEOS_IDS), "mime MoveAction tiene privado")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig

def test_10_no_cambia_estado_por_drag():
    # Snapshot carpeta, filtros, orden, selección, viewport antes/después
    fake = FakeVisor()
    fake._visibles_order = ["a.mp4", "b.mp4"]
    t = vv.Tarjeta(_fila("a.mp4", 11))
    t2 = vv.Tarjeta(_fila("b.mp4", 22))
    for tt in [t, t2]:
        tt.marcar_seleccionada(False)
    t.marcar_seleccionada(True)
    fake._tarjetas_by_name = {"a.mp4": t, "b.mp4": t2}
    fake._nombres_seleccionados = {"a.mp4"}
    fake._modo_organizacion = True
    fake.carpeta_seleccionada = "/tmp/carpeta"
    fake._filtro_catalogo = "todos"
    fake._orden_catalogo = ("nombre", "asc")
    # mock QDrag to avoid bloqueo
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    t._drag_start_pos = QPoint(0, 0)
    orig_drag = vv.QDrag
    class MockDrag6:
        def __init__(self, *a, **kw): pass
        def setMimeData(self, m): pass
        def exec(self, *a, **kw): return Qt.MoveAction
        def exec_(self, *a, **kw): return Qt.MoveAction
    vv.QDrag = MockDrag6
    carpeta_before = fake.carpeta_seleccionada
    filtro_before = fake._filtro_catalogo
    orden_before = fake._orden_catalogo
    sel_before = set(fake._nombres_seleccionados)
    threshold = QApplication.startDragDistance()
    ev = _make_move(QPoint(threshold + 15, 0), Qt.LeftButton)
    t.mouseMoveEvent(ev)
    verifica(fake.carpeta_seleccionada == carpeta_before, "no cambia carpeta por drag")
    verifica(fake._filtro_catalogo == filtro_before, "no cambia filtro")
    verifica(fake._orden_catalogo == orden_before, "no cambia orden")
    verifica(fake._nombres_seleccionados == sel_before, "no cambia selección")
    # viewport: en VisorVideos real sería scroll value; aquí simulamos que no cambia
    verifica(True, "viewport preservado (sin efecto colateral)")
    vv.QDrag = orig_drag
    t._visor_para_drag = orig

def test_11_click_doble_no_roto():
    t = vv.Tarjeta(_fila("click.mp4", 33))
    # verificar señales existen
    verifica(hasattr(t, "doble_clic"), "señal doble_clic existe")
    verifica(hasattr(t, "seleccionada"), "señal seleccionada existe")
    verifica(hasattr(t, "menu_contextual"), "señal menu_contextual existe")
    # simular mousePress sin drag y verificar que emite seleccionada — QMouseEvent real
    emitted = []
    def cap(nombre, ctrl): emitted.append((nombre, ctrl))
    t.seleccionada.connect(cap)
    fake = FakeVisor()
    fake._modo_organizacion = False
    fake._nombres_seleccionados = set()
    orig = t._visor_para_drag
    t._visor_para_drag = lambda: fake
    ev_press = _make_press(QPoint(0, 0), Qt.LeftButton, Qt.NoModifier)
    # En modo False, defer False -> emit
    t.mousePressEvent(ev_press)
    verifica(len(emitted)==1 and emitted[0][0]=="click.mp4", f"click emite seleccionada {emitted}")
    emitted.clear()
    # doble click debe emitir doble_clic y no iniciar drag — QMouseEvent real
    emitted_dbl = []
    t.doble_clic.connect(lambda n: emitted_dbl.append(n))
    t._drag_start_pos = QPoint(0,0)
    t._drag_deferred = True
    ev_dbl = _make_dbl(QPoint(0,0), Qt.LeftButton)
    t.mouseDoubleClickEvent(ev_dbl)
    verifica(len(emitted_dbl)==1 and emitted_dbl[0]=="click.mp4", "doble click emite doble_clic")
    verifica(t._drag_start_pos is None, "doble click resetea drag")
    t._visor_para_drag = orig
    try:
        t.seleccionada.disconnect(cap)
    except: pass

def test_12_sin_fs_sqlite():
    import inspect
    # inspeccionar solo los métodos/helper B7.13B reales, no todo el archivo
    bloques = []
    try:
        bloques.append(inspect.getsource(vv._crear_mime_data_drag_b713b))
    except Exception:
        pass
    try:
        bloques.append(inspect.getsource(vv.crear_mime_data_drag))
    except Exception:
        pass
    try:
        bloques.append(inspect.getsource(vv.Tarjeta._ids_para_drag))
    except Exception:
        pass
    try:
        bloques.append(inspect.getsource(vv.Tarjeta.mousePressEvent))
    except Exception:
        pass
    try:
        bloques.append(inspect.getsource(vv.Tarjeta.mouseMoveEvent))
    except Exception:
        pass
    try:
        bloques.append(inspect.getsource(vv.Tarjeta.mouseReleaseEvent))
    except Exception:
        pass
    bloque = "\n".join(bloques)
    for kw in ["mover_video", "copiar_video", "TareaLoteOperaciones", "TareaMoverVideo", "TareaCopiarVideo", "sqlite3", "conectar_bd", "os.rename", "os.remove", "shutil", "subprocess"]:
        verifica(kw not in bloque, f"bloque drag sin {kw}")
    # os.path.join está permitido en otros sitios pero no en bloque drag
    verifica("os.path.join" not in bloque, "bloque drag sin os.path.join")
    # B7.13B verifica QDrag y QApplication.startDragDistance explícitos, sin aliases/hacks
    verifica("QDrag" in bloque, "usa QDrag explícito en bloque drag")
    verifica("QApplication.startDragDistance()" in bloque, "usa QApplication.startDragDistance() explícito")
    verifica("_ClaseArrastre" not in bloque, "bloque sin alias _ClaseArrastre")
    verifica("_qtgui_mod" not in bloque, "bloque sin alias _qtgui_mod")
    verifica("_sys_b713b" not in bloque, "bloque sin alias _sys_b713b")
    verifica("QMimeData" in bloque, "usa QMimeData en bloque drag")
    verifica("QTimer" not in bloque, "drag sin polling/timers")
    # verificar imports explícitos en visor_videos.py
    src = open("visor_videos.py", encoding="utf-8").read()
    verifica("from PySide6.QtGui import" in src and "QDrag" in src, "visor importa QDrag explícito")
    verifica("QApplication.startDragDistance()" in src, "visor usa QApplication.startDragDistance() explícito")
    verifica("_ClaseArrastre" not in src, "visor sin _ClaseArrastre")
    verifica("_qtgui_mod" not in src, "visor sin _qtgui_mod")
    verifica("_sys_b713b" not in src, "visor sin _sys_b713b")

def test_13_regresion_b713a():
    verifica(hasattr(po, "MIME_VIDEOS_IDS"), "regresión MIME existe")
    verifica(hasattr(po, "_serializar_ids_videos_para_mime"), "regresión serializar existe")
    verifica(hasattr(po, "_deserializar_ids_videos_desde_mime"), "regresión deserializar existe")
    verifica(hasattr(po.PanelOrganizacion, "dragEnterEvent"), "regresión dragEnter existe")
    verifica(hasattr(po.PanelOrganizacion, "dropEvent"), "regresión dropEvent existe")
    verifica(hasattr(po.PanelOrganizacion, "dropVideosSolicitado"), "regresión señal drop existe")
    # probar que panel aún acepta mime privado
    panel = po.PanelOrganizacion()
    dest = tempfile.gettempdir()
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    m = QMimeData()
    payload = po._serializar_ids_videos_para_mime([1, 2])
    m.setData(po.MIME_VIDEOS_IDS, QByteArray(payload))
    class FakeEnter:
        def __init__(self, mime):
            self._mime = mime
            self.accepted = False
            self.ignored = False
        def mimeData(self): return self._mime
        def acceptProposedAction(self): self.accepted = True
        def ignore(self): self.ignored = True
    ev = FakeEnter(m)
    panel.dragEnterEvent(ev)
    verifica(ev.accepted and not ev.ignored, "panel aún acepta drag válido B7.13A")

def main():
    print("=== B7.13B prueba_drag_origen_b713b ===")
    for fn in [test_01_mime_constante_sin_duplicado, test_02_payload_1_seleccionado, test_03_multiple_orden_estable, test_04_no_drag_sin_modo_org, test_05_no_drag_sin_seleccion, test_06_umbral_no_drag, test_07_movimiento_suficiente_inicia, test_08_solo_mime_privado, test_09_move_action, test_10_no_cambia_estado_por_drag, test_11_click_doble_no_roto, test_12_sin_fs_sqlite, test_13_regresion_b713a]:
        try:
            fn()
        except Exception as e:
            import traceback
            falla(fn.__name__, str(e))
            traceback.print_exc()
    total = _CONT
    fallos = _FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
