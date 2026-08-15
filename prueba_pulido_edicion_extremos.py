"""Pruebas del Pulido Beta 5 #4 — edición de extremos A/B de segmentos.

Cubre:
- unitarias del repositorio `actualizar_segmento` (update por id, id
  inexistente, normalización, aislamiento por id) y de `TareaActualizarSegmento`;
- 22 casos de UI sobre la aplicación real:
  1. editar A hacia derecha; 2. editar B hacia derecha; 3. A cruza B;
  4. B cruza A; 5. jitter < umbral no edita; 6. clic simple sobre extremo no
  edita ni crea; 7. release fuera clamp; 8. extremos cercanos determinista;
  9. superposición; 10. segmento corto; 11. fuera de modo Segmento no edita;
  12. drag fuera de extremo sigue creando; 13. doble clic cerca de extremo
  solo reproduce; 14. clic derecho sigue abriendo menú; 15. A pendiente +
  edición no crea segmento nuevo; 16. conserva id; 17. persiste en SQLite;
  18. error revierte visualmente; 19. resultado stale no contamina otra
  tarjeta; 20. cierre con update pendiente sin errores; 21. Pulido #3 sigue
  funcionando; 22. marcador/MiniaturaMarcador sin regresión.
"""

import math
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QEventLoop, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPointingDevice, QPixmap
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    actualizar_segmento,
    conectar_bd,
    guardar_segmento,
    guardar_videos,
    listar_segmentos,
)
from exploracion_temporal import tiempo_a_posicion
from scrubber import _TOLERANCIA_EXTREMO_PX
from visor_videos import VisorVideos

_CONFIG = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "configuracion.json")
_MINI = tempfile.TemporaryDirectory()
_MINI_TMP = [None]


def _miniaturas_temporales():
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: _MINI.name
    visor_videos.ruta_carpeta_miniaturas = lambda: _MINI.name
    _MINI_TMP[0] = (original_escaneo, original_visor)


def _restaurar_miniaturas():
    if _MINI_TMP[0]:
        escanear_mod.ruta_carpeta_miniaturas, visor_videos.ruta_carpeta_miniaturas = _MINI_TMP[0]
        _MINI_TMP[0] = None


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
    for fila in escanear_mod.listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=12000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
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


def _drenar_segmentos(ventana, timeout_ms=15000):
    return _esperar(
        lambda v=ventana: not v.gestor_segmentos.activo
        and not v._cola_segmentos,
        timeout_ms=timeout_ms,
    )


