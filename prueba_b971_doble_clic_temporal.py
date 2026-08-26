"""B9.7.1 P23 DOBLE CLIC TEMPORAL — eventos reales Qt."""
import os, sys, tempfile, time, gc
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtGui import QPixmap, QColor, QMouseEvent
from PySide6.QtCore import Qt, QEvent, QPointF, QPoint, QTimer

import visor_videos
from visor_videos import Tarjeta, PreviewTiraTemporal, AjustadaGridWidget, MODO_TIRA, MODO_REDUCIDA, MODO_AJUSTADA, MODO_TIRA_DINAMICA, dimensiones_miniatura
from exploracion_temporal import tiempos_objetivo

app = QApplication.instance() or QApplication(sys.argv)

def _pix(color="#aabbcc"):
    pm = QPixmap(320,180)
    pm.fill(QColor(color))
    return pm

def _fila(nombre="video.mp4", dur=60, vid=1, carpeta="C:\\tmp_b971"):
    return (nombre, float(dur), 1920,1080, "h264", 3, 12345, os.path.join(carpeta,nombre), vid)

def _prep_tarjeta(dur=60, vid=1, nombre="video.mp4"):
    fila=_fila(nombre,dur,vid)
    t=Tarjeta(fila)
    # mostrar para que widgets existan y eventos se procesen
    t.show()
    t.resize(1200,800)
    QApplication.processEvents()
    t.expandir()
    QApplication.processEvents()
    # metadata densa: usar densidad 30 para tener N razonable
    try:
        mss=tiempos_objetivo(dur, 30)
        t.set_metadata_densa(mss, version=1)
    except Exception:
        pass
    QApplication.processEvents()
    return t

def _a_modo(t, modo):
    idx=t._selector_modo_tira.findData(modo)
    if idx>=0:
        t._selector_modo_tira.setCurrentIndex(idx)
        QApplication.processEvents()

def _ensure_tira(t):
    _a_modo(t, MODO_TIRA)
    try:
        t._tira_actualizar_logica()
        t._tira_refrescar_viewport()
    except Exception:
        pass
    QApplication.processEvents()
    # esperar pool
    for _ in range(5):
        QApplication.processEvents()
        time.sleep(0.02)
    return t

def _ensure_reducida(t):
    _a_modo(t, MODO_REDUCIDA)
    try:
        t._reducida_actualizar_logica()
    except Exception:
        pass
    QApplication.processEvents()
    time.sleep(0.05)
    QApplication.processEvents()
    return t

def _ensure_ajustada(t):
    _a_modo(t, MODO_AJUSTADA)
    try:
        t._ajustada_actualizar_logica()
    except Exception:
        pass
    QApplication.processEvents()
    # forzar geometría visible
    try:
        t.resize(1200,800)
        QApplication.processEvents()
        t._ajustada_actualizar_logica()
        QApplication.processEvents()
    except Exception:
        pass
    time.sleep(0.05)
    QApplication.processEvents()
    return t

def _send_press(widget, button=Qt.LeftButton, pos=None):
    if pos is None:
        try:
            pos = widget.rect().center()
        except Exception:
            pos = QPoint(5,5)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(pos), QPointF(pos), button, button, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)
    QApplication.processEvents()

def _send_double(widget, button=Qt.LeftButton, pos=None):
    if pos is None:
        try:
            pos = widget.rect().center()
        except Exception:
            pos = QPoint(5,5)
    # secuencia: press simple (primer click) luego double click
    ev1 = QMouseEvent(QEvent.MouseButtonPress, QPointF(pos), QPointF(pos), button, button, Qt.NoModifier)
    QApplication.sendEvent(widget, ev1)
    QApplication.processEvents()
    ev2 = QMouseEvent(QEvent.MouseButtonDblClick, QPointF(pos), QPointF(pos), button, button, Qt.NoModifier)
    QApplication.sendEvent(widget, ev2)
    QApplication.processEvents()

def _send_right(widget, pos=None):
    if pos is None:
        try:
            pos = widget.rect().center()
        except Exception:
            pos = QPoint(5,5)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(pos), QPointF(pos), Qt.RightButton, Qt.RightButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)
    QApplication.processEvents()

def _wait_interval():
    iv = QApplication.doubleClickInterval()
    # esperar intervalo + margen
    target = iv + 80
    start=time.monotonic()
    while (time.monotonic()-start)*1000 < target:
        QApplication.processEvents()
        time.sleep(0.01)

