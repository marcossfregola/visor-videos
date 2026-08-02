import os
import py_compile
import shutil
import sqlite3
import sys
import tempfile
import threading

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaEscaneo

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


def _crear_carpeta(nombres):
    temp = tempfile.TemporaryDirectory()
    carpeta = temp.name
    for nombre in nombres:
        with open(os.path.join(carpeta, nombre), "wb") as f:
            f.write(b"x")
    return temp, carpeta


class TareaEscaneoConHilo(TareaEscaneo):
    def __init__(self, carpeta):
        super().__init__(carpeta)
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
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_escaneo.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, carpeta = _crear_carpeta(["a.mp4", "b.mkv", "c.avi"])
    try:
        esperado = escanear_mod.escanear_videos(carpeta)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.error is None
            and cap.resultado == esperado
            and g.estado == Estado.INACTIVO
            and g.hilo is None
        )
        return (
            ok,
            f"resultado={cap.resultado} esperado={esperado} eventos={cap.eventos}",
        )
    finally:
        temp.cleanup()


def test_03():
    nombres = ["z.mp4", "a.avi", "m.mkv", "b.mp4"]
    temp, carpeta = _crear_carpeta(nombres)
    try:
        esperado = escanear_mod.escanear_videos(carpeta)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        orden_esperado = list(esperado)
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == esperado
            and cap.resultado == sorted(cap.resultado)
            and orden_esperado == sorted(orden_esperado)
        )
        return ok, f"resultado={cap.resultado}"
    finally:
        temp.cleanup()


def test_04():
    nombres = ["peli.mp4", "doc.txt", "nota.log", "imagen.png", "sin_ext", "serie.mkv", "clip.AVI"]
    temp, carpeta = _crear_carpeta(nombres)
    try:
        esperado = escanear_mod.escanear_videos(carpeta)
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        esperados = ["peli.mp4", "serie.mkv", "clip.AVI"]
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == sorted(esperados)
            and cap.resultado == esperado
            and not any(n in cap.resultado for n in ("doc.txt", "nota.log", "imagen.png", "sin_ext"))
        )
        return ok, f"resultado={cap.resultado}"
    finally:
        temp.cleanup()


def test_05():
    temp, carpeta = _crear_carpeta([])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.resultado == []
            and cap.error is None
        )
        return ok, f"resultado={cap.resultado} eventos={cap.eventos}"
    finally:
        temp.cleanup()


def test_06():
    base = tempfile.mkdtemp()
    try:
        inexistente = os.path.join(base, "carpeta_inexistente")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(inexistente))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "FileNotFoundError" in cap.error
        )
        return ok, f"error={cap.error!r}"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_07():
    temp, carpeta = _crear_carpeta(["un_video.mp4"])
    try:
        archivo = os.path.join(carpeta, "un_video.mp4")
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(archivo))
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "NotADirectoryError" in cap.error
        )
        return ok, f"error={cap.error!r}"
    finally:
        temp.cleanup()


def test_08():
    temp, carpeta = _crear_carpeta(["a.mp4"])
    try:
        original = tv.escanear_videos

        def _falla(_):
            raise RuntimeError("fallo controlado")

        tv.escanear_videos = _falla
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        finally:
            tv.escanear_videos = original
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "error", "finalizada"]
            and cap.resultado is None
            and cap.error is not None
            and "RuntimeError" in cap.error
            and "fallo controlado" in cap.error
        )
        return ok, f"error={cap.error!r}"
    finally:
        temp.cleanup()


def test_09():
    temp, carpeta = _crear_carpeta(["a.mp4", "b.avi"])
    try:
        llamadas = {"sqlite": 0, "subprocess": 0, "ffprobe": 0}
        sqlite_original = sqlite3.connect
        subprocess_original = escanear_mod.subprocess.run
        ffprobe_original = tv.obtener_datos_ffprobe

        def _conectar(*args, **kwargs):
            llamadas["sqlite"] += 1
            raise AssertionError("SQLite no debe invocarse")

        def _run(*args, **kwargs):
            llamadas["subprocess"] += 1
            raise AssertionError("No debe ejecutarse subproceso")

        def _ffprobe(*args, **kwargs):
            llamadas["ffprobe"] += 1
            raise AssertionError("FFprobe no debe invocarse")

        sqlite3.connect = _conectar
        escanear_mod.subprocess.run = _run
        tv.obtener_datos_ffprobe = _ffprobe
        try:
            g = GestorTareas()
            cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        finally:
            sqlite3.connect = sqlite_original
            escanear_mod.subprocess.run = subprocess_original
            tv.obtener_datos_ffprobe = ffprobe_original
        ok = (
            ok
            and not fl["timeout"]
            and cap.resultado == sorted(["a.mp4", "b.avi"])
            and llamadas == {"sqlite": 0, "subprocess": 0, "ffprobe": 0}
        )
        return ok, f"llamadas={llamadas} resultado={cap.resultado}"
    finally:
        temp.cleanup()


def test_10():
    miniaturas = ruta_carpeta_miniaturas()
    bd = ruta_biblioteca()

    def estado_real():
        return (
            os.path.isfile(bd),
            os.path.getmtime(bd) if os.path.isfile(bd) else None,
            sorted(os.listdir(miniaturas)) if os.path.isdir(miniaturas) else None,
        )

    antes = estado_real()
    temp, carpeta = _crear_carpeta(["x.mp4", "y.txt"])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
    finally:
        temp.cleanup()
    despues = estado_real()
    ok = (
        ok
        and not fl["timeout"]
        and cap.resultado == ["x.mp4"]
        and antes == despues
    )
    return ok, f"resultado={cap.resultado} datos_reales_sin_cambios={antes == despues}"


def test_11():
    temp, carpeta = _crear_carpeta(["a.mp4", "b.mkv"])
    try:
        g = GestorTareas()
        cap, fl, ok = correr(g, TareaEscaneo(carpeta))
        hilos_python = [
            t for t in threading.enumerate() if t is not threading.main_thread()
        ]
        avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
        ok = (
            ok
            and not fl["timeout"]
            and g.estado == Estado.INACTIVO
            and g.hilo is None
            and g.tarea is None
            and len(hilos_python) == 0
            and len(_GESTORES_ACTIVOS) == 0
            and not avisos
        )
        return (
            ok,
            f"estado={g.estado} hilos={len(hilos_python)} "
            f"gestores={len(_GESTORES_ACTIVOS)} avisos={len(avisos)}",
        )
    finally:
        temp.cleanup()


def test_12():
    id_main = threading.get_ident()
    temp, carpeta = _crear_carpeta(["a.mp4"])
    try:
        g = GestorTareas()
        tarea = TareaEscaneoConHilo(carpeta)
        cap, fl, ok = correr(g, tarea)
        ok = (
            ok
            and not fl["timeout"]
            and tarea.identificador is not None
            and tarea.identificador != id_main
            and tarea.en_principal is False
            and cap.resultado == ["a.mp4"]
            and set(cap.ids) == {"inicio", "resultado", "finalizada"}
            and all(py == id_main and qt for py, qt in cap.ids.values())
        )
        return (
            ok,
            f"main={id_main} worker={tarea.identificador} "
            f"en_principal={tarea.en_principal}",
        )
    finally:
        temp.cleanup()


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
