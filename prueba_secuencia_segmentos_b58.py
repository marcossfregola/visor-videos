"""Pruebas del Bloque D — Secuencia automática de segmentos (B5.8).

Cubre: acción "Reproducir segmentos en VLC" (paralela a marcadores),
`TareaListarSegmentosVarios`, datos desde el repositorio (videos no
expandidos incluidos), orden determinista, videos sin segmentos/archivos
faltantes, M3U de una entrada por segmento con start/stop y sin --loop,
duplicados/solapamientos, validación de secuencia, asincronía, solicitudes
rápidas, integridad de datos, B5.6/B5.7/B5.3/B4.4 intactos y pruebas reales
de VLC (secuencia 1→3/5→7/9→11, multi-video, instancia preexistente).
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
import threading
import time

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import playlist_vlc as pl
import tareas_videos as tv
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
from playlist_vlc import localizar_vlc, reproducir_secuencia_segmentos
from visor_videos import Tarjeta, VisorVideos

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


def _seleccionar(ventana, nombres):
    for nombre in nombres:
        ventana._nombres_seleccionados.add(nombre)
        tarjeta = dict(ventana.tarjetas)[nombre]
        tarjeta.marcar_seleccionada(True)


def _md5(ruta):
    with open(ruta, "rb") as archivo:
        return hashlib.md5(archivo.read()).hexdigest()


def _generar_video(directorio, nombre="video_temporal.mp4"):
    ffmpeg = os.environ.get("FFMPEG") or "ffmpeg"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        version = subprocess.run([ffmpeg, "-version"], capture_output=True, **flags)
        if version.returncode != 0:
            return None
    except OSError:
        return None
    ruta = os.path.join(directorio, nombre)
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


def _secuencia_capturada(ventana):
    capturas = []
    original = visor_videos.reproducir_secuencia_segmentos
    original_ruta = visor_videos.ruta_video_existente
    original_localizar = visor_videos.localizar_vlc
    visor_videos.reproducir_secuencia_segmentos = (
        lambda seg, v=None: capturas.append(list(seg))
    )
    visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
    visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
    return capturas, original, original_ruta, original_localizar


def _restaurar(originales, capturas):
    visor_videos.reproducir_secuencia_segmentos = originales[0]
    visor_videos.ruta_video_existente = originales[1]
    visor_videos.localizar_vlc = originales[2]


def _secuencia_obtenida(capturas):
    return capturas[0][-1] if capturas[0] else []


def test_01():
    modulos = [
        "playlist_vlc.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_secuencia_segmentos_b58.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """El menú de tarjeta contiene la acción de segmentos y la de marcadores."""
    fuente = inspect.getsource(VisorVideos._mostrar_menu_contextual)
    ok = (
        '"Reproducir segmentos en VLC"' in fuente
        and '"Reproducir marcadores en VLC"' in fuente
        and "_reproducir_segmentos_en_vlc" in fuente
    )
    return ok, f"menu={ok}"


def test_03():
    """`TareaListarSegmentosVarios` delega en el repositorio con contrato exacto."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
    try:
        id_a = _video_id(ruta_db, "a.mp4")
        id_b = _video_id(ruta_db, "b.mp4")
        sa = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
        sb = guardar_segmento(id_b, 5.0, 7.0, ruta_db)
        gestor = None
        try:
            gestor = __import__("tareas").GestorTareas()
            info = {}
            gestor.tarea_resultado.connect(lambda r: info.update(resultado=r))
            ok_aceptada = gestor.iniciar(
                tv.TareaListarSegmentosVarios([id_b, id_a], ruta_db)
            )
            ok_gestor = _esperar(
                lambda: not gestor.activo and gestor.hilo is None
            )
            resultado = info.get("resultado")
        finally:
            if gestor is not None:
                gestor.cerrar()
        esperado = [
            (sb[0], id_b, 5.0, 7.0, None),
            (sa[0], id_a, 1.0, 2.0, None),
        ]
        ok = ok_aceptada and ok_gestor and resultado == esperado
        return ok, f"resultado={resultado}"
    finally:
        temp.cleanup()


def test_04():
    """La UI no consulta SQLite ni accede a filesystem para lógica de negocio."""
    fuente = inspect.getsource(VisorVideos._procesar_secuencia_segmentos)
    ok = (
        "sqlite3" not in fuente
        and "conn.execute" not in fuente
        and "os.path.isfile" not in fuente
        and "subprocess" not in fuente
        and "Popen(" not in fuente
        and "#EXTVLCOPT" not in fuente
        and "generar_m3u(" not in fuente
    )
    return ok, f"capas={ok}"


