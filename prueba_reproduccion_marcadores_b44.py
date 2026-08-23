import inspect
import os
import py_compile
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication, QMessageBox

import escanear_videos as escanear_mod
import playlist_vlc as pl
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_videos,
    listar_marcadores,
    listar_marcadores_de,
    listar_videos,
)
from visor_videos import VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


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
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    if ventana.gestor_marcadores is not None:
        ventana.gestor_marcadores.cerrar()
    if ventana.gestor_reproduccion is not None:
        ventana.gestor_reproduccion.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _registro(nombre, ruta, duracion=100.0):
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 3,
        "tamano_bytes": 1000,
    }


def _crear_archivos(directorio, nombres):
    rutas = {}
    for nombre in nombres:
        ruta = os.path.join(directorio, nombre)
        with open(ruta, "wb") as archivo:
            archivo.write(b"")
        rutas[nombre] = ruta
    return rutas


def _crear_escenario(especificacion):
    """especificacion: {nombre: {"ruta": str, "marcadores": [tiempos]}}."""
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    registros = [
        _registro(nombre, spec["ruta"])
        for nombre, spec in especificacion.items()
    ]
    guardar_videos(registros, ruta_db)
    ids = {}
    for fila in listar_videos(ruta_db):
        ids[fila[0]] = fila[8]
    for nombre, spec in especificacion.items():
        for tiempo in spec.get("marcadores", []):
            guardar_marcador(ids[nombre], tiempo, ruta_db)
    return temp, ruta_db, ids


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _parsear_m3u(contenido):
    lineas = contenido.splitlines()
    if not lineas or lineas[0] != "#EXTM3U":
        return None
    entradas = []
    indice = 1
    while indice + 2 < len(lineas):
        extinf = lineas[indice]
        opt = lineas[indice + 1]
        ruta = lineas[indice + 2]
        if not extinf.startswith("#EXTINF:"):
            return None
        if not opt.startswith("#EXTVLCOPT:start-time="):
            return None
        entradas.append(
            {
                "titulo": extinf.split(",", 1)[1],
                "tiempo": opt.split("=", 1)[1],
                "ruta": ruta,
            }
        )
        indice += 3
    return entradas


_SIN_VLC = object()


def _ejecutar_flujo(ventana, seleccionados, decision=None, vlc_localizada=_SIN_VLC):
    capturas = []
    ventana._nombres_seleccionados = set(seleccionados)
    if decision is not None:
        ventana._preguntar_videos_sin_marcadores = (
            lambda cantidad, d=decision: d
        )
    if vlc_localizada is _SIN_VLC:
        vlc_localizada = "C:\\vlc\\vlc.exe"
    original_localizar = visor_videos.localizar_vlc
    original_abrir = visor_videos.abrir_playlist_en_vlc
    visor_videos.localizar_vlc = lambda: vlc_localizada

    def _abrir(ruta_m3u, ruta_vlc):
        with open(ruta_m3u, encoding="utf-8") as archivo:
            contenido = archivo.read()
        capturas.append(
            {"ruta_m3u": ruta_m3u, "vlc": ruta_vlc, "contenido": contenido}
        )
        return object()

    visor_videos.abrir_playlist_en_vlc = _abrir
    original_exec = visor_videos.QMessageBox.exec
    visor_videos.QMessageBox.exec = lambda self: QMessageBox.Ok
    try:
        ventana._reproducir_marcadores_en_vlc()
        espero = _esperar(lambda: not ventana.gestor_reproduccion.activo)
    finally:
        visor_videos.localizar_vlc = original_localizar
        visor_videos.abrir_playlist_en_vlc = original_abrir
        visor_videos.QMessageBox.exec = original_exec
    return capturas, espero


def _tiempos_de(capturas):
    if not capturas:
        return []
    entradas = _parsear_m3u(capturas[0]["contenido"])
    if entradas is None:
        return []
    return [entrada["tiempo"] for entrada in entradas]


