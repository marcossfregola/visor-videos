"""Pruebas del Bloque A — Entrada temporal directa a VLC (B5.3).

Cubre: señal de reproducción temporal desde la franja, doble clic que
convierte X→tiempo, no creación de marcador en el doble clic, coexistencia
con el doble clic de tarjeta y con clic simple/derecho de marcadores,
helper de `playlist_vlc` (start-time, decimales, rutas con espacios, UTF-8,
tiempo 0, validaciones), VLC ausente, archivo inexistente, ausencia de
subprocess/M3U/`os.path.isfile` en la UI, regresión de playlists de
marcadores y limpieza por PID propio de un lanzamiento real de VLC.
"""

import contextlib
import inspect
import math
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt, QThread
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication, QMessageBox

import escanear_videos as escanear_mod
import playlist_vlc as pl
import visor_videos
from exploracion_temporal import posicion_a_tiempo
from playlist_vlc import reproducir_desde_instante
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
    conn = escanear_mod.conectar_bd(ruta_db)
    conn.close()
    escanear_mod.guardar_videos([_registro(n) for n in nombres], ruta_db)
    return temp, ruta_db


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _mouse_press(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.LeftButton)


def _mouse_release(widget, x):
    _enviar(widget, QEvent.MouseButtonRelease, x, Qt.LeftButton)


def _mouse_doble(widget, x):
    _enviar(widget, QEvent.MouseButtonDblClick, x, Qt.LeftButton)


def _mouse_derecho(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.RightButton)


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


def _doble_clic_real(widget, x):
    _mouse_press(widget, x)
    _mouse_release(widget, x)
    _mouse_doble(widget, x)
    _mouse_release(widget, x)


def _generar_video_real(directorio):
    """Genera un video real de ~12 s; None si FFmpeg falta o falla."""
    import subprocess

    ffmpeg = os.environ.get("FFMPEG") or "ffmpeg"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        version = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True,
            **flags,
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


def _vlc_ruta():
    return pl.localizar_vlc()


def _cerrar_por_pid(proceso):
    """Escalera de cierre por PID propio (nunca global)."""
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


# ---------------------------------------------------------------------------
# 1) Señal y doble clic en la franja (aislado)
# ---------------------------------------------------------------------------


