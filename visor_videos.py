import escanear_videos
import os
import sys

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from configuracion import (
    guardar_cantidad_previews,
    guardar_preferencia_escaneo_automatico,
    guardar_preferencia_subcarpetas,
    guardar_retardo_vista_ampliada,
    guardar_tamano_miniaturas,
    guardar_tamano_vista_ampliada,
    guardar_ultima_carpeta,
    obtener_cantidad_previews,
    obtener_preferencia_escaneo_automatico,
    obtener_preferencia_subcarpetas,
    obtener_retardo_vista_ampliada,
    obtener_tamano_miniaturas,
    obtener_tamano_vista_ampliada,
    obtener_ultima_carpeta,
)
from escanear_videos import (
    _nombre_seguro,
    calcular_tiempo_preview,
    configurar_cantidad_previews,
    configurar_escaneo_recursivo,
)
from rutas import ruta_carpeta_miniaturas, ruta_configuracion
from tareas import Estado, GestorTareas
from apertura_videos import abrir_video_con_aplicacion_predeterminada
from arbol_navegacion import ArbolNavegacion
from tareas_videos import (
    TareaEscaneo,
    TareaFFprobe,
    TareaGuardarVideos,
    TareaLecturaCatalogoPaginada,
    TareaMiniaturas,
    TareaPreviewsProgresivas,
    TareaSincronizacionCatalogo,
    TareaTamanosArchivos,
    _es_archivo_preview,
    combinar_registros_con_ffprobe,
    combinar_registros_con_miniaturas,
    combinar_registros_con_tamanos,
    conectar_bd,
    guardar_videos,
    previews_existentes,
)

ANCHO_TARJETA = 320
ALTO_TARJETA = 180
TAMANIO_PAGINA_INICIAL = 100
TAMANIO_LOTE_PREVIEWS = 3
RETARDO_VISTA_AMPLIADA_MS = 400
LIMITE_ORIGINAL_MINIATURA = 1280
RETARDO_OCULTAR_VISTA_MS = 150
FACTOR_VISTA_AMPLIADA = 1.6
FACTORES_VISTA_AMPLIADA = (1.2, 1.6, 2.0, 2.5)
TEXTOS_FACTOR_VISTA_AMPLIADA = ("1.2x", "1.6x", "2.0x", "2.5x")
FACTOR_VISTA_AMPLIADA_ACTUAL = FACTOR_VISTA_AMPLIADA


def configurar_factor_vista_ampliada(factor):
    global FACTOR_VISTA_AMPLIADA_ACTUAL
    if isinstance(factor, float) and factor in FACTORES_VISTA_AMPLIADA:
        FACTOR_VISTA_AMPLIADA_ACTUAL = factor

TAMANIOS_MINIATURAS = {
    "pequeno": (260, 146),
    "mediano": (320, 180),
    "grande": (400, 225),
    "muy_grande": (512, 288),
}
TAMANIO_MINIATURAS_ACTUAL = "mediano"
TEXTO_TAMANO_MINIATURAS = {
    "pequeno": "Pequeño",
    "mediano": "Mediano",
    "grande": "Grande",
    "muy_grande": "Muy grande",
}


def configurar_tamano_miniaturas(nombre):
    global TAMANIO_MINIATURAS_ACTUAL
    if isinstance(nombre, str) and nombre in TAMANIOS_MINIATURAS:
        TAMANIO_MINIATURAS_ACTUAL = nombre


def dimensiones_miniatura():
    return TAMANIOS_MINIATURAS[TAMANIO_MINIATURAS_ACTUAL]


def texto_tamano_miniaturas(nombre):
    return TEXTO_TAMANO_MINIATURAS.get(nombre, "Mediano")


def clave_tamano_miniaturas(texto):
    for clave, valor in TEXTO_TAMANO_MINIATURAS.items():
        if valor == texto:
            return clave
    return "mediano"

MENSAJE_CARGANDO = "Cargando catálogo…"
MENSAJE_ERROR = "No se pudo cargar el catálogo"
MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"
MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"
MENSAJE_ESCANEANDO = "Escaneando carpeta…"
MENSAJE_ERROR_ESCANEO = "No se pudo escanear la carpeta"
MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"
MENSAJE_ERROR_TAMANOS = "No se pudieron obtener los tamaños de los archivos"
MENSAJE_ERROR_MINIATURAS = "No se pudieron generar las miniaturas"
MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"
MENSAJE_SINCRONIZANDO = "Sincronizando catálogo…"
MENSAJE_ERROR_SINCRONIZACION = "No se pudo sincronizar el catálogo"
MENSAJE_ERROR_RECARGA = "No se pudo actualizar el catálogo"
MENSAJE_ERROR_PAGINA = "No se pudo cargar la página"
MENSAJE_SIN_ESCANEO = "Sin escanear"
MENSAJE_ERROR_ABRIR = "No se pudo abrir el video"


def texto_resumen_sincronizacion(resumen):
    if resumen is None:
        resumen = {}
    incorporados = resumen.get("incorporados", 0)
    eliminados = resumen.get("eliminados", 0)
    restantes = resumen.get("candidatos_restantes", 0)
    return (
        f"Sincronización completa: {incorporados} incorporados, "
        f"{eliminados} eliminados, {restantes} candidatos restantes"
    )


def formatear_valor(valor):
    if valor is None:
        return "No disponible"
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def formatear_tamano(valor):
    if not isinstance(valor, int) or isinstance(valor, bool):
        return "Desconocido"
    if valor < 0:
        return "Desconocido"
    if valor < 1024:
        return f"{valor} B"
    if valor < 1024 * 1024:
        return f"{valor / 1024:.1f} KB"
    if valor < 1024 * 1024 * 1024:
        return f"{valor / (1024 * 1024):.1f} MB"
    return f"{valor / (1024 * 1024 * 1024):.1f} GB"


def formatear_tiempo(segundos):
    if not isinstance(segundos, (int, float)) or isinstance(segundos, bool):
        return None
    if segundos < 0:
        return None
    total = int(round(segundos))
    horas, resto = divmod(total, 3600)
    minutos, segundos_resto = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos_resto:02d}"
    return f"{minutos}:{segundos_resto:02d}"


def _duracion_valida(duracion):
    return (
        isinstance(duracion, (int, float))
        and not isinstance(duracion, bool)
        and duracion > 0
    )


