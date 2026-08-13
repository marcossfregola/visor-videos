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

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget

from exploracion_temporal import posicion_a_tiempo, tiempo_a_posicion

_COLOR_FONDO = QColor(244, 244, 244)
_COLOR_BORDE = QColor(204, 204, 204)
_COLOR_PISTA = QColor(224, 224, 224)
_COLOR_MARCADOR = QColor(33, 150, 243)
_COLOR_MARCA = QColor(229, 57, 53)
_COLOR_TEXTO = QColor(30, 30, 30)
_COLOR_SEGMENTO = QColor(33, 150, 243, 55)
_COLOR_SEGMENTO_BORDE = QColor(33, 150, 243, 150)
_COLOR_EXTREMO = QColor(76, 175, 80)

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
    extremo_segmento_solicitado = Signal(float)
    segmento_eliminar_solicitado = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duracion = None
        self._instante = None
        self._marcadores = []
        self._segmentos = []
        self._texto_tiempo = ""
        self._modo_crear_segmento = False
        self._extremo_pendiente = None
        self._extremo_pendiente_timer = None
        self._timer_extremo = QTimer(self)
        self._timer_extremo.setSingleShot(True)
        self._timer_extremo.timeout.connect(self._emitir_extremo)
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

    def set_segmentos(self, segmentos):
        """Recibe los segmentos a pintar (solo datos visuales/temporales).

        Cada segmento es un dict `{id, inicio, fin}`. La franja conserva la
        referencia a los mismos objetos para poder reportar el segmento
        exacto en el hit-testing (eliminación).
        """
        self._segmentos = (
            list(segmentos) if segmentos is not None else []
        )
        self.update()

    def set_inicio_segmento_pendiente(self, instante):
        self._extremo_pendiente = instante
        self.update()

    def set_modo_crear_segmento(self, activo):
        """Activa/desactiva el modo de creación de segmentos.

        En este modo, el clic izquierdo emite `extremo_segmento_solicitado`
        (diferido por el intervalo de doble clic) en lugar de crear un
        marcador. Al desactivar se cancela cualquier extremo pendiente.
        """
        self._modo_crear_segmento = bool(activo)
        if not self._modo_crear_segmento:
            self._cancelar_timer_extremo()

    def segmentos(self):
        return list(self._segmentos)

    def modo_crear_segmento(self):
        return self._modo_crear_segmento

    def inicio_segmento_pendiente(self):
        return self._extremo_pendiente

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

    def _segmento_en_posicion(self, x):
        if not self._segmentos:
            return None
        instante = self._instante_en(x)
        if instante is None:
            return None
        candidatos = []
        for seg in self._segmentos:
            inicio = seg.get("inicio")
            fin = seg.get("fin")
            if not (
                isinstance(inicio, (int, float))
                and not isinstance(inicio, bool)
                and isinstance(fin, (int, float))
                and not isinstance(fin, bool)
            ):
                continue
            if inicio <= instante <= fin:
                candidatos.append(seg)
        if not candidatos:
            return None
        # Preferencia: el segmento más corto que contenga el punto;
        # desempate por el id mayor (el pintado encima).
        return min(
            candidatos,
            key=lambda s: (
                (s["fin"] - s["inicio"]),
                -s["id"] if isinstance(s.get("id"), int) else 0,
            ),
        )

    def _cancelar_timer_extremo(self):
        if self._timer_extremo is not None and self._timer_extremo.isActive():
            self._timer_extremo.stop()
        self._extremo_pendiente_timer = None

    def _programar_extremo(self, instante):
        """Difiere el extremo por el intervalo de doble clic (B5.4).

        Así, un doble clic nunca emite un extremo de segmento y el doble
        clic de B5.3 (reproducción temporal) queda intacto. Se reutiliza un
        único QTimer persistente (se reinicia en cada pulsación).
        """
        self._cancelar_timer_extremo()
        self._extremo_pendiente_timer = float(instante)
        self._timer_extremo.start(QApplication.doubleClickInterval())

    def _emitir_extremo(self):
        instante = self._extremo_pendiente_timer
        self._extremo_pendiente_timer = None
        if instante is not None:
            self.extremo_segmento_solicitado.emit(instante)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            instante = self._instante_en(event.position().x())
            if instante is not None:
                self._actualizar_instante(instante)
                if self._modo_crear_segmento:
                    self._programar_extremo(instante)
                else:
                    self.marcador_solicitado.emit(instante)
                event.accept()
                return
        elif event.button() == Qt.RightButton:
            tiempo = self._marcador_en_posicion(event.position().x())
            if tiempo is not None:
                self.marcador_eliminar_solicitado.emit(tiempo)
                event.accept()
                return
            segmento = self._segmento_en_posicion(event.position().x())
            if segmento is not None:
                self.segmento_eliminar_solicitado.emit(segmento)
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
        self._cancelar_timer_extremo()
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

        for seg in self._segmentos:
            inicio = seg.get("inicio")
            fin = seg.get("fin")
            x1 = self._posicion_de(inicio)
            x2 = self._posicion_de(fin)
            if x1 is None or x2 is None:
                continue
            izquierda = min(x1, x2)
            ancho_banda = max(0.0, abs(x2 - x1))
            rect_banda = QRectF(izquierda, y_pista, ancho_banda, _ALTO_PISTA)
            pintor.fillRect(rect_banda, _COLOR_SEGMENTO)
            pintor.setPen(QPen(_COLOR_SEGMENTO_BORDE, 1))
            pintor.drawRect(rect_banda)

        for marca in self._marcadores:
            x = self._posicion_de(marca)
            if x is None:
                continue
            pintor.setPen(QPen(_COLOR_MARCA, 2))
            pintor.drawLine(
                QPointF(x, _MARGEN - 2),
                QPointF(x, y_pista - 2),
            )

        if self._extremo_pendiente is not None:
            x = self._posicion_de(self._extremo_pendiente)
            if x is not None:
                pintor.setPen(QPen(_COLOR_EXTREMO, 2))
                pintor.drawLine(
                    QPointF(x, _MARGEN - 2),
                    QPointF(x, rect.bottom() - 2),
                )

        x = self._posicion_de(self._instante)
        if x is not None:
            pintor.setPen(QPen(_COLOR_MARCADOR, 2))
            pintor.drawLine(
                QPointF(x, rect.top() + 2),
                QPointF(x, rect.bottom() - 2),
            )
        pintor.end()