def test_01_py_compile():
    ok = True
    detalles = []
    for archivo in [
        "escanear_videos.py",
        "tareas_videos.py",
        "playlist_vlc.py",
        "visor_videos.py",
        "prueba_reproduccion_marcadores_b44.py",
    ]:
        try:
            py_compile.compile(archivo, doraise=True)
        except py_compile.PyCompileError as exc:
            ok = False
            detalles.append(f"{archivo}: {exc}")
    return ok, "; ".join(detalles) or "py_compile OK"


def test_02_formateo_tiempos():
    ok = (
        pl.formatear_tiempo_vlc(12.437) == "12.437"
        and pl.formatear_tiempo_vlc(40.0) == "40"
        and pl.formatear_tiempo_vlc(0) == "0"
        and pl.formatear_tiempo_vlc(0.30000000000000004) == "0.3"
        and pl.formatear_tiempo_vlc(5.5) == "5.5"
        and "00:01:12.437" in pl.formatear_titulo_marcador("v.mp4", 72.437)
        and pl.formatear_titulo_marcador("v.mp4", 72.437).startswith("v.mp4")
    )
    return ok, (
        f"vlc={pl.formatear_tiempo_vlc(12.437)} "
        f"titulo={pl.formatear_titulo_marcador('v.mp4', 72.437)}"
    )


def test_03_generar_m3u():
    with tempfile.TemporaryDirectory() as directorio:
        ruta = os.path.join(directorio, "p.m3u")
        entradas = [
            {"ruta": r"C:\v\a.mp4", "nombre": "a.mp4", "tiempo": 12.437},
            {"ruta": r"C:\v\a.mp4", "nombre": "a.mp4", "tiempo": 40.0},
            {"ruta": r"C:\v\b.mp4", "nombre": "b.mp4", "tiempo": 5.5},
        ]
        pl.generar_m3u(entradas, ruta)
        with open(ruta, encoding="utf-8") as archivo:
            contenido = archivo.read()
        entradas_leidas = _parsear_m3u(contenido)
        ok = (
            entradas_leidas is not None
            and len(entradas_leidas) == 3
            and entradas_leidas[0]["tiempo"] == "12.437"
            and entradas_leidas[1]["tiempo"] == "40"
            and entradas_leidas[2]["tiempo"] == "5.5"
            and entradas_leidas[0]["ruta"] == r"C:\v\a.mp4"
            and entradas_leidas[1]["ruta"] == r"C:\v\a.mp4"
            and entradas_leidas[2]["ruta"] == r"C:\v\b.mp4"
        )
        return ok, contenido


def test_04_localizar_vlc():
    original_isfile = os.path.isfile
    original_which = pl.shutil.which
    original_env = pl.os.environ
    resultados = []
    try:
        os.path.isfile = lambda p: p == r"C:\Program Files\VideoLAN\VLC\vlc.exe"
        pl.shutil.which = lambda name: None
        pl.os.environ = {
            "ProgramFiles": r"C:\Program Files",
            "ProgramFiles(x86)": r"C:\Program Files (x86)",
        }
        resultados.append(
            pl.localizar_vlc() == r"C:\Program Files\VideoLAN\VLC\vlc.exe"
        )

        os.path.isfile = lambda p: False
        pl.shutil.which = lambda name: None
        resultados.append(pl.localizar_vlc() is None)

        pl.shutil.which = lambda name: r"C:\w\vlc.exe"
        resultados.append(pl.localizar_vlc() == r"C:\w\vlc.exe")
        pl.shutil.which = lambda name: None

        os.path.isfile = lambda p: p == r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        resultados.append(
            pl.localizar_vlc()
            == r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        )
    finally:
        os.path.isfile = original_isfile
        pl.shutil.which = original_which
        pl.os.environ = original_env
    return all(resultados), str(resultados)


