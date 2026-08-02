import os
import py_compile
import sys
import threading

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from rutas import ruta_carpeta_videos
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaFFprobe, rutas_videos

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


def _videos():
    return rutas_videos()


def _real():
    for ruta in _videos():
        if os.path.basename(ruta) == "video_real.mp4":
            return ruta
    return None


def _vacios():
    return [ruta for ruta in _videos() if os.path.basename(ruta) != "video_real.mp4"]


class TareaFFprobeConHilo(TareaFFprobe):
    def __init__(self, rutas):
        super().__init__(rutas)
        self.identificador = None
        self.en_principal = None

    def _trabajo(self):
        self.identificador = threading.get_ident()
        self.en_principal = QThread.isMainThread()
        return super()._trabajo()


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
    modulos = [
        "tareas.py",
        "escanear_videos.py",
        "rutas.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_ffprobe.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    real = _real()
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe([real]))
    r = cap.resultado or {}
    resultados = r.get("resultados") or []
    unico = resultados[0] if resultados else {}
    datos = unico.get("datos")
    ok = (
        ok
        and cap.eventos == ["inicio", "resultado", "finalizada"]
        and not fl["timeout"]
        and len(resultados) == 1
        and datos is not None
        and abs(datos["duracion_segundos"] - 5.0) < 0.1
        and datos["ancho"] == 640
        and datos["alto"] == 360
        and datos["codec_video"] == "h264"
        and unico.get("error") is None
    )
    return ok, f"datos={datos} eventos={cap.eventos}"


def test_03():
    vacios = _vacios()
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe(vacios))
    r = cap.resultado or {}
    resultados = r.get("resultados") or []
    ok = (
        ok
        and not fl["timeout"]
        and cap.eventos == ["inicio", "resultado", "finalizada"]
        and len(resultados) == len(vacios)
        and all(x["datos"] is None for x in resultados)
        and all(x["error"] == "archivo vacio" for x in resultados)
        and r.get("con_datos") == 0
        and r.get("con_error") == len(vacios)
    )
    return ok, f"vacios={len(vacios)} con_error={r.get('con_error')}"


def test_04():
    todos = _videos()
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe(todos))
    r = cap.resultado or {}
    resultados = r.get("resultados") or []
    por_nombre = {os.path.basename(x["ruta"]): x for x in resultados}
    real = por_nombre.get("video_real.mp4", {})
    ok = (
        ok
        and not fl["timeout"]
        and r.get("procesados") == len(todos)
        and r.get("con_datos") == 1
        and r.get("con_error") == len(todos) - 1
        and real.get("datos") is not None
        and all(
            por_nombre[n]["error"] == "archivo vacio"
            for n in ("video_01.mp4", "video_03.avi", "video_04.mp4")
        )
    )
    return (
        ok,
        f"procesados={r.get('procesados')} con_datos={r.get('con_datos')} "
        f"con_error={r.get('con_error')}",
    )


def test_05():
    real = _real()
    inexistente = os.path.join(ruta_carpeta_videos(), "no_existe.mp4")
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe([real, inexistente]))
    r = cap.resultado or {}
    resultados = r.get("resultados") or []
    ok = (
        ok
        and not fl["timeout"]
        and cap.eventos == ["inicio", "resultado", "finalizada"]
        and len(resultados) == 2
        and resultados[0]["datos"] is not None
        and resultados[0]["error"] is None
        and resultados[1]["datos"] is None
        and "inexistente" in resultados[1]["error"]
        and r.get("con_datos") == 1
        and r.get("con_error") == 1
    )
    return (
        ok,
        f"e0={resultados[0]['error']} e1={resultados[1]['error']} "
        f"con_datos={r.get('con_datos')}",
    )


def test_06():
    id_main = threading.get_ident()
    g = GestorTareas()
    tarea = TareaFFprobeConHilo(_videos())
    cap, fl, ok = correr(g, tarea)
    ok = (
        ok
        and not fl["timeout"]
        and tarea.identificador is not None
        and tarea.identificador != id_main
        and tarea.en_principal is False
    )
    return (
        ok,
        f"main={id_main} worker={tarea.identificador} en_principal={tarea.en_principal}",
    )


def test_07():
    id_main = threading.get_ident()
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe(_videos()))
    ok_slots = (
        set(cap.ids) == {"inicio", "resultado", "finalizada"}
        and all(py == id_main and qt for py, qt in cap.ids.values())
    )
    ok = ok and ok_slots and not fl["timeout"]
    return ok, f"ids={cap.ids}"


def test_08():
    real = _real()
    rutas = [real] * 15
    g = GestorTareas()
    ticks = {"n": 0}
    reloj = QTimer()
    reloj.setInterval(20)
    reloj.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    reloj.start()
    cap, fl, ok = correr(g, TareaFFprobe(rutas))
    reloj.stop()
    ok = ok and not fl["timeout"] and ticks["n"] >= 1
    return (
        ok,
        f"ticks={ticks['n']} procesados={(cap.resultado or {}).get('procesados')}",
    )


def test_09():
    g = GestorTareas()
    bucle = QEventLoop()
    flags = {"timeout": False}

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    ok1 = g.iniciar(TareaFFprobe(_videos()))
    ok2 = g.iniciar(TareaFFprobe(_videos()))
    rechazo = g.ultimo_rechazo
    g.tarea_finalizada.connect(fin)
    QTimer.singleShot(6000, por_si_acaso)
    bucle.exec()
    ok = (
        ok1
        and not ok2
        and rechazo == "ya hay una tarea en curso"
        and not flags["timeout"]
        and g.estado == Estado.INACTIVO
    )
    return ok, f"ok1={ok1} ok2={ok2} rechazo={rechazo} estado={g.estado}"


def test_10():
    g = GestorTareas()
    ok_inicio = g.iniciar(TareaFFprobe(_videos()))
    hilo = g.hilo
    cerrado = g.cerrar(timeout_ms=3000)
    try:
        running = hilo.isRunning()
    except RuntimeError:
        running = "colgado"
    ok = ok_inicio and cerrado and g.estado == Estado.CERRADO and running is False
    return ok, f"cerrar={cerrado} estado={g.estado} running={running}"


def test_11():
    g = GestorTareas()
    cap, fl, ok = correr(g, TareaFFprobe([]))
    r = cap.resultado or {}
    ok = (
        ok
        and not fl["timeout"]
        and r.get("procesados") == 0
        and cap.eventos == ["inicio", "resultado", "finalizada"]
    )
    return ok, f"procesados={r.get('procesados')} eventos={cap.eventos}"


def test_12():
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
    print(f"TOTAL={aprobadas}/12")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