def _pixmap_acotado(pixmap):
    if pixmap is None or pixmap.isNull():
        return pixmap
    ancho = pixmap.width()
    alto = pixmap.height()
    mayor = max(ancho, alto)
    if mayor <= LIMITE_ORIGINAL_MINIATURA:
        return pixmap
    escala = LIMITE_ORIGINAL_MINIATURA / mayor
    return pixmap.scaled(
        max(1, int(ancho * escala)),
        max(1, int(alto * escala)),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


def miniatura_principal(nombre):
    prefijo = _nombre_seguro(os.path.splitext(nombre)[0])
    carpeta = ruta_carpeta_miniaturas()
    if os.path.isdir(carpeta):
        for archivo in sorted(os.listdir(carpeta)):
            if (
                os.path.splitext(archivo)[0].startswith(prefijo)
                and not _es_archivo_preview(archivo, nombre)
            ):
                ruta = os.path.join(carpeta, archivo)
                return ruta
    return None


def previews_de(nombre):
    return previews_existentes(nombre)


ESTILO_SELECCIONADA = "Tarjeta { border: 3px solid #2196F3; }"


class PreviewConTiempo(QLabel):
    """Etiqueta de preview que superpone el instante temporal al fotograma.

    La superposición es exclusivamente visual: mantiene un widget por slot y
    el mismo layout, sin alterar tamaños de tarjeta, de miniaturas ni el
    scroll. El pixmap almacenado es el ya escalado (mismo criterio que antes
    de la etapa), por lo que `pixmap()` conserva el contrato y el tamaño de
    la etiqueta no cambia. Si no hay tiempo (duración desconocida o
    inválida), dibuja solo el fotograma, sin valores por defecto.
    """

    ESTILO_BASE = "background-color: #f0f0f0; border: 1px solid #ccc;"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_original = None
        self._tiempo = None
        self.setFixedHeight(dimensiones_miniatura()[1])
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(self.ESTILO_BASE)

    def poner_preview(self, pixmap, tiempo=None):
        if pixmap is None or pixmap.isNull():
            return False
        self._pixmap_original = _pixmap_acotado(pixmap)
        self._tiempo = tiempo
        ancho, alto = dimensiones_miniatura()
        self.setFixedHeight(alto)
        self.setPixmap(
            self._pixmap_original.scaled(
                ancho,
                alto,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.setText("")
        self.update()
        return True

    def reajustar(self):
        ancho, alto = dimensiones_miniatura()
        self.setFixedHeight(alto)
        if self._pixmap_original is None or self._pixmap_original.isNull():
            return False
        return self.poner_preview(self._pixmap_original, self._tiempo)

    def paintEvent(self, event):
        if self.pixmap() is None or self.pixmap().isNull():
            super().paintEvent(event)
            return
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor("#f0f0f0"))
        pintor.setPen(QColor("#cccccc"))
        pintor.setBrush(Qt.NoBrush)
        pintor.drawRect(self.rect().adjusted(0, 0, -1, -1))
        escalada = self.pixmap()
        x = (self.width() - escalada.width()) // 2
        y = (self.height() - escalada.height()) // 2
        pintor.drawPixmap(x, y, escalada)
        if self._tiempo is not None:
            metrica = pintor.fontMetrics()
            ancho = metrica.horizontalAdvance(self._tiempo) + 10
            alto = metrica.height() + 4
            bx = x + escalada.width() - ancho - 4
            by = y + escalada.height() - alto - 4
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(0, 0, 0, 150))
            pintor.drawRoundedRect(bx, by, ancho, alto, 3, 3)
            pintor.setPen(QColor(255, 255, 255, 235))
            pintor.drawText(bx + 5, by + metrica.ascent() + 2, self._tiempo)
        pintor.end()


class VistaAmpliada(QFrame):
    """Popup de vista ampliada al posar el mouse sobre una miniatura (Etapa B3.4).

    Ventana de nivel superior única por `VisorVideos` (nunca se crea ni destruye
    por hover). Muestra el pixmap original ya cargado en memoria, escalado a
    ~1.6x del tamaño configurado, sin leer disco ni regenerar miniaturas.
    """

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self._pixmap = None
        self._tam_amp = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._etiqueta = QLabel()
        self._etiqueta.setStyleSheet(
            "border: 2px solid #333; background-color: #ffffff;"
        )
        self._etiqueta.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._etiqueta)
        self.hide()

    def preparar(self, pixmap):
        ancho, alto = dimensiones_miniatura()
        ancho_amp = int(ancho * FACTOR_VISTA_AMPLIADA_ACTUAL)
        alto_amp = int(alto * FACTOR_VISTA_AMPLIADA_ACTUAL)
        if (
            self._pixmap is pixmap
            and self.isVisible()
            and self._tam_amp == (ancho_amp, alto_amp)
        ):
            return True
        self._pixmap = pixmap
        self._tam_amp = (ancho_amp, alto_amp)
        self._etiqueta.setPixmap(
            pixmap.scaled(
                ancho_amp,
                alto_amp,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.adjustSize()
        return False

    def ocultar(self):
        self._pixmap = None
        self._tam_amp = None
        self.hide()


RETARDOS_VISTA_AMPLIADA = (0, 250, 400, 600)
TEXTOS_RETARDO_VISTA_AMPLIADA = (
    "Inmediato",
    "250 ms",
    "400 ms",
    "600 ms",
)


class PreferenciasDialog(QDialog):
    """Diálogo modal de preferencias (Etapa B3.5).

    En esta primera versión contiene únicamente el retardo de la vista
    ampliada, con valores discretos. La infraestructura está preparada para
    incorporar más preferencias sin rediseñar la ventana principal.
    """

    def __init__(self, ruta_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self._ruta_config = ruta_config
        layout = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Retardo de la vista ampliada:"))
        self.combo_retardo = QComboBox()
        self.combo_retardo.addItems(list(TEXTOS_RETARDO_VISTA_AMPLIADA))
        self.combo_retardo.setCurrentIndex(
            self._indice_retardo(
                obtener_retardo_vista_ampliada(ruta_config)
            )
        )
        fila.addWidget(self.combo_retardo)
        fila.addStretch()
        layout.addLayout(fila)
        fila2 = QHBoxLayout()
        fila2.addWidget(QLabel("Tamaño de la vista ampliada:"))
        self.combo_factor_vista = QComboBox()
        self.combo_factor_vista.addItems(list(TEXTOS_FACTOR_VISTA_AMPLIADA))
        self.combo_factor_vista.setCurrentIndex(
            self._indice_factor(
                obtener_tamano_vista_ampliada(ruta_config)
            )
        )
        fila2.addWidget(self.combo_factor_vista)
        fila2.addStretch()
        layout.addLayout(fila2)
        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _indice_retardo(self, ms):
        if ms in RETARDOS_VISTA_AMPLIADA:
            return RETARDOS_VISTA_AMPLIADA.index(ms)
        return RETARDOS_VISTA_AMPLIADA.index(400)

    def retardo_seleccionado(self):
        indice = self.combo_retardo.currentIndex()
        if 0 <= indice < len(RETARDOS_VISTA_AMPLIADA):
            return RETARDOS_VISTA_AMPLIADA[indice]
        return 400

    def _indice_factor(self, factor):
        if factor in FACTORES_VISTA_AMPLIADA:
            return FACTORES_VISTA_AMPLIADA.index(factor)
        return FACTORES_VISTA_AMPLIADA.index(1.6)

    def factor_vista_seleccionado(self):
        indice = self.combo_factor_vista.currentIndex()
        if 0 <= indice < len(FACTORES_VISTA_AMPLIADA):
            return FACTORES_VISTA_AMPLIADA[indice]
        return 1.6


class Tarjeta(QFrame):
    doble_clic = Signal(str)
    seleccionada = Signal(str, bool)
    seleccion_por_rango = Signal(str)
    menu_contextual = Signal(str)
    vista_solicitada = Signal(object)
    vista_abandonada = Signal()
    seleccion_check = Signal(str, bool)

    def __init__(self, fila, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QHBoxLayout(self)

        nombre, duracion, ancho, alto, codec, miniaturas, tamano = fila

        resolucion = "No disponible"
        if ancho is not None and alto is not None:
            resolucion = f"{ancho}x{alto}"

        duracion_texto = "No disponible"
        if _duracion_valida(duracion):
            duracion_texto = formatear_tiempo(duracion)

        campos = [
            ("Nombre", nombre),
            ("Duración", duracion_texto),
            ("Resolución", resolucion),
            ("Codec", formatear_valor(codec)),
            ("Miniaturas", formatear_valor(miniaturas)),
            ("Tamaño", formatear_tamano(tamano)),
        ]
        columna_campos = QVBoxLayout()
        for etiqueta, valor in campos:
            campo = QLabel(f"<b>{etiqueta}:</b> {valor}")
            campo.setWordWrap(True)
            columna_campos.addWidget(campo)
        columna_campos.addStretch()
        datos_widget = QWidget()
        datos_widget.setMaximumWidth(240)
        datos_widget.setLayout(columna_campos)
        layout.addWidget(datos_widget)

        self._nombre = nombre
        self._duracion = duracion
        self._seleccionada = False
        self._etiquetas_previews = []
        self._imagen_miniatura = None
        self._miniatura_original = None
        self._recuadro_sin_miniatura = None

        contenedor_imagenes = QHBoxLayout()
        contenedor_imagenes.setContentsMargins(0, 0, 0, 0)
        contenedor_imagenes.setSpacing(6)
        self._contenedor_imagenes = contenedor_imagenes

        ancho, alto = dimensiones_miniatura()
        ruta_miniatura = miniatura_principal(nombre)
        if ruta_miniatura is not None:
            imagen = QLabel()
            pixmap = _pixmap_acotado(QPixmap(ruta_miniatura))
            imagen.setPixmap(
                pixmap.scaled(
                    ancho,
                    alto,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            imagen.setFixedHeight(alto)
            imagen.setAlignment(Qt.AlignCenter)
            self._imagen_miniatura = imagen
            self._miniatura_original = pixmap
            contenedor_imagenes.addWidget(imagen)
        else:
            recuadro = QLabel("Sin miniatura")
            recuadro.setFixedSize(ancho, alto)
            recuadro.setAlignment(Qt.AlignCenter)
            recuadro.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")
            self._recuadro_sin_miniatura = recuadro
            contenedor_imagenes.addWidget(recuadro)

        for _ in range(escanear_videos.CANTIDAD_PREVIEWS):
            etiqueta = PreviewConTiempo()
            etiqueta.setText("Generando preview…")
            self._etiquetas_previews.append(etiqueta)
            contenedor_imagenes.addWidget(etiqueta)

        if self._imagen_miniatura is not None:
            self._imagen_miniatura.installEventFilter(self)
        for etiqueta in self._etiquetas_previews:
            etiqueta.installEventFilter(self)

        contenedor_imagenes.addStretch()
        layout.addLayout(contenedor_imagenes, 1)

        self._check = QCheckBox()
        self._check.setVisible(False)
        self._check.stateChanged.connect(self._al_check_cambiar)
        layout.insertWidget(0, self._check)

    @property
    def nombre(self):
        return self._nombre

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            if shift:
                self.seleccion_por_rango.emit(self._nombre)
            else:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                self.seleccionada.emit(self._nombre, ctrl)
        elif event.button() == Qt.RightButton:
            if not self._seleccionada:
                self.seleccionada.emit(self._nombre, False)
            self.menu_contextual.emit(self._nombre)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.doble_clic.emit(self._nombre)

    def marcar_seleccionada(self, valor):
        self._seleccionada = valor
        if valor:
            self.setStyleSheet(ESTILO_SELECCIONADA)
        else:
            self.setStyleSheet("")

    def _al_check_cambiar(self, _estado):
        self.seleccion_check.emit(self._nombre, self._check.isChecked())

    def mostrar_check(self, visible):
        self._check.setVisible(visible)

    def set_check(self, marcado):
        self._check.blockSignals(True)
        self._check.setChecked(bool(marcado))
        self._check.blockSignals(False)

    def _colocar_preview(self, indice, ruta):
        if not (0 <= indice < len(self._etiquetas_previews)):
            return False
        etiqueta = self._etiquetas_previews[indice]
        pixmap = QPixmap(ruta)
        if pixmap.isNull():
            return False
        tiempo = None
        duracion = self._duracion
        if _duracion_valida(duracion):
            tiempo = formatear_tiempo(calcular_tiempo_preview(duracion, indice + 1))
        return etiqueta.poner_preview(pixmap, tiempo)

    def actualizar_previews(self, rutas):
        if rutas is None:
            return False
        if isinstance(rutas, str):
            rutas = [rutas]
        actualizado = False
        for indice in range(min(len(self._etiquetas_previews), len(rutas))):
            if self._colocar_preview(indice, rutas[indice]):
                actualizado = True
        return actualizado

    def _asegurar_slots_previews(self, cantidad):
        while len(self._etiquetas_previews) < cantidad:
            etiqueta = PreviewConTiempo()
            etiqueta.setText("Generando preview…")
            etiqueta.installEventFilter(self)
            self._etiquetas_previews.append(etiqueta)
            self._contenedor_imagenes.insertWidget(
                self._contenedor_imagenes.count() - 1, etiqueta
            )

    def ajustar_previews(self, cantidad):
        self._asegurar_slots_previews(cantidad)
        existentes = previews_de(self._nombre) or []
        for i, etiqueta in enumerate(self._etiquetas_previews):
            etiqueta.setVisible(i < cantidad)
        self.actualizar_previews(existentes[:cantidad])

    def aplicar_tamano(self):
        ancho, alto = dimensiones_miniatura()
        if self._imagen_miniatura is not None and self._miniatura_original is not None:
            self._imagen_miniatura.setPixmap(
                self._miniatura_original.scaled(
                    ancho,
                    alto,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self._imagen_miniatura.setFixedHeight(alto)
        if self._recuadro_sin_miniatura is not None:
            self._recuadro_sin_miniatura.setFixedSize(ancho, alto)
        for etiqueta in self._etiquetas_previews:
            etiqueta.reajustar()

    def _pixmap_ampliada(self, objeto):
        if objeto is self._imagen_miniatura:
            return self._miniatura_original
        if isinstance(objeto, PreviewConTiempo):
            return objeto._pixmap_original
        return None

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Enter:
            pixmap = self._pixmap_ampliada(objeto)
            if pixmap is not None:
                self.vista_solicitada.emit(pixmap)
        elif evento.type() == QEvent.Leave:
            self.vista_abandonada.emit()
        return super().eventFilter(objeto, evento)


class PanelPrincipal(QWidget):
    """Panel derecho del QSplitter que contiene toda la interfaz principal.

    Redefine minimumSizeHint() para devolver QSize(0, 0) porque el
    minimumSizeHint calculado por defecto (~720 px) esta dominado por
    la barra de herramientas (fila_carpeta) que contiene 8 widgets.

    Si no se anula, el QSplitter usa ese valor como tamano minimo
    efectivo del panel derecho, lo que bloquea el arrastre del divisor
    hacia la derecha porque el panel ya esta en su minimo.

    Al devolver (0, 0), el QSplitter solo respeta el minimumWidth
    explicito del panel izquierdo (80 px), permitiendo que el divisor
    se arrastre libremente en ambas direcciones.
    """

    def minimumSizeHint(self):
        return QSize(0, 0)


class VisorVideos(QMainWindow):
    def __init__(self, ruta_db=None, parent=None, ruta_config=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de videos")
        self.tarjetas = []
        self.visibles = []
        self._ruta_db = ruta_db
        self._ruta_config = ruta_config
        self._carga_completada = False
        self.tarea_lectura = None
        self.carpeta_seleccionada = None
        self._escaneo_pendiente = False
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.videos_detectados = None
        self.registros_guardados = None
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = None
        self.carpetas_escaneadas = set()
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = None
        self._cola_previews = []
        self.tarea_previews = None
        self.gestor_previews = None
        self._pipeline_activo = False
        self._nombres_seleccionados = set()
        self._ancla_seleccion = None
        self._modo_seleccion = False

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()
        self.resumen_seleccion = QLabel()
        self.estado_carga = QLabel(MENSAJE_CARGANDO)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setFixedHeight(24)

        self.boton_seleccionar_carpeta = QPushButton("Seleccionar carpeta")
        self.boton_seleccionar_carpeta.clicked.connect(self.seleccionar_carpeta)

        self.boton_escanear = QPushButton("Escanear carpeta")
        self.boton_escanear.setEnabled(False)
        self.boton_escanear.clicked.connect(self.iniciar_escaneo)

        self.incluir_subcarpetas = QCheckBox("Incluir subcarpetas")
        self.incluir_subcarpetas.stateChanged.connect(self._al_cambiar_subcarpetas)

        self.escaneo_automatico = QCheckBox("Escaneo automático")
        self.escaneo_automatico.stateChanged.connect(
            self._al_cambiar_escaneo_automatico
        )

        self.etiqueta_cantidad_previews = QLabel("Previews:")
        self.combo_cantidad_previews = QComboBox()
        self.combo_cantidad_previews.addItems(["3", "5", "7", "9"])
        self.combo_cantidad_previews.currentIndexChanged.connect(
            self._al_cambiar_cantidad_previews
        )

        self.etiqueta_tamano_miniaturas = QLabel("Tamaño:")
        self.combo_tamano_miniaturas = QComboBox()
        self.combo_tamano_miniaturas.addItems(
            ["Pequeño", "Mediano", "Grande", "Muy grande"]
        )
        self.combo_tamano_miniaturas.currentIndexChanged.connect(
            self._al_cambiar_tamano_miniaturas
        )

        self.boton_preferencias = QPushButton("Preferencias…")
        self.boton_preferencias.clicked.connect(self._abrir_preferencias)

        self.boton_modo_seleccion = QPushButton("Modo selección")
        self.boton_modo_seleccion.setCheckable(True)
        self.boton_modo_seleccion.toggled.connect(
            self._al_cambiar_modo_seleccion
        )

        self.boton_cargar_mas = QPushButton("Cargar más")
        self.boton_cargar_mas.setEnabled(False)
        self.boton_cargar_mas.clicked.connect(self.cargar_mas)

        self.etiqueta_carpeta = QLabel(MENSAJE_SIN_CARPETA)
        self.etiqueta_carpeta.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.estado_escaneo = QLabel(MENSAJE_SIN_ESCANEO)

        self.mensaje_carpeta = QLabel()
        self.mensaje_carpeta.setStyleSheet("color: #b00020;")

        fila_carpeta = QHBoxLayout()
        fila_carpeta.addWidget(self.boton_seleccionar_carpeta)
        fila_carpeta.addWidget(self.boton_escanear)
        fila_carpeta.addWidget(self.incluir_subcarpetas)
        fila_carpeta.addWidget(self.escaneo_automatico)
        fila_carpeta.addWidget(self.etiqueta_cantidad_previews)
        fila_carpeta.addWidget(self.combo_cantidad_previews)
        fila_carpeta.addWidget(self.etiqueta_tamano_miniaturas)
        fila_carpeta.addWidget(self.combo_tamano_miniaturas)
        fila_carpeta.addWidget(self.boton_preferencias)
        fila_carpeta.addWidget(self.boton_modo_seleccion)
        fila_carpeta.addWidget(self.etiqueta_carpeta, 1)
        fila_carpeta.addWidget(self.estado_escaneo)
        fila_carpeta.addWidget(self.mensaje_carpeta)

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.contador)
        barra.addWidget(self.resumen_seleccion)
        barra.addWidget(self.boton_cargar_mas)
        barra.addWidget(self.estado_carga)

        self.contenedor = QWidget()
        self.cuadricula = QGridLayout(self.contenedor)
        self.cuadricula.setColumnStretch(0, 1)
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        raiz = PanelPrincipal()
        layout = QVBoxLayout(raiz)
        layout.addLayout(fila_carpeta)
        layout.addLayout(barra)
        layout.addWidget(self.barra_progreso)
        layout.addWidget(self.area)

        panel_izquierdo = QWidget()
        panel_izquierdo.setMinimumWidth(80)
        panel_izquierdo.setMaximumWidth(400)
        panel_izquierdo.setStyleSheet("background-color: #e8e8e8;")
        layout_izquierdo = QVBoxLayout(panel_izquierdo)
        layout_izquierdo.setContentsMargins(0, 0, 0, 0)
        self.arbol_navegacion = ArbolNavegacion()
        self.arbol_navegacion.ruta_seleccionada.connect(
            self._al_carpeta_actual_arbol
        )
        layout_izquierdo.addWidget(self.arbol_navegacion)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        splitter.addWidget(panel_izquierdo)
        splitter.addWidget(raiz)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 680])
        splitter.setCollapsible(0, False)
        self.setCentralWidget(splitter)

        self.gestor = GestorTareas(self)
        self.gestor.tarea_resultado.connect(self._al_resultado)
        self.gestor.tarea_error.connect(self._al_error)
        self.gestor.tarea_finalizada.connect(self._al_tarea_finalizada)
        self.gestor.actividad_cambiada.connect(self._al_actividad)

        self.gestor_previews = GestorTareas(self)
        self.gestor_previews.tarea_resultado.connect(self._al_resultado_previews)
        self.gestor_previews.tarea_error.connect(self._al_error_previews)
        self.gestor_previews.tarea_finalizada.connect(self._al_previews_finalizada)

        self._timer_previews = QTimer(self)
        self._timer_previews.setSingleShot(True)
        self._timer_previews.setInterval(300)
        self._timer_previews.timeout.connect(self._iniciar_previews)

        self._vista = VistaAmpliada(self)
        self._vista_pendiente = None
        self._timer_vista_mostrar = QTimer(self)
        self._timer_vista_mostrar.setSingleShot(True)
        self._timer_vista_mostrar.setInterval(
            obtener_retardo_vista_ampliada(self._ruta_config)
        )
        configurar_factor_vista_ampliada(
            obtener_tamano_vista_ampliada(self._ruta_config)
        )
        self._timer_vista_mostrar.timeout.connect(self._mostrar_vista_diferida)
        self._timer_vista_ocultar = QTimer(self)
        self._timer_vista_ocultar.setSingleShot(True)
        self._timer_vista_ocultar.setInterval(RETARDO_OCULTAR_VISTA_MS)
        self._timer_vista_ocultar.timeout.connect(self._vista.ocultar)
        self.area.verticalScrollBar().valueChanged.connect(self._ocultar_vista)
        carpeta_guardada = obtener_ultima_carpeta(self._ruta_config)
        if carpeta_guardada is not None:
            self.carpeta_seleccionada = carpeta_guardada
            self.etiqueta_carpeta.setText(carpeta_guardada)
            if not self.arbol_navegacion.revelar_ruta(carpeta_guardada):
                self.carpeta_seleccionada = None
                self.etiqueta_carpeta.setText(MENSAJE_SIN_CARPETA)
            self._actualizar_botones_carpeta()
        self.incluir_subcarpetas.setChecked(
            obtener_preferencia_subcarpetas(self._ruta_config)
        )
        self.escaneo_automatico.setChecked(
            obtener_preferencia_escaneo_automatico(self._ruta_config)
        )
        cantidad = obtener_cantidad_previews(self._ruta_config)
        idx = self.combo_cantidad_previews.findText(str(cantidad))
        if idx >= 0:
            self.combo_cantidad_previews.setCurrentIndex(idx)
        configurar_cantidad_previews(cantidad)
        tamano = obtener_tamano_miniaturas(self._ruta_config)
        idx_tamano = self.combo_tamano_miniaturas.findText(
            texto_tamano_miniaturas(tamano)
        )
        self.combo_tamano_miniaturas.blockSignals(True)
        if idx_tamano >= 0:
            self.combo_tamano_miniaturas.setCurrentIndex(idx_tamano)
        self.combo_tamano_miniaturas.blockSignals(False)
        configurar_tamano_miniaturas(tamano)
        self._iniciar_carga()

    def _iniciar_carga(self):
        self.tarea_lectura = self._crear_tarea_lectura()
        self.gestor.iniciar(self.tarea_lectura)

    def _al_cambiar_subcarpetas(self, _estado):
        guardar_preferencia_subcarpetas(
            self.incluir_subcarpetas.isChecked(), self._ruta_config
        )

    def _al_cambiar_escaneo_automatico(self, _estado):
        guardar_preferencia_escaneo_automatico(
            self.escaneo_automatico.isChecked(), self._ruta_config
        )

    def _al_cambiar_cantidad_previews(self, _indice):
        texto = self.combo_cantidad_previews.currentText()
        try:
            n = int(texto)
        except (ValueError, TypeError):
            return
        guardar_cantidad_previews(n, self._ruta_config)
        configurar_cantidad_previews(n)
        for _, tarjeta in self.tarjetas:
            tarjeta.ajustar_previews(n)
        self._programar_previews()

    def _al_cambiar_tamano_miniaturas(self, _indice):
        nombre = clave_tamano_miniaturas(
            self.combo_tamano_miniaturas.currentText()
        )
        configurar_tamano_miniaturas(nombre)
        guardar_tamano_miniaturas(nombre, self._ruta_config)
        for _, tarjeta in self.tarjetas:
            tarjeta.aplicar_tamano()

    def _al_vista_solicitada(self, pixmap):
        if pixmap is None or pixmap.isNull():
            return
        self._timer_vista_ocultar.stop()
        if self._vista.isVisible() and self._vista._pixmap is not pixmap:
            self._vista.ocultar()
        self._vista_pendiente = pixmap
        self._timer_vista_mostrar.start()

    def _al_vista_abandonada(self):
        self._timer_vista_mostrar.stop()
        self._vista_pendiente = None
        self._timer_vista_ocultar.start()

    def _mostrar_vista_diferida(self):
        pixmap = self._vista_pendiente
        if pixmap is None or pixmap.isNull():
            return
        reutilizada = self._vista.preparar(pixmap)
        self._vista.move(self._posicion_vista())
        if not reutilizada:
            self._vista.show()
            self._vista.raise_()

    def _posicion_vista(self):
        cursor = QCursor.pos()
        pantalla = QApplication.primaryScreen().availableGeometry()
        margen = 16
        ancho = self._vista.width()
        alto = self._vista.height()
        x = cursor.x() + margen
        y = cursor.y() + margen
        if x + ancho > pantalla.right():
            x = cursor.x() - ancho - margen
        if y + alto > pantalla.bottom():
            y = cursor.y() - alto - margen
        x = max(pantalla.left(), min(x, pantalla.right() - ancho))
        y = max(pantalla.top(), min(y, pantalla.bottom() - alto))
        return QPoint(x, y)

    def _ocultar_vista(self, _valor=None):
        self._timer_vista_mostrar.stop()
        self._timer_vista_ocultar.stop()
        self._vista_pendiente = None
        self._vista.ocultar()

    def _abrir_preferencias(self):
        dialogo = PreferenciasDialog(self._ruta_config, self)
        if dialogo.exec() == QDialog.Accepted:
            self._aplicar_retardo_vista_ampliada(dialogo.retardo_seleccionado())
            self._aplicar_tamano_vista_ampliada(
                dialogo.factor_vista_seleccionado()
            )

    def _aplicar_retardo_vista_ampliada(self, ms):
        guardar_retardo_vista_ampliada(ms, self._ruta_config)
        self._timer_vista_mostrar.setInterval(ms)

    def _aplicar_tamano_vista_ampliada(self, factor):
        guardar_tamano_vista_ampliada(factor, self._ruta_config)
        configurar_factor_vista_ampliada(factor)

    def _crear_tarea_lectura(self, desplazamiento=0):
        return TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL, desplazamiento, None, self._ruta_db
        )

    def seleccionar_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de videos", ""
        )
        if not ruta:
            self._actualizar_botones_carpeta()
            return
        ruta_absoluta = os.path.abspath(ruta)
        if not os.path.isdir(ruta_absoluta):
            self.mensaje_carpeta.setText(MENSAJE_RUTA_INVALIDA)
            self._actualizar_botones_carpeta()
            return
        self.carpeta_seleccionada = ruta_absoluta
        self.etiqueta_carpeta.setText(ruta_absoluta)
        self.mensaje_carpeta.clear()
        guardar_ultima_carpeta(ruta_absoluta, self._ruta_config)
        self.arbol_navegacion.seleccionar_ruta(ruta_absoluta)
        self._actualizar_botones_carpeta()
        self._disparar_escaneo_si_automatico()

    def _disparar_escaneo_si_automatico(self):
        if self.escaneo_automatico.isChecked():
            self.iniciar_escaneo()

    def _al_carpeta_actual_arbol(self, ruta):
        if not isinstance(ruta, str) or not ruta:
            return
        if not os.path.isdir(ruta):
            return
        if self.carpeta_seleccionada == ruta:
            return
        self.carpeta_seleccionada = ruta
        self.etiqueta_carpeta.setText(ruta)
        self.mensaje_carpeta.clear()
        guardar_ultima_carpeta(ruta, self._ruta_config)
        self._actualizar_botones_carpeta()
        self._disparar_escaneo_si_automatico()

    def _actualizar_botones_carpeta(self):
        carpeta_valida = (
            self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        cadena_activa = (
            self._escaneo_pendiente
            or self._tamanos_pendiente
            or self._ffprobe_pendiente
            or self._miniaturas_pendiente
            or self._guardado_pendiente
            or self._sincronizacion_pendiente
            or self._recarga_catalogo_pendiente
            or self._pagina_pendiente
        )
        self.boton_seleccionar_carpeta.setEnabled(not cadena_activa)
        self.boton_escanear.setEnabled(
            carpeta_valida and not self.gestor.activo and not cadena_activa
        )
        hay_mas = (
            self._carga_completada
            and self._total_catalogo is not None
            and len(self.tarjetas) < self._total_catalogo
            and not self.gestor.activo
            and not cadena_activa
        )
        self.boton_cargar_mas.setEnabled(hay_mas)

    def _al_actividad(self, activo):
        self._actualizar_botones_carpeta()

    def _mostrar_progreso(self, texto):
        self._pipeline_activo = True
        self.barra_progreso.setFormat(texto)
        self.barra_progreso.setVisible(True)

    def _ocultar_progreso(self):
        self._pipeline_activo = False
        self.barra_progreso.setVisible(False)

    def _al_seleccionar_tarjeta(self, nombre, ctrl):
        if not ctrl:
            self._limpiar_seleccion()
        if nombre in self._nombres_seleccionados:
            self._nombres_seleccionados.discard(nombre)
            self._marcar_tarjeta(nombre, False)
        else:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        self._ancla_seleccion = nombre if self._nombres_seleccionados else None

    def _al_seleccion_por_rango(self, nombre):
        visibles = self.tarjetas_visibles()
        if self._ancla_seleccion is None or self._ancla_seleccion not in visibles:
            self._limpiar_seleccion()
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
            self._ancla_seleccion = nombre
            return
        idx_ancla = visibles.index(self._ancla_seleccion)
        idx_objetivo = visibles.index(nombre)
        inicio = min(idx_ancla, idx_objetivo)
        fin = max(idx_ancla, idx_objetivo)
        self._limpiar_seleccion()
        for idx in range(inicio, fin + 1):
            n = visibles[idx]
            self._nombres_seleccionados.add(n)
            self._marcar_tarjeta(n, True)

    def _limpiar_seleccion(self):
        for nombre in list(self._nombres_seleccionados):
            self._marcar_tarjeta(nombre, False)
        self._nombres_seleccionados.clear()
        self._actualizar_resumen_seleccion()

    def _marcar_tarjeta(self, nombre, valor):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                tarjeta.marcar_seleccionada(valor)
                tarjeta.set_check(valor)
                self._actualizar_resumen_seleccion()
                return

    def _al_check_tarjeta(self, nombre, marcado):
        if marcado:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        else:
            self._nombres_seleccionados.discard(nombre)
            self._marcar_tarjeta(nombre, False)

    def _al_cambiar_modo_seleccion(self, activo):
        self._modo_seleccion = bool(activo)
        for _, tarjeta in self.tarjetas:
            tarjeta.mostrar_check(self._modo_seleccion)

    def _actualizar_resumen_seleccion(self):
        visibles = self.visibles
        x = sum(
            1 for nombre in visibles if nombre in self._nombres_seleccionados
        )
        self.resumen_seleccion.setText(
            f"{x} de {len(visibles)} seleccionados"
        )

    @property
    def nombres_seleccionados(self):
        return set(self._nombres_seleccionados)

    def iniciar_escaneo(self):
        if self.gestor.activo:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self.mensaje_carpeta.setText(MENSAJE_RUTA_INVALIDA)
            self._actualizar_botones_carpeta()
            return
        configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())
        tarea = TareaEscaneo(carpeta)
        self._escaneo_pendiente = True
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.registros_guardados = None
        self.resultado_sincronizacion = None
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        if not self.gestor.iniciar(tarea):
            self._escaneo_pendiente = False
            self._actualizar_botones_carpeta()
            return
        self.tarea_escaneo = tarea
        self.estado_escaneo.setText(MENSAJE_ESCANEANDO)
        self._mostrar_progreso("Escaneando…")
        self._actualizar_botones_carpeta()

    def _limpiar_cadena(self):
        self._escaneo_pendiente = False
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self._ocultar_progreso()

    def _al_resultado_escaneo(self, videos):
        self._escaneo_pendiente = False
        self._tamanos_pendiente = True
        self.videos_detectados = list(videos)
        self._mostrar_estado_escaneo()
        self._actualizar_botones_carpeta()

    def _al_error_escaneo(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_ESCANEO)
        self._actualizar_botones_carpeta()

    def _mostrar_estado_escaneo(self):
        if self.videos_detectados is None:
            self.estado_escaneo.setText(MENSAJE_SIN_ESCANEO)
            return
        cantidad = len(self.videos_detectados)
        if cantidad == 1:
            self.estado_escaneo.setText("1 video detectado")
        else:
            self.estado_escaneo.setText(f"{cantidad} videos detectados")

    def _al_resultado(self, resultado):
        if self._escaneo_pendiente:
            self._al_resultado_escaneo(resultado)
            return
        if self._tamanos_pendiente:
            self._al_resultado_tamanos(resultado)
            return
        if self._ffprobe_pendiente:
            self._al_resultado_ffprobe(resultado)
            return
        if self._miniaturas_pendiente:
            self._al_resultado_miniaturas(resultado)
            return
        if self._guardado_pendiente:
            self._al_resultado_guardado(resultado)
            return
        if self._sincronizacion_pendiente:
            self._al_resultado_sincronizacion(resultado)
            return
        if self._recarga_catalogo_pendiente:
            self._al_resultado_recarga(resultado)
            return
        if self._pagina_pendiente:
            self._al_resultado_pagina(resultado)
            return
        if self._carga_completada:
            return
        self.estado_carga.hide()
        self._total_catalogo = resultado.get("total")
        self._crear_tarjetas(resultado.get("videos", []))
        self._carga_completada = True
        self._programar_previews()

    def _iniciar_tamanos(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaTamanosArchivos(
            self.videos_detectados, self.tarea_escaneo.carpeta
        )
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_tamanos = tarea
        self._mostrar_progreso("Obteniendo tamaños…")

    def _al_resultado_tamanos(self, resultado):
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = True
        self.tarea_tamanos = None
        self.resultado_tamanos = resultado
        self._actualizar_botones_carpeta()

    def _al_error_tamanos(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_TAMANOS)
        self._actualizar_botones_carpeta()

    def _iniciar_ffprobe(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        carpeta = self.tarea_escaneo.carpeta
        rutas = [os.path.join(carpeta, nombre) for nombre in self.videos_detectados]
        tarea = TareaFFprobe(rutas)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_ffprobe = tarea
        self._mostrar_progreso("Leyendo metadatos…")

    def _al_resultado_ffprobe(self, resultado):
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = True
        self.tarea_ffprobe = None
        self.resultado_ffprobe = resultado
        self._actualizar_botones_carpeta()

    def _al_error_ffprobe(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_FFPROBE)
        self._actualizar_botones_carpeta()

    def _iniciar_miniaturas(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaMiniaturas(self.videos_detectados, self.tarea_escaneo.carpeta)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_miniaturas = tarea
        self._mostrar_progreso("Generando miniaturas…")

    def _al_resultado_miniaturas(self, resultado):
        self._miniaturas_pendiente = False
        self._guardado_pendiente = True
        self.tarea_miniaturas = None
        self.resultado_miniaturas = resultado
        self._actualizar_botones_carpeta()

    def _al_error_miniaturas(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_MINIATURAS)
        self._actualizar_botones_carpeta()

    def _iniciar_guardado(self):
        if (
            self.tarea_escaneo is None
            or self.videos_detectados is None
            or self.resultado_tamanos is None
            or self.resultado_ffprobe is None
            or self.resultado_miniaturas is None
        ):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        registros = combinar_registros_con_ffprobe(
            self.videos_detectados, self.tarea_escaneo.carpeta, self.resultado_ffprobe
        )
        registros = combinar_registros_con_miniaturas(
            registros, self.resultado_miniaturas
        )
        registros = combinar_registros_con_tamanos(
            registros, self.resultado_tamanos
        )
        tarea = TareaGuardarVideos(registros, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_guardado = tarea
        self._mostrar_progreso("Guardando…")

    def _al_tarea_finalizada(self):
        if self.gestor.estado != Estado.INACTIVO:
            self._limpiar_cadena()
            return
        if self._escaneo_pendiente:
            return
        if self._tamanos_pendiente:
            self._iniciar_tamanos()
            return
        if self._ffprobe_pendiente:
            self._iniciar_ffprobe()
            return
        if self._miniaturas_pendiente:
            self._iniciar_miniaturas()
            return
        if self._guardado_pendiente:
            self._iniciar_guardado()
            return
        if self._sincronizacion_pendiente:
            self._iniciar_sincronizacion()
            return
        if self._recarga_catalogo_pendiente:
            self._iniciar_recarga_catalogo()
            return

    def _iniciar_sincronizacion(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaSincronizacionCatalogo(carpeta, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_sincronizacion = tarea
        self.estado_escaneo.setText(MENSAJE_SINCRONIZANDO)
        self._mostrar_progreso("Sincronizando…")
        self._actualizar_botones_carpeta()

    def _al_resultado_sincronizacion(self, resultado):
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = resultado
        self.estado_escaneo.setText(
            texto_resumen_sincronizacion(resultado.get("resumen"))
        )
        carpeta = resultado.get("diferencias", {}).get("carpeta")
        if isinstance(carpeta, str) and carpeta:
            self.carpetas_escaneadas.add(carpeta)
            self.arbol_navegacion.marcar_carpeta_escaneada(carpeta)
        self._recarga_catalogo_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error_sincronizacion(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_SINCRONIZACION)
        self._actualizar_botones_carpeta()

    def _iniciar_recarga_catalogo(self):
        tarea = self._crear_tarea_lectura()
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
            self._actualizar_botones_carpeta()
            return
        self.tarea_recarga_catalogo = tarea
        self._mostrar_progreso("Actualizando catálogo…")

    def _al_resultado_recarga(self, resultado):
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        self._reemplazar_tarjetas(resultado.get("videos", []))
        self._programar_previews()
        self._ocultar_progreso()
        self._actualizar_botones_carpeta()

    def _al_error_recarga(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
        self._actualizar_botones_carpeta()

    def _reemplazar_tarjetas(self, filas):
        self._ocultar_vista()
        seleccion_previa = set(self._nombres_seleccionados)
        self._limpiar_seleccion()
        self._ancla_seleccion = None
        for nombre, tarjeta in self.tarjetas:
            self.cuadricula.removeWidget(tarjeta)
            tarjeta.deleteLater()
        self.tarjetas = []
        self.visibles = []
        self._crear_tarjetas(filas)
        nombres_nuevos = {nombre for nombre, _ in self.tarjetas}
        for nombre in seleccion_previa:
            if nombre in nombres_nuevos:
                self._nombres_seleccionados.add(nombre)
                self._marcar_tarjeta(nombre, True)

    def cargar_mas(self):
        if self.gestor.activo:
            return
        if not self._carga_completada:
            return
        tarea = self._crear_tarea_lectura(len(self.tarjetas))
        self._pagina_pendiente = True
        self.tarea_pagina = tarea
        if not self.gestor.iniciar(tarea):
            self._pagina_pendiente = False
            self.tarea_pagina = None
            self._actualizar_botones_carpeta()
            return
        self._actualizar_botones_carpeta()

    def _al_resultado_pagina(self, resultado):
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        filas = resultado.get("videos", [])
        existentes = {nombre for nombre, _ in self.tarjetas}
        filas_nuevas = [fila for fila in filas if fila[0] not in existentes]
        self._agregar_tarjetas(filas_nuevas)
        self._programar_previews()
        self._actualizar_botones_carpeta()

    def _al_error_pagina(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_PAGINA)
        self._actualizar_botones_carpeta()

    def _programar_previews(self):
        if not self._carga_completada:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        self._timer_previews.start()

    def _iniciar_previews(self):
        if not self._carga_completada:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        nombres = [nombre for nombre, _ in self.tarjetas]
        if not nombres:
            return
        self._encolar_previews(nombres)
        self._al_previews_finalizada()

    def _encolar_previews(self, nombres):
        con_previews = set()
        for nombre, _ in self.tarjetas:
            existentes = previews_de(nombre) or []
            if len(existentes) >= escanear_videos.CANTIDAD_PREVIEWS:
                con_previews.add(nombre)
        pendientes = set(self._cola_previews)
        for nombre in nombres:
            if nombre in con_previews or nombre in pendientes:
                continue
            self._cola_previews.append(nombre)

    def _al_previews_finalizada(self):
        if self.gestor_previews.estado != Estado.INACTIVO:
            return
        self._siguiente_lote_previews()

    def _siguiente_lote_previews(self):
        if self.gestor_previews.activo:
            return
        lote = []
        while self._cola_previews and len(lote) < TAMANIO_LOTE_PREVIEWS:
            lote.append(self._cola_previews.pop(0))
        if not lote:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self._cola_previews = []
            return
        tarea = TareaPreviewsProgresivas(lote, carpeta)
        if not self.gestor_previews.iniciar(tarea):
            return
        self.tarea_previews = tarea

    def _al_resultado_previews(self, resultado):
        self._aplicar_previews(resultado)

    def _al_error_previews(self, mensaje):
        self._siguiente_lote_previews()

    def _aplicar_previews(self, resultado):
        for item in resultado.get("resultados", []):
            nombre = item.get("nombre")
            rutas = item.get("previews")
            if rutas:
                self.actualizar_previews(nombre, rutas)

    def actualizar_previews(self, nombre, rutas):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                return tarjeta.actualizar_previews(rutas)
        return False

    def _agregar_tarjetas(self, filas):
        inicio = len(self.tarjetas)
        for indice, fila in enumerate(filas):
            posicion = inicio + indice
            tarjeta = Tarjeta(fila)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            tarjeta.vista_solicitada.connect(self._al_vista_solicitada)
            tarjeta.vista_abandonada.connect(self._al_vista_abandonada)
            tarjeta.seleccion_check.connect(self._al_check_tarjeta)
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, posicion, 0)
            rutas_existentes = previews_de(fila[0])
            if rutas_existentes:
                tarjeta.actualizar_previews(rutas_existentes)
        self.filtrar(self.busqueda.text())

    def _al_resultado_guardado(self, resultado):
        self._guardado_pendiente = False
        self.tarea_guardado = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.registros_guardados = resultado.get("guardados")
        self._sincronizacion_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error(self, mensaje):
        if self._escaneo_pendiente:
            self._al_error_escaneo(mensaje)
            return
        if self._tamanos_pendiente:
            self._al_error_tamanos(mensaje)
            return
        if self._ffprobe_pendiente:
            self._al_error_ffprobe(mensaje)
            return
        if self._miniaturas_pendiente:
            self._al_error_miniaturas(mensaje)
            return
        if self._guardado_pendiente:
            self._al_error_guardado(mensaje)
            return
        if self._sincronizacion_pendiente:
            self._al_error_sincronizacion(mensaje)
            return
        if self._recarga_catalogo_pendiente:
            self._al_error_recarga(mensaje)
            return
        if self._pagina_pendiente:
            self._al_error_pagina(mensaje)
            return
        if self._carga_completada:
            return
        self.estado_carga.setText(MENSAJE_ERROR)
        self._carga_completada = True

    def _al_error_guardado(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_GUARDADO)
        self._actualizar_botones_carpeta()

    def _crear_tarjetas(self, filas):
        for indice, fila in enumerate(filas):
            tarjeta = Tarjeta(fila)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            tarjeta.vista_solicitada.connect(self._al_vista_solicitada)
            tarjeta.vista_abandonada.connect(self._al_vista_abandonada)
            tarjeta.seleccion_check.connect(self._al_check_tarjeta)
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice, 0)
            rutas_existentes = previews_de(fila[0])
            if rutas_existentes:
                tarjeta.actualizar_previews(rutas_existentes)
        self.filtrar(self.busqueda.text())

    def _abrir_video(self, nombre):
        carpeta = self.carpeta_seleccionada
        try:
            abrir_video_con_aplicacion_predeterminada(nombre, carpeta)
        except (ValueError, FileNotFoundError, OSError):
            self.mensaje_carpeta.setText(MENSAJE_ERROR_ABRIR)
            return
        self.mensaje_carpeta.clear()

    def _mostrar_menu_contextual(self, nombre):
        menu = QMenu(self)
        accion_abrir = menu.addAction("Abrir")
        accion_abrir_carpeta = menu.addAction("Abrir carpeta")
        accion_copiar_ruta = menu.addAction("Copiar ruta")
        accion_copiar_seleccionados = menu.addAction("Copiar rutas de los seleccionados")
        accion_abrir_seleccionados = menu.addAction("Abrir carpetas de los seleccionados")
        accion_abrir.triggered.connect(lambda: self._abrir_video(nombre))
        accion_abrir_carpeta.triggered.connect(lambda: self._abrir_carpeta(nombre))
        accion_copiar_ruta.triggered.connect(lambda: self._copiar_ruta(nombre))
        accion_copiar_seleccionados.triggered.connect(self._copiar_rutas_seleccionados)
        accion_abrir_seleccionados.triggered.connect(self._abrir_carpetas_seleccionados)
        menu.exec(QCursor.pos())

    def _abrir_carpeta(self, nombre):
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            os.startfile(carpeta)

    def _copiar_ruta(self, nombre):
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            ruta = os.path.abspath(os.path.join(carpeta, nombre))
            QApplication.clipboard().setText(ruta)

    def _copiar_rutas_seleccionados(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        rutas = []
        for nombre in self.tarjetas_visibles():
            if nombre in self._nombres_seleccionados:
                rutas.append(os.path.abspath(os.path.join(carpeta, nombre)))
        if rutas:
            QApplication.clipboard().setText("\n".join(rutas))

    def _abrir_carpetas_seleccionados(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        carpetas = []
        for nombre in self.tarjetas_visibles():
            if nombre in self._nombres_seleccionados:
                ruta = os.path.abspath(os.path.join(carpeta, nombre))
                carpetas.append(os.path.dirname(ruta))
        for c in dict.fromkeys(carpetas):
            os.startfile(c)

    def filtrar(self, texto):
        texto = texto.lower()
        visibles = []
        for nombre, tarjeta in self.tarjetas:
            coincide = texto in nombre.lower()
            tarjeta.setVisible(coincide)
            if coincide:
                visibles.append(nombre)
        self.visibles = visibles
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()

    def tarjetas_visibles(self):
        return list(self.visibles)

    def actualizar_contador(self):
        cantidad = len(self.tarjetas_visibles())
        palabra = "video" if cantidad == 1 else "videos"
        self.contador.setText(f"{cantidad} {palabra}")

    def closeEvent(self, event):
        self._timer_previews.stop()
        self._ocultar_vista()
        self.gestor.cerrar()
        if self.gestor_previews is not None:
            self.gestor_previews.cerrar()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(900, 600)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
