import py_compile
import sys
import threading
import time

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from tareas import GestorTareas, TareaBase, Estado, _GESTORES_ACTIVOS

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


class TareaEspera(TareaBase):
    def __init__(self, segundos=1.0, etiqueta=""):
        super().__init__()
        self.segundos = segundos
        self.etiqueta = etiqueta

    def _trabajo(self):
        time.sleep(self.segundos)
        return {
            "etiqueta": self.etiqueta,
            "segundos": self.segundos,
            "hilo_python": threading.get_ident(),
            "en_hilo_principal": QThread.isMainThread(),
        }


class TareaError(TareaBase):
    def _trabajo(self):
        raise ValueError("error de demostracion")


class Captura:
    def __init__(self):
        self.eventos = []
        self.resultado = None
        self.error = None
        self.ids = {}

    def al_inicio(self):
        self.eventos.append("inicio")
        self.ids["inicio"] = (threading.get_ident(), QThread.isMainThread())

    def al_resultado(self, valor):
        self.eventos.append("resultado")
        self.resultado = valor
        self.ids["resultado"] = (threading.get_ident(), QThread.isMainThread())

    def al_error(self, mensaje):
        self.eventos.append("error")
        self.error = mensaje
        self.ids["error"] = (threading.get_ident(), QThread.isMainThread())

    def al_finalizada(self):
        self.eventos.append("finalizada")
        self.ids["finalizada"] = (threading.get_ident(), QThread.isMainThread())


def correr(gestor, tarea, timeout_ms=6000):
    captura = Captura()
    gestor.tarea_iniciada.connect(captura.al_inicio)
    gestor.tarea_resultado.connect(captura.al_resultado)
    gestor.tarea_error.connect(captura.al_error)
    gestor.tarea_finalizada.connect(captura.al_finalizada)

    bucle = QEventLoop()
    flags = {"timeout": False}

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    gestor.tarea_finalizada.connect(fin)
    QTimer.singleShot(timeout_ms, por_si_acaso)

    ok = gestor.iniciar(tarea)
    if ok:
        bucle.exec()
    gestor.tarea_iniciada.disconnect(captura.al_inicio)
    gestor.tarea_resultado.disconnect(captura.al_resultado)
    gestor.tarea_error.disconnect(captura.al_error)
    gestor.tarea_finalizada.disconnect(captura.al_finalizada)
    gestor.tarea_finalizada.disconnect(fin)
    return captura, flags, ok


def test_01():
    py_compile.compile("tareas.py", doraise=True)
    py_compile.compile("prueba_tareas.py", doraise=True)
    g = GestorTareas()
    ok = (
        issubclass(GestorTareas, QObject)
        and issubclass(TareaBase, QObject)
        and g.estado == Estado.INACTIVO
        and not g.activo
        and g.hilo is None
        and g.tarea is None
    )
    return ok, f"estado={g.estado} activo={g.activo}"


def test_02():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaEspera(0.4, "a"))
    r = cap.resultado or {}
    ok = (
        cap.eventos == ["inicio", "resultado", "finalizada"]
        and r.get("etiqueta") == "a"
        and not fl["timeout"]
        and g.estado == Estado.INACTIVO
        and g.hilo is None
        and g.tarea is None
    )
    return ok, f"eventos={cap.eventos} estado={g.estado}"


def test_03():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaError())
    ok = (
        cap.eventos == ["inicio", "error", "finalizada"]
        and cap.error is not None
        and "ValueError" in cap.error
        and not fl["timeout"]
    )
    return ok, f"eventos={cap.eventos} error={cap.error!r}"


def test_04():
    id_py_main = threading.get_ident()
    es_main = QThread.isMainThread()
    g = GestorTareas()
    cap, fl, _ = correr(g, TareaEspera(0.3, "a"))
    res = cap.resultado or {}
    ok_senales = (
        set(cap.ids) == {"inicio", "resultado", "finalizada"}
        and all(py == id_py_main and qt for py, qt in cap.ids.values())
    )
    ok_fuera = (
        res.get("hilo_python") not in (None, id_py_main)
        and res.get("en_hilo_principal") is False
    )
    ok = ok_senales and ok_fuera
    return (
        ok,
        f"ids={cap.ids} tarea_py={res.get('hilo_python')} "
        f"es_main_qt={es_main} tarea_en_principal={res.get('en_hilo_principal')}",
    )


def test_05():
    g = GestorTareas()
    ticks = {"n": 0}
    reloj = QTimer()
    reloj.setInterval(150)
    reloj.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    reloj.start()
    cap, fl, ok = correr(g, TareaEspera(1.2, "a"))
    reloj.stop()
    ok = ok and ticks["n"] >= 3 and not fl["timeout"]
    return ok, f"ticks={ticks['n']}"


