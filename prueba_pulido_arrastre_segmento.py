"""Pruebas del Pulido Beta 5 #3 — creación de segmentos por arrastre.

Cubre, sobre la aplicación real y la franja:

1. drag izquierda→derecha crea exactamente un segmento;
2. drag derecha→izquierda crea exactamente un segmento normalizado;
3. movimiento menor a `startDragDistance` sigue siendo clic normal;
4. press/release sin movimiento sigue siendo clic normal A+B;
5. doble clic no crea segmento (y reproduce);
6. fuera de modo Segmento no crea segmento;
7. banda provisional aparece durante el drag;
8. banda provisional desaparece al soltar;
9. el segmento persistente usa el flujo existente (persistencia + id);
10. no quedan estados internos de drag tras completar/cancelar;
11. marcadores cercanos siguen funcionando;
12. MiniaturaMarcador sigue reenviando press/doble clic al arrastrar;
13. Pulido #2 continúa pintando bandas persistentes.
"""

import os
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QEventLoop, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from escanear_videos import conectar_bd, guardar_videos, listar_videos
from exploracion_temporal import tiempo_a_posicion
from visor_videos import VisorVideos

_CONFIG = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "configuracion.json")

_MINI = tempfile.TemporaryDirectory()


def _miniaturas_temporales():
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: _MINI.name
    visor_videos.ruta_carpeta_miniaturas = lambda: _MINI.name


def _restaurar_miniaturas():
    pass


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


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    ventana.resize(1000, 700)
    ventana.show()
    _procesar(80)
    QApplication.processEvents()
    return ventana


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


def _drenar_marcadores(ventana, timeout_ms=15000):
    return _esperar(
        lambda v=ventana: not v.gestor_marcadores.activo
        and not v._cola_marcadores,
        timeout_ms=timeout_ms,
    )


def _enviar(widget, tipo, x, boton):
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
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.LeftButton)


def _release(widget, x):
    _enviar(widget, QEvent.MouseButtonRelease, x, Qt.LeftButton)


def _move(widget, x):
    _enviar(widget, QEvent.MouseMove, x, Qt.LeftButton)


def _doble(widget, x):
    _enviar(widget, QEvent.MouseButtonDblClick, x, Qt.LeftButton)


def _doble_clic_real(widget, x):
    _press(widget, x)
    _release(widget, x)
    _doble(widget, x)
    _release(widget, x)
    QApplication.processEvents()


def _drag(widget, x1, x2, pasos=8):
    _press(widget, x1)
    QApplication.processEvents()
    for i in range(1, pasos + 1):
        x = x1 + (x2 - x1) * i / pasos
        _move(widget, x)
        QApplication.processEvents()
    _release(widget, x2)
    QApplication.processEvents()


def _tarjeta_y_franja(ventana, nombre):
    tarjeta = dict(ventana.tarjetas)[nombre]
    tarjeta.expandir()
    _esperar(lambda: tarjeta._franja.width() > 0)
    _procesar(80)
    QApplication.processEvents()
    return tarjeta, tarjeta._franja


def _pixel_en(franja, instante):
    dpr = franja.devicePixelRatioF() or 1.0
    imagen = franja.grab().toImage()
    y_pista = 6 + franja.fontMetrics().height() + 4
    y = int((y_pista + 5) * dpr)
    x = int(tiempo_a_posicion(instante, franja.width(), franja.duracion()) * dpr)
    return imagen.pixelColor(x, y)


def _crear_ventana(nombre="v.mp4"):
    _miniaturas_temporales()
    temp, ruta_db = _crear_bd_con_videos([nombre])
    ventana = _abrir_ventana(ruta_db)
    return ventana, temp, ruta_db