def test_05_abrir_playlist_en_vlc():
    original_popen = pl.subprocess.Popen
    llamadas = []

    def _popen(args, **kwargs):
        llamadas.append(args)
        return object()

    pl.subprocess.Popen = _popen
    try:
        pl.abrir_playlist_en_vlc(r"C:\t\p.m3u", r"C:\vlc\vlc.exe")
    finally:
        pl.subprocess.Popen = original_popen
    ok = (
        len(llamadas) == 1
        and llamadas[0] == [r"C:\vlc\vlc.exe", r"C:\t\p.m3u"]
    )
    return ok, str(llamadas)


def test_06_listar_marcadores_de():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["a.mp4", "b.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "a.mp4": {"ruta": rutas["a.mp4"], "marcadores": [70.0, 10.5, 40.0]},
                "b.mp4": {"ruta": rutas["b.mp4"], "marcadores": [30.0, 5.0]},
            }
        )
        try:
            filas = listar_marcadores_de([ids["b.mp4"], ids["a.mp4"]], ruta_db)
            tiempos = [tiempo for _, _, tiempo, _ in filas]
            ok = (
                tiempos == [5.0, 30.0, 10.5, 40.0, 70.0]
                and listar_marcadores_de([], ruta_db) == []
            )
            try:
                listar_marcadores_de("no", ruta_db)
                ok = False
            except TypeError:
                pass
            return ok, f"tiempos={tiempos}"
        finally:
            temp.cleanup()


def test_07_flujo_orden_y_precision():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [70.0, 10.0, 12.437, 40.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": [30.0, 5.0]},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, ["A.mp4", "B.mp4"])
            tiempos = _tiempos_de(capturas)
            ok = (
                espero
                and len(capturas) == 1
                and tiempos
                == ["10", "12.437", "40", "70", "5", "30"]
                and capturas[0]["vlc"] == "C:\\vlc\\vlc.exe"
            )
            return ok, f"tiempos={tiempos} espero={espero}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_08_orden_visible_no_seleccion():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": [5.0]},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, ["B.mp4", "A.mp4"])
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            ok = (
                espero
                and entradas is not None
                and [e["ruta"] for e in entradas]
                == [rutas["A.mp4"], rutas["B.mp4"]]
            )
            return ok, f"rutas={[e['ruta'] for e in entradas] if entradas else None}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_09_sin_marcadores_omitir():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0, 40.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": []},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4", "B.mp4"], decision="omitir"
            )
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            ok = (
                espero
                and entradas is not None
                and len(entradas) == 2
                and all(e["ruta"] == rutas["A.mp4"] for e in entradas)
            )
            return ok, f"rutas={[e['ruta'] for e in entradas] if entradas else None}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_10_sin_marcadores_desde_inicio():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": []},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4", "B.mp4"], decision="inicio"
            )
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            ok = (
                espero
                and entradas is not None
                and [e["ruta"] for e in entradas]
                == [rutas["A.mp4"], rutas["B.mp4"]]
                and [e["tiempo"] for e in entradas] == ["10", "0"]
            )
            return ok, f"tiempos={[e['tiempo'] for e in entradas] if entradas else None}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_11_sin_marcadores_cancelar():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": []},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4", "B.mp4"], decision="cancelar"
            )
            ok = espero and capturas == []
            return ok, f"capturas={len(capturas)}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_12_todos_sin_marcadores_desde_inicio():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": []},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": []},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4", "B.mp4"], decision="inicio"
            )
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            ok = (
                espero
                and entradas is not None
                and [e["ruta"] for e in entradas]
                == [rutas["A.mp4"], rutas["B.mp4"]]
                and all(e["tiempo"] == "0" for e in entradas)
            )
            return ok, f"entradas={len(entradas) if entradas else 0}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_13_todos_sin_marcadores_omitir_vacio():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": []},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": []},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4", "B.mp4"], decision="omitir"
            )
            ok = espero and capturas == []
            return ok, f"capturas={len(capturas)}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_14_vlc_no_encontrado():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {"A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]}}
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(
                ventana, ["A.mp4"], vlc_localizada=None
            )
            ok = espero and capturas == []
            return ok, f"capturas={len(capturas)}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_15_archivo_inexistente():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4"])
        ruta_inexistente = os.path.join(directorio, "no_existe.mp4")
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]},
                "B.mp4": {
                    "ruta": ruta_inexistente,
                    "marcadores": [20.0],
                },
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, ["A.mp4", "B.mp4"])
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            marcadores_aun = listar_marcadores(ids["B.mp4"], ruta_db)
            ok = (
                espero
                and entradas is not None
                and [e["ruta"] for e in entradas] == [rutas["A.mp4"]]
                and [tiempo for _, _, tiempo, _ in marcadores_aun] == [20.0]
            )
            return ok, (
                f"rutas={[e['ruta'] for e in entradas] if entradas else None} "
                f"marcadoresB={marcadores_aun}"
            )
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_16_no_modifica_marcadores():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {"A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0, 40.0]}}
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            antes = listar_marcadores(ids["A.mp4"], ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, ["A.mp4"])
            despues = listar_marcadores(ids["A.mp4"], ruta_db)
            ok = espero and antes == despues and len(capturas) == 1
            return ok, f"antes={antes} despues={despues}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_17_sin_seleccion_no_abre():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {"A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0]}}
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, [])
            ok = espero and capturas == []
            return ok, f"capturas={len(capturas)}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_18_accion_menu_contextual():
    fuente = inspect.getsource(visor_videos.VisorVideos._mostrar_menu_contextual)
    ok = (
        "Reproducir marcadores en VLC" in fuente
        and "setEnabled(bool(self._nombres_seleccionados))" in fuente
        and "_reproducir_marcadores_en_vlc" in fuente
    )
    return ok, "accion presente" if ok else "accion ausente"


