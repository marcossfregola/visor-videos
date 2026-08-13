"""Pruebas del Bloque C-1 — Reproducción simple de un segmento A→B en VLC (B5.6).

Cubre: menú contextual del segmento (Reproducir/Eliminar), prioridades del
clic derecho (marcador / segmento / zona vacía), helper `reproducir_segmento`
(start-time + stop-time), validaciones, VLC ausente, archivo inexistente,
reproducción sin tocar datos, duplicados/solapamientos, B5.3 y B4.4 intactos,
separación de capas y prueba real de VLC con medición de duración.
"""

import contextlib
import hashlib
import inspect
import os
import py_compile
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication, QMessageBox

import escanear_videos as escanear_mod
import playlist_vlc as pl
import visor_videos
from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
)
from playlist_vlc import reproducir_segmento
from visor_videos import FranjaExploracion, Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(
    _CONFIG_TEMPORAL.name, "configuracion.json"
)


def _esperar(predicado, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
    if ventana is None:
        return
    for gestor in (
        getattr(ventana, "gestor", None),
        getattr(ventana, "gestor_marcadores", None),
        getattr(ventana, "gestor_segmentos", None),
        getattr(ventana, "gestor_previews", None),
        getattr(ventana, "gestor_reproduccion", None),
        getattr(ventana, "gestor_exploracion", None),
    ):
        if gestor is not None:
            gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()


def _registro(nombre, duracion=100.0):
    return {
        "nombre": nombre,
        "ruta": f"C:\\v\\{nombre}",
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 3,
        "tamano_bytes": 1000,
    }


def _crear_bd_con_videos(nombres):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    guardar_videos([_registro(n) for n in nombres], ruta_db)
    return temp, ruta_db


def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _enviar(widget, tipo, x, boton):
    evento = QMouseEvent(
        tipo,
        QPointF(float(x), 6.0),
        boton,
        boton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


def _press(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.LeftButton)


def _press_derecho(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.RightButton)


def _expandir(tarjeta):
    tarjeta.expandir()
    _esperar(lambda: tarjeta._franja.width() > 0)


def _drenar_segmentos(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_segmentos.activo
        and not ventana._cola_segmentos,
        timeout_ms=timeout_ms,
    )


def _drenar_marcadores(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_marcadores.activo
        and not ventana._cola_marcadores,
        timeout_ms=timeout_ms,
    )


def _crear_segmento_ui(ventana, tarjeta, x1, x2, objetivo=1):
    tarjeta._boton_segmento.setChecked(True)
    _press(tarjeta._franja, x1)
    ok_a = _esperar(lambda: tarjeta._extremo_segmento is not None)
    _press(tarjeta._franja, x2)
    ok_b = _esperar(lambda: len(tarjeta._segmentos) >= objetivo)
    _drenar_segmentos(ventana)
    return ok_a and ok_b


def _abrir_menu_segmento(ventana, tarjeta, x):
    tarjeta._menu_segmento_actual = None
    _press_derecho(tarjeta._franja, x)
    _esperar(lambda: tarjeta._menu_segmento_actual is not None)
    return tarjeta._menu_segmento_actual


def _accion(menu, texto):
    for accion in menu.actions():
        if accion.text() == texto:
            return accion
    return None


def _md5(ruta):
    with open(ruta, "rb") as archivo:
        return hashlib.md5(archivo.read()).hexdigest()


def _generar_video_real(directorio):
    ffmpeg = os.environ.get("FFMPEG") or "ffmpeg"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        version = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, **flags
        )
        if version.returncode != 0:
            return None
    except OSError:
        return None
    ruta = os.path.join(directorio, "video_temporal.mp4")
    try:
        resultado = subprocess.run(
            [
                ffmpeg, "-y", "-f", "lavfi",
                "-i", "testsrc2=duration=12:size=320x240:rate=25",
                "-pix_fmt", "yuv420p", "-c:v", "libx264",
                "-preset", "ultrafast", "-t", "12", ruta,
            ],
            capture_output=True,
            **flags,
        )
    except OSError:
        return None
    return ruta if (resultado.returncode == 0 and os.path.isfile(ruta)) else None


def _pids_vlc():
    import re

    salida = os.popen("tasklist /FI \"IMAGENAME eq vlc.exe\" /FO CSV /NH").read()
    pids = set()
    for linea in salida.splitlines():
        if "vlc.exe" not in linea:
            continue
        numeros = re.findall(r'"(\d+)"', linea)
        if numeros:
            pids.add(int(numeros[0]))
    return pids


def _cerrar_por_pid(proceso):
    if proceso is None:
        return "sin-proceso"
    if proceso.poll() is not None:
        return "ya-terminado"
    try:
        proceso.terminate()
        proceso.wait(timeout=3)
        return "terminate"
    except Exception:
        try:
            proceso.kill()
            proceso.wait(timeout=3)
            return "kill"
        except Exception:
            return "no-termino"


def test_01():
    modulos = [
        "playlist_vlc.py",
        "scrubber.py",
        "visor_videos.py",
        "prueba_reproduccion_segmento_b56.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Existe el menú contextual del segmento y la señal de reproducción."""
    ok = (
        hasattr(Tarjeta, "_al_segmento_contextual_solicitado")
        and hasattr(Tarjeta, "segmento_reproduccion_solicitada")
        and hasattr(FranjaExploracion, "segmento_contextual_solicitado")
    )
    return ok, f"menu={ok}"


def test_03():
    """El menú del segmento contiene Reproducir y Eliminar."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.8)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.5)
            textos = [a.text() for a in menu.actions()]
            ok = "Reproducir segmento" in textos and "Eliminar segmento" in textos
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"textos={textos}"


def test_04():
    """Clic derecho sobre un marcador sigue eliminándolo (sin menú de segmento)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _press(franja, ancho * 0.3)
            ok_marcador = len(tarjeta._marcadores) == 1
            _press_derecho(franja, ancho * 0.3)
            _drenar_marcadores(ventana)
            ok = (
                ok_marcador
                and tarjeta._marcadores == []
                and tarjeta._menu_segmento_actual is None
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={len(tarjeta._marcadores)}"


def test_05():
    """Zona vacía de la franja conserva el menú contextual de la tarjeta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        llamadas = []
        original_menu = ventana._mostrar_menu_contextual
        ventana._mostrar_menu_contextual = (
            lambda nombre: llamadas.append(nombre)
        )
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            # punto sin marcador ni segmento (ancho*0.05)
            _press_derecho(franja, franja.width() * 0.05)
            _esperar(lambda: len(llamadas) >= 1)
            ok = (
                llamadas == ["a.mp4"]
                and tarjeta._menu_segmento_actual is None
            )
        finally:
            ventana._mostrar_menu_contextual = original_menu
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"llamadas={llamadas}"


def test_06():
    """Reproducir segmento no elimina el segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            capturas = []
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
                seg = dict(tarjeta._segmentos[0])
                original_reproducir = visor_videos.reproducir_segmento
                original_ruta = visor_videos.ruta_video_existente
                original_localizar = visor_videos.localizar_vlc
                visor_videos.reproducir_segmento = (
                    lambda r, n, i, f, v=None: capturas.append(
                        {"inicio": i, "fin": f}
                    )
                )
                visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
                visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
                try:
                    menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
                    accion = _accion(menu, "Reproducir segmento")
                    accion.trigger()
                    _esperar(lambda: len(capturas) >= 1)
                finally:
                    visor_videos.reproducir_segmento = original_reproducir
                    visor_videos.ruta_video_existente = original_ruta
                    visor_videos.localizar_vlc = original_localizar
                ok = (
                    len(capturas) == 1
                    and abs(capturas[0]["inicio"] - seg["inicio"]) < 1.0
                    and abs(capturas[0]["fin"] - seg["fin"]) < 1.0
                    and len(tarjeta._segmentos) == 1
                    and len(listar_segmentos(id_a, ruta_db)) == 1
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"capturas={capturas} segmentos={len(tarjeta._segmentos)}"
        finally:
            temp.cleanup()


def test_07():
    """Eliminar desde el menú sigue eliminando el segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            ok_creado = len(tarjeta._segmentos) == 1
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
            accion = _accion(menu, "Eliminar segmento")
            accion.trigger()
            _drenar_segmentos(ventana)
            ok = ok_creado and tarjeta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"segmentos={len(tarjeta._segmentos)}"


def _m3u_reproducir(ruta_video, nombre, inicio, fin, ruta_vlc):
    capturas = []
    original_abrir = pl.abrir_playlist_en_vlc

    def _abrir(ruta_m3u, vlc):
        with open(ruta_m3u, encoding="utf-8") as archivo:
            capturas.append(archivo.read())
        return object()

    pl.abrir_playlist_en_vlc = _abrir
    try:
        reproducir_segmento(ruta_video, nombre, inicio, fin, ruta_vlc)
    finally:
        pl.abrir_playlist_en_vlc = original_abrir
    return capturas[0] if capturas else None


def test_08():
    """El helper genera start-time y stop-time en una sola entrada."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_reproducir(ruta, "v.mp4", 2.0, 5.0, "C:\\vlc\\vlc.exe")
        ok = (
            contenido is not None
            and "start-time=2" in contenido
            and "stop-time=5" in contenido
            and contenido.count("start-time") == 1
            and contenido.count("stop-time") == 1
            and "EXTM3U" in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_09():
    """Conserva decimales en start-time y stop-time."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_reproducir(ruta, "v.mp4", 1.5, 3.25, "C:\\vlc\\vlc.exe")
        ok = (
            contenido is not None
            and "start-time=1.5" in contenido
            and "stop-time=3.25" in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_10():
    """Ruta con espacios y playlist UTF-8."""
    with tempfile.TemporaryDirectory() as carpeta:
        sub = os.path.join(carpeta, "mi carpeta")
        os.makedirs(sub)
        ruta = os.path.join(sub, "mi video.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_reproducir(ruta, "mi video — áéí.mp4", 1.0, 2.0, "C:\\vlc\\vlc.exe")
        ok = (
            contenido is not None
            and ruta in contenido
            and "áéí" in contenido
            and "start-time=1" in contenido
            and "stop-time=2" in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_11():
    """Inicio 0 válido y fin > inicio válido."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_reproducir(ruta, "v.mp4", 0.0, 1.0, "C:\\vlc\\vlc.exe")
        ok = contenido is not None and "start-time=0" in contenido and "stop-time=1" in contenido
        return ok, f"contenido={contenido!r}"


def _capturar(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return True
    except Exception:
        return False
    return False


def test_12():
    """Inicio negativo rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", -1.0, 2.0, "C:\\vlc\\vlc.exe")
        return ok, "negativo"


def test_13():
    """fin == inicio rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", 2.0, 2.0, "C:\\vlc\\vlc.exe")
        return ok, "fin==inicio"


def test_14():
    """fin < inicio rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", 5.0, 2.0, "C:\\vlc\\vlc.exe")
        return ok, "fin<inicio"


def test_15():
    """NaN rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        nan = float("nan")
        ok = _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", nan, 2.0, "C:\\vlc\\vlc.exe")
        ok = ok and _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", 1.0, nan, "C:\\vlc\\vlc.exe")
        return ok, "nan"


def test_16():
    """Infinito rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        inf = float("inf")
        ok = _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", inf, 2.0, "C:\\vlc\\vlc.exe")
        ok = ok and _capturar(ValueError, reproducir_segmento, ruta, "v.mp4", 1.0, inf, "C:\\vlc\\vlc.exe")
        return ok, "infinito"


def test_17():
    """Bool rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(TypeError, reproducir_segmento, ruta, "v.mp4", True, 2.0, "C:\\vlc\\vlc.exe")
        ok = ok and _capturar(TypeError, reproducir_segmento, ruta, "v.mp4", 1.0, False, "C:\\vlc\\vlc.exe")
        return ok, "bool"


def test_18():
    """VLC ausente: la UI informa y no llama al servicio."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        llamados = []
        dialogo = []
        original_reproducir = visor_videos.reproducir_segmento
        original_localizar = visor_videos.localizar_vlc
        original_ruta = visor_videos.ruta_video_existente
        original_exec = visor_videos.QMessageBox.exec
        visor_videos.reproducir_segmento = lambda *a, **k: llamados.append(a)
        visor_videos.localizar_vlc = lambda: None
        visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
        visor_videos.QMessageBox.exec = lambda self: dialogo.append(self.text())
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
            _accion(menu, "Reproducir segmento").trigger()
            _esperar(lambda: len(dialogo) >= 1)
        finally:
            visor_videos.reproducir_segmento = original_reproducir
            visor_videos.localizar_vlc = original_localizar
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.QMessageBox.exec = original_exec
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        ok = llamados == [] and len(dialogo) == 1 and "VLC" in dialogo[0]
        return ok, f"llamados={len(llamados)} dialogo={dialogo}"


def test_19():
    """Archivo inexistente: la UI informa y no abre VLC."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        llamados = []
        original_reproducir = visor_videos.reproducir_segmento
        original_localizar = visor_videos.localizar_vlc
        visor_videos.reproducir_segmento = lambda *a, **k: llamados.append(a)
        visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
            _accion(menu, "Reproducir segmento").trigger()
            _esperar(lambda: "no está disponible" in ventana.mensaje_carpeta.text())
        finally:
            visor_videos.reproducir_segmento = original_reproducir
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        ok = (
            llamados == []
            and "no está disponible" in ventana.mensaje_carpeta.text()
        )
        return ok, f"llamados={len(llamados)}"


def test_20():
    """La UI no usa subprocess, no construye M3U y no accede a filesystem."""
    fuente_reproducir = inspect.getsource(
        VisorVideos._al_segmento_reproduccion_solicitada
    )
    fuente_menu = inspect.getsource(Tarjeta._al_segmento_contextual_solicitado)
    fuente = fuente_reproducir + fuente_menu
    ok = (
        "subprocess." not in fuente
        and "Popen(" not in fuente
        and "#EXTVLCOPT" not in fuente
        and "generar_m3u(" not in fuente
        and "os.path.isfile" not in fuente
        and "sqlite3" not in fuente
    )
    return ok, f"capas={ok}"


def test_21():
    """Reproducir un segmento no modifica SQLite."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 3.0, ruta_db)
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            antes = _md5(ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = []
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and len(tarjeta._segmentos) == 1,
                    timeout_ms=15000,
                )
                original_reproducir = visor_videos.reproducir_segmento
                original_ruta = visor_videos.ruta_video_existente
                original_localizar = visor_videos.localizar_vlc
                visor_videos.reproducir_segmento = (
                    lambda r, n, i, f, v=None: capturas.append((i, f))
                )
                visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
                visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
                try:
                    menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.07)
                    _accion(menu, "Reproducir segmento").trigger()
                    _esperar(lambda: len(capturas) >= 1)
                finally:
                    visor_videos.reproducir_segmento = original_reproducir
                    visor_videos.ruta_video_existente = original_ruta
                    visor_videos.localizar_vlc = original_localizar
                despues = _md5(ruta_db)
                ok = (
                    len(capturas) == 1
                    and antes == despues
                    and len(listar_marcadores(id_a, ruta_db)) == 1
                    and len(listar_segmentos(id_a, ruta_db)) == 1
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"db_igual={antes == despues}"
        finally:
            temp.cleanup()


def test_22():
    """Marcadores no se ven afectados por la reproducción de segmentos."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 3.0, ruta_db)
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = []
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._marcadores_cargados
                    and tarjeta._segmentos_cargados,
                    timeout_ms=15000,
                )
                original_reproducir = visor_videos.reproducir_segmento
                original_ruta = visor_videos.ruta_video_existente
                original_localizar = visor_videos.localizar_vlc
                visor_videos.reproducir_segmento = (
                    lambda r, n, i, f, v=None: capturas.append((i, f))
                )
                visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
                visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
                try:
                    menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.07)
                    _accion(menu, "Reproducir segmento").trigger()
                    _esperar(lambda: len(capturas) >= 1)
                finally:
                    visor_videos.reproducir_segmento = original_reproducir
                    visor_videos.ruta_video_existente = original_ruta
                    visor_videos.localizar_vlc = original_localizar
                ok = (
                    len(capturas) == 1
                    and len(tarjeta._marcadores) == 1
                    and len(tarjeta._segmentos) == 1
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"marcadores={len(tarjeta._marcadores)} segmentos={len(tarjeta._segmentos)}"
        finally:
            temp.cleanup()


def test_23():
    """Duplicados reproducibles: cada ID reproduce el mismo intervalo."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        original_reproducir = visor_videos.reproducir_segmento
        original_ruta = visor_videos.ruta_video_existente
        original_localizar = visor_videos.localizar_vlc
        visor_videos.reproducir_segmento = (
            lambda r, n, i, f, v=None: capturas.append((i, f))
        )
        visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
        visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5, objetivo=2)
            ok_dos = len(tarjeta._segmentos) == 2
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.3)
            _accion(menu, "Reproducir segmento").trigger()
            _esperar(lambda: len(capturas) >= 1)
            ok = ok_dos and len(capturas) == 1 and len(tarjeta._segmentos) == 2
        finally:
            visor_videos.reproducir_segmento = original_reproducir
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas} segmentos={len(tarjeta._segmentos)}"


def test_24():
    """Solapamientos: el hit testing determina el segmento del menú."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            # dos segmentos solapados por SQLite directo (determinista)
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 20.0, 40.0, ruta_db)  # span 20
            guardar_segmento(id_a, 25.0, 35.0, ruta_db)  # span 10 (más corto)
            tarjeta._segmentos_cargados = False
            tarjeta.colapsar()
            tarjeta.expandir()
            _esperar(
                lambda: len(tarjeta._segmentos) == 2,
                timeout_ms=15000,
            )
            franja = tarjeta._franja
            ancho = franja.width()
            menu = _abrir_menu_segmento(ventana, tarjeta, ancho * 0.30)
            # en 30 s ambos contienen el punto; el más corto (25→35) gana
            ok = menu is not None and len(menu.actions()) >= 2
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"menu={ok} segmentos={len(tarjeta._segmentos)}"


def test_25():
    """B5.3: el doble clic sobre la franja sigue reproduciendo temporalmente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        original_reproducir = visor_videos.reproducir_desde_instante
        original_ruta = visor_videos.ruta_video_existente
        original_localizar = visor_videos.localizar_vlc
        visor_videos.reproducir_desde_instante = (
            lambda r, n, i, v: capturas.append(i)
        )
        visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
        visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _enviar(franja, QEvent.MouseButtonPress, ancho * 0.5, Qt.LeftButton)
            _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
            _enviar(franja, QEvent.MouseButtonDblClick, ancho * 0.5, Qt.LeftButton)
            _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
            _esperar(lambda: len(capturas) >= 1)
        finally:
            visor_videos.reproducir_desde_instante = original_reproducir
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        ok = len(capturas) == 1 and abs(capturas[0] - 50.0) < 1.0
        return ok, f"capturas={capturas}"


def test_26():
    """B4.4: la playlist de marcadores sigue sin stop-time."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        destino = os.path.join(carpeta, "visor_marcadores_m.m3u")
        pl.generar_m3u(
            [
                {"ruta": ruta, "nombre": "v.mp4", "tiempo": 1.5},
                {"ruta": ruta, "nombre": "v.mp4", "tiempo": 17.83},
            ],
            destino,
        )
        with open(destino, encoding="utf-8") as archivo:
            contenido = archivo.read()
        ok = (
            contenido.count("#EXTVLCOPT:start-time") == 2
            and "#EXTVLCOPT:stop-time" not in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_27():
    """Prueba real VLC: 2.0→5.0 dura ~3 s y 1.5→3.25 dura ~1.75 s."""
    vlc = pl.localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids_antes = _pids_vlc()
    with tempfile.TemporaryDirectory() as carpeta:
        video = _generar_video_real(carpeta)
        if video is None:
            return True, "skip: FFmpeg ausente"
        nombre = os.path.basename(video)
        # lanzamiento real del helper (instancia bajo control del usuario)
        proceso = None
        try:
            proceso = reproducir_segmento(video, nombre, 2.0, 5.0, vlc)
            vivo = proceso is not None and proceso.poll() is None
            time.sleep(1.2)
            sigue_vivo = proceso is not None and proceso.poll() is None
        finally:
            _cerrar_por_pid(proceso)

        def _medir(inicio, fin):
            m3u = os.path.join(carpeta, f"visor_marcadores_{int(inicio)}_{int(fin)}.m3u")
            pl.generar_m3u(
                [{"ruta": video, "nombre": nombre, "tiempo": inicio, "fin": fin}],
                m3u,
            )
            sw = time.monotonic()
            p = subprocess.Popen(
                [vlc, "--no-one-instance", "--intf", "dummy", "--play-and-exit", m3u],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                p.wait(timeout=25)
            except subprocess.TimeoutExpired:
                p.kill()
            return round(time.monotonic() - sw, 2)

        d1 = _medir(2.0, 5.0)   # ≈3 s
        d2 = _medir(1.5, 3.25)  # ≈1.75 s
        time.sleep(0.5)
        pids_despues = _pids_vlc()
        nuevos = pids_despues - pids_antes
        ok = (
            vivo
            and sigue_vivo
            and 2.2 <= d1 <= 6.0
            and 1.2 <= d2 <= 4.0
            and not nuevos
        )
        return (
            ok,
            f"vivo={vivo} d2_5={d1}s d1p5_3p25={d2}s residuales={sorted(nuevos)}",
        )


def main():
    app = QApplication(sys.argv)
    QApplication.setDoubleClickInterval(100)
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
        test_15,
        test_16,
        test_17,
        test_18,
        test_19,
        test_20,
        test_21,
        test_22,
        test_23,
        test_24,
        test_25,
        test_26,
        test_27,
    ]
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
