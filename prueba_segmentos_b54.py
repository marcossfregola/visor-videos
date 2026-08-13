"""Pruebas del Bloque B — Creación, representación visual, persistencia y
eliminación de segmentos A–B (B5.4).

Cubre: control de modo Segmento, modo normal vs modo segmento (marcadores
vs endpoints), normalización A/B, A incompleto y sus cancelaciones, bandas
en la franja (sin widgets), persistencia/eliminación asíncronas, duplicados,
solapamientos, hit-testing (marcador vs segmento), reconciliación optimista
(altas/bajas durante carga), reexpansión, reinicio, coexistencia con
marcadores, doble clic B5.3, aislamiento A→B, separación de capas,
rendimiento (0 FFmpeg/FFprobe/pixmaps) y concurrencia SQLite
marcadores ↔ segmentos.
"""

import contextlib
import inspect
import os
import py_compile
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import playlist_vlc
import scrubber as scrubber_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    conectar_bd,
    eliminar_marcador,
    eliminar_segmento,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
)
from tareas import GestorTareas
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


def _activar_modo_segmento(tarjeta):
    tarjeta._boton_segmento.setChecked(True)


def _crear_segmento_ui(ventana, tarjeta, x1, x2, objetivo=1):
    """Crea un segmento mediante clics reales sobre la franja (modo segmento).

    `objetivo` es el número de segmentos esperado al terminar (para crear
    varios consecutivos sin devolver antes de que el segundo extremo llegue).
    """
    _activar_modo_segmento(tarjeta)
    franja = tarjeta._franja
    _press(franja, x1)
    ok_a = _esperar(lambda: tarjeta._extremo_segmento is not None)
    _press(franja, x2)
    ok_b = _esperar(lambda: len(tarjeta._segmentos) >= objetivo)
    _drenar_segmentos(ventana)
    return ok_a and ok_b


@contextlib.contextmanager
def _repos_lentos(segundos=0.08):
    originales = {
        "guardar_marcador": tv.guardar_marcador,
        "eliminar_marcador": tv.eliminar_marcador,
        "guardar_segmento": tv.guardar_segmento,
        "eliminar_segmento": tv.eliminar_segmento,
    }

    def _lento(fn):
        def _envuelto(*a, **k):
            time.sleep(segundos)
            return fn(*a, **k)

        return _envuelto

    for nombre, fn in originales.items():
        setattr(tv, nombre, _lento(fn))
    try:
        yield
    finally:
        for nombre, fn in originales.items():
            setattr(tv, nombre, fn)


def _correr_tarea(gestor, tarea, errores):
    gestor.tarea_error.connect(lambda m, e=errores: e.append(m))
    if not gestor.iniciar(tarea):
        errores.append("tarea rechazada")


def _esperar_gestores(gestores):
    return _esperar(
        lambda: all(
            not g.activo and g.hilo is None for g in gestores
        )
    )