def test_05():
    """Videos no expandidos también aportan sus segmentos (desde repositorio)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 5.0, 7.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            try:
                _seleccionar(ventana, ["a.mp4", "b.mp4"])
                # B nunca se expande
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            sec = _secuencia_obtenida(capturas)
            ok = (
                len(sec) == 2
                and {"a.mp4", "b.mp4"} == {s["nombre"] for s in sec}
            )
            return ok, f"secuencia={[(s['nombre'], s['inicio']) for s in sec]}"
        finally:
            temp.cleanup()


def test_06():
    """Orden: videos en orden de selección y segmentos por inicio/fin/id."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 40.0, 50.0, ruta_db)
            guardar_segmento(id_a, 10.0, 20.0, ruta_db)
            guardar_segmento(id_b, 5.0, 8.0, ruta_db)
            guardar_segmento(id_b, 30.0, 35.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            try:
                _seleccionar(ventana, ["a.mp4", "b.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            sec = _secuencia_obtenida(capturas)
            pares = [(s["nombre"], s["inicio"]) for s in sec]
            ok = pares == [
                ("a.mp4", 10.0),
                ("a.mp4", 40.0),
                ("b.mp4", 5.0),
                ("b.mp4", 30.0),
            ]
            return ok, f"pares={pares}"
        finally:
            temp.cleanup()


def test_07():
    """Video sin segmentos se omite silenciosamente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4", "c.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_c = _video_id(ruta_db, "c.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_c, 3.0, 4.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            try:
                _seleccionar(ventana, ["a.mp4", "b.mp4", "c.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            sec = _secuencia_obtenida(capturas)
            ok = (
                len(sec) == 2
                and "b.mp4" not in {s["nombre"] for s in sec}
            )
            return ok, f"secuencia={[(s['nombre']) for s in sec]}"
        finally:
            temp.cleanup()


def test_08():
    """Ningún video seleccionado tiene segmentos → mensaje y no VLC."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = _secuencia_capturada(ventana)
        try:
            _seleccionar(ventana, ["a.mp4", "b.mp4"])
            ventana._reproducir_segmentos_en_vlc()
            _esperar(
                lambda: not ventana.gestor_reproduccion.activo,
                timeout_ms=15000,
            )
            ok = (
                capturas[0] == []
                and "no tienen segmentos" in ventana.mensaje_carpeta.text()
            )
        finally:
            _restaurar(capturas[1:], None)
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={len(capturas[0])} msg={ventana.mensaje_carpeta.text()!r}"


def test_09():
    """Archivo faltante omite sus segmentos y reproduce los válidos."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 5.0, 7.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            # a.mp4 no tiene archivo real; b.mp4 sí (via ruta existente)
            visor_videos.ruta_video_existente = (
                lambda c, n: "C:\\videos\\" + n if n == "b.mp4" else None
            )
            try:
                _seleccionar(ventana, ["a.mp4", "b.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            sec = _secuencia_obtenida(capturas)
            ok = (
                len(sec) == 1
                and sec[0]["nombre"] == "b.mp4"
                and "omitidos" in ventana.mensaje_carpeta.text()
            )
            return ok, f"secuencia={[(s['nombre']) for s in sec]}"
        finally:
            temp.cleanup()


def test_10():
    """Todos los archivos faltantes → no abre VLC (secuencia vacía)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            # sin rutas resolubles
            visor_videos.ruta_video_existente = lambda c, n: None
            try:
                _seleccionar(ventana, ["a.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(
                    lambda: not ventana.gestor_reproduccion.activo,
                    timeout_ms=15000,
                )
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            ok = capturas[0] == []
            return ok, f"secuencia={len(capturas[0])}"
        finally:
            temp.cleanup()


def _m3u_secuencia(segmentos, ruta_vlc):
    contenidos = []
    argv = []
    original = pl.abrir_playlist_en_vlc

    def _abrir(ruta_m3u, ruta_vlc, bucle=False):
        with open(ruta_m3u, encoding="utf-8") as archivo:
            contenidos.append(archivo.read())
        argv.append(
            [ruta_vlc] + (["--loop"] if bucle else []) + [ruta_m3u]
        )
        return object()

    pl.abrir_playlist_en_vlc = _abrir
    try:
        reproducir_secuencia_segmentos(segmentos, ruta_vlc)
    finally:
        pl.abrir_playlist_en_vlc = original
    return contenidos[0] if contenidos else "", argv[0] if argv else None


def _segmentos_entrada(video, nombre):
    return [
        {"ruta": video, "nombre": nombre, "inicio": 1.0, "fin": 3.0},
        {"ruta": video, "nombre": nombre, "inicio": 5.0, "fin": 7.0},
        {"ruta": video, "nombre": nombre, "inicio": 9.0, "fin": 11.0},
    ]


def test_11():
    """M3U con una entrada por segmento, start/stop y sin --loop."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido, argv = _m3u_secuencia(
            _segmentos_entrada(ruta, "v.mp4"), "C:\\vlc\\vlc.exe"
        )
        ok = (
            contenido.count("#EXTINF") == 3
            and contenido.count("#EXTVLCOPT:start-time") == 3
            and contenido.count("#EXTVLCOPT:stop-time") == 3
            and "--loop" not in argv
            and "start-time=1" in contenido
            and "stop-time=3" in contenido
            and "start-time=9" in contenido
            and "stop-time=11" in contenido
        )
        return ok, f"argv={argv}"


def test_12():
    """Mismo archivo puede repetirse (3 entradas del mismo video)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido, _argv = _m3u_secuencia(
            _segmentos_entrada(ruta, "v.mp4"), "C:\\vlc\\vlc.exe"
        )
        ok = (
            contenido.count("C:\\") >= 3
            and contenido.count("start-time") == 3
        )
        return ok, f"contenido={contenido!r}"


def test_13():
    """Decimales preservados en la secuencia."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido, _argv = _m3u_secuencia(
            [
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 1.5, "fin": 3.25},
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 5.75, "fin": 7.5},
            ],
            "C:\\vlc\\vlc.exe",
        )
        ok = (
            "start-time=1.5" in contenido
            and "stop-time=3.25" in contenido
            and "start-time=5.75" in contenido
            and "stop-time=7.5" in contenido
        )
        return ok, f"contenido={contenido!r}"


def test_14():
    """UTF-8 y rutas con espacios."""
    with tempfile.TemporaryDirectory() as carpeta:
        sub = os.path.join(carpeta, "mi carpeta")
        os.makedirs(sub)
        ruta = os.path.join(sub, "mi video.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido, _argv = _m3u_secuencia(
            [{"ruta": ruta, "nombre": "mi video — áéí.mp4", "inicio": 1.0, "fin": 2.0}],
            "C:\\vlc\\vlc.exe",
        )
        ok = ruta in contenido and "áéí" in contenido
        return ok, f"contenido={contenido!r}"


def test_15():
    """Duplicados y solapamientos conservados (no se deduplican ni fusionan)."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        contenido, _argv = _m3u_secuencia(
            [
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 10.0, "fin": 20.0},
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 10.0, "fin": 20.0},
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 15.0, "fin": 25.0},
            ],
            "C:\\vlc\\vlc.exe",
        )
        ok = contenido.count("#EXTINF") == 3
        return ok, f"entradas={contenido.count('#EXTINF')}"


