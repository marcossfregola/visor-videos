"""Suite B7.13A — receptor mínimo drag&drop interno en PanelOrganizacion."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import inspect
import ast
import json
import tempfile
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData, QByteArray, Qt, QPoint
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

import panel_organizacion as po

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

# ── helpers mock events ──
class MockDragEnterEvent:
    def __init__(self, mime):
        self._mime = mime
        self._accepted = False
        self._ignored = False
        self._action = Qt.CopyAction
    def mimeData(self):
        return self._mime
    def acceptProposedAction(self):
        self._accepted = True
        self._ignored = False
    def ignore(self):
        self._ignored = True
        self._accepted = False
    def isAccepted(self):
        return self._accepted
    def proposedAction(self):
        return self._action

class MockDropEvent:
    def __init__(self, mime):
        self._mime = mime
        self._accepted = False
        self._ignored = False
        self._action = Qt.CopyAction
    def mimeData(self):
        return self._mime
    def acceptProposedAction(self):
        self._accepted = True
        self._ignored = False
    def ignore(self):
        self._ignored = True
        self._accepted = False
    def isAccepted(self):
        return self._accepted
    def proposedAction(self):
        return self._action

def _make_mime(ids=None, mime_override=None, raw_bytes=None):
    m = QMimeData()
    mime_name = mime_override if mime_override is not None else po.MIME_VIDEOS_IDS
    if raw_bytes is not None:
        m.setData(mime_name, QByteArray(raw_bytes))
    elif ids is not None:
        payload = po._serializar_ids_videos_para_mime(ids)
        if payload is not None:
            m.setData(mime_name, QByteArray(payload))
        else:
            # still set empty to test? but for valid we need payload
            m.setData(mime_name, QByteArray(b""))
    return m

def test_01_mime_constante_existe():
    verifica(hasattr(po, "MIME_VIDEOS_IDS"), "MIME constante existe")
    mime = getattr(po, "MIME_VIDEOS_IDS", "")
    verifica(isinstance(mime, str) and len(mime) > 5, f"MIME es str no vacio ({mime})")
    verifica(mime.startswith("application/"), f"MIME formato application/ ({mime})")
    # debe ser privado estable, contener visor
    verifica("visor" in mime.lower() or "x-" in mime.lower(), f"MIME contiene visor/x- ({mime})")
    # verificar no usar text/uri-list
    verifica(mime not in ["text/plain", "text/uri-list", "application/x-qt-windows-mime;value=\"FileName\""], "MIME no es genérico")

def test_02_serializar_deserializar_1_y_varios():
    # 1 ID
    payload = po._serializar_ids_videos_para_mime([42])
    verifica(payload is not None and isinstance(payload, (bytes, bytearray)), "serializar 1 ID no None")
    ids = po._deserializar_ids_videos_desde_mime(payload)
    verifica(ids == [42], f"deserializar 1 ID -> {ids}")
    # varios IDs orden
    orig = [5, 1, 99, 7, 123]
    payload2 = po._serializar_ids_videos_para_mime(orig)
    ids2 = po._deserializar_ids_videos_desde_mime(payload2)
    verifica(ids2 == orig, f"varios IDs conserva orden {orig} -> {ids2}")
    # serializar preserva json
    try:
        txt = payload2.decode("utf-8")
        arr = json.loads(txt)
        verifica(arr == orig, "payload JSON conserva orden")
    except Exception as e:
        falla("payload JSON decode", str(e))

def test_03_mime_ajeno_rechazado():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    dest = os.path.join(tempfile.gettempdir(), "dest_b713a_ajeno")
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    # MIME ajeno text/plain
    m = QMimeData()
    m.setText("hello")
    # también probar con formato text/uri-list
    m2 = QMimeData()
    m2.setData("text/plain", QByteArray(b"123"))
    m3 = QMimeData()
    m3.setData("text/uri-list", QByteArray(b"file:///tmp/a.mp4"))
    for idx, mime in enumerate([m, m2, m3]):
        ev = MockDragEnterEvent(mime)
        panel.dragEnterEvent(ev)
        verifica(ev._ignored and not ev._accepted, f"MIME ajeno {idx} dragEnter ignorado")
        ev2 = MockDropEvent(mime)
        emitted = []
        def _cap_drop(ids, obj, _em=emitted):
            _em.append((ids, obj))
        panel.dropVideosSolicitado.connect(_cap_drop)
        panel.dropEvent(ev2)
        verifica(len(emitted) == 0, f"MIME ajeno {idx} drop no emite")
        verifica(ev2._ignored, f"MIME ajeno {idx} drop ignorado")
        # desconectar exactamente el mismo callable (sin RuntimeWarning)
        try:
            panel.dropVideosSolicitado.disconnect(_cap_drop)
        except (TypeError, RuntimeError):
            try:
                panel.dropVideosSolicitado.disconnect()
            except (TypeError, RuntimeError):
                pass

def test_04_payload_invalido_rechazado():
    # vacío, corrupto, no positivo
    casos = []
    # vacío -> serializar None, probamos payload vacío
    casos.append((b"", "vacio"))
    casos.append((b"not json", "corrupto no json"))
    casos.append((b"null", "null"))
    casos.append((b"[]", "lista vacia"))
    casos.append((json.dumps([0]).encode(), "ID 0"))
    casos.append((json.dumps([-5]).encode(), "ID negativo"))
    casos.append((json.dumps([3.14]).encode(), "float"))
    casos.append((json.dumps(["a"]).encode(), "string"))
    casos.append((json.dumps([True]).encode(), "bool True"))
    casos.append((json.dumps({"a":1}).encode(), "objeto no lista"))
    casos.append((json.dumps([1, 0]).encode(), "segundo 0"))
    # también payload con bytes nulos
    casos.append((b"\x00\x01\x02", "bytes nulos"))
    for payload, desc in casos:
        ids = po._deserializar_ids_videos_desde_mime(payload)
        verifica(ids is None, f"payload inválido {desc} -> None")
        # también probar dragEnter rechaza
        app = QApplication.instance() or QApplication(sys.argv)
        panel = po.PanelOrganizacion()
        panel.actualizar("/tmp/dest", False, False, destino_valido=True, subcarpetas=[], cargando=False, error=None)
        m = QMimeData()
        m.setData(po.MIME_VIDEOS_IDS, QByteArray(payload))
        ev = MockDragEnterEvent(m)
        panel.dragEnterEvent(ev)
        verifica(ev._ignored, f"drag inválido {desc} ignorado")
        ev2 = MockDropEvent(m)
        # conectar y verificar no emite
        emitted = []
        def cap(ids, obj):
            emitted.append((ids, obj))
        panel.dropVideosSolicitado.connect(cap)
        panel.dropEvent(ev2)
        verifica(len(emitted) == 0, f"drop inválido {desc} no emite")
        verifica(ev2._ignored, f"drop inválido {desc} ignorado")
        try:
            panel.dropVideosSolicitado.disconnect()
        except:
            pass

def test_05_drag_valido_raiz():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    dest = os.path.join(tempfile.gettempdir(), "dest_b713a_raiz")
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    # objetivo raíz por defecto None
    verifica(panel.objetivo_nombre() is None, "raiz objetivo None inicialmente")
    verifica(panel.objetivo_es_destino_raiz(), "raiz es destino raiz")
    m = _make_mime(ids=[10, 20])
    ev = MockDragEnterEvent(m)
    panel.dragEnterEvent(ev)
    verifica(ev._accepted and not ev._ignored, "drag valido raiz aceptado")
    # dragMove también
    evm = MockDragEnterEvent(m)
    # usar dragMoveEvent si existe
    if hasattr(panel, "dragMoveEvent"):
        evm2 = MockDragEnterEvent(m)
        # MockDragEnterEvent compatible con dragMove
        panel.dragMoveEvent(evm2)
        verifica(evm2._accepted, "dragMove valido raiz aceptado")

def test_06_drag_valido_hija():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    dest = os.path.join(tempfile.gettempdir(), "dest_b713a_hija")
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija", "otra"], cargando=False, error=None)
    # seleccionar hija como objetivo
    # buscar row de hija
    row = -1
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            row = i
            break
    verifica(row >= 0, "hija existe en lista para drag hija")
    panel.lista_subcarpetas.setCurrentRow(row)
    app.processEvents()
    verifica(panel.objetivo_nombre() == "hija", "objetivo hija seteado")
    m = _make_mime(ids=[1,2,3])
    ev = MockDragEnterEvent(m)
    panel.dragEnterEvent(ev)
    verifica(ev._accepted, "drag valido hija aceptado")

def test_07_destino_no_utilizable_rechazado():
    app = QApplication.instance() or QApplication(sys.argv)
    casos = []
    # cargando
    p1 = po.PanelOrganizacion()
    p1.actualizar("/tmp/dest", False, False, destino_valido=True, subcarpetas=["hija"], cargando=True, error=None)
    casos.append((p1, "cargando"))
    # error
    p2 = po.PanelOrganizacion()
    p2.actualizar("/tmp/dest", False, False, destino_valido=False, subcarpetas=["hija"], cargando=False, error="no disponible")
    casos.append((p2, "error"))
    # no valido
    p3 = po.PanelOrganizacion()
    p3.actualizar(None, False, False, destino_valido=False, subcarpetas=[], cargando=False, error=None)
    casos.append((p3, "no valido"))
    # ocupado
    p4 = po.PanelOrganizacion()
    p4.actualizar("/tmp/dest", False, True, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    casos.append((p4, "ocupado"))
    for panel, desc in casos:
        m = _make_mime(ids=[5])
        ev = MockDragEnterEvent(m)
        panel.dragEnterEvent(ev)
        verifica(ev._ignored and not ev._accepted, f"drag rechazado estado {desc}")
        ev2 = MockDropEvent(m)
        emitted = []
        def _h_rech(ids, obj, _e=emitted):
            _e.append((ids, obj))
        panel.dropVideosSolicitado.connect(_h_rech)
        panel.dropEvent(ev2)
        verifica(len(emitted)==0, f"drop rechazado estado {desc} no emite")
        verifica(ev2._ignored, f"drop rechazado estado {desc} ignorado")
        try:
            panel.dropVideosSolicitado.disconnect(_h_rech)
        except (TypeError, RuntimeError):
            try:
                panel.dropVideosSolicitado.disconnect()
            except (TypeError, RuntimeError):
                pass

def test_08_drop_emite_una_vez_correcto():
    app = QApplication.instance() or QApplication(sys.argv)
    # raíz
    panel = po.PanelOrganizacion()
    dest = "/tmp/dest_b713a_drop_raiz"
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    verifica(panel.objetivo_nombre() is None, "drop raiz objetivo None")
    m = _make_mime(ids=[99, 100, 101])
    ev = MockDropEvent(m)
    caps = []
    def cap(ids, obj):
        caps.append((list(ids), obj))
    panel.dropVideosSolicitado.connect(cap)
    panel.dropEvent(ev)
    verifica(ev._accepted, "drop valido raiz aceptado")
    verifica(len(caps) == 1, f"drop emite exactamente 1 (raiz) -> {len(caps)}")
    if len(caps)==1:
        verifica(caps[0][0] == [99,100,101], f"drop IDs correctos raiz {caps[0][0]}")
        verifica(caps[0][1] is None, f"drop objetivo None raiz {caps[0][1]}")
    try:
        panel.dropVideosSolicitado.disconnect()
    except:
        pass
    # hija
    panel2 = po.PanelOrganizacion()
    panel2.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija","otra"], cargando=False, error=None)
    # seleccionar hija
    for i in range(panel2.lista_subcarpetas.count()):
        if panel2.lista_subcarpetas.item(i).text() == "hija":
            panel2.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    verifica(panel2.objetivo_nombre() == "hija", "drop hija objetivo hija")
    m2 = _make_mime(ids=[7])
    ev2 = MockDropEvent(m2)
    caps2 = []
    def _cap_hija(ids, obj, _c=caps2):
        _c.append((list(ids), obj))
    panel2.dropVideosSolicitado.connect(_cap_hija)
    panel2.dropEvent(ev2)
    verifica(ev2._accepted, "drop valido hija aceptado")
    verifica(len(caps2)==1, f"drop hija emite 1 -> {len(caps2)}")
    if len(caps2)==1:
        verifica(caps2[0][0]==[7], f"IDs hija {caps2[0][0]}")
        verifica(caps2[0][1]=="hija", f"objetivo hija {caps2[0][1]}")
    try:
        panel2.dropVideosSolicitado.disconnect(_cap_hija)
    except (TypeError, RuntimeError):
        try:
            panel2.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass

def test_09_drop_invalido_no_emite():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    panel.actualizar("/tmp/dest", False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    # MIME ajeno
    m_ajeno = QMimeData()
    m_ajeno.setText("nope")
    ev = MockDropEvent(m_ajeno)
    caps=[]
    def _cap9a(ids, obj, _c=caps):
        _c.append((ids, obj))
    panel.dropVideosSolicitado.connect(_cap9a)
    panel.dropEvent(ev)
    verifica(len(caps)==0, "drop invalido MIME ajeno no emite")
    verifica(ev._ignored, "drop invalido ignorado")
    try:
        panel.dropVideosSolicitado.disconnect(_cap9a)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass
    # payload corrupto con MIME correcto
    m2 = QMimeData()
    m2.setData(po.MIME_VIDEOS_IDS, QByteArray(b"[]"))
    ev2 = MockDropEvent(m2)
    caps2=[]
    def _cap9b(ids, obj, _c=caps2):
        _c.append((ids, obj))
    panel.dropVideosSolicitado.connect(_cap9b)
    panel.dropEvent(ev2)
    verifica(len(caps2)==0, "drop payload vacío no emite")
    try:
        panel.dropVideosSolicitado.disconnect(_cap9b)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass

def test_10_no_navega_no_cambia_destino():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    dest = "/tmp/dest_b713a_no_navega"
    os.makedirs(dest, exist_ok=True)
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija","otra"], cargando=False, error=None)
    # seleccionar otra
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "otra":
            panel.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    objetivo_before = panel.objetivo_nombre()
    destino_before = panel.destino()
    navegados = []
    def _nav10(n, _arr=navegados):
        _arr.append(n)
    panel.entrarSubcarpetaSolicitada.connect(_nav10)
    m = _make_mime(ids=[1,2])
    ev = MockDropEvent(m)
    caps=[]
    def _cap10(ids, obj, _c=caps):
        _c.append((ids, obj))
    panel.dropVideosSolicitado.connect(_cap10)
    panel.dropEvent(ev)
    verifica(destino_before == panel.destino(), "drop no cambia destino")
    verifica(objetivo_before == panel.objetivo_nombre(), "drop no cambia objetivo")
    verifica(len(navegados)==0, "drop no navega")
    verifica(len(caps)==1, "drop aun emite pese a no navegar")
    try:
        panel.dropVideosSolicitado.disconnect(_cap10)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass
    try:
        panel.entrarSubcarpetaSolicitada.disconnect(_nav10)
    except (TypeError, RuntimeError):
        try:
            panel.entrarSubcarpetaSolicitada.disconnect()
        except (TypeError, RuntimeError):
            pass

def test_11_sin_fs_sqlite_ffmpeg_y_sin_origen_drag():
    src = open("panel_organizacion.py", encoding="utf-8").read()
    for kw in ["sqlite3", "conectar_bd", "escanear_videos", "lote_operaciones", "mover_video", "copiar_video", "subprocess", "QProcess"]:
        verifica(kw not in src, f"panel sin {kw}")
    verifica("import os" not in src, "panel no importa os")
    for kw in ["os.path.isdir", "os.path.isfile", "os.rename", "shutil", "os.remove", "os.listdir", "os.path.join"]:
        verifica(kw not in src, f"panel sin {kw} (fs)")
    # FFmpeg solo permitido en docstring pero no en import código
    import re
    code_lines = [l for l in src.splitlines() if not l.strip().startswith("#") and not l.strip().startswith('"""') and not l.strip().startswith("'''")]
    code_txt = "\n".join(code_lines)
    has_ffmpeg_import = ("import ffmpeg" in code_txt.lower() or "from ffmpeg" in code_txt.lower() or "import ffprobe" in code_txt.lower())
    verifica(not has_ffmpeg_import, "panel sin import FFmpeg/ffprobe")
    # origen drag no implementado
    verifica("setDragEnabled" not in src, "panel sin setDragEnabled (origen no)")
    verifica("startDrag" not in src, "panel sin startDrag")
    verifica("QDrag" not in src, "panel sin QDrag")
    # pero receptor sí existe
    verifica("setAcceptDrops" in src, "panel con setAcceptDrops (receptor)")
    verifica("dragEnterEvent" in src, "panel con dragEnterEvent")
    verifica("dropEvent" in src, "panel con dropEvent")
    verifica("dropVideosSolicitado" in src, "panel con señal dropVideosSolicitado")