def test_01():
    modulos = [
        "scrubber.py",
        "visor_videos.py",
        "prueba_segmentos_b54.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Existe el control 'Segmento' en la tarjeta expandida."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            ok = hasattr(tarjeta, "_boton_segmento") and tarjeta._boton_segmento.isCheckable()
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"boton={hasattr(tarjeta, '_boton_segmento')}"


def test_03():
    """Modo normal: clic izquierdo sigue creando marcador."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _press(franja, ancho * 0.25)
            ok = len(tarjeta._marcadores) == 1 and tarjeta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={len(tarjeta._marcadores)} segmentos={len(tarjeta._segmentos)}"


def test_04():
    """Modo segmento: primer clic fija A sin crear marcador."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _press(franja, ancho * 0.5)
            ok_a = _esperar(lambda: tarjeta._extremo_segmento is not None)
            ok = (
                ok_a
                and tarjeta._marcadores == []
                and tarjeta._segmentos == []
                and tarjeta._franja.inicio_segmento_pendiente() is not None
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"a={tarjeta._extremo_segmento} marcadores={len(tarjeta._marcadores)}"


def test_05():
    """Modo segmento: segundo clic crea el segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            ok_ui = _crear_segmento_ui(ventana, tarjeta, ancho * 0.25, ancho * 0.75)
            seg = tarjeta._segmentos[0] if tarjeta._segmentos else None
            ok = ok_ui and seg is not None and seg["id"] is not None
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"ui={ok_ui} seg={seg}"


def test_06():
    """Orden inverso normaliza A/B (40 y 20 → 20→40)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            x_40 = ancho * 0.4
            x_20 = ancho * 0.2
            _press(franja, x_40)
            _esperar(lambda: tarjeta._extremo_segmento is not None)
            _press(franja, x_20)
            _esperar(lambda: len(tarjeta._segmentos) >= 1)
            seg = tarjeta._segmentos[0]
            esperado_inicio = 20.0
            esperado_fin = 40.0
            ok = (
                abs(seg["inicio"] - esperado_inicio) < 1.0
                and abs(seg["fin"] - esperado_fin) < 1.0
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"seg={seg}"


def test_07():
    """A == B no persiste segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _press(franja, ancho * 0.5)
            _esperar(lambda: tarjeta._extremo_segmento is not None)
            _press(franja, ancho * 0.5)
            _drenar_segmentos(ventana)
            ok = tarjeta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"segmentos={tarjeta._segmentos}"


def test_08():
    """Desactivar modo cancela el A pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            _press(franja, franja.width() * 0.5)
            _esperar(lambda: tarjeta._extremo_segmento is not None)
            tarjeta._boton_segmento.setChecked(False)
            ok = (
                tarjeta._extremo_segmento is None
                and tarjeta._franja.inicio_segmento_pendiente() is None
                and not tarjeta._franja.modo_crear_segmento()
                and tarjeta._segmentos == []
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"a={tarjeta._extremo_segmento} modo={tarjeta._franja.modo_crear_segmento()}"


def test_09():
    """Colapsar cancela el A pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            _press(franja, franja.width() * 0.5)
            _esperar(lambda: tarjeta._extremo_segmento is not None)
            tarjeta.colapsar()
            ok = tarjeta._extremo_segmento is None and tarjeta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"a={tarjeta._extremo_segmento}"


def test_10():
    """Cambiar de tarjeta cancela el A pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            ta = dict(ventana.tarjetas)["a.mp4"]
            tb = dict(ventana.tarjetas)["b.mp4"]
            _expandir(ta)
            _activar_modo_segmento(ta)
            _press(ta._franja, ta._franja.width() * 0.5)
            _esperar(lambda: ta._extremo_segmento is not None)
            _expandir(tb)
            ok = ta._extremo_segmento is None and ta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"a={ta._extremo_segmento}"


def test_11():
    """La banda recibe los segmentos cargados desde SQLite."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            s1 = guardar_segmento(id_a, 10.0, 20.0, ruta_db)
            s2 = guardar_segmento(id_a, 30.0, 40.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and len(tarjeta._segmentos) == 2,
                    timeout_ms=15000,
                )
                franja = tarjeta._franja
                bandas = franja.segmentos()
                ok = (
                    len(bandas) == 2
                    and sorted(b["id"] for b in bandas) == sorted([s1[0], s2[0]])
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"bandas={bandas}"
        finally:
            temp.cleanup()


def test_12():
    """La banda representa inicio/fin correctamente."""
    franja = FranjaExploracion()
    franja.set_duracion(100.0)
    franja.resize(400, 80)
    franja.set_segmentos([{"id": 1, "inicio": 10.0, "fin": 40.0}])
    bandas = franja.segmentos()
    ok = len(bandas) == 1 and bandas[0]["inicio"] == 10.0 and bandas[0]["fin"] == 40.0
    franja.set_segmentos([])
    ok = ok and franja.segmentos() == []
    return ok, f"bandas={bandas}"


def test_13():
    """No se crean widgets por segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            hijos_antes = len(franja.findChildren(visor_videos.MiniaturaMarcador))
            _crear_segmento_ui(ventana, tarjeta, franja.width() * 0.2, franja.width() * 0.6)
            hijos_despues = len(franja.findChildren(visor_videos.MiniaturaMarcador))
            ok = hijos_antes == hijos_despues and len(tarjeta._segmentos) == 1
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"hijos={hijos_antes}->{hijos_despues}"


def test_14():
    """El segmento se guarda asíncronamente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(lambda: tarjeta._segmentos_cargados, timeout_ms=15000)
                _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
                persistidos = listar_segmentos(id_a, ruta_db)
                ok = len(persistidos) == 1
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"persistidos={persistidos}"
        finally:
            temp.cleanup()


def test_15():
    """El resultado `(id, inicio, fin)` se incorpora al registro local."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
            seg = tarjeta._segmentos[0]
            ok = (
                isinstance(seg["id"], int)
                and seg["id"] > 0
                and seg["inicio"] < seg["fin"]
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"seg={seg}"


def test_16():
    """Eliminar un segmento se persiste asíncronamente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            persistidos = None
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
                seg = tarjeta._segmentos[0]
                tarjeta._al_segmento_eliminar_solicitado(seg)
                _drenar_segmentos(ventana)
                persistidos = listar_segmentos(id_a, ruta_db)
                ok = (
                    tarjeta._segmentos == []
                    and persistidos == []
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"persistidos={persistidos}"
        finally:
            temp.cleanup()


def test_17():
    """Eliminar solo el ID objetivo (con duplicados)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _esperar(lambda: tarjeta._segmentos_cargados, timeout_ms=15000)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
            seg1 = tarjeta._segmentos[0]
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5, objetivo=2)
            seg2 = tarjeta._segmentos[1]
            ids = {s["id"] for s in tarjeta._segmentos}
            tarjeta._al_segmento_eliminar_solicitado(seg1)
            _drenar_segmentos(ventana)
            ok = (
                len(ids) == 2
                and len(tarjeta._segmentos) == 1
                and tarjeta._segmentos[0]["id"] == seg2["id"]
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"restante={[s['id'] for s in tarjeta._segmentos]}"


def test_18():
    """Duplicados soportados (dos segmentos idénticos, IDs distintos)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
            s1 = dict(tarjeta._segmentos[0])
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5, objetivo=2)
            s2 = dict(tarjeta._segmentos[1])
            ok = (
                len(tarjeta._segmentos) == 2
                and s1["inicio"] == s2["inicio"]
                and s1["fin"] == s2["fin"]
                and s1["id"] != s2["id"]
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"ids={s1['id']},{s2['id']}"


def test_19():
    """Solapamientos soportados (10→30 y 20→40)."""
    franja = FranjaExploracion()
    franja.set_duracion(100.0)
    franja.resize(400, 80)
    franja.set_segmentos(
        [
            {"id": 1, "inicio": 10.0, "fin": 30.0},
            {"id": 2, "inicio": 20.0, "fin": 40.0},
        ]
    )
    # x=25 s (ancho 400, duracion 100 → 100px) cae en ambos
    x = 100.0
    seg = franja._segmento_en_posicion(x)
    ok = len(franja.segmentos()) == 2
    # el más corto (10→30 tiene 20 de span; 20→40 tiene 20; empate → id mayor)
    ok = ok and seg is not None and seg["id"] == 2
    # x=15 s cae solo en 10→30
    seg15 = franja._segmento_en_posicion(60.0)
    ok = ok and seg15 is not None and seg15["id"] == 1
    return ok, f"seg_25={seg} seg_15={seg15}"


def test_20():
    """Clic derecho sobre un marcador sigue eliminando el marcador."""
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
            ok = ok_marcador and tarjeta._marcadores == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={len(tarjeta._marcadores)}"


def test_21():
    """Clic derecho sobre una banda elimina el segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.8)
            ok_creado = len(tarjeta._segmentos) == 1
            franja = tarjeta._franja
            ancho = franja.width()
            _press_derecho(franja, ancho * 0.5)
            _drenar_segmentos(ventana)
            ok = ok_creado and tarjeta._segmentos == []
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"segmentos={len(tarjeta._segmentos)}"


def test_22():
    """Clic derecho no elimina marcador y segmento juntos (marcador tiene prioridad)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            _press(franja, ancho * 0.5)
            _drenar_marcadores(ventana)
            # segmento que abarca el mismo instante (mismo punto central)
            tarjeta._modo_crear_segmento = True
            tarjeta._al_extremo_segmento_solicitado(ancho * 0.3 / ancho * 100.0)
            tarjeta._al_extremo_segmento_solicitado(ancho * 0.7 / ancho * 100.0)
            tarjeta._modo_crear_segmento = False
            _drenar_segmentos(ventana)
            ok_ambos = len(tarjeta._marcadores) == 1 and len(tarjeta._segmentos) == 1
            # clic derecho exactamente sobre la marca del marcador
            _press_derecho(franja, ancho * 0.5)
            _drenar_marcadores(ventana)
            ok = ok_ambos and tarjeta._marcadores == [] and len(tarjeta._segmentos) == 1
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"marcadores={len(tarjeta._marcadores)} segmentos={len(tarjeta._segmentos)}"


def test_23():
    """Alta durante carga: el segmento creado no desaparece con el snapshot."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        original = tv.listar_segmentos
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            # forzar carga lenta
            def _lento(*args, **kwargs):
                time.sleep(0.5)
                return original(*args, **kwargs)

            tv.listar_segmentos = _lento
            try:
                tarjeta.colapsar()
                tarjeta._segmentos_cargados = False
                tarjeta._segmentos = []
                tarjeta.expandir()
                _activar_modo_segmento(tarjeta)
                # crear un segmento local mientras la carga está en vuelo
                _press(tarjeta._franja, tarjeta._franja.width() * 0.2)
                _esperar(lambda: tarjeta._extremo_segmento is not None)
                _press(tarjeta._franja, tarjeta._franja.width() * 0.6)
                _esperar(lambda: len(tarjeta._segmentos) == 1)
            finally:
                tv.listar_segmentos = original
            _drenar_segmentos(ventana)
            ok = len(tarjeta._segmentos) == 1
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"segmentos={len(tarjeta._segmentos)}"


def test_24():
    """Baja durante carga: el segmento eliminado no reaparece con el snapshot."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            original = tv.listar_segmentos
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(lambda: tarjeta._segmentos_cargados, timeout_ms=15000)

                def _lento(*args, **kwargs):
                    time.sleep(0.6)
                    return original(*args, **kwargs)

                tv.listar_segmentos = _lento
                try:
                    tarjeta.colapsar()
                    tarjeta._segmentos_cargados = False
                    tarjeta._segmentos = []
                    tarjeta.expandir()
                    _activar_modo_segmento(tarjeta)
                    # crear localmente y eliminar durante la carga
                    _press(tarjeta._franja, tarjeta._franja.width() * 0.2)
                    _esperar(lambda: tarjeta._extremo_segmento is not None)
                    _press(tarjeta._franja, tarjeta._franja.width() * 0.6)
                    _esperar(lambda: len(tarjeta._segmentos) == 1)
                    seg = tarjeta._segmentos[0]
                    tarjeta._al_segmento_eliminar_solicitado(seg)
                finally:
                    tv.listar_segmentos = original
                _drenar_segmentos(ventana)
                db = listar_segmentos(id_a, ruta_db)
                ok = (
                    tarjeta._segmentos == []
                    and db == []
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"ram={len(tarjeta._segmentos)} db={db}"
        finally:
            temp.cleanup()


def test_25():
    """Reexpansión conserva el snapshot en RAM."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
            snapshot = list(tarjeta._segmentos)
            tarjeta.colapsar()
            tarjeta.expandir()
            _esperar(lambda: tarjeta._franja.width() > 0)
            ok = (
                tarjeta._segmentos == snapshot
                and len(tarjeta._franja.segmentos()) == len(snapshot)
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"n={len(tarjeta._segmentos)}"


def test_26():
    """Reinicio: el segmento vuelve desde SQLite en una ventana nueva."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana1 = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana1.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _crear_segmento_ui(ventana1, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.5)
                persistidos = listar_segmentos(id_a, ruta_db)
            finally:
                ventana1.close()
                _limpiar(ventana1)
            ventana2 = _abrir_ventana(ruta_db)
            try:
                tarjeta2 = dict(ventana2.tarjetas)["a.mp4"]
                _expandir(tarjeta2)
                _esperar(
                    lambda: tarjeta2._segmentos_cargados
                    and len(tarjeta2._segmentos) == 1,
                    timeout_ms=15000,
                )
                cargados = [s["id"] for s in tarjeta2._segmentos]
                ok = len(persistidos) == 1 and cargados == [persistidos[0][0]]
            finally:
                ventana2.close()
                _limpiar(ventana2)
                temp.cleanup()
            return ok, f"persistidos={persistidos} cargados={cargados}"
        finally:
            temp.cleanup()


def test_27():
    """Segmentos y marcadores coexisten en la misma tarjeta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _crear_segmento_ui(ventana, tarjeta, tarjeta._franja.width() * 0.2, tarjeta._franja.width() * 0.6)
            # modo normal para el marcador
            tarjeta._boton_segmento.setChecked(False)
            _press(tarjeta._franja, tarjeta._franja.width() * 0.8)
            _drenar_marcadores(ventana)
            ok = len(tarjeta._segmentos) == 1 and len(tarjeta._marcadores) == 1
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"segmentos={len(tarjeta._segmentos)} marcadores={len(tarjeta._marcadores)}"


def test_28():
    """Doble clic de B5.3 sigue reproduciendo temporalmente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = (
                lambda r, n, i, v: capturas.append(i)
            )
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                _enviar(franja, QEvent.MouseButtonPress, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonDblClick, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
                _esperar(lambda: len(capturas) >= 1)
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
            ok = len(capturas) == 1 and abs(capturas[0] - 50.0) < 1.0
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas}"


def test_29():
    """Doble clic en modo segmento no crea segmento (solo reproduce)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        capturas = []
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            original_reproducir = visor_videos.reproducir_desde_instante
            original_ruta = visor_videos.ruta_video_existente
            original_localizar = visor_videos.localizar_vlc
            visor_videos.reproducir_desde_instante = (
                lambda r, n, i, v: capturas.append(i)
            )
            visor_videos.ruta_video_existente = lambda c, n: "C:\\videos\\" + n
            visor_videos.localizar_vlc = lambda: "C:\\vlc\\vlc.exe"
            try:
                _enviar(franja, QEvent.MouseButtonPress, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonDblClick, ancho * 0.5, Qt.LeftButton)
                _enviar(franja, QEvent.MouseButtonRelease, ancho * 0.5, Qt.LeftButton)
                _esperar(lambda: len(capturas) >= 1)
                _drenar_segmentos(ventana)
            finally:
                visor_videos.reproducir_desde_instante = original_reproducir
                visor_videos.ruta_video_existente = original_ruta
                visor_videos.localizar_vlc = original_localizar
            ok = (
                capturas == [50.0]
                and tarjeta._segmentos == []
                and tarjeta._extremo_segmento is None
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return ok, f"capturas={capturas} segmentos={len(tarjeta._segmentos)}"


def test_30():
    """Video A/B no mezclan segmentos."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 9.0, 10.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                _expandir(ta)
                _esperar(
                    lambda: ta._segmentos_cargados and len(ta._segmentos) == 1,
                    timeout_ms=15000,
                )
                ok_a = [s["inicio"] for s in ta._segmentos] == [1.0]
                _expandir(tb)
                _esperar(
                    lambda: tb._segmentos_cargados and len(tb._segmentos) == 1,
                    timeout_ms=15000,
                )
                ok_b = [s["inicio"] for s in tb._segmentos] == [9.0]
                ok = ok_a and ok_b
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"a={[s['inicio'] for s in ta._segmentos]} b={[s['inicio'] for s in tb._segmentos]}"
        finally:
            temp.cleanup()


def test_31():
    """La UI no accede a SQLite directamente."""
    codigo = inspect.getsource(Tarjeta) + inspect.getsource(VisorVideos)
    ok = (
        "sqlite3.connect" not in codigo
        and "conectar_bd(" not in codigo
        and "conn.execute" not in codigo
    )
    return ok, f"sin_sqlite={ok}"


def test_32():
    """La franja no conoce SQLite, tareas ni VLC."""
    codigo = inspect.getsource(FranjaExploracion)
    ok = (
        "sqlite3" not in codigo
        and "escanear_videos" not in codigo
        and "tareas" not in codigo
        and "playlist_vlc" not in codigo
        and "subprocess" not in codigo
        and "Popen" not in codigo
    )
    return ok, f"franja_aislada={ok}"


def test_33():
    """Sin FFmpeg/FFprobe/pixmaps nuevos al operar segmentos."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        llamadas = {"ffprobe": 0, "ffmpeg": 0}
        original_probe = escanear_mod.obtener_datos_ffprobe
        original_ffmpeg = escanear_mod.ffmpeg_disponible

        def _contar_probe(*a, **k):
            llamadas["ffprobe"] += 1
            return original_probe(*a, **k)

        def _contar_ffmpeg(*a, **k):
            llamadas["ffmpeg"] += 1
            return original_ffmpeg(*a, **k)

        escanear_mod.obtener_datos_ffprobe = _contar_probe
        escanear_mod.ffmpeg_disponible = _contar_ffmpeg
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            tarjeta._modo_crear_segmento = True
            tarjeta._al_extremo_segmento_solicitado(franja.width() * 0.2 / franja.width() * 100.0)
            tarjeta._al_extremo_segmento_solicitado(franja.width() * 0.6 / franja.width() * 100.0)
            tarjeta._modo_crear_segmento = False
            _drenar_segmentos(ventana)
            densos_antes = len(tarjeta._previews_densos)
        finally:
            escanear_mod.obtener_datos_ffprobe = original_probe
            escanear_mod.ffmpeg_disponible = original_ffmpeg
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        ok = (
            llamadas["ffprobe"] == 0
            and llamadas["ffmpeg"] == 0
            and len(tarjeta._segmentos) == 1
            and densos_antes == 0
        )
        return ok, f"llamadas={llamadas}"


def test_34():
    """Concurrencia: guardar marcador mientras se guarda segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_v = _video_id(ruta_db, "a.mp4")
            errores = []
            with _repos_lentos():
                g1 = GestorTareas()
                g2 = GestorTareas()
                _correr_tarea(g1, tv.TareaGuardarMarcador(id_v, 1.0, ruta_db), errores)
                _correr_tarea(g2, tv.TareaGuardarSegmento(id_v, 1.0, 2.0, ruta_db), errores)
                _esperar_gestores([g1, g2])
                g1.cerrar()
                g2.cerrar()
            ok = (
                not errores
                and len(listar_marcadores(id_v, ruta_db)) == 1
                and len(listar_segmentos(id_v, ruta_db)) == 1
            )
            temp.cleanup()
            return ok, f"errores={errores}"
        finally:
            temp.cleanup()


def test_35():
    """Concurrencia: eliminar marcador mientras se guarda segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_v = _video_id(ruta_db, "a.mp4")
            mid = guardar_marcador(id_v, 5.0, ruta_db)
            errores = []
            with _repos_lentos():
                g1 = GestorTareas()
                g2 = GestorTareas()
                _correr_tarea(g1, tv.TareaEliminarMarcador(mid, ruta_db), errores)
                _correr_tarea(g2, tv.TareaGuardarSegmento(id_v, 3.0, 4.0, ruta_db), errores)
                _esperar_gestores([g1, g2])
                g1.cerrar()
                g2.cerrar()
            ok = (
                not errores
                and listar_marcadores(id_v, ruta_db) == []
                and len(listar_segmentos(id_v, ruta_db)) == 1
            )
            temp.cleanup()
            return ok, f"errores={errores}"
        finally:
            temp.cleanup()


def test_36():
    """Concurrencia: guardar marcador mientras se elimina segmento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_v = _video_id(ruta_db, "a.mp4")
            sid = guardar_segmento(id_v, 3.0, 4.0, ruta_db)
            errores = []
            with _repos_lentos():
                g1 = GestorTareas()
                g2 = GestorTareas()
                _correr_tarea(g1, tv.TareaGuardarMarcador(id_v, 9.0, ruta_db), errores)
                _correr_tarea(g2, tv.TareaEliminarSegmento(sid[0], ruta_db), errores)
                _esperar_gestores([g1, g2])
                g1.cerrar()
                g2.cerrar()
            ok = (
                not errores
                and len(listar_marcadores(id_v, ruta_db)) == 1
                and listar_segmentos(id_v, ruta_db) == []
            )
            temp.cleanup()
            return ok, f"errores={errores}"
        finally:
            temp.cleanup()


def test_37():
    """Ráfaga de escrituras alternadas sin lock ni pérdidas."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_v = _video_id(ruta_db, "a.mp4")
            errores = []
            with _repos_lentos(0.04):
                for i in range(12):
                    g1 = GestorTareas()
                    g2 = GestorTareas()
                    _correr_tarea(
                        g1, tv.TareaGuardarMarcador(id_v, float(i), ruta_db), errores
                    )
                    _correr_tarea(
                        g2,
                        tv.TareaGuardarSegmento(id_v, float(i), float(i) + 1.0, ruta_db),
                        errores,
                    )
                    _esperar_gestores([g1, g2])
                    g1.cerrar()
                    g2.cerrar()
            marcadores = listar_marcadores(id_v, ruta_db)
            segmentos = listar_segmentos(id_v, ruta_db)
            ok = (
                not errores
                and len(marcadores) == 12
                and len(segmentos) == 12
            )
            temp.cleanup()
            return ok, f"errores={errores} m={len(marcadores)} s={len(segmentos)}"
        finally:
            temp.cleanup()


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
        test_30,
        test_31,
        test_32,
        test_33,
        test_34,
        test_35,
        test_36,
        test_37,
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
