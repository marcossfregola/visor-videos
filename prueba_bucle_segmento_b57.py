"""Pruebas del Bloque C-2 — Bucle de un segmento A→B en VLC (B5.7).

Cubre: menú con la tercera acción "Reproducir segmento en bucle", helper
`reproducir_segmento_en_bucle` (start-time + stop-time + --loop), ausencia
de --loop en la reproducción normal, validaciones idénticas a B5.6, VLC
ausente, archivo inexistente, separación de capas, bucle sin tocar datos,
B5.6/B5.3/B4.4 intactos, prueba real con ≥3 ciclos (inspección por RC en el
harness) e instancia VLC preexistente.
"""

import contextlib
import hashlib
import inspect
import os
import py_compile
import re
import socket
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication

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
from playlist_vlc import (
    localizar_vlc,
    reproducir_segmento,
    reproducir_segmento_en_bucle,
)
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
    _enviar(widget, QEvent.MouseButtonRelease, x, Qt.LeftButton)


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


def _crear_segmento_ui(ventana, tarjeta, x1, x2):
    tarjeta._boton_segmento.setChecked(True)
    _press(tarjeta._franja, x1)
    ok_a = _esperar(lambda: tarjeta._extremo_segmento is not None)
    _press(tarjeta._franja, x2)
    ok_b = _esperar(lambda: len(tarjeta._segmentos) >= 1)
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
        version = subprocess.run([ffmpeg, "-version"], capture_output=True, **flags)
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


class _Rc:
    def __init__(self, puerto):
        self._s = socket.create_connection(("127.0.0.1", puerto), timeout=2)
        time.sleep(0.3)
        try:
            self._s.settimeout(0.2)
            while True:
                try:
                    self._s.recv(4096)
                except socket.timeout:
                    break
        except OSError:
            pass

    def get_time(self):
        self._s.settimeout(0.6)
        try:
            self._s.sendall(b"get_time\n")
        except OSError:
            return None
        datos = b""
        fin = time.monotonic() + 0.6
        while time.monotonic() < fin:
            try:
                chunk = self._s.recv(4096)
            except (socket.timeout, OSError):
                break
            if not chunk:
                break
            datos += chunk
        m = re.findall(r"(\d+(?:\.\d+)?)", datos.decode("utf-8", "ignore"))
        for valor in m:
            f = float(valor)
            if 0 <= f < 100000:
                return f
        return None

    def cerrar(self):
        try:
            self._s.sendall(b"quit\n")
        except Exception:
            pass
        self._s.close()


