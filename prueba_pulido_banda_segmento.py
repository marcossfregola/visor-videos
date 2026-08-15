"""Pruebas del Pulido Beta 5 #2 — banda visible de segmentos en la franja.

Verifica de forma estable (sin comparar screenshots completos):

- las constantes de color del segmento: relleno semitransparente, borde
  claramente más opaco que el relleno, y extremo pendiente (A) con color
  diferente (verde) al azul del segmento confirmado;
- la lógica de pintura usa un RELLENO (`fillRect`) además del contorno
  (`drawRect`) sobre el intervalo A→B;
- el relleno realmente se pinta: un pixel central de la banda es azulado
  (B > R) y no es el color opaco puro del segmento (se mezcla con el gris
  de la pista → semitransparente); un punto de la pista fuera de la banda
  sigue siendo gris;
- la lógica temporal A/B sigue intacta (clic A + clic B emiten extremos en
  modo segmento, sin crear marcadores);
- el extremo pendiente se representa con un color verde distinto;
- la superposición de segmentos no produce un bloque totalmente opaco;
- el paint con 50 segmentos completa sin errores y rápido.
"""

import contextlib
import sys
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from exploracion_temporal import tiempo_a_posicion
from scrubber import (
    FranjaExploracion,
    _ALTO_PISTA,
    _COLOR_EXTREMO,
    _COLOR_SEGMENTO,
    _COLOR_SEGMENTO_BORDE,
    _MARGEN,
)