def test_01():
    """Drag izquierda→derecha crea exactamente un segmento."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.2, ancho * 0.8)
        _drenar_segmentos(ventana)
        ok = len(tarjeta._segmentos) == 1
        detalle = f"segmentos={[(s['inicio'], s['fin']) for s in tarjeta._segmentos]}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_02():
    """Drag derecha→izquierda crea exactamente un segmento normalizado."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.8, ancho * 0.2)
        _drenar_segmentos(ventana)
        segs = [
            (s["inicio"], s["fin"]) for s in tarjeta._segmentos
        ]
        ok = (
            len(segs) == 1
            and segs[0][0] < segs[0][1]
        )
        detalle = f"segmentos={segs}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_03():
    """Movimiento menor a startDragDistance sigue siendo clic normal."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        x = ancho * 0.3
        dx = max(1, QApplication.startDragDistance() - 1)
        _press(franja, x)
        _move(franja, x + dx)
        _release(franja, x + dx)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _drenar_segmentos(ventana)
        ok = (
            len(tarjeta._segmentos) == 0
            and tarjeta._extremo_segmento is not None
            and franja._drag_activo is False
        )
        detalle = (
            f"segmentos={len(tarjeta._segmentos)} "
            f"a_pendiente={tarjeta._extremo_segmento} "
            f"drag_activo={franja._drag_activo}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_04():
    """Press/release sin movimiento sigue siendo clic normal A+B."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.2)
        _release(franja, ancho * 0.2)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _press(franja, ancho * 0.8)
        _release(franja, ancho * 0.8)
        _esperar(lambda: len(tarjeta._segmentos) == 1)
        _drenar_segmentos(ventana)
        ok = len(tarjeta._segmentos) == 1
        detalle = f"segmentos={len(tarjeta._segmentos)}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_05():
    """Doble clic no crea segmento y reproduce (no deja A pendiente)."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        reproducciones = []
        franja.reproduccion_solicitada.connect(reproducciones.append)
        tarjeta._boton_segmento.setChecked(True)
        _doble_clic_real(franja, ancho * 0.5)
        _drenar_segmentos(ventana)
        ok = (
            len(reproducciones) == 1
            and len(tarjeta._segmentos) == 0
            and tarjeta._extremo_segmento is None
            and franja._drag_activo is False
        )
        detalle = (
            f"reproducciones={len(reproducciones)} "
            f"segmentos={len(tarjeta._segmentos)} "
            f"a_pendiente={tarjeta._extremo_segmento}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_06():
    """Fuera de modo Segmento el drag no crea segmento."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        _drag(franja, ancho * 0.2, ancho * 0.8)
        _drenar_segmentos(ventana)
        ok = len(tarjeta._segmentos) == 0 and franja._drag_activo is False
        detalle = f"segmentos={len(tarjeta._segmentos)}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_07():
    """Banda provisional aparece durante el drag."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.2)
        _move(franja, ancho * 0.8)
        QApplication.processEvents()
        durante = _pixel_en(franja, 50.0)
        ok_durante = franja._drag_activo and durante.blue() > durante.red()
        _release(franja, ancho * 0.8)
        _drenar_segmentos(ventana)
        ok = ok_durante and len(tarjeta._segmentos) == 1
        detalle = (
            f"drag_activo={franja._drag_activo} pixel_durante={durante.name()} "
            f"segmentos={len(tarjeta._segmentos)}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_08():
    """Banda provisional desaparece al soltar."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.2, ancho * 0.8)
        _drenar_segmentos(ventana)
        ok = (
            franja._drag_activo is False
            and franja._drag_inicio is None
            and franja._drag_actual is None
            and franja._press_instante is None
            and franja._boton_presionado is False
        )
        detalle = (
            f"drag={franja._drag_activo} inicio={franja._drag_inicio} "
            f"actual={franja._drag_actual} press={franja._press_instante} "
            f"boton={franja._boton_presionado}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_09():
    """El segmento creado por drag persiste con el flujo existente (id)."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        id_video = _video_id(ruta_db, "v.mp4")
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.25, ancho * 0.6)
        _drenar_segmentos(ventana)
        persistidos = escanear_mod.listar_segmentos(id_video, ruta_db)
        ok = (
            len(tarjeta._segmentos) == 1
            and tarjeta._segmentos[0]["id"] is not None
            and len(persistidos) == 1
            and abs(persistidos[0][1] - 25.0) < 1e-6
            and abs(persistidos[0][2] - 60.0) < 1e-6
        )
        detalle = (
            f"id_ram={tarjeta._segmentos[0]['id'] if tarjeta._segmentos else None} "
            f"sqlite={persistidos}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_10():
    """No quedan estados internos de drag tras completar ni cancelar."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.1, ancho * 0.9)
        _drenar_segmentos(ventana)
        ok_completo = (
            franja._drag_activo is False
            and franja._drag_inicio is None
            and franja._press_instante is None
            and franja._boton_presionado is False
        )
        # cancelar: drag en curso y se desactiva el modo segmento
        _press(franja, ancho * 0.3)
        _move(franja, ancho * 0.7)
        QApplication.processEvents()
        estaba_drag = franja._drag_activo
        tarjeta._boton_segmento.setChecked(False)
        _release(franja, ancho * 0.7)
        ok_cancelado = (
            franja._drag_activo is False
            and franja._press_instante is None
            and franja._boton_presionado is False
        )
        ok = ok_completo and estaba_drag and ok_cancelado
        detalle = (
            f"completo={ok_completo} estaba_drag={estaba_drag} "
            f"cancelado={ok_cancelado}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_11():
    """Marcadores cercanos siguen funcionando (clic normal y reenvío)."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        _press(franja, ancho * 0.2)
        _release(franja, ancho * 0.2)
        _press(franja, ancho * 0.22)
        _release(franja, ancho * 0.22)
        _press(franja, ancho * 0.5)
        _release(franja, ancho * 0.5)
        _drenar_marcadores(ventana)
        tiempos = sorted(m["tiempo"] for m in tarjeta._marcadores)
        ok = (
            len(tarjeta._marcadores) >= 2
            and len(set(round(t, 3) for t in tiempos)) >= 2
        )
        detalle = f"marcadores={len(tarjeta._marcadores)} tiempos={[round(t,1) for t in tiempos]}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_12():
    """MiniaturaMarcador reenvía press/doble clic al arrastrar."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        # pixmap sintético para que el marcador genere su MiniaturaMarcador
        from PySide6.QtGui import QColor as _QColor, QPixmap as _QPixmap

        pixmap = _QPixmap(20, 20)
        pixmap.fill(_QColor(200, 200, 200))
        tarjeta._previews_exploracion = [
            {
                "instante": 40.0,
                "pixmap": pixmap,
                "pixmap_escalado": pixmap,
            }
        ]
        # creamos un marcador para generar su MiniaturaMarcador
        _press(franja, ancho * 0.4)
        _release(franja, ancho * 0.4)
        _drenar_marcadores(ventana)
        _esperar(
            lambda: tarjeta._marcadores
            and tarjeta._marcadores[0].get("etiqueta") is not None
        )
        etiqueta = tarjeta._marcadores[0]["etiqueta"]
        ok_miniatura = etiqueta is not None and etiqueta.isVisible()

        # drag que comienza sobre la miniatura (reenvío del press/move)
        tarjeta._boton_segmento.setChecked(True)
        x_min = etiqueta.width() // 2
        _press(etiqueta, x_min)
        _move(etiqueta, x_min)
        _move(etiqueta, etiqueta.width() * 3)
        QApplication.processEvents()
        ok_drag = franja._drag_activo
        _release(etiqueta, etiqueta.width() * 3)
        _drenar_segmentos(ventana)
        ok_segmento = len(tarjeta._segmentos) == 1

        # doble clic sobre la miniatura: reproduce sin crear segmento
        reproducciones = []
        franja.reproduccion_solicitada.connect(reproducciones.append)
        _doble_clic_real(etiqueta, etiqueta.width() // 2)
        _drenar_segmentos(ventana)
        ok_doble = (
            len(reproducciones) == 1
            and len(tarjeta._segmentos) == 1
        )
        ok = ok_miniatura and ok_drag and ok_segmento and ok_doble
        detalle = (
            f"miniatura={ok_miniatura} drag_desde_miniatura={ok_drag} "
            f"segmento={len(tarjeta._segmentos)} doble={ok_doble}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_13():
    """Pulido #2: la banda persistente creada por drag se pinta azulada."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _drag(franja, ancho * 0.2, ancho * 0.8)
        _drenar_segmentos(ventana)
        pixel = _pixel_en(franja, 50.0)
        ok = (
            len(tarjeta._segmentos) == 1
            and pixel.blue() > pixel.red()
            and pixel.red() > 33
        )
        detalle = f"pixel_banda={pixel.name()}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_14():
    """T1: A pendiente + press B + espera > doubleClickInterval sin release.

    Verifica que durante la espera NO se confirma todavía ningún segmento.
    """
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.2)
        _release(franja, ancho * 0.2)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _press(franja, ancho * 0.7)
        _procesar(QApplication.doubleClickInterval() + 400)
        durante = len(tarjeta._segmentos)
        _release(franja, ancho * 0.7)
        _drenar_segmentos(ventana)
        ok = durante == 0
        detalle = f"durante={durante}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_15():
    """T2: A pendiente + press B + espera + drag B->C + release -> 1 segmento B->C."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.2)
        _release(franja, ancho * 0.2)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _press(franja, ancho * 0.7)
        _procesar(QApplication.doubleClickInterval() + 400)
        durante = len(tarjeta._segmentos)
        _move(franja, ancho * 0.9)
        QApplication.processEvents()
        _release(franja, ancho * 0.9)
        _drenar_segmentos(ventana)
        segs = [(s["inicio"], s["fin"]) for s in tarjeta._segmentos]
        ok = (
            durante == 0
            and len(segs) == 1
            and segs[0][0] > 60.0
            and tarjeta._extremo_segmento is None
            and not franja._drag_activo
        )
        detalle = f"durante={durante} segs={segs} a_pendiente={tarjeta._extremo_segmento}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_16():
    """T3: A pendiente + press B + espera + release sin mover -> exactamente A->B."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.2)
        _release(franja, ancho * 0.2)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _press(franja, ancho * 0.7)
        _procesar(QApplication.doubleClickInterval() + 400)
        durante = len(tarjeta._segmentos)
        _release(franja, ancho * 0.7)
        _esperar(lambda: len(tarjeta._segmentos) == 1)
        _drenar_segmentos(ventana)
        segs = [(s["inicio"], s["fin"]) for s in tarjeta._segmentos]
        ok = (
            durante == 0
            and len(segs) == 1
            and abs(segs[0][0] - 20.0) < 1e-6
            and abs(segs[0][1] - 70.0) < 1e-6
            and tarjeta._extremo_segmento is None
        )
        detalle = f"durante={durante} segs={segs}"
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_17():
    """T4: press sostenido sin A pendiente -> nada durante; A pendiente tras release."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        tarjeta._boton_segmento.setChecked(True)
        _press(franja, ancho * 0.5)
        _procesar(QApplication.doubleClickInterval() + 400)
        durante_extremo = tarjeta._extremo_segmento
        durante_segs = len(tarjeta._segmentos)
        _release(franja, ancho * 0.5)
        _esperar(lambda: tarjeta._extremo_segmento is not None)
        _drenar_segmentos(ventana)
        ok = (
            durante_extremo is None
            and durante_segs == 0
            and tarjeta._extremo_segmento is not None
            and len(tarjeta._segmentos) == 0
        )
        detalle = (
            f"durante_extremo={durante_extremo} durante_segs={durante_segs} "
            f"tras_release={tarjeta._extremo_segmento}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def test_18():
    """T5: doble clic real -> reproducción y sin extremo/segmento residual."""
    ventana, temp, ruta_db = _crear_ventana()
    try:
        tarjeta, franja = _tarjeta_y_franja(ventana, "v.mp4")
        ancho = franja.width()
        reproducciones = []
        franja.reproduccion_solicitada.connect(reproducciones.append)
        tarjeta._boton_segmento.setChecked(True)
        _doble_clic_real(franja, ancho * 0.5)
        _procesar(QApplication.doubleClickInterval() + 400)
        _drenar_segmentos(ventana)
        ok = (
            len(reproducciones) == 1
            and tarjeta._extremo_segmento is None
            and len(tarjeta._segmentos) == 0
            and franja._extremo_pendiente_timer is None
            and franja._suprimir_release_clic is False
        )
        detalle = (
            f"reps={len(reproducciones)} a={tarjeta._extremo_segmento} "
            f"segs={len(tarjeta._segmentos)} "
            f"timer={franja._extremo_pendiente_timer} "
            f"suprimir={franja._suprimir_release_clic}"
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return ok, detalle


def main():
    app = QApplication(sys.argv)
    _miniaturas_temporales()
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
    print(f"TOTAL={aprobadas}/18")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
