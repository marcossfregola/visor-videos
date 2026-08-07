import py_compile
import sys
import threading
import time

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

from tareas import GestorTareas, TareaBase, Estado, _GESTORES_ACTIVOS, _RelayTarea


class TareaConProgreso(TareaBase):
    def __init__(self, total, intervalo=0.05, usar_helper=True):
        super().__init__()
        self.total = total
        self.intervalo = intervalo
        self.usar_helper = usar_helper

    def _trabajo(self):
        for i in range(self.total + 1):
            if self.usar_helper:
                self.reportar_progreso(i, self.total)
            else:
                self.progreso.emit(i, self.total)
            time.sleep(self.intervalo)
        return {"total": self.total}


class TareaSinProgreso(TareaBase):
    def _trabajo(self):
        time.sleep(0.1)
        return {"ok": True}


class Captura:
    def __init__(self):
        self.eventos = []
        self.progresos = []
        self.resultado = None
        self.error = None
        self.ids = {}

    def al_inicio(self):
        self.eventos.append("inicio")
        self.ids["inicio"] = (threading.get_ident(), QThread.isMainThread())

    def al_progreso(self, procesado, total):
        self.eventos.append("progreso")
        self.progresos.append((procesado, total))
        self.ids.setdefault(
            "progreso", (threading.get_ident(), QThread.isMainThread())
        )

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
    gestor.tarea_progreso.connect(captura.al_progreso)
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
    gestor.tarea_progreso.disconnect(captura.al_progreso)
    gestor.tarea_resultado.disconnect(captura.al_resultado)
    gestor.tarea_error.disconnect(captura.al_error)
    gestor.tarea_finalizada.disconnect(captura.al_finalizada)
    gestor.tarea_finalizada.disconnect(fin)
    return captura, flags, ok


def test_01():
    py_compile.compile("tareas.py", doraise=True)
    py_compile.compile("prueba_infraestructura_progreso.py", doraise=True)
    t = TareaBase()
    g = GestorTareas()
    ok = (
        hasattr(TareaBase, "progreso")
        and isinstance(t.progreso, Signal)
        and hasattr(GestorTareas, "tarea_progreso")
        and isinstance(g.tarea_progreso, Signal)
        and callable(TareaBase.reportar_progreso)
    )
    return ok, f"progreso={hasattr(TareaBase, 'progreso')} tarea_progreso={hasattr(GestorTareas, 'tarea_progreso')}"


def test_02():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaConProgreso(3))
    ok = (
        ok
        and cap.eventos
        == ["inicio", "progreso", "progreso", "progreso", "progreso", "resultado", "finalizada"]
        and cap.progresos == [(0, 3), (1, 3), (2, 3), (3, 3)]
        and not fl["timeout"]
        and g.estado == Estado.INACTIVO
    )
    return ok, f"eventos={cap.eventos} progresos={cap.progresos}"


def test_03():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaConProgreso(2, usar_helper=False))
    ok = (
        ok
        and cap.eventos
        == ["inicio", "progreso", "progreso", "progreso", "resultado", "finalizada"]
        and cap.progresos == [(0, 2), (1, 2), (2, 2)]
        and not fl["timeout"]
    )
    return ok, f"eventos={cap.eventos} progresos={cap.progresos}"


def test_04():
    id_py_main = threading.get_ident()
    g = GestorTareas()
    cap, fl, _ = correr(g, TareaConProgreso(2))
    ok = (
        cap.progresos != []
        and all(qt and py == id_py_main for py, qt in cap.ids.values())
        and "progreso" in cap.ids
    )
    return ok, f"ids={cap.ids}"


def test_05():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaSinProgreso())
    ok = (
        ok
        and cap.eventos == ["inicio", "resultado", "finalizada"]
        and cap.progresos == []
        and (cap.resultado or {}).get("ok") is True
        and not fl["timeout"]
    )
    return ok, f"eventos={cap.eventos} progresos={cap.progresos}"


def test_06():
    t = TareaBase()
    recibidos = []
    t.progreso.connect(lambda p, x: recibidos.append((p, x)))
    t.reportar_progreso(1, 3)
    t.reportar_progreso(5, 3)
    t.reportar_progreso(-2, 3)
    t.reportar_progreso(2, 0)
    t.reportar_progreso(2, -1)
    t.reportar_progreso("a", 3)
    t.reportar_progreso(2.9, 3)
    t.reportar_progreso(2, "3")
    ok = (
        recibidos
        == [(1, 3), (3, 3), (0, 3), (2, 3), (2, 3)]
    )
    return ok, f"recibidos={recibidos}"


def test_07():
    class GestorFalso(QObject):
        tarea_progreso = Signal(int, int)

        def __init__(self):
            super().__init__()
            self._token = 0

    g = GestorFalso()
    relay = _RelayTarea(g)
    recibidos = []
    g.tarea_progreso.connect(lambda p, x: recibidos.append((p, x)))
    relay.al_progreso(1, 3)
    g._token += 1
    relay.al_progreso(2, 3)
    relay.al_progreso(3, 3)
    ok = recibidos == [(1, 3)]
    return ok, f"recibidos={recibidos}"


def test_08():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaConProgreso(1))
    try:
        e = g.estado
        a = g.activo
        h = g.hilo
        t = g.tarea
    except RuntimeError as exc:
        return False, f"RuntimeError: {exc}"
    ok = ok and e == Estado.INACTIVO and a is False and h is None and t is None
    return ok, f"estado={e} activo={a}"


def test_09():
    bucle = QEventLoop()
    QTimer.singleShot(100, bucle.quit)
    bucle.exec()
    hilos_python = [
        t for t in threading.enumerate() if t is not threading.main_thread()
    ]
    ok = (
        len(hilos_python) == 0
        and len(_GESTORES_ACTIVOS) == 0
    )
    return (
        ok,
        f"python_threads={len(hilos_python)} gestores_activos={len(_GESTORES_ACTIVOS)}",
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
    print(f"TOTAL={aprobadas}/9")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
