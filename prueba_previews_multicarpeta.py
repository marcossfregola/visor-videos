import contextlib
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tareas_mod
import visor_videos
from configuracion import (
    MODO_ALCANCE_SELECCION,
    MODO_ALCANCE_SOLO,
    MODO_ALCANCE_SUBCARPETAS,
)
from visor_videos import VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

CANTIDAD = 3


def _esperar(predicado, timeout_ms=30000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _cadena_terminada(v):
    return (
        v.gestor.hilo is None
        and not v._escaneo_pendiente
        and not v._tamanos_pendiente
        and not v._ffprobe_pendiente
        and not v._miniaturas_pendiente
        and not v._guardado_pendiente
        and not v._sincronizacion_pendiente
        and not v._recarga_catalogo_pendiente
    )


def _previews_hechas(mini):
    if not os.path.isdir(mini):
        return []
    return sorted(a for a in os.listdir(mini) if "_preview_" in a)


@contextlib.contextmanager
def _escenario(nombres_carpetas):
    """Crea carpetas reales con archivos de video (no vacios) y miniaturas aisladas."""
    mini = tempfile.TemporaryDirectory()
    original_min = escanear_mod.ruta_carpeta_miniaturas
    visor_min = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name

    carpetas = []
    temp = tempfile.TemporaryDirectory()
    carpetas_tmp = []
    for lista in nombres_carpetas:
        carpeta = tempfile.TemporaryDirectory(dir=temp.name)
        carpetas_tmp.append(carpeta)
        for nombre in lista:
            ruta_archivo = os.path.join(carpeta.name, nombre)
            os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
            with open(ruta_archivo, "wb") as f:
                f.write(b"video")
        carpetas.append(carpeta.name)

    def _generar(ruta_video, destino, indice=None, duracion_segundos=None):
        imagen = QImage(40, 30, QImage.Format_RGB32)
        imagen.fill(QColor("green"))
        imagen.save(destino, "PNG")
        return True

    def _ffprobe_falso(ruta):
        # B8.2 corrección: duración válida finita >0 para regla productiva.
        # Evita que producción skippee previews por duración inválida;
        # mantiene fuerza funcional P02-P05 sin lógica test-aware.
        return {"duracion_segundos": 10.0, "ancho": 640, "alto": 360, "codec_video": "h264"}

    original_generar = escanear_mod.generar_preview
    original_ffprobe = escanear_mod.obtener_datos_ffprobe
    original_ffprobe_tv = tareas_mod.obtener_datos_ffprobe
    escanear_mod.generar_preview = _generar
    escanear_mod.obtener_datos_ffprobe = _ffprobe_falso
    tareas_mod.obtener_datos_ffprobe = _ffprobe_falso
    try:
        yield {
            "mini": mini.name,
            "carpetas": carpetas,
            "temp": temp.name,
            "mini_cleanup": mini.cleanup,
            "temp_cleanup": temp.cleanup,
        }
    finally:
        escanear_mod.generar_preview = original_generar
        escanear_mod.obtener_datos_ffprobe = original_ffprobe
        tareas_mod.obtener_datos_ffprobe = original_ffprobe_tv
        escanear_mod.ruta_carpeta_miniaturas = original_min
        visor_videos.ruta_carpeta_miniaturas = visor_min
        mini.cleanup()
        temp.cleanup()
        for carpeta_tmp in carpetas_tmp:
            carpeta_tmp.cleanup()


def _esperar_previews_hechas(mini, esperados, timeout_ms=40000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if len(_previews_hechas(mini)) >= esperados:
            return True
        time.sleep(0.05)
    QApplication.processEvents()
    return False


def _escaneo_y_previews(ventana, mini, esperados, carpeta_seleccionada="__mantener__"):
    if carpeta_seleccionada != "__mantener__":
        ventana.carpeta_seleccionada = carpeta_seleccionada
    ventana.iniciar_escaneo()
    ok_cadena = _esperar(lambda v=ventana: _cadena_terminada(v), timeout_ms=60000)
    ok_previews = _esperar_previews_hechas(mini, esperados)
    _esperar(
        lambda: (not ventana.gestor_previews.activo) and not ventana._cola_previews,
        timeout_ms=60000,
    )
    QApplication.processEvents()
    hechas = _previews_hechas(mini)
    return ok_cadena, ok_previews, len(hechas), hechas


def test_01():
    modulos = [
        "visor_videos.py",
        "escanear_videos.py",
        "tareas_videos.py",
        "tareas.py",
        "prueba_previews_multicarpeta.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Escenario 1: carpeta unica (Solo carpeta actual)."""
    with _escenario([["a.mp4", "b.mp4"]]) as esc:
        temp = tempfile.TemporaryDirectory()
        ruta_db = os.path.join(temp.name, "catalogo.db")
        conn = escanear_mod.conectar_bd(ruta_db)
        conn.close()
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana._modo_alcance = MODO_ALCANCE_SOLO
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ok1, ok2, n, hechas = _escaneo_y_previews(
                ventana, esc["mini"], 6, carpeta_seleccionada=esc["carpetas"][0]
            )
            detalle = f"cadena={ok1} previews_ok={ok2} previews={n}"
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            ventana.deleteLater()
            QApplication.processEvents()
            temp.cleanup()
            return (
                ok1 and ok2 and n == 6,
                detalle,
            )
        finally:
            temp.cleanup()


def test_03():
    """Escenario 2: carpeta + subcarpetas (recursivo)."""
    with _escenario([["a.mp4", "sub/b.mp4"]]) as esc:
        temp = tempfile.TemporaryDirectory()
        ruta_db = os.path.join(temp.name, "catalogo.db")
        conn = escanear_mod.conectar_bd(ruta_db)
        conn.close()
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana._modo_alcance = MODO_ALCANCE_SUBCARPETAS
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ok1, ok2, n, hechas = _escaneo_y_previews(
                ventana, esc["mini"], 6, carpeta_seleccionada=esc["carpetas"][0]
            )
            # B8.2: naming por id (v<id>_preview) no contiene nombre subcarpeta, verificar 2 videos distintos
            prefijos = sorted({a.split("_preview_")[0] for a in hechas})
            subfoto = len(prefijos) == 2 and n == 6
            detalle = f"cadena={ok1} previews_ok={ok2} previews={n} subfoto={subfoto} prefijos={prefijos}"
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            ventana.deleteLater()
            QApplication.processEvents()
            return (
                ok1 and ok2 and n == 6 and subfoto,
                detalle,
            )
        finally:
            temp.cleanup()


def test_04():
    """Escenario 3: seleccion personalizada con UNA carpeta y carpeta_seleccionada=None.

    Regresion original: las previews nunca comenzaban porque el sistema dependia
    de carpeta_seleccionada. Ahora cada video usa su propia carpeta del catalogo.
    """
    with _escenario([["a.mp4", "b.mp4"]]) as esc:
        temp = tempfile.TemporaryDirectory()
        ruta_db = os.path.join(temp.name, "catalogo.db")
        conn = escanear_mod.conectar_bd(ruta_db)
        conn.close()
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana._modo_alcance = MODO_ALCANCE_SELECCION
            ventana.seleccion_carpetas.seleccionar(esc["carpetas"][0])
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ok1, ok2, n, hechas = _escaneo_y_previews(
                ventana, esc["mini"], 6, carpeta_seleccionada=None
            )
            detalle = f"cadena={ok1} previews_ok={ok2} previews={n}"
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            ventana.deleteLater()
            QApplication.processEvents()
            return (
                ok1 and ok2 and n == 6,
                detalle,
            )
        finally:
            temp.cleanup()


def test_05():
    """Escenario 4: seleccion personalizada con MULTIPLES carpetas.

    Cada video debe generar sus previews usando su propia carpeta real.
    """
    with _escenario([["a.mp4", "b.mp4"], ["c.mp4", "d.mp4"]]) as esc:
        temp = tempfile.TemporaryDirectory()
        ruta_db = os.path.join(temp.name, "catalogo.db")
        conn = escanear_mod.conectar_bd(ruta_db)
        conn.close()
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana._modo_alcance = MODO_ALCANCE_SELECCION
            ventana.seleccion_carpetas.seleccionar(esc["carpetas"][0])
            ventana.seleccion_carpetas.seleccionar(esc["carpetas"][1])
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ok1, ok2, n, hechas = _escaneo_y_previews(
                ventana, esc["mini"], 12, carpeta_seleccionada=esc["carpetas"][0]
            )
            # B8.2: naming por id (v<id>_preview_XX.jpg) preservando contrato histórico 4 videos /12 previews
            # Sin reducir cobertura ni exigir interacción manual; los 4 videos deben terminar con sus 12 previews.
            prefijos = sorted({os.path.basename(a).split("_preview_")[0] for a in hechas})
            ok_pref = len(prefijos) == 4 and n == 12 and all(p.startswith("v") for p in prefijos)
            detalle = f"cadena={ok1} previews_ok={ok2} previews={n} nombres={prefijos}"
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            ventana.deleteLater()
            QApplication.processEvents()
            return (
                ok1 and ok2 and n == 12 and ok_pref,
                detalle,
            )
        finally:
            temp.cleanup()


def main():
    app = QApplication(sys.argv)
    pruebas = [test_01, test_02, test_03, test_04, test_05]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