def test_12_regresion_b712():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    dest = "/tmp/dest_b713a_reg"
    os.makedirs(dest, exist_ok=True)
    # objetivoSeleccionado sigue existiendo
    verifica(hasattr(panel, "objetivoSeleccionado"), "regresion objetivoSeleccionado existe")
    verifica(hasattr(panel, "objetivo_nombre"), "regresion objetivo_nombre existe")
    verifica(hasattr(panel, "objetivo_es_destino_raiz"), "regresion objetivo_es_destino_raiz existe")
    # probar clic simple no navega pero selecciona
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija","otra"], cargando=False, error=None)
    # doble clic navega via señal
    navegados=[]
    def _nav12a(n, _arr=navegados):
        _arr.append(n)
    panel.entrarSubcarpetaSolicitada.connect(_nav12a)
    # simular doble clic en hija
    item=None
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            item = panel.lista_subcarpetas.item(i)
            break
    verifica(item is not None, "regresion item hija existe")
    panel.lista_subcarpetas.itemDoubleClicked.emit(item)
    verifica(len(navegados)>=1 and navegados[0]=="hija", f"regresion doble clic navega {navegados}")
    # Entrar botón también
    navegados.clear()
    # seleccionar hija
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            panel.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    verifica(panel.boton_entrar_destino.isEnabled(), "regresion boton Entrar habilitado")
    panel.boton_entrar_destino.click()
    verifica(len(navegados)>=1, "regresion boton Entrar navega")
    # clic simple selecciona objetivo sin navegar
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija","otra"], cargando=False, error=None)
    emitted=[]
    def _emit12(n, _arr=emitted):
        _arr.append(n)
    panel.objetivoSeleccionado.connect(_emit12)
    # buscar hija row
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            panel.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    verifica(panel.objetivo_nombre()=="hija", "regresion clic objetivo hija")
    verifica("hija" in emitted, f"regresion emite objetivo hija {emitted}")
    # verificar que objetivoSeleccionado se emite solo cuando cambia
    try:
        panel.objetivoSeleccionado.disconnect(_emit12)
    except (TypeError, RuntimeError):
        try:
            panel.objetivoSeleccionado.disconnect()
        except (TypeError, RuntimeError):
            pass
    try:
        panel.entrarSubcarpetaSolicitada.disconnect(_nav12a)
    except (TypeError, RuntimeError):
        try:
            panel.entrarSubcarpetaSolicitada.disconnect()
        except (TypeError, RuntimeError):
            pass

