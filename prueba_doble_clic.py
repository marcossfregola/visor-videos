import ast
import contextlib
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEventLoop, Qt, QTimer, qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

import apertura_videos
import visor_videos
from rutas import ruta_raiz
from visor_videos import (
    MENSAJE_ERROR_ABRIR,
    Tarjeta,
    VisorVideos,
)

QT_MENSAJES = []

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


def _filas(nombres):
    filas = []
    for i, nombre in enumerate(nombres, start=1):
        filas.append(
            (
                nombre,
                os.path.join("C:\\", nombre),
                os.path.splitext(nombre)[1].lower(),
                "2026-08-04T00:00:00",
                float(i % 5),
                i,
                i,
                "h264",
                i % 3,
            )
        )
    return filas


def _crear_bd(filas):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute(
            """
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                ruta TEXT NOT NULL,
                extension TEXT NOT NULL,
                fecha_importacion TEXT NOT NULL,
                duracion_segundos REAL,
                ancho INTEGER,
                alto INTEGER,
                codec_video TEXT,
                cantidad_miniaturas INTEGER,
                tamano_bytes INTEGER
            )
            """
        )
        conn.executemany(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


def _carpeta_con(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        with open(os.path.join(temp.name, nombre), "w", encoding="utf-8") as f:
            f.write("contenido")
    return temp


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _mostrar(ventana):
    ventana.resize(900, 600)
    ventana.show()
    QApplication.processEvents()
    _procesar(80)
    QApplication.processEvents()


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


@contextlib.contextmanager
def _dialogo_falso(ruta):
    original = visor_videos.QFileDialog.getExistingDirectory
    visor_videos.QFileDialog.getExistingDirectory = lambda *a, **k: ruta
    try:
        yield
    finally:
        visor_videos.QFileDialog.getExistingDirectory = original


@contextlib.contextmanager
def _startfile_falso(fn):
    original = apertura_videos.os.startfile
    apertura_videos.os.startfile = fn
    try:
        yield
    finally:
        apertura_videos.os.startfile = original


@contextlib.contextmanager
def _servicio_falso(fn):
    original = visor_videos.abrir_video_con_aplicacion_predeterminada
    visor_videos.abrir_video_con_aplicacion_predeterminada = fn
    try:
        yield
    finally:
        visor_videos.abrir_video_con_aplicacion_predeterminada = original


def _doble_clic(tarjeta):
    QTest.mouseDClick(tarjeta, Qt.LeftButton)


# ===================== SERVICIO =====================


def test_01():
    modulos = [
        "apertura_videos.py",
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_doble_clic.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        abiertas = []
        with _startfile_falso(lambda r: abiertas.append(r) or 42):
            ruta = apertura_videos.abrir_video_con_aplicacion_predeterminada(
                "a.mp4", carpeta.name
            )
        esperada = os.path.abspath(os.path.join(carpeta.name, "a.mp4"))
        ok = ruta == esperada and abiertas == [esperada]
        return ok, f"ruta={ruta} abiertas={abiertas} esperada={esperada}"
    finally:
        carpeta.cleanup()


def test_03():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        llamadas = []
        with _startfile_falso(lambda r: llamadas.append(r) or 42):
            ruta = apertura_videos.abrir_video_con_aplicacion_predeterminada(
                "a.mp4", carpeta.name
            )
        esperada = os.path.abspath(os.path.join(carpeta.name, "a.mp4"))
        ok = llamadas == [esperada] and ruta == esperada
        return ok, f"llamadas={llamadas} ruta={ruta}"
    finally:
        carpeta.cleanup()


def test_04():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        resultados = {}
        for caso in [None, "", "   ", 123]:
            try:
                apertura_videos.abrir_video_con_aplicacion_predeterminada(
                    "a.mp4", caso
                )
                resultados[repr(caso)] = "sin_error"
            except ValueError:
                resultados[repr(caso)] = "ValueError"
            except Exception as exc:
                resultados[repr(caso)] = f"{type(exc).__name__}"
        ok = all(v == "ValueError" for v in resultados.values())
        return ok, f"resultados={resultados}"
    finally:
        carpeta.cleanup()


def test_05():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        resultados = {}
        for caso in [None, "", "   ", 123]:
            try:
                apertura_videos.abrir_video_con_aplicacion_predeterminada(
                    caso, carpeta.name
                )
                resultados[repr(caso)] = "sin_error"
            except ValueError:
                resultados[repr(caso)] = "ValueError"
            except Exception as exc:
                resultados[repr(caso)] = f"{type(exc).__name__}"
        ok = all(v == "ValueError" for v in resultados.values())
        return ok, f"resultados={resultados}"
    finally:
        carpeta.cleanup()


def test_06():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        resultado = "sin_error"
        with _startfile_falso(lambda r: None):
            try:
                apertura_videos.abrir_video_con_aplicacion_predeterminada(
                    "inexistente.mp4", carpeta.name
                )
            except FileNotFoundError:
                resultado = "FileNotFoundError"
            except Exception as exc:
                resultado = f"{type(exc).__name__}"
        ok = resultado == "FileNotFoundError"
        return ok, f"resultado={resultado}"
    finally:
        carpeta.cleanup()


def test_07():
    carpeta = _carpeta_con(["a.mp4"])
    try:
        def _falla(ruta):
            raise OSError("no se puede abrir")

        resultado = "sin_error"
        with _startfile_falso(_falla):
            try:
                apertura_videos.abrir_video_con_aplicacion_predeterminada(
                    "a.mp4", carpeta.name
                )
            except OSError:
                resultado = "OSError"
            except Exception as exc:
                resultado = f"{type(exc).__name__}"
        ok = resultado == "OSError"
        return ok, f"resultado={resultado}"
    finally:
        carpeta.cleanup()


def test_08():
    ruta = os.path.join(ruta_raiz(), "apertura_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombres.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                nombres.add(nodo.module.split(".")[0])
            for alias in nodo.names:
                if alias.name != "*":
                    nombres.add(alias.name)
        elif isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
    ok = "subprocess" not in nombres and "Popen" not in nombres
    return ok, f"nombres_subprocess={'subprocess' in nombres}"


# ===================== INTERFAZ =====================


def test_09():
    fila = ("a.mp4", 5.0, 640, 360, "h264", 1, 100)
    tarjeta = Tarjeta(fila)
    recibidos = []
    tarjeta.doble_clic.connect(recibidos.append)
    contenedor = QWidget()
    layout = QHBoxLayout(contenedor)
    layout.addWidget(tarjeta)
    contenedor.resize(500, 300)
    contenedor.show()
    QApplication.processEvents()
    _doble_clic(tarjeta)
    QApplication.processEvents()
    contenedor.close()
    tarjeta.deleteLater()
    contenedor.deleteLater()
    ok = recibidos == ["a.mp4"]
    return ok, f"recibidos={recibidos}"


def test_10():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["a.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        _mostrar(ventana)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        llamadas = []
        with _servicio_falso(lambda n, c: llamadas.append((n, c)) or None):
            _doble_clic(ventana.tarjetas[0][1])
            QApplication.processEvents()
        ventana.close()
        _limpiar(ventana)
        carpeta_esperada = os.path.abspath(carpeta.name)
        ok = llamadas == [("a.mp4", carpeta_esperada)]
        return ok, f"llamadas={llamadas} carpeta_esperada={carpeta_esperada}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["a.mp4"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        _mostrar(ventana)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()

        def _falla(n, c):
            raise FileNotFoundError("no existe")

        sin_excepcion = True
        with _servicio_falso(_falla):
            try:
                _doble_clic(ventana.tarjetas[0][1])
                QApplication.processEvents()
            except Exception:
                sin_excepcion = False
        mensaje = ventana.mensaje_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = sin_excepcion and mensaje == MENSAJE_ERROR_ABRIR
        return ok, f"sin_excepcion={sin_excepcion} mensaje={mensaje!r}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        _mostrar(ventana)

        def _falla(n, c):
            raise ValueError("carpeta inválida")

        llamadas = []
        with _servicio_falso(lambda n, c: llamadas.append((n, c)) or _falla(n, c)):
            sin_excepcion = True
            try:
                _doble_clic(ventana.tarjetas[0][1])
                QApplication.processEvents()
            except Exception:
                sin_excepcion = False
        mensaje = ventana.mensaje_carpeta.text()
        ventana.close()
        _limpiar(ventana)
        ok = (
            sin_excepcion
            and llamadas == [("a.mp4", None)]
            and mensaje == MENSAJE_ERROR_ABRIR
        )
        return (
            ok,
            f"sin_excepcion={sin_excepcion} llamadas={llamadas} "
            f"mensaje={mensaje!r}",
        )
    finally:
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd(_filas(["a.mp4"]))
    carpeta = _carpeta_con(["a.mp4", "b.mkv"])
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        _mostrar(ventana)
        with _dialogo_falso(carpeta.name):
            ventana.seleccionar_carpeta()
        ventana._agregar_tarjetas([("b.mkv", 3.0, 320, 240, "h264", 1, 50)])
        QApplication.processEvents()
        llamadas = []
        with _servicio_falso(lambda n, c: llamadas.append((n, c)) or None):
            por_nombre = {nombre: tarjeta for nombre, tarjeta in ventana.tarjetas}
            _doble_clic(por_nombre["b.mkv"])
            _doble_clic(por_nombre["a.mp4"])
            QApplication.processEvents()
        ventana.close()
        _limpiar(ventana)
        carpeta_esperada = os.path.abspath(carpeta.name)
        ok = llamadas == [
            ("b.mkv", carpeta_esperada),
            ("a.mp4", carpeta_esperada),
        ]
        return ok, f"llamadas={llamadas}"
    finally:
        carpeta.cleanup()
        temp.cleanup()


def test_14():
    ruta = os.path.join(ruta_raiz(), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), ruta)

    def _referencia_os(attr):
        if attr.attr not in ("isfile", "startfile"):
            return False
        valor = attr.value
        if isinstance(valor, ast.Name):
            return valor.id == "os"
        return (
            isinstance(valor, ast.Attribute)
            and valor.attr == "path"
            and isinstance(valor.value, ast.Name)
            and valor.value.id == "os"
        )

    referencias = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Attribute) and _referencia_os(n)
    ]
    ok = len(referencias) == 0
    return ok, f"referencias={[getattr(r, 'attr', None) for r in referencias]}"


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
        test_14,
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
    print(f"TOTAL={aprobadas}/14")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