def test_06():
    g1 = GestorTareas()
    g2 = GestorTareas()
    cap1, cap2 = Captura(), Captura()
    for g, cap in ((g1, cap1), (g2, cap2)):
        g.tarea_iniciada.connect(cap.al_inicio)
        g.tarea_resultado.connect(cap.al_resultado)
        g.tarea_finalizada.connect(cap.al_finalizada)

    bucle = QEventLoop()
    flags = {"timeout": False, "fin": 0}

    def fin():
        flags["fin"] += 1
        if flags["fin"] == 2:
            bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    g1.tarea_finalizada.connect(fin)
    g2.tarea_finalizada.connect(fin)
    QTimer.singleShot(6000, por_si_acaso)

    ok1 = g1.iniciar(TareaEspera(0.7, "g1"))
    ok2 = g2.iniciar(TareaEspera(0.7, "g2"))
    h1, h2 = g1.hilo, g2.hilo
    hilos_distintos = h1 is not None and h2 is not None and id(h1) != id(h2)
    bucle.exec()

    ok = (
        ok1
        and ok2
        and hilos_distintos
        and not flags["timeout"]
        and cap1.eventos == ["inicio", "resultado", "finalizada"]
        and cap2.eventos == ["inicio", "resultado", "finalizada"]
        and (cap1.resultado or {}).get("etiqueta") == "g1"
        and (cap2.resultado or {}).get("etiqueta") == "g2"
    )
    return (
        ok,
        f"e1={cap1.eventos} e2={cap2.eventos} "
        f"hilos_distintos={hilos_distintos}",
    )


def test_07():
    g = GestorTareas()
    cap1, fl1, ok1 = correr(g, TareaEspera(0.3, "primera"))
    estado_entre = g.estado
    cap2, fl2, ok2 = correr(g, TareaEspera(0.3, "segunda"))
    ok = (
        ok1
        and ok2
        and (cap1.resultado or {}).get("etiqueta") == "primera"
        and (cap2.resultado or {}).get("etiqueta") == "segunda"
        and estado_entre == Estado.INACTIVO
        and g.estado == Estado.INACTIVO
        and not fl1["timeout"]
        and not fl2["timeout"]
    )
    return (
        ok,
        f"estado_entre={estado_entre} estado_final={g.estado} "
        f"t1={(cap1.resultado or {}).get('etiqueta')} "
        f"t2={(cap2.resultado or {}).get('etiqueta')}",
    )


def test_08():
    g = GestorTareas()
    t1 = TareaEspera(0.8, "a")
    t2 = TareaEspera(0.8, "b")

    bucle = QEventLoop()
    flags = {"timeout": False}

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    try:
        g.iniciar("no-es-tarea")
        tipo_invalido = False
    except TypeError:
        tipo_invalido = True

    ok_inicio = g.iniciar(t1)
    reemplazo = g.iniciar(t2)
    reinicio = g.iniciar(t1)

    g.tarea_finalizada.connect(fin)
    QTimer.singleShot(6000, por_si_acaso)
    bucle.exec()

    reuso = g.iniciar(t1)
    ok = (
        ok_inicio
        and not reemplazo
        and not reinicio
        and tipo_invalido
        and not reuso
        and not flags["timeout"]
    )
    return (
        ok,
        f"reemplazo={reemplazo} reinicio={reinicio} "
        f"tipo_invalido={tipo_invalido} reuso={reuso}",
    )


def test_09():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaEspera(0.3, "a"))
    try:
        e = g.estado
        a = g.activo
        h = g.hilo
        t = g.tarea
    except RuntimeError as exc:
        return False, f"RuntimeError: {exc}"
    ok = ok and e == Estado.INACTIVO and a is False and h is None and t is None
    return ok, f"estado={e} activo={a} hilo={h} tarea={t}"


def test_10():
    g = GestorTareas()
    ok1 = g.cerrar()
    ok2 = not g.iniciar(TareaEspera(0.1, "x"))
    return (
        ok1 and ok2 and g.estado == Estado.CERRADO,
        f"cerrar={ok1} estado={g.estado}",
    )


def test_11():
    g = GestorTareas()
    ok_inicio = g.iniciar(TareaEspera(0.5, "a"))
    h = g.hilo
    cerrado = g.cerrar(timeout_ms=3000)
    try:
        running = h.isRunning()
    except RuntimeError:
        running = "colgado"
    ok = ok_inicio and cerrado and g.estado == Estado.CERRADO and running is False
    return ok, f"cerrar={cerrado} estado={g.estado} running={running}"


def test_12():
    antes = len(QT_MENSAJES)
    bucle = QEventLoop()
    flags = {"timeout": False}
    hilo = []

    def crear():
        g = GestorTareas()
        ok = g.iniciar(TareaEspera(0.6, "a"))
        hilo.append(g.hilo)
        return ok

    ok_inicio = crear()
    hilo[0].finished.connect(bucle.quit)
    QTimer.singleShot(6000, lambda: (flags.__setitem__("timeout", True), bucle.quit()))
    bucle.exec()

    nuevos = QT_MENSAJES[antes:]
    avisos = [m for m in nuevos if "Destroyed while thread" in m]
    ok = ok_inicio and not flags["timeout"] and not avisos
    return ok, f"avisos={len(avisos)} qt_nuevos={nuevos}"


def test_13():
    bucle = QEventLoop()
    QTimer.singleShot(100, bucle.quit)
    bucle.exec()
    avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
    hilos_python = [
        t for t in threading.enumerate() if t is not threading.main_thread()
    ]
    ok = (
        not avisos
        and len(hilos_python) == 0
        and len(_GESTORES_ACTIVOS) == 0
    )
    return (
        ok,
        f"avisos={len(avisos)} python_threads={len(hilos_python)} "
        f"gestores_activos={len(_GESTORES_ACTIVOS)}",
    )


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
        test_09,
        test_10,
        test_11,
        test_12,
        test_13,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/13")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