def test_13_acepta_solo_mime_privado_no_urls():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = po.PanelOrganizacion()
    panel.actualizar("/tmp/dest", False, False, destino_valido=True, subcarpetas=["hija"], cargando=False, error=None)
    # mime con urls
    m = QMimeData()
    m.setData("text/uri-list", QByteArray(b"file:///tmp/video.mp4"))
    # sin mime privado -> debe ignorar aunque tenga url
    ev = MockDragEnterEvent(m)
    panel.dragEnterEvent(ev)
    verifica(ev._ignored, "mime url sin privado ignorado")
    # mime con privado + url -> debe aceptar porque tiene privado válido
    m2 = _make_mime(ids=[1])
    m2.setData("text/uri-list", QByteArray(b"file:///tmp/video.mp4"))
    ev2 = MockDragEnterEvent(m2)
    panel.dragEnterEvent(ev2)
    verifica(ev2._accepted, "mime privado + url aceptado (prevalece privado)")
    # mime con texto genérico + privado válido -> acepta (privado prevalece)
    m3 = _make_mime(ids=[2])
    m3.setText("algún texto")
    ev3 = MockDragEnterEvent(m3)
    panel.dragEnterEvent(ev3)
    verifica(ev3._accepted, "mime privado + text aceptado")

def test_14_evento_qt_real_panel_y_viewport():
    """Prueba despacho REAL de eventos Qt vía QApplication.sendEvent."""
    app = QApplication.instance() or QApplication(sys.argv)
    dest = os.path.join(tempfile.gettempdir(), "dest_b713a_real")
    os.makedirs(dest, exist_ok=True)
    # helper para crear MIME válido REAL
    def _mime_real(ids):
        payload = po._serializar_ids_videos_para_mime(ids)
        m = QMimeData()
        m.setData(po.MIME_VIDEOS_IDS, QByteArray(payload if payload is not None else b""))
        return m
    def _mime_invalido_texto():
        m = QMimeData()
        m.setText("invalido")
        return m
    def _mime_invalido_vacio():
        m = QMimeData()
        m.setData(po.MIME_VIDEOS_IDS, QByteArray(b""))
        return m

    # ── 14a: superficie PanelOrganizacion vía evento REAL ──
    panel = po.PanelOrganizacion()
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija", "otra"], cargando=False, error=None)
    panel.resize(320, 220)
    panel.show()
    app.processEvents()
    verifica(panel.objetivo_nombre() is None, "real panel objetivo raiz None inicial")
    # dragEnter válido REAL aceptado
    m_val = _mime_real([11, 22, 33])
    ev_enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, m_val, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_enter)
    verifica(ev_enter.isAccepted(), "real panel dragEnter valido aceptado")
    # dragMove válido aceptado
    m_val2 = _mime_real([11, 22, 33])
    ev_move = QDragMoveEvent(QPoint(10, 10), Qt.CopyAction, m_val2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_move)
    verifica(ev_move.isAccepted(), "real panel dragMove valido aceptado")
    # drop válido emite exactamente 1 con IDs+objetivo
    caps = []
    def _cap_real(ids, obj, _c=caps):
        _c.append((list(ids), obj))
    panel.dropVideosSolicitado.connect(_cap_real)
    m_drop = _mime_real([11, 22, 33])
    ev_drop = QDropEvent(QPoint(10, 10), Qt.CopyAction, m_drop, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_drop)
    verifica(ev_drop.isAccepted(), "real panel drop valido aceptado")
    verifica(len(caps) == 1, f"real panel drop emite exactamente 1 ({len(caps)})")
    if len(caps) == 1:
        verifica(caps[0][0] == [11, 22, 33], f"real panel IDs correctos {caps[0][0]}")
        verifica(caps[0][1] is None, f"real panel objetivo raiz None {caps[0][1]}")
    caps.clear()
    # evento inválido ignorado (texto ajeno)
    m_bad = _mime_invalido_texto()
    ev_bad_enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, m_bad, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_bad_enter)
    verifica(not ev_bad_enter.isAccepted(), "real panel dragEnter invalido texto ignorado")
    m_bad2 = _mime_invalido_texto()
    ev_bad_drop = QDropEvent(QPoint(10, 10), Qt.CopyAction, m_bad2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_bad_drop)
    verifica(not ev_bad_drop.isAccepted(), "real panel drop invalido texto ignorado")
    verifica(len(caps) == 0, "real panel drop invalido no emite")
    # payload vacío también ignorado
    m_vac = _mime_invalido_vacio()
    ev_vac = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, m_vac, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ev_vac)
    verifica(not ev_vac.isAccepted(), "real panel dragEnter vacio ignorado")
    try:
        panel.dropVideosSolicitado.disconnect(_cap_real)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass

    # ── 14b: viewport / lista_subcarpetas superficie efectiva REAL ──
    # Reutilizamos panel pero ya con subcarpetas; probamos viewport y lista
    for surface_name, target_fn in [
        ("lista", lambda p: p.lista_subcarpetas),
        ("viewport", lambda p: p.lista_subcarpetas.viewport()),
    ]:
        # destino utilizable sigue válido
        # valido enter/move/drop
        m_v = _mime_real([99, 100])
        ent = QDragEnterEvent(QPoint(15, 15), Qt.CopyAction, m_v, Qt.LeftButton, Qt.NoModifier)
        tgt = target_fn(panel)
        QApplication.sendEvent(tgt, ent)
        verifica(ent.isAccepted(), f"real {surface_name} dragEnter valido aceptado")
        m_v2 = _mime_real([99, 100])
        mov = QDragMoveEvent(QPoint(15, 15), Qt.CopyAction, m_v2, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(tgt, mov)
        verifica(mov.isAccepted(), f"real {surface_name} dragMove valido aceptado")
        caps2 = []
        def _cap_s(ids, obj, _c=caps2):
            _c.append((list(ids), obj))
        panel.dropVideosSolicitado.connect(_cap_s)
        m_d = _mime_real([99, 100])
        dr = QDropEvent(QPoint(15, 15), Qt.CopyAction, m_d, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(tgt, dr)
        verifica(dr.isAccepted(), f"real {surface_name} drop valido aceptado")
        verifica(len(caps2) == 1, f"real {surface_name} drop emite 1 ({len(caps2)})")
        if len(caps2) == 1:
            verifica(caps2[0][0] == [99, 100], f"real {surface_name} IDs ok {caps2[0][0]}")
            # B7.13D: (15,15) viewport es sobre fila hija => hija por posición física
            verifica(caps2[0][1] == "hija", f"real {surface_name} objetivo hija por posición {caps2[0][1]}")
        try:
            panel.dropVideosSolicitado.disconnect(_cap_s)
        except (TypeError, RuntimeError):
            try:
                panel.dropVideosSolicitado.disconnect()
            except (TypeError, RuntimeError):
                pass
        # invalido ignorado en esa superficie
        m_bad_s = _mime_invalido_texto()
        ent_bad = QDragEnterEvent(QPoint(15, 15), Qt.CopyAction, m_bad_s, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(tgt, ent_bad)
        verifica(not ent_bad.isAccepted(), f"real {surface_name} dragEnter invalido ignorado")
        caps3 = []
        def _cap_s_bad(ids, obj, _c=caps3):
            _c.append((ids, obj))
        panel.dropVideosSolicitado.connect(_cap_s_bad)
        m_bad_d = _mime_invalido_texto()
        dr_bad = QDropEvent(QPoint(15, 15), Qt.CopyAction, m_bad_d, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(tgt, dr_bad)
        verifica(not dr_bad.isAccepted(), f"real {surface_name} drop invalido ignorado")
        verifica(len(caps3) == 0, f"real {surface_name} drop invalido no emite")
        try:
            panel.dropVideosSolicitado.disconnect(_cap_s_bad)
        except (TypeError, RuntimeError):
            try:
                panel.dropVideosSolicitado.disconnect()
            except (TypeError, RuntimeError):
                pass

    # ── 14c: drop REAL con objetivo hija vía viewport ──
    # seleccionar hija
    row_hija = -1
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            row_hija = i
            break
    verifica(row_hija >= 0, "real viewport objetivo hija row existe")
    panel.lista_subcarpetas.setCurrentRow(row_hija)
    app.processEvents()
    verifica(panel.objetivo_nombre() == "hija", "real objetivo hija seteado para drop real")
    caps_h = []
    def _cap_h(ids, obj, _c=caps_h):
        _c.append((list(ids), obj))
    panel.dropVideosSolicitado.connect(_cap_h)
    # secuencia dragEnter/dragMove/drop real para hija vía viewport
    m_enter_h = _mime_real([7, 8, 9])
    ent_h = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, m_enter_h, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel.lista_subcarpetas.viewport(), ent_h)
    verifica(ent_h.isAccepted(), "real viewport dragEnter hija aceptado")
    m_move_h = _mime_real([7, 8, 9])
    mov_h = QDragMoveEvent(QPoint(10, 10), Qt.CopyAction, m_move_h, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel.lista_subcarpetas.viewport(), mov_h)
    verifica(mov_h.isAccepted(), "real viewport dragMove hija aceptado")
    m_h = _mime_real([7, 8, 9])
    # enviar drop al viewport (superficie efectiva del usuario)
    vp = panel.lista_subcarpetas.viewport()
    drop_h = QDropEvent(QPoint(10, 10), Qt.CopyAction, m_h, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(vp, drop_h)
    verifica(drop_h.isAccepted(), "real viewport drop hija aceptado")
    verifica(len(caps_h) == 1, f"real viewport drop hija emite 1 ({len(caps_h)})")
    if len(caps_h) == 1:
        verifica(caps_h[0][0] == [7, 8, 9], f"real viewport hija IDs {caps_h[0][0]}")
        verifica(caps_h[0][1] == "hija", f"real viewport hija objetivo hija {caps_h[0][1]}")
    try:
        panel.dropVideosSolicitado.disconnect(_cap_h)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass
    # también drop a panel con hija debe respetar mismo objetivo
    # B7.13D: drop por posición física — panel (10,10) es header/fondo => raíz (None), no hija por selección previa
    caps_h2 = []
    def _cap_h2(ids, obj, _c=caps_h2):
        _c.append((list(ids), obj))
    panel.dropVideosSolicitado.connect(_cap_h2)
    m_enter_h2 = _mime_real([5])
    ent_h2 = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, m_enter_h2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, ent_h2)
    verifica(ent_h2.isAccepted(), "real panel dragEnter hija persistente aceptado")
    m_h2 = _mime_real([5])
    drop_h2 = QDropEvent(QPoint(10, 10), Qt.CopyAction, m_h2, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(panel, drop_h2)
    verifica(drop_h2.isAccepted(), "real panel drop hija aceptado (objetivo persistente)")
    # B7.13D: header/fondo => None (no hija por selección)
    verifica(len(caps_h2) == 1 and caps_h2[0][1] is None, f"real panel drop hija objetivo raíz (B7.13D header) {caps_h2}")
    try:
        panel.dropVideosSolicitado.disconnect(_cap_h2)
    except (TypeError, RuntimeError):
        try:
            panel.dropVideosSolicitado.disconnect()
        except (TypeError, RuntimeError):
            pass

    # ── 14d: navegación/clic/doble clic/Enter siguen funcionando tras drops REALES ──
    navegados = []
    def _nav_real(n, _a=navegados):
        _a.append(n)
    panel.entrarSubcarpetaSolicitada.connect(_nav_real)
    # doble clic
    item_hija = None
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            item_hija = panel.lista_subcarpetas.item(i)
            break
    verifica(item_hija is not None, "real navegacion item hija existe tras drops")
    panel.lista_subcarpetas.itemDoubleClicked.emit(item_hija)
    verifica(len(navegados) >= 1 and navegados[0] == "hija", f"real doble clic navega tras drops {navegados}")
    navegados.clear()
    # botón Entrar habilitado y navega
    # re-seleccionar hija porque navegar limpia
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija", "otra"], cargando=False, error=None)
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            panel.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    verifica(panel.boton_entrar_destino.isEnabled(), "real boton Entrar habilitado tras drops")
    panel.boton_entrar_destino.click()
    verifica(len(navegados) >= 1, f"real boton Entrar navega tras drops {navegados}")
    # clic simple selecciona objetivo sin navegar extra
    panel.actualizar(dest, False, False, destino_valido=True, subcarpetas=["hija", "otra"], cargando=False, error=None)
    emitted = []
    def _emit_real(n, _a=emitted):
        _a.append(n)
    panel.objetivoSeleccionado.connect(_emit_real)
    for i in range(panel.lista_subcarpetas.count()):
        if panel.lista_subcarpetas.item(i).text() == "hija":
            panel.lista_subcarpetas.setCurrentRow(i)
            break
    app.processEvents()
    verifica(panel.objetivo_nombre() == "hija", "real clic objetivo hija tras drops")
    verifica("hija" in emitted, f"real emite objetivo hija tras drops {emitted}")
    # Enter vía itemActivated
    navegados.clear()
    item_cur = panel.lista_subcarpetas.currentItem()
    if item_cur is not None:
        panel.lista_subcarpetas.itemActivated.emit(item_cur)
        verifica(len(navegados) >= 1, f"real itemActivated navega tras drops {navegados}")
    else:
        verifica(False, "real itemActivated no hay currentItem")
    try:
        panel.entrarSubcarpetaSolicitada.disconnect(_nav_real)
    except (TypeError, RuntimeError):
        try:
            panel.entrarSubcarpetaSolicitada.disconnect()
        except (TypeError, RuntimeError):
            pass
    try:
        panel.objetivoSeleccionado.disconnect(_emit_real)
    except (TypeError, RuntimeError):
        try:
            panel.objetivoSeleccionado.disconnect()
        except (TypeError, RuntimeError):
            pass
    panel.close()

def main():
    print("=== B7.13A prueba_drag_drop_b713a ===")
    for fn in [test_01_mime_constante_existe, test_02_serializar_deserializar_1_y_varios, test_03_mime_ajeno_rechazado, test_04_payload_invalido_rechazado, test_05_drag_valido_raiz, test_06_drag_valido_hija, test_07_destino_no_utilizable_rechazado, test_08_drop_emite_una_vez_correcto, test_09_drop_invalido_no_emite, test_10_no_navega_no_cambia_destino, test_11_sin_fs_sqlite_ffmpeg_y_sin_origen_drag, test_12_regresion_b712, test_13_acepta_solo_mime_privado_no_urls, test_14_evento_qt_real_panel_y_viewport]:
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