def _enviar(widget, tipo, x, boton=Qt.LeftButton):
    evento = QMouseEvent(
        tipo,
        QPointF(float(x), float(widget.height() // 2)),
        boton,
        boton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


def _press(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x)


def _release(widget, x):
    _enviar(widget, QEvent.MouseButtonRelease, x)


def _move(widget, x):
    _enviar(widget, QEvent.MouseMove, x)


def _doble(widget, x):
    _enviar(widget, QEvent.MouseButtonDblClick, x)


def _press_derecho(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.RightButton)


def _doble_clic_real(widget, x):
    _press(widget, x)
    _release(widget, x)
    _doble(widget, x)
    _release(widget, x)
    QApplication.processEvents()


def _drag_extremo(widget, x1, x2, pasos=8):
    _press(widget, x1)
    QApplication.processEvents()
    for i in range(1, pasos + 1):
        _move(widget, x1 + (x2 - x1) * i / pasos)
        QApplication.processEvents()
    _release(widget, x2)
    QApplication.processEvents()


def _posicion_extremo(franja, instante):
    return tiempo_a_posicion(instante, franja.width(), franja.duracion())


def _abrir_ventana_con_segmentos(nombre, segmentos, nombres_extra=None):
    """Ventana real con segmentos pre-persistidos para el video `nombre`."""
    todos = [nombre] + (nombres_extra or [])
    temp, ruta_db = _crear_bd_con_videos(todos)
    id_video = _video_id(ruta_db, nombre)
    for inicio, fin in segmentos:
        guardar_segmento(id_video, inicio, fin, ruta_db)
    ventana = VisorVideos(ruta_db=ruta_db)
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    ventana.resize(1000, 700)
    ventana.show()
    _procesar(80)
    QApplication.processEvents()
    tarjeta = dict(ventana.tarjetas)[nombre]
    tarjeta.expandir()
    _esperar(lambda: tarjeta._franja.width() > 0)
    _esperar(
        lambda: tarjeta._segmentos_cargados
        and len(tarjeta._segmentos) == len(segmentos),
        timeout_ms=15000,
    )
    _procesar(80)
    QApplication.processEvents()
    return ventana, tarjeta, tarjeta._franja, temp, ruta_db, id_video


# --------------------------------------------------------------------------
# Unitarias del repositorio / tarea
# --------------------------------------------------------------------------

def test_01():
    """`actualizar_segmento` actualiza y conserva el id."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        sid = guardar_segmento(id_video, 20.0, 50.0, ruta_db)
        resultado = actualizar_segmento(sid[0], 30.0, 60.0, ruta_db)
        filas = listar_segmentos(id_video, ruta_db)
        ok = (
            resultado == (sid[0], 30.0, 60.0)
            and filas == [(sid[0], 30.0, 60.0)]
            and len(filas) == 1
        )
    finally:
        temp.cleanup()
    return ok, f"resultado={resultado} filas={filas}"


def test_02():
    """`actualizar_segmento` con id inexistente devuelve None."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        resultado = actualizar_segmento(99999, 10.0, 20.0, ruta_db)
        ok = resultado is None
    finally:
        temp.cleanup()
    return ok, f"resultado={resultado}"


def test_03():
    """`actualizar_segmento` rechaza fin <= inicio (normalización)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        sid = guardar_segmento(id_video, 20.0, 50.0, ruta_db)
        rechazo = False
        try:
            actualizar_segmento(sid[0], 60.0, 40.0, ruta_db)
        except ValueError:
            rechazo = True
        filas = listar_segmentos(id_video, ruta_db)
        ok = rechazo and filas == [(sid[0], 20.0, 50.0)]
    finally:
        temp.cleanup()
    return ok, f"rechazo={rechazo} filas={filas}"


def test_04():
    """`actualizar_segmento` aísla por id (no afecta otros)."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s1 = guardar_segmento(id_video, 10.0, 20.0, ruta_db)
        s2 = guardar_segmento(id_video, 30.0, 40.0, ruta_db)
        actualizar_segmento(s1[0], 5.0, 25.0, ruta_db)
        filas = listar_segmentos(id_video, ruta_db)
        ok = filas == [(s1[0], 5.0, 25.0), (s2[0], 30.0, 40.0)]
    finally:
        temp.cleanup()
    return ok, f"filas={filas}"


def test_05():
    """`TareaActualizarSegmento` ejecuta en el gestor y devuelve el contrato."""
    from tareas import GestorTareas

    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        sid = guardar_segmento(id_video, 20.0, 50.0, ruta_db)
        gestor = GestorTareas()
        resultados = []
        errores = []
        gestor.tarea_resultado.connect(resultados.append)
        gestor.tarea_error.connect(lambda m: errores.append(m))
        gestor.iniciar(tv.TareaActualizarSegmento(sid[0], 25.0, 55.0, ruta_db))
        _esperar(lambda: gestor.hilo is None, timeout_ms=15000)
        filas = listar_segmentos(id_video, ruta_db)
        ok = (
            resultados == [(sid[0], 25.0, 55.0)]
            and not errores
            and filas == [(sid[0], 25.0, 55.0)]
        )
        gestor.cerrar()
    finally:
        temp.cleanup()
    return ok, f"resultados={resultados} errores={errores} filas={filas}"


# --------------------------------------------------------------------------
# Casos de UI
# --------------------------------------------------------------------------

def test_06():
    """Editar A hacia la derecha (20→50 a 30→50)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        _drag_extremo(franja, x_a, _posicion_extremo(franja, 30.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 30.0) < 1e-6
            and abs(seg["fin"] - 50.0) < 1e-6
            and seg["id"] is not None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']}) id={seg['id']}"


def test_07():
    """Editar B hacia la derecha (20→50 a 20→60)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 60.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 20.0) < 1e-6
            and abs(seg["fin"] - 60.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_08():
    """A cruza B: 20→50, mover A a 70 → resultado 50→70."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        _drag_extremo(franja, x_a, _posicion_extremo(franja, 70.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 50.0) < 1e-6
            and abs(seg["fin"] - 70.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_09():
    """B cruza A: 20→50, mover B a 10 → resultado 10→20."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 10.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 10.0) < 1e-6
            and abs(seg["fin"] - 20.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_10():
    """Jitter < startDragDistance sobre extremo: no edita ni crea ni deja A."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        dx = max(1, QApplication.startDragDistance() - 1)
        _press(franja, x_a)
        _move(franja, x_a + dx)
        _release(franja, x_a + dx)
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 20.0) < 1e-6
            and abs(seg["fin"] - 50.0) < 1e-6
            and len(tarjeta._segmentos) == 1
            and tarjeta._extremo_segmento is None
            and franja._edicion_activa is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_11():
    """Clic simple sobre extremo: no edita ni crea ni deja A."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        _press(franja, x_a)
        _release(franja, x_a)
        _procesar(QApplication.doubleClickInterval() + 300)
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 20.0) < 1e-6
            and len(tarjeta._segmentos) == 1
            and tarjeta._extremo_segmento is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_12():
    """Release fuera: clamp a [0, duracion]."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        _drag_extremo(franja, x_a, franja.width() + 200)
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            seg["fin"] <= 100.0 + 1e-6
            and seg["inicio"] < seg["fin"]
            and franja._edicion_activa is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_13():
    """Extremos compartidos: elección determinista (más corto, luego id)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0), (30.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        # ambos comparten el extremo 50; el más corto (30→50) gana
        x = _posicion_extremo(franja, 50.0)
        seg, lado = franja._extremo_en_posicion(x)
        ok = (
            seg is not None
            and abs(seg["inicio"] - 30.0) < 1e-6
            and abs(seg["fin"] - 50.0) < 1e-6
            and lado == "fin"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']}) lado={lado}"


def test_14():
    """Segmentos superpuestos: editar un extremo no altera el otro segmento."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0), (40.0, 90.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 20.0)
        _drag_extremo(franja, x_a, _posicion_extremo(franja, 30.0))
        _drenar_segmentos(ventana)
        ordenados = sorted(tarjeta._segmentos, key=lambda s: s["id"])
        ok = (
            len(ordenados) == 2
            and abs(ordenados[0]["inicio"] - 30.0) < 1e-6
            and abs(ordenados[0]["fin"] - 50.0) < 1e-6
            and abs(ordenados[1]["inicio"] - 40.0) < 1e-6
            and abs(ordenados[1]["fin"] - 90.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"segs={[(s['inicio'], s['fin']) for s in ordenados]}"


def test_15():
    """Segmento corto: hit testing usable sin ambigüedad absurda."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(40.0, 42.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_a = _posicion_extremo(franja, 40.0)
        _drag_extremo(franja, x_a, _posicion_extremo(franja, 45.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 42.0) < 1e-6
            and abs(seg["fin"] - 45.0) < 1e-6
            and len(tarjeta._segmentos) == 1
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_16():
    """Fuera de modo Segmento: el drag sobre extremo no edita."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        x_a = _posicion_extremo(franja, 20.0)
        _drag_extremo(franja, x_a, _posicion_extremo(franja, 30.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 20.0) < 1e-6
            and abs(seg["fin"] - 50.0) < 1e-6
            and franja._edicion_activa is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']})"


def test_17():
    """Drag fuera de extremos sigue creando segmentos (Pulido #3)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _drag_extremo(franja, franja.width() * 0.6, franja.width() * 0.8)
        _drenar_segmentos(ventana)
        ok = (
            len(tarjeta._segmentos) == 2
            and abs(tarjeta._segmentos[-1]["inicio"] - 60.0) < 1e-6
            and abs(tarjeta._segmentos[-1]["fin"] - 80.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"segs={[(s['inicio'], s['fin']) for s in tarjeta._segmentos]}"


def test_18():
    """Doble clic cerca de extremo: solo reproduce, sin edición ni creación."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        reproducciones = []
        franja.reproduccion_solicitada.connect(reproducciones.append)
        x_a = _posicion_extremo(franja, 20.0)
        _doble_clic_real(franja, x_a)
        _procesar(QApplication.doubleClickInterval() + 300)
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            len(reproducciones) == 1
            and abs(seg["inicio"] - 20.0) < 1e-6
            and len(tarjeta._segmentos) == 1
            and tarjeta._extremo_segmento is None
            and franja._edicion_activa is None
            and franja._edicion_candidato is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"reps={len(reproducciones)} seg=({seg['inicio']}, {seg['fin']})"


def test_19():
    """Clic derecho sobre segmento sigue abriendo el menú."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        tarjeta._menu_segmento_actual = None
        x = franja.width() * 0.35
        _press_derecho(franja, x)
        _esperar(lambda: tarjeta._menu_segmento_actual is not None)
        menu = tarjeta._menu_segmento_actual
        textos = [a.text() for a in menu.actions()]
        ok = (
            "Reproducir segmento" in textos
            and "Reproducir segmento en bucle" in textos
            and "Eliminar segmento" in textos
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"textos={textos}"


def test_20():
    """A pendiente + drag de edición: no crea segmento nuevo."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        # A pendiente en 60 (fuera del segmento, clic normal)
        _press(franja, franja.width() * 0.6)
        _release(franja, franja.width() * 0.6)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        # edición de B: 50 -> 60
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 60.0))
        _drenar_segmentos(ventana)
        ok = (
            len(tarjeta._segmentos) == 1
            and abs(tarjeta._segmentos[0]["fin"] - 60.0) < 1e-6
            and tarjeta._extremo_segmento is None
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"segs={[(s['inicio'], s['fin']) for s in tarjeta._segmentos]}"


def test_21():
    """La actualización conserva el id (UPDATE, no delete+insert)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        id_antes = tarjeta._segmentos[0]["id"]
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 70.0))
        _drenar_segmentos(ventana)
        ok = (
            tarjeta._segmentos[0]["id"] == id_antes
            and len(tarjeta._segmentos) == 1
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"id_antes={id_antes} id_despues={tarjeta._segmentos[0]['id']}"


def test_22():
    """La edición persiste en SQLite con el mismo id."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        id_seg = tarjeta._segmentos[0]["id"]
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 65.0))
        _drenar_segmentos(ventana)
        filas = listar_segmentos(id_v, ruta_db)
        ok = (
            filas == [(id_seg, 20.0, 65.0)]
            and len(filas) == 1
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"sqlite={filas}"


def test_23():
    """Error de actualización revierte el intervalo optimista."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    original = tv.actualizar_segmento

    def _fallar(*a, **k):
        raise OSError("fallo simulado")

    tv.actualizar_segmento = _fallar
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 65.0))
        _drenar_segmentos(ventana)
        seg = tarjeta._segmentos[0]
        ok = (
            abs(seg["inicio"] - 20.0) < 1e-6
            and abs(seg["fin"] - 50.0) < 1e-6
            and ventana.mensaje_carpeta.text() != ""
        )
    finally:
        tv.actualizar_segmento = original
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"seg=({seg['inicio']}, {seg['fin']}) mensaje={ventana.mensaje_carpeta.text()!r}"


def test_24():
    """Resultado stale no contamina otra tarjeta/video."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)], nombres_extra=["b.mp4"]
    )
    try:
        tarjeta_b = dict(ventana.tarjetas)["b.mp4"]
        tarjeta_b.expandir()
        _esperar(lambda: tarjeta_b._franja.width() > 0)
        tarjeta._boton_segmento.setChecked(True)
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 65.0))
        _drenar_segmentos(ventana)
        ok = (
            tarjeta_b._segmentos == []
            and tarjeta._segmentos[0]["fin"] == 65.0
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"b_segs={len(tarjeta_b._segmentos)} a_fin={tarjeta._segmentos[0]['fin']}"


def test_25():
    """Cierre con update pendiente no genera errores."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    qt_mensajes = []
    from PySide6.QtCore import qInstallMessageHandler

    def _hook(tipo, contexto, texto):
        qt_mensajes.append(str(texto))

    qInstallMessageHandler(_hook)
    try:
        tarjeta._boton_segmento.setChecked(True)
        x_b = _posicion_extremo(franja, 50.0)
        _drag_extremo(franja, x_b, _posicion_extremo(franja, 65.0))
        # cerrar inmediatamente, sin drenar
        ventana.close()
        _limpiar(ventana)
        qInstallMessageHandler(None)
        errores_qt = [m for m in qt_mensajes if "QThread" in m or "Destroyed" in m]
        ok = not errores_qt
    finally:
        qInstallMessageHandler(None)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"qt_warnings={len(errores_qt)}"


def test_26():
    """Pulido #3 intacto: clic A+B crea segmento (sin editar extremos)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        # clic en 70 (no extremo) y 90 (no extremo) -> crea A+B
        _press(franja, franja.width() * 0.7)
        _release(franja, franja.width() * 0.7)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _press(franja, franja.width() * 0.9)
        _release(franja, franja.width() * 0.9)
        _esperar(lambda: len(tarjeta._segmentos) == 2)
        _drenar_segmentos(ventana)
        nuevo = tarjeta._segmentos[-1]
        ok = (
            len(tarjeta._segmentos) == 2
            and abs(nuevo["inicio"] - 70.0) < 1e-6
            and abs(nuevo["fin"] - 90.0) < 1e-6
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"segs={[(s['inicio'], s['fin']) for s in tarjeta._segmentos]}"


def test_27():
    """Marcador/MiniaturaMarcador sin regresión (clic y doble clic)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 50.0)]
    )
    try:
        pixmap = QPixmap(20, 20)
        pixmap.fill(QColor(200, 200, 200))
        tarjeta._previews_exploracion = [
            {"instante": 30.0, "pixmap": pixmap, "pixmap_escalado": pixmap}
        ]
        # modo marcador (no segmento)
        _press(franja, franja.width() * 0.3)
        _release(franja, franja.width() * 0.3)
        _esperar(
            lambda: tarjeta._marcadores
            and tarjeta._marcadores[0].get("etiqueta") is not None
        )
        etiqueta = tarjeta._marcadores[0]["etiqueta"]
        reproducciones = []
        franja.reproduccion_solicitada.connect(reproducciones.append)
        _doble_clic_real(etiqueta, etiqueta.width() // 2)
        _procesar(QApplication.doubleClickInterval() + 200)
        ok = (
            len(tarjeta._marcadores) == 1
            and len(reproducciones) == 1
            and len(tarjeta._segmentos) == 1
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"marcadores={len(tarjeta._marcadores)} reps={len(reproducciones)}"


def test_28():
    """Cursor: fuera de modo Segmento sobre extremo -> normal (Arrow)."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        x_a = _posicion_extremo(franja, 20.0)
        _move(franja, x_a)
        QApplication.processEvents()
        ok = franja.cursor().shape() != Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_29():
    """Cursor: modo Segmento + fuera de extremo -> normal."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, franja.width() * 0.5)
        QApplication.processEvents()
        ok = franja.cursor().shape() != Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_30():
    """Cursor: sobre extremo A -> SizeHorCursor."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        ok = franja.cursor().shape() == Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_31():
    """Cursor: sobre extremo B -> SizeHorCursor."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 80.0))
        QApplication.processEvents()
        ok = franja.cursor().shape() == Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_32():
    """Cursor: salir del extremo restaura el cursor normal."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        _move(franja, franja.width() * 0.5)
        QApplication.processEvents()
        ok = franja.cursor().shape() != Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_33():
    """Cursor: desactivar Segmento estando sobre extremo -> normal."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        tarjeta._boton_segmento.setChecked(False)
        QApplication.processEvents()
        ok = franja.cursor().shape() != Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_34():
    """Cursor: colapsar/ocultar la franja -> sin cursor residual."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        tarjeta.colapsar()
        _procesar(80)
        QApplication.processEvents()
        ok = franja.cursor().shape() != Qt.SizeHorCursor
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, f"shape={franja.cursor().shape()}"


def test_35():
    """Hover: sobre extremo editable identifica el extremo candidato."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        h = franja._hover_extremo
        ok = (
            h is not None
            and h[1] == "inicio"
            and h[0] is tarjeta._segmentos[0]
        )
        detalle = f"hover={h is not None} lado={h[1] if h else None}"
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, detalle


def test_36():
    """Hover: fuera del extremo no hay hover de edición."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, franja.width() * 0.5)
        QApplication.processEvents()
        ok = franja._hover_extremo is None
        detalle = f"hover={franja._hover_extremo}"
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, detalle


def test_37():
    """Hover: desactivar el modo limpia el hover."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        tarjeta._boton_segmento.setChecked(False)
        QApplication.processEvents()
        ok = franja._hover_extremo is None
        detalle = f"hover={franja._hover_extremo}"
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, detalle


def test_38():
    """Hover: leave y colapsar limpian el hover."""
    _miniaturas_temporales()
    ventana, tarjeta, franja, temp, ruta_db, id_v = _abrir_ventana_con_segmentos(
        "a.mp4", [(20.0, 80.0)]
    )
    try:
        tarjeta._boton_segmento.setChecked(True)
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        from PySide6.QtCore import QEvent as _QEvent

        QApplication.sendEvent(franja, _QEvent(_QEvent.Leave))
        QApplication.processEvents()
        ok_leave = franja._hover_extremo is None
        _move(franja, _posicion_extremo(franja, 20.0))
        QApplication.processEvents()
        tarjeta.colapsar()
        _procesar(80)
        QApplication.processEvents()
        ok_colapso = franja._hover_extremo is None
        ok = ok_leave and ok_colapso
        detalle = f"leave={ok_leave} colapso={ok_colapso}"
    finally:
        ventana.close()
        _limpiar(ventana)
        _restaurar_miniaturas()
        temp.cleanup()
    return ok, detalle


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
        test_38,
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
    print(f"TOTAL={aprobadas}/38")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