def test_01():
    modulos = [
        "playlist_vlc.py",
        "visor_videos.py",
        "prueba_bucle_segmento_b57.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """El menú contiene la acción de bucle en el orden esperado."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.8)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.5)
            textos = [a.text() for a in menu.actions()]
            ok = (
                textos
                == [
                    "Reproducir segmento",
                    "Reproducir segmento en bucle",
                    "Eliminar segmento",
                ]
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"textos={textos}"


def test_03():
    """Reproducción normal y Eliminar siguen existiendo en el menú."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.8)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.5)
            ok = (
                _accion(menu, "Reproducir segmento") is not None
                and _accion(menu, "Eliminar segmento") is not None
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"normal={_accion(menu, 'Reproducir segmento') is not None}"


def test_04():
    """La acción de bucle llama al helper correcto en la UI."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        original_bucle = visor_videos.reproducir_segmento_en_bucle
        original_ruta = visor_videos.ruta_video_existente
        original_localizar = visor_videos.localizar_vlc
        visor_videos.reproducir_segmento_en_bucle = (
            lambda r, n, i, f, v=None: capturas.append((i, f))
        )
        visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
        visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            seg = dict(tarjeta._segmentos[0])
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
            _accion(menu, "Reproducir segmento en bucle").trigger()
            _esperar(lambda: len(capturas) >= 1)
            ok = (
                len(capturas) == 1
                and abs(capturas[0][0] - seg["inicio"]) < 1.0
                and abs(capturas[0][1] - seg["fin"]) < 1.0
            )
        finally:
            visor_videos.reproducir_segmento_en_bucle = original_bucle
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas}"


def _capturar_abrir(contenidos, argv):
    original = pl.abrir_playlist_en_vlc

    def _abrir(ruta_m3u, ruta_vlc, bucle=False):
        with open(ruta_m3u, encoding="utf-8") as archivo:
            contenidos.append(archivo.read())
        argv.append(
            [ruta_vlc] + (["--loop"] if bucle else []) + [ruta_m3u]
        )
        return object()

    pl.abrir_playlist_en_vlc = _abrir
    return original


def test_05():
    """El helper de bucle genera start-time, stop-time y agrega --loop."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenidos = []
        argv = []
        original = _capturar_abrir(contenidos, argv)
        try:
            reproducir_segmento_en_bucle(ruta, "v.mp4", 2.0, 5.0, "C:\\vlc\\vlc.exe")
        finally:
            pl.abrir_playlist_en_vlc = original
        contenido = contenidos[0] if contenidos else ""
        ok = (
            "start-time=2" in contenido
            and "stop-time=5" in contenido
            and "--loop" in argv[0]
            and contenido.count("start-time") == 1
            and contenido.count("stop-time") == 1
        )
        return ok, f"argv={argv[0] if argv else None}"


def test_06():
    """La reproducción normal NO usa --loop."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenidos = []
        argv = []
        original = _capturar_abrir(contenidos, argv)
        try:
            reproducir_segmento(ruta, "v.mp4", 2.0, 5.0, "C:\\vlc\\vlc.exe")
        finally:
            pl.abrir_playlist_en_vlc = original
        ok = (
            "--loop" not in argv[0]
            and "start-time=2" in contenidos[0]
            and "stop-time=5" in contenidos[0]
        )
        return ok, f"argv={argv[0] if argv else None}"


def test_07():
    """Playlist de una entrada y decimales preservados."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenidos = []
        argv = []
        original = _capturar_abrir(contenidos, argv)
        try:
            reproducir_segmento_en_bucle(ruta, "v.mp4", 1.5, 3.25, "C:\\vlc\\vlc.exe")
        finally:
            pl.abrir_playlist_en_vlc = original
        contenido = contenidos[0] if contenidos else ""
        ok = (
            "start-time=1.5" in contenido
            and "stop-time=3.25" in contenido
            and contenido.count("#EXTVLCOPT") == 2
        )
        return ok, f"contenido={contenido!r}"


def test_08():
    """Ruta con espacios y UTF-8."""
    with tempfile.TemporaryDirectory() as carpeta:
        sub = os.path.join(carpeta, "mi carpeta")
        os.makedirs(sub)
        ruta = os.path.join(sub, "mi video.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenidos = []
        argv = []
        original = _capturar_abrir(contenidos, argv)
        try:
            reproducir_segmento_en_bucle(ruta, "mi video — áéí.mp4", 1.0, 2.0, "C:\\vlc\\vlc.exe")
        finally:
            pl.abrir_playlist_en_vlc = original
        contenido = contenidos[0] if contenidos else ""
        ok = ruta in contenido and "áéí" in contenido
        return ok, f"contenido={contenido!r}"


def test_09():
    """Inicio 0 válido."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenidos = []
        argv = []
        original = _capturar_abrir(contenidos, argv)
        try:
            reproducir_segmento_en_bucle(ruta, "v.mp4", 0.0, 1.0, "C:\\vlc\\vlc.exe")
        finally:
            pl.abrir_playlist_en_vlc = original
        ok = "start-time=0" in contenidos[0] and "stop-time=1" in contenidos[0]
        return ok, f"contenido={contenidos[0]!r}"


def _capturar(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return True
    except Exception:
        return False
    return False


def test_10():
    """fin == inicio rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(
            ValueError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", 2.0, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "fin==inicio"


def test_11():
    """fin < inicio rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(
            ValueError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", 5.0, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "fin<inicio"


def test_12():
    """Negativo rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(
            ValueError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", -1.0, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "negativo"


def test_13():
    """NaN rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        nan = float("nan")
        ok = _capturar(
            ValueError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", nan, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "nan"


def test_14():
    """Infinito rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        inf = float("inf")
        ok = _capturar(
            ValueError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", inf, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "infinito"


def test_15():
    """Bool rechazado."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(
            TypeError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", True, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "bool"


def test_16():
    """Archivo inexistente → FileNotFoundError."""
    ruta = os.path.join(tempfile.gettempdir(), "b57_no_existe.mp4")
    if os.path.isfile(ruta):
        os.remove(ruta)
    try:
        ok = _capturar(
            FileNotFoundError,
            reproducir_segmento_en_bucle, ruta, "v.mp4", 1.0, 2.0, "C:\\vlc\\vlc.exe",
        )
        return ok, "file_not_found"
    finally:
        if os.path.isfile(ruta):
            os.remove(ruta)


def test_17():
    """VLC ausente → RuntimeError (si no se resuelve)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        original = pl.localizar_vlc
        pl.localizar_vlc = lambda: None
        try:
            ok = _capturar(
                RuntimeError,
                reproducir_segmento_en_bucle, ruta, "v.mp4", 1.0, 2.0, None,
            )
        finally:
            pl.localizar_vlc = original
        return ok, "vlc_ausente"


def test_18():
    """UI sin subprocess ni M3U en los handlers de bucle."""
    fuente = inspect.getsource(
        VisorVideos._reproducir_segmento
    ) + inspect.getsource(Tarjeta._al_segmento_contextual_solicitado)
    ok = (
        "subprocess." not in fuente
        and "Popen(" not in fuente
        and "#EXTVLCOPT" not in fuente
        and "generar_m3u(" not in fuente
        and "os.path.isfile" not in fuente
        and "sqlite3" not in fuente
    )
    return ok, f"capas={ok}"


def test_19():
    """El bucle no modifica SQLite ni los datos de segmentos/marcadores."""
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
                original_bucle = visor_videos.reproducir_segmento_en_bucle
                original_ruta = visor_videos.ruta_video_existente
                original_localizar = visor_videos.localizar_vlc
                visor_videos.reproducir_segmento_en_bucle = (
                    lambda r, n, i, f, v=None: capturas.append((i, f))
                )
                visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
                visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
                try:
                    menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.07)
                    _accion(menu, "Reproducir segmento en bucle").trigger()
                    _esperar(lambda: len(capturas) >= 1)
                finally:
                    visor_videos.reproducir_segmento_en_bucle = original_bucle
                    visor_videos.ruta_video_existente = original_ruta
                    visor_videos.localizar_vlc = original_localizar
                despues = _md5(ruta_db)
                ok = (
                    len(capturas) == 1
                    and antes == despues
                    and len(listar_marcadores(id_a, ruta_db)) == 1
                    and len(listar_segmentos(id_a, ruta_db)) == 1
                    and len(tarjeta._segmentos) == 1
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"db_igual={antes == despues}"
        finally:
            temp.cleanup()


def test_20():
    """B5.6 normal intacto: Reproducir segmento llama a reproducir_segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        original_normal = visor_videos.reproducir_segmento
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
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            menu = _abrir_menu_segmento(ventana, tarjeta, tarjeta._franja.width() * 0.4)
            _accion(menu, "Reproducir segmento").trigger()
            _esperar(lambda: len(capturas) >= 1)
            ok = len(capturas) == 1
        finally:
            visor_videos.reproducir_segmento = original_normal
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas}"


def test_21():
    """B5.3 intacto: doble clic sobre la franja sigue reproduciendo temporalmente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        original = visor_videos.reproducir_desde_instante
        original_ruta = visor_videos.ruta_video_existente
        original_localizar = visor_videos.localizar_vlc
        visor_videos.reproducir_desde_instante = lambda r, n, i, v: capturas.append(i)
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
            ok = len(capturas) == 1 and abs(capturas[0] - 50.0) < 1.0
        finally:
            visor_videos.reproducir_desde_instante = original
            visor_videos.ruta_video_existente = original_ruta
            visor_videos.localizar_vlc = original_localizar
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas}"


def test_22():
    """B4.4 intacto: playlist de marcadores sin stop-time y sin --loop."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        destino = os.path.join(carpeta, "visor_marcadores_m.m3u")
        pl.generar_m3u(
            [{"ruta": ruta, "nombre": "v.mp4", "tiempo": 1.5}],
            destino,
        )
        with open(destino, encoding="utf-8") as archivo:
            contenido = archivo.read()
        ok = (
            "start-time=1.5" in contenido
            and "#EXTVLCOPT:stop-time" not in contenido
            and "--loop" not in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_23():
    """Prueba real: loop A→B con ≥3 ciclos (inspección RC del harness)."""
    vlc = localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids0 = _pids_vlc()
    with tempfile.TemporaryDirectory() as carpeta:
        video = _generar_video_real(carpeta)
        if video is None:
            return True, "skip: FFmpeg ausente"
        nombre = os.path.basename(video)
        # lanzamiento real del helper de bucle (ventana del usuario)
        proceso = None
        try:
            proceso = reproducir_segmento_en_bucle(video, nombre, 2.0, 5.0, vlc)
            vivo = proceso is not None and proceso.poll() is None
            time.sleep(1.2)
            sigue = proceso is not None and proceso.poll() is None
        finally:
            _cerrar_por_pid(proceso)

        # inspección del loop (solo harness): misma m3u + --loop + RC
        m3u = os.path.join(carpeta, "visor_marcadores_loop.m3u")
        pl.generar_m3u(
            [{"ruta": video, "nombre": nombre, "tiempo": 2.0, "fin": 5.0}],
            m3u,
        )
        puerto = 4224
        p_rc = subprocess.Popen(
            [
                vlc, "--no-one-instance", "--intf", "dummy",
                "--extraintf=rc", f"--rc-host=127.0.0.1:{puerto}",
                "--loop", m3u,
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **{"creationflags": subprocess.CREATE_NO_WINDOW},
        )
        rc = None
        muestras = []
        try:
            time.sleep(2.0)
            rc = _Rc(puerto)
            for _ in range(24):
                muestras.append(rc.get_time())
                time.sleep(0.5)
        finally:
            if rc is not None:
                rc.cerrar()
            if p_rc.poll() is None:
                try:
                    p_rc.terminate(); p_rc.wait(timeout=3)
                except Exception:
                    try:
                        p_rc.kill()
                    except Exception:
                        pass
        # contar ciclos: saltos hacia abajo (de ~5 a ~2) = reinicios del loop
        ciclos = 0
        for i in range(1, len(muestras)):
            a, b = muestras[i - 1], muestras[i]
            if a is not None and b is not None and (a - b) > 2.0:
                ciclos += 1
        time.sleep(0.8)
        residuales = sorted(_pids_vlc() - pids0)
        ok = (
            vivo
            and sigue
            and ciclos >= 3
            and not residuales
        )
        return (
            ok,
            f"vivo={vivo} ciclos={ciclos} muestras={muestras} residuales={residuales}",
        )


def test_24():
    """Instancia VLC preexistente: el loop abre una nueva y no toca la previa."""
    vlc = localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids0 = _pids_vlc()
    puerto = 4225
    pre = subprocess.Popen(
        [vlc, "--extraintf=rc", f"--rc-host=127.0.0.1:{puerto}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **{"creationflags": subprocess.CREATE_NO_WINDOW},
    )
    pid_pre = pre.pid
    rc = None
    popen = None
    try:
        time.sleep(2.0)
        rc = _Rc(puerto)
        with tempfile.TemporaryDirectory() as carpeta:
            video = _generar_video_real(carpeta)
            if video is None:
                return True, "skip: FFmpeg ausente"
            popen = reproducir_segmento_en_bucle(
                video, os.path.basename(video), 2.0, 5.0, vlc
            )
            pid_nuevo = popen.pid
            time.sleep(1.5)
            pids = _pids_vlc()
            t_pre = rc.get_time()
            ok = (
                pid_pre in pids
                and pid_nuevo in pids
                and len(pids) >= 2
                and t_pre in (0.0, None)
            )
    finally:
        if rc is not None:
            rc.cerrar()
        if popen is not None and popen.poll() is None:
            _cerrar_por_pid(popen)
        if pre.poll() is None:
            _cerrar_por_pid(pre)
        time.sleep(0.8)
        residuales = sorted(_pids_vlc() - pids0)
    return (
        ok and not residuales,
        f"pre_viva={pid_pre in _pids_vlc()} nueva={pid_nuevo} t_pre={t_pre} residuales={residuales}",
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