def test_19_lanzamiento_unico():
    with tempfile.TemporaryDirectory() as directorio:
        rutas = _crear_archivos(directorio, ["A.mp4", "B.mp4"])
        temp, ruta_db, ids = _crear_escenario(
            {
                "A.mp4": {"ruta": rutas["A.mp4"], "marcadores": [10.0, 40.0, 70.0]},
                "B.mp4": {"ruta": rutas["B.mp4"], "marcadores": [5.0]},
            }
        )
        ventana = None
        try:
            ventana = _abrir_ventana(ruta_db)
            capturas, espero = _ejecutar_flujo(ventana, ["A.mp4", "B.mp4"])
            entradas = _parsear_m3u(capturas[0]["contenido"]) if capturas else None
            ok = espero and len(capturas) == 1 and len(entradas) == 4
            return ok, f"abrir={len(capturas)} entradas={len(entradas) if entradas else 0}"
        finally:
            if ventana is not None:
                ventana.close()
                _limpiar(ventana)
            temp.cleanup()


def test_20_limpieza_playlists_anteriores():
    with tempfile.TemporaryDirectory() as directorio:
        a = os.path.join(directorio, "visor_marcadores_a.m3u")
        b = os.path.join(directorio, "visor_marcadores_b.m3u")
        for ruta in (a, b):
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write("#EXTM3U\n")
        nueva = os.path.join(directorio, "visor_marcadores_nueva.m3u")
        pl.generar_m3u(
            [{"ruta": r"C:\v\a.mp4", "nombre": "a.mp4", "tiempo": 1.0}],
            nueva,
        )
        ok = (
            not os.path.exists(a)
            and not os.path.exists(b)
            and os.path.exists(nueva)
        )
        return ok, (
            f"a={os.path.exists(a)} b={os.path.exists(b)} "
            f"nueva={os.path.exists(nueva)}"
        )


def test_21_no_borra_ajenos():
    with tempfile.TemporaryDirectory() as directorio:
        usuario = os.path.join(directorio, "playlist_usuario.m3u")
        otro = os.path.join(directorio, "nota.txt")
        for ruta in (usuario, otro):
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write("x")
        pl.limpiar_playlists_anteriores(directorio)
        ok = os.path.exists(usuario) and os.path.exists(otro)
        return ok, f"usuario={os.path.exists(usuario)} otro={os.path.exists(otro)}"