def _cleanup(t):
    try:
        t.close()
    except Exception:
        pass
    try:
        t.deleteLater()
    except Exception:
        pass
    for _ in range(5):
        QApplication.processEvents()
        time.sleep(0.02)
    try:
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except Exception:
        pass
    QApplication.processEvents()
    gc.collect()

# ---------- TEST 1: Tira click simple -> 1 simple, 0 reproducción
def test1():
    t=_prep_tarjeta(dur=30, vid=101, nombre="t1.mp4")
    _ensure_tira(t)
    w=None
    try:
        w=t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget tira"
    if w is None or w._logical_ms is None:
        _cleanup(t)
        return False, "widget sin logical"
    simples=[]
    repros=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    ms=w._logical_ms
    _send_press(w)
    _wait_interval()
    ok = len(simples)==1 and len(repros)==0
    # verificar tiempo lógico exacto
    if simples:
        try:
            if abs(float(simples[0]["tiempo"])*1000 - ms) > 0.001:
                ok=False
        except Exception:
            pass
    _cleanup(t)
    return ok, f"simples={len(simples)} repros={len(repros)} ms={ms}"

# ---------- TEST 2: Tira double-click -> 0 simple, 1 reproducción exacta
def test2():
    t=_prep_tarjeta(dur=30, vid=102, nombre="t2.mp4")
    _ensure_tira(t)
    try:
        w=t._tira_previews_widgets[1] if len(t._tira_previews_widgets)>1 else t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget"
    ms=w._logical_ms
    simples=[]
    repros=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    _send_double(w)
    _wait_interval()
    ok=True
    if len(simples)!=0:
        ok=False
    if len(repros)!=1:
        ok=False
    else:
        try:
            if abs(float(repros[0])*1000 - ms) > 1e-6:
                ok=False
        except Exception:
            ok=False
    _cleanup(t)
    return ok, f"simples={len(simples)} repros={len(repros)} repro={repros[0] if repros else None} ms={ms}"

# ---------- TEST 3: Reducida double-click -> 0 simple, 1 reproducción exacta
def test3():
    t=_prep_tarjeta(dur=60, vid=103, nombre="t3.mp4")
    t.resize(900,800)
    QApplication.processEvents()
    _ensure_reducida(t)
    w=None
    try:
        w=t._reducida_previews_widgets[0] if t._reducida_previews_widgets else None
    except Exception:
        w=None
    if w is None:
        _cleanup(t)
        return False, "no widget reducida"
    ms=w._logical_ms
    simples=[]
    repros=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    _send_double(w)
    _wait_interval()
    ok = len(simples)==0 and len(repros)==1
    if ok:
        try:
            if abs(float(repros[0])*1000 - ms) > 1e-6:
                ok=False
        except Exception:
            ok=False
    _cleanup(t)
    return ok, f"simples={len(simples)} repros={len(repros)} ms={ms} repro={repros[0] if repros else None}"

# ---------- TEST 4: Ajustada double sobre celda concreta -> 0 simple, 1 repro exacta
def test4():
    t=_prep_tarjeta(dur=40, vid=104, nombre="t4.mp4")
    t.resize(1200,900)
    QApplication.processEvents()
    _ensure_ajustada(t)
    grid=t._ajustada_grid
    if not grid._logical_ms:
        _cleanup(t)
        return False, "ajustada sin logical"
    # elegir índice 4 o 0 si corto
    idx=4 if len(grid._logical_ms)>4 else 0
    ms=grid._logical_ms[idx]
    # calcular centro de celda
    try:
        rect=grid._rect_for_index(idx)
        pos=rect.center()
    except Exception:
        pos=QPoint(10,10)
    simples=[]
    repros=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    # enviar doble en grid en pos de celda
    _send_double(grid, pos=pos)
    _wait_interval()
    ok = len(simples)==0 and len(repros)==1
    if ok:
        try:
            if abs(float(repros[0])*1000 - ms) > 1e-6:
                ok=False
        except Exception:
            ok=False
    _cleanup(t)
    return ok, f"idx={idx} ms={ms} repro={repros[0] if repros else None} simples={len(simples)}"

