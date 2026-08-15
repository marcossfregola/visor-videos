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
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget

from exploracion_temporal import posicion_a_tiempo, tiempo_a_posicion

_COLOR_FONDO = QColor(244, 244, 244)
_COLOR_BORDE = QColor(204, 204, 204)
_COLOR_PISTA = QColor(224, 224, 224)
_COLOR_MARCADOR = QColor(33, 150, 243)
_COLOR_MARCA = QColor(229, 57, 53)
_COLOR_TEXTO = QColor(30, 30, 30)
_COLOR_SEGMENTO = QColor(33, 150, 243, 120)
_COLOR_SEGMENTO_BORDE = QColor(33, 150, 243, 230)
_COLOR_SEGMENTO_PROVISIONAL = QColor(33, 150, 243, 170)
_COLOR_EXTREMO = QColor(76, 175, 80)

_MARGEN = 6
_ALTO_PISTA = 10
_TOLERANCIA_MARCA_PX = 6
_TOLERANCIA_EXTREMO_PX = 12


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
            # Reenviar el clic izquierdo a la superficie (B5.9.2B): la miniatura
            # cubre una amplia zona de la franja; si se traga el clic, no puede
            # crearse un marcador temporalmente cercano aunque esté en un instante
            # distinto. Se replica el patrón de `mouseMoveEvent`/doble clic.
            superficie = self._superficie
            if superficie is not None and superficie.width() > 0:
                global_pos = self.mapToGlobal(event.position().toPoint())
                local = superficie.mapFromGlobal(global_pos)
                nuevo = QMouseEvent(
                    QEvent.MouseButtonPress,
                    QPointF(local),
                    event.button(),
                    event.buttons(),
                    event.modifiers(),
                )
                QApplication.sendEvent(superficie, nuevo)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Reenvía el doble clic a la superficie (B5.9.2).

        La miniatura se crea en el punto del marcador; sobre un video real
        Qt entrega el doble clic a esta etiqueta (widget topmost) y, si no se
        reenvía, la franja nunca recibe `reproduccion_solicitada`. Se replica
        el patrón de `mouseMoveEvent`: se reenvía el evento en coordenadas de
        la superficie para que el doble clic temporal (B5.3) siga abriendo VLC.
        """
        superficie = self._superficie
        if (
            event.button() == Qt.LeftButton
            and superficie is not None
            and superficie.width() > 0
        ):
            global_pos = self.mapToGlobal(event.position().toPoint())
            local = superficie.mapFromGlobal(global_pos)
            nuevo = QMouseEvent(
                QEvent.MouseButtonDblClick,
                QPointF(local),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            QApplication.sendEvent(superficie, nuevo)
        event.accept()

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
    segmento_arrastre_confirmado = Signal(float, float)
    extremo_editado = Signal(object, float, float)
    segmento_contextual_solicitado = Signal(object)

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
        self._boton_presionado = False
        self._press_pos = None
        self._press_instante = None
        self._drag_activo = False
        self._drag_inicio = None
        self._drag_actual = None
        self._suprimir_release_clic = False
        self._edicion_candidato = None
        self._edicion_activa = None
        self._hover_extremo = None
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

        En este modo, el clic izquierdo completo (press+release sin arrastre)
        emite `extremo_segmento_solicitado` (diferido por el intervalo de
        doble clic, solo tras el release) en lugar de crear un marcador; el
        arrastre emite `segmento_arrastre_confirmado`. Al desactivar se
        cancela cualquier extremo pendiente y estado de interacción.
        """
        self._modo_crear_segmento = bool(activo)
        if not self._modo_crear_segmento:
            self._cancelar_timer_extremo()
            self._limpiar_drag()
            self._suprimir_release_clic = False
            self._hover_extremo = None
            self.unsetCursor()
            self.update()

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

    def _extremo_en_posicion(self, x):
        """Extremo de segmento editable bajo `x` (solo en modo segmento).

        Devuelve `(segmento, lado)` con `lado` en `{"inicio", "fin"}` si la
        posición cae dentro de `_TOLERANCIA_EXTREMO_PX` de un extremo.
        Regla determinista: menor distancia al cursor; desempate por el
        segmento más corto (pintado encima), luego el `id` mayor y luego el
        lado `"inicio"` antes que `"fin"`.
        """
        if not self._segmentos:
            return None
        mejor = None
        mejor_clave = None
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
            xa = self._posicion_de(inicio)
            xb = self._posicion_de(fin)
            if xa is None or xb is None:
                continue
            for lado, x_ext in (("inicio", xa), ("fin", xb)):
                distancia = abs(x_ext - x)
                if distancia > _TOLERANCIA_EXTREMO_PX:
                    continue
                clave = (
                    distancia,
                    fin - inicio,
                    -seg["id"] if isinstance(seg.get("id"), int) else 0,
                    lado,
                )
                if mejor_clave is None or clave < mejor_clave:
                    mejor_clave = clave
                    mejor = (seg, lado)
        return mejor

    def _cancelar_timer_extremo(self):
        if self._timer_extremo is not None and self._timer_extremo.isActive():
            self._timer_extremo.stop()
        self._extremo_pendiente_timer = None

    def _programar_extremo(self, instante):
        """Difiere un clic candidato por el intervalo de doble clic.

        Solo se programa DESPUÉS del release de un clic sin arrastre. Así, un
        press sostenido jamás confirma un extremo por sí mismo: si llega un
        doble clic, `mouseDoubleClickEvent` cancela el candidato; si no llega,
        el timer emite el extremo (clic normal). Se reutiliza un único QTimer
        persistente (se reinicia en cada pulsación).
        """
        self._cancelar_timer_extremo()
        self._extremo_pendiente_timer = float(instante)
        self._timer_extremo.start(QApplication.doubleClickInterval())

    def _emitir_extremo(self):
        instante = self._extremo_pendiente_timer
        self._extremo_pendiente_timer = None
        if instante is not None:
            self.extremo_segmento_solicitado.emit(instante)

    def _limpiar_drag(self):
        self._boton_presionado = False
        self._press_pos = None
        self._press_instante = None
        self._drag_activo = False
        self._drag_inicio = None
        self._drag_actual = None
        self._edicion_candidato = None
        self._edicion_activa = None
        self.update()

    def _iniciar_edicion_extremo(self):
        """Convierte un press sobre un extremo en edición real (≥ umbral)."""
        segmento, lado = self._edicion_candidato
        self._edicion_candidato = None
        fijo = segmento["fin"] if lado == "inicio" else segmento["inicio"]
        actual = segmento["inicio"] if lado == "inicio" else segmento["fin"]
        self._edicion_activa = {
            "segmento": segmento,
            "lado": lado,
            "fijo": float(fijo),
            "actual": float(actual),
            "inicio_original": float(segmento["inicio"]),
            "fin_original": float(segmento["fin"]),
        }
        self._cancelar_timer_extremo()
        self.update()

    def _actualizar_edicion_extremo(self, instante):
        if instante is None or self._edicion_activa is None:
            return
        self._edicion_activa["actual"] = float(instante)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            instante = self._instante_en(event.position().x())
            if instante is not None:
                self._actualizar_instante(instante)
                if self._modo_crear_segmento:
                    self._press_pos = event.position()
                    self._press_instante = float(instante)
                    self._boton_presionado = True
                    self._edicion_candidato = self._extremo_en_posicion(
                        event.position().x()
                    )
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
                self.segmento_contextual_solicitado.emit(segmento)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        instante = self._instante_en(event.position().x())
        if instante is not None:
            self._actualizar_instante(instante)
        if (
            self._modo_crear_segmento
            and self._boton_presionado
            and self._press_pos is not None
        ):
            if (
                not self._drag_activo
                and self._edicion_activa is None
                and self._edicion_candidato is not None
            ):
                distancia = (
                    event.position() - self._press_pos
                ).manhattanLength()
                if distancia >= QApplication.startDragDistance():
                    self._iniciar_edicion_extremo()
            elif (
                self._edicion_activa is None
                and not self._drag_activo
            ):
                distancia = (
                    event.position() - self._press_pos
                ).manhattanLength()
                if distancia >= QApplication.startDragDistance():
                    self._drag_activo = True
                    self._cancelar_timer_extremo()
                    self._drag_inicio = self._press_instante
            if self._edicion_activa is not None:
                self._actualizar_edicion_extremo(instante)
            elif self._drag_activo:
                self._drag_actual = (
                    float(instante) if instante is not None else None
                )
                self.update()
        elif not self._boton_presionado:
            self._actualizar_cursor_extremo(event.position().x())
        event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._boton_presionado = False
            if self._drag_activo:
                inicio = self._drag_inicio
                instante_final = self._instante_en(event.position().x())
                self._limpiar_drag()
                if (
                    inicio is not None
                    and instante_final is not None
                ):
                    a = min(inicio, instante_final)
                    b = max(inicio, instante_final)
                    if b > a:
                        self.segmento_arrastre_confirmado.emit(a, b)
                event.accept()
                return
            if self._edicion_activa is not None:
                edicion = self._edicion_activa
                fijo = edicion["fijo"]
                actual = self._instante_en(event.position().x())
                self._limpiar_drag()
                if actual is not None:
                    a = min(fijo, actual)
                    b = max(fijo, actual)
                    if b > a:
                        self.extremo_editado.emit(
                            edicion["segmento"], a, b
                        )
                event.accept()
                return
            if self._edicion_candidato is not None:
                self._limpiar_drag()
                event.accept()
                return
            if self._suprimir_release_clic:
                self._suprimir_release_clic = False
                self._limpiar_drag()
                event.accept()
                return
            instante = self._press_instante
            if instante is None:
                instante = self._instante_en(event.position().x())
            if self._modo_crear_segmento and instante is not None:
                self._programar_extremo(instante)
            self._limpiar_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _actualizar_cursor_extremo(self, x):
        extremo = (
            self._extremo_en_posicion(x)
            if self._modo_crear_segmento
            else None
        )
        self._hover_extremo = extremo
        if extremo is not None:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.unsetCursor()
        self.update()

    def enterEvent(self, event):
        self._actualizar_cursor_extremo(event.position().x())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_extremo = None
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._cancelar_timer_extremo()
        self._suprimir_release_clic = True
        if self._drag_activo or self._edicion_activa is not None:
            self._limpiar_drag()
        if event.button() == Qt.LeftButton:
            instante = self._instante_en(event.position().x())
            if instante is not None:
                self.reproduccion_solicitada.emit(instante)
        event.accept()

    def hideEvent(self, event):
        self._cancelar_timer_extremo()
        self._limpiar_drag()
        self._suprimir_release_clic = False
        self._hover_extremo = None
        self.unsetCursor()
        self.update()
        super().hideEvent(event)

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
            pintor.fillRect(rect_banda, QBrush(_COLOR_SEGMENTO))
            pintor.setBrush(Qt.NoBrush)
            pintor.setPen(QPen(_COLOR_SEGMENTO_BORDE, 2))
            pintor.drawRect(rect_banda)

        if (
            self._drag_activo
            and self._drag_inicio is not None
            and self._drag_actual is not None
        ):
            x1 = self._posicion_de(self._drag_inicio)
            x2 = self._posicion_de(self._drag_actual)
            if x1 is not None and x2 is not None:
                izquierda = min(x1, x2)
                ancho_banda = max(0.0, abs(x2 - x1))
                rect_prov = QRectF(
                    izquierda, y_pista, ancho_banda, _ALTO_PISTA
                )
                pintor.fillRect(
                    rect_prov, QBrush(_COLOR_SEGMENTO_PROVISIONAL)
                )
                pintor.setBrush(Qt.NoBrush)
                pintor.setPen(QPen(_COLOR_SEGMENTO_BORDE, 1, Qt.DashLine))
                pintor.drawRect(rect_prov)

        if self._edicion_activa is not None:
            edicion = self._edicion_activa
            a = min(edicion["fijo"], edicion["actual"])
            b = max(edicion["fijo"], edicion["actual"])
            x1 = self._posicion_de(a)
            x2 = self._posicion_de(b)
            x_ext = self._posicion_de(edicion["actual"])
            if x1 is not None and x2 is not None:
                izquierda = min(x1, x2)
                ancho_banda = max(0.0, abs(x2 - x1))
                rect_edit = QRectF(
                    izquierda, y_pista, ancho_banda, _ALTO_PISTA
                )
                pintor.fillRect(
                    rect_edit, QBrush(_COLOR_SEGMENTO_PROVISIONAL)
                )
                pintor.setBrush(Qt.NoBrush)
                pintor.setPen(QPen(_COLOR_SEGMENTO_BORDE, 1, Qt.DashLine))
                pintor.drawRect(rect_edit)
            if x_ext is not None:
                pintor.setPen(QPen(_COLOR_SEGMENTO_BORDE, 3))
                pintor.drawLine(
                    QPointF(x_ext, y_pista - 4),
                    QPointF(x_ext, y_pista + _ALTO_PISTA + 4),
                )

        if (
            self._hover_extremo is not None
            and self._edicion_activa is None
            and self._modo_crear_segmento
        ):
            seg_h, lado_h = self._hover_extremo
            inst_h = (
                seg_h.get("inicio")
                if lado_h == "inicio"
                else seg_h.get("fin")
            )
            xh = self._posicion_de(inst_h)
            if xh is not None:
                ancho_handle = 10.0
                rect_handle = QRectF(
                    xh - ancho_handle / 2.0,
                    y_pista - 4,
                    ancho_handle,
                    _ALTO_PISTA + 8,
                )
                pintor.setBrush(QBrush(_COLOR_SEGMENTO_BORDE))
                pintor.setPen(Qt.NoPen)
                pintor.drawRoundedRect(rect_handle, 2, 2)
                pintor.setPen(QPen(QColor(255, 255, 255), 1))
                pintor.drawLine(
                    QPointF(xh, y_pista),
                    QPointF(xh, y_pista + _ALTO_PISTA),
                )

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