def test_22_eliminacion_bloqueada():
    with tempfile.TemporaryDirectory() as directorio:
        vieja = os.path.join(directorio, "visor_marcadores_vieja.m3u")
        with open(vieja, "w", encoding="utf-8") as archivo:
            archivo.write("#EXTM3U\n")
        original_remove = pl.os.remove

        def _remove_bloqueado(ruta, **kwargs):
            if ruta == vieja:
                raise PermissionError("bloqueado por VLC")
            return original_remove(ruta)

        pl.os.remove = _remove_bloqueado
        try:
            nueva = os.path.join(directorio, "visor_marcadores_nueva.m3u")
            pl.generar_m3u(
                [{"ruta": r"C:\v\a.mp4", "nombre": "a.mp4", "tiempo": 2.5}],
                nueva,
            )
        finally:
            pl.os.remove = original_remove
        with open(nueva, encoding="utf-8") as archivo:
            contenido = archivo.read()
        ok = os.path.exists(vieja) and os.path.exists(nueva)
        ok = ok and "#EXTVLCOPT:start-time=2.5" in contenido
        return ok, (
            f"vieja={os.path.exists(vieja)} nueva={os.path.exists(nueva)}"
        )


def test_23_ruta_con_espacios():
    with tempfile.TemporaryDirectory() as directorio:
        ruta_destino = os.path.join(directorio, "visor_marcadores_x.m3u")
        ruta_video = r"C:\Mis Videos\Vacaciones 2026\video prueba.mp4"
        pl.generar_m3u(
            [
                {
                    "ruta": ruta_video,
                    "nombre": "video prueba.mp4",
                    "tiempo": 1.0,
                }
            ],
            ruta_destino,
        )
        with open(ruta_destino, encoding="utf-8") as archivo:
            contenido = archivo.read()
        entradas = _parsear_m3u(contenido)
        ok = entradas is not None and entradas[0]["ruta"] == ruta_video
        return ok, contenido


def test_24_ruta_unicode():
    with tempfile.TemporaryDirectory() as directorio:
        ruta_destino = os.path.join(directorio, "visor_marcadores_u.m3u")
        ruta_video = "C:\\Vídeos\\Cumpleaños José\\acción 01.mp4"
        pl.generar_m3u(
            [
                {
                    "ruta": ruta_video,
                    "nombre": "acción 01.mp4",
                    "tiempo": 3.5,
                }
            ],
            ruta_destino,
        )
        with open(ruta_destino, encoding="utf-8") as archivo:
            contenido = archivo.read()
        entradas = _parsear_m3u(contenido)
        ok = (
            entradas is not None
            and entradas[0]["ruta"] == ruta_video
            and "Vídeos" in contenido
            and "José" in contenido
            and "acción" in contenido
        )
        return ok, contenido


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01_py_compile,
        test_02_formateo_tiempos,
        test_03_generar_m3u,
        test_04_localizar_vlc,
        test_05_abrir_playlist_en_vlc,
        test_06_listar_marcadores_de,
        test_07_flujo_orden_y_precision,
        test_08_orden_visible_no_seleccion,
        test_09_sin_marcadores_omitir,
        test_10_sin_marcadores_desde_inicio,
        test_11_sin_marcadores_cancelar,
        test_12_todos_sin_marcadores_desde_inicio,
        test_13_todos_sin_marcadores_omitir_vacio,
        test_14_vlc_no_encontrado,
        test_15_archivo_inexistente,
        test_16_no_modifica_marcadores,
        test_17_sin_seleccion_no_abre,
        test_18_accion_menu_contextual,
        test_19_lanzamiento_unico,
        test_20_limpieza_playlists_anteriores,
        test_21_no_borra_ajenos,
        test_22_eliminacion_bloqueada,
        test_23_ruta_con_espacios,
        test_24_ruta_unicode,
    ]
    resultados = []
    for indice, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((indice, ok, detalle))
        print(f"P{indice:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