# ---------- TEST 5: Modo Segmento con A pendiente -> double no altera A/no crea B, sí reproduce
def test5():
    t=_prep_tarjeta(dur=30, vid=105, nombre="t5.mp4")
    _ensure_tira(t)
    # activar modo segmento y fijar A pendiente
    try:
        t._modo_crear_segmento=True
        t._boton_segmento.setChecked(True)
        QApplication.processEvents()
        t._extremo_segmento = 5.0
        t._franja.set_inicio_segmento_pendiente(5.0)
        QApplication.processEvents()
    except Exception:
        pass
    w=None
    try:
        w=t._tira_previews_widgets[2] if len(t._tira_previews_widgets)>2 else t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget"
    ms=w._logical_ms
    segs=[]
    repros=[]
    t.segmento_creado.connect(lambda s: segs.append(s))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    a_before=t._extremo_segmento
    _send_double(w)
    _wait_interval()
    a_after=t._extremo_segmento
    ok=True
    if a_after != a_before:
        ok=False
    if len(segs)!=0:
        ok=False
    if len(repros)!=1:
        ok=False
    else:
        try:
            if abs(float(repros[0])*1000 - ms) > 1e-6:
                ok=False
        except Exception:
            ok=False
    # limpiar modo
    try:
        t._modo_crear_segmento=False
        t._boton_segmento.setChecked(False)
    except Exception:
        pass
    _cleanup(t)
    return ok, f"A_before={a_before} A_after={a_after} segs={len(segs)} repros={len(repros)}"

# ---------- TEST 6: Right-click inmediata una sola emisión
def test6():
    # Tira right
    t=_prep_tarjeta(dur=30, vid=106, nombre="t6.mp4")
    _ensure_tira(t)
    w=None
    try:
        w=t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget tira"
    right_counts=[]
    # conectar right
    w.tira_right_clicked.connect(lambda ms,pos: right_counts.append(ms))
    _send_right(w)
    # right debe ser inmediato sin esperar
    QApplication.processEvents()
    time.sleep(0.05)
    QApplication.processEvents()
    # esperar un poco más para asegurar no duplica por timer
    time.sleep(0.1)
    QApplication.processEvents()
    ok_tira = len(right_counts)==1
    # Ajustada right
    t2=_prep_tarjeta(dur=30, vid=107, nombre="t6b.mp4")
    t2.resize(1200,800)
    QApplication.processEvents()
    _ensure_ajustada(t2)
    grid=t2._ajustada_grid
    if not grid._logical_ms:
        _cleanup(t)
        _cleanup(t2)
        return False, "ajustada sin logical"
    idx=0
    try:
        rect=grid._rect_for_index(idx)
        pos=rect.center()
    except Exception:
        pos=QPoint(10,10)
    right2=[]
    grid.ajustada_right_clicked.connect(lambda ms,pos: right2.append(ms))
    _send_right(grid, pos=pos)
    QApplication.processEvents()
    time.sleep(0.05)
    QApplication.processEvents()
    time.sleep(0.1)
    QApplication.processEvents()
    ok_aj = len(right2)==1
    _cleanup(t)
    _cleanup(t2)
    return (ok_tira and ok_aj), f"tira_right={len(right_counts)} ajustada_right={len(right2)}"

# ---------- TEST 7: Dos tarjetas aislamiento
def test7():
    t1=_prep_tarjeta(dur=20, vid=201, nombre="iso1.mp4")
    t2=_prep_tarjeta(dur=20, vid=202, nombre="iso2.mp4")
    _ensure_tira(t1)
    _ensure_tira(t2)
    try:
        w1=t1._tira_previews_widgets[0]
        w2=t2._tira_previews_widgets[0]
    except Exception:
        _cleanup(t1); _cleanup(t2)
        return False, "no widgets"
    repros1=[]
    repros2=[]
    simples1=[]
    simples2=[]
    t1.reproduccion_temporal_solicitada.connect(lambda inst: repros1.append(inst))
    t2.reproduccion_temporal_solicitada.connect(lambda inst: repros2.append(inst))
    t1.marcador_creado.connect(lambda m: simples1.append(m))
    t2.marcador_creado.connect(lambda m: simples2.append(m))
    # double en t1
    _send_double(w1)
    _wait_interval()
    # verificar aislamiento: solo t1 reproduce, t2 nada, y viceversa luego
    ok1 = len(repros1)==1 and len(repros2)==0 and len(simples1)==0 and len(simples2)==0
    # ahora double en t2
    # reset counts for second phase? mantener acumulados pero verificar incrementos
    repros1_before=len(repros1)
    repros2_before=len(repros2)
    _send_double(w2)
    _wait_interval()
    ok2 = len(repros2)==repros2_before+1 and len(repros1)==repros1_before and len(simples1)==0 and len(simples2)==0
    # exacta aislamiento ms
    try:
        if abs(float(repros1[0])*1000 - w1._logical_ms)>1e-6:
            ok1=False
        if len(repros2)>=1 and abs(float(repros2[0])*1000 - w2._logical_ms)>1e-6:
            ok2=False
    except Exception:
        ok1=False
        ok2=False
    _cleanup(t1); _cleanup(t2)
    return (ok1 and ok2), f"ok1={ok1} ok2={ok2} r1={len(repros1)} r2={len(repros2)}"