def _capturar(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return True
    except Exception:
        return False
    return False


def test_16():
    """Secuencia corrupta (fin<=inicio) rechazada antes de lanzar."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        ok = _capturar(
            ValueError,
            reproducir_secuencia_segmentos,
            [
                {"ruta": ruta, "nombre": "v.mp4", "inicio": 5.0, "fin": 3.0}
            ],
            "C:\\vlc\\vlc.exe",
        )
        return ok, "corrupto"


def test_17():
    """Secuencia con ruta inexistente → FileNotFoundError."""
    ruta = os.path.join(tempfile.gettempdir(), "b58_no_existe.mp4")
    if os.path.isfile(ruta):
        os.remove(ruta)
    try:
        ok = _capturar(
            FileNotFoundError,
            reproducir_secuencia_segmentos,
            [{"ruta": ruta, "nombre": "v.mp4", "inicio": 1.0, "fin": 2.0}],
            "C:\\vlc\\vlc.exe",
        )
        return ok, "file_not_found"
    finally:
        if os.path.isfile(ruta):
            os.remove(ruta)


def test_18():
    """Secuencia vacía → ValueError; entrada no dict → TypeError."""
    ok = _capturar(ValueError, reproducir_secuencia_segmentos, [], "C:\\vlc\\vlc.exe")
    ok = ok and _capturar(
        TypeError,
        reproducir_secuencia_segmentos,
        ["no-es-dict"],
        "C:\\vlc\\vlc.exe",
    )
    return ok, "vacia/no-dict"


def test_19():
    """VLC ausente → RuntimeError."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "v.mp4")
        with open(ruta, "wb") as archivo:
            archivo.write(b"\x00" * 4)
        original = pl.localizar_vlc
        pl.localizar_vlc = lambda: None
        try:
            ok = _capturar(
                RuntimeError,
                reproducir_secuencia_segmentos,
                [{"ruta": ruta, "nombre": "v.mp4", "inicio": 1.0, "fin": 2.0}],
                None,
            )
        finally:
            pl.localizar_vlc = original
        return ok, "vlc_ausente"


def test_20():
    """Reproducir la secuencia no modifica SQLite."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 3.0, ruta_db)
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            antes = _md5(ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            try:
                _seleccionar(ventana, ["a.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
                despues = _md5(ruta_db)
                marcadores = listar_marcadores(id_a, ruta_db)
                segmentos = listar_segmentos(id_a, ruta_db)
                ok = (
                    antes == despues
                    and len(marcadores) == 1
                    and len(segmentos) == 1
                )
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"db_igual={antes == despues}"
        finally:
            temp.cleanup()


def test_21():
    """Marcadores no se ven afectados por la secuencia."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 3.0, ruta_db)
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            try:
                _seleccionar(ventana, ["a.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
                sec = _secuencia_obtenida(capturas)
                marcadores = listar_marcadores(id_a, ruta_db)
                ok = len(sec) == 1 and len(marcadores) == 1
            finally:
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"marcadores={len(marcadores)}"
        finally:
            temp.cleanup()


def test_22():
    """B5.6 y B5.7 intactos: reproducir_segmento / en_bucle siguen en la UI."""
    ok = (
        hasattr(visor_videos, "reproducir_segmento")
        and hasattr(visor_videos, "reproducir_segmento_en_bucle")
        and hasattr(Tarjeta, "segmento_reproduccion_solicitada")
        and hasattr(Tarjeta, "segmento_bucle_solicitado")
    )
    return ok, f"b56_b57={ok}"


def test_23():
    """B5.3 intacto: doble clic sobre la franja sigue reproduciendo temporalmente."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QPointingDevice

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
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            franja = tarjeta._franja
            ancho = franja.width()
            for tipo in (
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.MouseButtonDblClick,
                QEvent.MouseButtonRelease,
            ):
                evento = QMouseEvent(
                    tipo,
                    QPointF(float(ancho * 0.5), 6.0),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                    QPointingDevice.primaryPointingDevice(),
                )
                QApplication.sendEvent(franja, evento)
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


def test_24():
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
        ok = "start-time=1.5" in contenido and "stop-time" not in contenido
        return ok, f"contenido={contenido!r}"


def test_25():
    """La consulta multi-video se ejecuta fuera del hilo principal."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 3.0, 4.0, ruta_db)
            info = {}
            original = tv.listar_segmentos_de

            def _espiar(*args, **kwargs):
                info["principal"] = QThread.isMainThread()
                return original(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            tv.listar_segmentos_de = _espiar
            try:
                _seleccionar(ventana, ["a.mp4", "b.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(lambda: len(capturas[0]) >= 1 and not ventana.gestor_reproduccion.activo, timeout_ms=15000)
            finally:
                tv.listar_segmentos_de = original
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            ok = (
                info.get("principal") is False
                and len(_secuencia_obtenida(capturas)) == 2
            )
            return ok, f"principal={info.get('principal')}"
        finally:
            temp.cleanup()


def test_26():
    """Solicitudes rápidas: la infraestructura no mezcla resultados."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 3.0, 4.0, ruta_db)
            original = tv.listar_segmentos_de

            def _lento(*args, **kwargs):
                time.sleep(0.5)
                return original(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            capturas = _secuencia_capturada(ventana)
            tv.listar_segmentos_de = _lento
            try:
                _seleccionar(ventana, ["a.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                # segunda solicitud inmediata (gestor ocupado → rechazada)
                _seleccionar(ventana, ["b.mp4"])
                ventana._reproducir_segmentos_en_vlc()
                _esperar(
                    lambda: not ventana.gestor_reproduccion.activo,
                    timeout_ms=20000,
                )
            finally:
                tv.listar_segmentos_de = original
                _restaurar(capturas[1:], None)
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            sec = _secuencia_obtenida(capturas)
            # sin mezcla: si hubo captura, es íntegramente de un solo video
            nombres = {s["nombre"] for s in sec}
            ok = len(nombres) <= 1
            return ok, f"secuencia={[(s['nombre']) for s in sec]}"
        finally:
            temp.cleanup()


def test_27():
    """Prueba real VLC: secuencia 1→3 / 5→7 / 9→11 (~6 s) auto-avance."""
    vlc = localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids0 = _pids_vlc()
    with tempfile.TemporaryDirectory() as carpeta:
        video = _generar_video(carpeta)
        if video is None:
            return True, "skip: FFmpeg ausente"
        nombre = os.path.basename(video)
        segmentos = _segmentos_entrada(video, nombre)
        proceso = None
        try:
            proceso = reproducir_secuencia_segmentos(segmentos, vlc)
            vivo = proceso is not None and proceso.poll() is None
            time.sleep(1.2)
            sigue = proceso is not None and proceso.poll() is None
        finally:
            _cerrar_por_pid(proceso)
        m3u = os.path.join(carpeta, "visor_marcadores_sec.m3u")
        pl.generar_m3u(
            [
                {"ruta": s["ruta"], "nombre": s["nombre"], "tiempo": s["inicio"], "fin": s["fin"]}
                for s in segmentos
            ],
            m3u,
        )
        sw = time.monotonic()
        p = subprocess.Popen(
            [vlc, "--no-one-instance", "--intf", "dummy", "--play-and-exit", m3u],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **{"creationflags": subprocess.CREATE_NO_WINDOW},
        )
        try:
            p.wait(timeout=25)
        except subprocess.TimeoutExpired:
            p.kill()
        duracion = round(time.monotonic() - sw, 2)
        time.sleep(0.8)
        residuales = sorted(_pids_vlc() - pids0)
        ok = (
            vivo and sigue
            and 4.0 <= duracion <= 9.0
            and not residuales
        )
        return (
            ok,
            f"vivo={vivo} duracion={duracion}s residuales={residuales}",
        )


def test_28():
    """Prueba real VLC multi-video: A(1→2,4→5) B(2→3,6→7)."""
    vlc = localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids0 = _pids_vlc()
    with tempfile.TemporaryDirectory() as carpeta:
        video_a = _generar_video(carpeta, "video_a.mp4")
        if video_a is None:
            return True, "skip: FFmpeg ausente"
        video_b = os.path.join(carpeta, "video_b.mp4")
        subprocess.run(["copy", "/y", video_a, video_b], shell=True, capture_output=True)
        if not os.path.isfile(video_b):
            return True, "skip: no se pudo duplicar video"
        segmentos = [
            {"ruta": video_a, "nombre": "A", "inicio": 1.0, "fin": 2.0},
            {"ruta": video_a, "nombre": "A", "inicio": 4.0, "fin": 5.0},
            {"ruta": video_b, "nombre": "B", "inicio": 2.0, "fin": 3.0},
            {"ruta": video_b, "nombre": "B", "inicio": 6.0, "fin": 7.0},
        ]
        proceso = None
        try:
            proceso = reproducir_secuencia_segmentos(segmentos, vlc)
            vivo = proceso is not None and proceso.poll() is None
        finally:
            _cerrar_por_pid(proceso)
        m3u = os.path.join(carpeta, "visor_marcadores_multi.m3u")
        pl.generar_m3u(
            [
                {"ruta": s["ruta"], "nombre": s["nombre"], "tiempo": s["inicio"], "fin": s["fin"]}
                for s in segmentos
            ],
            m3u,
        )
        sw = time.monotonic()
        p = subprocess.Popen(
            [vlc, "--no-one-instance", "--intf", "dummy", "--play-and-exit", m3u],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **{"creationflags": subprocess.CREATE_NO_WINDOW},
        )
        try:
            p.wait(timeout=25)
        except subprocess.TimeoutExpired:
            p.kill()
        duracion = round(time.monotonic() - sw, 2)
        time.sleep(0.8)
        residuales = sorted(_pids_vlc() - pids0)
        ok = vivo and 2.5 <= duracion <= 7.0 and not residuales
        return ok, f"vivo={vivo} duracion={duracion}s residuales={residuales}"


def test_29():
    """Instancia VLC preexistente: la secuencia abre una nueva y no toca la previa."""
    vlc = localizar_vlc()
    if vlc is None:
        return True, "skip: VLC ausente"
    pids0 = _pids_vlc()
    puerto = 4226
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
            video = _generar_video(carpeta)
            if video is None:
                return True, "skip: FFmpeg ausente"
            segmentos = _segmentos_entrada(video, os.path.basename(video))
            popen = reproducir_secuencia_segmentos(segmentos, vlc)
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
        test_25,
        test_26,
        test_27,
        test_28,
        test_29,
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