def _esperar(predicado, timeout_ms=4000, paso_ms=15):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _press(widget, x):
    evento = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(float(x), float(widget.height() // 2)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


def _release(widget, x):
    evento = QMouseEvent(
        QEvent.MouseButtonRelease,
        QPointF(float(x), float(widget.height() // 2)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


@contextlib.contextmanager
def _franja_mostrada(ancho=400, alto=224):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    layout.setContentsMargins(0, 0, 0, 0)
    franja = FranjaExploracion()
    layout.addWidget(franja)
    contenedor.resize(ancho, alto)
    contenedor.show()
    QApplication.processEvents()
    franja.set_duracion(100.0)
    franja.set_instante(None)
    try:
        yield franja
    finally:
        contenedor.close()
        franja.deleteLater()
        contenedor.deleteLater()
        for _ in range(3):
            QApplication.processEvents()


def _y_pista(franja):
    return _MARGEN + franja.fontMetrics().height() + 4


def _pixel_central_banda(franja, inicio, fin, x_fuera=11):
    imagen = franja.grab().toImage()
    dpr = franja.devicePixelRatioF() or 1.0
    y = int((_y_pista(franja) + _ALTO_PISTA // 2) * dpr)
    x1 = tiempo_a_posicion(inicio, franja.width(), franja.duracion()) * dpr
    x2 = tiempo_a_posicion(fin, franja.width(), franja.duracion()) * dpr
    x_medio = int((x1 + x2) / 2)
    dentro = imagen.pixelColor(x_medio, y)
    fuera = imagen.pixelColor(int(x_fuera * dpr), y)
    return dentro, fuera


def test_01():
    """Relleno semitransparente, borde mas opaco y extremo pendiente distinto."""
    ok_relleno = 0 < _COLOR_SEGMENTO.alpha() < 255
    ok_borde = _COLOR_SEGMENTO_BORDE.alpha() > _COLOR_SEGMENTO.alpha()
    ok_borde_visible = _COLOR_SEGMENTO_BORDE.alpha() >= 200
    azul_segmento = (
        _COLOR_SEGMENTO.blue() > _COLOR_SEGMENTO.red()
        and _COLOR_SEGMENTO.blue() > _COLOR_SEGMENTO.green()
    )
    verde_extremo = (
        _COLOR_EXTREMO.green() > _COLOR_EXTREMO.red()
        and _COLOR_EXTREMO.green() > _COLOR_EXTREMO.blue()
    )
    distinto = _COLOR_EXTREMO != _COLOR_SEGMENTO
    ok = (
        ok_relleno
        and ok_borde
        and ok_borde_visible
        and azul_segmento
        and verde_extremo
        and distinto
    )
    return (
        ok,
        f"relleno_alpha={_COLOR_SEGMENTO.alpha()} "
        f"borde_alpha={_COLOR_SEGMENTO_BORDE.alpha()} "
        f"segmento={_COLOR_SEGMENTO.name()} extremo={_COLOR_EXTREMO.name()}",
    )


def test_02():
    """El paint del segmento usa relleno (fillRect) ademas del contorno."""
    with open("scrubber.py", "r", encoding="utf-8") as f:
        fuente = f.read()
    inicio = fuente.index("for seg in self._segmentos:")
    fin = fuente.index("for marca in self._marcadores:")
    bloque = fuente[inicio:fin]
    ok = (
        "fillRect(rect_banda, QBrush(_COLOR_SEGMENTO))" in bloque
        and "drawRect(rect_banda)" in bloque
        and "_COLOR_SEGMENTO_BORDE" in bloque
    )
    return (
        ok,
        f"relleno={'fillRect(rect_banda, QBrush(_COLOR_SEGMENTO))' in bloque} "
        f"contorno={'drawRect' in bloque} "
        f"borde_const={'_COLOR_SEGMENTO_BORDE' in bloque}",
    )


def test_03():
    """El relleno se pinta de verdad: banda azulada, pista gris fuera."""
    with _franja_mostrada() as franja:
        franja.set_segmentos([{"id": 1, "inicio": 20.0, "fin": 80.0}])
        dentro, fuera = _pixel_central_banda(franja, 20.0, 80.0)
        azulado = dentro.blue() > dentro.red()
        no_opaco = dentro.red() > _COLOR_SEGMENTO.red()
        gris_fuera = (
            abs(fuera.red() - fuera.green()) <= 8
            and abs(fuera.green() - fuera.blue()) <= 8
        )
        ok = azulado and no_opaco and gris_fuera
        detalle = (
            f"dentro={dentro.name()} fuera={fuera.name()} "
            f"azulado={azulado} no_opaco={no_opaco} gris_fuera={gris_fuera}"
        )
    return ok, detalle


def test_04():
    """Logica A/B intacta: clic A y clic B emiten extremos, sin marcador."""
    with _franja_mostrada() as franja:
        extremos = []
        marcadores = []
        franja.extremo_segmento_solicitado.connect(extremos.append)
        franja.marcador_solicitado.connect(marcadores.append)
        franja.set_modo_crear_segmento(True)
        _press(franja, 60.0)
        _release(franja, 60.0)
        _esperar(lambda: len(extremos) == 1)
        _press(franja, 300.0)
        _release(franja, 300.0)
        _esperar(lambda: len(extremos) == 2)
        ok = (
            len(extremos) == 2
            and abs(extremos[0] - 15.0) < 1e-6
            and abs(extremos[1] - 75.0) < 1e-6
            and len(marcadores) == 0
            and franja.modo_crear_segmento() is True
        )
        detalle = (
            f"extremos={[round(e, 2) for e in extremos]} "
            f"marcadores={len(marcadores)}"
        )
    return ok, detalle


def test_05():
    """Extremo pendiente (A) se pinta en verde, distinto de la banda azul."""
    with _franja_mostrada() as franja:
        franja.set_inicio_segmento_pendiente(50.0)
        imagen = franja.grab().toImage()
        dpr = franja.devicePixelRatioF() or 1.0
        y = int((_y_pista(franja) + _ALTO_PISTA // 2) * dpr)
        x = int(tiempo_a_posicion(50.0, franja.width(), franja.duracion()) * dpr)
        color = imagen.pixelColor(x, y)
        verde = (
            color.green() > color.red()
            and color.green() > color.blue()
        )
        ok = verde
        detalle = (
            f"pixel_extremo={color.name()} verde={verde} "
            f"extremo_puro={_COLOR_EXTREMO.name()}"
        )
    return ok, detalle


def test_06():
    """Superposicion/duplicados: no produce bloque totalmente opaco."""
    with _franja_mostrada() as franja:
        franja.set_segmentos(
            [
                {"id": 1, "inicio": 20.0, "fin": 80.0},
                {"id": 2, "inicio": 20.0, "fin": 80.0},
                {"id": 3, "inicio": 50.0, "fin": 90.0},
            ]
        )
        dentro, _ = _pixel_central_banda(franja, 20.0, 80.0)
        azulado = dentro.blue() > dentro.red()
        no_opaco = dentro.red() > _COLOR_SEGMENTO.red() * 0.5
        opaco_puro = (
            dentro.red() == _COLOR_SEGMENTO.red()
            and dentro.blue() == _COLOR_SEGMENTO.blue()
        )
        ok = azulado and no_opaco and not opaco_puro
        detalle = (
            f"pixel_superpuesto={dentro.name()} azulado={azulado} "
            f"no_opaco={no_opaco} no_es_puro={not opaco_puro}"
        )
    return ok, detalle


def test_07():
    """Paint con 50 segmentos: completa sin errores y en tiempo razonable."""
    with _franja_mostrada() as franja:
        segmentos = []
        for i in range(50):
            inicio = (i * 7) % 92
            fin = inicio + 5 + (i % 10)
            segmentos.append({"id": i, "inicio": float(inicio), "fin": float(fin)})
        franja.set_segmentos(segmentos)
        t0 = time.perf_counter()
        imagen = franja.grab().toImage()
        t1 = time.perf_counter()
        ok = (
            not imagen.isNull()
            and len(franja.segmentos()) == 50
            and (t1 - t0) < 0.5
        )
        detalle = (
            f"segmentos={len(franja.segmentos())} "
            f"tiempo_paint={1000 * (t1 - t0):.1f} ms"
        )
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
    print(f"TOTAL={aprobadas}/7")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