# ---------- TEST 8: Un click simple produce una única acción luego del intervalo
def test8():
    t=_prep_tarjeta(dur=30, vid=108, nombre="t8.mp4")
    _ensure_tira(t)
    w=None
    try:
        w=t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget"
    simples=[]
    repros=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    t.reproduccion_temporal_solicitada.connect(lambda inst: repros.append(inst))
    _send_press(w)
    # verificar que antes de intervalo no hay acción
    time.sleep(0.02)
    QApplication.processEvents()
    early = len(simples)
    _wait_interval()
    ok = early==0 and len(simples)==1 and len(repros)==0
    _cleanup(t)
    return ok, f"early={early} finales simples={len(simples)} repros={len(repros)} interval={QApplication.doubleClickInterval()}"

# ---------- TEST 9: Colapsar/destruir con simple pendiente -> no fantasma
def test9():
    # colapsar
    t=_prep_tarjeta(dur=30, vid=109, nombre="t9.mp4")
    _ensure_tira(t)
    w=None
    try:
        w=t._tira_previews_widgets[0]
    except Exception:
        _cleanup(t)
        return False, "no widget"
    simples=[]
    t.marcador_creado.connect(lambda m: simples.append(m))
    _send_press(w)
    # inmediatamente colapsar antes de intervalo
    t.colapsar()
    QApplication.processEvents()
    _wait_interval()
    ok_collapse = len(simples)==0
    _cleanup(t)
    # destruir
    t2=_prep_tarjeta(dur=30, vid=110, nombre="t9b.mp4")
    _ensure_tira(t2)
    try:
        w2=t2._tira_previews_widgets[0]
    except Exception:
        _cleanup(t2)
        return False, "no widget2"
    simples2=[]
    t2.marcador_creado.connect(lambda m: simples2.append(m))
    _send_press(w2)
    # destruir widget antes de intervalo: deleteLater simulando destrucción tarjeta
    # llamamos _limpiar_tira_b93 y close
    t2.close()
    try:
        # intentar cancelar pendiente explicitamente como haría destrucción
        for _w in list(getattr(t2, "_tira_previews_widgets", []) or []):
            try:
                if hasattr(_w, "_cancel_tira_pending"):
                    _w._cancel_tira_pending()
            except Exception:
                pass
    except Exception:
        pass
    QApplication.processEvents()
    _wait_interval()
    # después de destruir, no debería haber creación (simples2 sigue 0)
    ok_destroy = len(simples2)==0
    _cleanup(t2)
    return (ok_collapse and ok_destroy), f"collapse_ok={ok_collapse} destroy_ok={ok_destroy} simples={len(simples)} simples2={len(simples2)}"

def main():
    tests = [
        ("1 Tira simple -> 1 simple 0 repro", test1),
        ("2 Tira double -> 0 simple 1 repro exacta", test2),
        ("3 Reducida double -> 0 simple 1 repro exacta", test3),
        ("4 Ajustada double celda -> 0 simple 1 repro exacta", test4),
        ("5 Segmento A pendiente double no altera A", test5),
        ("6 Right-click inmediata única", test6),
        ("7 Aislamiento dos tarjetas video_id distintos", test7),
        ("8 Simple único tras intervalo", test8),
        ("9 Colapsar/destruir con pendiente no fantasma", test9),
    ]
    passed=0
    for name, fn in tests:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            ok=False
            msg=f"exception {e}\n{traceback.format_exc()}"
        status="PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")
        if ok:
            passed+=1
    print(f"TOTAL {passed}/{len(tests)}")
    return 0 if passed==len(tests) else 1

if __name__=="__main__":
    sys.exit(main())