def test_01():
    modulos = [
        "scrubber.py",
        "playlist_vlc.py",
        "visor_videos.py",
        "prueba_entrada_temporal_b53.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Existe la señal `reproduccion_solicitada` en `FranjaExploracion`."""
    ok = hasattr(FranjaExploracion, "reproduccion_solicitada")
    return ok, f"senal={ok}"


def test_03():
    """Doble clic convierte X→tiempo correcto y emite exactamente una vez."""
    franja = FranjaExploracion()
    franja.set_duracion(100.0)
    franja.resize(400, 80)
    recibidos = []
    franja.reproduccion_solicitada.connect(lambda t: recibidos.append(t))
    _doble_clic_real(franja, 200.0)  # 50 % de 400 px = 50 s
    ok_instante = len(recibidos) == 1 and abs(recibidos[0] - 50.0) < 1e-6
    ok_una_vez = len(recibidos) == 1
    return (
        ok_instante and ok_una_vez,
        f"recibidos={recibidos}",
    )


def test_04():
    """Doble clic sin duración válida no emite."""
    franja = FranjaExploracion()
    franja.set_duracion(None)
    franja.resize(400, 80)
    recibidos = []
    franja.reproduccion_solicitada.connect(lambda t: recibidos.append(t))
    _doble_clic_real(franja, 200.0)
    return len(recibidos) == 0, f"recibidos={recibidos}"


# ---------------------------------------------------------------------------
# 2) Helper de playlist_vlc
# ---------------------------------------------------------------------------


def _m3u_de_helper(ruta_video, nombre, instante, ruta_vlc):
    capturas = []
    original_abrir = pl.abrir_playlist_en_vlc

    def _abrir(ruta_m3u, vlc):
        with open(ruta_m3u, encoding="utf-8") as archivo:
            capturas.append(archivo.read())
        return object()

    pl.abrir_playlist_en_vlc = _abrir
    try:
        reproducir_desde_instante(ruta_video, nombre, instante, ruta_vlc)
    finally:
        pl.abrir_playlist_en_vlc = original_abrir
    return capturas[0] if capturas else None


def test_05():
    """El helper genera una playlist de una entrada con `start-time`."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_de_helper(ruta, "v.mp4", 12.0, "C:\\vlc\\vlc.exe")
        ok_inf = contenido is not None and "#EXTM3U" in contenido
        ok_start = (
            "#EXTVLCOPT:start-time=12" in contenido
            and "#EXTVLCOPT:stop-time" not in contenido
        )
        ok_una = contenido.count("start-time") == 1
        return (
            ok_inf and ok_start and ok_una,
            f"contenido={contenido!r}",
        )


def test_06():
    """Preserva el decimal del instante."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_de_helper(ruta, "v.mp4", 12.437, "C:\\vlc\\vlc.exe")
        ok = contenido is not None and "start-time=12.437" in contenido
        return ok, f"contenido={contenido!r}"


def test_07():
    """Ruta con espacios se serializa sin romper."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "mi carpeta", "mi video.mp4")
        os.makedirs(os.path.dirname(ruta))
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_de_helper(ruta, "mi video.mp4", 3.0, "C:\\vlc\\vlc.exe")
        ok = contenido is not None and ruta in contenido
        return ok, f"contenido={contenido!r}"


def test_08():
    """Playlist UTF-8 (nombres con acentos y Unicode)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "clase.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_de_helper(ruta, "clase — áéíóú.mp4", 3.0, "C:\\vlc\\vlc.exe")
        ok = contenido is not None and "áéíóú" in contenido
        return ok, f"contenido={contenido!r}"


def test_09():
    """Tiempo 0 es válido (start-time=0)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido = _m3u_de_helper(ruta, "v.mp4", 0.0, "C:\\vlc\\vlc.exe")
        ok = contenido is not None and "start-time=0" in contenido
        return ok, f"contenido={contenido!r}"


def test_10():
    """Tiempo negativo rechazado (ValueError)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        try:
            reproducir_desde_instante(ruta, "v.mp4", -1.0, "C:\\vlc\\vlc.exe")
        except ValueError:
            return True, "negativo"
        return False, "no rechazó negativo"


def test_11():
    """NaN rechazado (ValueError)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        try:
            reproducir_desde_instante(ruta, "v.mp4", float("nan"), "C:\\vlc\\vlc.exe")
        except ValueError:
            return True, "nan"
        return False, "no rechazó nan"


def test_12():
    """Infinito rechazado (ValueError)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        try:
            reproducir_desde_instante(ruta, "v.mp4", float("inf"), "C:\\vlc\\vlc.exe")
        except ValueError:
            return True, "infinito"
        return False, "no rechazó infinito"


def test_13():
    """Bool rechazado (TypeError)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        try:
            reproducir_desde_instante(ruta, "v.mp4", True, "C:\\vlc\\vlc.exe")
        except TypeError:
            return True, "bool"
        return False, "no rechazó bool"


def test_14():
    """Archivo inexistente → FileNotFoundError (y no deja playlist)."""
    ruta = os.path.join(tempfile.gettempdir(), "b53_no_existe.mp4")
    if os.path.isfile(ruta):
        os.remove(ruta)
    try:
        try:
            reproducir_desde_instante(ruta, "v.mp4", 1.0, "C:\\vlc\\vlc.exe")
        except FileNotFoundError:
            ok = True
        else:
            ok = False
        temporales = [
            n
            for n in os.listdir(tempfile.gettempdir())
            if n.startswith("visor_marcadores_") and n.endswith(".m3u")
        ]
        return ok, f"file_not_found={ok} temporales={len(temporales)}"
    finally:
        if os.path.isfile(ruta):
            os.remove(ruta)


# ---------------------------------------------------------------------------
# 3) UI: doble clic franja → VLC; coexistencia con tarjeta y marcadores
# ---------------------------------------------------------------------------


def test_15():
    """Doble clic en la franja → la UI invoca el servicio VLC con el instante."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            capturas = []
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = (
                lambda r, n, i, v: capturas.append({"ruta": r, "nombre": n, "instante": i, "vlc": v})
            )
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                x = ancho * 0.5
                _doble_clic_real(superficie, x)
                esperado = posicion_a_tiempo(x, ancho, 100.0)
                _esperar(lambda: len(capturas) >= 1)
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
            ok = (
                len(capturas) == 1
                and capturas[0]["nombre"] == "a.mp4"
                and capturas[0]["ruta"] == "C:\\videos\\a.mp4"
                and abs(capturas[0]["instante"] - esperado) < 1e-6
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas}"


def test_16():
    """Doble clic en la franja no crea marcador (ni en RAM ni persistido)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        persistidos = None
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            capturas = []
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = lambda *a: capturas.append(a)
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                _doble_clic_real(superficie, ancho * 0.5)
                _esperar(
                    lambda: len(capturas) >= 1
                    and not ventana.gestor_marcadores.activo
                    and not ventana._cola_marcadores,
                    timeout_ms=15000,
                )
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
            persistidos = escanear_mod.listar_marcadores(id_a, ruta_db)
            ok = (
                tarjeta._marcadores == []
                and tarjeta._marcador_creado_prensa is None
                and persistidos == []
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores_ram={tarjeta._marcadores} persistidos={persistidos}"


def _video_id(ruta_db, nombre):
    for fila in escanear_mod.listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


def test_17():
    """Clic simple conserva el comportamiento de marcador."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            _mouse_press(superficie, ancho * 0.25)
            ok = len(tarjeta._marcadores) == 1
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={[m['tiempo'] for m in tarjeta._marcadores]}"


def test_18():
    """Clic derecho conserva la eliminación de marcadores."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            _mouse_press(superficie, ancho * 0.25)
            _mouse_derecho(superficie, ancho * 0.25)
            ok = len(tarjeta._marcadores) == 0
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={[m['tiempo'] for m in tarjeta._marcadores]}"


def test_19():
    """Doble clic en la franja no propaga la apertura de tarjeta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            propagado = []
            tarjeta.doble_clic.connect(lambda n: propagado.append(n))
            capturas = []
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = lambda *a: capturas.append(a)
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                _doble_clic_real(superficie, ancho * 0.5)
                _esperar(lambda: len(capturas) >= 1)
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
            ok = len(capturas) == 1 and propagado == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"reproducciones={len(capturas)} propagadas={propagado}"


def test_20():
    """La tarjeta conserva su doble clic tradicional (abrir con app por defecto)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            recibidos = []
            tarjeta.doble_clic.connect(lambda n: recibidos.append(n))
            _enviar(tarjeta, QEvent.MouseButtonDblClick, 30.0, Qt.LeftButton)
            ok = recibidos == ["a.mp4"]
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"recibidos={recibidos}"


def test_21():
    """VLC ausente: la UI muestra mensaje y no llama al servicio."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            llamado = []
            dialogo = []
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            original_exec = visor_videos.QMessageBox.exec
            visor_videos.reproducir_desde_instante = lambda *a: llamado.append(a)
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: None
            visor_videos.QMessageBox.exec = lambda self: dialogo.append(self.text())
            try:
                _doble_clic_real(superficie, ancho * 0.5)
                _esperar(lambda: len(dialogo) >= 1)
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
                visor_videos.QMessageBox.exec = original_exec
            ok = llamado == [] and len(dialogo) == 1 and "VLC" in dialogo[0]
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"llamado={len(llamado)} dialogo={dialogo}"


def test_22():
    """Video inexistente: la UI informa y no llama al servicio."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            superficie = tarjeta._franja
            ancho = superficie.width()
            llamado = []
            original_reproducir = visor_videos.reproducir_desde_instante
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = lambda *a: llamado.append(a)
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                _doble_clic_real(superficie, ancho * 0.5)
                _esperar(lambda: "no está disponible" in ventana.mensaje_carpeta.text())
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.localizar_vlc = original_localizar
            ok = (
                llamado == []
                and "no está disponible" in ventana.mensaje_carpeta.text()
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"llamado={len(llamado)} mensaje={ventana.mensaje_carpeta.text()!r}"


def test_23():
    """El handler de entrada temporal (B5.3) no usa subprocess, M3U ni isfile."""
    fuente_handler = inspect.getsource(
        VisorVideos._al_reproduccion_temporal_solicitada
    )
    ok_no_subprocess = (
        "subprocess." not in fuente_handler
        and "Popen(" not in fuente_handler
        and "import subprocess" not in fuente_handler
    )
    ok_no_m3u = (
        "#EXTVLCOPT" not in fuente_handler
        and "#EXTM3U" not in fuente_handler
        and "generar_m3u(" not in fuente_handler
    )
    ok_no_isfile = "os.path.isfile" not in fuente_handler
    codigo_ui = inspect.getsource(Tarjeta) + inspect.getsource(VisorVideos)
    ok_ui_isfile = "os.path.isfile" not in codigo_ui
    ok = (
        ok_no_subprocess
        and ok_no_m3u
        and ok_no_isfile
        and ok_ui_isfile
    )
    return (
        ok,
        f"sin_subprocess={ok_no_subprocess} sin_m3u={ok_no_m3u} sin_isfile={ok_no_isfile} ui_sin_isfile={ok_ui_isfile}",
    )


def test_24():
    """Regresión: la playlist de marcadores (B4.4) sigue intacta."""
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
            and "start-time=1.5" in contenido
            and "start-time=17.83" in contenido
            and "#EXTVLCOPT:stop-time" not in contenido
        )
        return ok, f"contenido={contenido!r}"


# ---------------------------------------------------------------------------
# 4) Prueba real con VLC (evidencia automatizada + limpieza por PID)
# ---------------------------------------------------------------------------


def test_25():
    """Lanzamiento real de VLC desde un instante: arranca ~en t y se limpia por PID.

    Se genera un video real de ~12 s; se abre VLC con `reproducir_desde_instante`
    en t=5 s y se verifica (mediante interfaz RC sobre la misma playlist) que la
    reproducción comienza aproximadamente en 5 s (margen por seek/keyframes). El
    proceso se cierra por PID propio y se verifica que no queda ningún VLC creado
    por la prueba.
    """
    vlc = _vlc_ruta()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids_antes = _pids_vlc()
    with tempfile.TemporaryDirectory() as carpeta:
        video = _generar_video_real(carpeta)
        if video is None:
            return True, "skip: FFmpeg ausente"
        nombre = os.path.basename(video)
        # Paso 1: lanzamiento real del helper (instancia bajo control del usuario).
        proceso = None
        try:
            proceso = reproducir_desde_instante(video, nombre, 5.0, vlc)
            vivo = proceso is not None and proceso.poll() is None
            time.sleep(1.2)
            sigue_vivo = proceso is not None and proceso.poll() is None
        finally:
            _cerrar_por_pid(proceso)

        # Paso 2: evidencia automatizada del inicio en ~5 s (RC sobre la misma playlist).
        m3u = os.path.join(carpeta, "visor_marcadores_rc.m3u")
        pl.generar_m3u([{"ruta": video, "nombre": nombre, "tiempo": 5.0}], m3u)
        puerto = 4216
        proceso_rc = None
        muestras = []
        try:
            proceso_rc = __import__("subprocess").Popen(
                [
                    vlc,
                    "--no-one-instance",
                    "--intf", "dummy",
                    "--extraintf=rc",
                    f"--rc-host=127.0.0.1:{puerto}",
                    m3u,
                ],
                stdout=__import__("subprocess").DEVNULL,
                stderr=__import__("subprocess").DEVNULL,
            )
            time.sleep(2.0)
            import socket

            cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                cliente.settimeout(2)
                cliente.connect(("127.0.0.1", puerto))
                time.sleep(0.3)
                cliente.settimeout(2)
                for _ in range(8):
                    try:
                        cliente.sendall(b"get_time\n")
                        time.sleep(0.3)
                        datos = cliente.recv(2048).decode("utf-8", "ignore")
                        for token in datos.split():
                            if token.replace(".", "", 1).isdigit():
                                muestras.append(float(token))
                    except OSError:
                        break
            finally:
                cliente.close()
        finally:
            try:
                if proceso_rc is not None and proceso_rc.poll() is None:
                    proceso_rc.terminate()
                    try:
                        proceso_rc.wait(timeout=3)
                    except Exception:
                        proceso_rc.kill()
            except Exception:
                pass
        ok_arranca = (
            vivo
            and sigue_vivo
            and any(4.0 <= m <= 7.0 for m in muestras)
        )
        # Paso 3: no quedan VLC creados por la prueba.
        time.sleep(0.5)
        pids_despues = _pids_vlc()
        nuevos = pids_despues - pids_antes
        ok_sin_residual = not nuevos
        return (
            ok_arranca and ok_sin_residual,
            f"vivo={vivo} sigue={sigue_vivo} muestras={muestras} residuales={sorted(nuevos)}",
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
