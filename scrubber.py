"""Widget de superficie temporal para la exploración por scrubbing (B4.1).

Toda la segunda fila expandida representa la duración completa del video:
el extremo izquierdo corresponde al instante 0 y el extremo derecho a la
duración total. El movimiento del mouse sobre cualquier parte de la
superficie se convierte en una señal con el instante correspondiente
(la posición vertical no influye: solo importa la X). El clic solicita
la creación de un marcador temporal persistente.

Este widget no conoce videos, FFmpeg, SQLite, caché ni previews: dibuja
la pista, el marcador móvil del cursor, las marcas persistentes y el
texto de tiempo que la tarjeta le provee.
"""

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget

from exploracion_temporal import posicion_a_tiempo, tiempo_a_posicion

_COLOR_FONDO = QColor(244, 244, 244)
_COLOR_BORDE = QColor(204, 204, 204)
_COLOR_PISTA = QColor(224, 224, 224)
_COLOR_MARCADOR = QColor(33, 150, 243)
_COLOR_MARCA = QColor(229, 57, 53)
_COLOR_TEXTO = QColor(30, 30, 30)

_MARGEN = 6
_ALTO_PISTA = 10
_TOLERANCIA_MARCA_PX = 6


class MiniaturaMarcador(QLabel):
    """Miniatura fijada de un marcador temporal.

    Recibe únicamente el clic derecho para solicitar la eliminación del
    marcador asociado. El clic izquierdo queda reservado para funciones
    futuras (no crea ni elimina nada). El movimiento del mouse se reenvía
    a la superficie en coordenadas de la superficie para que el scrubbing
    continúe funcionando aunque el cursor pase por encima de la miniatura.
    """

    eliminar_solicitado = Signal(float)

    def __init__(self, superficie, tiempo):
        super().__init__(superficie)
        self._tiempo = tiempo
        self._superficie = superficie
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.eliminar_solicitado.emit(self._tiempo)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        superficie = self._superficie
        if superficie is not None and superficie.width() > 0:
            global_pos = self.mapToGlobal(event.position().toPoint())
            local = superficie.mapFromGlobal(global_pos)
            nuevo = QMouseEvent(
                QEvent.MouseMove,
                QPointF(local),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            QApplication.sendEvent(superficie, nuevo)
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()


class FranjaExploracion(QWidget):
    instante_seleccionado = Signal(float)
    marcador_solicitado = Signal(float)
    marcador_eliminar_solicitado = Signal(float)
    reproduccion_solicitada = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duracion = None
        self._instante = None
        self._marcadores = []
        self._texto_tiempo = ""
        self.setMouseTracking(True)

    def set_duracion(self, duracion):
        self._duracion = duracion
        self.update()

    def set_instante(self, instante):
        self._instante = instante
        self.update()

    def set_marcadores(self, marcadores):
        self._marcadores = [
            m for m in marcadores
            if isinstance(m, (int, float)) and not isinstance(m, bool)
        ]
        self.update()

    def set_texto_tiempo(self, texto):
        self._texto_tiempo = texto if isinstance(texto, str) else ""
        self.update()

    def duracion(self):
        return self._duracion

    def instante(self):
        return self._instante

    def texto_tiempo(self):
        return self._texto_tiempo

    def _posicion_de(self, instante):
        return tiempo_a_posicion(instante, self.width(), self._duracion)

    def _instante_en(self, x):
        return posicion_a_tiempo(x, self.width(), self._duracion)

    def _actualizar_instante(self, instante):
        self._instante = instante
        self.instante_seleccionado.emit(instante)
        self.update()

    def _marcador_en_posicion(self, x):
        if not self._marcadores:
            return None
        mejor = None
        mejor_distancia = None
        for tiempo in self._marcadores:
            posicion = self._posicion_de(tiempo)
            if posicion is None:
                continue
            distancia = abs(posicion - x)
            if mejor_distancia is None or distancia < mejor_distancia:
                mejor_distancia = distancia
                mejor = tiempo
        if mejor_distancia is not None and mejor_distancia <= _TOLERANCIA_MARCA_PX:
            return mejor
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            instante = self._instante_en(event.position().x())
            if instante is not None:
                self._actualizar_instante(instante)
                self.marcador_solicitado.emit(instante)
                event.accept()
                return
        elif event.button() == Qt.RightButton:
            tiempo = self._marcador_en_posicion(event.position().x())
            if tiempo is not None:
                self.marcador_eliminar_solicitado.emit(tiempo)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        instante = self._instante_en(event.position().x())
        if instante is not None:
            self._actualizar_instante(instante)
        event.accept()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            instante = self._instante_en(event.position().x())
            if instante is not None:
                self.reproduccion_solicitada.emit(instante)
        event.accept()

    def paintEvent(self, event):
        pintor = QPainter(self)
        rect = self.rect()
        pintor.fillRect(rect, _COLOR_FONDO)
        pintor.setPen(QPen(_COLOR_BORDE, 1))
        pintor.setBrush(Qt.NoBrush)
        pintor.drawRect(rect.adjusted(0, 0, -1, -1))

        ancho_util = max(0, rect.width() - 2 * _MARGEN)

        if self._texto_tiempo:
            pintor.setPen(_COLOR_TEXTO)
            metrica = pintor.fontMetrics()
            ancho_txt = metrica.horizontalAdvance(self._texto_tiempo)
            pintor.drawText(
                rect.right() - ancho_txt - _MARGEN,
                _MARGEN + metrica.ascent(),
                self._texto_tiempo,
            )

        y_pista = _MARGEN + pintor.fontMetrics().height() + 4
        pista = QRectF(_MARGEN, y_pista, ancho_util, _ALTO_PISTA)
        pintor.setPen(QPen(_COLOR_BORDE, 1))
        pintor.setBrush(_COLOR_PISTA)
        pintor.drawRoundedRect(pista, 3, 3)

        for marca in self._marcadores:
            x = self._posicion_de(marca)
            if x is None:
                continue
            pintor.setPen(QPen(_COLOR_MARCA, 2))
            pintor.drawLine(
                QPointF(x, _MARGEN - 2),
                QPointF(x, y_pista - 2),
            )

        x = self._posicion_de(self._instante)
        if x is not None:
            pintor.setPen(QPen(_COLOR_MARCADOR, 2))
            pintor.drawLine(
                QPointF(x, rect.top() + 2),
                QPointF(x, rect.bottom() - 2),
            )
        pintor.end()
